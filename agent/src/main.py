from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

# Removed langserve import - using direct FastAPI endpoints
# from langserve import add_routes
from langchain.schema import BaseMessage
from langchain_core.runnables import RunnableLambda

from .services.enhanced_generator import EnhancedQuestionGenerator
from .services.hendrycks_dataset import HendrycksDatasetManager
from .services.rag_retriever import RAGRetriever
from .services.validators import EnhancedQuestionValidator
from .models.schemas import (
    QuestionGenerationRequest,
    QuestionCandidate,
    GenerationResult,
    HealthResponse
)
from .utils.config import get_settings
from .utils.tracing import setup_tracing
from langchain_community.vectorstores.pgvector import PGVector

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global services
rag_retriever: Optional[RAGRetriever] = None
enhanced_validator: Optional[EnhancedQuestionValidator] = None
enhanced_generator: Optional[EnhancedQuestionGenerator] = None
hendrycks_manager: Optional[HendrycksDatasetManager] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global rag_retriever, enhanced_validator, enhanced_generator, hendrycks_manager
    
    settings = get_settings()
    
    # Initialize services
    logger.info("Initializing GyanSaathiAI Agent v2 services...")
    
    # Initialize RAG retriever
    rag_retriever = RAGRetriever(
        postgres_url=settings.postgres_url,
        openai_api_key=settings.openai_api_key
    )
    await rag_retriever.initialize()
    
    # Initialize dedicated PGVector collection for math exemplars
    exemplar_vector_store = PGVector(
        connection_string=settings.postgres_url,
        embedding_function=rag_retriever.embeddings,
        collection_name="math_exemplars"
    )
    logger.info("✅ Connected to PGVector for math exemplars (collection: math_exemplars)")
    
    # Initialize Hendrycks dataset manager (uses dedicated exemplar vector store)
    hendrycks_manager = HendrycksDatasetManager(
        vector_store=exemplar_vector_store
    )
    
    # Initialize MongoDB client for validator and persistence
    from pymongo import MongoClient
    mongo_client = MongoClient(settings.mongo_url)
    
    # Initialize validator (v2 only)
    enhanced_validator = EnhancedQuestionValidator(settings, mongo_client)
    
    # Initialize v2 generator only
    enhanced_generator = EnhancedQuestionGenerator(
        rag_retriever=rag_retriever,
        hendrycks_manager=hendrycks_manager,
        mongo_client=mongo_client,  # Enable MongoDB persistence
        vector_store=rag_retriever.vector_store if rag_retriever else None
    )
    
    # Setup tracing
    setup_tracing()
    
    logger.info("✅ Agent v2 services initialized successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down agent services...")
    if rag_retriever:
        await rag_retriever.close()
    if mongo_client:
        mongo_client.close()

