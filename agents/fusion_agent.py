"""
Fusion Agent - Cross-Source Intelligence
Combines SQL database queries with RAG document search
for validated, comprehensive answers.

Features:
- Smart query routing (SQL-only, RAG-only, or BOTH)
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
from config.settings import settings
from utils.quota_tracker import get_tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

quota_tracker = get_tracker()


class FusionAgent:
    """
    Orchestrates SQL Agent and RAG Agent for cross-source intelligence
    """
    
    def __init__(self):
        logger.info("Initializing Fusion Agent...")
        
        # Initialize sub-agents
        self.sql_agent = SQLAgent(mode="development")
        self.rag_agent = get_rag_agent()
        
        # LLM clients (reuse from RAG agent)
        self.gemini_flash = self.rag_agent.gemini_flash
        self.groq_client = self.rag_agent.groq_client
        
        logger.info("✅ Fusion Agent initialized!")
    
    def _classify_query_source(self, question: str) -> str:
        """
        Determine which source(s) to use for answering
        
        Returns:
            "sql_only" - Pure data questions (counts, sums, lists)
            "rag_only" - Context/policy questions (why, explain, policy)
            "both" - Questions that benefit from cross-validation
            "comparison" - Quarter/period comparisons (use RAG agentic)
        """
        
        question_lower = question.lower()
        
        # Comparison queries → RAG agentic mode
        comparison_words = ['compare', 'vs', 'versus', 'difference between']
        if any(word in question_lower for word in comparison_words):
            return "comparison"
        
        # RAG-only: Policy, strategy, explanation questions
        rag_indicators = [
            'policy', 'return policy', 'contract', 'agreement',
            'why', 'explain', 'strategy', 'plan', 'recommend',
            'expansion', 'roadmap', 'compliance', 'employee',
            'handbook', 'procedure'
        ]
        if any(ind in question_lower for ind in rag_indicators):
            return "rag_only"
        
        # SQL-only: Very specific data queries
        sql_only_indicators = [
            'how many transactions', 'count', 'list all',
            'show all', 'top 10', 'bottom 5',
            'each store', 'per store', 'daily',
            'specific date', 'on january', 'on february'
        ]
        if any(ind in question_lower for ind in sql_only_indicators):
            return "sql_only"
        
        # BOTH: Revenue, sales, performance questions with numbers
        both_indicators = [
            'revenue', 'sales', 'total', 'growth',
            'quarter', 'q1', 'q2', 'q3', 'q4',
            'region', 'category', 'electronics', 'clothing',
            'digital wallet', 'payment', 'performance',
            'validate', 'verify', 'confirm', 'check',
            'how much', 'what was'
        ]
        if any(ind in question_lower for ind in both_indicators):
            return "both"
        
        # Default to both (safer)
        return "both"
    
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
        sql_result: Dict,
        rag_result: Dict,
        validation: Dict
    ) -> str:
        """Generate unified answer combining both sources"""
        
        # Build fusion prompt
        fusion_prompt = f"""You are a business intelligence analyst. Combine information from TWO data sources into ONE comprehensive answer.

QUESTION: {question}

SOURCE 1 - SQL DATABASE (Exact transaction data):
{sql_result.get('answer', 'No SQL data available')}
SQL Query Used: {sql_result.get('query', 'N/A')}

SOURCE 2 - DOCUMENT REPORTS (Business context and analysis):
{rag_result.get('answer', 'No document data available')}

CROSS-VALIDATION RESULTS:
- Confidence: {validation['confidence']} ({validation['confidence_reason']})
- Matches: {len(validation['matches'])} numbers verified across sources
- Discrepancies: {len(validation['discrepancies'])}

RULES:
1. Combine the BEST information from both sources
2. Use SQL for exact numbers (it queries actual transaction records)
3. Use PDF reports for context, trends, and explanations
4. Mention when data is VALIDATED across sources
5. If sources disagree, mention both with explanation
6. Start with a direct answer, then supporting details
7. End with confidence level

FORMAT:
📊 **Answer:** [Direct answer]

**Details:**
- [Bullet points combining SQL precision + PDF context]

