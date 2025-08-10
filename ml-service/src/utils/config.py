import os
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Server settings
    port: int = 8001
    debug: bool = False
    
    # Model settings
    model_name: str = "microsoft/DialoGPT-medium"
    model_cache_dir: str = "./cache"
    model_max_length: int = 512
    
    # Generation settings
    max_questions_per_batch: int = 10
    generation_temperature: float = 0.7
    generation_max_tokens: int = 256
    
    # Database settings
    mongodb_url: str = "mongodb://admin:admin123@localhost:27017/tutor_content?authSource=admin"
    postgres_url: str = "postgresql://tutor_user:tutor_password@localhost:5432/tutor_db"
    
    # Redis settings
    redis_url: str = "redis://localhost:6379"
    cache_ttl: int = 3600  # 1 hour
    
    # OpenAI settings (fallback)
    openai_api_key: str = ""
    use_openai_fallback: bool = False
    
    # Hugging Face settings
    hf_token: str = ""
    hf_cache_dir: str = "./cache/huggingface"
    
    # MLflow settings
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    mlflow_experiment_name: str = "tutor_content_generation"
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()