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
        
        logger.info("RAG Agent initialized successfully!")
    
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
        similarity_threshold: float = 0.5  # ✨ Higher threshold for cosine (0-1 scale)
    ) -> List[Dict]:
        """
        Semantic search over document collection
        
        Args:
            query: User question
            n_results: Max number of chunks to retrieve
            similarity_threshold: Minimum similarity score (0-1, higher = more similar)
        
        Returns:
            List of retrieved chunks with metadata and similarity scores
        """
        
        logger.info(f"Searching documents for: '{query}'")
        
        # Generate query embedding (normalized for cosine)
        query_embedding = self.embedding_model.encode(
            query, 
            convert_to_numpy=True,
            normalize_embeddings=True  # ✨ Important for cosine similarity
        )
        
        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results
        )
        
        # Parse results
        chunks = []
        
        if not results['documents'] or not results['documents'][0]:
            logger.warning("No results found in ChromaDB")
            return chunks
        
        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            # ✨ FIX: Cosine distance to similarity
            # Cosine distance = 1 - cosine_similarity
            # So: cosine_similarity = 1 - cosine_distance
            similarity = 1 - distance
            
            # Filter by threshold
            if similarity < similarity_threshold:
                logger.debug(f"Skipping chunk {i+1}: similarity {similarity:.3f} below threshold {similarity_threshold}")
                continue
            
            # ✨ Better page info
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
        
        logger.info(f"Retrieved {len(chunks)} relevant chunks (threshold: {similarity_threshold})")
        
        return chunks
    
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
        Classify query as simple or complex
        
        Simple: Single fact lookup
        Complex: Multi-document synthesis, comparisons, analysis
        """
        
        complex_indicators = [
            'compare', 'difference', 'why', 'how', 'analyze', 
            'explain', 'relationship', 'trend', 'impact',
            'vs', 'versus', 'better', 'worse', 'between',
            'multiple', 'all', 'every', 'across', 'summary',
            'overview', 'breakdown', 'detail'
        ]
        
        query_lower = query.lower()
        
        if any(indicator in query_lower for indicator in complex_indicators):
            return "complex"
        
        if len(query.split()) > 15:  # Long questions likely complex
            return "complex"
        
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
    
    def query(
        self, 
        question: str,
        n_results: int = 5,
        return_sources: bool = True
    ) -> Dict:
        """
        Main RAG query method
        
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
                'models_tried': List[Dict]
            }
        """
        
        start_time = datetime.now()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"RAG Query: {question}")
        logger.info(f"{'='*70}")
        
        # Step 1: Classify complexity FIRST (we need this for context building)
        complexity = self._classify_query_complexity(question)
        logger.info(f"Query complexity: {complexity}")
        
        # Step 2: Search documents
        chunks = self.search_documents(question, n_results=n_results)
        
        if not chunks:
            return {
                'answer': "I couldn't find any relevant information in the documents to answer your question.",
                'sources': [],
                'model_used': 'none',
                'chunks_retrieved': 0,
                'query_time': (datetime.now() - start_time).total_seconds(),
                'complexity': complexity,
                'models_tried': [],
                'error': 'No relevant documents found'
            }
        
        # Step 3: Determine which model will likely be used (for context sizing)
        if complexity == "complex":
            likely_model = "gemini-2.5-flash"
        else:
            likely_model = "llama-3.3-70b-versatile"
        
        # Step 4: Build context with model-aware limits
        context = self._build_context(chunks, model_name=likely_model)
        
        # Step 5: Create prompt
        prompt = self._create_prompt(question, context)
        
        # Step 6: Generate answer with fallback
        answer, model_used, models_tried = self._generate_answer_with_fallback(prompt, complexity)
        
        if not answer:
            return {
                'answer': "I apologize, but I'm unable to generate an answer at the moment due to technical issues. Please try again.",
                'sources': [],
                'model_used': 'none',
                'chunks_retrieved': len(chunks),
                'query_time': (datetime.now() - start_time).total_seconds(),
                'complexity': complexity,
                'models_tried': models_tried,
                'error': 'All LLM models failed'
            }
        
        # Step 7: Extract sources
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
            'models_tried': models_tried,
            'chunks': chunks  # For debugging
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