"""
Test Fusion Agent - SQL + RAG Cross-Validation
"""

from agents.fusion_agent import get_fusion_agent


def test_fusion():
    """Test all query routing types"""
    
    agent = get_fusion_agent()
    
    test_queries = [
        # BOTH sources (cross-validation)
        {
            "query": "What was Q4 2024 Electronics revenue?",
            "expected_source": "both",
            "description": "Cross-validate revenue across SQL and PDF"
        },
        {
            "query": "What was Q4 2024 total revenue?",
            "expected_source": "both",
            "description": "Cross-validate total revenue"
        },
        
        # RAG only
        {
            "query": "What is the return policy for Electronics?",
            "expected_source": "rag_only",
            "description": "Policy question - only in PDFs"
        },
        
        # SQL only
        {
            "query": "How many transactions happened in October 2024?",
            "expected_source": "sql_only",
            "description": "Count query - better from SQL"
        },
        
        # Comparison (RAG agentic)
        {
            "query": "Compare Q3 and Q4 2024 revenue",
            "expected_source": "comparison",
            "description": "Quarter comparison - uses RAG agentic"
        },
    ]
    
    for test in test_queries:
        print(f"\n{'='*70}")
        print(f"QUERY: {test['query']}")
        print(f"EXPECTED SOURCE: {test['expected_source']}")
        print(f"DESCRIPTION: {test['description']}")
        print(f"{'='*70}")
        
        result = agent.query(test['query'])
        
        print(f"\n📋 Source Used: {result['source_type']}")
        routing_match = "✅" if result['source_type'] == test['expected_source'] else "⚠️"
        print(f"   Routing: {routing_match} (expected: {test['expected_source']})")
        
        print(f"\n📝 ANSWER:\n{result['answer']}")
        
        # Show validation if available
        if result.get('validation'):
            v = result['validation']
            confidence_emoji = {"HIGH": "✅", "MEDIUM": "🟡", "LOW": "🔴"}.get(v['confidence'], "⚪")
            print(f"\n🔍 CROSS-VALIDATION:")
            print(f"   {confidence_emoji} Confidence: {v['confidence']} ({v['confidence_reason']})")
            
            if v['matches']:
                print(f"   ✅ Matches:")
                for m in v['matches']:
                    print(f"      SQL: ${m['sql_value']:,.2f} | RAG: ${m['rag_value']:,.2f} | Diff: {m['pct_difference']}%")
            
            if v['discrepancies']:
                print(f"   ❌ Discrepancies:")
                for d in v['discrepancies']:
                    print(f"      SQL: ${d['sql_value']:,.2f} | RAG: ${d['rag_value']:,.2f} | Diff: {d['pct_difference']}%")
        
        # Show timing
        if result.get('sql_result'):
            print(f"\n⏱️  SQL time: {result['sql_result'].get('time', 0)}s")
        if result.get('rag_result'):
            print(f"⏱️  RAG time: {result['rag_result'].get('time', 0)}s")
        print(f"⏱️  Total time: {result['query_time']:.2f}s")
        
        print(f"\n{'-'*70}")
    
    agent.close()
    print("\n✅ Fusion Agent testing complete!")


if __name__ == "__main__":
    test_fusion()
