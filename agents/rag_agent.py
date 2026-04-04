"""
RAG Agent - Retrieval Augmented Generation
Semantic search over business documents with LLM-powered answer generation

Features:
- Multi-model fallback (Gemini Flash -> Groq -> Ollama)
- Circuit breaker integration (quota tracker)
- Source citation extraction
- Multi-document synthesis
- Context window management
- Error recovery
- Gemini Pro feature flag (disabled by default)
"""

import os
# ✨ Fix tokenizer parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings as ChromaSettings
import sys
sys.path.append(str(Path(__file__).parent.parent))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
import ollama

from config.settings import settings
from utils.quota_tracker import get_tracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize quota tracker
quota_tracker = get_tracker()


class RAGAgent:
    """
    RAG Agent for document Q&A with semantic search and LLM generation
    """
    # ✨ Model-specific context limits (in tokens)
    MODEL_CONTEXT_LIMITS = {
        "gemini-2.5-pro": 20000,
        "gemini-2.5-flash": 16000,
        "llama-3.3-70b-versatile": 10000,
        "deepseek-r1:1.5b": 4000
    }
    
    DEFAULT_CONTEXT_LIMIT = 8000
    # ✨ Model configurations - Different priorities for different query types
    MODELS = {
        "complex": [
            # Complex queries need SMARTER models first
            # Multi-document synthesis, comparisons, analysis
            {
                "name": "gemini-2.5-flash",
                "type": "gemini",
                "description": "Gemini 2.5 Flash (Smart + Fast)",
                "quota": "1,500/day",
                "priority_reason": "Best for complex document synthesis"
            },
            {
                "name": "llama-3.3-70b-versatile",
                "type": "groq",
                "description": "Groq Llama 3.3 70B (Fallback)",
                "quota": "14,400/day",
                "priority_reason": "Good comprehension, very fast"
            },
            {
                "name": "deepseek-r1:1.5b",
                "type": "ollama",
                "description": "Ollama DeepSeek-R1 (Local Backup)",
                "quota": "Unlimited",
                "priority_reason": "Always available, basic capability"
            }
        ],
        "simple": [
            # Simple queries prioritize SPEED over smarts
            # Single fact lookup, direct answers
            {
                "name": "llama-3.3-70b-versatile",
                "type": "groq",
                "description": "Groq Llama 3.3 70B (Fastest)",
                "quota": "14,400/day",
                "priority_reason": "Fastest response for simple lookups"
            },
            {
                "name": "gemini-2.5-flash",
                "type": "gemini",
                "description": "Gemini 2.5 Flash (Reliable)",
                "quota": "1,500/day",
                "priority_reason": "Reliable fallback"
            },
            {
                "name": "deepseek-r1:1.5b",
                "type": "ollama",
                "description": "Ollama DeepSeek-R1 (Local Backup)",
                "quota": "Unlimited",
                "priority_reason": "Always available"
            }
        ]
    }
    
    def __init__(self):
        """Initialize RAG agent with embedding model, vector DB, and LLM clients"""
        
        logger.info("Initializing RAG Agent...")
        
        # Initialize embedding model (same as setup)
        logger.info("Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        
        # Initialize ChromaDB
        chroma_dir = Path(settings.chroma_persist_directory)
        if not chroma_dir.exists():
            raise FileNotFoundError(
                f"ChromaDB directory not found: {chroma_dir}\n"
                "Run database/setup_rag_pipeline.py first!"
            )
        
        logger.info(f"Connecting to ChromaDB at {chroma_dir}...")
        self.chroma_client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        try:
            self.collection = self.chroma_client.get_collection("nexusiq_docs")
            logger.info(f"Connected to collection with {self.collection.count()} documents")
        except Exception as e:
            raise Exception(f"Collection 'nexusiq_docs' not found. Run setup_rag_pipeline.py first! Error: {e}")
        
        # Initialize LLM clients
        self._init_llm_clients()
        self._init_bm25_index()
        
        logger.info("RAG Agent initialized successfully!")
    
    def _init_bm25_index(self):
        """Initialize BM25 keyword index from ChromaDB documents"""
        from rank_bm25 import BM25Okapi
        
        logger.info("Building BM25 index for hybrid search...")
        
        # Get all documents from ChromaDB
        all_docs = self.collection.get(
            limit=self.collection.count(),
            include=["documents", "metadatas"]
        )
        
        self.bm25_documents = all_docs['documents']
        self.bm25_metadatas = all_docs['metadatas']
        self.bm25_ids = all_docs['ids']
        
        # Tokenize documents for BM25
        tokenized_docs = [doc.lower().split() for doc in self.bm25_documents]
        self.bm25_index = BM25Okapi(tokenized_docs)
        
        logger.info(f"✅ BM25 index built with {len(self.bm25_documents)} documents")
    
    def _init_llm_clients(self):
        """Initialize LLM clients for answer generation with feature flags"""
        
        # ✨ Gemini Pro (conditional - disabled by default)
        if settings.google_api_key and settings.use_gemini_pro:
            self.gemini_pro = ChatGoogleGenerativeAI(
                model=settings.gemini_pro_model,
                google_api_key=settings.google_api_key,
                temperature=0.3,
                max_retries=settings.gemini_pro_max_retries,
                timeout=settings.gemini_pro_timeout
            )
            logger.info("✅ Gemini Pro initialized (use_gemini_pro=True)")
        else:
            self.gemini_pro = None
            if settings.google_api_key:
                logger.info("⚠️  Gemini Pro DISABLED (use_gemini_pro=False)")
        
        # ✨ Gemini Flash (always available if key exists)
        if settings.google_api_key:
            self.gemini_flash = ChatGoogleGenerativeAI(
                model=settings.gemini_flash_model,
                google_api_key=settings.google_api_key,
                temperature=0.3,
                max_retries=settings.gemini_flash_max_retries,
                timeout=settings.gemini_flash_timeout
            )
            logger.info("✅ Gemini Flash initialized")
        else:
            self.gemini_flash = None
            logger.warning("⚠️  No Google API key - Gemini unavailable")
        
        # ✨ Groq client
        if settings.groq_api_key:
            self.groq_client = ChatGroq(
                model=settings.groq_model,
                groq_api_key=settings.groq_api_key,
                temperature=0.3
            )
            logger.info("✅ Groq client initialized")
        else:
            self.groq_client = None
            logger.warning("⚠️  No Groq API key - Groq unavailable")
        
        # Ollama (always available if running locally)
        logger.info("✅ Ollama client ready (local)")
    
    def search_documents(
        self, 
        query: str, 
        n_results: int = 5,
        similarity_threshold: float = None,
        metadata_filter: dict = None  # ✅ NEW: Optional metadata filter
    ) -> List[Dict]:
        """
        Semantic search with optional metadata filtering
        """
        
        if similarity_threshold is None:
            similarity_threshold = self._get_adaptive_threshold(query)
        
        logger.info(f"Searching documents for: '{query}' (threshold: {similarity_threshold:.2f})")
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(
            query, 
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        # ✅ Build ChromaDB query with optional metadata filter
        query_params = {
            "query_embeddings": [query_embedding.tolist()],
            "n_results": n_results
        }
        
        # ✅ Add metadata filter if provided
        if metadata_filter:
            query_params["where"] = metadata_filter
            logger.info(f"  Applied metadata filter: {metadata_filter}")
        
        # Search ChromaDB
        results = self.collection.query(**query_params)
        
        # Parse results (rest stays the same)
        chunks = []
        
        if not results['documents'] or not results['documents'][0]:
            logger.warning("No results found in ChromaDB")
            return chunks
        
        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            similarity = 1 - distance
            
            if similarity < similarity_threshold:
                continue
            
            page_info = metadata.get('page', 'Unknown')
            if metadata.get('page_start') and metadata.get('page_end'):
                if metadata['page_start'] != metadata['page_end']:
                    page_info = f"{metadata['page_start']}-{metadata['page_end']}"
            
            chunks.append({
                'text': doc,
                'filename': metadata.get('filename', 'Unknown'),
                'category': metadata.get('category', 'Unknown'),
                'page': page_info,
                'chunk_id': metadata.get('chunk_id', i),
                'similarity': round(similarity, 3)
            })
        
        logger.info(f"Retrieved {len(chunks)} relevant chunks (threshold: {similarity_threshold:.2f})")
        
        return chunks
    
    def _get_adaptive_threshold(self, query: str, base_threshold: float = 0.3) -> float:
        """
        ✅ NEW: Adjust similarity threshold based on query characteristics
        
        - Comparative queries → Lower threshold (need multiple docs)
        - Specific fact queries → Higher threshold (need precise match)
        - Broad overview queries → Lower threshold (need variety)
        
        Args:
            query: User question
            base_threshold: Default threshold (0.3)
        
        Returns:
            Adjusted threshold (0.2 - 0.5 range)
        """
        query_lower = query.lower()
        
        # Lower threshold for comparative/analytical queries (need multiple perspectives)
        if any(word in query_lower for word in ['compare', 'vs', 'versus', 'difference', 'between']):
            threshold = base_threshold * 0.8  # 20% lower → 0.24
            logger.debug(f"Comparative query detected → threshold: {threshold:.2f}")
            return threshold
        
        # Lower threshold for broad/summary queries (need variety)
        if any(word in query_lower for word in ['all', 'every', 'summary', 'overview', 'tell me about']):
            threshold = base_threshold * 0.85  # 15% lower → 0.255
            logger.debug(f"Broad query detected → threshold: {threshold:.2f}")
            return threshold
        
        # Lower threshold for multi-topic queries (contains "and")
        if ' and ' in query_lower:
            threshold = base_threshold * 0.9  # 10% lower → 0.27
            logger.debug(f"Multi-topic query detected → threshold: {threshold:.2f}")
            return threshold
        
        # Higher threshold for specific fact lookups (need precision)
        if any(word in query_lower for word in ['what was', 'how much', 'when did', 'what is the']):
            threshold = base_threshold * 1.2  # 20% higher → 0.36
            logger.debug(f"Specific fact query detected → threshold: {threshold:.2f}")
            return threshold
        
        # Default threshold
        return base_threshold

    def _build_context(self, 
        chunks: List[Dict], 
        model_name: str = None,
        max_tokens: int = None
    ) -> str:
        """
        ✨ IMPROVED: Build context with model-aware token limits
        
        Args:
            chunks: Retrieved document chunks
            model_name: Target model (for context limit)
            max_tokens: Override token limit (optional)
        
        Returns:
            Formatted context string
        """
        
        if not chunks:
            return ""
        
        # ✨ Determine token limit based on model
        if max_tokens is None:
            if model_name:
                # Extract base model name
                for key in self.MODEL_CONTEXT_LIMITS:
                    if key in model_name.lower():
                        max_tokens = self.MODEL_CONTEXT_LIMITS[key]
                        break
            if max_tokens is None:
                max_tokens = self.DEFAULT_CONTEXT_LIMIT
        
        logger.info(f"Building context with {max_tokens} token limit")
        
        context_parts = []
        token_count = 0
        
        # Sort by similarity (highest first)
        sorted_chunks = sorted(chunks, key=lambda x: x['similarity'], reverse=True)
        
        for i, chunk in enumerate(sorted_chunks, 1):
            # Rough token estimate (1 token ≈ 4 characters for English)
            chunk_tokens = len(chunk['text']) / 4
            
            if token_count + chunk_tokens > max_tokens:
                logger.info(f"Reached token limit at chunk {i}/{len(sorted_chunks)}")
                break
            
            # Format chunk with source info
            context_parts.append(
                f"[Source {i}: {chunk['filename']} (Page {chunk['page']})]\n"
                f"{chunk['text']}\n"
            )
            token_count += chunk_tokens
        
        context = "\n".join(context_parts)
        logger.info(f"Built context from {len(context_parts)} chunks (~{int(token_count)} tokens)")
        
        return context
    
    def _create_prompt(self, query: str, context: str) -> str:
        """
        Create RAG prompt for LLM
        
        Args:
            query: User question
            context: Retrieved document context
        
        Returns:
            Formatted prompt
        """
        
        prompt = f"""You are a knowledgeable business analyst assistant for NexusIQ Corporation. 
Your job is to answer questions based ONLY on the provided document excerpts.

IMPORTANT RULES:
1. Answer ONLY using information from the provided sources
2. If the answer isn't in the sources, say "I don't have enough information to answer that question based on the available documents."
3. Always cite your sources using the format: (Source: filename, Page X)
4. Be concise but thorough
5. If multiple sources provide relevant info, synthesize them

DOCUMENT EXCERPTS:
{context}

USER QUESTION: {query}

ANSWER (include source citations):"""
        
        return prompt
    
    def _invoke_model(self, model_config: Dict, prompt: str) -> Optional[str]:
        """
        Invoke a specific model based on config
        
        Args:
            model_config: Model configuration dict
            prompt: The prompt to send
        
        Returns:
            Response text or None if failed
        """
        model_type = model_config["type"]
        model_name = model_config["name"]
        
        try:
            if model_type == "gemini":
                if "pro" in model_name.lower():
                    if self.gemini_pro is None:
                        return None
                    response = self.gemini_pro.invoke(prompt)
                else:  # flash
                    if self.gemini_flash is None:
                        return None
                    response = self.gemini_flash.invoke(prompt)
                return response.content
            
            elif model_type == "groq":
                if self.groq_client is None:
                    return None
                response = self.groq_client.invoke(prompt)
                return response.content
            
            elif model_type == "ollama":
                response = ollama.chat(
                    model=settings.ollama_model,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response['message']['content']
            
            else:
                logger.error(f"Unknown model type: {model_type}")
                return None
                
        except Exception as e:
            logger.error(f"{model_name} failed: {e}")
            raise  # Re-raise to be caught by fallback handler
    
    def _generate_answer_with_fallback(
        self, 
        prompt: str, 
        query_complexity: str = "complex"
    ) -> Tuple[Optional[str], str, List[Dict]]:
        """
        Generate answer with multi-model fallback
        
        Args:
            prompt: RAG prompt with context
            query_complexity: "simple" or "complex"
        
        Returns:
            (answer, model_used, models_tried)
        """
        
        import time
        
        # Get model list based on complexity
        models_to_try = list(self.MODELS.get(query_complexity, self.MODELS["complex"]))
        models_tried = []
        
        # ✨ Conditionally add Gemini Pro as FIRST model if enabled
        if settings.use_gemini_pro and self.gemini_pro is not None:
            gemini_pro_config = {
                "name": "gemini-2.5-pro",
                "type": "gemini",
                "description": "Gemini 2.5 Pro (Best for complex analysis)",
                "quota": "50/day (free tier)",
                "priority_reason": "Highest intelligence"
            }
            models_to_try = [gemini_pro_config] + models_to_try
            logger.info("🟢 Gemini Pro ENABLED - trying first")
        
        for model_config in models_to_try:
            model_name = model_config["name"]
            model_start = time.time()
            
            # Check circuit breaker
            available, reason = quota_tracker.is_available(model_name)
            if not available:
                models_tried.append({
                    "model": model_name,
                    "description": model_config["description"],
                    "status": "⏭️ SKIPPED",
                    "error": reason,
                    "time": 0.0
                })
                logger.info(f"⏭️ Skipping {model_name}: {reason}")
                continue
            
            logger.info(f"🔄 Trying {model_config['description']}...")
            
            try:
                answer = self._invoke_model(model_config, prompt)
                elapsed = time.time() - model_start
                
                if answer:
                    quota_tracker.report_success(model_name)
                    models_tried.append({
                        "model": model_name,
                        "description": model_config["description"],
                        "status": "✅ SUCCESS",
                        "error": None,
                        "time": round(elapsed, 2)
                    })
                    logger.info(f"✅ Success with {model_name} in {elapsed:.2f}s")
                    return answer, model_config["description"], models_tried
                else:
                    quota_tracker.report_failure(model_name, "Empty response")
                    models_tried.append({
                        "model": model_name,
                        "description": model_config["description"],
                        "status": "❌ EMPTY RESPONSE",
                        "error": "Model returned empty response",
                        "time": round(elapsed, 2)
                    })
            
            except Exception as e:
                elapsed = time.time() - model_start
                error_msg = str(e)
                quota_tracker.report_failure(model_name, error_msg)
                
                # Determine error type for display
                if "429" in error_msg or "quota" in error_msg.lower():
                    status = "❌ QUOTA EXCEEDED"
                elif "404" in error_msg:
                    status = "❌ MODEL NOT FOUND"
                elif "timeout" in error_msg.lower():
                    status = "❌ TIMEOUT"
                else:
                    status = "❌ FAILED"
                
                models_tried.append({
                    "model": model_name,
                    "description": model_config["description"],
                    "status": status,
                    "error": error_msg[:150],
                    "time": round(elapsed, 2)
                })
                logger.warning(f"{status} {model_name}: {error_msg[:100]}")
                continue
        
        logger.error("All models failed!")
        return None, "none", models_tried
    
    def _classify_query_complexity(self, query: str) -> str:
        """
        ✅ IMPROVED: Classify query as simple or complex
        
        Simple: Single fact lookup, direct answer
        Complex: Multi-document synthesis, comparisons, analysis, explanations
        
        Returns:
            "simple" or "complex"
        """
        
        query_lower = query.lower()
        
        # ✅ Expanded complex indicators
        complex_indicators = [
            # Analysis & comparison
            'compare', 'difference', 'vs', 'versus', 'between',
            'relationship', 'correlation', 'impact', 'affect',
            
            # Deep understanding
            'why', 'how does', 'explain', 'analyze', 'describe',
            
            # Trends & patterns
            'trend', 'growth', 'change', 'over time', 'pattern',
            
            # Breadth indicators
            'all', 'every', 'multiple', 'across', 'various',
            'summary', 'overview', 'breakdown', 'detail',
            
            # Strategic/planning topics
            'plan', 'strategy', 'budget', 'forecast', 'expansion',
            'recommendation', 'should', 'best',
            
            # Narrative requests
            'tell me about', 'what do you know about'
        ]
        
        # Check for complex indicators
        if any(indicator in query_lower for indicator in complex_indicators):
            return "complex"
        
        # ✅ NEW: Multi-topic detection ("X and Y" pattern)
        if ' and ' in query_lower:
            # "revenue and profit" = complex (multiple aspects)
            return "complex"
        
        # ✅ NEW: Long questions are likely complex
        if len(query.split()) > 10:  # Lowered from 15
            return "complex"
        
        # ✅ NEW: Questions with multiple question marks or clauses
        if query.count('?') > 1 or query.count(',') > 2:
            return "complex"
        
        # Default to simple for direct fact lookups
        return "simple"
    
    def _extract_sources(self, answer: str, chunks: List[Dict]) -> List[Dict]:
        """
        Extract source citations from answer
        
        Returns:
            List of cited sources with metadata
        """
        
        sources = []
        seen_files = set()
        
        # Extract from answer citations
        citation_pattern = r'\(Source:\s*([^,]+),\s*Page\s*(\d+)\)'
        matches = re.findall(citation_pattern, answer, re.IGNORECASE)
        
        for filename, page in matches:
            filename = filename.strip()
            if filename not in seen_files:
                sources.append({
                    'filename': filename,
                    'page': page,
                    'cited_in_answer': True
                })
                seen_files.add(filename)
        
        # Add top chunks used (even if not explicitly cited)
        for chunk in chunks[:3]:  # Top 3
            if chunk['filename'] not in seen_files:
                sources.append({
                    'filename': chunk['filename'],
                    'page': chunk['page'],
                    'similarity': chunk['similarity'],
                    'cited_in_answer': False
                })
                seen_files.add(chunk['filename'])
        
        return sources
    

    def _detect_query_type(self, query: str) -> str:
        """
        Detect query type for routing
            
        Returns:
            "comparison" | "multi_part" | "simple"
        """
        query_lower = query.lower()
            
        # Comparison queries
        comparison_indicators = [
            'compare', 'vs', 'versus', 'difference between',
            'vs.', 'compared to', 'contrast'
        ]
        if any(ind in query_lower for ind in comparison_indicators):
            return "comparison"
            
        # Multi-part queries (contains "and")
        if ' and ' in query_lower and '?' in query:
            return "multi_part"
            
        # Simple queries
        return "simple"
    
    def _decompose_comparison_query(self, query: str) -> dict:
        """
        ✨ FIXED: Decompose comparison query with circuit breaker
        
        Example:
            "Compare Q3 and Q4 2024 performance"
            → {
                "original": "Compare Q3 and Q4 2024 performance",
                "sub_queries": [
                    "What was Q3 2024 performance?",
                    "What was Q4 2024 performance?"
                ],
                "comparison_type": "temporal"
            }
        """
        
        decomposition_prompt = f"""You are a query analyzer. Break down this comparison question into 2-3 specific sub-questions.

ORIGINAL QUESTION: {query}

RULES:
1. Create 2-3 sub-questions that, when answered, allow full comparison
2. Make each sub-question standalone and specific
3. Return ONLY a JSON object (no markdown, no explanation)

OUTPUT FORMAT:
{{
    "sub_queries": ["question 1", "question 2"],
    "entities_to_compare": ["entity 1", "entity 2"],
    "metrics_needed": ["metric 1", "metric 2"]
}}

JSON OUTPUT:"""

        # Use the best available model for decomposition
        models_to_try = [
            ("gemini-2.5-flash", self.gemini_flash),
            ("llama-3.3-70b-versatile", self.groq_client),
        ]
        
        for model_name, client in models_to_try:
            if client is None:
                continue
            
            # ✅ FIXED: Check circuit breaker BEFORE trying
            available, reason = quota_tracker.is_available(model_name)
            if not available:
                logger.debug(f"Skipping {model_name}: {reason}")
                continue
            
            try:
                logger.info(f"Decomposing query with {model_name}...")
                response = client.invoke(decomposition_prompt)
                
                # Parse JSON response
                import re
                
                content = response.content.strip()
                # Remove markdown code blocks if present
                content = re.sub(r'```json\s*|\s*```', '', content)
                
                decomposition = json.loads(content)
                
                logger.info(f"✅ Decomposed into {len(decomposition['sub_queries'])} sub-queries")
                
                # ✅ Report success
                quota_tracker.report_success(model_name)
                
                return {
                    "original": query,
                    "sub_queries": decomposition["sub_queries"],
                    "entities": decomposition.get("entities_to_compare", []),
                    "metrics": decomposition.get("metrics_needed", [])
                }
                
            except Exception as e:
                error_msg = str(e)
                # ✅ Report failure
                quota_tracker.report_failure(model_name, error_msg)
                logger.warning(f"Decomposition failed with {model_name}: {error_msg[:100]}")
                continue
        
        # Fallback: Simple split if LLM fails
        logger.warning("LLM decomposition failed, using fallback")
        return self._fallback_decomposition(query)
    
    def _fallback_decomposition(self, query: str) -> dict:
        """Fallback decomposition using pattern matching"""
        
        query_lower = query.lower()
        
        # Pattern: "Compare X and Y"
        if 'compare' in query_lower:
            import re
            # Try to extract entities being compared
            match = re.search(r'compare\s+(.*?)\s+and\s+(.*?)(?:\s|$|performance|revenue)', query_lower)
            if match:
                entity1 = match.group(1).strip()
                entity2 = match.group(2).strip()
                
                return {
                    "original": query,
                    "sub_queries": [
                        f"What was {entity1} performance?",
                        f"What was {entity2} performance?"
                    ],
                    "entities": [entity1, entity2],
                    "metrics": ["revenue", "performance"]
                }
        
        # Default fallback
        return {
            "original": query,
            "sub_queries": [query],
            "entities": [],
            "metrics": []
        }
    
    def _extract_structured_metrics(self, chunks: List[Dict], metric_names: List[str]) -> Dict:
        """
        ✨ FIXED: Extract structured metrics with Groq fallback
        
        Args:
            chunks: Retrieved document chunks
            metric_names: List of metrics to extract (e.g., ["revenue", "transactions"])
        
        Returns:
            {
                "revenue": "$45.2M",
                "transactions": "25,000",
                "growth": "23%",
                ...
            }
        """
        
        if not chunks:
            return {}
        
        context = self._build_context(chunks, max_tokens=4000)
        
        extraction_prompt = f"""Extract EXACT metrics from these document excerpts. Pay close attention to which quarter (Q1, Q2, Q3, Q4) the numbers refer to.

DOCUMENT EXCERPTS:
{context}

METRICS TO EXTRACT:
{', '.join(metric_names)}

CRITICAL RULES:
1. Extract ONLY numbers that are EXPLICITLY STATED in the text
2. Include the quarter/year context (e.g., "Q3 2024 revenue: $38.7M")
3. DO NOT extract targets, projections, or future estimates - only ACTUAL results
4. Include units (e.g., "$38.7M", "23,500 transactions", "24% adoption")
5. If a metric is mentioned for MULTIPLE quarters, extract each separately with labels:
   - Use "Q3_revenue" for Q3 data
   - Use "Q4_revenue" for Q4 data
6. If metric not found for the specific quarter in question, use "Not mentioned"
7. Return ONLY a JSON object (no markdown, no explanations)

EXAMPLE OUTPUT:
{{
    "Q3_revenue": "$38.7M",
    "Q3_transactions": "23,500",
    "Q4_revenue": "$45.2M",
    "Q4_transactions": "25,000",
    "digital_wallet_adoption": "31%"
}}

JSON OUTPUT:"""

        # ✨ FIXED: Try multiple models with delay
        import time
        
        models_to_try = [
            ("gemini-2.5-flash", self.gemini_flash),
            ("llama-3.3-70b-versatile", self.groq_client),  # ✅ Added Groq fallback
        ]
        
        for model_name, client in models_to_try:
            if client is None:
                continue
            
            # ✅ Check quota before trying
            available, _ = quota_tracker.is_available(model_name)
            if not available:
                logger.debug(f"Skipping {model_name} (quota exhausted)")
                continue
            
            try:
                # ✅ Add delay to avoid quota burst
                time.sleep(0.5)  # 500ms between calls
                
                logger.debug(f"Extracting metrics with {model_name}...")
                response = client.invoke(extraction_prompt)
                
                import re
                content = response.content.strip()
                content = re.sub(r'```json\s*|\s*```', '', content)
                
                metrics = json.loads(content)
                logger.debug(f"✅ Extracted {len(metrics)} metrics with {model_name}")
                return metrics
                
            except Exception as e:
                logger.warning(f"Metric extraction failed with {model_name}: {str(e)[:100]}")
                continue
        
        # ✅ Fallback: Improved regex extraction
        logger.warning("All LLM extractions failed, using improved regex fallback")
        return self._fallback_metric_extraction(context)
    
    def _fallback_metric_extraction(self, context: str) -> Dict:
        """
        ✨ IMPROVED: Smarter regex-based extraction with quarter-specific patterns
        """
        
        import re
        
        metrics = {}
        
        # ═══════════════════════════════════════════════════════
        # Quarter-specific revenue extraction (PRIORITY)
        # ═══════════════════════════════════════════════════════
        
        # Q4 2024 revenue patterns
        q4_patterns = [
            r'Q4\s+2024.*?revenue.*?\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)',
            r'Q4.*?\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)',
            r'fourth\s+quarter.*?\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)',
        ]
        
        for pattern in q4_patterns:
            match = re.search(pattern, context, re.IGNORECASE | re.DOTALL)
            if match:
                metrics["Q4_revenue"] = f"${match.group(1)}M"
                logger.debug(f"Extracted Q4 revenue: ${match.group(1)}M")
                break
        
        # Q3 2024 revenue patterns
        q3_patterns = [
            r'Q3\s+2024.*?revenue.*?\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)',
            r'Q3.*?\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)',
            r'third\s+quarter.*?\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)',
        ]
        
        for pattern in q3_patterns:
            match = re.search(pattern, context, re.IGNORECASE | re.DOTALL)
            if match:
                metrics["Q3_revenue"] = f"${match.group(1)}M"
                logger.debug(f"Extracted Q3 revenue: ${match.group(1)}M")
                break
        
        # ═══════════════════════════════════════════════════════
        # Generic revenue (if quarter-specific not found)
        # ═══════════════════════════════════════════════════════
        
        if not metrics:
            revenue_patterns = [
                r'(?:total\s+)?revenue.*?\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)',
                r'\$?([\d,]+(?:\.\d+)?)\s*(?:M|million).*?revenue',
                r'revenue.*?([\d,]+(?:\.\d+)?)',  # Fallback without M/million
            ]
            
            for pattern in revenue_patterns:
                match = re.search(pattern, context, re.IGNORECASE)
                if match:
                    num = match.group(1).replace(',', '')
                    # If no M/million, assume it's raw number (convert to M)
                    if 'M' not in match.group(0) and 'million' not in match.group(0).lower():
                        if float(num) > 1000:  # Likely in thousands
                            num = str(float(num) / 1000)
                    metrics["revenue"] = f"${num}M"
                    logger.debug(f"Extracted generic revenue: ${num}M")
                    break
        
        # ═══════════════════════════════════════════════════════
        # Transaction counts
        # ═══════════════════════════════════════════════════════
        
        txn_patterns = [
            r'([\d,]+)\s+transactions',
            r'transactions.*?([\d,]+)',
        ]
        
        for pattern in txn_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                metrics["transactions"] = match.group(1).replace(',', '')
                logger.debug(f"Extracted transactions: {metrics['transactions']}")
                break
        
        # ═══════════════════════════════════════════════════════
        # Growth percentages
        # ═══════════════════════════════════════════════════════
        
        growth_patterns = [
            r'([\d.]+)%\s*(?:growth|increase|YoY|year-over-year)',
            r'(?:growth|increase).*?([\d.]+)%',
        ]
        
        for pattern in growth_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                metrics["growth"] = f"{match.group(1)}%"
                logger.debug(f"Extracted growth: {metrics['growth']}")
                break
        
        # ═══════════════════════════════════════════════════════
        # Digital Wallet percentage
        # ═══════════════════════════════════════════════════════
        
        wallet_pattern = r'Digital\s+Wallet.*?([\d.]+)%'
        match = re.search(wallet_pattern, context, re.IGNORECASE)
        if match:
            metrics["digital_wallet"] = f"{match.group(1)}%"
            logger.debug(f"Extracted Digital Wallet: {metrics['digital_wallet']}")
        
        logger.info(f"Fallback extraction found {len(metrics)} metrics: {list(metrics.keys())}")
        
        return metrics
    
    def _compute_comparison(self, entity1_metrics: Dict, entity2_metrics: Dict, entities: List[str]) -> Dict:
        """
        ✨ IMPROVED: Smarter comparison with flexible metric matching
        
        Returns:
            {
                "entity1_name": "Q3 2024",
                "entity2_name": "Q4 2024",
                "comparisons": {
                    "revenue": {
                        "Q3 2024": "$38.7M",
                        "Q4 2024": "$45.2M",
                        "difference": "$6.5M",
                        "percent_change": "+16.8%"
                    },
                    ...
                }
            }
        """
        
        import re
        
        # ✅ FIXED: Define entity names FIRST (outside the loop)
        entity1_name = entities[0] if len(entities) > 0 else 'Entity 1'
        entity2_name = entities[1] if len(entities) > 1 else 'Entity 2'
        
        def parse_currency(value: str) -> float:
            """Parse currency string to float (millions)"""
            if not value or value == "Not mentioned":
                return None
            match = re.search(r'([\d,]+(?:\.\d+)?)', str(value).replace(',', ''))
            if match:
                num = float(match.group(1))
                if 'M' in str(value) or 'million' in str(value).lower():
                    return num
                else:
                    return num / 1_000_000
            return None
        
        def parse_percentage(value: str) -> float:
            """Parse percentage string to float"""
            if not value or value == "Not mentioned":
                return None
            match = re.search(r'([\d.]+)', str(value))
            return float(match.group(1)) if match else None
        
        def parse_number(value: str) -> float:
            """Parse number string (for transactions, etc.)"""
            if not value or value == "Not mentioned":
                return None
            match = re.search(r'([\d,]+)', str(value).replace(',', ''))
            return float(match.group(1)) if match else None
        
        def normalize_metrics(metrics: Dict) -> Dict:
            """Normalize metric names to common format"""
            normalized = {}
            for key, value in metrics.items():
                clean_key = re.sub(r'Q[1-4]_', '', key)
                normalized[clean_key] = value
            return normalized
        
        comparisons = {}
        
        norm_entity1 = normalize_metrics(entity1_metrics)
        norm_entity2 = normalize_metrics(entity2_metrics)
        
        # Compare common metrics
        common_metrics = set(norm_entity1.keys()) & set(norm_entity2.keys())
        logger.debug(f"Common metrics to compare: {common_metrics}")
        
        for metric in common_metrics:
            val1_str = norm_entity1[metric]
            val2_str = norm_entity2[metric]
            
            # Try to parse and compute difference
            if '$' in str(val1_str) and '$' in str(val2_str):
                val1 = parse_currency(val1_str)
                val2 = parse_currency(val2_str)
                
                if val1 and val2:
                    diff = val2 - val1
                    pct_change = ((val2 - val1) / val1) * 100
                    
                    comparisons[metric] = {
                        entity1_name: val1_str,
                        entity2_name: val2_str,
                        "difference": f"${abs(diff):.1f}M",
                        "percent_change": f"{'+' if pct_change > 0 else ''}{pct_change:.1f}%",
                        "direction": "increase" if diff > 0 else "decrease"
                    }
                    logger.info(f"Computed comparison for {metric}: {val1_str} → {val2_str} ({pct_change:+.1f}%)")
            
            elif '%' in str(val1_str) and '%' in str(val2_str):
                val1 = parse_percentage(val1_str)
                val2 = parse_percentage(val2_str)
                
                if val1 is not None and val2 is not None:
                    diff = val2 - val1
                    comparisons[metric] = {
                        entity1_name: val1_str,
                        entity2_name: val2_str,
                        "difference": f"{abs(diff):.1f} percentage points",
                        "direction": "increase" if diff > 0 else "decrease"
                    }
                    logger.info(f"Computed comparison for {metric}: {val1_str} → {val2_str} ({diff:+.1f} pp)")
            
            elif str(val1_str).replace(',', '').replace('.', '').isdigit() and str(val2_str).replace(',', '').replace('.', '').isdigit():
                val1 = parse_number(val1_str)
                val2 = parse_number(val2_str)
                
                if val1 and val2:
                    diff = val2 - val1
                    pct_change = ((val2 - val1) / val1) * 100
                    
                    comparisons[metric] = {
                        entity1_name: f"{val1:,.0f}",
                        entity2_name: f"{val2:,.0f}",
                        "difference": f"{abs(diff):,.0f}",
                        "percent_change": f"{'+' if pct_change > 0 else ''}{pct_change:.1f}%",
                        "direction": "increase" if diff > 0 else "decrease"
                    }
                    logger.info(f"Computed comparison for {metric}: {val1:,.0f} → {val2:,.0f} ({pct_change:+.1f}%)")
            
            else:
                comparisons[metric] = {
                    entity1_name: str(val1_str),
                    entity2_name: str(val2_str)
                }
                logger.debug(f"No computation for {metric}: {val1_str} vs {val2_str}")
        
        logger.info(f"Final comparison has {len(comparisons)} metrics")
        
        return {
            "entity1_name": entity1_name,
            "entity2_name": entity2_name,
            "comparisons": comparisons
        }
    
    def _synthesize_comparison_answer(
        self, 
        query: str, 
        decomposition: Dict, 
        comparison_data: Dict,
        all_sources: List[Dict]
    ) -> str:
        """
        ✅ FIXED: Generate natural language answer with circuit breaker
        """
        
        synthesis_prompt = f"""You are a business analyst. Synthesize this comparison into a clear, executive-friendly answer.

ORIGINAL QUESTION: {query}

COMPARISON DATA:
{json.dumps(comparison_data, indent=2)}

RULES:
1. Start with a direct answer to the question
2. Highlight key numbers and trends
3. Use bullet points for clarity
4. Cite sources using format: (Source: filename, Page X)
5. Be concise but comprehensive
6. If data shows growth/decline, mention the percentage

ANSWER:"""

        # Use best model for synthesis
        models_to_try = [
            ("gemini-2.5-flash", self.gemini_flash),
            ("llama-3.3-70b-versatile", self.groq_client),
        ]
        
        for model_name, client in models_to_try:
            if client is None:
                continue
            
            # ✅ FIXED: Check circuit breaker
            available, reason = quota_tracker.is_available(model_name)
            if not available:
                logger.debug(f"Skipping {model_name}: {reason}")
                continue
            
            try:
                response = client.invoke(synthesis_prompt)
                # ✅ Report success
                quota_tracker.report_success(model_name)
                return response.content
            except Exception as e:
                error_msg = str(e)
                # ✅ Report failure
                quota_tracker.report_failure(model_name, error_msg)
                logger.warning(f"Synthesis failed with {model_name}: {error_msg[:100]}")
                continue
        
        # Fallback: Simple template
        return self._fallback_synthesis(comparison_data)
    
    def _fallback_synthesis(self, comparison_data: Dict) -> str:
        """Simple template-based synthesis if LLM fails"""
        
        entity1 = comparison_data.get("entity1_name", "First period")
        entity2 = comparison_data.get("entity2_name", "Second period")
        comparisons = comparison_data.get("comparisons", {})
        
        lines = [f"Comparison: {entity1} vs {entity2}\n"]
        
        for metric, data in comparisons.items():
            val1 = data.get(entity1, "N/A")
            val2 = data.get(entity2, "N/A")
            
            if "percent_change" in data:
                lines.append(
                    f"• {metric.title()}: {val1} → {val2} ({data['percent_change']})"
                )
            else:
                lines.append(f"• {metric.title()}: {val1} vs {val2}")
        
        return "\n".join(lines)
    
    def query(
        self, 
        question: str,
        n_results: int = 5,
        return_sources: bool = True
    ) -> Dict:
        """
        ✨ ENHANCED: Main RAG query method with multi-step reasoning
        
        Args:
            question: User question
            n_results: Number of chunks to retrieve
            return_sources: Include source documents in response
        
        Returns:
            {
                'answer': str,
                'sources': List[Dict],
                'model_used': str,
                'chunks_retrieved': int,
                'query_time': float,
                'query_type': str,  # ✨ NEW
                'decomposition': Dict,  # ✨ NEW (if applicable)
                'models_tried': List[Dict]
            }
        """
        
        start_time = datetime.now()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"RAG Query: {question}")
        logger.info(f"{'='*70}")
        
        # Step 1: Detect query type
        query_type = self._detect_query_type(question)
        logger.info(f"Query type: {query_type}")
        
        # Step 2: Route based on query type
        if query_type == "comparison":
            return self._handle_comparison_query(question, n_results, return_sources, start_time)
        else:
            # Use existing simple query flow
            return self._handle_simple_query(question, n_results, return_sources, start_time)
    
    def _handle_simple_query(
        self, 
        question: str, 
        n_results: int, 
        return_sources: bool, 
        start_time: datetime
    ) -> Dict:
        """Handle simple, direct queries (existing logic)"""
        
        # Classify complexity
        complexity = self._classify_query_complexity(question)
        logger.info(f"Query complexity: {complexity}")
        
        # Search documents
        chunks = self.search_documents(question, n_results=n_results)
        
        if not chunks:
            return {
                'answer': "I couldn't find any relevant information in the documents to answer your question.",
                'sources': [],
                'model_used': 'none',
                'chunks_retrieved': 0,
                'query_time': (datetime.now() - start_time).total_seconds(),
                'complexity': complexity,
                'query_type': 'simple',
                'models_tried': [],
                'error': 'No relevant documents found'
            }
        
        # Determine likely model
        if complexity == "complex":
            likely_model = "gemini-2.5-flash"
        else:
            likely_model = "llama-3.3-70b-versatile"
        
        # Build context
        context = self._build_context(chunks, model_name=likely_model)
        
        # Create prompt
        prompt = self._create_prompt(question, context)
        
        # Generate answer
        answer, model_used, models_tried = self._generate_answer_with_fallback(prompt, complexity)
        
        if not answer:
            return {
                'answer': "I apologize, but I'm unable to generate an answer at the moment due to technical issues. Please try again.",
                'sources': [],
                'model_used': 'none',
                'chunks_retrieved': len(chunks),
                'query_time': (datetime.now() - start_time).total_seconds(),
                'complexity': complexity,
                'query_type': 'simple',
                'models_tried': models_tried,
                'error': 'All LLM models failed'
            }
        
        # Extract sources
        sources = self._extract_sources(answer, chunks) if return_sources else []
        
        query_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Query complete in {query_time:.2f}s using {model_used}")
        
        return {
            'answer': answer,
            'sources': sources,
            'model_used': model_used,
            'chunks_retrieved': len(chunks),
            'query_time': query_time,
            'complexity': complexity,
            'query_type': 'simple',
            'models_tried': models_tried,
            'chunks': chunks
        }
    
    def _handle_comparison_query(
        self, 
        question: str, 
        n_results: int, 
        return_sources: bool, 
        start_time: datetime
    ) -> Dict:
        """
        ✨ SIMPLIFIED: Handle comparison queries with focused retrieval + single synthesis
        
        Strategy:
        1. Decompose into sub-queries
        2. Retrieve chunks for each (filtered by quarter)
        3. Build combined context from ALL relevant chunks
        4. ONE LLM call to compare and synthesize
        
        This is more reliable than multi-step extraction + computation
        """
        
        import time
        
        logger.info("🧠 AGENTIC MODE: Comparison reasoning")
        
        # Step 1: Decompose query
        logger.info("Step 1: Decomposing comparison query...")
        decomposition = self._decompose_comparison_query(question)
        
        logger.info(f"Decomposed into {len(decomposition['sub_queries'])} sub-queries:")
        for i, sq in enumerate(decomposition['sub_queries'], 1):
            logger.info(f"  {i}. {sq}")
        
        # Step 2: Retrieve chunks using HYBRID search
        logger.info("Step 2: Hybrid retrieval (BM25 + Vector)...")
        all_chunks = []
        seen_texts = set()
        
        for sq in decomposition['sub_queries']:
            # ✅ Use hybrid search instead of vector-only
            chunks = self.hybrid_search(
                sq, 
                n_results=5,  # Only need 5 because ranking is better!
                bm25_weight=0.4,
                vector_weight=0.6
            )
            
            for chunk in chunks:
                chunk_key = chunk['text'][:100]
                if chunk_key not in seen_texts:
                    seen_texts.add(chunk_key)
                    all_chunks.append(chunk)
            
            logger.info(f"  '{sq[:60]}...' → {len(chunks)} chunks")
        
        logger.info(f"Total unique chunks: {len(all_chunks)}")

        
        # Step 3: Build combined context
        logger.info("Step 3: Building combined context...")
        context = self._build_context(all_chunks, model_name="llama-3.3-70b-versatile")
        
        # Step 4: ONE LLM call to compare and synthesize
        logger.info("Step 4: Synthesizing comparison answer...")
        
        comparison_prompt = f"""You are a business analyst comparing financial performance across quarters.

DOCUMENT EXCERPTS:
{context}

QUESTION: {question}

INSTRUCTIONS:
1. Read the document excerpts carefully
2. Find the EXACT numbers for each quarter mentioned
3. Compare them side by side
4. Calculate the difference and percentage change
5. Include source citations: (Source: filename, Page X)

RULES:
- ONLY use numbers that appear in the document excerpts above
- These are OFFICIAL financial reports - treat all numbers as FACTS
- Do NOT say "estimated" or "assumed" - report exactly what documents state
- If a number appears in the excerpts, it IS the actual number
- Include all available metrics: revenue, transactions, growth rates, percentages

FORMAT:
Start with a one-line summary, then bullet points with specific numbers.

ANSWER:"""

        # Use fallback chain for synthesis
        models_tried = []
        answer = None
        model_used = "none"
        
        models_to_try = [
            ("gemini-2.5-flash", self.gemini_flash),
            ("llama-3.3-70b-versatile", self.groq_client),
        ]
        
        for model_name, client in models_to_try:
            if client is None:
                continue
            
            available, reason = quota_tracker.is_available(model_name)
            if not available:
                models_tried.append({
                    "model": model_name,
                    "status": "⏭️ SKIPPED",
                    "error": reason,
                    "time": 0.0
                })
                logger.info(f"⏭️ Skipping {model_name}: {reason}")
                continue
            
            try:
                model_start = time.time()
                logger.info(f"🔄 Trying {model_name}...")
                
                response = client.invoke(comparison_prompt)
                elapsed = time.time() - model_start
                
                if response and response.content:
                    answer = response.content
                    model_used = model_name
                    quota_tracker.report_success(model_name)
                    
                    models_tried.append({
                        "model": model_name,
                        "status": "✅ SUCCESS",
                        "error": None,
                        "time": round(elapsed, 2)
                    })
                    logger.info(f"✅ Success with {model_name} in {elapsed:.2f}s")
                    break
                    
            except Exception as e:
                elapsed = time.time() - model_start
                error_msg = str(e)
                quota_tracker.report_failure(model_name, error_msg)
                
                models_tried.append({
                    "model": model_name,
                    "status": "❌ FAILED",
                    "error": error_msg[:100],
                    "time": round(elapsed, 2)
                })
                logger.warning(f"❌ {model_name} failed: {error_msg[:100]}")
                continue
        
        if not answer:
            answer = "Unable to generate comparison. All models failed."
        
        # Extract sources
        sources = self._extract_sources(answer, all_chunks) if return_sources else []
        
        query_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Comparison complete in {query_time:.2f}s using {model_used}")
        
        return {
            'answer': answer,
            'sources': sources,
            'model_used': model_used,
            'chunks_retrieved': len(all_chunks),
            'query_time': query_time,
            'query_type': 'comparison',
            'decomposition': decomposition,
            'models_tried': models_tried,
            'chunks': all_chunks
        }

    
    
    def get_collection_stats(self) -> Dict:
        """Get statistics about the document collection"""
        
        total_docs = self.collection.count()
        
        # Get sample to analyze categories
        sample = self.collection.get(limit=total_docs)
        
        categories = {}
        if sample and sample['metadatas']:
            for metadata in sample['metadatas']:
                cat = metadata.get('category', 'Unknown')
                categories[cat] = categories.get(cat, 0) + 1
        
        return {
            'total_chunks': total_docs,
            'categories': categories,
            'collection_name': 'nexusiq_docs'
        }
    
    def hybrid_search(
        self, 
        query: str, 
        n_results: int = 5,
        similarity_threshold: float = None,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6
    ) -> List[Dict]:
        """
        ✅ Hybrid Search: BM25 (keyword) + Vector (semantic)
        
        BM25 finds exact keyword matches ("Q3", "revenue", "$38.7M")
        Vector finds semantic matches ("money" ≈ "revenue")
        Combined score gives best of both worlds
        
        Args:
            query: User question
            n_results: Max results to return
            similarity_threshold: Min score threshold
            bm25_weight: Weight for keyword score (0-1)
            vector_weight: Weight for semantic score (0-1)
        
        Returns:
            List of chunks sorted by hybrid score
        """
        
        if similarity_threshold is None:
            similarity_threshold = self._get_adaptive_threshold(query)
        
        logger.info(f"Hybrid search for: '{query}' (BM25={bm25_weight}, Vector={vector_weight})")
        
        # ═══════════════════════════════════════════════
        # Part A: BM25 Keyword Search
        # ═══════════════════════════════════════════════
        
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25_index.get_scores(tokenized_query)
        
        # Normalize BM25 scores to 0-1
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
        bm25_normalized = bm25_scores / max_bm25
        
        # ═══════════════════════════════════════════════
        # Part B: Vector Semantic Search
        # ═══════════════════════════════════════════════
        
        query_embedding = self.embedding_model.encode(
            query, 
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        vector_results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=min(n_results * 3, len(self.bm25_documents))  # Get more for merging
        )
        
        # Build vector score map
        vector_scores = {}
        if vector_results['ids'] and vector_results['ids'][0]:
            for doc_id, distance in zip(vector_results['ids'][0], vector_results['distances'][0]):
                vector_scores[doc_id] = 1 - distance  # Convert distance to similarity
        
        # ═══════════════════════════════════════════════
        # Part C: Combine Scores
        # ═══════════════════════════════════════════════
        
        hybrid_results = []
        
        for idx in range(len(self.bm25_documents)):
            doc_id = self.bm25_ids[idx]
            
            bm25_score = float(bm25_normalized[idx])
            vector_score = vector_scores.get(doc_id, 0.0)
            
            # Combined score
            hybrid_score = (bm25_weight * bm25_score) + (vector_weight * vector_score)
            
            if hybrid_score > similarity_threshold * 0.5:  # Looser threshold for hybrid
                metadata = self.bm25_metadatas[idx]
                
                page_info = metadata.get('page', 'Unknown')
                if metadata.get('page_start') and metadata.get('page_end'):
                    if metadata['page_start'] != metadata['page_end']:
                        page_info = f"{metadata['page_start']}-{metadata['page_end']}"
                
                hybrid_results.append({
                    'text': self.bm25_documents[idx],
                    'filename': metadata.get('filename', 'Unknown'),
                    'category': metadata.get('category', 'Unknown'),
                    'page': page_info,
                    'chunk_id': metadata.get('chunk_id', idx),
                    'similarity': round(hybrid_score, 3),
                    'bm25_score': round(bm25_score, 3),
                    'vector_score': round(vector_score, 3)
                })
        
        # Sort by hybrid score (highest first)
        hybrid_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Take top n_results
        results = hybrid_results[:n_results]
        
        # Log top results for debugging
        logger.info(f"Hybrid search results ({len(results)} chunks):")
        for i, r in enumerate(results[:3], 1):
            logger.info(f"  #{i}: {r['filename']} (Page {r['page']}) "
                        f"hybrid={r['similarity']:.3f} bm25={r['bm25_score']:.3f} vector={r['vector_score']:.3f}")
        
        return results

# Singleton instance
_rag_agent_instance = None

def get_rag_agent() -> RAGAgent:
    """Get singleton RAG agent instance"""
    global _rag_agent_instance
    
    if _rag_agent_instance is None:
        _rag_agent_instance = RAGAgent()
    
    return _rag_agent_instance


# ═══════════════════════════════════════════════════════════
#  CLI Testing Interface
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    """Test RAG agent from command line"""
    
    print("\n" + "="*70)
    print("RAG Agent - Interactive Testing")
    print("="*70 + "\n")
    
    # Show Gemini Pro status
    if settings.use_gemini_pro:
        print("🟢 Gemini Pro: ENABLED")
    else:
        print("🔵 Gemini Pro: DISABLED (free tier protection)")
    print()
    
    # Initialize agent
    agent = get_rag_agent()
    
    # Show collection stats
    stats = agent.get_collection_stats()
    print(f"📚 Collection Stats:")
    print(f"  Total Chunks: {stats['total_chunks']}")
    print(f"  Categories: {stats['categories']}")
    print()
    
    # Test queries - mix of simple and complex
    test_questions = [
        # Simple queries (should use Groq first)
        ("What was Q4 2024 revenue?", "simple"),
        ("What is the return policy for Electronics?", "simple"),
        
        # Complex queries (should use Gemini Flash first)
        ("Compare Q3 and Q4 2024 performance", "complex"),
        ("Tell me about the West region expansion plan and budget", "complex"),
        ("What are the Digital Wallet adoption rates across different demographics?", "complex"),
    ]
    
    for question, expected_complexity in test_questions:
        print(f"\n{'='*70}")
        print(f"Q: {question}")
        print(f"Expected Complexity: {expected_complexity}")
        print(f"{'='*70}\n")
        
        result = agent.query(question)
        
        print(f"A: {result['answer']}\n")
        
        print(f"📊 Metadata:")
        print(f"  Detected Complexity: {result.get('complexity', 'unknown')}")
        print(f"  Model Used: {result['model_used']}")
        print(f"  Chunks Retrieved: {result['chunks_retrieved']}")
        print(f"  Query Time: {result['query_time']:.2f}s")
        
        # Show models tried
        if result.get('models_tried'):
            print(f"\n🔄 Models Tried:")
            for m in result['models_tried']:
                print(f"  {m['status']} {m['model']} ({m['time']}s)")
        
        if result['sources']:
            print(f"\n📄 Sources:")
            for source in result['sources']:
                cited = "✓" if source.get('cited_in_answer') else " "
                print(f"  [{cited}] {source['filename']} (Page {source['page']})")
        
        print("\n" + "-"*70)
    
    print("\n✅ RAG Agent testing complete!\n")