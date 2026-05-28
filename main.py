"""
NexusIQ AI — Main Application
"""
import streamlit as st
COMMAND_CENTER_PROMPTS = [
    {
        "title": "Validate Q4 Electronics revenue",
        "question": "Validate Q4 Electronics revenue across SQL and PDF reports.",
        "route": "SQL + RAG",
        "signal": "Cross-source revenue validation",
    },
    {
        "title": "Compare Q3 and Q4 performance",
        "question": "Compare Q3 and Q4 2024 performance across all metrics.",
        "route": "RAG comparison",
        "signal": "Multi-document synthesis",
    },
    {
        "title": "Explain West vs South",
        "question": "Explain why West region outperformed South in 2024.",
        "route": "SQL + RAG",
        "signal": "Numbers plus business context",
    },
    {
        "title": "Find competitor pricing",
        "question": "What are competitor prices for electronics?",
        "route": "Live web",
        "signal": "External market data",
    },
    {
        "title": "Summarize return policy",
        "question": "What is the return policy for Electronics?",
        "route": "RAG",
        "signal": "Internal policy retrieval",
    },
    {
        "title": "Count October transactions",
        "question": "Show October 2024 transaction count from the database.",
        "route": "SQL",
        "signal": "Exact database query",
    },
]


def launch_fusion(
    question: str | None = None,
    show_command_center: bool = False,
    data_context_key: str = "live",
):
    if question:
        st.session_state.pending_suggestion = question
    if st.session_state.get("data_context_key", "live") != data_context_key:
        for key in (
            "query_history",
            "chat_messages",
            "pending_suggestion",
            "pending_query_to_process",
            "pending_repeat_decision",
            "source_filter_radio",
        ):
            st.session_state.pop(key, None)
        st.session_state.source_filter = "Auto"
    st.session_state.data_context_key = data_context_key
    st.session_state.pop("data_context_selector", None)
    st.session_state.pop("nexusiq_agent", None)
    st.session_state.show_fusion_command_center = show_command_center
    st.session_state.nav_to_fusion = True
    st.rerun()


