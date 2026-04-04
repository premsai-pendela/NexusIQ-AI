"""
NexusIQ AI — SQL Agent Chat Interface
With User-Controlled Visualizations
"""

import streamlit as st
import pandas as pd
import time
import random
import sys
import io
from datetime import datetime
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from config.settings import settings

sys.path.append(str(Path(__file__).parent.parent))

from agents.sql_agent import SQLAgent
from utils.validators import VALID_REGIONS, VALID_CATEGORIES


def run_sql_chat():
    """Main function for SQL Chat interface"""

    # ═══════════════════════════════════════════════════════
    #  CONFIGURATION
    # ═══════════════════════════════════════════════════════

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

    CHART_TYPES = {
        "bar": {"icon": "📊", "name": "Bar Chart", "description": "Compare categories"},
        "bar_horizontal": {"icon": "📊", "name": "Horizontal Bar", "description": "Ranking/Top N"},
        "line": {"icon": "📈", "name": "Line Chart", "description": "Trends over time"},
        "pie": {"icon": "🥧", "name": "Pie Chart", "description": "Show proportions"},
        "scatter": {"icon": "🔵", "name": "Scatter Plot", "description": "Find patterns"},
        "area": {"icon": "📉", "name": "Area Chart", "description": "Cumulative trends"},
    }

    # ═══════════════════════════════════════════════════════
    #  HELPER FUNCTIONS
    # ═══════════════════════════════════════════════════════

    def format_time(seconds: float) -> str:
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

    def time_ago(timestamp: datetime) -> str:
        diff = datetime.now() - timestamp
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        else:
            return f"{int(seconds // 86400)}d ago"

    def can_visualize(df) -> dict:
        """
        Check if dataframe can be visualized and return available options.
        Returns dict with 'can_chart', 'reason', 'numeric_cols', 'text_cols', 'date_cols'
        """
        if df is None or df.empty:
            return {
                "can_chart": False,
                "reason": "No data to visualize",
                "numeric_cols": [],
                "text_cols": [],
                "date_cols": []
            }

        if len(df) < 1:
            return {
                "can_chart": False,
                "reason": "Need at least 1 row of data",
                "numeric_cols": [],
                "text_cols": [],
                "date_cols": []
            }

        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        text_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        date_cols = [
            col for col in df.columns
            if 'date' in col.lower() or 'month' in col.lower() 
            or 'year' in col.lower() or 'time' in col.lower()
        ]

        if not numeric_cols:
            return {
                "can_chart": False,
                "reason": "No numeric columns to plot",
                "numeric_cols": [],
                "text_cols": text_cols,
                "date_cols": date_cols
            }

        return {
            "can_chart": True,
            "reason": "Ready to visualize!",
            "numeric_cols": numeric_cols,
            "text_cols": text_cols,
            "date_cols": date_cols,
            "row_count": len(df)
        }

    def generate_chart(df, chart_type: str, x_col: str, y_col: str, color_col: str = None) -> go.Figure:
        """Generate a Plotly chart based on user selections."""
        
        try:
            title = f"{y_col} by {x_col}"
            
            if chart_type == "bar":
                fig = px.bar(
                    df, x=x_col, y=y_col,
                    color=color_col if color_col and color_col != "None" else None,
                    title=f"📊 {title}",
                    text_auto=True
                )
                
            elif chart_type == "bar_horizontal":
                fig = px.bar(
                    df, x=y_col, y=x_col,
                    color=color_col if color_col and color_col != "None" else None,
                    title=f"📊 {title}",
                    orientation='h',
                    text_auto=True
                )
                fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                
            elif chart_type == "line":
                fig = px.line(
                    df, x=x_col, y=y_col,
                    color=color_col if color_col and color_col != "None" else None,
                    title=f"📈 {title}",
                    markers=True
                )
                
            elif chart_type == "pie":
                fig = px.pie(
                    df, names=x_col, values=y_col,
                    title=f"🥧 {title}",
                    hole=0.4
                )
                
            elif chart_type == "scatter":
                fig = px.scatter(
                    df, x=x_col, y=y_col,
                    color=color_col if color_col and color_col != "None" else None,
                    title=f"🔵 {title}",
                    size=y_col if len(df) > 1 else None
                )
                
            elif chart_type == "area":
                fig = px.area(
                    df, x=x_col, y=y_col,
                    color=color_col if color_col and color_col != "None" else None,
                    title=f"📉 {title}"
                )
            
            else:
                # Default to bar
                fig = px.bar(df, x=x_col, y=y_col, title=title)

            # Common styling
            fig.update_layout(
                template="plotly_white",
                height=400,
                showlegend=bool(color_col and color_col != "None"),
                margin=dict(t=50, b=50, l=50, r=50)
            )
            
            return fig
            
        except Exception as e:
            # Return error figure
            fig = go.Figure()
            fig.add_annotation(
                text=f"⚠️ Chart Error: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="red")
            )
            fig.update_layout(height=200)
            return fig

    def build_validation_content(question: str, validation_issues: list, error_msg: str) -> str:
        """Convert validation_issues list into a rich Markdown string."""
        parts = ["⚠️ **Question needs clarification**\n"]

        for issue in validation_issues:
            issue_type = issue.get("type", "")
            details = issue.get("details", {})

            if issue_type == "typo":
                typo_word = details.get("typo", "")
                suggestion = details.get("suggestion", "")
                corrected = question.replace(typo_word, suggestion)
                parts.append(
                    f"**🔤 Typo detected:** `{typo_word}` → Did you mean **`{suggestion}`**?\n\n"
                    f"✅ **Try:** *{corrected}*"
                )

            elif issue_type == "date_range":
                parts.append(
                    f"**📅 Date issue:** {details.get('issue', 'Invalid date range')}\n\n"
                    f"📆 **Available range:** {details.get('data_range', 'Unknown')}"
                )

            elif issue_type == "ambiguous":
                options_text = "\n".join(
                    [f"  - ✅ *{question} by {opt.split('(')[0].strip().lower().replace('by ', '')}*"
                     for opt in details.get("options", [])]
                )
                parts.append(
                    f"**🤔 Ambiguous question:** {details.get('question', question)}\n\n"
                    f"Which metric did you mean?\n{options_text}"
                )

            elif issue_type == "invalid_region":
                valid = ", ".join(details.get("valid_regions", VALID_REGIONS))
                parts.append(
                    f"**🌐 Invalid region:** `{details.get('region', '')}`\n\n"
                    f"✅ **Valid regions:** {valid}"
                )

            elif issue_type == "invalid_category":
                valid = ", ".join(details.get("valid_categories", VALID_CATEGORIES))
                parts.append(
                    f"**🏷️ Invalid category:** `{details.get('category', '')}`\n\n"
                    f"✅ **Valid categories:** {valid}"
                )

            else:
                parts.append(f"**ℹ️ {issue_type}:** {details}")

        return "\n\n---\n\n".join(parts)

    # ─────────────────────────────────────────────────────
    #  RENDER CHART BUILDER UI
    # ─────────────────────────────────────────────────────

    def render_chart_builder(msg_id: str, df: pd.DataFrame):
        """Render the chart builder interface for a message."""
        
        viz_info = can_visualize(df)
        
        if not viz_info["can_chart"]:
            st.warning(f"📊 Cannot visualize: {viz_info['reason']}")
            return None

        st.markdown("**🎨 Build Your Chart**")
        
        # Chart type selection with icons
        chart_cols = st.columns(6)
        selected_chart = st.session_state.get(f"chart_type_{msg_id}", "bar")
        
        for i, (chart_key, chart_info) in enumerate(CHART_TYPES.items()):
            with chart_cols[i]:
                is_selected = selected_chart == chart_key
                btn_type = "primary" if is_selected else "secondary"
                if st.button(
                    f"{chart_info['icon']}",
                    key=f"chart_btn_{msg_id}_{chart_key}",
                    help=f"{chart_info['name']}: {chart_info['description']}",
                    type=btn_type,
                    use_container_width=True
                ):
                    st.session_state[f"chart_type_{msg_id}"] = chart_key
                    st.rerun()
        
        # Show selected chart type name
        st.caption(f"Selected: **{CHART_TYPES[selected_chart]['name']}** - {CHART_TYPES[selected_chart]['description']}")
        
        st.markdown("---")
        
        # Column selection
        all_cols = df.columns.tolist()
        numeric_cols = viz_info["numeric_cols"]
        text_cols = viz_info["text_cols"]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # X-axis: prefer text/category columns
            x_options = text_cols + numeric_cols if text_cols else all_cols
            x_col = st.selectbox(
                "📍 X-Axis (Categories)",
                options=x_options,
                key=f"x_col_{msg_id}",
                help="Usually categories, dates, or labels"
            )
        
        with col2:
            # Y-axis: prefer numeric columns
            y_options = numeric_cols if numeric_cols else all_cols
            y_col = st.selectbox(
                "📊 Y-Axis (Values)",
                options=y_options,
                key=f"y_col_{msg_id}",
                help="Usually numbers to measure"
            )
        
        with col3:
            # Color by (optional)
            color_options = ["None"] + text_cols
            color_col = st.selectbox(
                "🎨 Color By (Optional)",
                options=color_options,
                key=f"color_col_{msg_id}",
                help="Add color grouping"
            )
        
        # Generate button
        if st.button("✨ Generate Chart", key=f"gen_btn_{msg_id}", type="primary", use_container_width=True):
            chart_type = st.session_state.get(f"chart_type_{msg_id}", "bar")
            color = color_col if color_col != "None" else None
            
            fig = generate_chart(df, chart_type, x_col, y_col, color)
            
            # Save to session state
            st.session_state[f"generated_chart_{msg_id}"] = fig
            st.rerun()
        
        # Display generated chart if exists
        if f"generated_chart_{msg_id}" in st.session_state:
            fig = st.session_state[f"generated_chart_{msg_id}"]
            st.plotly_chart(fig, use_container_width=True)
            
            # Download chart button
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                # Download as HTML
                html_buffer = io.StringIO()
                fig.write_html(html_buffer)
                st.download_button(
                    "📥 Download Chart (HTML)",
                    data=html_buffer.getvalue(),
                    file_name=f"chart_{msg_id}.html",
                    mime="text/html",
                    key=f"dl_html_{msg_id}",
                    use_container_width=True
                )
            with dl_col2:
                if st.button("🗑️ Clear Chart", key=f"clear_chart_{msg_id}", use_container_width=True):
                    del st.session_state[f"generated_chart_{msg_id}"]
                    st.rerun()
        
        return None

    # ─────────────────────────────────────────────────────
    #  RENDER ASSISTANT MESSAGE
    # ─────────────────────────────────────────────────────

    def render_assistant_message(msg: dict, is_latest: bool = False):
        """Render a single assistant chat message with all its components."""

        # Main content
        st.markdown(msg["content"])

        # SQL Query expander
        if msg.get("query"):
            with st.expander("🔍 View SQL Query"):
                st.code(msg["query"], language="sql")

        # Explanation expander
        if msg.get("explanation"):
            with st.expander("📖 How This Query Works"):
                st.markdown(msg["explanation"])

        # Data table + exports + CHART BUILDER
        if msg.get("results"):
            msg_id = msg.get("id", "0")
            df = pd.DataFrame(msg["results"])
            
            # Data expander
            with st.expander(f"📊 View Data ({msg.get('row_count', len(df))} rows)"):
                st.dataframe(df, use_container_width=True)

                st.markdown("**📥 Export Data:**")
                e1, e2, e3, e4 = st.columns(4)

                with e1:
                    st.download_button(
                        "📄 CSV", data=df.to_csv(index=False),
                        file_name=f"query_{msg_id}.csv", mime="text/csv",
                        use_container_width=True, key=f"csv_{msg_id}"
                    )

                with e2:
                    st.download_button(
                        "📋 JSON",
                        data=df.to_json(orient="records", indent=2),
                        file_name=f"query_{msg_id}.json",
                        mime="application/json",
                        use_container_width=True, key=f"json_{msg_id}"
                    )

                with e3:
                    from openpyxl.utils import get_column_letter
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Results')
                        ws = writer.sheets['Results']
                        for ci, col_name in enumerate(df.columns, 1):
                            ml = max(
                                len(str(col_name)),
                                max((len(str(v)) for v in df[col_name]), default=0)
                            )
                            ws.column_dimensions[get_column_letter(ci)].width = min(ml + 3, 50)
                    st.download_button(
                        "📊 Excel", data=buf.getvalue(),
                        file_name=f"query_{msg_id}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, key=f"excel_{msg_id}"
                    )

                with e4:
                    st.download_button(
                        "📝 MD", data=df.to_markdown(index=False),
                        file_name=f"query_{msg_id}.md", mime="text/markdown",
                        use_container_width=True, key=f"md_{msg_id}"
                    )
            
            # ═══════════════════════════════════════════════
            #  📊 VISUALIZATION SECTION — User Controlled!
            # ═══════════════════════════════════════════════
            
            viz_info = can_visualize(df)
            
            if viz_info["can_chart"]:
                with st.expander("📊 Visualize This Data?", expanded=is_latest):
                    render_chart_builder(msg_id, df)
            else:
                st.caption(f"📊 {viz_info['reason']}")

        # Suggested corrections — clickable buttons
        if msg.get("suggestions"):
            st.markdown("---")
            st.markdown("**💡 Did you mean:**")
            for i, suggestion in enumerate(msg["suggestions"]):
                sug_key = f"sug_{msg.get('id', '0')}_{i}"
                if st.button(f"✅ {suggestion}", key=sug_key, use_container_width=True):
                    st.session_state.pending_suggestion = suggestion
                    st.rerun()

        # Timing info
        if msg.get("time"):
            model_info = f" • 🤖 {msg['model']}" if msg.get("model") else ""
            st.caption(f"⏱️ {format_time(msg['time'])}{model_info}")

    # ═══════════════════════════════════════════════════════
    #  INITIALIZE
    # ═══════════════════════════════════════════════════════

    @st.cache_resource
    def get_agent():
        return SQLAgent(mode="development")

    agent = get_agent()

    # ═══════════════════════════════════════════════════════
    #  SESSION STATE
    # ═══════════════════════════════════════════════════════

    if "query_history" not in st.session_state:
        st.session_state.query_history = []
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "pending_suggestion" not in st.session_state:
        st.session_state.pending_suggestion = None

    def add_to_history(question, result, execution_time):
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
        st.session_state.query_history = st.session_state.query_history[:10]

    # ═══════════════════════════════════════════════════════
    #  PAGE LAYOUT
    # ═══════════════════════════════════════════════════════

    st.title("🗄️ SQL Agent — Database Query Interface")
    st.markdown("*Ask questions about your sales data in plain English*")

    # ═══════════════════════════════════════════════════════
    #  SIDEBAR
    # ═══════════════════════════════════════════════════════

    with st.sidebar:
        st.header("📊 Database Schema")

        with st.expander("📋 sales_transactions"):
            st.code(
                "• transaction_date\n• region (5 regions)\n• store_id\n"
                "• product_category\n• product_name\n• quantity, unit_price\n"
                "• total_amount\n• customer_id\n• payment_method"
            )

        with st.expander("👥 customers"):
            st.code(
                "• customer_id\n• name, email, region\n"
                "• signup_date\n• total_purchases"
            )

        st.markdown("---")
        st.subheader("💡 Example Questions")
        
        example_questions = [
            "What is the total revenue?",
            "Show sales by region",
            "Top 5 products by revenue",
            "Monthly sales trend",
            "Compare payment methods"
        ]
        
        for eq in example_questions:
            if st.button(f"💬 {eq}", key=f"ex_{eq}", use_container_width=True):
                st.session_state.pending_suggestion = eq
                st.rerun()

        st.markdown("---")
        st.subheader("📊 Model Status")
        # ✨ NEW: Show Gemini Pro toggle status
        if settings.use_gemini_pro:
            st.warning("🟡 Gemini Pro: **ENABLED** (may exhaust quickly)")
        else:
            st.info("🔵 Gemini Pro: **DISABLED** (free tier protection)")
        
        quota_status = agent.get_quota_status()
        if quota_status:
            for model, status in quota_status.items():
                # ✨ NEW: Skip showing Pro if disabled
                if "pro" in model.lower() and not settings.use_gemini_pro:
                    continue
                st.caption(f"{status['status']} {model.split('-')[0]}")
        else:
            st.caption("🟢 All models available")

        # ✨ NEW: Optional - Allow toggling Pro at runtime (advanced users only)
        if st.checkbox("⚙️ Advanced: Enable Gemini Pro", value=settings.use_gemini_pro, key="toggle_pro"):
            st.warning("⚠️ Enabling Pro may exhaust your free tier quota in 1-2 queries!")
            if st.button("🔓 Unlock Gemini Pro (I understand)", use_container_width=True):
                settings.use_gemini_pro = True
                st.success("✅ Gemini Pro enabled for this session")
                st.rerun()

        if st.button("🔄 Reset Quota Tracking"):
            agent.reset_quota_tracking()
            st.rerun()

        st.markdown("---")
        st.subheader("📜 Query History")

        if st.session_state.query_history:
            for i, item in enumerate(st.session_state.query_history[:5]):
                icon = "✅" if item["success"] else "❌"
                short = item["question"][:25] + ("..." if len(item["question"]) > 25 else "")
                if st.button(f"{icon} {short}", key=f"hist_{i}", use_container_width=True):
                    st.session_state.pending_suggestion = item["question"]
                    st.rerun()
                st.caption(f"⏱️ {item['time']:.1f}s • {time_ago(item['timestamp'])}")

            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state.query_history = []
                st.session_state.chat_messages = []
                # Clear all chart-related session state
                keys_to_clear = [k for k in st.session_state.keys() 
                                if k.startswith(('chart_', 'generated_chart_', 'x_col_', 'y_col_', 'color_col_'))]
                for k in keys_to_clear:
                    del st.session_state[k]
                st.rerun()
        else:
            st.caption("No queries yet")

    # ═══════════════════════════════════════════════════════
    #  REPLAY CHAT HISTORY
    # ═══════════════════════════════════════════════════════

    total_messages = len(st.session_state.chat_messages)
    
    for idx, msg in enumerate(st.session_state.chat_messages):
        is_latest = (idx == total_messages - 1) and msg["role"] == "assistant"
        
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🧠"):
                render_assistant_message(msg, is_latest=is_latest)

    # ═══════════════════════════════════════════════════════
    #  HANDLE SUGGESTION CLICKS / CHAT INPUT
    # ═══════════════════════════════════════════════════════

    if st.session_state.pending_suggestion:
        question = st.session_state.pending_suggestion
        st.session_state.pending_suggestion = None
    else:
        question = st.chat_input("💬 Ask a question about your data...")

    # ═══════════════════════════════════════════════════════
    #  PROCESS NEW QUESTION
    # ═══════════════════════════════════════════════════════

    if question:
        # Add user message
        st.session_state.chat_messages.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):
            st.markdown(question)

        # Process query
        with st.chat_message("assistant", avatar="🧠"):
            status = st.empty()
            insight_box = st.empty()

            insight_box.info(random.choice(INSIGHTS))

            status.markdown("🔍 Analyzing question...")
            time.sleep(0.3)

            status.markdown("🧠 Detecting complexity...")
            time.sleep(0.3)

            status.markdown("⚡ Generating SQL query...")

            start_time = time.time()
            result = agent.ask(question)
            total_time = time.time() - start_time

            status.empty()
            insight_box.empty()

            msg_id = str(int(time.time() * 1000))

            # ─────────────────────────────────────
            #  SUCCESS
            # ─────────────────────────────────────
            if result["success"]:
                st.markdown(result["answer"])

                with st.expander("🔍 View SQL Query"):
                    st.code(result["query"], language="sql")

                if result.get("explanation"):
                    with st.expander("📖 How This Query Works"):
                        st.markdown(result["explanation"])

                if result.get("results"):
                    df = pd.DataFrame(result["results"])
                    
                    with st.expander(f"📊 View Data ({result['row_count']} rows)"):
                        st.dataframe(df, use_container_width=True)
                    
                    # Check if visualization is possible
                    viz_info = can_visualize(df)
                    
                    if viz_info["can_chart"]:
                        with st.expander("📊 Visualize This Data?", expanded=True):
                            render_chart_builder(msg_id, df)
                    else:
                        st.info(f"📊 {viz_info['reason']}")

                st.caption(f"⏱️ {format_time(total_time)} • 🤖 {result.get('model_used', 'Unknown')}")

                # Save to chat history
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "query": result.get("query", ""),
                    "explanation": result.get("explanation", ""),
                    "results": result.get("results", []),
                    "row_count": result.get("row_count", 0),
                    "time": total_time,
                    "model": result.get("model_used", "Unknown"),
                    "id": msg_id
                })

                add_to_history(question, result, total_time)

            # ─────────────────────────────────────
            #  FAILURE — WITH VALIDATION ISSUES
            # ─────────────────────────────────────
            elif result.get("validation_issues"):
                validation_issues = result["validation_issues"]

                content = build_validation_content(
                    question, validation_issues, result.get("error", "")
                )

                st.markdown(content)

                # Build clickable suggestions
                suggestions = []
                for issue in validation_issues:
                    issue_type = issue.get("type", "")
                    details = issue.get("details", {})

                    if issue_type == "typo":
                        corrected = question.replace(
                            details.get("typo", ""),
                            details.get("suggestion", "")
                        )
                        suggestions.append(corrected)

                    elif issue_type == "ambiguous":
                        for opt in details.get("options", []):
                            metric = opt.split("(")[0].strip().lower().replace("by ", "")
                            suggestions.append(f"{question} by {metric}")

                if suggestions:
                    st.markdown("---")
                    st.markdown("**💡 Click to try:**")
                    for i, sug in enumerate(suggestions):
                        if st.button(f"✅ {sug}", key=f"sug_live_{msg_id}_{i}", use_container_width=True):
                            st.session_state.pending_suggestion = sug
                            st.rerun()

                st.caption(f"⏱️ {format_time(total_time)}")

                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": content,
                    "suggestions": suggestions,
                    "time": total_time,
                    "id": msg_id
                })

                add_to_history(question, result, total_time)

            # ─────────────────────────────────────
            #  FAILURE — GENERIC ERROR
            # ─────────────────────────────────────
            else:
                error_content = f"❌ **Error:** {result.get('error', 'Unknown error occurred')}"
                
                error_msg = result.get("error", "").lower()
                if "region" in error_msg or "region" in question.lower():
                    error_content += f"\n\n🌐 **Valid regions:** {', '.join(VALID_REGIONS)}"
                if "category" in error_msg or "category" in question.lower():
                    error_content += f"\n\n🏷️ **Valid categories:** {', '.join(VALID_CATEGORIES)}"

                st.error(error_content)
                st.caption(f"⏱️ {format_time(total_time)}")

                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": error_content,
                    "time": total_time,
                    "id": msg_id
                })

                add_to_history(question, result, total_time)

        st.rerun()

    # ─────────────────────────────────────────────────────
    #  EMPTY STATE / WELCOME
    # ─────────────────────────────────────────────────────
    if not st.session_state.chat_messages:
        st.markdown("---")
        
        st.markdown(
            """
            <div style='text-align:center; padding:40px;'>
                <h2>👋 Welcome to NexusIQ SQL Agent</h2>
                <p style='color:#888; font-size:1.1em;'>
                    Ask questions about your sales database in plain English.<br>
                    I'll translate them to SQL and show you the results!
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown("### 🚀 Quick Start")
        
        qs1, qs2, qs3 = st.columns(3)
        
        with qs1:
            st.markdown("**📈 Analytics**")
            if st.button("💰 Total revenue?", use_container_width=True, key="qs1"):
                st.session_state.pending_suggestion = "What is the total revenue?"
                st.rerun()
            if st.button("📅 Monthly trend?", use_container_width=True, key="qs2"):
                st.session_state.pending_suggestion = "Show monthly sales trend"
                st.rerun()
        
        with qs2:
            st.markdown("**🏆 Rankings**")
            if st.button("🥇 Top 5 products?", use_container_width=True, key="qs3"):
                st.session_state.pending_suggestion = "What are the top 5 products by revenue?"
                st.rerun()
            if st.button("🌟 Best region?", use_container_width=True, key="qs4"):
                st.session_state.pending_suggestion = "Which region has the highest sales?"
                st.rerun()
        
        with qs3:
            st.markdown("**📊 Comparisons**")
            if st.button("🌐 By region?", use_container_width=True, key="qs5"):
                st.session_state.pending_suggestion = "Compare sales by region"
                st.rerun()
            if st.button("💳 By payment?", use_container_width=True, key="qs6"):
                st.session_state.pending_suggestion = "Sales breakdown by payment method"
                st.rerun()
        
        st.markdown("---")
        st.info("💡 **Tip:** After getting results, you can create custom visualizations using the chart builder!")