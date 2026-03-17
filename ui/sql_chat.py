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
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agents.sql_agent import SQLAgent

# ═══════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════

QUERY_TIPS = [
    "💡 **Tip:** Ask 'top 5' or 'top 10' for ranked results",
    "🎯 **Tip:** Include time periods like 'last month' or 'Q3 2024'",
    "📊 **Tip:** Try 'compare X and Y' for side-by-side analysis",
    "⚡ **Tip:** Simple queries (SUM, COUNT) run in seconds",
    "🔒 **Tip:** All queries are read-only — your data is safe",
    "🧠 **Tip:** Complex queries use our smartest AI model",
    "📈 **Tip:** You can download results as CSV",
    "🌐 **Tip:** We analyze 100,000 transactions across 5 regions",
    "💰 **Tip:** Ask about revenue, products, regions, or customers",
    "🔍 **Tip:** Be specific: 'West region' vs 'best region'",
    "⏱️ **Tip:** First query may be slower (model warm-up)",
    "🔄 **Tip:** We auto-switch models if one hits quota limits",
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


def get_random_tip(exclude: str = None) -> str:
    """Get a random tip, excluding the current one"""
    available_tips = [t for t in QUERY_TIPS if t != exclude]
    return random.choice(available_tips)


# ═══════════════════════════════════════════════════════════
#  INITIALIZE AGENT
# ═══════════════════════════════════════════════════════════

@st.cache_resource
def get_agent():
    return SQLAgent(mode="development")

agent = get_agent()

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

# ═══════════════════════════════════════════════════════════
#  MAIN CHAT INTERFACE
# ═══════════════════════════════════════════════════════════

question = st.text_input(
    "💬 Ask a question:",
    placeholder="e.g., What was total revenue last month?",
    key="user_question"
)

col1, col2 = st.columns([1, 5])
with col1:
    ask_button = st.button("🔍 Ask", type="primary", use_container_width=True)

# ═══════════════════════════════════════════════════════════
#  QUERY PROCESSING
# ═══════════════════════════════════════════════════════════

if ask_button and question:
    
    start_time = time.time()
    result = None
    
    # Create UI elements
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        tip_box = st.empty()
        
        # Initial tip
        current_tip = get_random_tip()
        tip_box.info(current_tip)
        
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
        last_tip_time = time.time()
        tip_interval = 6  # Change tip every 6 seconds
        
        # Execute query with tip rotation
        query_start = time.time()
        
        # Create a flag for completion
        query_done = False
        
        while not query_done:
            # Update tip independently every 6 seconds
            if time.time() - last_tip_time > tip_interval:
                current_tip = get_random_tip(current_tip)
                tip_box.info(current_tip)
                last_tip_time = time.time()
            
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