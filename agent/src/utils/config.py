"""
Configuration management for TutorNestAI Agent
"""

import os
from typing import Optional

# Try to import pydantic_settings, fall back to regular dict-based config if not available
try:
    from pydantic_settings import BaseSettings
    PYDANTIC_AVAILABLE = True
except ImportError:
    try:
        # Try older pydantic import
        from pydantic import BaseSettings
        PYDANTIC_AVAILABLE = True
    except ImportError:
        PYDANTIC_AVAILABLE = False
        BaseSettings = object

if PYDANTIC_AVAILABLE:
    class Settings(BaseSettings):
        """Application settings with Pydantic"""
        
        # Database URLs
        postgres_url: str = "postgresql://tutor_user:tutor_password@postgres:5432/tutor_db"
        mongo_url: str = "mongodb://admin:admin123@mongodb:27017/tutor_content?authSource=admin"
        redis_url: str = "redis://redis:6379"
        
        # OpenAI Configuration
        openai_api_key: Optional[str] = None  # Will be loaded from environment variable
        openai_model: str = "gpt-4o-mini"
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
        
        # Enhanced Question Generation Config (v2)
        exemplar_k: int = 3
        retrieval_tau: float = 0.62
        novelty_max_overlap: float = 0.80
        dedup_cosine_threshold: float = 0.92
        
        # Template Inducer Config
        template_confidence_threshold: float = 0.75
        sympy_timeout_seconds: int = 30
        distractor_count: int = 3
        
        # Validator Config
        latex_render_timeout: int = 10
        difficulty_classifier_threshold: float = 0.7
        grounding_min_score: float = 0.6
        
        # Vector Search Config
        rerank_top_k: int = 10
        math_embedding_weight: float = 0.6
        text_embedding_weight: float = 0.4
        
        # LLM Generation Config  
        generation_temperature: float = 0.7
        # Cap to avoid length-limit errors and ensure JSON completes
        max_tokens: int = 700
        
        # Logging
        log_level: str = "INFO"

        # Airflow integration
        airflow_base_url: str = "http://airflow-webserver:8080"
        airflow_username: Optional[str] = None
        airflow_password: Optional[str] = None
        airflow_dag_id: str = "generate_questions_batch"
        
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
else:
    class Settings:
        """Application settings fallback (no Pydantic)"""
        
        def __init__(self):
            # Database URLs
            self.postgres_url = os.getenv("POSTGRES_URL", "postgresql://tutor_user:tutor_password@postgres:5432/tutor_db")
            self.mongo_url = os.getenv("MONGO_URL", "mongodb://admin:admin123@mongodb:27017/tutor_content?authSource=admin")
            self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
            
            # OpenAI Configuration
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
            self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.openai_embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            
            # Agent Configuration
            self.max_questions_per_batch = int(os.getenv("MAX_QUESTIONS_PER_BATCH", "10"))
            self.question_generation_timeout = int(os.getenv("QUESTION_GENERATION_TIMEOUT", "30"))
            self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
            
            # RAG Configuration
            self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
            self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
            self.max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "4000"))
            self.similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
            
            # Enhanced Question Generation Config (v2)
            self.exemplar_k = int(os.getenv("EXEMPLAR_K", "3"))
            self.retrieval_tau = float(os.getenv("RETRIEVAL_TAU", "0.62"))
            self.novelty_max_overlap = float(os.getenv("NOVELTY_MAX_OVERLAP", "0.80"))
            self.dedup_cosine_threshold = float(os.getenv("DEDUP_COSINE_THRESHOLD", "0.92"))
            
            # Template Inducer Config
            self.template_confidence_threshold = float(os.getenv("TEMPLATE_CONFIDENCE_THRESHOLD", "0.75"))
            self.sympy_timeout_seconds = int(os.getenv("SYMPY_TIMEOUT_SECONDS", "30"))
            self.distractor_count = int(os.getenv("DISTRACTOR_COUNT", "3"))
            
            # Validator Config
            self.latex_render_timeout = int(os.getenv("LATEX_RENDER_TIMEOUT", "10"))
            self.difficulty_classifier_threshold = float(os.getenv("DIFFICULTY_CLASSIFIER_THRESHOLD", "0.7"))
            self.grounding_min_score = float(os.getenv("GROUNDING_MIN_SCORE", "0.6"))
            
            # Vector Search Config
            self.rerank_top_k = int(os.getenv("RERANK_TOP_K", "10"))
            self.math_embedding_weight = float(os.getenv("MATH_EMBEDDING_WEIGHT", "0.6"))
            self.text_embedding_weight = float(os.getenv("TEXT_EMBEDDING_WEIGHT", "0.4"))
            
            # LLM Generation Config
            self.generation_temperature = float(os.getenv("GENERATION_TEMPERATURE", "0.7"))
            self.max_tokens = int(os.getenv("MAX_TOKENS", "700"))
            
            # Logging
            self.log_level = os.getenv("LOG_LEVEL", "INFO")

            # Airflow integration
            self.airflow_base_url = os.getenv("AIRFLOW_BASE_URL", "http://airflow-webserver:8080")
            self.airflow_username = os.getenv("AIRFLOW_USERNAME")
            self.airflow_password = os.getenv("AIRFLOW_PASSWORD")
            self.airflow_dag_id = os.getenv("AIRFLOW_DAG_ID", "generate_questions_batch")

def get_settings() -> Settings:
    """Get application settings"""
    settings = Settings()
    
    # Debug logging for API key
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Check environment variables directly
        logger.info(f"Using {'Pydantic' if PYDANTIC_AVAILABLE else 'fallback'} settings")
        logger.info(f"Environment OPENAI_API_KEY present: {bool(os.getenv('OPENAI_API_KEY'))}")
        logger.info(f"Environment OPENAI_API_KEY length: {len(os.getenv('OPENAI_API_KEY', ''))}")
        if os.getenv('OPENAI_API_KEY'):
            logger.info(f"Environment OPENAI_API_KEY starts with: {os.getenv('OPENAI_API_KEY')[:10]}...")
        
        # Check what was loaded
        logger.info(f"Settings loaded - OpenAI API Key present: {bool(settings.openai_api_key)}")
        logger.info(f"Settings loaded - OpenAI API Key length: {len(settings.openai_api_key) if settings.openai_api_key else 0}")
        if settings.openai_api_key:
            logger.info(f"Settings loaded - OpenAI API Key starts with: {settings.openai_api_key[:10]}...")
    except Exception as e:
        logger.error(f"Error in settings debug logging: {e}")
    
    return settings

# Global settings instance
settings = get_settings()