**Sources:**
- 🗄️ SQL: [what SQL provided]
- 📄 Documents: [what PDFs provided]

**Confidence:** [HIGH/MEDIUM/LOW] - [reason]

ANSWER:"""

        # Use fallback chain
        models_to_try = [
            ("gemini-2.5-flash", self.gemini_flash),
            ("llama-3.3-70b-versatile", self.groq_client),
        ]
        
        for model_name, client in models_to_try:
            if client is None:
                continue
            
            available, reason = quota_tracker.is_available(model_name)
            if not available:
                continue
            
            try:
                response = client.invoke(fusion_prompt)
                quota_tracker.report_success(model_name)
                return response.content
            except Exception as e:
                quota_tracker.report_failure(model_name, str(e))
                continue
        
        # Fallback: Simple combination
        return self._simple_fusion(sql_result, rag_result, validation)
    
    def _simple_fusion(self, sql_result: Dict, rag_result: Dict, validation: Dict) -> str:
        """Fallback fusion without LLM"""
        
        parts = []
        
        if sql_result.get('success'):
            parts.append(f"🗄️ **SQL Database:**\n{sql_result['answer']}")
        
        if rag_result.get('success'):
            parts.append(f"📄 **Documents:**\n{rag_result['answer']}")
        
        confidence_emoji = {"HIGH": "✅", "MEDIUM": "🟡", "LOW": "🔴"}.get(validation['confidence'], "⚪")
        parts.append(f"\n**Confidence:** {confidence_emoji} {validation['confidence']} - {validation['confidence_reason']}")
        
        return "\n\n".join(parts)
    
    def query(self, question: str) -> Dict:
        """
        Main fusion query method
        
        Routes to appropriate source(s) and combines results
        """
        
        start_time = datetime.now()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 FUSION AGENT: {question}")
        logger.info(f"{'='*70}")
        
        # Step 1: Classify query source
        source_type = self._classify_query_source(question)
        logger.info(f"📋 Query routing: {source_type}")
        
        # Step 2: Execute based on routing
        sql_result = None
        rag_result = None
        validation = None
        
        if source_type == "sql_only":
            logger.info("→ Using SQL Agent only")
            sql_result = self._run_sql_query(question)
            
            answer = sql_result.get('answer', 'No answer generated')
            
            return {
                'answer': answer,
                'source_type': source_type,
                'sql_result': sql_result,
                'rag_result': None,
                'validation': None,
                'query_time': (datetime.now() - start_time).total_seconds()
            }
        
        elif source_type == "rag_only":
            logger.info("→ Using RAG Agent only")
            rag_result = self._run_rag_query(question)
            
            answer = rag_result.get('answer', 'No answer generated')
            
            return {
                'answer': answer,
                'source_type': source_type,
                'sql_result': None,
                'rag_result': rag_result,
                'validation': None,
                'sources': rag_result.get('sources', []),
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
                'validation': None,
                'sources': rag_result.get('sources', []),
                'query_time': (datetime.now() - start_time).total_seconds()
            }
        
        else:  # "both"
            logger.info("→ Using BOTH SQL + RAG with cross-validation")
            
            # Run both agents
            sql_result = self._run_sql_query(question)
            rag_result = self._run_rag_query(question)
            
            # Cross-validate
            validation = self._cross_validate(sql_result, rag_result)
            
            # Generate fused answer
            answer = self._generate_fused_answer(
                question, sql_result, rag_result, validation
            )
            
            query_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ Fusion complete in {query_time:.2f}s")
            
            return {
                'answer': answer,
                'source_type': source_type,
                'sql_result': sql_result,
                'rag_result': rag_result,
                'validation': validation,
                'sources': rag_result.get('sources', []),
                'query_time': query_time
            }
    
    def close(self):
        """Clean up resources"""
        self.sql_agent.close()
        logger.info("🔌 Fusion Agent closed")


# Singleton
_fusion_instance = None

def get_fusion_agent() -> FusionAgent:
    """Get singleton Fusion Agent instance"""
    global _fusion_instance
    if _fusion_instance is None:
        _fusion_instance = FusionAgent()
    return _fusion_instance
