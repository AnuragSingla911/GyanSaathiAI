import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

from src.services.content_generator import ContentGeneratorService
from src.services.explanation_generator import ExplanationGeneratorService
from src.models.requests import (
    QuestionGenerationRequest,
    ExplanationRequest,
    FeedbackRequest,
    BatchQuestionRequest
)
from src.models.responses import (
    QuestionResponse,
    ExplanationResponse,
    FeedbackResponse,
    HealthResponse
)
from src.utils.config import get_settings
from src.utils.logging import setup_logging

# Setup logging
setup_logging()
logger = structlog.get_logger()

# Metrics
REQUEST_COUNT = Counter('ml_service_requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('ml_service_request_duration_seconds', 'Request duration')
GENERATION_COUNT = Counter('content_generation_total', 'Total content generations', ['type'])
ERROR_COUNT = Counter('ml_service_errors_total', 'Total errors', ['type'])

# Global services
content_generator = None
explanation_generator = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global content_generator, explanation_generator
    
    try:
        logger.info("Starting ML service...")
        settings = get_settings()
        
        # Initialize services
        content_generator = ContentGeneratorService()
        explanation_generator = ExplanationGeneratorService()
        
        # Load models
        await content_generator.initialize()
        await explanation_generator.initialize()
        
        logger.info("ML service started successfully")
        yield
        
    except Exception as e:
        logger.error("Failed to start ML service", error=str(e))
        raise
    finally:
        logger.info("Shutting down ML service...")

# Create FastAPI app
app = FastAPI(
    title="AI Tutor ML Service",
    description="Machine Learning service for generating educational content and explanations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get services
def get_content_generator() -> ContentGeneratorService:
    if content_generator is None:
        raise HTTPException(status_code=503, detail="Content generator not initialized")
    return content_generator

def get_explanation_generator() -> ExplanationGeneratorService:
    if explanation_generator is None:
        raise HTTPException(status_code=503, detail="Explanation generator not initialized")
    return explanation_generator

@app.middleware("http")
async def metrics_middleware(request, call_next):
    """Middleware to collect metrics"""
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path
    ).inc()
    
    with REQUEST_DURATION.time():
        response = await call_next(request)
    
    return response

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Check if services are initialized
        services_status = {
            "content_generator": content_generator is not None and content_generator.is_ready(),
            "explanation_generator": explanation_generator is not None and explanation_generator.is_ready()
        }
        
        all_healthy = all(services_status.values())
        
        return HealthResponse(
            status="healthy" if all_healthy else "degraded",
            services=services_status,
            version="1.0.0"
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/generate/question", response_model=QuestionResponse)
async def generate_question(
    request: QuestionGenerationRequest,
    generator: ContentGeneratorService = Depends(get_content_generator)
):
    """Generate a single question"""
    try:
        logger.info("Generating question", subject=request.subject, topic=request.topic)
        
        question = await generator.generate_question(
            subject=request.subject,
            topic=request.topic,
            difficulty=request.difficulty_level,
            question_type=request.question_type,
            grade_level=request.grade_level
        )
        
        GENERATION_COUNT.labels(type="question").inc()
        
        return QuestionResponse(
            success=True,
            question=question
        )
        
    except Exception as e:
        ERROR_COUNT.labels(type="question_generation").inc()
        logger.error("Question generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Question generation failed: {str(e)}")

@app.post("/generate/questions/batch", response_model=list[QuestionResponse])
async def generate_questions_batch(
    request: BatchQuestionRequest,
    generator: ContentGeneratorService = Depends(get_content_generator)
):
    """Generate multiple questions"""
    try:
        logger.info("Generating batch questions", count=request.count)
        
        questions = await generator.generate_questions_batch(
            subject=request.subject,
            topic=request.topic,
            difficulty=request.difficulty_level,
            question_type=request.question_type,
            grade_level=request.grade_level,
            count=request.count
        )
        
        GENERATION_COUNT.labels(type="question_batch").inc()
        
        return [QuestionResponse(success=True, question=q) for q in questions]
        
    except Exception as e:
        ERROR_COUNT.labels(type="batch_generation").inc()
        logger.error("Batch question generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {str(e)}")

@app.post("/generate/explanation", response_model=ExplanationResponse)
async def generate_explanation(
    request: ExplanationRequest,
    generator: ExplanationGeneratorService = Depends(get_explanation_generator)
):
    """Generate explanation for a question"""
    try:
        logger.info("Generating explanation", question_id=request.question_id)
        
        explanation = await generator.generate_explanation(
            question_text=request.question_text,
            correct_answer=request.correct_answer,
            student_answer=request.student_answer,
            explanation_type=request.explanation_type,
            learning_style=request.learning_style
        )
        
        GENERATION_COUNT.labels(type="explanation").inc()
        
        return ExplanationResponse(
            success=True,
            explanation=explanation
        )
        
    except Exception as e:
        ERROR_COUNT.labels(type="explanation_generation").inc()
        logger.error("Explanation generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Explanation generation failed: {str(e)}")

@app.post("/generate/feedback", response_model=FeedbackResponse)
async def generate_feedback(
    request: FeedbackRequest,
    generator: ExplanationGeneratorService = Depends(get_explanation_generator)
):
    """Generate personalized feedback"""
    try:
        logger.info("Generating feedback")
        
        feedback = await generator.generate_feedback(
            question_text=request.question_text,
            student_answer=request.student_answer,
            correct_answer=request.correct_answer,
            attempt_number=request.attempt_number,
            time_taken=request.time_taken
        )
        
        GENERATION_COUNT.labels(type="feedback").inc()
        
        return FeedbackResponse(
            success=True,
            feedback=feedback
        )
        
    except Exception as e:
        ERROR_COUNT.labels(type="feedback_generation").inc()
        logger.error("Feedback generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Feedback generation failed: {str(e)}")

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    ERROR_COUNT.labels(type="unhandled").inc()
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG") == "true" else "An unexpected error occurred"
        }
    )

if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )