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
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from config.data_contexts import DataContext, LIVE_CONTEXT, get_data_context
from config.settings import settings
from utils.llm_gateway import get_llm_gateway
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
    
    def __init__(self, data_context: DataContext = LIVE_CONTEXT):
        """Initialize RAG agent with embedding model, vector DB, and LLM clients"""
        
        logger.info("Initializing RAG Agent...")
        self.data_context = data_context
        self.collection_name = data_context.chroma_collection
        
        # Initialize embedding model (same as setup)
        logger.info("Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        
        # Initialize ChromaDB
        chroma_dir = Path(data_context.chroma_directory or settings.chroma_persist_directory)
        self.chroma_directory = chroma_dir
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
            self.collection = self.chroma_client.get_collection(self.collection_name)
            logger.info(f"Connected to collection with {self.collection.count()} documents")
        except Exception as e:
            raise Exception(
                f"Collection {self.collection_name!r} not found for {data_context.label}. "
                f"Prepare the configured evidence index first. Error: {e}"
            )
        
        # Initialize LLM clients
        self._init_llm_clients()
        self.llm_gateway = get_llm_gateway()
        self._init_bm25_index()
        self._ingestion_version = self._read_ingestion_version()
        self.cross_encoder = None  # lazy-loaded on first rerank call

        logger.info("RAG Agent initialized successfully!")

    def _models_for_complexity(self, complexity: str) -> List[Dict]:
        """Return RAG model configs in the existing preference order."""
        models_to_try = list(self.MODELS.get(complexity, self.MODELS["complex"]))
        if settings.use_gemini_pro and self.gemini_pro is not None:
            models_to_try.insert(0, {
                "name": "gemini-2.5-pro",
                "type": "gemini",
                "description": "Gemini 2.5 Pro (Best for complex analysis)",
                "quota": "50/day (free tier)",
                "priority_reason": "Highest intelligence",
            })
        return models_to_try

    def _reasoning_models(self) -> List[Dict]:
        """Return document reasoning models with Gemini-first ordering."""
        models = []
        if self.gemini_flash is not None:
            models.append({
                "name": "gemini-2.5-flash",
                "type": "gemini",
                "description": "Gemini 2.5 Flash",
            })
        if self.groq_client is not None:
            models.append({
                "name": "llama-3.3-70b-versatile",
                "type": "groq",
                "description": "Groq Llama 3.3 70B",
            })
        return models

    @staticmethod
    def _valid_json_response(content: str) -> bool:
        try:
            json.loads(re.sub(r"```json\s*|\s*```", "", content).strip())
            return True
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
    
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

    def refresh_bm25(self) -> None:
        """Reload BM25 index from current ChromaDB state after incremental PDF ingestion."""
        self._init_bm25_index()
        self._ingestion_version = self._read_ingestion_version()
        logger.info("BM25 index refreshed from ChromaDB")

    def _read_ingestion_version(self) -> int:
        """Read the ingestion version counter written by the ingestion pipeline."""
        version_file = self.chroma_directory / "ingestion_version.json"
        if not version_file.exists():
            return 0
        try:
            return json.loads(version_file.read_text()).get("version", 0)
        except Exception:
            return 0

    def _ensure_bm25_fresh(self) -> None:
        """Auto-refresh BM25 if ChromaDB doc count or ingestion version has changed."""
        chroma_count = self.collection.count()
        current_version = self._read_ingestion_version()
        if chroma_count != len(self.bm25_documents) or current_version != self._ingestion_version:
            logger.info(
                f"BM25 stale (docs: {len(self.bm25_documents)}→{chroma_count}, "
                f"version: {self._ingestion_version}→{current_version}) — refreshing"
            )
            self._init_bm25_index()
            self._ingestion_version = current_version

    def _init_llm_clients(self):
        """Initialize LLM clients for answer generation with feature flags"""
        
        # ✨ Gemini Pro (conditional - disabled by default)
        if settings.google_api_key and settings.use_gemini_pro:
            self.gemini_pro = ChatGoogleGenerativeAI(
                model=settings.gemini_pro_model,
                google_api_key=settings.google_api_key,
                temperature=0.1,
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
                temperature=0.1,
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
                temperature=0.1
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

    def _extract_metadata_filter(self, question: str) -> Optional[dict]:
        """Extract ChromaDB metadata filter from question keywords (quarter, category)."""
        q = question.lower()
        quarter_map = {"q1": "Q1", "q2": "Q2", "q3": "Q3", "q4": "Q4",
                       "first quarter": "Q1", "second quarter": "Q2",
                       "third quarter": "Q3", "fourth quarter": "Q4"}
        for keyword, label in quarter_map.items():
            if keyword in q:
                return {"filename": {"$contains": label}}
        return None

    def _hyde_search(self, question: str, n_results: int) -> List[Dict]:
        """Generate hypothetical answer then search with it (HyDE)."""
        models = []
        if getattr(self, "groq_client", None) is not None:
            models.append({
                "name": "llama-3.3-70b-versatile",
                "type": "groq",
                "description": "Groq Llama 3.3 70B",
            })
        if getattr(self, "gemini_flash", None) is not None:
            models.append({
                "name": "gemini-2.5-flash",
                "type": "gemini",
                "description": "Gemini 2.5 Flash",
            })

        result = self.llm_gateway.invoke_with_fallback(
            prompt=(
                "Write one factual paragraph answering this business question. "
                f"Use approximate numbers if needed. Be concise.\n\nQuestion: {question}"
            ),
            models=models,
            tracker=quota_tracker,
            task="rag.hyde",
            temperature=0.1,
            metadata={"agent": "rag"},
            response_validator=lambda content: bool(content.strip()),
        )
        fake_answer = result.get("response") if result.get("success") else None

        if not fake_answer:
            return []

        logger.info(f"HyDE generated hypothetical answer ({len(fake_answer)} chars), re-searching...")
        return self.hybrid_search(fake_answer, n_results=n_results)

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
        
        # Preserve retriever/reranker order. hybrid_search already returns the
        # final relevance order; re-sorting here by the pre-rerank hybrid score
        # can put a less relevant template ahead of the best evidence.
        sorted_chunks = chunks
        
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
        
        prompt = f"""You are a business analyst for NexusIQ Corporation. Answer using ONLY the provided document excerpts.

FORMATTING RULES (follow strictly — users must enjoy reading this):
• Lead with a direct 1-2 sentence answer at the top.
• Then use bullet points or short numbered sections for supporting details.
• Use **bold** for key numbers, thresholds, and policy terms.
• Break up any answer longer than 3 sentences into sections with a short header.
• Do NOT write one long paragraph — that makes answers hard to read.
• Put ALL source citations in a clean block at the END, not mid-sentence.
  Format: 📄 *filename* — brief description of what it contributed.

CONTENT RULES:
1. Answer ONLY from the provided sources. If not covered, say "I don't have enough information from the available documents."
2. For policy/SOP questions: lead with the key rule → then conditions/exceptions → then eligibility table if present.
3. For vendor/supply situations: use ▸ **Situation** → ▸ **Impact** → ▸ **Actions Taken** structure.
4. For numeric questions: bold the exact figure first, then explain context.
5. For "explain" questions: break into clearly labeled sub-topics (e.g., Background, What Happened, Current Status).
6. If sources disagree on numbers, call it out explicitly — don't silently pick one.
7. Do not add caveats or qualifiers not present in the sources.

DOCUMENT EXCERPTS:
{context}

USER QUESTION: {query}

ANSWER:"""
        
        return prompt
    
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
        
        result = self.llm_gateway.invoke_with_fallback(
            prompt=prompt,
            models=self._models_for_complexity(query_complexity),
            tracker=quota_tracker,
            task="rag.answer",
            temperature=0.1,
            metadata={"agent": "rag", "complexity": query_complexity},
            response_validator=lambda content: bool(content.strip()),
        )
        if result.get("success"):
            return result["response"], result["model_used"], result["models_tried"]
        logger.error("All models failed!")
        return None, "none", result.get("models_tried", [])
    
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
        chunk_lookup = {}
        for chunk in chunks:
            key = (str(chunk.get('filename', '')).strip(), str(chunk.get('page', '')).strip())
            chunk_lookup.setdefault(key, chunk)
        
        # Extract from answer citations
        citation_pattern = r'\(Source:\s*([^,]+),\s*Page\s*(\d+)\)'
        matches = re.findall(citation_pattern, answer, re.IGNORECASE)
        
        for filename, page in matches:
            filename = filename.strip()
            if filename not in seen_files:
                chunk = chunk_lookup.get((filename, str(page).strip()), {})
                sources.append({
                    'filename': filename,
                    'page': page,
                    'similarity': chunk.get('similarity'),
                    'rerank_score': chunk.get('rerank_score'),
                    'relevance_score': chunk.get('rerank_score', chunk.get('similarity')),
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
                    'rerank_score': chunk.get('rerank_score'),
                    'relevance_score': chunk.get('rerank_score', chunk.get('similarity')),
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

        result = self.llm_gateway.invoke_with_fallback(
            prompt=decomposition_prompt,
            models=self._reasoning_models(),
            tracker=quota_tracker,
            task="rag.decompose",
            temperature=0.1,
            metadata={"agent": "rag", "query_type": "comparison"},
            response_validator=self._valid_json_response,
        )
        if result.get("success"):
            content = re.sub(r"```json\s*|\s*```", "", result["response"]).strip()
            decomposition = json.loads(content)
            if decomposition.get("sub_queries"):
                logger.info(f"✅ Decomposed into {len(decomposition['sub_queries'])} sub-queries")
                return {
                    "original": query,
                    "sub_queries": decomposition["sub_queries"],
                    "entities": decomposition.get("entities_to_compare", []),
                    "metrics": decomposition.get("metrics_needed", [])
                }
        
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

        result = self.llm_gateway.invoke_with_fallback(
            prompt=extraction_prompt,
            models=self._reasoning_models(),
            tracker=quota_tracker,
            task="rag.extract_metrics",
            temperature=0.1,
            metadata={"agent": "rag"},
            response_validator=self._valid_json_response,
        )
        if result.get("success"):
            content = re.sub(r"```json\s*|\s*```", "", result["response"]).strip()
            metrics = json.loads(content)
            logger.debug(f"✅ Extracted {len(metrics)} metrics with {result.get('model_used')}")
            return metrics
        
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

        result = self.llm_gateway.invoke_with_fallback(
            prompt=synthesis_prompt,
            models=self._reasoning_models(),
            tracker=quota_tracker,
            task="rag.synthesize_comparison",
            temperature=0.1,
            metadata={"agent": "rag", "query_type": "comparison"},
            response_validator=lambda content: bool(content.strip()),
        )
        if result.get("success"):
            return result["response"]
        
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
    
    # Cross-encoder logit thresholds, calibrated on the live corpus
    # (strong matches ~+7..+9, marginal correct ~+1..+2, off-topic ~-10):
    # below WEAK the evidence is questionable -> one HyDE retry, then caveat;
    # below INSUFFICIENT nothing retrieved is relevant -> honest refusal.
    _RERANK_WEAK_THRESHOLD = 0.0
    _RERANK_INSUFFICIENT_THRESHOLD = -5.0
    _HYBRID_WEAK_FALLBACK = 0.35

    @classmethod
    def _assess_evidence(cls, chunks: List[Dict]) -> Dict:
        """Deterministic retrieval-quality check. No LLM calls.

        Uses cross-encoder logits when present (the only score comparable
        across queries); falls back to hybrid score when the reranker was
        unavailable. Hybrid scores are query-relative (per-query min-max BM25)
        and must not be compared across queries.
        """
        if not chunks:
            return {"quality": "insufficient", "reason": "no_chunks",
                    "top_rerank": None, "top_hybrid": None, "unique_docs": 0}

        rerank_scores = [c["rerank_score"] for c in chunks if "rerank_score" in c]
        top_rerank = max(rerank_scores) if rerank_scores else None
        top_hybrid = max((c.get("similarity", 0.0) for c in chunks), default=0.0)
        unique_docs = len({c.get("filename") for c in chunks})

        if top_rerank is not None:
            if top_rerank < cls._RERANK_INSUFFICIENT_THRESHOLD:
                quality, reason = "insufficient", "top_rerank_below_relevance_floor"
            elif top_rerank < cls._RERANK_WEAK_THRESHOLD:
                quality, reason = "weak", "top_rerank_below_confidence_threshold"
            else:
                quality, reason = "sufficient", "rerank_confident"
        else:
            if top_hybrid < cls._HYBRID_WEAK_FALLBACK:
                quality, reason = "weak", "no_reranker_low_hybrid_score"
            else:
                quality, reason = "sufficient", "no_reranker_hybrid_acceptable"

        return {
            "quality": quality,
            "reason": reason,
            "top_rerank": round(top_rerank, 3) if top_rerank is not None else None,
            "top_hybrid": round(top_hybrid, 3),
            "unique_docs": unique_docs,
        }

    @staticmethod
    def _evidence_better(candidate: List[Dict], current: List[Dict]) -> bool:
        """Compare retrievals by top rerank logit; hybrid only as fallback."""
        def top(chunks, key, default):
            values = [c[key] for c in chunks if key in c]
            return max(values) if values else default

        candidate_rerank = top(candidate, "rerank_score", None)
        current_rerank = top(current, "rerank_score", None)
        if candidate_rerank is not None and current_rerank is not None:
            return candidate_rerank > current_rerank
        return top(candidate, "similarity", 0.0) > top(current, "similarity", 0.0)

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
        
        retrieval_query = self._normalize_retrieval_query(question)
        if retrieval_query != question:
            logger.info(f"Retrieval query normalized: '{retrieval_query}'")

        # Hybrid BM25+vector search — BM25 naturally prioritizes keyword matches (Q4, Electronics)
        # which makes metadata pre-filtering redundant; hybrid covers cross-document content too
        chunks = self.hybrid_search(retrieval_query, n_results=n_results)

        # Bounded evidence loop: retrieve -> assess (deterministic, on
        # cross-encoder logits) -> if weak, one HyDE retry -> re-assess ->
        # answer, caveat, or abstain honestly. One retry max.
        initial_assessment = self._assess_evidence(chunks)
        evidence = {"initial": initial_assessment, "retried": False}
        if initial_assessment["quality"] != "sufficient":
            logger.info(
                "Weak evidence (%s, top_rerank=%s) → HyDE retry",
                initial_assessment["reason"], initial_assessment["top_rerank"],
            )
            hyde_chunks = self._hyde_search(retrieval_query, n_results=n_results)
            evidence["retried"] = True
            if hyde_chunks and self._evidence_better(hyde_chunks, chunks):
                logger.info("HyDE improved retrieval — using HyDE results")
                chunks = hyde_chunks
        final_assessment = self._assess_evidence(chunks) if evidence["retried"] else initial_assessment
        evidence["final"] = final_assessment

        if not chunks or final_assessment["quality"] == "insufficient":
            return {
                'answer': (
                    "I couldn't find documents relevant enough to answer this reliably. "
                    "The closest matches scored below the evidence threshold, so I won't "
                    "guess from unrelated content."
                ) if chunks else "I couldn't find any relevant information in the documents to answer your question.",
                'sources': [],
                'model_used': 'none',
                'chunks_retrieved': 0,
                'query_time': (datetime.now() - start_time).total_seconds(),
                'complexity': complexity,
                'query_type': 'simple',
                'models_tried': [],
                'evidence': evidence,
                'evidence_quality': 'insufficient',
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
        
        # Weak-but-usable evidence: answer with an explicit caveat instead of
        # presenting low-relevance retrieval as confident.
        if final_assessment["quality"] == "weak":
            answer = (
                f"{answer}\n\n"
                "⚠️ **Evidence caveat:** retrieval confidence for this question was low "
                "even after a retry — the cited documents may only partially cover it. "
                "Treat this answer as a lead, not a verified fact."
            )

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
            'evidence': evidence,
            'evidence_quality': final_assessment["quality"],
            'chunks': chunks
        }

    def _normalize_retrieval_query(self, question: str) -> str:
        """Remove orchestration wording that can overpower the actual evidence target."""
        query = str(question or "").strip()
        lowered = query.lower()
        is_validation_revenue_query = (
            "revenue" in lowered
            and any(term in lowered for term in ("validate", "verify", "cross-reference", "cross reference"))
            and "sql" in lowered
            and any(term in lowered for term in ("pdf", "document", "report"))
        )
        if not is_validation_revenue_query:
            return query

        normalized = re.sub(
            r"\b(validate|verify|confirm|cross-reference|cross reference)\b",
            " ",
            query,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\bacross\s+sql\s+and\s+pdf\s+reports?\b",
            " ",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\bagainst\s+(sql\s+and\s+)?pdf\s+reports?\b",
            " ",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"\bsql\b|\bdatabase\b|\bpdfs?\b", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip(" .")

        if "report" not in normalized.lower():
            normalized = f"{normalized} financial report"
        return normalized
    
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

        result = self.llm_gateway.invoke_with_fallback(
            prompt=comparison_prompt,
            models=self._reasoning_models(),
            tracker=quota_tracker,
            task="rag.compare_answer",
            temperature=0.1,
            metadata={"agent": "rag", "query_type": "comparison"},
            response_validator=lambda content: bool(content.strip()),
        )
        answer = result.get("response") if result.get("success") else "Unable to generate comparison. All models failed."
        model_used = result.get("model_used") or "none"
        models_tried = result.get("models_tried", [])
        
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
            'collection_name': self.collection_name
        }
    
    def hybrid_search(
        self,
        query: str,
        n_results: int = 5,
        similarity_threshold: float = None,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        rerank: bool = True,
        rerank_top_k: int = 20,
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
        
        self._ensure_bm25_fresh()

        # ═══════════════════════════════════════════════
        # Part A: BM25 Keyword Search
        # ═══════════════════════════════════════════════

        tokenized_query = query.lower().split()
        bm25_scores = self.bm25_index.get_scores(tokenized_query)
        
        # BM25 can be negative when query terms occur throughout a small corpus.
        # Min-max scaling preserves relative keyword relevance without penalizing
        # otherwise strong vector matches below zero.
        min_bm25 = float(min(bm25_scores)) if len(bm25_scores) else 0.0
        max_bm25 = float(max(bm25_scores)) if len(bm25_scores) else 0.0
        if max_bm25 > min_bm25:
            bm25_normalized = (bm25_scores - min_bm25) / (max_bm25 - min_bm25)
        elif max_bm25 > 0:
            bm25_normalized = bm25_scores / max_bm25
        else:
            bm25_normalized = bm25_scores * 0
        
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
        quarter_scope = self._single_quarter_scope(query)
        
        for idx in range(len(self.bm25_documents)):
            doc_id = self.bm25_ids[idx]
            
            bm25_score = float(bm25_normalized[idx])
            vector_score = vector_scores.get(doc_id, 0.0)
            
            # Combined score
            hybrid_score = (bm25_weight * bm25_score) + (vector_weight * vector_score)
            
            if hybrid_score > similarity_threshold * 0.5:  # Looser threshold for hybrid
                metadata = self.bm25_metadatas[idx]
                quarter_match = self._quarter_match(
                    query=query,
                    text=self.bm25_documents[idx],
                    filename=metadata.get('filename', 'Unknown'),
                    quarter_scope=quarter_scope,
                )
                if quarter_match == "exclude":
                    continue
                if quarter_match == "strong":
                    hybrid_score += 0.08
                elif quarter_match == "weak":
                    hybrid_score += 0.03
                
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

        if rerank:
            # Expand candidate pool for reranker, then let cross-encoder pick the best
            candidates = hybrid_results[:rerank_top_k]
            results = self._rerank_chunks(query, candidates, top_n=n_results)
        else:
            results = hybrid_results[:n_results]

        # Log top results for debugging
        logger.info(f"Hybrid search results ({len(results)} chunks):")
        for i, r in enumerate(results[:3], 1):
            logger.info(f"  #{i}: {r['filename']} (Page {r['page']}) "
                        f"hybrid={r['similarity']:.3f} bm25={r['bm25_score']:.3f} vector={r['vector_score']:.3f}")

        return results

    def _get_cross_encoder(self):
        """Lazy-load cross-encoder model on first call. CPU-friendly, ~22MB."""
        if self.cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info("Loading cross-encoder model (cross-encoder/ms-marco-MiniLM-L-6-v2)...")
                self.cross_encoder = CrossEncoder(
                    "cross-encoder/ms-marco-MiniLM-L-6-v2",
                    device="cpu",
                    max_length=512,
                )
                logger.info("Cross-encoder loaded.")
            except Exception as e:
                logger.warning(f"Cross-encoder unavailable: {e}. Skipping rerank.")
        return self.cross_encoder

    def _rerank_chunks(self, query: str, chunks: List[Dict], top_n: int) -> List[Dict]:
        """
        Re-score chunks using cross-encoder and return top_n.

        Cross-encoder reads (query, passage) together and produces a relevance
        logit that is more accurate than the bi-encoder cosine score, at the
        cost of needing a forward pass per candidate.
        """
        model = self._get_cross_encoder()
        if model is None or not chunks:
            return chunks[:top_n]

        pairs = [(query, c["text"]) for c in chunks]
        try:
            scores = model.predict(pairs, show_progress_bar=False)
        except Exception as e:
            logger.warning(f"Cross-encoder scoring failed: {e}. Returning un-reranked.")
            return chunks[:top_n]

        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)

        reranked = sorted(chunks, key=lambda x: x.get("rerank_score", 0), reverse=True)
        logger.info(
            f"Reranker top-3: "
            + " | ".join(
                f"{r['filename']} (r={r['rerank_score']:.2f})"
                for r in reranked[:3]
            )
        )
        return reranked[:top_n]

    def _single_quarter_scope(self, query: str) -> Optional[str]:
        """Return Q1-Q4 only when the query asks for one quarter, not a comparison."""
        normalized = str(query or "").lower()
        mentions = []
        quarter_patterns = {
            "Q1": (r"\bq1\b", r"\bfirst quarter\b"),
            "Q2": (r"\bq2\b", r"\bsecond quarter\b"),
            "Q3": (r"\bq3\b", r"\bthird quarter\b"),
            "Q4": (r"\bq4\b", r"\bfourth quarter\b"),
        }
        for quarter, patterns in quarter_patterns.items():
            if any(re.search(pattern, normalized) for pattern in patterns):
                mentions.append(quarter)

        if len(mentions) != 1:
            return None
        if any(term in normalized for term in ("compare", "versus", " vs ", "between", "trend", "growth")):
            return None
        return mentions[0]

    def _quarter_match(
        self,
        query: str,
        text: str,
        filename: str,
        quarter_scope: Optional[str] = None,
    ) -> str:
        """
        Classify whether a chunk belongs to the single-quarter scope.

        Quarterly report templates are nearly identical, so embeddings and a
        generic cross-encoder often rank Q2/Q3 revenue passages highly for Q4
        questions. This guard keeps those wrong-quarter templates out while
        preserving annual summaries that mention the requested quarter.
        """
        quarter = quarter_scope or self._single_quarter_scope(query)
        if not quarter:
            return "neutral"

        target = quarter.lower()
        filename_lower = str(filename or "").lower()
        text_lower = str(text or "").lower()
        haystack = f"{filename_lower}\n{text_lower[:1200]}"
        quarter_tokens = {"q1", "q2", "q3", "q4"}
        filename_quarters = {
            token.upper()
            for token in quarter_tokens
            if re.search(rf"(^|[^a-z0-9]){token}([^a-z0-9]|$)", filename_lower)
        }
        present = {
            token.upper()
            for token in quarter_tokens
            if re.search(rf"(^|[^a-z0-9]){token}([^a-z0-9]|$)", haystack)
        }

        if target in filename_lower:
            return "strong"
        if filename_quarters and quarter not in filename_quarters:
            return "exclude"
        if quarter in present:
            return "weak"
        if present and quarter not in present:
            return "exclude"
        return "neutral"


# Singleton instances are isolated by data context so live and pilot evidence never share state.
_rag_agent_instances = {}


def get_rag_agent(data_context_key: str = "live") -> RAGAgent:
    """Get a RAG agent instance scoped to one evidence context."""
    if data_context_key not in _rag_agent_instances:
        _rag_agent_instances[data_context_key] = RAGAgent(get_data_context(data_context_key))
    return _rag_agent_instances[data_context_key]


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
