"""
NexusIQ AI — Configuration Management
"""
import os
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional

# Load Streamlit Cloud secrets into env vars so pydantic_settings can read them
try:
    import streamlit as st
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k.upper(), str(_v))
except Exception:
    pass


class Settings(BaseSettings):
    # API Keys — defaults to "" so the app loads even without secrets configured
    google_api_key: str = ""
    groq_api_key: str = ""
    
    # Model names
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_pro_model: str = "gemini-2.5-pro"
    gemini_flash_model: str = "gemini-2.5-flash"
    ollama_model: str = "deepseek-r1:1.5b"  # ✨ Added (was missing)
    
    # Legacy/compatibility fields (keep for backward compatibility)
    default_llm: str = "gemini"
    gemini_model: str = "gemini-2.5-flash-lite"
    
    # ✨ NEW: Gemini Pro Feature Flags
    use_gemini_pro: bool = False  # Disabled by default (free tier exhausts fast)
    ENABLE_WEB_AGENT: bool = os.getenv("ENABLE_WEB_AGENT", "true").lower() == "true"
    gemini_pro_max_retries: int = 0  # No retries when enabled
    gemini_pro_timeout: int = 8  # Fast fail (seconds)
    gemini_flash_max_retries: int = 1  # Flash can retry once
    gemini_flash_timeout: int = 15  # Flash gets more time (seconds)

    # ✨ RAG-specific settings
    rag_similarity_threshold: float = 0.5  # Cosine similarity threshold (0-1)
    rag_max_chunks: int = 5  # Max chunks to retrieve
    rag_chunk_size: int = 800  # Characters per chunk
    rag_chunk_overlap: int = 150  # Overlap characters
    
    # Rate limiting
    max_requests_per_minute: int = 25  # Stay under 30 RPM limit
    
    # Relational source: PostgreSQL only. Production/local demo configuration
    # supplies the Supabase URL via DATABASE_URL; SQLite snapshots are retired.
    database_url: str = "postgresql://nagapremsaipendela@localhost:5432/nexusiq_db"

    @field_validator("database_url")
    @classmethod
    def relational_source_must_be_postgresql(cls, value: str) -> str:
        """Do not silently fall back to a stale local SQLite sales snapshot."""
        if not value.lower().startswith(("postgresql://", "postgresql+")):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL/Supabase connection URL; "
                "local SQLite relational sources are retired."
            )
        return value
    
    # Vector Store (ChromaDB)
    chroma_persist_directory: str = "./data/chroma_db"
    
    # App
    environment: str = "development"
    log_level: str = "INFO"
    web_allow_sample_fallback: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
