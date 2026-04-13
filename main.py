"""
NexusIQ AI — Main Application
"""
import streamlit as st
import requests

st.set_page_config(
    page_title="NexusIQ AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Navigation state ──────────────────────────────────────────────────────────
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "🏠 Home"
if st.session_state.get("nav_to_fusion"):
    st.session_state.nav_page = "🔗 Fusion Agent"
    st.session_state.nav_to_fusion = False

page = st.sidebar.radio(
    "🧠 NexusIQ AI",
    ["🏠 Home", "🔗 Fusion Agent"],
    key="nav_page"
)

# ══════════════════════════════════════════════════════════════════════════════
#  HOME PAGE
# ══════════════════════════════════════════════════════════════════════════════

if page == "🏠 Home":

    # ── Hero ─────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align:center; padding: 32px 0 8px 0;">
            <div style="font-size:64px; margin-bottom:8px;">🧠</div>
            <h1 style="font-size:3rem; font-weight:900; margin:0; letter-spacing:-1px;">NexusIQ AI</h1>
            <p style="font-size:1.25rem; color:#9ca3af; margin-top:12px; font-weight:400;">
                Ask a business question. Get a cross-validated answer — from SQL, PDFs, and live web data.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── CTA button ───────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1.5, 2, 1.5])
    with col_c:
        if st.button("🚀  Launch Fusion Agent  →", type="primary", use_container_width=True):
            st.session_state.nav_to_fusion = True
            st.rerun()
        st.markdown(
            "<p style='text-align:center; color:#6b7280; font-size:13px; margin-top:6px;'>"
            "Cross-validates answers across 3 live data sources</p>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    # ── Metrics strip ────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("📦 Transactions", "100,000", "PostgreSQL")
    with m2:
        st.metric("📄 Business Docs", "23 PDFs", "ChromaDB + BM25")
    with m3:
        st.metric("🤖 AI Agents", "4 Active", "Always on")
    with m4:
        st.metric("🌐 Data Sources", "3 Types", "SQL · RAG · Web")

    st.divider()

    # ── How it works ─────────────────────────────────────────────────────────
    st.markdown("### ⚡ How It Works")
    st.markdown("<br>", unsafe_allow_html=True)

    h1, h2, h3 = st.columns(3)
    with h1:
        st.markdown(
            """
            <div style="background:#1e293b; border-radius:12px; padding:24px; height:180px;">
                <div style="font-size:32px;">💬</div>
                <h4 style="margin:8px 0 4px 0;">1. Ask in plain English</h4>
                <p style="color:#94a3b8; font-size:14px; margin:0;">
                    No SQL. No keyword search.<br>
                    <em>"What was our best region in Q4 2024?"</em>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown(
            """
            <div style="background:#1e293b; border-radius:12px; padding:24px; height:180px;">
                <div style="font-size:32px;">🔍</div>
                <h4 style="margin:8px 0 4px 0;">2. Agents investigate</h4>
                <p style="color:#94a3b8; font-size:14px; margin:0;">
                    SQL Agent queries the database. RAG Agent scans PDFs.
                    Web Agent scrapes live competitor prices — in parallel.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with h3:
        st.markdown(
            """
            <div style="background:#1e293b; border-radius:12px; padding:24px; height:180px;">
                <div style="font-size:32px;">✅</div>
                <h4 style="margin:8px 0 4px 0;">3. Cross-validated answer</h4>
                <p style="color:#94a3b8; font-size:14px; margin:0;">
                    Results are compared across sources. Discrepancies flagged.
                    Confidence score shown with every answer.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    # ── Features ─────────────────────────────────────────────────────────────
    st.markdown("### 🛠️ What's Under the Hood")
    st.markdown("<br>", unsafe_allow_html=True)

    f1, f2 = st.columns(2)
    with f1:
        st.markdown("""
**Core Agents**
- 🔗 **Fusion Agent** — Orchestrates all agents, merges results, validates
- 🗄️ **SQL Agent** — Natural language → PostgreSQL via LLM
- 📄 **RAG Agent** — Hybrid BM25 + vector search over 23 documents
- 🌐 **Web Agent** — Live competitor price scraping (Newegg + more)
        """)
    with f2:
        st.markdown("""
**Intelligence Layer**
- 🔍 **Cross-Validation Engine** — Compares SQL vs PDF numbers automatically
- ⚡ **Circuit Breaker** — Switches LLM models if quota exceeded
- 🧠 **Smart Routing** — Detects query type, picks the best agent
- 📊 **Chart Builder** — Auto-generates Plotly charts from SQL results
- 💬 **Export** — Download answers as CSV, JSON, Excel, or Markdown
        """)

    st.divider()

    # ── Tech stack ───────────────────────────────────────────────────────────
    st.markdown("### 🧰 Tech Stack")
    st.markdown(
        """
        <p style="font-size:15px; line-height:2; color:#cbd5e1;">
        <code>Google Gemini 2.5</code> &nbsp;·&nbsp;
        <code>Groq LLaMA 3.3-70B</code> &nbsp;·&nbsp;
        <code>LangChain</code> &nbsp;·&nbsp;
        <code>PostgreSQL</code> &nbsp;·&nbsp;
        <code>Supabase</code> &nbsp;·&nbsp;
        <code>ChromaDB</code> &nbsp;·&nbsp;
        <code>Sentence Transformers</code> &nbsp;·&nbsp;
        <code>SQLAlchemy</code> &nbsp;·&nbsp;
        <code>Streamlit</code> &nbsp;·&nbsp;
        <code>Plotly</code> &nbsp;·&nbsp;
        <code>Python 3.11</code>
        </p>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Bottom CTA ───────────────────────────────────────────────────────────
    st.markdown(
        "<h3 style='text-align:center; margin-bottom:16px;'>Ready to explore?</h3>",
        unsafe_allow_html=True,
    )
    col_l2, col_c2, col_r2 = st.columns([1.5, 2, 1.5])
    with col_c2:
        if st.button("🚀  Try It Now — Launch Fusion Agent", type="primary", use_container_width=True):
            st.session_state.nav_to_fusion = True
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  FUSION AGENT PAGE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🔗 Fusion Agent":
    from ui.fusion_chat import run_fusion_chat
    run_fusion_chat()
