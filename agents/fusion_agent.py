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
from config.data_contexts import DataContext, LIVE_CONTEXT, get_data_context
from config.settings import settings
from observability.tracer import TraceSession, get_tracer, summarize_agent_result
from utils.llm_gateway import get_llm_gateway
from utils.query_normalization import canonical_question_key
from utils.quota_tracker import get_tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

quota_tracker = get_tracker()


class FusionAgent:
    """
    Orchestrates SQL Agent, RAG Agent, and Web Agent for cross-source intelligence
    """

    WEB_CATEGORIES = ("electronics", "clothing", "home", "food", "sports")
    WEB_COMPETITOR_CATEGORIES = {
        "goal zero": "electronics",
        "newegg": "electronics",
        "ikea": "home",
        "taylor stitch": "clothing",
        "chubbies": "clothing",
        "finisterre": "clothing",
        "swanson": "food",
        "nativepath": "food",
        "campmor": "sports",
    }
    
    def __init__(self, data_context: DataContext = LIVE_CONTEXT):
        logger.info("Initializing Fusion Agent...")
        self.data_context = data_context
        
        # Initialize sub-agents
        self.sql_agent = SQLAgent(mode="development", data_context=data_context)
        self.rag_agent = get_rag_agent(data_context.key)
        self.web_agent = get_web_agent()  # ✅ NEW: Initialize Web Agent
        
        # LLM clients (reuse from RAG agent)
        self.gemini_flash = self.rag_agent.gemini_flash
        self.groq_client = self.rag_agent.groq_client
        self.llm_gateway = get_llm_gateway()
        
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

        logger.info("✅ Fusion Agent initialized for %s!", data_context.label)

    def _routing_context_prompt(self) -> str:
        """Describe sources available to the agent."""
        return """**SQL** - 100,000 Supabase sales transactions for 2024 (Q1-Q4). Use for
revenue, counts, rankings, trends, growth rates, and quarterly breakdowns.

**RAG** - 25 PDF documents: Q1-Q4 2024 financial reports, operations/compliance policies,
expansion plans, budget, digital wallet initiative, and vendor contracts. Use alongside SQL
for quarterly or annual revenue validation, and alone for policy or strategy.

**Web** - live competitor pricing from supported retail sources. Use only for competitor or
market pricing; do not use it for our transaction facts.

Cross-validation rules:
- Use sql=true AND rag=true for quarterly/annual totals and explicit validation requests.
- Use sql=true and rag=false for rankings, non-quarterly breakdowns, monthly trends, or counts.
- Use rag=true alone for policy or strategy; use web=true alone for competitor pricing."""
    
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

    @staticmethod
    def _rule_based_web_route(question: str) -> Optional[str]:
        """Route clear live-pricing requests to Web without an LLM routing call."""
        from config.data_inventory import can_web_answer

        q = str(question or "").lower()
        if not can_web_answer(question).get("can_answer"):
            return None

        own_data_terms = ("our ", "our own", "sales", "revenue", "transaction", "database")
        if any(term in q for term in own_data_terms):
            return None

        pricing_terms = (
            "price",
            "pricing",
            "discount",
            "original price",
            "cheapest",
            "most expensive",
            "lowest price",
            "highest price",
            "product",
        )
        return "web_only" if any(term in q for term in pricing_terms) else None

    def _history_context(self, max_turns: int = 3) -> str:
        if not self._history:
            return ""
        turns = "\n".join(
            f"Q: {turn['question']}\nA: {turn['answer']}"
            for turn in self._history[-max_turns:]
        )
        return f"\n## Conversation History\n{turns}\n"

    def _gateway_models(self) -> List[Dict]:
        """Return configured Fusion models in existing preference order."""
        models = []
        if getattr(self, "gemini_flash", None) is not None:
            models.append({
                "name": settings.gemini_flash_model,
                "type": "gemini",
                "description": "Gemini Flash",
            })
        if getattr(self, "groq_client", None) is not None:
            models.append({
                "name": settings.groq_model,
                "type": "groq",
                "description": "Groq",
            })
        return models

    @staticmethod
    def _valid_routing_response(content: str) -> bool:
        """Require router output to contain a usable source-selection object."""
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return False
        try:
            routing = json.loads(match.group())
        except json.JSONDecodeError:
            return False
        return all(key in routing for key in ("sql", "rag", "web"))

    def _needs_history_resolution(self, question: str) -> bool:
        """Return True only for questions that are likely contextual follow-ups."""
        q = str(question or "").strip().lower()
        if not q:
            return False

        tokens = re.findall(r"[a-z0-9]+", q)
        if not tokens:
            return False

        followup_starts = (
            "what about",
            "how about",
            "and ",
            "also ",
            "same for",
            "compare that",
            "compare it",
        )
        if q.startswith(followup_starts):
            return True

        contextual_terms = {
            "it",
            "its",
            "they",
            "them",
            "their",
            "this",
            "that",
            "these",
            "those",
            "previous",
            "above",
            "same",
        }
        if any(token in contextual_terms for token in tokens):
            return True

        # Very short fragments like "refunds?" may depend on the prior topic.
        if len(tokens) <= 3 and not any(token in {"policy", "revenue", "sales", "returns", "refund"} for token in tokens):
            return True

        return False

    def _resolve_question(self, question: str) -> str:
        """Expand ambiguous follow-up using conversation history. Returns original if no history or LLM fails."""
        if not self._history:
            return question
        if not self._needs_history_resolution(question):
            return question

        history_ctx = self._history_context(max_turns=3)
        prompt = f"""Given this conversation history and a follow-up question, rewrite the follow-up as a complete standalone question.
If the follow-up is already self-contained and clear, return it unchanged.
Output ONLY the rewritten question, no explanation, no quotes.

{history_ctx}
Follow-up: {question}
Standalone question:"""

        result = self.llm_gateway.invoke_with_fallback(
            prompt=prompt,
            models=self._gateway_models(),
            tracker=quota_tracker,
            task="fusion.resolve_question",
            temperature=0.1,
            metadata={"agent": "fusion"},
            response_validator=lambda content: bool(content.strip()),
        )
        if result.get("success"):
            resolved = str(result.get("response") or "").strip().strip("\"'")
            if resolved:
                return resolved

        return question

    def _classify_query_source_llm(self, question: str) -> Optional[str]:
        """
        LLM-based dynamic routing — understands meaning, not just keywords.
        Falls back to None on failure so caller can use keyword routing instead.
        """
        prompt = f"""You are a data routing agent for NexusIQ AI. Decide which sources answer the user question.

## Sources And Rules

{self._routing_context_prompt()}

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

        models = self._gateway_models()
        primary_client_name = models[0]["description"] if models else None
        if models and models[0]["description"] == "Gemini Flash":
            self._gemini_routing_calls.append(time.time())

        result = self.llm_gateway.invoke_with_fallback(
            prompt=prompt,
            models=models,
            tracker=quota_tracker,
            task="fusion.route",
            temperature=0.1,
            metadata={"agent": "fusion"},
            response_validator=self._valid_routing_response,
        )
        if result.get("success"):
            client_name = result.get("model_used")
            content = str(result.get("response") or "")
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
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
                    ordered = sorted(sources, key=lambda s: ["sql", "rag", "web"].index(s))
                    route = "_".join(ordered)
                else:
                    route = "all"

            quarter_terms = ["quarter", "quarterly", "q1", "q2", "q3", "q4"]
            if route == "rag_only" and any(t in question.lower() for t in quarter_terms):
                logger.info("  Safety net: quarterly question upgraded rag_only → sql_rag")
                route = "sql_rag"

            self._last_routing_model = routing.get("_routing_model", client_name)
            self._last_routing_fallback = routing.get("_routing_fallback", False)

            return route

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
                'error': result.get('error', ''),
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
    
    @classmethod
    def _infer_web_category(cls, question: str) -> Optional[str]:
        """Resolve category from a known competitor or explicit category phrase."""
        q = str(question or "").lower()
        for competitor, category in cls.WEB_COMPETITOR_CATEGORIES.items():
            if competitor in q:
                return category
        for category in cls.WEB_CATEGORIES:
            if category in q:
                return category
        return None

    @classmethod
    def _should_compare_all_web_categories(cls, question: str) -> bool:
        """Return True when the user asks for broad competitor pricing coverage."""
        q = str(question or "").lower()
        has_pricing_intent = (
            "competitor pricing" in q
            or ("competitor" in q and any(term in q for term in ("price", "pricing", "prices")))
            or ("market" in q and any(term in q for term in ("price", "pricing", "prices")))
        )
        broad_terms = (
            "all categories",
            "all product",
            "across categories",
            "across product",
            "company-wide",
            "overall",
            "complete",
            "comprehensive",
            "full analysis",
        )
        return has_pricing_intent and any(term in q for term in broad_terms)

    @classmethod
    def _infer_web_competitor(cls, question: str) -> Optional[str]:
        """Return the canonical competitor named in the question, if configured."""
        q = str(question or "").lower()
        for competitor in cls.WEB_COMPETITOR_CATEGORIES:
            if competitor in q:
                return competitor.title()
        return None

    @staticmethod
    def _format_web_price_range(products: list) -> str:
        prices = []
        for product in products or []:
            raw_price = str(product.get("price", "")).replace("$", "").replace(",", "").strip()
            try:
                prices.append(float(raw_price))
            except ValueError:
                continue
        if not prices:
            return "price range unavailable"
        return f"${min(prices):,.2f} - ${max(prices):,.2f}"

    def _run_all_web_categories_query(self, question: str) -> Dict:
        """Collect competitor pricing across every supported category without guessing one."""
        category_payloads = {}
        all_competitors = []
        answer_lines = [
            "Compared competitor pricing across all supported product categories:",
        ]

        for category in self.WEB_CATEGORIES:
            if hasattr(self.web_agent, "scrape_competitor_pricing"):
                pricing_data = self.web_agent.scrape_competitor_pricing(category)
                category_answer = ""
            else:
                result = self.web_agent.query(question, category=category, competitor=None)
                pricing_data = result.get("raw_data", {})
                category_answer = result.get("answer", "")

            competitors = pricing_data.get("competitors", []) or []
            category_payloads[category] = pricing_data
            all_competitors.extend(competitors)

            if competitors:
                summaries = []
                for competitor_data in competitors:
                    products = competitor_data.get("products", []) or []
                    summaries.append(
                        f"{competitor_data.get('competitor', 'Unknown')}: "
                        f"{self._format_web_price_range(products)}"
                    )
                answer_lines.append(f"- {category.title()}: " + "; ".join(summaries))
            elif category_answer:
                answer_lines.append(f"- {category.title()}: {category_answer}")
            else:
                answer_lines.append(f"- {category.title()}: no live competitor pricing data available")

        answer_lines.append(
            "If you want a deeper Web-only comparison, ask for one category such as electronics, home, clothing, food, or sports."
        )

        return {
            "answer": "\n".join(answer_lines),
            "answer_mode": "deterministic_all_categories",
            "model_used": "Deterministic all-category aggregation",
            "raw_data": {
                "category": "all",
                "categories": category_payloads,
                "competitors": all_competitors,
            },
            "category": "all",
        }

    def _run_web_query(self, question: str, selected_category: Optional[str] = None) -> Dict:
        """✅ NEW: Run Web Agent and capture results"""
        
        logger.info("🌐 Running Web Agent...")
        start = time.time()
        
        try:
            category = self._infer_web_category(question)
            if category is None and selected_category in self.WEB_CATEGORIES:
                category = selected_category
            competitor = self._infer_web_competitor(question)
            if category is None and competitor is None and self._should_compare_all_web_categories(question):
                result = self._run_all_web_categories_query(question)
            else:
                result = self.web_agent.query(question, category=category, competitor=competitor)
            elapsed = time.time() - start
            
            has_answer = bool(result.get('answer'))
            competitors = result.get('raw_data', {}).get('competitors', [])
            has_data = bool(competitors)
            sample_only = has_data and all(
                competitor_data.get('is_mock')
                or competitor_data.get('data_status') == 'sample'
                for competitor_data in competitors
            )
            hard_error = bool(result.get('error'))   # only set on total failure
            return {
                'success': has_answer and has_data and not sample_only and not hard_error,
                'answer': result.get('answer', 'No web data available'),
                'raw_data': result.get('raw_data', {}),
                'category': result.get('category'),
                'time': round(elapsed, 2),
                'source': 'Web Scraping',
                'answer_mode': result.get('answer_mode'),
                'model_used': result.get('model_used', ''),
                'sample_only': sample_only,
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
        """Extract monetary/large-number facts AND plain count facts with lightweight context."""
        facts = []
        if not text:
            return facts

        # Match patterns like $45.2M, $15,400,000, $38.7 million
        dollar_pattern = re.compile(
            r'\$?([\d,]+(?:\.\d+)?)\s*(M|million|B|billion)?',
            re.IGNORECASE
        )

        for match in dollar_pattern.finditer(text):
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

        # Also extract plain counts near count-context words (returns, transactions,
        # orders, refunds, units, items, customers, records).
        # Strip markdown bold/italic first so "**331** returns" → "331 returns".
        # Threshold >= 10 to avoid noise from small ordinals.
        count_text = re.sub(r'\*+', ' ', text)  # strip markdown stars
        count_pattern = re.compile(
            r'(?<![\d.])([\d,]+)\s*(?=(?:returns?|refunds?|transactions?|orders?|units?'
            r'|items?|customers?|records?|products?|accounts?|entries|rows))',
            re.IGNORECASE
        )
        for match in count_pattern.finditer(count_text):
            cleaned = match.group(1).replace(',', '').strip()
            try:
                value = float(cleaned)
            except ValueError:
                continue
            if value < 10:
                continue
            window = text[max(0, match.start() - 60):match.end() + 60]
            facts.append({
                'value': value,
                'label': 'count',
                'context': self._infer_number_context(window, fallback="count"),
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
            rows = sql_result.get('results', [])
            # COUNT-type columns (return_count, quantity, num_*, total_*)
            # are valid for cross-validation regardless of row count.
            COUNT_KEYS = re.compile(
                r'count|quantity|num_|total_|n_',
                re.IGNORECASE
            )
            if len(rows) == 1:
                # Single-row: extract all numeric columns > threshold
                for key, value in rows[0].items():
                    if self._is_validation_metadata(key):
                        continue
                    try:
                        num = float(value)
                    except (TypeError, ValueError):
                        continue
                    threshold = 10 if COUNT_KEYS.search(key) else 1000
                    if num > threshold:
                        sql_numbers.append({
                            'value': num,
                            'label': key,
                            'context': self._infer_number_context(key, fallback=key),
                            'source': 'SQL'
                        })
            else:
                # Multi-row: extract count/quantity columns from ALL rows
                for row in rows:
                    for key, value in row.items():
                        if not COUNT_KEYS.search(key):
                            continue
                        if self._is_validation_metadata(key):
                            continue
                        try:
                            num = float(value)
                        except (TypeError, ValueError):
                            continue
                        if num < 10:
                            continue
                        sql_numbers.append({
                            'value': num,
                            'label': key,
                            'context': self._infer_number_context(key, fallback=key),
                            'source': 'SQL'
                        })

            if not rows and not sql_numbers:
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

        validated_answer = self._format_validated_sql_rag_answer(
            sql_result=sql_result,
            rag_result=rag_result,
            validation=validation,
            web_result=web_result,
        )
        if validated_answer:
            self._last_answer_generation = {
                "mode": "deterministic_validated",
                "reason": "high_confidence_cross_source_validation",
                "model_used": None,
            }
            return validated_answer

        degraded_answer = self._format_degraded_multi_source_answer(
            sql_result=sql_result,
            rag_result=rag_result,
            web_result=web_result,
        )
        if degraded_answer:
            self._last_answer_generation = {
                "mode": "deterministic_degraded",
                "reason": "only_one_requested_source_succeeded",
                "model_used": None,
            }
            return degraded_answer
        
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
        fusion_prompt = f"""You are a business intelligence analyst. Combine data from MULTIPLE sources into ONE clear, structured answer.
{history_ctx}
QUESTION: {question}

