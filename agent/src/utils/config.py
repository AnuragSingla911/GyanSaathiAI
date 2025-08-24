"""
Configuration management for AI Tutor Agent
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Database URLs
    postgres_url: str = "postgresql://tutor_user:tutor_password@postgres:5432/tutor_db"
    mongo_url: str = "mongodb://admin:admin123@mongodb:27017/tutor_content?authSource=admin"
    redis_url: str = "redis://redis:6379"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None  # Will be loaded from environment variable
    openai_model: str = "gpt-5-nano"
    openai_embedding_model: str = "text-embedding-3-small"
    
    # Agent Configuration
    max_questions_per_batch: int = 10
    question_generation_timeout: int = 30
    max_retries: int = 3
    
    # RAG Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_context_length: int = 4000
    similarity_threshold: float = 0.7
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    """Get application settings"""
    settings = Settings()
    
    # Debug logging for API key
    import logging
    logger = logging.getLogger(__name__)
    
    # Check environment variables directly
    logger.info(f"Environment OPENAI_API_KEY present: {bool(os.getenv('OPENAI_API_KEY'))}")
    logger.info(f"Environment OPENAI_API_KEY length: {len(os.getenv('OPENAI_API_KEY', ''))}")
    if os.getenv('OPENAI_API_KEY'):
        logger.info(f"Environment OPENAI_API_KEY starts with: {os.getenv('OPENAI_API_KEY')[:10]}...")
    
    # Check what pydantic loaded
    logger.info(f"Pydantic loaded - OpenAI API Key present: {bool(settings.openai_api_key)}")
    logger.info(f"Pydantic loaded - OpenAI API Key length: {len(settings.openai_api_key) if settings.openai_api_key else 0}")
    if settings.openai_api_key:
        logger.info(f"Pydantic loaded - OpenAI API Key starts with: {settings.openai_api_key[:10]}...")
    
    return settings

# Global settings instance
settings = get_settings()
