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

from .services.question_generator import create_question_generation_graph
from .services.rag_retriever import RAGRetriever
from .services.validators import QuestionValidator
from .models.schemas import (
    QuestionGenerationRequest,
    QuestionCandidate,
    GenerationResult,
    HealthResponse
)
from .utils.config import get_settings
from .utils.tracing import setup_tracing

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global services
rag_retriever: Optional[RAGRetriever] = None
question_validator: Optional[QuestionValidator] = None
question_graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global rag_retriever, question_validator, question_graph
    
    settings = get_settings()
    
    # Initialize services
    logger.info("Initializing GyanSaathiAI Agent services...")
    
    rag_retriever = RAGRetriever(
        postgres_url=settings.postgres_url,
        openai_api_key=settings.openai_api_key
    )
    await rag_retriever.initialize()
    
    question_validator = QuestionValidator()
    question_graph = create_question_generation_graph(rag_retriever, question_validator)
    
    # Setup tracing
    setup_tracing()
    
    logger.info("✅ Agent services initialized successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down agent services...")
    if rag_retriever:
        await rag_retriever.close()

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
        "question_validator": "healthy" if question_validator else "unhealthy",
        "question_graph": "healthy" if question_graph else "unhealthy"
    }
    
    overall_status = "healthy" if all(status == "healthy" for status in services_status.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        services=services_status,
        version="1.0.0"
    )

@app.post("/admin/generate/question", response_model=GenerationResult)
async def generate_single_question(request: QuestionGenerationRequest):
    """ADMIN ONLY: Generate a single question using the LangGraph pipeline"""
    if not question_graph:
        raise HTTPException(status_code=503, detail="Question generation service not available")
    
    try:
        logger.info(f"Admin generating question for: {request.subject}/{request.topic}")
        
        # Debug: Log the API key being used
        from .utils.config import get_settings
        settings = get_settings()
        logger.info(f"OpenAI API Key (first 10 chars): {settings.openai_api_key[:10] if settings.openai_api_key else 'NOT_SET'}")
        logger.info(f"OpenAI API Key length: {len(settings.openai_api_key) if settings.openai_api_key else 0}")
        
        # Convert request to graph input
        graph_input = {
            "spec": {
                "subject": request.subject,
                "class": request.class_level,
                "topic": request.topic,
                "skills": request.skills,
                "difficulty": request.difficulty,
                "style": request.style,
                "question_type": request.question_type
            },
            "model_version": "gpt-5-nano",
            "prompt_version": "v1.0",
            "data_version": "v1.0"
        }
        
        # Run the generation graph
        result = await question_graph.ainvoke(graph_input)
        
        if result.get("status") == "success":
            # Use the question_candidate directly - it's already in the correct format
            print(result);
            question = result.get("question_candidate")
            
            # Ensure question exists before proceeding
            if not question:
                return GenerationResult(
                    success=False,
                    error="No question generated",
                    validation_results=result.get("validation_results", {}),
                    metadata={
                        "model_version": graph_input["model_version"],
                        "prompt_version": graph_input["prompt_version"],
                        "trace_id": result.get("trace_id")
                    }
                )
            
            # Auto-insert the generated question into MongoDB
            try:
                from pymongo import MongoClient
                from .utils.config import get_settings
                settings = get_settings()
                
                client = MongoClient(settings.mongo_url)
                db = client.get_default_database()
                questions_collection = db.questions
                
                # Convert validation results to MongoDB-compatible format
                validation_results_dict = {}
                if result.get("validation_results"):
                    for key, validation_result in result.get("validation_results").items():
                        validation_results_dict[key] = {
                            "validator_name": validation_result.validator_name,
                            "passed": validation_result.passed,
                            "score": validation_result.score,
                            "details": validation_result.details,
                            "error_message": validation_result.error_message
                        }
                
                # Convert to MongoDB document format
                question_doc = {
                    "questionText": question.stem,
                    "options": [{"id": opt.id, "text": opt.text} for opt in question.options],
                    "correctAnswer": question.correct_option_ids[0] if question.correct_option_ids else None,
                    "explanation": question.explanation,
                    "subject": request.subject,
                    "topic": request.topic,
                    "difficulty": request.difficulty,
                    "question_type": request.question_type,
                    "generated_by": "ai_agent_v1.0",
                    "generated_at": datetime.utcnow(),
                    "trace_id": result.get("trace_id"),
                    "validation_results": validation_results_dict
                }
                
                result_id = questions_collection.insert_one(question_doc).inserted_id
                logger.info(f"✅ Question saved to MongoDB with ID: {result_id}")
                client.close()
                
            except Exception as e:
                logger.error(f"Failed to save question to MongoDB: {e}")
                # Continue anyway - the question was generated successfully
            
            return GenerationResult(
                success=True,
                question=question,
                validation_results=result.get("validation_results", {}),
                metadata={
                    "model_version": graph_input["model_version"],
                    "prompt_version": graph_input["prompt_version"],
                    "trace_id": result.get("trace_id"),
                    "mongodb_id": str(result_id) if 'result_id' in locals() else None
                }
            )
        else:
            return GenerationResult(
                success=False,
                error=result.get("error", "Unknown error"),
                validation_results=result.get("validation_results", {}),
                metadata={
                    "model_version": graph_input["model_version"],
                    "prompt_version": graph_input["prompt_version"],
                    "trace_id": result.get("trace_id")
                }
            )
            
    except Exception as e:
        logger.error(f"Error generating question: {str(e)}")
        return GenerationResult(
            success=False,
            error=f"Question generation failed: {str(e)}",
            metadata={}
        )

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

@app.post("/admin/generate/batch", response_model=List[GenerationResult])
async def generate_batch_questions(requests: List[QuestionGenerationRequest]):
    """ADMIN ONLY: Generate multiple questions in batch"""
    if not question_graph:
        raise HTTPException(status_code=503, detail="Question generation service not available")
    
    if len(requests) > 10:  # Limit batch size
        raise HTTPException(status_code=400, detail="Batch size limited to 10 questions")
    
    try:
        # Generate questions concurrently
        tasks = [generate_single_question(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        formatted_results = []
        for result in results:
            if isinstance(result, Exception):
                formatted_results.append(GenerationResult(
                    success=False,
                    error=str(result),
                    validation_results={},
                    metadata={}
                ))
            else:
                formatted_results.append(result)
        
        return formatted_results
    
    except Exception as e:
        logger.error(f"Error in batch generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {str(e)}")

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

# LangServe routes removed - using direct FastAPI endpoints instead
# Direct graph access available through /generate/* endpoints

# CORS middleware for development
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)