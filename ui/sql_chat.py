"""
NexusIQ AI — SQL Agent Chat Interface
Features:
  - Independent tip rotation (timer-based)
  - Smart time formatting
  - Model journey log (if > 20s)
  - Progress tracking
"""

import streamlit as st
import pandas as pd
import time
import random
import threading
import sys
from datetime import datetime
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agents.sql_agent import SQLAgent

# ═══════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════

INSIGHTS = [
    "💡 **Did You Know?** We analyze 100,000 transactions across 5 regions",
    "🧠 **Did You Know?** Complex queries use Gemini 2.5 Pro — our smartest model",
    "⚡ **Did You Know?** Simple queries complete in under 5 seconds",
    "🔄 **Did You Know?** We auto-switch models if one hits quota limits",
    "🔒 **Did You Know?** All queries are read-only — your data stays safe",
    "📊 **Did You Know?** You can download results as CSV with one click",
    "🎯 **Did You Know?** Adding time ranges makes queries more precise",
    "🚀 **Did You Know?** Our circuit breaker skips failed models instantly",
    "💰 **Did You Know?** The database tracks $139M+ in total revenue",
    "🌐 **Did You Know?** We support 5 regions: East, West, North, South, Central",
    "🛒 **Did You Know?** Products span 5 categories: Electronics, Clothing, Food, Home, Sports",
    "⏱️ **Did You Know?** First query may be slower due to model warm-up",
]

