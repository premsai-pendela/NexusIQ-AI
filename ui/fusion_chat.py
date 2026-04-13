"""
NexusIQ AI — Fusion Agent Chat Interface
Multi-source intelligence combining SQL + RAG + Web with cross-validation

Features:
- Smart routing display (SQL/RAG/Web/Combined)
- Multi-source result sections (expandable)
- Cross-validation confidence badges
- Query history with full fusion results
- Multi-format export (CSV/JSON/Excel/MD)
- Chart builder for SQL data
- Source filters + category selector
- All existing SQL chat features preserved
"""

import streamlit as st
import pandas as pd
import time
import random
import sys
import json
import io
import threading
from datetime import datetime
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go

sys.path.append(str(Path(__file__).parent.parent))

from agents.fusion_agent import get_fusion_agent
from config.settings import settings
from utils.validators import VALID_REGIONS, VALID_CATEGORIES

# ═══════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════

INSIGHTS = [
    "💡 **Did You Know?** Fusion Agent combines 3 data sources for validated answers",
    "🧠 **Did You Know?** Cross-validation checks SQL numbers against PDF reports",
    "⚡ **Did You Know?** Simple queries complete in under 5 seconds",
    "🔄 **Did You Know?** We auto-switch models if one hits quota limits",
    "🔒 **Did You Know?** All SQL queries are read-only — your data stays safe",
    "📊 **Did You Know?** RAG Agent searches 23 business documents",
    "🎯 **Did You Know?** Web Agent scrapes live competitor pricing",
    "🚀 **Did You Know?** Circuit breaker skips failed models instantly",
    "💰 **Did You Know?** Database tracks $139M+ in total revenue",
    "🌐 **Did You Know?** We support 5 regions: East, West, North, South, Central",
    "🛒 **Did You Know?** Web Agent supports 5 categories: Electronics, Home, Sports, Food, Clothing",
    "⏱️ **Did You Know?** First query may be slower due to model warm-up",
    "🔍 **Did You Know?** Fusion Agent detects comparison queries and uses multi-step reasoning",
    "📄 **Did You Know?** RAG Agent uses hybrid BM25+Vector search for better accuracy",
]

CHART_TYPES = {
    "bar": {"icon": "📊", "name": "Bar Chart", "description": "Compare categories"},
    "bar_horizontal": {"icon": "📊", "name": "Horizontal Bar", "description": "Ranking/Top N"},
    "line": {"icon": "📈", "name": "Line Chart", "description": "Trends over time"},
    "pie": {"icon": "🥧", "name": "Pie Chart", "description": "Show proportions"},
    "scatter": {"icon": "🔵", "name": "Scatter Plot", "description": "Find patterns"},
    "area": {"icon": "📉", "name": "Area Chart", "description": "Cumulative trends"},
}

SOURCE_ICONS = {
    "sql": "🗄️",
    "rag": "📄",
    "web": "🌐",
    "fusion": "🔗"
}

# ═══════════════════════════════════════════════════════
#  HELPER FUNCTIONS (from sql_chat.py - kept as-is)
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
    """Check if dataframe can be visualized"""
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
            fig = px.bar(df, x=x_col, y=y_col, title=title)

        fig.update_layout(
            template="plotly_white",
            height=400,
            showlegend=bool(color_col and color_col != "None"),
            margin=dict(t=50, b=50, l=50, r=50)
        )
        
        return fig
        
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(
            text=f"⚠️ Chart Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="red")
        )
        fig.update_layout(height=200)
        return fig

# ─────────────────────────────────────────────────────
#  CHART BUILDER UI (from sql_chat.py - kept as-is)
# ─────────────────────────────────────────────────────

