"""
Test Agentic RAG - Query Decomposition
"""

from agents.rag_agent import get_rag_agent

def test_comparison_queries():
    """Test comparison query handling"""
    
    agent = get_rag_agent()
    
    test_queries = [
        "Compare Q3 and Q4 2024 performance",
        "What's the difference between Q3 and Q4 revenue?",
        "How did Q4 2024 perform versus Q3 2024?",
    ]
    
    for query in test_queries:
        print(f"\n{'='*70}")
        print(f"QUERY: {query}")
        print(f"{'='*70}")
        
        result = agent.query(query)
        
        print(f"\nQUERY TYPE: {result['query_type']}")
        
        if result.get('decomposition'):
            print(f"\nDECOMPOSITION:")
            print(f"  Sub-queries: {result['decomposition']['sub_queries']}")
            print(f"  Entities: {result['decomposition'].get('entities', [])}")
        
        print(f"\nANSWER:\n{result['answer']}")
        
        print(f"\nMETADATA:")
        print(f"  Chunks Retrieved: {result['chunks_retrieved']}")
        print(f"  Query Time: {result['query_time']:.2f}s")
        print(f"  Model Used: {result['model_used']}")
        
        if result.get('sources'):
            print(f"\nSOURCES:")
            for src in result['sources'][:3]:
                cited = "✓" if src.get('cited_in_answer') else " "
                print(f"  [{cited}] {src['filename']} (Page {src['page']})")

if __name__ == "__main__":
    test_comparison_queries()
