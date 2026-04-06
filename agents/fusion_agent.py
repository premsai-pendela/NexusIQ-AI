"""
Fusion Agent - Cross-Source Intelligence
Combines SQL database queries with RAG document search and Web scraping
for validated, comprehensive answers.

Features:
- Smart query routing (SQL-only, RAG-only, Web-only, or multi-source)
- Cross-source validation
- Confidence scoring
- Unified answer generation
"""

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import re
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agents.sql_agent import SQLAgent
from agents.rag_agent import get_rag_agent
from agents.web_agent import get_web_agent  # ✅ NEW: Import Web Agent
from config.settings import settings
from utils.quota_tracker import get_tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

quota_tracker = get_tracker()


class FusionAgent:
    """
    Orchestrates SQL Agent, RAG Agent, and Web Agent for cross-source intelligence
    """
    
    def __init__(self):
        logger.info("Initializing Fusion Agent...")
        
        # Initialize sub-agents
        self.sql_agent = SQLAgent(mode="development")
        self.rag_agent = get_rag_agent()
        self.web_agent = get_web_agent()  # ✅ NEW: Initialize Web Agent
        
        # LLM clients (reuse from RAG agent)
        self.gemini_flash = self.rag_agent.gemini_flash
        self.groq_client = self.rag_agent.groq_client
        
        logger.info("✅ Fusion Agent initialized with SQL + RAG + Web!")
    
    def _classify_query_source(self, question: str) -> str:
        """
        Determine which source(s) to use for answering
        
        Returns:
            "sql_only" | "rag_only" | "web_only" | "sql_rag" | "sql_web" | "rag_web" | "all"
        """
        
        question_lower = question.lower()
        
        # ✅ PRIORITY 1: Web-only (competitor/industry questions)
        web_indicators = [
            'competitor', 'walmart', 'best buy', 'target',
            'industry trend', 'market', 'pricing', 'price comparison',
            'news', 'latest trends', 'current market',
            'what are competitors', 'how do we compare'
        ]
        if any(ind in question_lower for ind in web_indicators):
            return "web_only"
        
        # ✅ PRIORITY 2: Comparison queries → RAG agentic mode
        comparison_words = ['compare', 'vs', 'versus', 'difference between']
        if any(word in question_lower for word in comparison_words):
            # Check if it's comparing quarters/periods (RAG)
            if any(period in question_lower for period in ['q1', 'q2', 'q3', 'q4', 'quarter', 'year']):
                return "comparison"
            # Otherwise might be competitor comparison (Web + RAG)
            else:
                return "rag_web"
        
        # ✅ PRIORITY 3: RAG-only (policy/strategy questions)
        rag_indicators = [
            'policy', 'return policy', 'contract', 'agreement',
            'why', 'explain', 'strategy', 'plan', 'recommend',
            'expansion', 'roadmap', 'compliance', 'employee',
            'handbook', 'procedure', 'budget allocation'
        ]
        if any(ind in question_lower for ind in rag_indicators):
            return "rag_only"
        
        # ✅ PRIORITY 4: SQL-only (specific data queries)
        sql_only_indicators = [
            'how many transactions', 'count', 'list all',
            'show all', 'top 10', 'bottom 5',
            'each store', 'per store', 'daily',
            'specific date', 'on january', 'on february'
        ]
        if any(ind in question_lower for ind in sql_only_indicators):
            return "sql_only"
        
        # ✅ PRIORITY 5: SQL + RAG (revenue/performance with validation)
        both_indicators = [
            'revenue', 'sales', 'total', 'growth',
            'quarter', 'q1', 'q2', 'q3', 'q4',
            'region', 'category', 'electronics', 'clothing',
            'digital wallet', 'payment', 'performance',
            'validate', 'verify', 'confirm', 'check',
            'how much', 'what was'
        ]
        if any(ind in question_lower for ind in both_indicators):
            return "sql_rag"
        
        # ✅ PRIORITY 6: Web + RAG (competitive intelligence with context)
        web_rag_indicators = [
            'competitor revenue', 'industry benchmark', 'pricing strategy',
            'market position', 'competitive advantage'
        ]
        if any(ind in question_lower for ind in web_rag_indicators):
            return "rag_web"
        
        # ✅ DEFAULT: SQL + RAG (safest for business questions)
        return "sql_rag"
    
    def _run_sql_query(self, question: str) -> Dict:
        """Run SQL Agent and capture results"""
        
        logger.info("🗄️  Running SQL Agent...")
        start = time.time()
        
        try:
            result = self.sql_agent.ask(question)
            elapsed = time.time() - start
            
            return {
                'success': result.get('success', False),
                'answer': result.get('answer', ''),
                'query': result.get('query', ''),
                'results': result.get('results', []),
                'row_count': result.get('row_count', 0),
                'model_used': result.get('model_used', ''),
                'time': round(elapsed, 2),
                'source': 'SQL Database'
            }
            
        except Exception as e:
            logger.error(f"SQL Agent failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'time': round(time.time() - start, 2),
                'source': 'SQL Database'
            }
    
    def _run_rag_query(self, question: str) -> Dict:
        """Run RAG Agent and capture results"""
        
        logger.info("📄 Running RAG Agent...")
        start = time.time()
        
        try:
            result = self.rag_agent.query(question)
            elapsed = time.time() - start
            
            return {
                'success': True if result.get('answer') and 'couldn\'t find' not in result.get('answer', '').lower() else False,
                'answer': result.get('answer', ''),
                'sources': result.get('sources', []),
                'chunks_retrieved': result.get('chunks_retrieved', 0),
                'model_used': result.get('model_used', ''),
                'query_type': result.get('query_type', 'simple'),
                'time': round(elapsed, 2),
                'source': 'PDF Documents'
            }
            
        except Exception as e:
            logger.error(f"RAG Agent failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'time': round(time.time() - start, 2),
                'source': 'PDF Documents'
            }
    
    def _run_web_query(self, question: str) -> Dict:
        """✅ NEW: Run Web Agent and capture results"""
        
        logger.info("🌐 Running Web Agent...")
        start = time.time()
        
        try:
            # Detect category from question
            category = None
            categories = ['electronics', 'clothing', 'home', 'food', 'sports']
            for cat in categories:
                if cat in question.lower():
                    category = cat
                    break
            
            result = self.web_agent.query(question, category=category)
            elapsed = time.time() - start
            
            return {
                'success': True if result.get('answer') and 'error' not in result.get('answer', '').lower() else False,
                'answer': result.get('answer', 'No web data available'),
                'raw_data': result.get('raw_data', {}),
                'category': result.get('category'),
                'time': round(elapsed, 2),
                'source': 'Web Scraping'
            }
            
        except Exception as e:
            logger.error(f"Web Agent failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'time': round(time.time() - start, 2),
                'source': 'Web Scraping'
            }
    
    def _extract_numbers(self, text: str) -> List[float]:
        """Extract dollar amounts from text"""
        
        numbers = []
        
        # Match patterns like $45.2M, $15,400,000, $38.7 million
        patterns = [
            r'\$?([\d,]+(?:\.\d+)?)\s*(?:M|million)',  # $45.2M
            r'\$?([\d,]+(?:\.\d+)?)\s*(?:B|billion)',   # $1.5B
            r'\$([\d,]+(?:\.\d+)?)',                      # $15,400,000
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                num = float(match.replace(',', ''))
                # Normalize to actual value
                if 'M' in text[text.find(match):text.find(match)+len(match)+5].upper() or 'million' in text[text.find(match):text.find(match)+len(match)+10].lower():
                    num = num * 1_000_000
                elif 'B' in text[text.find(match):text.find(match)+len(match)+5].upper():
                    num = num * 1_000_000_000
                numbers.append(num)
        
        return numbers
    
    def _cross_validate(self, sql_result: Dict, rag_result: Dict) -> Dict:
        """
        Cross-validate results from SQL and RAG
        
        Returns:
            {
                'validated': bool,
                'confidence': str (HIGH/MEDIUM/LOW),
                'confidence_score': float (0-1),
                'sql_numbers': list,
                'rag_numbers': list,
                'matches': list,
                'discrepancies': list
            }
        """
        
        logger.info("🔍 Cross-validating sources...")
        
        # Extract numbers from both sources
        sql_numbers = []
        if sql_result.get('success') and sql_result.get('results'):
            # Get numbers from SQL results
            for row in sql_result['results']:
                for key, value in row.items():
                    if isinstance(value, (int, float)) and value > 0:
                        sql_numbers.append({
                            'value': float(value),
                            'label': key,
                            'source': 'SQL'
                        })
        
        rag_numbers = self._extract_numbers(rag_result.get('answer', ''))
        rag_number_dicts = [{'value': n, 'label': 'extracted', 'source': 'RAG'} for n in rag_numbers]
        
        # Compare numbers
        matches = []
        discrepancies = []
        
        for sql_num in sql_numbers:
            sql_val = sql_num['value']
            best_match = None
            best_diff = float('inf')
            
            for rag_num in rag_number_dicts:
                rag_val = rag_num['value']
                
                # Check if values are close (within 1% tolerance)
                if sql_val > 0:
                    pct_diff = abs(sql_val - rag_val) / sql_val * 100
                    
                    if pct_diff < best_diff:
                        best_diff = pct_diff
                        best_match = {
                            'sql_value': sql_val,
                            'rag_value': rag_val,
                            'difference': abs(sql_val - rag_val),
                            'pct_difference': round(pct_diff, 4),
                            'label': sql_num['label']
                        }
            
            if best_match:
                if best_match['pct_difference'] < 1.0:  # Within 1%
                    matches.append(best_match)
                elif best_match['pct_difference'] < 10.0:  # Within 10%
                    best_match['note'] = 'Close but not exact match'
                    matches.append(best_match)
                else:
                    discrepancies.append(best_match)
        
        # Calculate confidence
        total_comparisons = len(matches) + len(discrepancies)
        
        if total_comparisons == 0:
            confidence = "MEDIUM"
            confidence_score = 0.5
            confidence_reason = "No overlapping numbers to validate"
        elif len(discrepancies) == 0 and len(matches) > 0:
            confidence = "HIGH"
            confidence_score = 0.95
            confidence_reason = f"{len(matches)} numbers match across sources"
        elif len(matches) > len(discrepancies):
            confidence = "MEDIUM"
            confidence_score = 0.7
            confidence_reason = f"{len(matches)} matches, {len(discrepancies)} discrepancies"
        else:
            confidence = "LOW"
            confidence_score = 0.3
            confidence_reason = f"Multiple discrepancies found ({len(discrepancies)})"
        
        validation = {
            'validated': len(discrepancies) == 0 and len(matches) > 0,
            'confidence': confidence,
            'confidence_score': confidence_score,
            'confidence_reason': confidence_reason,
            'matches': matches,
            'discrepancies': discrepancies,
            'sql_numbers_found': len(sql_numbers),
            'rag_numbers_found': len(rag_numbers)
        }
        
        logger.info(f"  Validation: {confidence} confidence ({confidence_reason})")
        
        return validation
    
    def _generate_fused_answer(
        self, 
        question: str,
        sql_result: Optional[Dict] = None,
        rag_result: Optional[Dict] = None,
        web_result: Optional[Dict] = None,  # ✅ NEW: Web result parameter
        validation: Optional[Dict] = None
    ) -> str:
        """✅ UPDATED: Generate unified answer combining SQL + RAG + Web sources"""
        
        # Build source summaries
        sources_text = ""
        
        if sql_result and sql_result.get('success'):
            sources_text += f"""
SOURCE 1 - SQL DATABASE (Exact transaction data):
{sql_result.get('answer', 'No SQL data available')}
SQL Query Used: {sql_result.get('query', 'N/A')}
"""
        
        if rag_result and rag_result.get('success'):
            sources_text += f"""
SOURCE 2 - DOCUMENT REPORTS (Business context and analysis):
{rag_result.get('answer', 'No document data available')}
"""
        
        if web_result and web_result.get('success'):
            sources_text += f"""
SOURCE 3 - WEB SCRAPING (Competitor & industry data):
{web_result.get('answer', 'No web data available')}
"""
        
        # Build validation text
        validation_text = ""
        if validation:
            validation_text = f"""
CROSS-VALIDATION RESULTS:
- Confidence: {validation['confidence']} ({validation['confidence_reason']})
- Matches: {len(validation['matches'])} numbers verified across sources
- Discrepancies: {len(validation['discrepancies'])}
"""
        
        # Build fusion prompt
        fusion_prompt = f"""You are a business intelligence analyst. Combine information from MULTIPLE data sources into ONE comprehensive answer.

QUESTION: {question}

{sources_text}

{validation_text}

RULES:
1. Combine the BEST information from all available sources
2. Use SQL for exact numbers (it queries actual transaction records)
3. Use PDF reports for context, trends, and strategic explanations
4. Use Web data for competitor comparisons and market context
5. When data is VALIDATED across sources, mention it with confidence
6. If sources disagree, mention both with explanation
7. Start with a direct answer, then supporting details
8. End with confidence level (if validation available)

FORMAT:
📊 **Answer:** [Direct answer to the question]

**Details:**
- [Bullet points combining precision from SQL + context from PDFs + market data from Web]

**Sources Used:**
{f"- 🗄️ SQL Database: {sql_result.get('row_count', 0)} transactions analyzed" if sql_result and sql_result.get('success') else ""}
{f"- 📄 Documents: {rag_result.get('chunks_retrieved', 0)} document excerpts" if rag_result and rag_result.get('success') else ""}
{f"- 🌐 Web Scraping: {web_result.get('category', 'General')} data" if web_result and web_result.get('success') else ""}

{f"**Confidence:** {validation['confidence']} - {validation['confidence_reason']}" if validation else ""}

ANSWER:"""

        # Use fallback chain for synthesis
        models_to_try = [
            ("gemini-2.5-flash", self.gemini_flash),
            ("llama-3.3-70b-versatile", self.groq_client),
        ]
        
        for model_name, client in models_to_try:
            if client is None:
                continue
            
            available, reason = quota_tracker.is_available(model_name)
            if not available:
                logger.debug(f"Skipping {model_name}: {reason}")
                continue
            
            try:
                response = client.invoke(fusion_prompt)
                quota_tracker.report_success(model_name)
                logger.info(f"✅ Fused answer generated with {model_name}")
                return response.content
            except Exception as e:
                quota_tracker.report_failure(model_name, str(e))
                logger.warning(f"Fusion failed with {model_name}: {str(e)[:100]}")
                continue
        
        # Fallback: Simple combination without LLM
        logger.warning("All LLM models failed, using simple fusion")
        return self._simple_fusion(sql_result, rag_result, web_result, validation)
    
    def _simple_fusion(
        self, 
        sql_result: Optional[Dict], 
        rag_result: Optional[Dict], 
        web_result: Optional[Dict],  # ✅ NEW
        validation: Optional[Dict]
    ) -> str:
        """✅ UPDATED: Fallback fusion without LLM (includes Web)"""
        
        parts = []
        
        if sql_result and sql_result.get('success'):
            parts.append(f"🗄️ **SQL Database:**\n{sql_result['answer']}")
        
        if rag_result and rag_result.get('success'):
            parts.append(f"📄 **Documents:**\n{rag_result['answer']}")
        
        if web_result and web_result.get('success'):
            parts.append(f"🌐 **Web Data:**\n{web_result['answer']}")
        
        if validation:
            confidence_emoji = {"HIGH": "✅", "MEDIUM": "🟡", "LOW": "🔴"}.get(validation['confidence'], "⚪")
            parts.append(f"\n**Confidence:** {confidence_emoji} {validation['confidence']} - {validation['confidence_reason']}")
        
        return "\n\n".join(parts)
    
    def query(self, question: str) -> Dict:
        """
        ✅ UPDATED: Main fusion query method with Web Agent support
        
        Routes to appropriate source(s) and combines results
        """
        
        start_time = datetime.now()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 FUSION AGENT: {question}")
        logger.info(f"{'='*70}")
        
        # Step 1: Classify query source
        source_type = self._classify_query_source(question)
        logger.info(f"📋 Query routing: {source_type.upper()}")
        
        # Step 2: Execute based on routing
        sql_result = None
        rag_result = None
        web_result = None
        validation = None
        
        # ═══════════════════════════════════════════════════════════
        # SINGLE-SOURCE ROUTES
        # ═══════════════════════════════════════════════════════════
        
        if source_type == "sql_only":
            logger.info("→ Using SQL Agent only")
            sql_result = self._run_sql_query(question)
            
            return {
                'answer': sql_result.get('answer', 'No answer generated'),
                'source_type': source_type,
                'sql_result': sql_result,
                'rag_result': None,
                'web_result': None,
                'validation': None,
                'query_time': (datetime.now() - start_time).total_seconds()
            }
        
        elif source_type == "rag_only":
            logger.info("→ Using RAG Agent only")
            rag_result = self._run_rag_query(question)
            
            return {
                'answer': rag_result.get('answer', 'No answer generated'),
                'source_type': source_type,
                'sql_result': None,
                'rag_result': rag_result,
                'web_result': None,
                'validation': None,
                'sources': rag_result.get('sources', []),
                'query_time': (datetime.now() - start_time).total_seconds()
            }
        
        elif source_type == "web_only":
            logger.info("→ Using Web Agent only")
            web_result = self._run_web_query(question)
            
            return {
                'answer': web_result.get('answer', 'No answer generated'),
                'source_type': source_type,
                'sql_result': None,
                'rag_result': None,
                'web_result': web_result,
                'validation': None,
                'query_time': (datetime.now() - start_time).total_seconds()
            }
        
        elif source_type == "comparison":
            logger.info("→ Using RAG Agentic Comparison")
            rag_result = self._run_rag_query(question)
            
            return {
                'answer': rag_result.get('answer', 'No answer generated'),
                'source_type': source_type,
                'sql_result': None,
                'rag_result': rag_result,
                'web_result': None,
                'validation': None,
                'sources': rag_result.get('sources', []),
                'query_time': (datetime.now() - start_time).total_seconds()
            }
        
        # ═══════════════════════════════════════════════════════════
        # MULTI-SOURCE ROUTES (sql_rag, sql_web, rag_web, all)
        # ═══════════════════════════════════════════════════════════
        
        else:
            logger.info(f"→ Using MULTI-SOURCE fusion: {source_type.upper()}")
            
            # Run agents based on source_type
            if 'sql' in source_type:
                sql_result = self._run_sql_query(question)
            
            if 'rag' in source_type:
                rag_result = self._run_rag_query(question)
            
            if 'web' in source_type:
                web_result = self._run_web_query(question)
            
            # Cross-validate if we have SQL + RAG
            if sql_result and rag_result and sql_result.get('success') and rag_result.get('success'):
                validation = self._cross_validate(sql_result, rag_result)
            
            # Generate fused answer
            answer = self._generate_fused_answer(
                question, 
                sql_result, 
                rag_result, 
                web_result,  # ✅ Now properly passed
                validation
            )
            
            query_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ Fusion complete in {query_time:.2f}s")
            
            return {
                'answer': answer,
                'source_type': source_type,
                'sql_result': sql_result,
                'rag_result': rag_result,
                'web_result': web_result,  # ✅ Now included in response
                'validation': validation,
                'sources': rag_result.get('sources', []) if rag_result else [],
                'query_time': query_time
            }
    
    def close(self):
        """Clean up resources"""
        self.sql_agent.close()
        self.web_agent.close()  # ✅ NEW: Close Web Agent
        logger.info("🔌 Fusion Agent closed")


# Singleton
_fusion_instance = None

def get_fusion_agent() -> FusionAgent:
    """Get singleton Fusion Agent instance"""
    global _fusion_instance
    if _fusion_instance is None:
        _fusion_instance = FusionAgent()
    return _fusion_instance


# ═══════════════════════════════════════════════════════════
#  CLI TESTING
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    """Test Fusion Agent from command line"""
    
    print("\n" + "="*70)
    print("🔗 Fusion Agent - Multi-Source Testing")
    print("="*70 + "\n")
    
    agent = get_fusion_agent()
    
    test_questions = [
        ("What was Q4 2024 Electronics revenue?", "sql_rag"),  # SQL + RAG validation
        ("What is the return policy?", "rag_only"),            # RAG only
        ("How many transactions in October?", "sql_only"),     # SQL only
        ("What are competitor prices for electronics?", "web_only"),  # Web only
        ("Compare our pricing to Walmart", "rag_web"),         # RAG + Web
    ]
    
    for question, expected_route in test_questions:
        print(f"\n{'='*70}")
        print(f"Q: {question}")
        print(f"Expected Route: {expected_route}")
        print(f"{'='*70}\n")
        
        result = agent.query(question)
        
        print(f"Actual Route: {result['source_type']}")
        print(f"\nA: {result['answer']}\n")
        
        print(f"⏱️  Query Time: {result['query_time']:.2f}s")
        
        if result.get('validation'):
            v = result['validation']
            print(f"🔍 Validation: {v['confidence']} - {v['confidence_reason']}")
        
        print("\n" + "-"*70)
    
    agent.close()
    print("\n✅ Fusion Agent testing complete!\n")