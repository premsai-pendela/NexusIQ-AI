"""
NexusIQ AI — Main Application
Full-screen Lottie loading for page transitions
"""
import streamlit as st
import time
import requests
from streamlit_lottie import st_lottie

# Page config
st.set_page_config(
    page_title="NexusIQ AI",
    page_icon="🧠",
    layout="wide"
)

# ═══════════════════════════════════════════════════════════
#  LOTTIE ANIMATION LOADER
# ═══════════════════════════════════════════════════════════

@st.cache_data
def load_lottie_url(url: str):
    """Load Lottie animation from URL"""
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

# Lottie animation URLs
LOTTIE_BRAIN = "https://lottie.host/embed/ff7e1ed4-8b9f-4b57-b926-4a3e7c5f5a88/LBg8D4lCYv.json"
LOTTIE_LOADING = "https://assets9.lottiefiles.com/packages/lf20_x62chJ.json"

# ═══════════════════════════════════════════════════════════
#  SIDEBAR NAVIGATION
# ═══════════════════════════════════════════════════════════

page = st.sidebar.radio(
    "🧠 NexusIQ AI",
    ["🏠 Home", "🗄️ SQL Agent"]
)

# ═══════════════════════════════════════════════════════════
#  HOME PAGE
# ═══════════════════════════════════════════════════════════

if page == "🏠 Home":
    st.title("🧠 NexusIQ AI")
    st.subheader("Multi-Source Business Intelligence Agent System")
    
    st.markdown("""
    ### 🎯 What We Do
    NexusIQ AI autonomously answers business questions by investigating across 
    multiple data sources in minutes instead of days.
    
    ### 🚀 Features
    - 🗄️ **SQL Agent** — Query 100K+ transactions in plain English
    - 📄 **RAG Agent** — Search through business documents *(Coming Week 1)*
    - 🌐 **Web Agent** — Scrape competitor data *(Coming Week 2)*
    - 📊 **Data Agent** — Analyze CSVs and sentiment *(Coming Week 2)*
    """)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Database Records", "100,000", "✅")
    with col2:
        st.metric("Agents Built", "1 / 6", "+1 this week")
    with col3:
        st.metric("Status", "Active", "🟢")

# ═══════════════════════════════════════════════════════════
#  SQL AGENT PAGE — FULL SCREEN LOADING
# ═══════════════════════════════════════════════════════════

elif page == "🗄️ SQL Agent":
    
    # Session state for loading
    if "sql_agent_loaded" not in st.session_state:
        st.session_state.sql_agent_loaded = False
    
    # FULL SCREEN LOADING ANIMATION
    if not st.session_state.sql_agent_loaded:
        
        # Hide everything else with custom CSS
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] {display: none;}
        .stApp > header {display: none;}
        </style>
        """, unsafe_allow_html=True)
        
        # Full screen loading container
        loading_col1, loading_col2, loading_col3 = st.columns([1, 2, 1])
        
        with loading_col2:
            st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
            
            st.markdown("""
            <h1 style='text-align: center; color: #4A90D9;'>
                🧠 NexusIQ AI
            </h1>
            <h3 style='text-align: center; color: #888;'>
                Loading SQL Agent...
            </h3>
            """, unsafe_allow_html=True)
            
            # Lottie animation
            lottie_json = load_lottie_url(LOTTIE_LOADING)
            if lottie_json:
                st_lottie(lottie_json, height=250, key="loading_brain")
            else:
                # Fallback spinner
                st.markdown("""
                <div style='text-align: center; font-size: 80px; animation: pulse 1s infinite;'>
                    🧠
                </div>
                <style>
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                </style>
                """, unsafe_allow_html=True)
            
            st.markdown("""
            <p style='text-align: center; color: #888;'>
                💡 Initializing AI models and database connection...
            </p>
            """, unsafe_allow_html=True)
            
            # Progress bar
            progress = st.progress(0)
            for i in range(100):
                time.sleep(0.012)
                progress.progress(i + 1)
        
        # Mark as loaded
        st.session_state.sql_agent_loaded = True
        st.rerun()
    
    else:
        # LOAD THE ACTUAL SQL CHAT INTERFACE
        exec(open("ui/sql_chat.py").read())