"""
NexusIQ AI — Configuration Management
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


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
    
    # Database (defaults to SQLite for zero-setup deployment)
    database_url: str = "sqlite:///data/sales.db"
    
    # Vector Store (ChromaDB)
    chroma_persist_directory: str = "./data/chroma_db"
    
    # App
    environment: str = "development"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()