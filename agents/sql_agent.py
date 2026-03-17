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

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from utils.quota_tracker import get_tracker
from typing import Dict, Any, List
import logging
import time
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
            {
                "name": "gemini-2.5-pro",
                "type": "gemini",
                "description": "Gemini 2.5 Pro (Best for complex queries)",
                "quota": "500/day"
            },
            {
                "name": "llama-3.3-70b-versatile",
                "type": "groq",
                "description": "Groq Llama 3.3 70B (Fast fallback)",
                "quota": "14,400/day"
            },
            {
                "name": "deepseek-coder:6.7b",
                "type": "ollama",
                "description": "Ollama DeepSeek-Coder (Unlimited local)",
                "quota": "Unlimited"
            }
        ],
        "simple": [
            {
                "name": "llama-3.3-70b-versatile",
                "type": "groq",
                "description": "Groq Llama 3.3 70B (Fast)",
                "quota": "14,400/day"
            },
            {
                "name": "deepseek-coder:6.7b",
                "type": "ollama",
                "description": "Ollama DeepSeek-Coder (Unlimited local)",
                "quota": "Unlimited"
            },
            {
                "name": "gemini-2.5-flash",
                "type": "gemini",
                "description": "Gemini 2.5 Flash (Backup)",
                "quota": "500/day"
            }
        ]
    }
    
    def __init__(self, mode: str = "development"):
        """Initialize SQL Agent"""
        
        self.mode = mode
        self.tracker = get_tracker()
        
        # Database connection
        self.engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.session.rollback()  # Clear any leftover transactions
        
        # Schema context
        self.schema_context = self._get_schema_info()
        
        logger.info(f"✅ SQL Agent initialized in {mode.upper()} mode")
    
    
    def _get_schema_info(self) -> str:
        """Get database schema for LLM context"""
        
        schema = """
I am using PostgreSQL 15. Here is my database schema:

TABLE: sales_transactions (100,000 rows)
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

TABLE: inventory
  • id, store_id, product_name, stock_level, reorder_point, last_restocked

TABLE: customers (5,000 rows)
  • id, customer_id, name, email, region, signup_date, total_purchases

POSTGRESQL NOTES:
• Use ILIKE for case-insensitive matching
• Use DATE_TRUNC('month', column) for grouping
• Use CURRENT_DATE, INTERVAL '1 month' for dates
• Total revenue = SUM(total_amount)
"""
        return schema
    
    
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
    
    
    def _create_llm(self, model_config: dict):
        """Create LLM instance based on model config"""
        
        model_type = model_config["type"]
        model_name = model_config["name"]
        
        if model_type == "gemini":
            if not settings.google_api_key:
                raise Exception("Gemini API key not configured")
            
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=settings.google_api_key,
                temperature=0.1,
                max_retries=2  # Reduced retries for faster fallback
            )
        
        elif model_type == "groq":
            if not settings.groq_api_key:
                raise Exception("Groq API key not configured")
            
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=model_name,
                groq_api_key=settings.groq_api_key,
                temperature=0.1
            )
        
        elif model_type == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model_name,
                temperature=0.1
            )
        
        else:
            raise Exception(f"Unknown model type: {model_type}")
    
    
    def _invoke_with_fallback(self, prompt: str, complexity: str = "simple") -> Dict[str, Any]:
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
        
        models_to_try = self.MODELS.get(complexity, self.MODELS["simple"])
        models_tried = []
        
        for model_config in models_to_try:
            model_name = model_config["name"]
            model_start = time.time()
            
            # CHECK QUOTA TRACKER FIRST
            is_available, skip_reason = self.tracker.is_available(model_name)
            
            if not is_available:
                # Skip this model - it's known to be dead
                models_tried.append({
                    "model": model_name,
                    "description": model_config["description"],
                    "status": "⏭️ SKIPPED",
                    "error": skip_reason,
                    "time": 0.0
                })
                logger.info(f"⏭️ Skipping {model_name}: {skip_reason}")
                continue
            
            # TRY THE MODEL
            try:
                logger.info(f"🔄 Trying {model_config['description']}...")
                
                llm = self._create_llm(model_config)
                response = llm.invoke(prompt)
                
                elapsed = time.time() - model_start
                
                # SUCCESS - Mark model as working
                self.tracker.report_success(model_name)
                
                models_tried.append({
                    "model": model_name,
                    "description": model_config["description"],
                    "status": "✅ SUCCESS",
                    "error": None,
                    "time": round(elapsed, 2)
                })
                
                logger.info(f"✅ Success with {model_name} in {elapsed:.2f}s")
                
                return {
                    "success": True,
                    "response": response.content.strip(),
                    "model_used": model_config["description"],
                    "models_tried": models_tried
                }
            
            except Exception as e:
                elapsed = time.time() - model_start
                error_msg = str(e)
                
                # FAILURE - Mark model as dead
                self.tracker.report_failure(model_name, error_msg)
                
                # Determine error type for display
                if "429" in error_msg or "quota" in error_msg.lower():
                    status = "❌ QUOTA EXCEEDED"
                elif "404" in error_msg:
                    status = "❌ MODEL NOT FOUND"
                elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    status = "❌ CONNECTION ERROR"
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
        
        # ALL MODELS FAILED
        return {
            "success": False,
            "response": None,
            "model_used": None,
            "models_tried": models_tried,
            "error": "All LLM models failed"
        }
    
    
    def _create_sql_prompt(self, question: str) -> str:
        """Create prompt for SQL generation"""
        
        prompt_template = """You are an expert PostgreSQL query generator.

{schema}

USER QUESTION: {question}

RULES:
1. Generate ONLY valid PostgreSQL query
2. Use table aliases for clarity
3. Use aggregate functions when needed
4. Add ORDER BY and LIMIT for rankings
5. NEVER use DELETE, DROP, UPDATE, INSERT
6. Return ONLY the SQL query, no explanations

SQL QUERY:"""

        return prompt_template.format(schema=self.schema_context, question=question)
    
    
    def _validate_query(self, sql_query: str) -> tuple[bool, str]:
        """Safety check: ensure query is read-only"""
        
        query_upper = sql_query.upper().strip()
        
        forbidden = ['DELETE', 'DROP', 'TRUNCATE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']
        
        for keyword in forbidden:
            if keyword in query_upper:
                return False, f"Forbidden keyword: {keyword}"
        
        if not query_upper.startswith('SELECT') and not query_upper.startswith('WITH'):
            return False, "Only SELECT queries allowed"
        
        return True, ""
    
    
    def generate_query(self, question: str) -> Dict[str, Any]:
        """Generate SQL from natural language"""
        
        complexity = self._detect_query_complexity(question)
        prompt = self._create_sql_prompt(question)
        
        logger.info(f"🤔 Generating SQL for: {question} (Complexity: {complexity})")
        
        result = self._invoke_with_fallback(prompt, complexity)
        
        if not result["success"]:
            return {
                "success": False,
                "query": None,
                "error": result.get("error", "Failed to generate SQL"),
                "models_tried": result["models_tried"]
            }
        
        # Clean SQL
        sql_query = result["response"]
        if sql_query.startswith('```sql'):
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        elif sql_query.startswith('```'):
            sql_query = sql_query.replace('```', '').strip()
        
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
            "models_tried": result["models_tried"]
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

        result = self._invoke_with_fallback(formatting_prompt, complexity)
        
        if result["success"]:
            return {
                "success": True,
                "answer": result["response"],
                "models_tried": result["models_tried"]
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
                "models_tried": result["models_tried"]
            }
    
    
    @rate_limit(calls_per_minute=20)
    def ask(self, question: str) -> Dict[str, Any]:
        """
        Main method: Ask a question, get complete answer with execution history.
        """
        
        start_time = time.time()
        all_models_tried = []
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 SQL AGENT — Processing Question")
        logger.info(f"{'='*60}")
        
        # Step 1: Generate SQL
        query_result = self.generate_query(question)
        all_models_tried.extend(query_result.get("models_tried", []))
        
        if not query_result["success"]:
            return {
                "success": False,
                "question": question,
                "error": query_result["error"],
                "models_tried": all_models_tried,
                "execution_time": time.time() - start_time
            }
        
        # Step 2: Execute SQL
        execution_result = self.execute_query(query_result["query"])
        
        if not execution_result["success"]:
            return {
                "success": False,
                "question": question,
                "query": query_result["query"],
                "error": execution_result["error"],
                "models_tried": all_models_tried,
                "model_used": query_result.get("model_used"),
                "execution_time": time.time() - start_time
            }
        
        # Step 3: Format answer
        format_result = self._format_answer(
            question=question,
            query=query_result["query"],
            results=execution_result["results"],
            complexity=query_result.get("complexity", "simple")
        )
        all_models_tried.extend(format_result.get("models_tried", []))
        
        total_time = time.time() - start_time
        
        return {
            "success": True,
            "question": question,
            "query": query_result["query"],
            "results": execution_result["results"],
            "row_count": execution_result["row_count"],
            "answer": format_result["answer"],
            "complexity": query_result.get("complexity", "simple"),
            "model_used": query_result.get("model_used"),
            "models_tried": all_models_tried,
            "execution_time": total_time
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
    
    # Show quota status
    print("\n📊 QUOTA STATUS:")
    print(agent.get_quota_status())
    
    agent.close()