app = FastAPI(
    title="GyanSaathiAI Agent",
    description="LangChain/LangGraph agent for question generation and content processing",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services_status = {
        "rag_retriever": "healthy" if rag_retriever and rag_retriever.is_healthy() else "unhealthy",
        "enhanced_validator": "healthy" if enhanced_validator else "unhealthy",
        "enhanced_generator": "healthy" if enhanced_generator else "unhealthy",
        "hendrycks_manager": "healthy" if hendrycks_manager else "unhealthy"
    }
    
    overall_status = "healthy" if all(status == "healthy" for status in services_status.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        services=services_status,
        version="2.0.0"
    )

# v1 single-question endpoint removed

@app.post("/ingestEmbedding")
async def ingest_embedding(request: dict):
    """Ingest a document with embeddings into the vector database"""
    try:
        if not rag_retriever:
            raise HTTPException(status_code=503, detail="RAG retriever not available")
        
        # Extract document content and metadata
        content = request.get("content")
        metadata = request.get("metadata", {})
        
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")
        
        logger.info(f"Ingesting document: {metadata.get('title', 'Untitled')}")
        
        # Use the RAG retriever's vector store to add the document
        from langchain.schema import Document
        
        # Create LangChain Document
        doc = Document(
            page_content=content,
            metadata=metadata
        )
        
        # Add to vector store
        await rag_retriever.vector_store.aadd_documents([doc])
        
        logger.info(f"✅ Document ingested successfully")
        
        return {
            "success": True,
            "message": "Document ingested successfully",
            "metadata": metadata
        }
        
    except Exception as e:
        logger.error(f"Error ingesting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest document: {str(e)}")

@app.post("/ingestSampleCorpus")
async def ingest_sample_corpus():
    """Ingest sample corpus data for testing"""
    try:
        if not rag_retriever:
            raise HTTPException(status_code=503, detail="RAG retriever not available")
        
        logger.info("Ingesting sample corpus...")
        
        # Read sample corpus from JSON file
        import json
        import os
        
        # Path to the sample corpus JSON file
        json_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_corpus.json")
        
        if not os.path.exists(json_path):
            raise HTTPException(status_code=404, detail="Sample corpus file not found")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            corpus_data = json.load(f)
        
        documents = corpus_data.get("documents", [])
        logger.info(f"Found {len(documents)} documents in sample corpus")
        
        # Ingest each document
        ingested_count = 0
        for doc in documents:
            try:
                await ingest_embedding(doc)
                ingested_count += 1
                logger.info(f"✅ Ingested document: {doc['metadata'].get('title', 'Untitled')}")
            except Exception as e:
                logger.error(f"Failed to ingest document: {e}")
                continue
        
        logger.info(f"✅ Sample corpus ingestion completed. Successfully ingested {ingested_count}/{len(documents)} documents")
        
        return {
            "success": True,
            "message": "Sample corpus ingested successfully",
            "documents_count": ingested_count,
            "total_documents": len(documents),
            "corpus_metadata": corpus_data.get("metadata", {})
        }
        
    except Exception as e:
        logger.error(f"Error ingesting sample corpus: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest sample corpus: {str(e)}")

# v1 batch generation endpoint removed

@app.post("/admin/add-question", response_model=Dict[str, Any])
async def add_generated_question(question_data: Dict[str, Any]):
    """ADMIN ONLY: Add a generated question to the database for student use"""
    try:
        # Import MongoDB connection here to avoid circular imports
        from pymongo import MongoClient
        from .utils.config import get_settings
        
        settings = get_settings()
        mongo_client = MongoClient(settings.mongo_url)
        db = mongo_client.get_default_database()
        
        # Add metadata
        question_data["created_at"] = datetime.utcnow()
        question_data["created_by"] = "ai_agent"
        question_data["status"] = "active"
        
        # Insert into questions collection
        result = db.questions.insert_one(question_data)
        
        logger.info(f"Question added to database with ID: {result.inserted_id}")
        
        return {
            "success": True,
            "message": "Question added successfully",
            "question_id": str(result.inserted_id),
            "question": question_data
        }
        
    except Exception as e:
        logger.error(f"Error adding question to database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add question: {str(e)}")

@app.get("/corpus/search")
async def search_corpus(
    query: str,
    subject: Optional[str] = None,
    class_level: Optional[str] = None,
    limit: int = 10
):
    """Search RAG corpus for relevant content"""
    if not rag_retriever:
        raise HTTPException(status_code=503, detail="RAG retriever not available")
    
    try:
        results = await rag_retriever.search(
            query=query,
            subject=subject,
            class_level=class_level,
            limit=limit
        )
        
        return {
            "success": True,
            "results": results,
            "total_found": len(results)
        }
    
    except Exception as e:
        logger.error(f"Error searching corpus: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Corpus search failed: {str(e)}")

# Enhanced v2 API Endpoints

@app.post("/ingestExemplars")
async def ingest_exemplars(request: Dict[str, Any]):
    """Ingest Hendrycks MATH dataset as exemplars"""
    if not hendrycks_manager:
        raise HTTPException(status_code=503, detail="Hendrycks dataset manager not available")
    
    try:
        logger.info("Starting Hendrycks MATH dataset ingestion...")
        
        # Load all subjects from Hendrycks dataset
        datasets = await hendrycks_manager.load_all_subjects()
        
        # Get configuration
        max_per_subject = request.get("max_per_subject", 1000)
        
        # Ingest into MongoDB and vector store
        # Ingest with user-specified limit and force reload option
        force_reload = request.get("force_reload", False)
        ingestion_stats = await hendrycks_manager.ingest_datasets(datasets, max_per_subject, force_reload)
        
        return {
            "success": True,
            "message": "Hendrycks MATH dataset ingested successfully",
            "ingestion_stats": ingestion_stats,
            "total_ingested": sum(ingestion_stats.values())
        }
        
    except Exception as e:
        logger.error(f"Error ingesting Hendrycks dataset: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest exemplars: {str(e)}")

@app.get("/exemplars/stats")
async def get_exemplar_stats():
    """Get statistics about ingested exemplars"""
    if not hendrycks_manager:
        raise HTTPException(status_code=503, detail="Hendrycks dataset manager not available")
    
    try:
        stats = await hendrycks_manager.get_exemplar_stats()
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting exemplar stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get exemplar stats: {str(e)}")

@app.post("/admin/generate/question/v2", response_model=GenerationResult)
async def generate_question_v2(request: QuestionGenerationRequest):
    """ADMIN ONLY: Generate question using enhanced v2 pipeline with exemplars"""
    if not enhanced_generator:
        raise HTTPException(status_code=503, detail="Enhanced question generator not available")
    
    try:
        logger.info(f"Admin generating question v2 for: {request.subject}/{request.topic}")
        
        # Convert request to spec
        spec = {
            "subject": request.subject,
            "class_level": request.class_level,
            "topic": request.topic,
            "skills": request.skills,
            "difficulty": request.difficulty,
            "style": request.style,
            "question_type": request.question_type,
            "context": request.context
        }
        
        # Run enhanced generation pipeline
        result = await enhanced_generator.generate_question(spec)
        
        if result.get("status") == "success":
            question = result.get("question_candidate")
            
            if not question:
                return GenerationResult(
                    success=False,
                    error="No question generated",
                    validation_results=result.get("validation_results", {}),
                    metadata={
                        "version": "v2",
                        "trace_id": result.get("trace_id"),
                        "orchestration_path": result.get("orchestration_path"),
                        "retrieval_confidence": result.get("retrieval_confidence")
                    }
                )
            
            return GenerationResult(
                success=True,
                question=question,
                validation_results=result.get("validation_results", {}),
                metadata={
                    "version": "v2",
                    "trace_id": result.get("trace_id"),
                    "generation_time_ms": result.get("generation_time_ms"),
                    "orchestration_path": result.get("orchestration_path"),
                    "retrieval_confidence": result.get("retrieval_confidence"),
                    "template_used": result.get("metadata", {}).get("template_used"),
                    "validation_passed": result.get("metadata", {}).get("validation_passed")
                }
            )
        else:
            return GenerationResult(
                success=False,
                error=result.get("error", "Unknown error"),
                validation_results={},
                metadata={
                    "version": "v2",
                    "trace_id": result.get("trace_id")
                }
            )
            
    except Exception as e:
        logger.error(f"Error in v2 question generation: {str(e)}")
        return GenerationResult(
            success=False,
            error=f"v2 generation failed: {str(e)}",
            metadata={"version": "v2"}
        )

@app.post("/admin/generate/batch/v2", response_model=List[GenerationResult])
async def generate_batch_questions_v2(requests: List[QuestionGenerationRequest]):
    """ADMIN ONLY: Generate multiple questions using v2 pipeline"""
    if not enhanced_generator:
        raise HTTPException(status_code=503, detail="Enhanced question generator not available")
    
    if len(requests) > 5:  # Stricter limit for v2 due to complexity
        raise HTTPException(status_code=400, detail="v2 batch size limited to 5 questions")
    
    try:
        # Generate questions concurrently
        tasks = [generate_question_v2(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        formatted_results = []
        for result in results:
            if isinstance(result, Exception):
                formatted_results.append(GenerationResult(
                    success=False,
                    error=str(result),
                    validation_results={},
                    metadata={"version": "v2"}
                ))
            else:
                formatted_results.append(result)
        
        return formatted_results
    
    except Exception as e:
        logger.error(f"Error in v2 batch generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"v2 batch generation failed: {str(e)}")

@app.get("/admin/config")
async def get_agent_config():
    """ADMIN ONLY: Get current agent configuration"""
    settings = get_settings()
    
    return {
        "success": True,
        "config": {
            "exemplar_k": settings.exemplar_k,
            "retrieval_tau": settings.retrieval_tau,
            "novelty_max_overlap": settings.novelty_max_overlap,
            "dedup_cosine_threshold": settings.dedup_cosine_threshold,
            "max_retries": settings.max_retries,
            "template_confidence_threshold": settings.template_confidence_threshold,
            "difficulty_classifier_threshold": settings.difficulty_classifier_threshold,
            "grounding_min_score": settings.grounding_min_score,
            "generation_model": settings.openai_model,
            "generation_temperature": settings.generation_temperature
        },
        "version": "v2"
    }

@app.post("/admin/validate")
async def validate_question(question_data: Dict[str, Any]):
    """ADMIN ONLY: Validate a question using enhanced validator"""
    if not enhanced_validator:
        raise HTTPException(status_code=503, detail="Enhanced validator not available")
    
    try:
        # Convert dict to QuestionCandidate
        from .models.schemas import QuestionCandidate
        question = QuestionCandidate(**question_data.get("question", {}))
        spec = question_data.get("spec", {})
        
        # Run validation with auto-fix
        validation_results, fixed_question = await enhanced_validator.validate_with_autofix(question, spec)
        
        return {
            "success": True,
            "validation_results": {
                name: {
                    "validator_name": result.validator_name,
                    "passed": result.passed,
                    "score": result.score,
                    "details": result.details,
                    "error_message": result.error_message
                }
                for name, result in validation_results.items()
            },
            "fixed_question": {
                "stem": fixed_question.stem,
                "options": [{"id": opt.id, "text": opt.text} for opt in fixed_question.options],
                "correct_option_ids": fixed_question.correct_option_ids,
                "explanation": fixed_question.explanation
            },
            "overall_passed": all(result.passed for result in validation_results.values())
        }
        
    except Exception as e:
        logger.error(f"Error in question validation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

# LangServe routes removed - using direct FastAPI endpoints instead
# Direct graph access available through /generate/* endpoints

# CORS middleware for development
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:80", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)