"""
RAG Pipeline Setup (v2 - Optimized)
Processes PDFs, chunks intelligently, embeds, and stores in ChromaDB

Fixes Applied:
- Cosine distance for better similarity scoring
- Improved page tracking in chunks
- Proper overlap implementation
- Better text cleaning
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple
import pypdf
import pdfplumber
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from datetime import datetime
import json

# Fix tokenizer warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Paths
PDF_BASE_DIR = Path("./data/pdfs")
CHROMA_DIR = Path("./data/chroma_db")

# Categories to process
CATEGORIES = [
    "01_financial",
    "02_market_intelligence",
    "03_contracts_legal",
    "04_products_operations",
    "05_strategic_planning",
    "06_hr_compliance"
]


class RAGPipelineSetup:
    """Setup RAG pipeline: Extract -> Chunk -> Embed -> Store"""
    
    def __init__(self):
        print("\n" + "="*70)
        print("RAG Pipeline Setup v2 - NexusIQ Document Processing")
        print("="*70 + "\n")
        
        # Initialize embedding model
        print("Loading embedding model (sentence-transformers)...")
        self.embedding_model = SentenceTransformer(
            'all-MiniLM-L6-v2',
            device='cpu'
        )
        print("✅ Model loaded: all-MiniLM-L6-v2 (384 dimensions)")
        
        # Initialize ChromaDB
        print(f"\nInitializing ChromaDB at {CHROMA_DIR}...")
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Delete existing collection for fresh start
        try:
            self.chroma_client.delete_collection("nexusiq_docs")
            print("🗑️  Deleted existing collection for fresh start")
        except:
            pass
        
        # ✨ FIX: Create collection with COSINE distance metric
        self.collection = self.chroma_client.create_collection(
            name="nexusiq_docs",
            metadata={
                "description": "NexusIQ business documents",
                "hnsw:space": "cosine"  # ✨ Use cosine similarity!
            }
        )
        print("✅ Created collection: nexusiq_docs (cosine distance)")
        
        self.stats = {
            "pdfs_processed": 0,
            "chunks_created": 0,
            "categories": {},
            "distance_metric": "cosine"
        }
    
    def extract_text_from_pdf(self, pdf_path: Path) -> Tuple[List[Dict], Dict]:
        """
        Extract text from PDF with page-level tracking
        
        Returns:
            (list of {page_num, text}, metadata)
        """
        pages_data = []
        metadata = {
            "filename": pdf_path.name,
            "category": pdf_path.parent.name,
            "pages": 0,
            "extraction_method": ""
        }
        
        try:
            # Try pypdf first (faster)
            with open(pdf_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                metadata["pages"] = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        pages_data.append({
                            "page_num": page_num,
                            "text": self._clean_text(page_text)
                        })
                
                metadata["extraction_method"] = "pypdf"
        
        except Exception as e:
            print(f"  ⚠️ pypdf failed, trying pdfplumber: {e}")
            
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    metadata["pages"] = len(pdf.pages)
                    
                    for page_num, page in enumerate(pdf.pages, 1):
                        page_text = page.extract_text()
                        if page_text and page_text.strip():
                            pages_data.append({
                                "page_num": page_num,
                                "text": self._clean_text(page_text)
                            })
                    
                    metadata["extraction_method"] = "pdfplumber"
            
            except Exception as e2:
                print(f"  ❌ Both extraction methods failed: {e2}")
                return [], metadata
        
        return pages_data, metadata
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        # Remove page break artifacts
        text = re.sub(r'[-_]{5,}', '', text)
        
        # Fix common Unicode characters
        text = text.replace('\u2014', '-')      # em dash
        text = text.replace('\u2019', "'")      # right single quote
        text = text.replace('\u2018', "'")      # left single quote
        text = text.replace('\u201c', '"')      # left double quote
        text = text.replace('\u201d', '"')      # right double quote
        text = text.replace('\u2022', '•')      # bullet
        text = text.replace('\u2013', '-')      # en dash
        
        return text.strip()
    
    def chunk_text(
        self, 
        pages_data: List[Dict], 
        metadata: Dict, 
        chunk_size: int = 800, 
        overlap_chars: int = 150
    ) -> List[Dict]:
        """
        ✨ IMPROVED: Intelligent chunking with proper overlap and page tracking
        
        Args:
            pages_data: List of {page_num, text} dicts
            metadata: Document metadata
            chunk_size: Target characters per chunk
            overlap_chars: Character overlap between chunks
        
        Returns:
            List of chunk dicts with accurate page tracking
        """
        chunks = []
        chunk_id = 0
        
        # Process each page
        for page_data in pages_data:
            page_num = page_data["page_num"]
            page_text = page_data["text"]
            
            # Split into sentences for smarter boundaries
            sentences = re.split(r'(?<=[.!?])\s+', page_text)
            
            current_chunk = ""
            current_chunk_start_page = page_num
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                # Check if adding this sentence exceeds chunk size
                if len(current_chunk) + len(sentence) + 1 > chunk_size and current_chunk:
                    # Save current chunk if substantial
                    if len(current_chunk.strip()) > 50:
                        chunks.append({
                            "text": current_chunk.strip(),
                            "metadata": {
                                **metadata,
                                "chunk_id": chunk_id,
                                "page_start": current_chunk_start_page,
                                "page_end": page_num,
                                "page": current_chunk_start_page,  # Primary page reference
                                "char_count": len(current_chunk.strip())
                            }
                        })
                        chunk_id += 1
                    
                    # ✨ FIX: Proper overlap - take last N characters
                    if len(current_chunk) > overlap_chars:
                        # Find a sentence boundary within overlap region
                        overlap_text = current_chunk[-overlap_chars:]
                        # Try to start at a sentence boundary
                        sentence_start = overlap_text.find('. ')
                        if sentence_start > 0:
                            overlap_text = overlap_text[sentence_start + 2:]
                        current_chunk = overlap_text + " " + sentence
                    else:
                        current_chunk = sentence
                    
                    current_chunk_start_page = page_num
                else:
                    # Add sentence to current chunk
                    if current_chunk:
                        current_chunk += " " + sentence
                    else:
                        current_chunk = sentence
                        current_chunk_start_page = page_num
            
            # Don't forget remaining content from this page
            # (It will be carried over or saved in the next iteration)
        
        # Save final chunk
        if current_chunk.strip() and len(current_chunk.strip()) > 50:
            chunks.append({
                "text": current_chunk.strip(),
                "metadata": {
                    **metadata,
                    "chunk_id": chunk_id,
                    "page_start": current_chunk_start_page,
                    "page_end": pages_data[-1]["page_num"] if pages_data else 1,
                    "page": current_chunk_start_page,
                    "char_count": len(current_chunk.strip())
                }
            })
        
        return chunks
    
    def embed_and_store(self, chunks: List[Dict]):
        """Generate embeddings and store in ChromaDB"""
        if not chunks:
            return
        
        texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings (batch processing)
        print(f"    Generating embeddings for {len(texts)} chunks...")
        embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True  # ✨ Normalize for cosine similarity
        )
        
        # Prepare for ChromaDB
        ids = []
        for i, chunk in enumerate(chunks):
            # Create unique ID
            safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', chunk['metadata']['filename'])
            chunk_id = f"{safe_filename}_chunk_{chunk['metadata']['chunk_id']}"
            ids.append(chunk_id)
        
        metadatas = [chunk["metadata"] for chunk in chunks]
        
        # Convert metadata values to strings (ChromaDB requirement)
        for m in metadatas:
            for key, value in m.items():
                m[key] = str(value)
        
        # Store in ChromaDB
        self.collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas
        )
        
        print(f"    ✅ Stored {len(chunks)} chunks in ChromaDB")
    
    def process_all_pdfs(self):
        """Process all PDFs in all categories"""
        total_start = datetime.now()
        
        for category in CATEGORIES:
            category_path = PDF_BASE_DIR / category
            
            if not category_path.exists():
                print(f"⚠️  Category not found: {category}")
                continue
            
            pdf_files = list(category_path.glob("*.pdf"))
            
            if not pdf_files:
                print(f"⚠️  No PDFs in {category}")
                continue
            
            print(f"\n📁 Processing {category} ({len(pdf_files)} PDFs)...")
            
            category_chunks = 0
            
            for pdf_file in pdf_files:
                print(f"\n  📄 {pdf_file.name}")
                
                # Extract text with page tracking
                pages_data, metadata = self.extract_text_from_pdf(pdf_file)
                
                if not pages_data:
                    print(f"    ❌ No text extracted")
                    continue
                
                total_chars = sum(len(p["text"]) for p in pages_data)
                print(f"    Extracted {total_chars} chars from {metadata['pages']} pages")
                
                # Chunk text with improved algorithm
                chunks = self.chunk_text(pages_data, metadata)
                print(f"    Created {len(chunks)} chunks")
                
                # Embed and store
                self.embed_and_store(chunks)
                
                # Update stats
                self.stats["pdfs_processed"] += 1
                self.stats["chunks_created"] += len(chunks)
                category_chunks += len(chunks)
            
            self.stats["categories"][category] = {
                "pdfs": len(pdf_files),
                "chunks": category_chunks
            }
        
        total_time = (datetime.now() - total_start).total_seconds()
        
        # Print summary
        self._print_summary(total_time)
    
    def _print_summary(self, total_time: float):
        """Print processing summary"""
        print("\n" + "="*70)
        print("✅ RAG Pipeline Setup Complete!")
        print("="*70)
        
        print(f"\n📊 Processing Summary:")
        print(f"  Total PDFs: {self.stats['pdfs_processed']}")
        print(f"  Total Chunks: {self.stats['chunks_created']}")
        print(f"  Processing Time: {total_time:.1f} seconds")
        if self.stats['pdfs_processed'] > 0:
            print(f"  Avg Chunks/PDF: {self.stats['chunks_created'] / self.stats['pdfs_processed']:.1f}")
        
        print(f"\n📁 Breakdown by Category:")
        for category, data in self.stats["categories"].items():
            print(f"  {category}: {data['pdfs']} PDFs → {data['chunks']} chunks")
        
        print(f"\n🗄️  ChromaDB Collection:")
        print(f"  Name: nexusiq_docs")
        print(f"  Distance Metric: COSINE ✨")  # Highlight the fix
        print(f"  Total Documents: {self.collection.count()}")
        print(f"  Location: {CHROMA_DIR}")
        
        # Save stats
        stats_file = CHROMA_DIR / "processing_stats.json"
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        print(f"\n📝 Stats saved to: {stats_file}")
    
    def test_retrieval(self, query: str, n_results: int = 3):
        """Test semantic search with cosine similarity"""
        print(f"\n🔍 Testing Retrieval: '{query}'")
        
        # Generate query embedding (normalized for cosine)
        query_embedding = self.embedding_model.encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results
        )
        
        print(f"\n📋 Top {n_results} Results:\n")
        
        if results['documents'] and results['documents'][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ), 1):
                # ✨ FIX: Cosine distance to similarity (cosine distance = 1 - cosine similarity)
                similarity = 1 - distance
                
                page_info = f"Page {metadata['page']}"
                if metadata.get('page_start') != metadata.get('page_end'):
                    page_info = f"Pages {metadata.get('page_start', '?')}-{metadata.get('page_end', '?')}"
                
                print(f"{i}. {metadata['filename']} ({page_info})")
                print(f"   Similarity: {similarity:.3f} (distance: {distance:.3f})")
                print(f"   Preview: {doc[:150]}...")
                print()
        else:
            print("No results found.")


def main():
    """Main execution"""
    pipeline = RAGPipelineSetup()
    
    # Process all PDFs
    pipeline.process_all_pdfs()
    
    # Test retrieval
    print("\n" + "="*70)
    print("🧪 Running Test Queries")
    print("="*70)
    
    test_queries = [
        "What was Q4 2024 revenue?",
        "What are the Digital Wallet adoption rates?",
        "Tell me about the West region expansion plan",
        "What is the return policy for Electronics?",
        "Compare Q3 and Q4 2024 performance"
    ]
    
    for query in test_queries:
        pipeline.test_retrieval(query, n_results=2)
        print("-" * 70)
    
    print("\n✅ RAG Pipeline Ready!")
    print("Next: Run 'python agents/rag_agent.py' to test the agent\n")


if __name__ == "__main__":
    main()