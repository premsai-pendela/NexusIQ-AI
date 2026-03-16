"""
NexusIQ AI — Configuration Management
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # LLM Settings
    google_api_key: str
    groq_api_key: str = ""
    default_llm: str = "gemini"
    gemini_model: str = "gemini-2.5-flash"  # ← Updated this
    
    # Database
    database_url: str
    
    # Vector Store
    chroma_persist_directory: str = "./data/chroma_db"
    
    # App
    environment: str = "development"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()