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
        
        # Routing metadata (set per-query by _classify_query_source_llm)
        self._last_routing_model = None
        self._last_routing_fallback = False
        self._no_data_reason = None

        # Proactive Gemini rate limiter — free tier allows 5 req/min
        # Track timestamps of recent Gemini routing calls (rolling 60s window)
        self._gemini_routing_calls: list = []
        self._gemini_rpm_limit = 4  # stay 1 below hard limit as buffer

        logger.info("✅ Fusion Agent initialized with SQL + RAG + Web!")
    
    def _classify_query_source(self, question: str) -> str:
        """
        ✅ ENHANCED: Data-aware intelligent routing
        
        Uses data inventory to determine which sources can actually answer the question
        
        Returns:
            "sql_only" | "rag_only" | "web_only" | "sql_rag" | "comparison" | ...
        """
        
        from config.data_inventory import (
            can_sql_answer, can_rag_answer, can_web_answer, should_cross_validate
        )
        
        question_lower = question.lower()
        
        logger.info(f"🧠 Intelligent routing for: {question}")
        
        # ═══════════════════════════════════════════════════════
        # STEP 1: Check data availability in each source
        # ═══════════════════════════════════════════════════════
        
        sql_check = can_sql_answer(question)
        rag_check = can_rag_answer(question)
        web_check = can_web_answer(question)
        
        logger.info(f"  SQL: {sql_check['can_answer']} ({sql_check['confidence']})")
        logger.info(f"  RAG: {rag_check['can_answer']} ({rag_check['confidence']})")
        logger.info(f"  Web: {web_check['can_answer']} ({web_check['confidence']})")
        
        # ═══════════════════════════════════════════════════════
        # STEP 2: Priority routing based on question type
        # ═══════════════════════════════════════════════════════
        
        # Priority 1: Comparison queries (RAG agentic mode)
        if any(word in question_lower for word in ['compare', 'vs', 'versus', 'difference']):
            if any(q in question_lower for q in ['q1', 'q2', 'q3', 'q4', 'quarter']):
                logger.info("  → Route: comparison (RAG agentic)")
                return "comparison"
        
        # Priority 2: Cross-validation (SQL + RAG both have data)
        validation_check = should_cross_validate(question)
        if validation_check["should_validate"]:
            logger.info(f"  → Route: sql_rag (cross-validate {validation_check['validation_topic']})")
            return "sql_rag"
        
        # Priority 3: Single source with high confidence
        sources_available = []
        if sql_check["can_answer"] and sql_check["confidence"] == "high":
            sources_available.append("sql")
        if rag_check["can_answer"] and rag_check["confidence"] == "high":
            sources_available.append("rag")
        if web_check["can_answer"] and web_check["confidence"] == "high":
            sources_available.append("web")
        
        if len(sources_available) == 1:
            logger.info(f"  → Route: {sources_available[0]}_only")
            return f"{sources_available[0]}_only"
        
        # Priority 4: Multi-source fusion (normalize order: sql before rag/web)
        if len(sources_available) == 2:
            ordered = sorted(sources_available, key=lambda s: ["sql", "rag", "web"].index(s))
            route = "_".join(ordered)
            logger.info(f"  → Route: {route} (multi-source)")
            return route
        
        if len(sources_available) == 3:
            logger.info("  → Route: all (3 sources)")
            return "all"
        
        # Priority 5: Default fallback
        if sql_check["can_answer"]:
            logger.info("  → Route: sql_only (default fallback)")
            return "sql_only"
        elif rag_check["can_answer"]:
            logger.info("  → Route: rag_only (default fallback)")
            return "rag_only"
        else:
            logger.warning("  → Route: sql_only (no match, trying SQL anyway)")
            return "sql_only"

    def _classify_query_source_llm(self, question: str) -> Optional[str]:
        """
        LLM-based dynamic routing — understands meaning, not just keywords.
        Falls back to None on failure so caller can use keyword routing instead.
        """
        prompt = f"""You are a data routing agent for NexusIQ AI. Decide which sources answer the user question.

## Sources

**SQL** — 90,500 sales transactions for 2024 (Q1-Q4). Columns: date, region, category,
product, quantity, unit_price, total_amount, payment_method, customer_id.
✅ Use for: revenue, counts, rankings, trends, growth rates, quarterly breakdowns,
   "by quarter", "each quarter", "quarter over quarter", "year-over-year by quarter"
   (SQL has all 4 quarters of 2024 so it CAN show quarterly trends and compute
   quarter-over-quarter growth — even when the phrase "year-over-year" appears,
   if the question asks for a quarterly breakdown SQL must be included)
❌ Skip for: policies, strategies, contracts, competitor pricing

**RAG** — 23 PDF documents: Q1-Q4 2024 performance reports, return/privacy/compliance
policies, expansion plans, budget, digital wallet initiative, vendor contracts.
✅ Use for: policies, strategies, plans, performance narratives, compliance
   (also use alongside SQL for quarterly/revenue questions — PDF reports contain
   the same revenue figures, enabling cross-validation)
❌ Skip for: granular row-level transaction data

**Web** — live competitor pricing scraped from Newegg, IKEA, Campmor, Swanson.
✅ Use for: competitor prices, market pricing comparisons
❌ Skip for: anything about our own data

## Cross-Validation Rules (IMPORTANT — follow strictly)

**When to use sql=true AND rag=true (cross_validate=true):**
- Quarterly totals: "Q1/Q2/Q3/Q4 revenue", "quarterly performance", "compare quarters"
- Annual totals: "total revenue", "annual revenue", "full year"
- "Validate", "verify", "confirm", "cross-check" — always cross-validate
REASON: PDF quarterly reports independently confirm these aggregate figures.

**When to use sql=true ONLY (rag=false):**
- Rankings/top-N: "top 5 products", "best performing store", "highest revenue product"
- Breakdowns without quarterly context: "sales by region", "by payment method", "by category"
- Trends over months: "monthly trend", "month by month", "weekly sales"
- Counts: "how many transactions", "number of orders"
REASON: PDF reports do NOT contain product rankings, monthly trends, or payment breakdowns.
Adding RAG to these queries wastes time and adds no validation value.

**Other rules:**
- Strategy/policy only: rag=true, sql=false
- Competitor pricing only: web=true, sql=false, rag=false

## Question
"{question}"

Reply with ONLY this JSON (no extra text):
{{
  "sql": true or false,
  "rag": true or false,
  "web": true or false,
  "cross_validate": true or false,
  "reasoning": "one sentence"
}}"""

        # ── Proactive Gemini rate limiter ────────────────────────────────────────
        # Free tier = 5 req/min. Track rolling 60s window; wait if at limit.
        now_ts = time.time()
        self._gemini_routing_calls = [t for t in self._gemini_routing_calls if now_ts - t < 60]
        if len(self._gemini_routing_calls) >= self._gemini_rpm_limit:
            oldest = self._gemini_routing_calls[0]
            wait_s = 60 - (now_ts - oldest) + 1  # +1s buffer
            if wait_s > 0:
                logger.info(f"⏳ Gemini RPM limit reached — waiting {wait_s:.1f}s to avoid quota exhaustion")
                time.sleep(wait_s)
            self._gemini_routing_calls = [t for t in self._gemini_routing_calls if time.time() - t < 60]

        # Try available LLM clients in order: Gemini Flash → Groq
        clients = []
        if self.gemini_flash:
            clients.append(("Gemini Flash", self.gemini_flash))
        if self.groq_client:
            clients.append(("Groq", self.groq_client))

        primary_client_name = clients[0][0] if clients else None

        for client_name, client in clients:
            try:
                # Track Gemini calls for rate limiting
                if client_name == "Gemini Flash":
                    self._gemini_routing_calls.append(time.time())

                response = client.invoke(prompt)
                content = response.content.strip()

                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if not json_match:
                    continue

                routing = json.loads(json_match.group())
                is_fallback = client_name != primary_client_name
                routing["_routing_model"] = client_name
                routing["_routing_fallback"] = is_fallback
                if is_fallback:
                    logger.warning(f"  ⚠️  Routing fallback: primary LLM unavailable, using {client_name}")
                logger.info(f"  LLM routing ({client_name}) → {routing}")

                sources = []
                if routing.get("sql"):
                    sources.append("sql")
                if routing.get("rag"):
                    sources.append("rag")
                if routing.get("web"):
                    sources.append("web")

                if not sources:
                    # LLM explicitly says no source can answer — store reasoning and signal caller
                    self._last_routing_model = client_name
                    self._last_routing_fallback = routing.get("_routing_fallback", False)
                    self._no_data_reason = routing.get("reasoning", "No available source covers this query.")
                    logger.warning(f"  LLM says no source applies: {self._no_data_reason}")
                    return "no_data"

                if len(sources) == 1:
                    route = f"{sources[0]}_only"
                else:
                    if routing.get("cross_validate") and "sql" in sources and "rag" in sources:
                        route = "sql_rag" if len(sources) == 2 else "all"
                    elif len(sources) == 2:
                        # Normalize order: always sql before rag/web
                        ordered = sorted(sources, key=lambda s: ["sql","rag","web"].index(s))
                        route = "_".join(ordered)
                    else:
                        route = "all"

                # Safety net: questions asking for quarterly breakdowns need SQL
                # even if LLM said rag_only (SQL has full Q1-Q4 2024 data)
                quarter_terms = ["quarter", "quarterly", "q1","q2","q3","q4"]
                if route == "rag_only" and any(t in question.lower() for t in quarter_terms):
                    logger.info("  Safety net: quarterly question upgraded rag_only → sql_rag")
                    route = "sql_rag"

                # Attach routing metadata for callers
                self._last_routing_model = routing.get("_routing_model", client_name)
                self._last_routing_fallback = routing.get("_routing_fallback", False)

                return route

            except Exception as e:
                logger.warning(f"LLM routing failed ({client_name}): {e}")
                continue

        return None

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
            
            has_answer = bool(result.get('answer'))
            has_data   = bool(result.get('raw_data', {}).get('competitors'))
            hard_error = bool(result.get('error'))   # only set on total failure
            return {
                'success': (has_answer or has_data) and not hard_error,
                'answer': result.get('answer', 'No web data available'),
                'raw_data': result.get('raw_data', {}),
                'category': result.get('category'),
                'time': round(elapsed, 2),
                'source': 'Web Scraping',
                'llm_error': result.get('llm_error')
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
                cleaned = match.replace(',', '').strip()
                if not cleaned:
                    continue
                num = float(cleaned)
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
        if sql_result.get('success'):
            # Primary: extract formatted numbers from the SQL answer text
            # (catches aggregated totals like "$45.2M" that row-level data misses)
            answer_nums = self._extract_numbers(sql_result.get('answer', ''))
            for n in answer_nums:
                sql_numbers.append({'value': n, 'label': 'answer', 'source': 'SQL'})

            # Secondary: row-level numeric values (single-row results only —
            # multi-row results contain per-item amounts that don't match RAG totals)
            rows = sql_result.get('results', [])
            if len(rows) == 1:
                for key, value in rows[0].items():
                    if isinstance(value, (int, float)) and value > 1000:
                        sql_numbers.append({'value': float(value), 'label': key, 'source': 'SQL'})

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
            confidence_reason = f"Multiple discrepancies found ({len(discrepancies)}) — PDF figures may be projected/reported revenue while SQL reflects actual transaction totals"
        
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
        elif sql_result and not sql_result.get('success'):
            sources_text += f"""
SOURCE 1 - SQL DATABASE (Unavailable):
SQL query failed: {sql_result.get('error', 'unknown error')}. Answer will be based on documents only.
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
            discrepancy_note = ""
            if validation['confidence'] == "LOW" and validation.get('discrepancies'):
                discrepancy_note = """
- IMPORTANT: The numbers differ between SQL and PDF. In your answer you MUST explicitly state:
  1. SQL shows actual transaction revenue recorded in the database.
  2. PDF shows projected or reported revenue (may include adjustments, forecasts, or channels not in the database).
  3. The gap is normal in real businesses — it does NOT mean either source is wrong.
"""
            validation_text = f"""
CROSS-VALIDATION RESULTS:
- Confidence: {validation['confidence']} ({validation['confidence_reason']})
- Matches: {len(validation['matches'])} numbers verified across sources
- Discrepancies: {len(validation['discrepancies'])}{discrepancy_note}
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
6. If sources disagree, mention both with explanation — a common reason is that PDF reports contain projected/forecast revenue while the SQL database contains actual transaction revenue. Always tell the user which is which
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
    
    def query(self, question: str, force_source: Optional[str] = None) -> Dict:
        """
        ✅ UPDATED: Main fusion query method with Web Agent support

        Routes to appropriate source(s) and combines results.

        Args:
            question: The user's question
            force_source: Override auto-routing. One of "sql_only", "rag_only",
                          "web_only", or None to use auto-detection.
        """

        start_time = datetime.now()
        self._last_routing_model = None
        self._last_routing_fallback = False
        self._no_data_reason = None

        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 FUSION AGENT: {question}")
        logger.info(f"{'='*70}")

        # Step 1: Classify query source (forced → LLM → keyword fallback)
        if force_source:
            source_type = force_source
            logger.info(f"📋 Query routing: {source_type.upper()} (forced by user)")
        else:
            source_type = self._classify_query_source_llm(question)
            if source_type:
                logger.info(f"📋 Query routing: {source_type.upper()} (LLM)")
            else:
                source_type = self._classify_query_source(question)
                self._last_routing_model = "keyword fallback"
                self._last_routing_fallback = True
                logger.info(f"📋 Query routing: {source_type.upper()} (keyword fallback)")
        
        # Step 2: Execute based on routing
        sql_result = None
        rag_result = None
        web_result = None
        validation = None
        
        # ═══════════════════════════════════════════════════════════
        # NO DATA — LLM explicitly said no source covers this query
        # ═══════════════════════════════════════════════════════════

        if source_type == "no_data":
            reason = self._no_data_reason or "No available data source covers this query."
            logger.warning(f"→ No data route: {reason}")
            return {
                'answer': f"I don't have data to answer this question.\n\n**Reason:** {reason}\n\nAvailable data covers: SQL transactions (2024 only), internal PDF documents, and live competitor pricing.",
                'source_type': 'no_data',
                'sql_result': None,
                'rag_result': None,
                'web_result': None,
                'validation': None,
                'routing_model': self._last_routing_model,
                'routing_fallback': self._last_routing_fallback,
                'query_time': (datetime.now() - start_time).total_seconds()
            }

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
                'routing_model': self._last_routing_model,
                'routing_fallback': self._last_routing_fallback,
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
                'routing_model': self._last_routing_model,
                'routing_fallback': self._last_routing_fallback,
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
                'routing_model': self._last_routing_model,
                'routing_fallback': self._last_routing_fallback,
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
                'routing_model': self._last_routing_model,
                'routing_fallback': self._last_routing_fallback,
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

            # Downgrade source_type label when SQL silently failed
            if sql_result and not sql_result.get('success') and rag_result and rag_result.get('success'):
                logger.warning(f"SQL failed in {source_type} route — answer will be RAG-only. SQL error: {sql_result.get('error', 'unknown')}")
                source_type = "rag_only (sql_failed)"

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
                'web_result': web_result,
                'validation': validation,
                'sources': rag_result.get('sources', []) if rag_result else [],
                'routing_model': self._last_routing_model,
                'routing_fallback': self._last_routing_fallback,
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