{sources_text}

{validation_text}

CONTENT RULES:
1. SQL = exact transaction records. Use for precise numbers.
2. PDFs = reported/aggregated figures. Use for context, trends, policy.
3. Web = live market/competitor data. Use for benchmarking.
4. If sources have different numbers for the SAME thing, explicitly state both and explain why they differ.
   Common reasons: (a) different time periods — SQL may be a specific day/date while PDF covers a full week or quarter;
   (b) PDF figures may be projected/reported while SQL reflects actual transaction totals;
   (c) different scopes — SQL is transaction-level, PDFs may include offline channels.
   ALWAYS specify the time scope of each figure when they differ.
5. When validated across sources with matching numbers, state confidence clearly.

FORMATTING RULES (users must find this easy to read):
• Start with a direct 1-2 sentence answer.
• Use **bold** for key numbers and conclusions.
• Use bullet points for supporting details — no walls of text.
• If answer has multiple parts (e.g., SQL figure + PDF figure + explanation), use short labeled sections.
• Put source references at the END in a clean block.

FORMAT:
📊 **Answer:** [Direct 1-2 sentence answer]

**Key Facts:**
- [Bullet: SQL figure with its exact time scope]
- [Bullet: PDF figure with its exact time scope/context — if different from SQL, explain why]
- [Additional context bullets as needed]

