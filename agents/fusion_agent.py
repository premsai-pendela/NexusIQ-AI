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
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agents.sql_agent import SQLAgent
from agents.rag_agent import get_rag_agent
from agents.web_agent import get_web_agent  # ✅ NEW: Import Web Agent
from config.settings import settings
from observability.tracer import TraceSession, get_tracer, summarize_agent_result
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

        # Query result cache: {question_lower: (result_dict, timestamp)}
        # TTL = 3600s, max 50 entries (evict oldest on overflow)
        self._query_cache: Dict[str, tuple] = {}
        self._cache_ttl = 3600
        self._cache_max = 50

        # Conversation history — last N turns for context engineering
        self._history: List[Dict[str, str]] = []
        self._history_max = 5

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

    def _history_context(self, max_turns: int = 3) -> str:
        if not self._history:
            return ""
        turns = "\n".join(
            f"Q: {turn['question']}\nA: {turn['answer']}"
            for turn in self._history[-max_turns:]
        )
        return f"\n## Conversation History\n{turns}\n"

    def _resolve_question(self, question: str) -> str:
        """Expand ambiguous follow-up using conversation history. Returns original if no history or LLM fails."""
        if not self._history:
            return question

        history_ctx = self._history_context(max_turns=3)
        prompt = f"""Given this conversation history and a follow-up question, rewrite the follow-up as a complete standalone question.
If the follow-up is already self-contained and clear, return it unchanged.
Output ONLY the rewritten question, no explanation, no quotes.

{history_ctx}
Follow-up: {question}
Standalone question:"""

        for client in [self.gemini_flash, self.groq_client]:
            if client is None:
                continue
            try:
                response = client.invoke(prompt)
                resolved = response.content.strip().strip("\"'")
                if resolved:
                    return resolved
            except Exception as exc:
                logger.debug(f"Question resolution failed with client: {exc}")

        return question

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