def render_chart_builder(msg_id: str, df: pd.DataFrame):
    """Render the chart builder interface for a message."""
    
    viz_info = can_visualize(df)
    
    if not viz_info["can_chart"]:
        st.warning(f"📊 Cannot visualize: {viz_info['reason']}")
        return None

    st.markdown("**🎨 Build Your Chart**")
    
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
    
    st.caption(f"Selected: **{CHART_TYPES[selected_chart]['name']}** - {CHART_TYPES[selected_chart]['description']}")
    
    st.markdown("---")
    
    all_cols = df.columns.tolist()
    numeric_cols = viz_info["numeric_cols"]
    text_cols = viz_info["text_cols"]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        x_options = text_cols + numeric_cols if text_cols else all_cols
        x_col = st.selectbox(
            "📍 X-Axis (Categories)",
            options=x_options,
            key=f"x_col_{msg_id}",
            help="Usually categories, dates, or labels"
        )
    
    with col2:
        y_options = numeric_cols if numeric_cols else all_cols
        y_col = st.selectbox(
            "📊 Y-Axis (Values)",
            options=y_options,
            key=f"y_col_{msg_id}",
            help="Usually numbers to measure"
        )
    
    with col3:
        color_options = ["None"] + text_cols
        color_col = st.selectbox(
            "🎨 Color By (Optional)",
            options=color_options,
            key=f"color_col_{msg_id}",
            help="Add color grouping"
        )
    
    if st.button("✨ Generate Chart", key=f"gen_btn_{msg_id}", type="primary", use_container_width=True):
        chart_type = st.session_state.get(f"chart_type_{msg_id}", "bar")
        color = color_col if color_col != "None" else None
        
        fig = generate_chart(df, chart_type, x_col, y_col, color)
        st.session_state[f"generated_chart_{msg_id}"] = fig
        st.rerun()
    
    if f"generated_chart_{msg_id}" in st.session_state:
        fig = st.session_state[f"generated_chart_{msg_id}"]
        st.plotly_chart(fig, use_container_width=True)
        
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
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

# ═══════════════════════════════════════════════════════
#  ✨ NEW: FUSION-SPECIFIC UI COMPONENTS
# ═══════════════════════════════════════════════════════