def render_command_center_styles():
    st.markdown(
        """
        <style>
            .nexusiq-shell {
                padding: 20px 0 6px;
            }
            .nexusiq-eyebrow {
                color: #38bdf8;
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0;
                text-transform: uppercase;
                margin-bottom: 8px;
            }
            .nexusiq-hero {
                border: 1px solid rgba(148, 163, 184, 0.28);
                border-radius: 8px;
                padding: 28px;
                background:
                    linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(17, 24, 39, 0.96)),
                    radial-gradient(circle at 20% 10%, rgba(56, 189, 248, 0.22), transparent 32%);
                box-shadow: 0 18px 45px rgba(2, 6, 23, 0.22);
            }
            .nexusiq-hero h1 {
                margin: 0;
                color: #f8fafc;
                font-size: clamp(2.1rem, 5vw, 4.3rem);
                line-height: 1.02;
                letter-spacing: 0;
                font-weight: 900;
            }
            .nexusiq-hero p {
                max-width: 760px;
                margin: 14px 0 0;
                color: #cbd5e1;
                font-size: 1.04rem;
                line-height: 1.65;
            }
            .nexusiq-chip {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                min-height: 30px;
                padding: 6px 10px;
                border-radius: 999px;
                border: 1px solid rgba(56, 189, 248, 0.28);
                background: rgba(8, 47, 73, 0.42);
                color: #e0f2fe;
                font-size: 0.78rem;
                font-weight: 700;
                margin: 6px 6px 0 0;
            }
            .nexusiq-chip span {
                width: 8px;
                height: 8px;
                border-radius: 999px;
                background: #22c55e;
                box-shadow: 0 0 14px rgba(34, 197, 94, 0.72);
            }
            .nexusiq-band {
                border: 1px solid rgba(148, 163, 184, 0.22);
                border-radius: 8px;
                padding: 18px;
                background: #f8fafc;
                min-height: 122px;
            }
            .nexusiq-band strong {
                display: block;
                font-size: 0.9rem;
                color: #0f172a;
                margin-bottom: 6px;
            }
            .nexusiq-band p {
                color: #475569;
                font-size: 0.88rem;
                line-height: 1.45;
                margin: 0;
            }
            .nexusiq-flow {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 10px;
                align-items: stretch;
                margin-top: 12px;
            }
            .nexusiq-flow-step {
                border: 1px solid rgba(14, 116, 144, 0.22);
                border-radius: 8px;
                padding: 14px;
                background: #f8fafc;
                min-height: 112px;
            }
            .nexusiq-flow-step b {
                display: block;
                color: #0f172a;
                font-size: 0.92rem;
                margin-bottom: 5px;
            }
            .nexusiq-flow-step small {
                color: #64748b;
                line-height: 1.35;
            }
            .nexusiq-answer {
                border-left: 5px solid #0ea5e9;
                border-radius: 8px;
                padding: 18px 20px;
                background: #f8fafc;
                color: #0f172a;
                margin-top: 14px;
            }
            .nexusiq-answer h4 {
                margin: 0 0 10px;
                color: #0f172a;
            }
            .nexusiq-answer p {
                margin: 6px 0;
                color: #334155;
                line-height: 1.48;
            }
            @media (max-width: 900px) {
                .nexusiq-hero {
                    padding: 22px;
                }
                .nexusiq-flow {
                    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="NexusIQ AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed"
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
    render_command_center_styles()

    # ── Hero ─────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="nexusiq-shell">
            <div class="nexusiq-hero">
                <div class="nexusiq-eyebrow">Intelligence Command Center</div>
                <h1>NexusIQ AI</h1>
                <p>
                    A production-minded AI intelligence system that routes business questions across
                    SQL transactions, indexed business documents, and live web sources, then validates
                    the answer before showing confidence and citations.
                </p>
                <div style="margin-top:16px;">
                    <div class="nexusiq-chip"><span></span>100,000 Supabase transactions</div>
                    <div class="nexusiq-chip"><span></span>43 business documents indexed</div>
                    <div class="nexusiq-chip"><span></span>SQL + RAG validation</div>
                    <div class="nexusiq-chip"><span></span>Live web intelligence</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── CTA button ───────────────────────────────────────────────────────────
    st.markdown("")
    cta_left, cta_center, cta_right = st.columns([1, 2, 1])
    with cta_center:
        if st.button("Ask NexusIQ", type="primary", use_container_width=True):
            launch_fusion()

    st.divider()

    # ── Metrics strip ────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Transactions Indexed", "100,000", "Supabase SQL")
    with m2:
        st.metric("Business Docs", "43", "BM25 + vector RAG + reranker")
    with m3:
        st.metric("Agents Active", "4", "SQL, RAG, Web, Fusion")
    with m4:
        st.metric("Validation Mode", "3-way", "SQL · RAG · Web")

    st.divider()

    st.markdown("### How Answers Are Built")
    st.markdown(
        """
        <div class="nexusiq-flow">
            <div class="nexusiq-flow-step"><b>Question</b><small>You ask a business question in your own words.</small></div>
            <div class="nexusiq-flow-step"><b>Router</b><small>System chooses SQL, RAG, Web, or multi-source fusion.</small></div>
            <div class="nexusiq-flow-step"><b>Agents</b><small>Independent agents run in parallel where possible.</small></div>
            <div class="nexusiq-flow-step"><b>Validation</b><small>Numbers are reconciled across exact and document sources.</small></div>
            <div class="nexusiq-flow-step"><b>Answer</b><small>Final response includes confidence, route, and citations.</small></div>
        </div>
        <div class="nexusiq-answer">
            <h4>Featured validation preview</h4>
            <p><b>Question:</b> Validate Q4 Electronics revenue across SQL and PDF reports.</p>
            <p><b>Expected result:</b> SQL and RAG validate Q4 Electronics revenue at about <b>$31.7M</b>, with source difference and confidence shown in the answer.</p>
            <p><b>Route:</b> SQL Agent + RAG Agent → Fusion Agent → validated answer.</p>
            <p><b>Sources:</b> sales_transactions, Q4 2024 Financial Report.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown("### Starter Questions")
    prompt_cols = st.columns(3)
    for idx, prompt in enumerate(COMMAND_CENTER_PROMPTS):
        with prompt_cols[idx % 3]:
            st.markdown(
                f"""
                <div class="nexusiq-band">
                    <strong>{prompt["title"]}</strong>
                    <p>{prompt["signal"]}<br><b>Route:</b> {prompt["route"]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Run this question", key=f"home_prompt_{idx}", use_container_width=True):
                launch_fusion(prompt["question"])

    st.divider()

    # ── Features ─────────────────────────────────────────────────────────────
    st.markdown("### Production Signals")
    f1, f2 = st.columns(2)
    with f1:
        st.markdown("""
**System intelligence**
- Fusion Agent orchestrates SQL, RAG, and Web agents.
- Hybrid BM25 + vector search + cross-encoder reranker for precision retrieval.
- Cross-validation compares exact database values with document-reported values.
- Progressive status updates show which source finished and how long it took.
        """)
    with f2:
        st.markdown("""
**Trust and demo readiness**
- Circuit breaker moves between Gemini and Groq when quota is exhausted.
- Query cache returns repeat questions quickly without stale unbounded memory.
- SQL results expose generated queries and exportable result tables.
- Source badges make Database, PDF Reports, Live Web, and Fusion routes visible.
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
        if st.button("Ask NexusIQ", type="primary", use_container_width=True, key="bottom_ask_nexusiq"):
            launch_fusion()

# ══════════════════════════════════════════════════════════════════════════════
#  FUSION AGENT PAGE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🔗 Fusion Agent":
    # Show instant feedback BEFORE heavy import
    _loading_msg = st.empty()
    _loading_msg.markdown(
        """
        <div style='text-align:center; padding:60px 0;'>
            <div style='font-size:64px; margin-bottom:12px;'>🧠</div>
            <h3 style='color:#4F8BF9;'>Preparing Fusion Agent...</h3>
            <p style='color:#888;'>Loading modules, please wait</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    from ui.fusion_chat import run_fusion_chat
    
    _loading_msg.empty()
    run_fusion_chat()