# ═══════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def format_time(seconds: float) -> str:
    """
    Format seconds into human-readable time.
    < 60s: "35 seconds"
    60-3600s: "1 minute 15 seconds"
    > 3600s: "1 hour 5 minutes 30 seconds"
    """
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        if secs == 0:
            return f"{mins} minute{'s' if mins > 1 else ''}"
        return f"{mins} minute{'s' if mins > 1 else ''} {secs} seconds"
    else:
        hours = int(seconds // 3600)
        remaining = seconds % 3600
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        result = f"{hours} hour{'s' if hours > 1 else ''}"
        if mins > 0:
            result += f" {mins} minute{'s' if mins > 1 else ''}"
        if secs > 0:
            result += f" {secs} seconds"
        return result



# ═══════════════════════════════════════════════════════════
#  INITIALIZE AGENT
# ═══════════════════════════════════════════════════════════

@st.cache_resource
def get_agent():
    return SQLAgent(mode="development")

agent = get_agent()

# ═══════════════════════════════════════════════════════════
#  QUERY HISTORY STATE
# ═══════════════════════════════════════════════════════════

if "query_history" not in st.session_state:
    st.session_state.query_history = []

if "selected_history" not in st.session_state:
    st.session_state.selected_history = None

if "rerun_question" not in st.session_state:
    st.session_state.rerun_question = None

def add_to_history(question: str, result: dict, execution_time: float):
    """Add query to history (max 10 items)"""
    st.session_state.query_history.insert(0, {
        "question": question,
        "query": result.get("query", ""),
        "answer": result.get("answer", ""),
        "explanation": result.get("explanation", ""),
        "results": result.get("results", []),
        "row_count": result.get("row_count", 0),
        "success": result.get("success", False),
        "error": result.get("error", ""),
        "model_used": result.get("model_used", ""),
        "time": execution_time,
        "timestamp": datetime.now()
    })
    # Keep only last 10
    st.session_state.query_history = st.session_state.query_history[:10]

    # Keep only last 10
    st.session_state.query_history = st.session_state.query_history[:10]

def time_ago(timestamp: datetime) -> str:
    """Convert timestamp to human-readable 'time ago'"""
    diff = datetime.now() - timestamp
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        mins = int(seconds // 60)
        return f"{mins}m ago"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours}h ago"
    else:
        days = int(seconds // 86400)
        return f"{days}d ago"

# ═══════════════════════════════════════════════════════════
#  PAGE LAYOUT
# ═══════════════════════════════════════════════════════════

st.title("🗄️ SQL Agent — Database Query Interface")
st.markdown("*Ask questions about your sales data in plain English*")

# ═══════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════

with st.sidebar:
    st.header("📊 Database Schema")
    
    with st.expander("📋 sales_transactions"):
        st.code("""
• transaction_date
• region (5 regions)
• store_id
• product_category
• product_name
• quantity, unit_price
• total_amount
• customer_id
• payment_method
        """)
    
    with st.expander("👥 customers"):
        st.code("""
• customer_id
• name, email, region
• signup_date
• total_purchases
        """)
    
    st.markdown("---")
    st.subheader("💡 Examples")
    st.info("""
**Simple:**
- Total revenue?
- Sales in West region?

**Complex:**
- Top 5 products?
- Compare regions?
    """)
    
    st.markdown("---")
    
    # Quota status
    st.subheader("📊 Model Status")
    quota_status = agent.get_quota_status()
    if quota_status:
        for model, status in quota_status.items():
            st.caption(f"{status['status']} {model.split('-')[0]}")
    else:
        st.caption("🟢 All models available")
    
    if st.button("🔄 Reset Quota Tracking"):
        agent.reset_quota_tracking()
        st.success("Reset complete!")
        st.rerun()
    st.markdown("---")
    
    # Query History Section
    st.subheader("📜 Query History")
    
    if st.session_state.query_history:
        for i, item in enumerate(st.session_state.query_history):
            status_icon = "✅" if item["success"] else "❌"
            time_str = time_ago(item["timestamp"])
            
            # Truncate long questions
            short_question = item["question"][:30] + "..." if len(item["question"]) > 30 else item["question"]
            
            if st.button(f"{status_icon} {short_question}", key=f"history_{i}", use_container_width=True):
                st.session_state.selected_history = item
                st.rerun()
            
            st.caption(f"⏱️ {item['time']:.1f}s • {time_str}")
        
        # Clear history button
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.query_history = []
            st.rerun()
    else:
        st.caption("No queries yet")

# ═══════════════════════════════════════════════════════════
#  MAIN CHAT INTERFACE
# ═══════════════════════════════════════════════════════════

# Check if we're re-running from history
if "rerun_question" in st.session_state and st.session_state.rerun_question:
    question = st.session_state.rerun_question
    st.session_state.rerun_question = None  # Clear it
else:
    question = None
question = st.text_input(
    "💬 Ask a question:",
    value=question if question else "",
    placeholder="e.g., What was total revenue last month?",
    key="user_question"
)

col1, col2 = st.columns([1, 5])
with col1:
    ask_button = st.button("🔍 Ask", type="primary", use_container_width=True)


# ═══════════════════════════════════════════════════════════
#  DISPLAY SELECTED HISTORY ITEM
# ═══════════════════════════════════════════════════════════

if "selected_history" in st.session_state and st.session_state.selected_history:
    item = st.session_state.selected_history
    
    st.info(f"📜 **Showing saved result for:** {item['question']}")
    
    if item["success"]:
        # Success display
        time_display = format_time(item["time"])
        st.success(f"✅ Query completed in **{time_display}** (cached)")
        
        # Answer
        st.markdown("---")
        st.markdown("### 💬 Answer")
        st.markdown(item.get("answer", "No answer available"))
        
        # SQL Query
        if item.get("query"):
            with st.expander("🔍 View SQL Query"):
                st.code(item["query"], language="sql")
        
        # Explanation
        if item.get("explanation"):
            with st.expander("📖 How This Query Works"):
                st.markdown(item["explanation"])
        
        # Data Table
        if item.get("results"):
            with st.expander(f"📊 View Data ({item.get('row_count', 0)} rows)"):
                df = pd.DataFrame(item["results"])
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Download CSV",
                    data=csv,
                    file_name=f"query_{int(time.time())}.csv",
                    mime="text/csv"
                )
    else:
        # Error display
        st.error(f"❌ This query failed")
        st.markdown(f"**Error:** {item.get('error', 'Unknown error')}")
    
    # Button to clear selection and ask new question
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Re-run This Query", use_container_width=True):
            st.session_state.rerun_question = item["question"]
            st.session_state.selected_history = None
            st.rerun()
    with col2:
        if st.button("❌ Close & Ask New", use_container_width=True):
            st.session_state.selected_history = None
            st.rerun()
    
    # Stop here - don't show the normal query interface
    st.stop()

# ═══════════════════════════════════════════════════════════
#  QUERY PROCESSING
# ═══════════════════════════════════════════════════════════

if ask_button and question:
    # Clear any selected history when asking new question
    st.session_state.selected_history = None
    start_time = time.time()
    result = None
    
    # Create UI elements
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        insight_box = st.empty()
        
        # Initial tip
        current_insight = random.choice(INSIGHTS)
        insight_box.info(current_insight)
        
        # ─────────────────────────────────────
        # STEP 1: Analyze (5%)
        # ─────────────────────────────────────
        status_text.markdown("### 🔍 Step 1/5: Analyzing question...")
        progress_bar.progress(5)
        time.sleep(0.3)
        
        # ─────────────────────────────────────
        # STEP 2: Detect Complexity (15%)
        # ─────────────────────────────────────
        status_text.markdown("### 🧠 Step 2/5: Detecting complexity...")
        progress_bar.progress(15)
        time.sleep(0.3)
        
        # ─────────────────────────────────────
        # STEP 3: Select Model (25%)
        # ─────────────────────────────────────
        status_text.markdown("### 🤖 Step 3/5: Selecting AI model...")
        progress_bar.progress(25)
        time.sleep(0.3)
        
        # ─────────────────────────────────────
        # STEP 4: Generate SQL (Long wait)
        # ─────────────────────────────────────
        status_text.markdown("### ⚡ Step 4/5: Generating SQL query...")
        st.caption("*Complex queries may take 30-60 seconds if switching models*")
        progress_bar.progress(35)
        
        # Independent tip rotation during API call
        last_insight_time = time.time()
        insight_interval = 5  # Change tip every 6 seconds
        
        # Execute query with tip rotation
        query_start = time.time()
        
        # Create a flag for completion
        query_done = False
        
        while not query_done:
            # Update tip independently every 6 seconds
            if time.time() - last_insight_time > insight_interval:
                current_insight = random.choice([i for i in INSIGHTS if i != current_insight])
                insight_box.info(current_insight)
                last_insight_time = time.time()
            
            # Simulate progress (35% -> 70%)
            elapsed = time.time() - query_start
            simulated = min(70, 35 + int(elapsed * 0.5))
            progress_bar.progress(simulated)
            
            # Execute query (this blocks)
            if result is None:
                result = agent.ask(question)
                query_done = True
            
            time.sleep(0.3)
        
        # ─────────────────────────────────────
        # STEP 5: Execute & Format (100%)
        # ─────────────────────────────────────
        status_text.markdown("### ✅ Step 5/5: Formatting results...")
        progress_bar.progress(100)
        time.sleep(0.2)
    
    # Calculate total time
    total_time = time.time() - start_time
    
    # Clear progress
    progress_container.empty()
    
    # ═══════════════════════════════════════════════════════════
    #  DISPLAY RESULTS
    # ═══════════════════════════════════════════════════════════
    
    if result["success"]:
        # Save to history
        add_to_history(question, result, total_time)
        # ─────────────────────────────────────
        # SUCCESS HEADER WITH TIME
        # ─────────────────────────────────────
        time_display = format_time(total_time)
        st.success(f"✅ Query completed in **{time_display}**")
        
        # ─────────────────────────────────────
        # MODEL JOURNEY LOG (if > 20 seconds)
        # ─────────────────────────────────────
        if total_time > 20 and result.get("models_tried"):
            with st.expander("⏱️ **Why did it take this long?** (Click to see model journey)", expanded=True):
                st.markdown("**📋 Model Execution Journey:**")
                
                for i, model_info in enumerate(result["models_tried"], 1):
                    status = model_info["status"]
                    model = model_info["model"]
                    desc = model_info.get("description", model)
                    err = model_info.get("error", "")
                    model_time = model_info.get("time", 0)
                    
                    if "SUCCESS" in status:
                        st.markdown(f"""
                        **Step {i}:** {status} **{desc}**  
                        ⏱️ Completed in {model_time}s
                        """)
                    elif "SKIPPED" in status:
                        st.markdown(f"""
                        **Step {i}:** {status} **{desc}**  
                        ↳ Reason: {err}
                        """)
                    else:
                        st.markdown(f"""
                        **Step {i}:** {status} **{desc}**  
                        ↳ Error: {err[:100]}...  
                        ⏱️ Waited {model_time}s before switching
                        """)
                
                st.markdown(f"""
                ---
                **Summary:**  
                • Total models tried: {len(result["models_tried"])}  
                • Final model used: {result.get("model_used", "Unknown")}  
                • Total time: {time_display}
                """)
        
        # ─────────────────────────────────────
        # ANSWER
        # ─────────────────────────────────────
        st.markdown("---")
        st.markdown("### 💬 Answer")
        st.markdown(result["answer"])
        
        # Show model used (if query was fast)
        if total_time <= 20:
            st.caption(f"🤖 Model: {result.get('model_used', 'Unknown')}")
        
        # ─────────────────────────────────────
        # SQL QUERY
        # ─────────────────────────────────────
        with st.expander("🔍 View SQL Query"):
            st.code(result["query"], language="sql")
            # Show query explanation
        if result.get("explanation"):
            with st.expander("📖 How This Query Works", expanded=False):
                st.markdown(result["explanation"])
        
        # ─────────────────────────────────────
        # DATA TABLE
        # ─────────────────────────────────────
        if result["results"]:
            with st.expander(f"📊 View Data ({result['row_count']} rows)"):
                df = pd.DataFrame(result["results"])
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Download CSV",
                    data=csv,
                    file_name=f"query_{int(time.time())}.csv",
                    mime="text/csv"
                )
    
    else:
        # Save failed query to history too
        add_to_history(question, result, total_time)
        # ─────────────────────────────────────
        # ERROR DISPLAY
        # ─────────────────────────────────────
        time_display = format_time(total_time)
        st.error(f"❌ Query failed after {time_display}")
        st.markdown(f"**Error:** {result.get('error', 'Unknown error')}")
        
        # Show model journey on error too
        if result.get("models_tried"):
            with st.expander("📋 Model Journey"):
                for model_info in result["models_tried"]:
                    st.markdown(f"• {model_info['status']} {model_info['model']}")
        
        st.info("💡 Try rephrasing or simplifying your question")

elif ask_button and not question:
    st.warning("⚠️ Please enter a question")

# ═══════════════════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════════════════

st.markdown("---")
st.caption("🧠 NexusIQ AI | Intelligent multi-model fallback with quota tracking")