def render_routing_badge(source_type: str):
    """
    Display which source(s) the Fusion Agent used
    
    Args:
        source_type: "sql_only" | "rag_only" | "web_only" | "sql_rag" | "comparison" etc.
    """
    
    route_config = {
        "no_data": {"icon": "🚫", "label": "No Data Available", "color": "#F44336"},
        "sql_only": {"icon": "🗄️", "label": "SQL Database", "color": "#4CAF50"},
        "rag_only": {"icon": "📄", "label": "PDF Documents", "color": "#2196F3"},
        "web_only": {"icon": "🌐", "label": "Web Scraping", "color": "#FF9800"},
        "comparison": {"icon": "🧠", "label": "RAG Comparison Mode", "color": "#9C27B0"},
        "sql_rag": {"icon": "🔗", "label": "SQL + RAG Fusion", "color": "#00BCD4"},
        "sql_web": {"icon": "🔗", "label": "SQL + Web Fusion", "color": "#FF5722"},
        "rag_web": {"icon": "🔗", "label": "RAG + Web Fusion", "color": "#795548"},
        "all": {"icon": "🌟", "label": "All Sources Fusion", "color": "#E91E63"},
    }
    
    config = route_config.get(source_type, {"icon": "❓", "label": source_type, "color": "#9E9E9E"})
    
    st.markdown(
        f"""
        <div style='
            background: linear-gradient(135deg, {config['color']}22 0%, {config['color']}11 100%);
            border-left: 4px solid {config['color']};
            padding: 12px 16px;
            border-radius: 8px;
            margin: 10px 0;
        '>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='font-size: 24px;'>{config['icon']}</span>
                <div>
                    <div style='font-weight: 600; color: #333; font-size: 14px;'>
                        ROUTING DECISION
                    </div>
                    <div style='color: {config['color']}; font-weight: 700; font-size: 16px; margin-top: 2px;'>
                        {config['label']}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_confidence_badge(validation: dict):
    """
    Display cross-validation confidence badge
    
    Args:
        validation: dict with 'confidence', 'confidence_reason', 'matches', 'discrepancies'
    """
    
    if not validation:
        return
    
    confidence = validation.get('confidence', 'UNKNOWN')
    reason = validation.get('confidence_reason', '')
    matches = validation.get('matches', [])
    discrepancies = validation.get('discrepancies', [])
    
    # Confidence colors
    confidence_config = {
        "HIGH": {"emoji": "✅", "color": "#4CAF50", "bg": "#E8F5E9"},
        "MEDIUM": {"emoji": "🟡", "color": "#FF9800", "bg": "#FFF3E0"},
        "LOW": {"emoji": "🔴", "color": "#F44336", "bg": "#FFEBEE"},
    }
    
    config = confidence_config.get(confidence, {"emoji": "⚪", "color": "#9E9E9E", "bg": "#F5F5F5"})
    
    st.markdown(
        f"""
        <div style='
            background: {config['bg']};
            border: 2px solid {config['color']};
            padding: 12px 16px;
            border-radius: 8px;
            margin: 10px 0;
        '>
            <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 8px;'>
                <span style='font-size: 24px;'>{config['emoji']}</span>
                <div>
                    <div style='font-weight: 600; color: #666; font-size: 12px;'>
                        CROSS-VALIDATION CONFIDENCE
                    </div>
                    <div style='color: {config['color']}; font-weight: 700; font-size: 18px;'>
                        {confidence}
                    </div>
                </div>
            </div>
            <div style='color: #555; font-size: 14px; margin-top: 8px;'>
                {reason}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Show match/discrepancy details
    if matches or discrepancies:
        with st.expander("🔍 Validation Details", expanded=False):
            if matches:
                st.markdown(f"**✅ Validated Numbers ({len(matches)} matches):**")
                for match in matches[:5]:  # Show top 5
                    sql_val = match.get('sql_value', 'N/A')
                    rag_val = match.get('rag_value', 'N/A')
                    pct_diff = match.get('pct_difference', 0)
                    st.markdown(f"- **{match.get('label', 'value')}**: SQL={sql_val:,.0f} ≈ RAG={rag_val:,.0f} (Δ{pct_diff:.2f}%)")
            
            if discrepancies:
                st.markdown(f"**⚠️ Discrepancies ({len(discrepancies)}):**")
                for disc in discrepancies[:3]:
                    st.markdown(f"- **{disc.get('label', 'value')}**: SQL={disc.get('sql_value', 'N/A')} vs RAG={disc.get('rag_value', 'N/A')}")

def render_sql_section(msg_id: str, sql_result: dict, is_latest: bool = False):
    """
    Render SQL results section (query + table + explanation + chart builder)
    
    Args:
        msg_id: Unique message ID
        sql_result: SQL agent output dict
        is_latest: Whether this is the latest message (auto-expand charts)
    """
    
    if not sql_result or not sql_result.get('success'):
        st.warning("❌ SQL query failed or returned no results")
        if sql_result and sql_result.get('error'):
            st.error(f"Error: {sql_result['error']}")
        return
    
    with st.expander("🗄️ SQL Database Results", expanded=True):
        # SQL Query
        if sql_result.get('query'):
            st.markdown("**📝 Generated SQL Query:**")
            st.code(sql_result['query'], language="sql")
        
        # SQL Explanation
        if sql_result.get('explanation'):
            with st.expander("📖 How This Query Works"):
                st.markdown(sql_result['explanation'])
        
        # Data Table + Exports
        if sql_result.get('results'):
            df = pd.DataFrame(sql_result['results'])
            
            st.markdown(f"**📊 Data Table ({sql_result.get('row_count', len(df))} rows):**")
            st.dataframe(df, use_container_width=True)
            
            # Export buttons
            st.markdown("**📥 Export Data:**")
            e1, e2, e3, e4 = st.columns(4)
            
            with e1:
                st.download_button(
                    "📄 CSV", data=df.to_csv(index=False),
                    file_name=f"fusion_sql_{msg_id}.csv", mime="text/csv",
                    use_container_width=True, key=f"sql_csv_{msg_id}"
                )
            
            with e2:
                st.download_button(
                    "📋 JSON",
                    data=df.to_json(orient="records", indent=2),
                    file_name=f"fusion_sql_{msg_id}.json",
                    mime="application/json",
                    use_container_width=True, key=f"sql_json_{msg_id}"
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
                    file_name=f"fusion_sql_{msg_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"sql_excel_{msg_id}"
                )
            
            with e4:
                st.download_button(
                    "📝 MD", data=df.to_markdown(index=False),
                    file_name=f"fusion_sql_{msg_id}.md", mime="text/markdown",
                    use_container_width=True, key=f"sql_md_{msg_id}"
                )
            
            # Chart Builder
            viz_info = can_visualize(df)
            
            if viz_info["can_chart"]:
                st.markdown("---")
                with st.expander("📊 Visualize This Data?", expanded=is_latest):
                    render_chart_builder(f"sql_{msg_id}", df)
            else:
                st.caption(f"📊 {viz_info['reason']}")
        
        # Timing info
        if sql_result.get('time'):
            st.caption(f"⏱️ SQL execution: {format_time(sql_result['time'])}")

def render_rag_section(msg_id: str, rag_result: dict):
    """
    Render RAG results section (answer + sources + document references)
    
    Args:
        msg_id: Unique message ID
        rag_result: RAG agent output dict
    """
    
    if not rag_result or not rag_result.get('success'):
        st.warning("❌ RAG query failed or found no relevant documents")
        if rag_result and rag_result.get('error'):
            st.error(f"Error: {rag_result['error']}")
        return
    
    with st.expander("📄 Document Search Results", expanded=True):
        # RAG Answer
        st.markdown("**💬 Document-Based Answer:**")
        st.markdown(rag_result['answer'])
        
        # Source Citations
        if rag_result.get('sources'):
            st.markdown("---")
            st.markdown(f"**📚 Source Documents ({len(rag_result['sources'])} citations):**")
            
            for i, source in enumerate(rag_result['sources'], 1):
                cited = "✅" if source.get('cited_in_answer') else "📎"
                similarity = source.get('similarity', '')
                sim_text = f" (Score: {similarity})" if similarity else ""
                
                st.markdown(
                    f"{cited} **{source['filename']}** (Page {source['page']}){sim_text}"
                )
        
        # Metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Chunks Retrieved", rag_result.get('chunks_retrieved', 0))
        with col2:
            query_type = rag_result.get('query_type', 'simple')
            st.metric("Query Type", query_type.title())
        with col3:
            st.metric("Time", f"{rag_result.get('time', 0):.2f}s")

def render_web_section(msg_id: str, web_result: dict):
    """
    Render Web scraping results section with scraper status dashboard.
    """

    if not web_result or not web_result.get('success'):
        st.warning("❌ Web scraping failed or returned no data")
        if web_result and web_result.get('error'):
            st.error(f"Error: {web_result['error']}")
        return

    with st.expander("🌐 Competitor Intelligence", expanded=True):

        # ── Scraper Status Dashboard ──────────────────────────────
        raw_data = web_result.get('raw_data', {})
        statuses = raw_data.get('scraper_statuses', [])

        if statuses:
            st.markdown("**🔍 Scraper Status Dashboard**")
            cols = st.columns(len(statuses))
            for col, s in zip(cols, statuses):
                name    = s.get('name', 'Unknown')
                status  = s.get('status', 'unknown')
                products = s.get('products', 0)
                elapsed  = s.get('time', 0)
                error    = s.get('error')

                if status == 'success':
                    icon = '🟢'
                    label = f"{products} products"
                elif status == 'fallback':
                    icon = '🟡'
                    label = f"Mock ({products} items)"
                elif status == 'empty':
                    icon = '🟠'
                    label = 'No products'
                else:
                    icon = '🔴'
                    label = 'Failed'

                with col:
                    st.metric(
                        label=f"{icon} {name}",
                        value=label,
                        delta=f"{elapsed}s" if elapsed else None,
                        delta_color="off"
                    )
                    if error and status != 'success':
                        st.caption(f"_{error[:60]}_")

            # Show fallback warning if any mock data was used
            fallbacks = [s for s in statuses if s.get('status') == 'fallback']
            if fallbacks:
                st.warning("⚠️ All live scrapers failed — answer is based on sample data, not real prices.")

            st.markdown("---")

        # ── Competitor Analysis Answer ────────────────────────────
        st.markdown("**🛒 Competitor Analysis:**")
        if web_result.get('llm_error'):
            st.caption(f"⚠️ LLM unavailable — showing raw scraped prices. ({web_result['llm_error'][:80]})")
        st.markdown(web_result['answer'])

        # ── Product Details per Competitor ────────────────────────
        if raw_data.get('competitors'):
            st.markdown("---")
            st.markdown("**📊 Scraped Products:**")
            for comp_data in raw_data['competitors']:
                competitor = comp_data.get('competitor', 'Unknown')
                method     = comp_data.get('method', 'Unknown')
                total      = comp_data.get('total_found', len(comp_data.get('products', [])))
                products   = comp_data.get('products', [])
                is_mock    = comp_data.get('is_mock', False)

                badge = " *(sample data)*" if is_mock else ""
                st.markdown(f"**{competitor}**{badge} — {method}")
                st.caption(f"Found: {total} | Showing: {len(products)}")

                for i, product in enumerate(products[:5], 1):
                    st.markdown(f"{i}. **{product.get('name', 'Unknown')}** — {product.get('price', 'N/A')}")

                st.markdown("---")

        # ── Export ────────────────────────────────────────────────
        if raw_data:
            st.download_button(
                "📋 Download JSON",
                data=json.dumps(raw_data, indent=2, default=str),
                file_name=f"fusion_web_{msg_id}.json",
                mime="application/json",
                key=f"web_json_{msg_id}"
            )

        if web_result.get('time'):
            st.caption(f"⏱️ Web scraping: {format_time(web_result['time'])}")

def render_model_journey(models_tried: list):
    """
    Display which models were tried and their status
    
    Args:
        models_tried: List of dicts with 'model', 'status', 'time', 'error'
    """
    
    if not models_tried:
        return
    
    with st.expander("🔄 Model Journey", expanded=False):
        st.markdown("**Models attempted for this query:**")
        
        for i, attempt in enumerate(models_tried, 1):
            model = attempt.get('model', 'Unknown')
            status = attempt.get('status', '❓ UNKNOWN')
            time_taken = attempt.get('time', 0)
            error = attempt.get('error', '')
            
            # Color code by status
            if '✅' in status:
                color = "#4CAF50"
            elif '⏭️' in status:
                color = "#9E9E9E"
            else:
                color = "#F44336"
            
            st.markdown(
                f"""
                <div style='
                    border-left: 4px solid {color};
                    padding: 8px 12px;
                    margin: 8px 0;
                    background: {color}11;
                    border-radius: 4px;
                '>
                    <div style='font-weight: 600;'>{status} {model}</div>
                    <div style='font-size: 12px; color: #666; margin-top: 4px;'>
                        Time: {time_taken:.2f}s
                        {f"<br>Error: {error[:100]}" if error else ""}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

# ─────────────────────────────────────────────────────
#  ✨ NEW: FUSION MESSAGE RENDERER
# ─────────────────────────────────────────────────────

def render_fusion_message(msg: dict, is_latest: bool = False):
    """
    Render a complete Fusion Agent message with all sections
    
    Args:
        msg: Message dict with 'answer', 'source_type', 'sql_result', 'rag_result', 'web_result', etc.
        is_latest: Whether this is the latest message
    """
    
    msg_id = msg.get("id", "0")
    
    # ═══════════════════════════════════════════════════════════
    # 1. ROUTING DECISION
    # ═══════════════════════════════════════════════════════════
    
    render_routing_badge(msg.get("source_type", "unknown"))

    # Routing fallback warning
    if msg.get("routing_fallback"):
        routing_model = msg.get("routing_model", "backup model")
        st.warning(
            f"⚠️ **Routing used fallback LLM** ({routing_model}) — primary model was unavailable. "
            "Routing decision may differ from normal. Results could vary.",
            icon="⚠️"
        )

    # ═══════════════════════════════════════════════════════════
    # 2. FUSED ANSWER (Main response)
    # ═══════════════════════════════════════════════════════════
    
    st.markdown("### 💡 Answer")
    st.markdown(msg.get("answer", "No answer available"))
    
    # ═══════════════════════════════════════════════════════════
    # 3. CROSS-VALIDATION (if available)
    # ═══════════════════════════════════════════════════════════
    
    if msg.get("validation"):
        render_confidence_badge(msg["validation"])
    
    st.markdown("---")
    
    # ═══════════════════════════════════════════════════════════
    # 4. SOURCE-SPECIFIC SECTIONS (Expandable)
    # ═══════════════════════════════════════════════════════════
    
    # SQL Section
    if msg.get("sql_result"):
        render_sql_section(msg_id, msg["sql_result"], is_latest)
    
    # RAG Section
    if msg.get("rag_result"):
        render_rag_section(msg_id, msg["rag_result"])
    
    # Web Section
    if msg.get("web_result"):
        render_web_section(msg_id, msg["web_result"])
    
    # ═══════════════════════════════════════════════════════════
    # 5. MODEL JOURNEY (All models tried across all agents)
    # ═══════════════════════════════════════════════════════════
    
    all_models_tried = []
    
    if msg.get("sql_result") and msg["sql_result"].get("models_tried"):
        all_models_tried.extend(msg["sql_result"]["models_tried"])
    
    if msg.get("rag_result") and msg["rag_result"].get("models_tried"):
        all_models_tried.extend(msg["rag_result"]["models_tried"])
    
    if all_models_tried:
        render_model_journey(all_models_tried)
    
    # ═══════════════════════════════════════════════════════════
    # 6. TIMING INFO
    # ═══════════════════════════════════════════════════════════
    
    total_time = msg.get("query_time", 0)
    st.caption(f"⏱️ Total query time: {format_time(total_time)}")

# ═══════════════════════════════════════════════════════
#  INITIALIZE AGENT
# ═══════════════════════════════════════════════════════

def get_agent():
    return get_fusion_agent()



def add_to_history(question, result, execution_time):
    """Add query to history (now stores full fusion result)"""
    st.session_state.query_history.insert(0, {
        "question": question,
        "answer": result.get("answer", ""),
        "source_type": result.get("source_type", "unknown"),
        "sql_result": result.get("sql_result"),
        "rag_result": result.get("rag_result"),
        "web_result": result.get("web_result"),
        "validation": result.get("validation"),
        "sources": result.get("sources", []),
        "time": execution_time,
        "timestamp": datetime.now(),
        "success": True
    })
    st.session_state.query_history = st.session_state.query_history[:10]

# ═══════════════════════════════════════════════════════
#  PAGE LAYOUT
# ═══════════════════════════════════════════════════════

def run_fusion_chat():
    """Main function for Fusion Chat interface"""

    # ═══════════════════════════════════════════════════════
    #  LOAD AGENT (cached — only slow on first load)
    # ═══════════════════════════════════════════════════════

    if "nexusiq_agent" not in st.session_state:
        # Kick off background load on first visit so the script thread
        # stays free to render the loading UI across poll cycles.
        if "_agent_loader" not in st.session_state:
            _result: dict = {}

            def _worker():
                try:
                    _result["agent"] = get_fusion_agent()
                except Exception as exc:
                    _result["error"] = exc

            _t = threading.Thread(target=_worker, daemon=True)
            _t.start()
            st.session_state._agent_loader = (_t, _result)

        _thread, _result = st.session_state._agent_loader

        st.markdown("<br><br>", unsafe_allow_html=True)
        _l, _c, _r = st.columns([1, 2, 1])
        with _c:
            st.markdown(
                """
                <div style='text-align:center; padding:40px;'>
                    <div style='font-size:72px; margin-bottom:16px;'>🧠</div>
                    <h2 style='color:#4F8BF9; margin-bottom:8px;'>Loading Fusion Agent</h2>
                    <p style='color:#888; font-size:16px;'>Initializing AI models & vector database...</p>
                    <p style='color:#aaa; font-size:13px; margin-top:8px;'>First load only — ~20 seconds</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(0, text="Loading AI models...")

        if _thread.is_alive():
            # Poll: let Streamlit flush the loading UI, then rerun.
            time.sleep(0.4)
            st.rerun()

        if "error" in _result:
            st.error(f"Failed to load Fusion Agent: {_result['error']}")
            del st.session_state._agent_loader
            st.stop()

        st.session_state.nexusiq_agent = _result["agent"]
        del st.session_state._agent_loader
        st.rerun()

    agent = st.session_state.nexusiq_agent

    # ═══════════════════════════════════════════════════════
    #  SESSION STATE
    # ═══════════════════════════════════════════════════════

    if "query_history" not in st.session_state:
        st.session_state.query_history = []
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "pending_suggestion" not in st.session_state:
        st.session_state.pending_suggestion = None
    if "pending_correction" not in st.session_state:
        st.session_state.pending_correction = None   # {"original": str, "corrected": str, "corrections": list}
    if "_last_corrected_q" not in st.session_state:
        st.session_state["_last_corrected_q"] = None
    if "source_filter" not in st.session_state:
        st.session_state.source_filter = "Auto"  # ✨ NEW: Default to auto-routing
    if "web_category" not in st.session_state:
        st.session_state.web_category = "electronics"  # ✨ NEW: Default web category
    
    st.title("🔗 Fusion Agent — Multi-Source Intelligence")
    st.markdown("*Cross-validates answers across SQL database, business PDFs, and live competitor pricing*")
    st.markdown(
        "<p style='font-size:13px; color:#6b7280; margin-top:-8px;'>"
        "<code>Gemini 2.5</code> &nbsp;·&nbsp; <code>Groq LLaMA 3.3</code> &nbsp;·&nbsp; "
        "<code>PostgreSQL</code> &nbsp;·&nbsp; <code>ChromaDB</code> &nbsp;·&nbsp; "
        "<code>BM25 + Vector Search</code> &nbsp;·&nbsp; <code>Live Web Scraping</code>"
        "</p>",
        unsafe_allow_html=True,
    )
    
    # ═══════════════════════════════════════════════════════
    #  SIDEBAR
    # ═══════════════════════════════════════════════════════
    
    with st.sidebar:
        st.header("⚙️ Source Controls")
        
        # ✨ NEW: Source Filter
        st.subheader("🎯 Routing Mode")
        source_filter = st.radio(
            "Choose how to route queries:",
            ["Auto", "SQL Only", "RAG Only", "Web Only"],
            index=0,
            key="source_filter_radio",
            help="Auto: Let Fusion Agent decide | Manual: Force a specific source"
        )
        st.session_state.source_filter = source_filter
        
        # ✨ NEW: Web Category Selector (only show if Web is involved)
        if source_filter in ["Auto", "Web Only"]:
            st.markdown("---")
            st.subheader("🛒 Web Scraping Category")
            web_category = st.selectbox(
                "Product category for competitor data:",
                ["electronics", "home", "clothing", "food", "sports"],
                index=0,
                key="web_cat_select"
            )
            st.session_state.web_category = web_category
        
        st.markdown("---")
        st.subheader("📊 Database Schema")
        
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
            ("What was Q4 2024 revenue?", "Fusion (SQL+RAG)"),
            ("Compare Q3 and Q4 performance", "RAG Comparison"),
            ("What are competitor prices for electronics?", "Web Scraping"),
            ("Top 5 products by revenue", "SQL Only"),
            ("What is the return policy?", "RAG Only"),
        ]
        
        for eq, hint in example_questions:
            if st.button(f"💬 {eq}", key=f"ex_{eq[:20]}", use_container_width=True):
                st.session_state.pending_suggestion = eq
                st.rerun()
            st.caption(f"→ {hint}")
        
        st.markdown("---")
        st.subheader("📊 Model Status")
        
        # Show Gemini Pro status
        if settings.use_gemini_pro:
            st.warning("🟡 Gemini Pro: **ENABLED** (may exhaust quickly)")
        else:
            st.info("🔵 Gemini Pro: **DISABLED** (free tier protection)")
        
        # Get quota status from SQL agent (Fusion uses same models)
        quota_status = agent.sql_agent.get_quota_status()
        if quota_status:
            for model, status in quota_status.items():
                if "pro" in model.lower() and not settings.use_gemini_pro:
                    continue
                st.caption(f"{status['status']} {model.split('-')[0]}")
        else:
            st.caption("🟢 All models available")
        
        if st.button("🔄 Reset Quota Tracking", use_container_width=True):
            agent.sql_agent.reset_quota_tracking()
            st.rerun()
        
        st.markdown("---")
        st.subheader("📜 Query History")
        
        if st.session_state.query_history:
            for i, item in enumerate(st.session_state.query_history[:5]):
                # Show source type icon
                source_type = item.get("source_type", "unknown")
                icon = SOURCE_ICONS.get(source_type.split('_')[0], "❓")
                
                short = item["question"][:25] + ("..." if len(item["question"]) > 25 else "")
                
                if st.button(f"{icon} {short}", key=f"hist_{i}", use_container_width=True):
                    st.session_state.pending_suggestion = item["question"]
                    st.rerun()
                
                st.caption(f"⏱️ {item['time']:.1f}s • {time_ago(item['timestamp'])}")
            
            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state.query_history = []
                st.session_state.chat_messages = []
                # Clear chart state
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
            with st.chat_message("assistant", avatar="🔗"):
                render_fusion_message(msg, is_latest=is_latest)
    
    # ═══════════════════════════════════════════════════════
    #  DID YOU MEAN? (spell-correction prompt)
    # ═══════════════════════════════════════════════════════

    if st.session_state.pending_correction:
        corr = st.session_state.pending_correction
        correction_labels = " | ".join(
            [f"**{c['from']}** → **{c['to']}**" for c in corr["corrections"]]
        )
        with st.chat_message("assistant", avatar="🔗"):
            st.info(
                f"Did you mean: **\"{corr['corrected']}\"**?\n\n"
                f"*Auto-detected correction: {correction_labels}*"
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button(
                    f"✅ Yes — run \"{corr['corrected']}\"",
                    key="use_corrected",
                    use_container_width=True
                ):
                    st.session_state.pending_suggestion = corr["corrected"]
                    st.session_state.pending_correction = None
                    st.rerun()
            with col2:
                if st.button(
                    f"❌ No — run as typed",
                    key="use_original",
                    use_container_width=True
                ):
                    st.session_state.pending_suggestion = corr["original"]
                    st.session_state.pending_correction = None
                    st.session_state["_last_corrected_q"] = corr["original"]
                    st.rerun()

    # ═══════════════════════════════════════════════════════
    #  HANDLE INPUT
    # ═══════════════════════════════════════════════════════

    if st.session_state.pending_suggestion:
        question = st.session_state.pending_suggestion
        st.session_state.pending_suggestion = None
    else:
        question = st.chat_input("💬 Ask a question across all data sources...")
    
    # ═══════════════════════════════════════════════════════
    #  PROCESS NEW QUESTION
    # ═══════════════════════════════════════════════════════
    
    if question:
        from utils.validators import auto_correct_question

        # Check for spelling corrections BEFORE running the query.
        # Only intercept on fresh user input — not when re-running a corrected query.
        is_corrected_rerun = question == (st.session_state.get("_last_corrected_q"))
        correction = auto_correct_question(question) if not is_corrected_rerun else {"corrected": False}

        if correction["corrected"] and not is_corrected_rerun:
            # Show the user's original message in chat
            st.session_state.chat_messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            # Store correction for the "Did you mean?" UI and rerun
            st.session_state.pending_correction = {
                "original": question,
                "corrected": correction["corrected_question"],
                "corrections": correction["corrections"],
            }
            st.session_state["_last_corrected_q"] = correction["corrected_question"]
            st.rerun()

        # Mark this as a resolved corrected query so we don't re-intercept it
        if is_corrected_rerun:
            st.session_state["_last_corrected_q"] = None

        # Add user message
        st.session_state.chat_messages.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):
            st.markdown(question)

        # Process with Fusion Agent
        with st.chat_message("assistant", avatar="🔗"):
            status = st.empty()
            insight_box = st.empty()
            
            insight_box.info(random.choice(INSIGHTS))
            
            status.markdown("🔍 Analyzing question...")
            time.sleep(0.3)
            
            status.markdown("🧠 Routing to appropriate sources...")
            time.sleep(0.3)
            
            status.markdown("⚡ Gathering intelligence...")
            
            start_time = time.time()
            
            # ✨ Call Fusion Agent (respect user's routing mode selection)
            source_filter = st.session_state.get("source_filter", "Auto")
            force_source_map = {
                "SQL Only": "sql_only",
                "RAG Only": "rag_only",
                "Web Only": "web_only",
            }
            force_source = force_source_map.get(source_filter)  # None when "Auto"
            result = agent.query(question, force_source=force_source)
            
            total_time = time.time() - start_time
            
            status.empty()
            insight_box.empty()
            
            msg_id = str(int(time.time() * 1000))
            
            # Render the fusion result
            render_fusion_message({
                "id": msg_id,
                "answer": result.get("answer", "No answer generated"),
                "source_type": result.get("source_type", "unknown"),
                "sql_result": result.get("sql_result"),
                "rag_result": result.get("rag_result"),
                "web_result": result.get("web_result"),
                "validation": result.get("validation"),
                "sources": result.get("sources", []),
                "query_time": total_time
            }, is_latest=True)
            
            # Save to chat history
            st.session_state.chat_messages.append({
                "role": "assistant",
                "id": msg_id,
                "answer": result.get("answer", ""),
                "source_type": result.get("source_type", "unknown"),
                "sql_result": result.get("sql_result"),
                "rag_result": result.get("rag_result"),
                "web_result": result.get("web_result"),
                "validation": result.get("validation"),
                "sources": result.get("sources", []),
                "query_time": total_time
            })
            
            # Save to query history
            add_to_history(question, result, total_time)
        
        st.rerun()
    
    # ═══════════════════════════════════════════════════════
    #  EMPTY STATE (Welcome Screen)
    # ═══════════════════════════════════════════════════════
    
    if not st.session_state.chat_messages:
        st.markdown("---")
        
        st.markdown(
            """
            <div style='text-align:center; padding:32px 0 16px 0;'>
                <h2 style='font-size:2rem; font-weight:800; margin-bottom:8px;'>
                    What do you want to know?
                </h2>
                <p style='color:#9ca3af; font-size:1.05em; margin:0;'>
                    Type any business question — the agent decides whether to query SQL, search PDFs, or scrape the web.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # Metrics strip
        sq1, sq2, sq3, sq4 = st.columns(4)
        with sq1:
            st.metric("Transactions", "100K", "in PostgreSQL")
        with sq2:
            st.metric("Documents", "23 PDFs", "vector-indexed")
        with sq3:
            st.metric("LLM Models", "2 Active", "Gemini + Groq")
        with sq4:
            st.metric("Web Sources", "5 Sites", "live scraping")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🚀 Quick Start — click any question below")

        qs1, qs2, qs3 = st.columns(3)

        with qs1:
            st.markdown("**📊 Cross-Validated Queries**")
            st.caption("SQL answer checked against PDF reports")
            if st.button("💰 Q4 2024 revenue validated?", use_container_width=True, key="qs1"):
                st.session_state.pending_suggestion = "What was Q4 2024 revenue?"
                st.rerun()
            if st.button("📈 Compare Q3 vs Q4 performance", use_container_width=True, key="qs2"):
                st.session_state.pending_suggestion = "Compare Q3 and Q4 2024 performance"
                st.rerun()

        with qs2:
            st.markdown("**📄 Document Intelligence**")
            st.caption("Searches 23 indexed business PDFs")
            if st.button("📋 What is the return policy?", use_container_width=True, key="qs3"):
                st.session_state.pending_suggestion = "What is the return policy for Electronics?"
                st.rerun()
            if st.button("🌐 West region expansion plan?", use_container_width=True, key="qs4"):
                st.session_state.pending_suggestion = "What is the West region expansion plan?"
                st.rerun()

        with qs3:
            st.markdown("**🛒 Competitor Intelligence**")
            st.caption("Live prices scraped from competitor sites")
            if st.button("💻 Electronics competitor pricing?", use_container_width=True, key="qs5"):
                st.session_state.pending_suggestion = "What are competitor prices for electronics?"
                st.rerun()
            if st.button("🏠 Home goods vs competitors?", use_container_width=True, key="qs6"):
                st.session_state.pending_suggestion = "Compare our home goods prices to competitors"
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 **Tip:** Use the sidebar to force SQL / RAG / Web only, or leave it on **Auto** to let the agent decide.")

# Run the app
if __name__ == "__main__":
    run_fusion_chat()
