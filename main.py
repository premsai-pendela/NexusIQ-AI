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
    ["🏠 Home", "🔗 Fusion Agent"]  # ✨ Changed from "SQL Agent" to "Fusion Agent"
)

if page == "🏠 Home":
    st.title("🧠 NexusIQ AI")
    st.subheader("Multi-Source Business Intelligence Agent System")
    
    st.markdown("""
    ### 🎯 What We Do
    NexusIQ AI autonomously answers business questions by investigating across 
    multiple data sources in minutes instead of days.

    ### 🚀 Features
    - 🔗 **Fusion Agent** — Cross-validated intelligence from SQL + RAG + Web
    - 🗄️ **SQL Agent** — Query 100K+ transactions in plain English
    - 📄 **RAG Agent** — Search through 23 business documents
    - 🌐 **Web Agent** — Scrape competitor pricing (Newegg, IKEA, Campmor, Swanson)
    - 🔍 **Cross-Validation** — Verify numbers across multiple sources
    """)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Database Records", "100,000", "✅")
    with col2:
        st.metric("PDF Documents", "23", "✅")
    with col3:
        st.metric("Agents Active", "4 / 4", "🟢")

elif page == "🔗 Fusion Agent":  # ✨ Changed condition
    
    if "fusion_agent_loaded" not in st.session_state:  # ✨ Changed key
        st.session_state.fusion_agent_loaded = False
    
    from ui.fusion_chat import run_fusion_chat
    run_fusion_chat()