**Sources Used:**
{f"- 🗄️ SQL Database: {sql_source_summary}" if sql_result and sql_result.get('success') else ""}
{f"- 📄 Documents: {rag_result.get('chunks_retrieved', 0)} document excerpts" if rag_result and rag_result.get('success') else ""}
{f"- 🌐 Web Scraping: {web_result.get('category', 'General')} data" if web_result and web_result.get('success') else ""}

{f"**Confidence:** {validation['confidence']} — {validation['confidence_reason']}" if validation else ""}

ANSWER:"""

        result = self.llm_gateway.invoke_with_fallback(
            prompt=fusion_prompt,
            models=self._gateway_models(),
            tracker=quota_tracker,
            task="fusion.answer",
            temperature=0.1,
            metadata={"agent": "fusion"},
            response_validator=lambda content: bool(content.strip()),
        )
        if result.get("success"):
            logger.info("✅ Fused answer generated with %s", result.get("model_used"))
            self._last_answer_generation = {
                "mode": "llm_synthesis",
                "reason": "multiple_sources_require_reconciliation",
                "model_used": result.get("model_used"),
            }
            return result["response"]
        
        # Fallback: Simple combination without LLM
        logger.warning("All LLM models failed, using simple fusion")
        self._last_answer_generation = {
            "mode": "deterministic_fallback",
            "reason": "fusion_llm_unavailable",
            "model_used": None,
        }
        return self._simple_fusion(sql_result, rag_result, web_result, validation)

    def _format_validated_sql_rag_answer(
        self,
        sql_result: Optional[Dict],
        rag_result: Optional[Dict],
        validation: Optional[Dict],
        web_result: Optional[Dict] = None,
    ) -> Optional[str]:
        """Return a stable public-demo answer for high-confidence SQL/RAG matches."""
        if not (
            validation
            and validation.get("confidence") == "HIGH"
            and validation.get("validated")
            and validation.get("matches")
            and sql_result
            and sql_result.get("success")
            and rag_result
            and rag_result.get("success")
        ):
            return None

        # If web data is involved, keep the LLM synthesis path because market context
        # needs more narrative judgment than a numeric validation answer.
        if web_result and web_result.get("success"):
            return None

        match = validation["matches"][0]
        sql_value = match.get("sql_value")
        rag_value = match.get("rag_value")
        pct_difference = match.get("pct_difference", 0)
        label = self._humanize_fact_label(match.get("label") or match.get("sql_label") or "value")
        rag_descriptor = (
            "PDF-derived value"
            if match.get("rag_label") == "derived_percentage_revenue"
            else "PDF/document value"
        )
        transactions = self._extract_supporting_transaction_count(sql_result)
        transaction_text = (
            f" across **{transactions:,} transactions**"
            if transactions
            else ""
        )
        chunks = rag_result.get("chunks_retrieved", 0)

        return (
            f"📊 **Answer:** {label} is validated across SQL and PDF sources. "
            f"The SQL database reports **{self._format_currency(sql_value)}**{transaction_text}, "
            f"while the {rag_descriptor} is **{self._format_currency(rag_value)}**. "
            f"The difference is **{pct_difference:.2f}%**, which is within the validation threshold.\n\n"
            "**Details:**\n"
            f"- SQL is treated as the source of exact transaction totals: **{self._format_currency(sql_value)}**.\n"
            f"- Documents provide the comparison point: **{self._format_currency(rag_value)}**.\n"
            f"- Cross-source validation found **{len(validation.get('matches', []))} matching fact** and "
            f"**{len(validation.get('discrepancies', []))} discrepancies**.\n\n"
            "**Sources Used:**\n"
            f"- 🗄️ SQL Database: {self._describe_sql_source(sql_result)}\n"
            f"- 📄 Documents: {chunks} document excerpts\n\n"
            f"**Confidence:** {validation['confidence']} - {validation['confidence_reason']}"
        )

    def _format_currency(self, value) -> str:
        try:
            return f"${float(value):,.2f}"
        except (TypeError, ValueError):
            return str(value)

    def _humanize_fact_label(self, label: str) -> str:
        label = str(label or "value").replace("_", " ").strip()
        if not label:
            return "The validated value"
        return label[:1].upper() + label[1:]

    def _extract_supporting_transaction_count(self, sql_result: Dict) -> Optional[int]:
        for row in sql_result.get("results") or []:
            if not isinstance(row, dict):
                continue
            for key, value in row.items():
                key_lower = str(key).lower()
                if "transaction" in key_lower and any(term in key_lower for term in ["count", "analyzed"]):
                    try:
                        return int(value)
                    except (TypeError, ValueError):
                        return None
        return None

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

    def _format_degraded_multi_source_answer(
        self,
        sql_result: Optional[Dict],
        rag_result: Optional[Dict],
        web_result: Optional[Dict],
    ) -> Optional[str]:
        """Return one complete surviving source answer without an unnecessary LLM call."""
        sources = (
            ("SQL Database", sql_result),
            ("Documents", rag_result),
            ("Web Data", web_result),
        )
        attempted = [(label, result) for label, result in sources if result is not None]
        successful = [
            (label, result)
            for label, result in attempted
            if result.get("success") and str(result.get("answer") or "").strip()
        ]
        unavailable = [label for label, result in attempted if not result.get("success")]

        if len(attempted) < 2 or len(successful) != 1 or not unavailable:
            return None

        source_label, source_result = successful[0]
        unavailable_text = ", ".join(unavailable)
        return (
            f"{source_result['answer']}\n\n"
            f"**Availability note:** {unavailable_text} could not provide usable evidence for this request. "
            f"The answer above uses **{source_label}** only; cross-source synthesis and validation were not performed."
        )

    @staticmethod
    def _degraded_source_type(
        source_type: str,
        sql_result: Optional[Dict],
        rag_result: Optional[Dict],
        web_result: Optional[Dict],
    ) -> str:
        """Label a multi-source attempt accurately when only one source survives."""
        attempted = [
            (name, result)
            for name, result in (("sql", sql_result), ("rag", rag_result), ("web", web_result))
            if result is not None
        ]
        successful = [name for name, result in attempted if result.get("success")]
        failed = [name for name, result in attempted if not result.get("success")]
        if len(attempted) >= 2 and len(successful) == 1 and failed:
            return f"{successful[0]}_only ({'_'.join(failed)}_failed)"
        return source_type
    
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
        key = canonical_question_key(question)
        entry = self._query_cache.get(key)
        if entry and (time.time() - entry[1]) < self._cache_ttl:
            logger.info("Cache hit for query")
            return dict(entry[0], _from_cache=True)
        return None

    def _should_cache_result(self, source_type: str, result: Dict) -> tuple[bool, str]:
        """Admit only verified, non-degraded answers into the final-answer cache."""
        if not result.get("answer"):
            return False, "empty_answer"

        normalized_source = str(source_type or result.get("source_type") or "").lower()
        if normalized_source == "no_data":
            return False, "no_data_can_go_stale"
        if "sql_failed" in normalized_source:
            return False, "degraded_sql_failed"

        sql_result = result.get("sql_result")
        rag_result = result.get("rag_result")
        web_result = result.get("web_result")
        validation = result.get("validation") or {}

        if sql_result is not None and not sql_result.get("success"):
            return False, "sql_error"
        if rag_result is not None and not rag_result.get("success"):
            return False, "rag_error"
        if web_result is not None and not web_result.get("success"):
            return False, "web_error"

        if "sql" in normalized_source and "rag" in normalized_source:
            if not validation.get("validated"):
                return False, "validation_not_verified"
            if validation.get("confidence") != "HIGH":
                return False, "validation_not_high_confidence"
            if validation.get("discrepancies"):
                return False, "validation_has_discrepancies"

        if normalized_source == "sql_only":
            if not sql_result or not sql_result.get("success"):
                return False, "sql_not_successful"
            return True, "sql_success"

        if normalized_source in {"rag_only", "comparison"}:
            if not rag_result or not rag_result.get("success"):
                return False, "rag_not_successful"
            if rag_result.get("chunks_retrieved", 0) <= 0 and not rag_result.get("sources"):
                return False, "rag_has_no_evidence"
            return True, "rag_has_evidence"

        if normalized_source == "web_only":
            if not web_result or not web_result.get("success"):
                return False, "web_not_successful"
            return True, "web_success"

        return True, "passed_quality_gate"

    def _cache_set(self, question: str, result: Dict) -> None:
        key = canonical_question_key(question)
        if len(self._query_cache) >= self._cache_max:
            oldest = min(self._query_cache, key=lambda k: self._query_cache[k][1])
            del self._query_cache[oldest]
        self._query_cache[key] = (result, time.time())

    def _collect_answer_models(self, result: Dict) -> str:
        """Return the model(s) that actually generated answer content."""
        models = []
        for label, key in (("SQL", "sql_result"), ("RAG", "rag_result"), ("Web", "web_result")):
            agent_result = result.get(key) or {}
            model = agent_result.get("model_used")
            if model and model != "none":
                models.append(f"{label}: {model}")
        if models:
            return "; ".join(models)
        if result.get("source_type") == "no_data":
            return "System response"
        return "n/a"

    def _finalize_trace(self, trace: TraceSession, result: Dict, cached: bool = False) -> Dict:
        """Attach trace metadata to the response after writing the trace file."""
        result["answer_models"] = result.get("answer_models") or self._collect_answer_models(result)
        final_summary = {
            "source_type": result.get("source_type"),
            "routing_model": result.get("routing_model"),
            "answer_models": result.get("answer_models"),
            "answer_generation_mode": result.get("answer_generation_mode"),
            "answer_generation_reason": result.get("answer_generation_reason"),
            "fusion_model_used": result.get("fusion_model_used"),
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

    def query(
        self,
        question: str,
        force_source: Optional[str] = None,
        progress_cb: Optional[Callable[[str, Dict], None]] = None,
        bypass_cache: bool = False,
        web_category: Optional[str] = None,
    ) -> Dict:
        """
        Main fusion query method. Routes to source(s) and combines results.
        progress_cb(source_name, result_dict) called as each parallel agent finishes.
        """
        use_langgraph = os.getenv("NEXUSIQ_USE_LANGGRAPH", "false").strip().lower() in {"1", "true", "yes"}
        if use_langgraph:
            from agents.fusion_graph import FusionGraph

            if not hasattr(self, "_fusion_graph"):
                self._fusion_graph = FusionGraph(self)
            return self._fusion_graph.query(
                question,
                force_source=force_source,
                progress_cb=progress_cb,
                bypass_cache=bypass_cache,
                web_category=web_category,
            )

        trace = get_tracer().start_trace(
            question,
            {
                "force_source": force_source,
                "bypass_cache": bypass_cache,
                "environment": getattr(settings, "environment", "unknown"),
            },
        )

        # Cache check — skip for forced-source overrides
        if bypass_cache:
            trace.record_event("cache.bypass", {"reason": "user_requested_fresh_answer"})
        if not force_source and not bypass_cache:
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
                source_type = self._rule_based_web_route(question)
                if source_type:
                    if not self._last_routing_model:
                        self._last_routing_model = "Rules-based Web routing"
                        logger.info(f"📋 Query routing: {source_type.upper()} (explicit web pricing rule)")
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
            web_runner = lambda query: self._run_web_query(query, selected_category=web_category)
            web_result = self._run_agent_with_trace(trace, "web", web_runner, resolved_question)

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
            run_all_sources = source_type == "all"

            sql_result, rag_result, web_result = self._run_agents_parallel(
                resolved_question,
                run_sql=run_all_sources or 'sql' in source_type,
                run_rag=run_all_sources or 'rag' in source_type,
                run_web=(run_all_sources or 'web' in source_type) and settings.ENABLE_WEB_AGENT,
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

            degraded_source_type = self._degraded_source_type(
                source_type, sql_result, rag_result, web_result
            )
            if degraded_source_type != source_type:
                logger.warning(
                    "Only one source succeeded for %s route; reporting degraded route as %s",
                    source_type,
                    degraded_source_type,
                )
                source_type = degraded_source_type

            # Generate fused answer
            with trace.span("fusion.answer_generation") as span:
                self._last_answer_generation = {}
                answer = self._generate_fused_answer(
                    question,
                    sql_result,
                    rag_result,
                    web_result,  # ✅ Now properly passed
                    validation
                )
                span["metadata"]["answer_preview"] = str(answer or "")[:500]
                span["metadata"].update(self._last_answer_generation)
            
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
                'answer_generation_mode': self._last_answer_generation.get("mode"),
                'answer_generation_reason': self._last_answer_generation.get("reason"),
                'fusion_model_used': self._last_answer_generation.get("model_used"),
                'query_time': query_time
            }
            if not force_source:
                should_cache, cache_reason = self._should_cache_result(source_type, result)
                trace.record_event(
                    "cache.admission",
                    {
                        "accepted": should_cache,
                        "reason": cache_reason,
                        "source_type": source_type,
                    },
                )
                if should_cache:
                    self._cache_set(question, result)
            return self._finalize_trace(trace, result)
    
    def close(self):
        """Clean up resources"""
        self.sql_agent.close()
        self.web_agent.close()  # ✅ NEW: Close Web Agent
        logger.info("🔌 Fusion Agent closed")


# Singleton agents remain separated by context so cached answers cannot cross evidence boundaries.
_fusion_instances = {}


def get_fusion_agent(data_context_key: str = "live") -> FusionAgent:
    """Get a Fusion Agent scoped to a live or pilot data context."""
    if data_context_key not in _fusion_instances:
        _fusion_instances[data_context_key] = FusionAgent(get_data_context(data_context_key))
    return _fusion_instances[data_context_key]


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
