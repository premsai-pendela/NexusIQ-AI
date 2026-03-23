"""
NexusIQ AI — Main Application
"""
import streamlit as st
import time
import requests
from streamlit_lottie import st_lottie

st.set_page_config(
    page_title="NexusIQ AI",
    page_icon="🧠",
    layout="wide"
)

@st.cache_data
def load_lottie_url(url: str):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

LOTTIE_LOADING = "https://assets9.lottiefiles.com/packages/lf20_x62chJ.json"

page = st.sidebar.radio(
    "🧠 NexusIQ AI",
    ["🏠 Home", "🗄️ SQL Agent"]
)

if page == "🏠 Home":
    st.title("🧠 NexusIQ AI")
    st.subheader("Multi-Source Business Intelligence Agent System")
    
    st.markdown("""
    ### 🎯 What We Do
    NexusIQ AI autonomously answers business questions by investigating across 
    multiple data sources in minutes instead of days.
    
    ### 🚀 Features
    - 🗄️ **SQL Agent** — Query 100K+ transactions in plain English
    - 📄 **RAG Agent** — Search through business documents *(Coming Soon)*
    - 🌐 **Web Agent** — Scrape competitor data *(Coming Soon)*
    - 📊 **Data Agent** — Analyze CSVs and sentiment *(Coming Soon)*
    """)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Database Records", "100,000", "✅")
    with col2:
        st.metric("Agents Built", "1 / 6", "+1 this week")
    with col3:
        st.metric("Status", "Active", "🟢")

elif page == "🗄️ SQL Agent":
    
    if "sql_agent_loaded" not in st.session_state:
        st.session_state.sql_agent_loaded = False
    
    if not st.session_state.sql_agent_loaded:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🔄 Loading SQL Agent...")
            lottie_json = load_lottie_url(LOTTIE_LOADING)
            if lottie_json:
                st_lottie(lottie_json, height=200, key="loading_brain")
            else:
                st.markdown("<div style='text-align:center;font-size:60px;'>🧠</div>", unsafe_allow_html=True)
            
            progress = st.progress(0)
            for i in range(100):
                time.sleep(0.01)
                progress.progress(i + 1)
        
        st.session_state.sql_agent_loaded = True
        st.rerun()
    
    else:
        from ui.sql_chat import run_sql_chat
        run_sql_chat()