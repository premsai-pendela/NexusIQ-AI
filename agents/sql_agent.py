"""
NexusIQ AI — SQL Query Agent (Production Edition)
Features:
  - Intelligent model fallback with quota tracking
  - Circuit breaker pattern to skip dead models
  - Returns complete execution history
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
try:
    import sqlglot
    from sqlglot import errors as sqlglot_errors
    from sqlglot import exp
except Exception:  # pragma: no cover - fallback path when optional parser is unavailable
    sqlglot = None
    sqlglot_errors = None
    exp = None
from config.data_contexts import DataContext, LIVE_CONTEXT
from config.settings import settings
from context.business_context import build_context_block, business_context_enabled
from utils.llm_gateway import get_llm_gateway
from utils.quota_tracker import get_tracker
from utils.validators import validate_question
from typing import Dict, Any, List, Optional
import logging
import os
import time
import re
from functools import wraps

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  RATE LIMITING DECORATOR
# ═══════════════════════════════════════════════════════════

def rate_limit(calls_per_minute=25):
    """Decorator to limit API calls per minute"""
    min_interval = 60.0 / calls_per_minute
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                logger.info(f"⏳ Rate limiting: waiting {left_to_wait:.1f}s")
                time.sleep(left_to_wait)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════
#  SQL AGENT CLASS
# ═══════════════════════════════════════════════════════════

class SQLAgent:
    """
    AI Agent that converts natural language to SQL queries
    with intelligent multi-model fallback and quota tracking.
    """
    
    # Model configurations
    MODELS = {
        "complex": [
            # Complex queries need SMARTER models first
            # Joins, comparisons, trends, multi-step analysis
            {
                "name": "publishers/google/models/gemini-2.5-flash",
                "type": "vertex",
                "description": "Gemini 2.5 Flash via Vertex AI (GCP)",
                "quota": "GCP billing",
                "priority_reason": "Enterprise-grade via Google Cloud Vertex AI"
            },
            {
                "name": "gemini-2.5-flash",
                "type": "gemini",
                "description": "Gemini 2.5 Flash (Smart + Fast)",
                "quota": "1,500/day",
                "priority_reason": "Best for complex SQL generation"
            },
            {
                "name": "llama-3.3-70b-versatile",
                "type": "groq",
                "description": "Groq Llama 3.3 70B (Fallback)",
                "quota": "14,400/day",
                "priority_reason": "Good SQL capability, very fast"
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
            # Single table, basic aggregations, lookups
            {
                "name": "llama-3.3-70b-versatile",
                "type": "groq",
                "description": "Groq Llama 3.3 70B (Fastest)",
                "quota": "14,400/day",
                "priority_reason": "Fastest response for simple queries"
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
    
    def __init__(self, mode: str = "development", data_context: DataContext = LIVE_CONTEXT):
        """Initialize SQL Agent"""
        
        self.mode = mode
        self.data_context = data_context
        self.tracker = get_tracker()
        self.llm_gateway = get_llm_gateway()
        
        # Database connection
        self.engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.session.rollback()  # Clear any leftover transactions
        
        # Schema context
        self.schema_context = self._get_schema_info()
        
        logger.info(f"✅ SQL Agent initialized in {mode.upper()} mode")
    
    
    def _get_schema_info(self) -> str:
        """Dynamically discover schema from database, falling back to hardcoded string."""
        try:
            discovery_sql = """
            SELECT
                c.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable
            FROM information_schema.columns c
            WHERE c.table_schema = 'public'
            ORDER BY c.table_name, c.ordinal_position;
            """
            result = self.session.execute(text(discovery_sql))
            rows = [dict(zip(result.keys(), row)) for row in result.fetchall()]
            if not rows:
                return self._get_schema_fallback()

            schema_lines = ["I am using PostgreSQL 15. Here are the available tables and columns:\n"]
            current_table = None
            for row in rows:
                table = row.get("table_name", "")
                col = row.get("column_name", "")
                dtype = row.get("data_type", "")
                nullable = row.get("is_nullable", "YES")
                if table != current_table:
                    current_table = table
                    schema_lines.append(f"\nTABLE: {table}")
                nullable_str = "" if nullable == "YES" else " NOT NULL"
                schema_lines.append(f"  • {col} ({dtype}{nullable_str})")

            schema_lines.append(
                "\n⚠️ CRITICAL: ALL data is from year 2024 ONLY. "
                "Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec. "
                "Never use CURRENT_DATE."
            )
            return "\n".join(schema_lines)

        except Exception as e:
            print(f"Schema discovery failed: {e}, using fallback")
            return self._get_schema_fallback()

    def _get_schema_fallback(self) -> str:
        """Hardcoded schema — used when INFORMATION_SCHEMA discovery fails."""
        return """
    I am using PostgreSQL 15. Here is my database schema:

    TABLE: sales_transactions (100,000 rows in configured Supabase PostgreSQL source)
    • id (INTEGER, PRIMARY KEY)
    • transaction_date (TIMESTAMP)
    • region (VARCHAR): 'East', 'West', 'North', 'South', 'Central'
    • store_id (VARCHAR): e.g., 'E001', 'W015'
    • product_category (VARCHAR): 'Electronics', 'Clothing', 'Food', 'Home', 'Sports'
    • product_name (VARCHAR)
    • quantity (INTEGER)
    • unit_price (NUMERIC)
    • total_amount (NUMERIC)
    • customer_id (VARCHAR)
    • payment_method (VARCHAR): 'Credit Card', 'Debit Card', 'Cash', 'Digital Wallet'

    ⚠️ CRITICAL DATE INFORMATION:
    • ALL data is from year 2024 ONLY (January 1, 2024 to December 31, 2024)
    • There is NO data for 2025 or 2026
    • When user mentions Q4, Q3, etc. - ALWAYS assume 2024

    QUARTER DATE RANGES (USE THESE EXACT DATES):
    • Q1 2024: transaction_date >= '2024-01-01' AND transaction_date < '2024-04-01'
    • Q2 2024: transaction_date >= '2024-04-01' AND transaction_date < '2024-07-01'
    • Q3 2024: transaction_date >= '2024-07-01' AND transaction_date < '2024-10-01'
    • Q4 2024: transaction_date >= '2024-10-01' AND transaction_date < '2025-01-01'

    EXAMPLES:
    • "Q4 revenue" → WHERE transaction_date >= '2024-10-01' AND transaction_date < '2025-01-01'
    • "Q4 Electronics" → WHERE product_category = 'Electronics' AND transaction_date >= '2024-10-01' AND transaction_date < '2025-01-01'
    • "Compare Q3 and Q4" → Use the date ranges above for each quarter

    DO NOT USE:
    • CURRENT_DATE (data is historical from 2024)
    • EXTRACT(QUARTER FROM ...) without explicit year filter

    TABLE: customers (14,979 rows — one per unique customer in sales_transactions)
    • id (INTEGER, PRIMARY KEY)
    • customer_id (VARCHAR): matches customer_id in sales_transactions, e.g. 'CUST00001'
    • name (VARCHAR): full name
    • email (VARCHAR)
    • region (VARCHAR): dominant region from purchase history
    • signup_date (TIMESTAMP): date customer first registered
    • total_purchases (NUMERIC): lifetime spend derived from sales_transactions

    TABLE: products (20 rows — full product catalog)
    • id (INTEGER, PRIMARY KEY)
    • product_name (VARCHAR): matches product_name in sales_transactions
    • category (VARCHAR): matches product_category in sales_transactions
    • avg_unit_price (NUMERIC): historical average price from sales
    • min_unit_price (NUMERIC)
    • max_unit_price (NUMERIC)
    • description (TEXT): product description

    TABLE: inventory (2,000 rows — stock levels per store per product)
    • id (INTEGER, PRIMARY KEY)
    • store_id (VARCHAR): matches store_id in sales_transactions, e.g. 'E001'
    • product_name (VARCHAR): matches product_name in sales_transactions
    • stock_level (INTEGER): current units in stock
    • reorder_point (INTEGER): threshold that triggers reorder
    • last_restocked (TIMESTAMP)

    TABLE: returns (3,000 rows — product return records)
    • id (INTEGER, PRIMARY KEY)
    • transaction_id (INTEGER): references id in sales_transactions
    • customer_id (VARCHAR): references customer_id in sales_transactions
    • product_name (VARCHAR)
    • return_date (TIMESTAMP)
    • reason (VARCHAR): 'Changed mind', 'Defective product', 'Wrong size', 'Not as described', 'Better price found', 'Duplicate order', 'Quality not satisfactory'
    • refund_amount (NUMERIC)
    • status (VARCHAR): 'pending', 'approved', 'received', 'refunded', 'rejected'

    TABLE: support_cases (2,000 rows — customer support tickets)
    • id (INTEGER, PRIMARY KEY)
    • customer_id (VARCHAR): references customer_id in sales_transactions
    • subject (VARCHAR): issue description
    • priority (VARCHAR): 'low', 'medium', 'high', 'urgent'
    • status (VARCHAR): 'open', 'in_progress', 'resolved', 'closed'
    • created_at (TIMESTAMP): when ticket was opened (all in 2024)
    • resolved_at (TIMESTAMP): NULL if not yet resolved

    JOIN EXAMPLES:
    • sales + customers: JOIN customers c ON st.customer_id = c.customer_id
    • sales + returns: JOIN returns r ON st.id = r.transaction_id
    • sales + support: JOIN support_cases sc ON st.customer_id = sc.customer_id
    • inventory by store: SELECT store_id, SUM(stock_level) FROM inventory GROUP BY store_id

    POSTGRESQL NOTES:
    • Use ILIKE for case-insensitive matching
    • Use DATE_TRUNC('month', column) for grouping by month
    • Total revenue = ROUND(SUM(total_amount)::numeric, 2)
    """
    
    
    def _detect_query_complexity(self, question: str) -> str:
        """Detect if query is complex or simple"""
        
        question_lower = question.lower()
        
        complex_keywords = [
            'join', 'compare', 'trend', 'growth', 'year-over-year',
            'yoy', 'mom', 'correlation', 'rank', 'top.*by',
            'relationship', 'impact', 'multiple', 'complex'
        ]
        
        for keyword in complex_keywords:
            if keyword in question_lower:
                return "complex"
        
        return "simple"
    
    
    def _models_for_complexity(self, complexity: str) -> List[Dict[str, Any]]:
        """Return ordered model configs for a task, including optional Gemini Pro."""
        models_to_try = list(self.MODELS.get(complexity, self.MODELS["simple"]))

        if settings.use_gemini_pro and settings.google_api_key:
            gemini_pro_config = {
                "name": "gemini-2.5-pro",
                "type": "gemini",
                "description": "Gemini 2.5 Pro (Best for complex queries)",
                "quota": "50/day (free tier)"
            }
            models_to_try = [gemini_pro_config] + models_to_try
            logger.info("🟢 Gemini Pro ENABLED - trying first")

        return models_to_try


    def _invoke_with_fallback(
        self,
        prompt: str,
        complexity: str = "simple",
        task: str = "sql_agent",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Invoke LLM with intelligent fallback and quota tracking.
        Skips models known to be unavailable.
        
        Returns:
            {
                "success": bool,
                "response": str,
                "model_used": str,
                "models_tried": [
                    {"model": str, "status": str, "error": str, "time": float}
                ]
            }
        """
        
        metadata = {"agent": "sql", "complexity": complexity}
        if extra_metadata:
            metadata.update(extra_metadata)
        return self.llm_gateway.invoke_with_fallback(
            prompt=prompt,
            models=self._models_for_complexity(complexity),
            tracker=self.tracker,
            task=task,
            temperature=0.1,
            metadata=metadata,
        )
    
    
    def _create_sql_prompt(self, question: str) -> str:
        """Create prompt for SQL generation"""
        
        prompt_template = """You are an expert PostgreSQL query generator.

{schema}
{business_context}USER QUESTION: {question}

RULES:
1. Generate ONLY valid PostgreSQL query
2. Use table aliases for clarity
3. Use aggregate functions when needed
4. Add ORDER BY and LIMIT for rankings
5. NEVER use DELETE, DROP, UPDATE, INSERT
6. Return ONLY the SQL query, no explanations
7. PostgreSQL ROUND rules (CRITICAL — wrong form causes "function not exist" error):
   - Simple aggregate: ROUND(SUM(col)::numeric, 2) ✓
   - Percentage/ratio: ROUND((numerator * 100.0 / denominator)::numeric, 2) ✓
   - Cast the ENTIRE expression to ::numeric BEFORE ROUND, not inside SUM
   - WRONG: ROUND(SUM(col) * 100.0 / SUM(other), 2) — double precision ÷ returns double
   - RIGHT:  ROUND((SUM(col) * 100.0 / NULLIF(SUM(other), 0))::numeric, 2)
   - Always use NULLIF(denominator, 0) to avoid division by zero
8. For single aggregate questions over {table_name}, include COUNT(*) AS transactions_analyzed unless the user asks only for a count
9. For display, list, sample, or "show rows" requests (not validation queries), return detail columns with LIMIT only; never add aggregate columns such as COUNT(*)
10. For questions using "validate", "verify", "confirm", or "compare" with a single category or time period, generate a single-row aggregate query using SUM/COUNT WITHOUT GROUP BY on detail columns (region, store, product) — one total number is required for cross-source comparison

SQL QUERY:"""

        business_context = {"block": "", "ids": [], "chars": 0}
        if business_context_enabled():
            business_context = build_context_block(question)
        # Stashed for generate_query so context IDs reach ledger/trace metadata.
        self._last_business_context = business_context

        # Empty context must leave the prompt byte-identical to the
        # pre-context-layer prompt (single blank line between sections).
        context_section = f"\n{business_context['block']}\n\n" if business_context["block"] else "\n"

        return prompt_template.format(
            schema=self.schema_context,
            business_context=context_section,
            question=question,
            table_name=self.data_context.sql_table,
        )

    
    
    @staticmethod
    def _legacy_validate_query(sql_query: str) -> tuple[bool, str]:
        """Conservative text fallback used only when sqlglot is unavailable."""
        query_upper = sql_query.upper().strip()
        forbidden = ['DELETE', 'DROP', 'TRUNCATE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']

        for keyword in forbidden:
            if re.search(rf"\b{keyword}\b", query_upper):
                return False, f"Forbidden keyword: {keyword}"

        if not query_upper.startswith('SELECT') and not query_upper.startswith('WITH'):
            return False, "Only SELECT queries allowed"

        return True, ""

    @staticmethod
    def _unsafe_statement_type(expression) -> Optional[str]:
        if exp is None or expression is None:
            return None

        unsafe_types = {
            exp.Delete: "DELETE",
            exp.Drop: "DROP",
            exp.Update: "UPDATE",
            exp.Insert: "INSERT",
            exp.Alter: "ALTER",
            exp.Create: "CREATE",
        }
        truncate_type = getattr(exp, "TruncateTable", None) or getattr(exp, "Truncate", None)
        if truncate_type is not None:
            unsafe_types[truncate_type] = "TRUNCATE"

        for node in expression.walk():
            for node_type, label in unsafe_types.items():
                if isinstance(node, node_type):
                    return label
        return None

    @staticmethod
    def _is_read_only_expression(expression) -> bool:
        if exp is None or expression is None:
            return False

        read_only_types = [exp.Select, exp.Union, exp.Except, exp.Intersect]
        return isinstance(expression, tuple(read_only_types))

    def _validate_query(self, sql_query: str) -> tuple[bool, str]:
        """Safety check: parse SQL and allow only one read-only statement."""
        if not str(sql_query or "").strip():
            return False, "Empty SQL query"

        if sqlglot is None:
            return self._legacy_validate_query(sql_query)

        try:
            statements = sqlglot.parse(sql_query, read="postgres")
        except Exception as exc:
            parse_error_types = tuple(
                error_type
                for error_type in (
                    getattr(sqlglot_errors, "ParseError", None),
                    getattr(sqlglot_errors, "TokenError", None),
                )
                if error_type is not None
            )
            if parse_error_types and isinstance(exc, parse_error_types):
                return False, f"SQL parse error: {str(exc).splitlines()[0]}"
            return False, f"SQL parse error: {str(exc).splitlines()[0]}"

        statements = [statement for statement in statements if statement is not None]
        if not statements:
            return False, "Empty SQL query"

        for statement in statements:
            unsafe_type = self._unsafe_statement_type(statement)
            if unsafe_type:
                return False, f"Forbidden statement type: {unsafe_type}"

        if len(statements) != 1:
            return False, "Only one SQL statement allowed"

        statement = statements[0]
        if not self._is_read_only_expression(statement):
            return False, "Only SELECT or WITH queries allowed"

        return True, ""
    
    
    def generate_query(self, question: str) -> Dict[str, Any]:
        """Generate SQL from natural language"""
        
        complexity = self._detect_query_complexity(question)
        prompt = self._create_sql_prompt(question)
        context_meta = getattr(self, "_last_business_context", None) or {"ids": [], "chars": 0}

        logger.info(f"🤔 Generating SQL for: {question} (Complexity: {complexity})")
        if context_meta.get("ids"):
            logger.info(f"📚 Business context applied: {', '.join(context_meta['ids'])}")

        extra_metadata = None
        if context_meta.get("ids"):
            extra_metadata = {
                "business_context_ids": context_meta["ids"],
                "business_context_chars": context_meta.get("chars", 0),
            }
        result = self._invoke_with_fallback(
            prompt, complexity, task="sql.generate_query", extra_metadata=extra_metadata
        )
        
        if not result["success"]:
            return {
                "success": False,
                "query": None,
                "error": result.get("error", "Failed to generate SQL"),
                "models_tried": result["models_tried"]
            }
        
        # Clean SQL
        sql_query = self._strip_sql_fences(result["response"])

        # Validate
        is_safe, error = self._validate_query(sql_query)
        if not is_safe:
            return {
                "success": False,
                "query": sql_query,
                "error": error,
                "models_tried": result["models_tried"]
            }
        
        return {
            "success": True,
            "query": sql_query,
            "question": question,
            "complexity": complexity,
            "model_used": result["model_used"],
            "models_tried": result["models_tried"],
            "business_context": context_meta if context_meta.get("ids") else None,
        }
    
    def execute_query(self, sql_query: str) -> Dict[str, Any]:
        """Execute SQL and return results with auto-recovery"""
        
        try:
            is_safe, error = self._validate_query(sql_query)
            if not is_safe:
                return {"success": False, "error": error, "results": None}
            
            logger.info("⚡ Executing query...")
            result = self.session.execute(text(sql_query))
            
            rows = result.fetchall()
            columns = result.keys()
            
            data = [dict(zip(columns, row)) for row in rows]
            
            # Commit successful transaction
            self.session.commit()
            
            logger.info(f"✅ Query returned {len(data)} rows")
            
            return {
                "success": True,
                "results": data,
                "row_count": len(data),
                "columns": list(columns)
            }
        
        except Exception as e:
            # ROLLBACK failed transaction to recover
            self.session.rollback()
            logger.error(f"❌ Query error (rolled back): {str(e)}")
            return {"success": False, "error": str(e), "results": None}
    
    
    @staticmethod
    def _strip_sql_fences(sql_text: str) -> str:
        sql_text = str(sql_text or "")
        if sql_text.startswith('```sql'):
            return sql_text.replace('```sql', '').replace('```', '').strip()
        if sql_text.startswith('```'):
            return sql_text.replace('```', '').strip()
        return sql_text.strip()

    # Database errors worth one error-feedback repair attempt: the SQL parsed
    # as safe but PostgreSQL rejected its semantics. Connection/timeout/quota
    # problems are NOT repairable by rewriting SQL and must not burn a call.
    _REPAIRABLE_DB_ERROR = re.compile(
        r"syntax error|GROUP BY|aggregate|cannot cast|does not exist|undefined"
        r"|ambiguous|invalid input|operator|GroupingError|must appear",
        re.IGNORECASE,
    )

    def _attempt_sql_repair(
        self,
        question: str,
        failed_sql: str,
        db_error: str,
        complexity: str = "simple",
    ) -> Dict[str, Any]:
        """One bounded error-feedback repair: regenerate SQL with the DB error
        in context, re-validate with the same AST safety gate, execute once.

        Never loops. Never hides the original error. Returns
        {"success", "query", "execution_result", "models_tried", "metadata"}.
        """
        metadata = {
            "attempted": False,
            "succeeded": False,
            "original_error": str(db_error)[:300],
        }

        if not self._REPAIRABLE_DB_ERROR.search(str(db_error)):
            metadata["reason"] = "error_not_repairable_by_sql_rewrite"
            return {"success": False, "metadata": metadata, "models_tried": []}

        metadata["attempted"] = True
        context_meta = getattr(self, "_last_business_context", None) or {}
        context_block = context_meta.get("block") or ""

        repair_prompt = f"""You are an expert PostgreSQL query repairer.

A generated query failed when PostgreSQL executed it. Fix it.

{self.schema_context}
{context_block}
ORIGINAL QUESTION: {question}

FAILED SQL:
{failed_sql}

POSTGRESQL ERROR:
{db_error}

RULES:
1. Return ONLY the corrected PostgreSQL query, no explanations
2. Keep it a single read-only SELECT or WITH statement
3. Fix the specific error above; preserve the original intent of the question
4. Never mix a bare aggregate like COUNT(*) with non-grouped columns in the same SELECT
5. Cast intervals via EXTRACT(EPOCH FROM ...) before numeric math

CORRECTED SQL:"""

        extra_metadata = {"repair": True}
        if context_meta.get("ids"):
            extra_metadata["business_context_ids"] = context_meta["ids"]
        result = self._invoke_with_fallback(
            repair_prompt, complexity, task="sql.repair_query", extra_metadata=extra_metadata
        )
        if not result["success"]:
            metadata["reason"] = "repair_generation_failed"
            return {"success": False, "metadata": metadata, "models_tried": result.get("models_tried", [])}

        repaired_sql = self._strip_sql_fences(result["response"])
        is_safe, safety_error = self._validate_query(repaired_sql)
        if not is_safe:
            metadata["reason"] = "repaired_sql_rejected_by_safety_gate"
            metadata["safety_error"] = safety_error
            logger.warning("🔧 SQL repair rejected by safety gate: %s", safety_error)
            return {"success": False, "metadata": metadata, "models_tried": result.get("models_tried", [])}

        execution_result = self.execute_query(repaired_sql)
        metadata["repair_model"] = result.get("model_used")
        if execution_result.get("success"):
            metadata["succeeded"] = True
            logger.info("🔧 SQL repair succeeded after: %s", str(db_error)[:120])
            return {
                "success": True,
                "query": repaired_sql,
                "execution_result": execution_result,
                "metadata": metadata,
                "models_tried": result.get("models_tried", []),
            }

        metadata["reason"] = "repaired_sql_execution_failed"
        metadata["repair_error"] = str(execution_result.get("error"))[:300]
        return {"success": False, "metadata": metadata, "models_tried": result.get("models_tried", [])}

    # Column-name heuristics for deterministic value rendering.
    # Order matters: percent and count hints win over money hints so columns
    # like "total_transactions" or "return_rate" are not rendered as dollars.
    _PCT_COLUMN_HINTS = ("percent", "pct", "rate", "margin", "share", "ratio")
    _COUNT_COLUMN_HINTS = (
        "count", "quantity", "transactions", "orders", "units",
        "customers", "items", "records", "num_", "rows", "qty",
    )
    _MONEY_COLUMN_HINTS = (
        "revenue", "amount", "price", "sales", "cost", "total",
        "spend", "value", "profit", "income",
    )

    @classmethod
    def _classify_column(cls, column: str) -> str:
        name = column.lower()
        if any(hint in name for hint in cls._PCT_COLUMN_HINTS):
            return "percent"
        if any(hint in name for hint in cls._COUNT_COLUMN_HINTS):
            return "count"
        if any(hint in name for hint in cls._MONEY_COLUMN_HINTS):
            return "money"
        return "plain"

    @classmethod
    def _format_cell(cls, column: str, value: Any) -> str:
        """Render one SQL value as business-friendly text without an LLM."""
        if value is None:
            return "n/a"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)

        kind = cls._classify_column(column)
        if kind == "percent":
            return f"{number:,.2f}%"
        if kind == "count":
            return f"{int(round(number)):,}"
        if kind == "money":
            return f"${number:,.2f}"
        if float(number).is_integer():
            return f"{int(number):,}"
        return f"{number:,.2f}"

    @staticmethod
    def _humanize_column(column: str) -> str:
        return str(column).replace("_", " ").strip().capitalize()

    def _deterministic_format_answer(self, results: list) -> Optional[str]:
        """Format common SQL result shapes without an LLM call.

        Returns None when the shape is unusual, so the caller can fall back
        to LLM formatting.
        """
        if not results or not isinstance(results[0], dict):
            return None

        columns = list(results[0].keys())
        if not columns:
            return None

        # Single row, single column: scalar aggregate.
        if len(results) == 1 and len(columns) == 1:
            column = columns[0]
            return f"{self._humanize_column(column)}: **{self._format_cell(column, results[0][column])}**"

        # Single row, multiple columns: key-value summary.
        if len(results) == 1:
            lines = [
                f"- {self._humanize_column(column)}: **{self._format_cell(column, results[0][column])}**"
                for column in columns
            ]
            return "Result:\n" + "\n".join(lines)

        # Multiple rows: markdown table, capped at 10 rows.
        display_rows = results[:10]
        header = "| " + " | ".join(self._humanize_column(column) for column in columns) + " |"
        divider = "|" + "|".join([" --- "] * len(columns)) + "|"
        body = [
            "| " + " | ".join(self._format_cell(column, row.get(column)) for column in columns) + " |"
            for row in display_rows
        ]
        table = "\n".join([header, divider, *body])
        if len(results) > len(display_rows):
            table += f"\n\nShowing first {len(display_rows)} of {len(results):,} rows."
        return f"Found {len(results):,} results:\n\n{table}"

    def _format_answer(self, question: str, query: str, results: list, complexity: str) -> Dict[str, Any]:
        """Format results as natural language"""

        if not results:
            return {
                "success": True,
                "answer": "No data found matching your question.",
                "models_tried": []
            }

        sample_results = results[:10] if len(results) > 10 else results

        formatting_prompt = f"""Based on this SQL query and results, provide a clear answer.

QUESTION: {question}
SQL QUERY: {query}
RESULTS: {sample_results}

Provide a business-friendly answer with:
1. Direct answer to the question
2. Key numbers highlighted
3. Brief insights if multiple rows

ANSWER:"""

        format_mode = os.getenv("NEXUSIQ_SQL_FORMAT_MODE", "deterministic").lower()
        if format_mode != "llm":
            deterministic_answer = self._deterministic_format_answer(results)
            if deterministic_answer:
                self.llm_gateway.record_avoided_call(
                    task="sql.format_answer",
                    reason="deterministic_sql_format",
                    prompt=formatting_prompt,
                    metadata={"agent": "sql", "complexity": complexity, "row_count": len(results)},
                )
                return {
                    "success": True,
                    "answer": deterministic_answer,
                    "models_tried": [],
                    "answer_mode": "deterministic_sql_format",
                }

        result = self._invoke_with_fallback(formatting_prompt, complexity, task="sql.format_answer")
        
        if result["success"]:
            return {
                "success": True,
                "answer": result["response"],
                "models_tried": result["models_tried"],
                "answer_mode": "llm_sql_format",
            }
        else:
            # Fallback to simple formatting
            if len(results) == 1:
                simple_answer = f"Result: {', '.join(f'{k}: {v}' for k, v in results[0].items())}"
            else:
                simple_answer = f"Found {len(results)} results. Top result: {results[0]}"
            
            return {
                "success": True,
                "answer": simple_answer,
                "models_tried": result.get("models_tried", []),
                "answer_mode": "deterministic_fallback",
            }
    
    
    def _explain_query(self, sql_query: str, question: str) -> Dict[str, Any]:
        """Generate plain English explanation of SQL query"""

        explanation_prompt = f"""You are a SQL teacher explaining a query to a beginner.

ORIGINAL QUESTION: {question}

SQL QUERY:
{sql_query}

Explain this query in simple terms. Break it down step-by-step.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

**Overview:** [One sentence summary of what the query does]

**Step-by-step breakdown:**
1. **FROM [table]** → [What data source we're using and why]
2. **WHERE [condition]** → [What filters are applied and why]
3. **GROUP BY [column]** → [How data is grouped, if applicable]
4. **SELECT [columns]** → [What data we're retrieving]
5. **ORDER BY [column]** → [How results are sorted, if applicable]
6. **LIMIT [n]** → [Why we're limiting results, if applicable]

**Key insight:** [One sentence about what makes this query effective]

Only include steps that are actually in the query. Be concise but clear.

EXPLANATION:"""

        explain_mode = os.getenv("NEXUSIQ_SQL_EXPLAIN_MODE", "deterministic").lower()
        if explain_mode != "llm":
            self.llm_gateway.record_avoided_call(
                task="sql.explain_query",
                reason="deterministic_explanation_default",
                prompt=explanation_prompt,
                metadata={"agent": "sql"},
            )
            return {
                "success": True,
                "explanation": self._generate_basic_explanation(sql_query),
                "models_tried": [],
                "explanation_mode": "deterministic_explanation",
            }

        result = self._invoke_with_fallback(explanation_prompt, "simple", task="sql.explain_query")

        if result["success"]:
            return {
                "success": True,
                "explanation": result["response"],
                "models_tried": result["models_tried"],
                "explanation_mode": "llm_explanation",
            }
        else:
            return {
                "success": True,
                "explanation": self._generate_basic_explanation(sql_query),
                "models_tried": result.get("models_tried", []),
                "explanation_mode": "deterministic_fallback",
            }
    
    
    def _generate_basic_explanation(self, sql_query: str) -> str:
        """Generate basic explanation without LLM (fallback)"""
        
        explanation_parts = ["**Query breakdown:**\n"]
        sql_upper = sql_query.upper()
        
        if "SELECT" in sql_upper:
            if "SUM(" in sql_upper:
                explanation_parts.append("• **Aggregation:** Calculating totals using SUM()")
            if "COUNT(" in sql_upper:
                explanation_parts.append("• **Counting:** Counting records using COUNT()")
            if "AVG(" in sql_upper:
                explanation_parts.append("• **Average:** Calculating averages using AVG()")
        
        if self.data_context.sql_table.upper() in sql_upper:
            explanation_parts.append(f"• **Data source:** Using {self.data_context.label}")
        
        if "WHERE" in sql_upper:
            explanation_parts.append("• **Filtering:** Applying conditions to narrow down results")
        
        if "GROUP BY" in sql_upper:
            explanation_parts.append("• **Grouping:** Organizing results into categories")
        
        if "ORDER BY" in sql_upper:
            if "DESC" in sql_upper:
                explanation_parts.append("• **Sorting:** Ordering results from highest to lowest")
            else:
                explanation_parts.append("• **Sorting:** Ordering results from lowest to highest")
        
        if "LIMIT" in sql_upper:
            explanation_parts.append("• **Limiting:** Restricting to top N results")
        
        if "JOIN" in sql_upper:
            explanation_parts.append("• **Joining:** Combining data from multiple tables")
        
        return "\n".join(explanation_parts)
    
    
    @rate_limit(calls_per_minute=20)
    def ask(self, question: str) -> Dict[str, Any]:
        """Main method: Ask a question, get complete answer with execution history."""
        
        start_time = time.time()
        all_models_tried = []
        correction_note = None
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 SQL AGENT — Processing Question")
        logger.info(f"{'='*60}")

        # ═══════════════════════════════════════════════════════
        # Step 0: Validate question with auto-correction
        # ═══════════════════════════════════════════════════════
        
        validation = validate_question(
            question,
            auto_fix=True,
            available_years=self.data_context.available_years,
        )
        
        # If auto-corrected, use the corrected question
        if validation.get("auto_corrected"):
            corrected_q = validation["corrected_question"]
            logger.info(f"✨ Auto-corrected: '{question}' → '{corrected_q}'")
            correction_note = f"Auto-corrected: {', '.join([c['from'] + ' → ' + c['to'] for c in validation.get('corrections', [])])}"
            question = corrected_q
        
        # If still not valid, return error
        if not validation["valid"]:
            return {
                "success": False,
                "question": question,
                "error": "Question validation failed",
                "validation_issues": validation["issues"],
                "suggestions": validation["suggestions"],
                "execution_time": time.time() - start_time
            }
        
        # ═══════════════════════════════════════════════════════
        # Step 1: Generate SQL
        # ═══════════════════════════════════════════════════════
        
        query_result = self.generate_query(question)
        all_models_tried.extend(query_result.get("models_tried", []))
        
        if not query_result["success"]:
            return {
                "success": False,
                "question": question,
                "query": query_result.get("query"),
                "error": query_result.get("error", "Failed to generate SQL"),
                "models_tried": all_models_tried,
                "execution_time": time.time() - start_time
            }
        
        # ═══════════════════════════════════════════════════════
        # Step 2: Execute SQL
        # ═══════════════════════════════════════════════════════
        
        execution_result = self.execute_query(query_result["query"])

        # Bounded verification loop: on a semantic DB failure, regenerate the
        # SQL once with the error in context, re-validate, execute. One
        # attempt only; the original error is preserved either way.
        sql_repair = None
        if not execution_result["success"]:
            repair = self._attempt_sql_repair(
                question=question,
                failed_sql=query_result["query"],
                db_error=execution_result.get("error", ""),
                complexity=query_result.get("complexity", "simple"),
            )
            sql_repair = repair["metadata"]
            all_models_tried.extend(repair.get("models_tried", []))
            if repair["success"]:
                query_result["query"] = repair["query"]
                execution_result = repair["execution_result"]

        if not execution_result["success"]:
            return {
                "success": False,
                "question": question,
                "query": query_result["query"],
                "error": execution_result.get("error", "Query execution failed"),
                "models_tried": all_models_tried,
                "model_used": query_result.get("model_used"),
                "sql_repair": sql_repair,
                "execution_time": time.time() - start_time
            }
        
        # ═══════════════════════════════════════════════════════
        # Step 3: Format answer
        # ═══════════════════════════════════════════════════════
        
        format_result = self._format_answer(
            question=question,
            query=query_result["query"],
            results=execution_result["results"],
            complexity=query_result.get("complexity", "simple")
        )
        all_models_tried.extend(format_result.get("models_tried", []))
        
        # ═══════════════════════════════════════════════════════
        # Step 4: Generate query explanation
        # ═══════════════════════════════════════════════════════
        
        explain_result = self._explain_query(
            sql_query=query_result["query"],
            question=question
        )
        all_models_tried.extend(explain_result.get("models_tried", []))
        
        # ═══════════════════════════════════════════════════════
        # Step 5: Return complete result
        # ═══════════════════════════════════════════════════════
        
        total_time = time.time() - start_time
        
        return {
            "success": True,
            "question": question,
            "query": query_result["query"],
            "results": execution_result["results"],
            "row_count": execution_result["row_count"],
            "answer": format_result["answer"],
            "explanation": explain_result.get("explanation", ""),
            "answer_mode": format_result.get("answer_mode"),
            "explanation_mode": explain_result.get(
                "explanation_mode",
                "llm_explanation" if explain_result.get("models_tried") else "deterministic_fallback",
            ),
            "explanation_generated_by_llm": bool(explain_result.get("models_tried")),
            "complexity": query_result.get("complexity", "simple"),
            "model_used": query_result.get("model_used"),
            "models_tried": all_models_tried,
            "execution_time": total_time,
            "correction_note": correction_note,
            "business_context": query_result.get("business_context"),
            "sql_repair": sql_repair,
        }

    
    
    def get_quota_status(self) -> Dict[str, dict]:
        """Get current quota status for all models"""
        return self.tracker.get_status_report()
    
    
    def reset_quota_tracking(self):
        """Reset all quota tracking (use when quotas refresh)"""
        self.tracker.reset_all()
    
    
    def close(self):
        """Close database connection"""
        self.session.close()
        logger.info("🔌 SQL Agent connection closed")


# ═══════════════════════════════════════════════════════════
#  TESTING
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    agent = SQLAgent(mode="development")
    
    test_questions = [
        "What is the total revenue?",
        "Top 5 products by revenue?",
        "Compare revenue by region?",
    ]
    
    print("\n" + "="*60)
    print("🧪 TESTING SQL AGENT WITH QUOTA TRACKING")
    print("="*60 + "\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'─'*60}")
        print(f"❓ Q{i}: {question}")
        print('─'*60)
        
        result = agent.ask(question)
        
        if result["success"]:
            print(f"\n✅ QUERY:\n{result['query']}\n")
            print(f"📊 ROWS: {result['row_count']}")
            print(f"⏱️ TIME: {result['execution_time']:.2f}s")
            print(f"\n💬 ANSWER:\n{result['answer']}\n")
            
            print("\n📋 MODELS TRIED:")
            for m in result["models_tried"]:
                print(f"   {m['status']} {m['model']} ({m['time']}s)")
        else:
            print(f"\n❌ ERROR: {result['error']}\n")
        
        time.sleep(1)
    
    print("\n📊 QUOTA STATUS:")
    print(agent.get_quota_status())
    
    agent.close()
