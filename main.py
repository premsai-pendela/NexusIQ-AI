"""
NexusIQ AI — Main Application Entry Point
"""
import streamlit as st
from config.settings import settings

def main():
    st.set_page_config(
        page_title="NexusIQ AI",
        page_icon="🧠",
        layout="wide"
    )
    
    st.title("🧠 NexusIQ AI")
    st.subheader("Multi-Source Business Intelligence Agent")
    
    st.info("🚀 System is initializing... Coming soon!")
    
    # Show environment info
    with st.expander("⚙️ System Configuration"):
        st.write(f"**Environment:** {settings.environment}")
        st.write(f"**LLM:** {settings.default_llm}")
        st.write(f"**Database:** Connected ✅" if settings.database_url else "Not configured ❌")

if __name__ == "__main__":
    main()
