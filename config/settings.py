"""
NexusIQ AI — Configuration Management
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # LLM Settings
    google_api_key: str
    groq_api_key: str = ""
    
    # Model selection
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_pro_model: str = "gemini-2.5-pro"
    gemini_flash_model: str = "gemini-2.5-flash"
    default_llm: str = "gemini"
    gemini_model: str = "gemini-2.5-flash-lite"  # ✅ Updated
    
    # Rate limiting
    max_requests_per_minute: int = 25  # Stay under 30 RPM limit
    
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