{self._history_context()}## Question
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
    
    def _infer_number_context(self, text: str, fallback: str = "value") -> str:
        """Infer a rough business context so close but different facts do not merge."""
        text_lower = str(text or "").lower()
        context_keywords = {
            "revenue": ["revenue", "sales", "total_amount", "amount"],
            "expense": ["expense", "cost", "spend"],
            "profit": ["profit", "income", "earnings"],
            "margin": ["margin"],
            "price": ["price", "pricing"],
            "quantity": ["quantity", "units"],
            "count": ["count", "transactions_analyzed", "transaction_count"],
        }
        for context, keywords in context_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return context
        return fallback

    def _extract_number_facts(self, text: str, source: str, label: str = "answer") -> List[Dict]:
        """Extract monetary/large-number facts with lightweight context."""
        facts = []
        if not text:
            return facts

        # Match patterns like $45.2M, $15,400,000, $38.7 million
        pattern = re.compile(
            r'\$?([\d,]+(?:\.\d+)?)\s*(M|million|B|billion)?',
            re.IGNORECASE
        )

        for match in pattern.finditer(text):
            raw_number, scale = match.groups()
            has_dollar = match.group(0).strip().startswith("$")
            has_scale = bool(scale)
            if not has_dollar and not has_scale:
                continue

            cleaned = raw_number.replace(',', '').strip()
            if not cleaned:
                continue

            try:
                value = float(cleaned)
            except ValueError:
                continue

            scale_lower = (scale or "").lower()
            if scale_lower in {"m", "million"}:
                value *= 1_000_000
            elif scale_lower in {"b", "billion"}:
                value *= 1_000_000_000

            window = text[max(0, match.start() - 45):match.end() + 45]
            facts.append({
                'value': value,
                'label': label,
                'context': self._infer_number_context(window, fallback=label),
                'source': source,
            })

        facts.extend(self._extract_percentage_revenue_facts(text, source=source))
        return facts

    def _extract_percentage_revenue_facts(self, text: str, source: str) -> List[Dict]:
        """Derive revenue facts from patterns like "$59.3M total revenue, Electronics 53.4%"."""
        facts = []
        if not text:
            return facts

        money_pattern = re.compile(r'\$([\d,]+(?:\.\d+)?)\s*(M|million|B|billion)?', re.IGNORECASE)
        pct_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*%', re.IGNORECASE)

        for pct_match in pct_pattern.finditer(text):
            window = text[max(0, pct_match.start() - 160):pct_match.end() + 160]
            if not re.search(r'\b(revenue|sales)\b', window, re.IGNORECASE):
                continue

            money_match = money_pattern.search(window)
            if not money_match or not pct_match:
                continue

            raw_money, scale = money_match.groups()
            try:
                total = float(raw_money.replace(',', ''))
                pct = float(pct_match.group(1))
            except ValueError:
                continue

            scale_lower = (scale or "").lower()
            if scale_lower in {"m", "million"}:
                total *= 1_000_000
            elif scale_lower in {"b", "billion"}:
                total *= 1_000_000_000

            if total <= 0 or pct <= 0 or pct > 100:
                continue

            facts.append({
                'value': total * (pct / 100),
                'label': 'derived_percentage_revenue',
                'context': 'revenue',
                'source': source,
            })

        return facts

    def _extract_numbers(self, text: str) -> List[float]:
        """Extract dollar amounts from text."""
        return [fact['value'] for fact in self._extract_number_facts(text, source="text")]

    def _dedupe_number_facts(self, facts: List[Dict], tolerance_pct: float = 0.1) -> List[Dict]:
        """Dedupe near-identical facts within the same source/context."""
        deduped = []
        for fact in facts:
            value = fact.get('value')
            context = fact.get('context', 'value')
            if value is None:
                continue

            duplicate = False
            for existing in deduped:
                if existing.get('context') != context:
                    continue
                existing_value = existing.get('value', 0)
                if existing_value == 0:
                    continue
                pct_diff = abs(existing_value - value) / abs(existing_value) * 100
                if pct_diff <= tolerance_pct:
                    duplicate = True
                    break
            if not duplicate:
                deduped.append(fact)

        return deduped

    def _contexts_compatible(self, left: str, right: str) -> bool:
        if left == right:
            return True

        generic_contexts = {"value", "answer", "extracted", None}
        strict_contexts = {"count", "quantity"}

        # Counts are often supporting metadata in SQL answers
        # (for example, "transactions_analyzed") while RAG reports contain
        # large revenue figures. Never let a generic/extracted document
        # number validate or contradict a structured SQL count.
        if left in strict_contexts or right in strict_contexts:
            return False

        return left in generic_contexts or right in generic_contexts

    def _is_validation_metadata(self, label: str) -> bool:
        """Return True for helper metrics that should not be cross-source facts."""
        label_lower = str(label or "").lower()
        metadata_labels = {
            "transactions_analyzed",
            "row_count",
            "result_count",
            "result_rows",
        }
        return label_lower in metadata_labels
    
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
        
        # Extract numbers from both sources. Prefer structured SQL result rows;
        # SQL answer text is fallback evidence because it can repeat/round values.
        sql_numbers = []
        if sql_result.get('success'):
            # Primary: row-level numeric values (single-row results only —
            # multi-row results contain per-item amounts that don't match RAG totals).
            rows = sql_result.get('results', [])
            if len(rows) == 1:
                for key, value in rows[0].items():
                    if self._is_validation_metadata(key):
                        continue
                    if isinstance(value, (int, float)) and value > 1000:
                        sql_numbers.append({
                            'value': float(value),
                            'label': key,
                            'context': self._infer_number_context(key, fallback=key),
                            'source': 'SQL'
                        })
                    elif hasattr(value, "__float__"):
                        try:
                            num = float(value)
                            if num > 1000:
                                sql_numbers.append({
                                    'value': num,
                                    'label': key,
                                    'context': self._infer_number_context(key, fallback=key),
                                    'source': 'SQL'
                                })
                        except (TypeError, ValueError):
                            pass

            if not sql_numbers:
                sql_numbers.extend(self._extract_number_facts(sql_result.get('answer', ''), source="SQL"))

        rag_number_dicts = self._extract_number_facts(
            rag_result.get('answer', ''),
            source="RAG",
            label="extracted"
        )
        sql_numbers = self._dedupe_number_facts(sql_numbers)
        rag_number_dicts = self._dedupe_number_facts(rag_number_dicts)
        
        # Compare facts one-to-one so one repeated PDF value cannot validate
        # multiple duplicated SQL values.
        candidates = []
        for sql_idx, sql_num in enumerate(sql_numbers):
            sql_val = sql_num['value']
            if sql_val <= 0:
                continue
            for rag_idx, rag_num in enumerate(rag_number_dicts):
                if not self._contexts_compatible(sql_num.get('context'), rag_num.get('context')):
                    continue
                rag_val = rag_num['value']
                pct_diff = abs(sql_val - rag_val) / sql_val * 100
                candidates.append((pct_diff, sql_idx, rag_idx, {
                    'sql_value': sql_val,
                    'rag_value': rag_val,
                    'difference': abs(sql_val - rag_val),
                    'pct_difference': round(pct_diff, 4),
                    'label': sql_num.get('context') or sql_num.get('label', 'value'),
                    'sql_label': sql_num.get('label', 'value'),
                    'rag_label': rag_num.get('label', 'value'),
                }))

        matches = []
        discrepancies = []
        used_sql = set()
        used_rag = set()

        for pct_diff, sql_idx, rag_idx, candidate in sorted(candidates, key=lambda item: item[0]):
            if sql_idx in used_sql or rag_idx in used_rag:
                continue
            used_sql.add(sql_idx)
            used_rag.add(rag_idx)

            if pct_diff < 1.0:
                matches.append(candidate)
            elif pct_diff < 10.0:
                candidate['note'] = 'Close but not exact match'
                matches.append(candidate)
            else:
                discrepancies.append(candidate)
        
        # Calculate confidence
        total_comparisons = len(matches) + len(discrepancies)
        
        if total_comparisons == 0:
            confidence = "MEDIUM"
            confidence_score = 0.5
            confidence_reason = "No overlapping numbers to validate"
        elif len(discrepancies) == 0 and len(matches) > 0:
            confidence = "HIGH"
            confidence_score = 0.95
            fact_label = "fact" if len(matches) == 1 else "facts"
            confidence_reason = f"{len(matches)} validated {fact_label} across sources"
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
            'rag_numbers_found': len(rag_number_dicts)
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
        sql_source_summary = self._describe_sql_source(sql_result)
        
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
- Validated facts: {len(validation['matches'])}
- Discrepancies: {len(validation['discrepancies'])}{discrepancy_note}
"""
        
        # Build fusion prompt
        history_ctx = self._history_context()
        fusion_prompt = f"""You are a business intelligence analyst. Combine information from MULTIPLE data sources into ONE comprehensive answer.
{history_ctx}
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
{f"- 🗄️ SQL Database: {sql_source_summary}" if sql_result and sql_result.get('success') else ""}
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

    def _describe_sql_source(self, sql_result: Optional[Dict]) -> str:
        if not sql_result or not sql_result.get('success'):
            return "unavailable"

        rows = sql_result.get('results') or []
        row_count = sql_result.get('row_count', len(rows))
        if rows:
            first_row = rows[0]
            for key, value in first_row.items():
                key_lower = str(key).lower()
                if key_lower in {"transactions_analyzed", "transaction_count", "transactions_count", "row_count"}:
                    try:
                        analyzed = int(float(value))
                        row_label = "result row" if row_count == 1 else "result rows"
                        return f"{analyzed:,} transactions analyzed · {row_count} {row_label}"
                    except (TypeError, ValueError):
                        break

        row_label = "result row" if row_count == 1 else "result rows"
        return f"{row_count} {row_label} returned"
    
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
    
    def _cache_get(self, question: str) -> Optional[Dict]:
        key = question.strip().lower()
        entry = self._query_cache.get(key)
        if entry and (time.time() - entry[1]) < self._cache_ttl:
            logger.info("Cache hit for query")
            return dict(entry[0], _from_cache=True)
        return None

    def _cache_set(self, question: str, result: Dict) -> None:
        key = question.strip().lower()
        if len(self._query_cache) >= self._cache_max:
            oldest = min(self._query_cache, key=lambda k: self._query_cache[k][1])
            del self._query_cache[oldest]
        self._query_cache[key] = (result, time.time())

    def _finalize_trace(self, trace: TraceSession, result: Dict, cached: bool = False) -> Dict:
        """Attach trace metadata to the response after writing the trace file."""
        final_summary = {
            "source_type": result.get("source_type"),
            "routing_model": result.get("routing_model"),
            "routing_fallback": result.get("routing_fallback"),
            "query_time_s": round(float(result.get("query_time", 0) or 0), 3),
            "from_cache": cached or bool(result.get("_from_cache")),
            "answer_preview": str(result.get("answer") or "")[:500],
            "validation": {
                "confidence": (result.get("validation") or {}).get("confidence"),
                "confidence_reason": (result.get("validation") or {}).get("confidence_reason"),
            }
            if result.get("validation")
            else None,
            "sql": summarize_agent_result(result.get("sql_result")),
            "rag": summarize_agent_result(result.get("rag_result")),
            "web": summarize_agent_result(result.get("web_result")),
        }
        trace_path = trace.finish(final_summary)
        result["trace_id"] = trace.trace_id
        if trace_path:
            result["trace_path"] = str(trace_path)

        if not cached:
            question = trace.data.get("question", "")
            answer_snippet = (result.get("answer") or "")[:200]
            if question and answer_snippet:
                self._history.append({"question": question, "answer": answer_snippet})
                if len(self._history) > self._history_max:
                    self._history.pop(0)

        return result

    def _run_agent_with_trace(
        self,
        trace: Optional[TraceSession],
        key: str,
        runner: Callable[[str], Dict],
        question: str,
    ) -> Dict:
        if trace is None:
            return runner(question)

        with trace.span(f"agent.{key}", {"source": key}) as span:
            result = runner(question)
            span["metadata"]["result"] = summarize_agent_result(result)
            span["status"] = "ok" if result.get("success") else "error"
            if result.get("error"):
                span["error"] = str(result.get("error"))[:500]
            return result

    def _run_agents_parallel(
        self,
        question: str,
        run_sql: bool,
        run_rag: bool,
        run_web: bool,
        progress_cb: Optional[Callable[[str, Dict], None]] = None,
        trace: Optional[TraceSession] = None,
    ) -> tuple:
        """Run requested agents concurrently. Returns (sql_result, rag_result, web_result)."""

        # Map future → source name (clean, no inversion needed)
        future_to_key = {}

        with ThreadPoolExecutor(max_workers=3) as pool:
            if run_sql:
                future_to_key[pool.submit(self._run_agent_with_trace, trace, "sql", self._run_sql_query, question)] = "sql"
            if run_rag:
                future_to_key[pool.submit(self._run_agent_with_trace, trace, "rag", self._run_rag_query, question)] = "rag"
            if run_web:
                future_to_key[pool.submit(self._run_agent_with_trace, trace, "web", self._run_web_query, question)] = "web"

            results = {"sql": None, "rag": None, "web": None}

            # as_completed yields Future objects one by one as they finish
            for fut in as_completed(future_to_key):
                key = future_to_key[fut]        # Future → "sql" / "rag" / "web"
                try:
                    results[key] = fut.result()
                except Exception as e:
                    logger.error(f"Agent '{key}' raised exception: {e}")
                    results[key] = {
                        "success": False,
                        "error": str(e),
                        "source": key
                    }

                if progress_cb:
                    progress_cb(key, results[key])

        return results["sql"], results["rag"], results["web"]

    def query(self, question: str, force_source: Optional[str] = None, progress_cb: Optional[Callable[[str, Dict], None]] = None) -> Dict:
        """
        Main fusion query method. Routes to source(s) and combines results.
        progress_cb(source_name, result_dict) called as each parallel agent finishes.
        """
        trace = get_tracer().start_trace(
            question,
            {
                "force_source": force_source,
                "environment": getattr(settings, "environment", "unknown"),
            },
        )

        # Cache check — skip for forced-source overrides
        if not force_source:
            cached = self._cache_get(question)
            if cached:
                trace.record_event(
                    "cache.hit",
                    {
                        "source_type": cached.get("source_type"),
                        "previous_trace_id": cached.get("trace_id"),
                    },
                )
                cached["query_time"] = 0
                return self._finalize_trace(trace, cached, cached=True)

        start_time = datetime.now()
        self._last_routing_model = None
        self._last_routing_fallback = False
        self._no_data_reason = None

        logger.info(f"\n{'='*70}")
        logger.info(f"🔗 FUSION AGENT: {question}")
        logger.info(f"{'='*70}")

        # Step 1: Classify query source (forced → LLM → keyword fallback)
        with trace.span("routing", {"forced": bool(force_source)}) as span:
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
            span["metadata"].update(
                {
                    "source_type": source_type,
                    "routing_model": self._last_routing_model,
                    "routing_fallback": self._last_routing_fallback,
                    "no_data_reason": self._no_data_reason,
                }
            )
        
        # Step 2: Resolve ambiguous follow-up questions using conversation history
        with trace.span("query.resolution") as span:
            resolved_question = self._resolve_question(question)
            span["metadata"]["original"] = question
            span["metadata"]["resolved"] = resolved_question
            span["metadata"]["changed"] = resolved_question != question
            if resolved_question != question:
                logger.info(f"🔍 Question resolved: '{question}' → '{resolved_question}'")

        # Step 3: Execute based on routing
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
            result = {
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
            return self._finalize_trace(trace, result)

        # ═══════════════════════════════════════════════════════════
        # SINGLE-SOURCE ROUTES
        # ═══════════════════════════════════════════════════════════

        if source_type == "sql_only":
            logger.info("→ Using SQL Agent only")
            sql_result = self._run_agent_with_trace(trace, "sql", self._run_sql_query, resolved_question)

            result = {
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
            return self._finalize_trace(trace, result)

        elif source_type == "rag_only":
            logger.info("→ Using RAG Agent only")
            rag_result = self._run_agent_with_trace(trace, "rag", self._run_rag_query, resolved_question)

            result = {
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
            return self._finalize_trace(trace, result)

        elif source_type == "web_only":
            logger.info("→ Using Web Agent only")
            web_result = self._run_agent_with_trace(trace, "web", self._run_web_query, resolved_question)

            result = {
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
            return self._finalize_trace(trace, result)

        elif source_type == "comparison":
            logger.info("→ Using RAG Agentic Comparison")
            rag_result = self._run_agent_with_trace(trace, "rag", self._run_rag_query, resolved_question)

            result = {
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
            return self._finalize_trace(trace, result)
        
        # ═══════════════════════════════════════════════════════════
        # MULTI-SOURCE ROUTES (sql_rag, sql_web, rag_web, all)
        # ═══════════════════════════════════════════════════════════

        else:
            logger.info(f"→ Using MULTI-SOURCE fusion (parallel): {source_type.upper()}")

            sql_result, rag_result, web_result = self._run_agents_parallel(
                resolved_question,
                run_sql='sql' in source_type,
                run_rag='rag' in source_type,
                run_web='web' in source_type,
                progress_cb=progress_cb,
                trace=trace,
            )
            
            # Cross-validate if we have SQL + RAG
            if sql_result and rag_result and sql_result.get('success') and rag_result.get('success'):
                with trace.span("validation.cross_source") as span:
                    validation = self._cross_validate(sql_result, rag_result)
                    span["metadata"]["confidence"] = validation.get("confidence")
                    span["metadata"]["confidence_reason"] = validation.get("confidence_reason")
                    span["metadata"]["matches"] = len(validation.get("matches", []))
                    span["metadata"]["discrepancies"] = len(validation.get("discrepancies", []))

            # Downgrade source_type label when SQL silently failed
            if sql_result and not sql_result.get('success') and rag_result and rag_result.get('success'):
                logger.warning(f"SQL failed in {source_type} route — answer will be RAG-only. SQL error: {sql_result.get('error', 'unknown')}")
                source_type = "rag_only (sql_failed)"

            # Generate fused answer
            with trace.span("fusion.answer_generation") as span:
                answer = self._generate_fused_answer(
                    question,
                    sql_result,
                    rag_result,
                    web_result,  # ✅ Now properly passed
                    validation
                )
                span["metadata"]["answer_preview"] = str(answer or "")[:500]
            
            query_time = (datetime.now() - start_time).total_seconds()

            logger.info(f"✅ Fusion complete in {query_time:.2f}s")

            result = {
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
            if not force_source:
                self._cache_set(question, result)
            return self._finalize_trace(trace, result)
    
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
