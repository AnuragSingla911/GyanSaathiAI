# GyanSaathiAI Agent - Question Generation Pipeline Technical Specification

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [API Specifications](#api-specifications)
6. [Data Models](#data-models)
7. [Pipeline States and Workflow](#pipeline-states-and-workflow)
8. [Validation Framework](#validation-framework)
9. [Dependencies](#dependencies)
10. [Configuration](#configuration)
11. [Deployment](#deployment)
12. [Performance Considerations](#performance-considerations)
13. [Monitoring and Observability](#monitoring-and-observability)
14. [Error Handling](#error-handling)
15. [Security](#security)

## System Overview

The GyanSaathiAI Agent Question Generation Pipeline is a sophisticated AI-powered system built on LangChain/LangGraph framework that generates educational questions using Retrieval Augmented Generation (RAG). The system transforms educational content specifications into high-quality, validated questions across multiple subjects and difficulty levels.

### Key Features
- **Multi-Modal Question Generation**: Supports multiple choice, short answer, true/false, and problem-solving questions
- **RAG-Powered Context**: Leverages vector embeddings and semantic search for grounded question generation
- **Comprehensive Validation**: Multi-stage validation including schema, grounding, mathematical accuracy, and safety checks
- **Batch Processing**: Concurrent generation of multiple questions with rate limiting
- **Database Integration**: Automatic persistence to MongoDB with tracing metadata
- **Real-time Health Monitoring**: Service health checks and observability

## Architecture

### System Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        UI[Admin UI]
        API[API Client]
    end
    
    subgraph "Agent Service Layer"
        FastAPI[FastAPI Server]
        Auth[Authentication]
        Middleware[CORS/Error Middleware]
    end
    
    subgraph "LangGraph Pipeline"
        Planner[Planner Node]
        Retriever[Retriever Node]
        Generator[Generator Node]
        Validator[Validator Node]
    end
    
    subgraph "AI Services"
        OpenAI[OpenAI GPT-4]
        Embeddings[OpenAI Embeddings]
    end
    
    subgraph "Data Layer"
        PGVector[(PGVector Store)]
        MongoDB[(MongoDB)]
        Redis[(Redis Cache)]
    end
    
    subgraph "External Systems"
        Backend[Backend Service]
        Corpus[Content Corpus]
    end
    
    UI --> FastAPI
    API --> FastAPI
    FastAPI --> Auth
    FastAPI --> Middleware
    FastAPI --> Planner
    
    Planner --> Retriever
    Retriever --> Generator
    Generator --> Validator
    
    Retriever --> PGVector
    PGVector --> Embeddings
    Generator --> OpenAI
    Validator --> MongoDB
    
    FastAPI --> Redis
    Backend --> MongoDB
    Corpus --> PGVector
```

### Technology Stack
- **Framework**: FastAPI with Python 3.9+
- **AI Orchestration**: LangChain + LangGraph
- **LLM**: OpenAI GPT-4 Turbo with JSON mode
- **Vector Database**: PostgreSQL with pgvector extension
- **Document Database**: MongoDB
- **Cache**: Redis
- **Embeddings**: OpenAI text-embedding-3-small
- **Data Validation**: Pydantic v2
- **Math Processing**: SymPy for mathematical validation

## Core Components

### 1. FastAPI Application (`main.py`)
The main application server providing RESTful APIs for question generation.

**Key Responsibilities:**
- Service lifecycle management with async context managers
- Health monitoring and status reporting
- CORS and error handling middleware
- Route management for generation, corpus management, and health checks

**Critical Endpoints:**
- `POST /admin/generate/question` - Single question generation
- `POST /admin/generate/batch` - Batch question generation (max 10)
- `POST /ingestEmbedding` - Corpus document ingestion
- `GET /corpus/search` - RAG corpus search
- `GET /health` - Service health status

### 2. LangGraph Question Generation Pipeline (`question_generator.py`)

A state-driven workflow engine implementing a four-stage question generation process:

#### Pipeline Nodes:

**Planner Node**
- Normalizes and validates input specifications
- Ensures required fields (subject, topic, difficulty, etc.)
- Standardizes input format for downstream processing

**Retriever Node**
- Queries RAG corpus using semantic search
- Implements fallback strategies for improved recall
- Filters by subject, class level, and educational metadata
- Returns top-K relevant document chunks

**Generator Node**
- Invokes OpenAI GPT-4 with structured prompts
- Uses JSON mode for guaranteed parseable output
- Generates questions with options, explanations, and solutions
- Includes citation tracking for content grounding

**Validator Node**
- Runs comprehensive validation suite
- Checks schema compliance, content grounding, safety
- Validates mathematical accuracy for STEM subjects
- Provides detailed scoring and feedback

### 3. RAG Retriever Service (`rag_retriever.py`)

**Architecture:**
- OpenAI embeddings (text-embedding-3-small) for vector generation
- PostgreSQL with pgvector extension for similarity search
- LangChain PGVector integration for seamless operations

**Features:**
- Metadata filtering by subject, class level, chapter
- Semantic similarity search with configurable thresholds
- Automatic collection management and cleanup
- Health monitoring and connection management

**Search Strategy:**
```python
# Primary search with metadata filters
results = vector_store.similarity_search(
    query=search_query,
    k=limit,
    filter={"subject": subject, "class": class_level}
)

# Fallback strategies for improved recall
if not results:
    # Remove subject constraint
    results = vector_store.similarity_search(query, k=limit)
```

### 4. Validation Framework (`validators.py`)

A comprehensive multi-validator system ensuring question quality:

#### Validator Types:

**Schema Validator**
- Validates question structure and required fields
- Checks option count, correct answer specification
- Ensures reasonable content lengths and formats

**Grounding Validator**
- Verifies question alignment with source citations
- Checks explanation-citation coherence
- Measures content overlap and relevance

**Math Solver Validator**
- Validates mathematical expressions using SymPy
- Checks numerical reasonableness of answers
- Ensures proper mathematical notation and syntax

**Deduplication Validator**
- Identifies potentially duplicate questions
- Checks for generic phrasing patterns
- Analyzes option similarity to prevent redundancy

**Safety Validator**
- Screens for inappropriate content and PII
- Implements content filtering policies
- Ensures educational appropriateness

**Difficulty Validator**
- Estimates question complexity using heuristics
- Validates against target difficulty levels
- Provides difficulty scoring metrics

## Data Flow

### Question Generation Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI Server
    participant P as Planner
    participant R as Retriever
    participant G as Generator
    participant V as Validator
    participant DB as MongoDB
    participant PG as PGVector
    participant AI as OpenAI

    C->>API: POST /admin/generate/question
    API->>P: Initialize pipeline with spec
    P->>P: Validate and normalize spec
    P->>R: Forward to retriever
    R->>PG: Search for relevant content
    PG-->>R: Return document chunks
    R->>G: Forward with context
    G->>AI: Generate question with prompts
    AI-->>G: Return structured question
    G->>V: Forward for validation
    V->>V: Run all validators
    V->>DB: Store question if valid
    V->>API: Return result
    API->>C: Question generation response
```

### Corpus Ingestion Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI Server
    participant RAG as RAG Retriever
    participant EMB as OpenAI Embeddings
    participant PG as PGVector

    C->>API: POST /ingestEmbedding
    API->>RAG: Process document
    RAG->>EMB: Generate embeddings
    EMB-->>RAG: Return vectors
    RAG->>PG: Store document + embeddings
    PG-->>RAG: Confirm storage
    RAG->>API: Return success
    API->>C: Ingestion complete
```

## API Specifications

### Question Generation API

#### Generate Single Question
```http
POST /admin/generate/question
Content-Type: application/json

{
  "subject": "math",
  "class_level": "8",
  "topic": "linear equations",
  "skills": ["algebra", "problem_solving"],
  "difficulty": "medium",
  "style": "standard",
  "question_type": "multiple_choice",
  "context": "Optional additional context"
}
```

**Response:**
```json
{
  "success": true,
  "question": {
    "stem": "Solve for x: 2x + 3 = 11",
    "options": [
      {"id": "a", "text": "x = 4"},
      {"id": "b", "text": "x = 5"},
      {"id": "c", "text": "x = 3"},
      {"id": "d", "text": "x = 6"}
    ],
    "correct_option_ids": ["a"],
    "question_type": "multiple_choice",
    "canonical_solution": "2x + 3 = 11\n2x = 8\nx = 4",
    "explanation": "This tests linear equation solving skills",
    "difficulty": "medium",
    "tags": ["math", "linear equations", "medium"]
  },
  "validation_results": {
    "schema": {"passed": true, "score": 1.0},
    "grounding": {"passed": true, "score": 0.9},
    "math_solver": {"passed": true, "score": 1.0}
  },
  "metadata": {
    "model_version": "gpt-4-turbo-preview",
    "prompt_version": "v1.0",
    "trace_id": "uuid-trace-id",
    "mongodb_id": "document-id"
  }
}
```

#### Batch Generation
```http
POST /admin/generate/batch
Content-Type: application/json

[
  {"subject": "math", "topic": "algebra", "difficulty": "easy"},
  {"subject": "science", "topic": "physics", "difficulty": "medium"}
]
```

### Corpus Management API

#### Ingest Document
```http
POST /ingestEmbedding
Content-Type: application/json

{
  "content": "Document content text...",
  "metadata": {
    "subject": "math",
    "class": "8",
    "chapter": "Algebra",
    "title": "Linear Equations",
    "skills": ["algebra", "problem_solving"]
  }
}
```

#### Search Corpus
```http
GET /corpus/search?query=linear%20equations&subject=math&class_level=8&limit=5
```

## Data Models

### Core Schemas (`schemas.py`)

```python
class QuestionCandidate(BaseModel):
    question_id: Optional[str] = None
    stem: str = Field(..., description="The main question text")
    options: List[QuestionOption] = Field(default_factory=list)
    correct_option_ids: List[str] = Field(default_factory=list)
    question_type: str = Field(default="multiple_choice")
    canonical_solution: Optional[str] = None
    explanation: Optional[str] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    difficulty: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    skill_ids: List[str] = Field(default_factory=list)

class QuestionGenerationRequest(BaseModel):
    subject: str
    class_level: Optional[str] = None
    topic: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard", "adaptive"] = "medium"
    style: Optional[str] = None
    question_type: Literal["multiple_choice", "short_answer", "true_false", "problem_solving"] = "multiple_choice"
    context: Optional[str] = None

class ValidationResult(BaseModel):
    validator_name: str
    passed: bool
    score: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
```

### Database Schemas

#### MongoDB Question Document
```json
{
  "_id": "ObjectId",
  "questionText": "Question stem",
  "options": [
    {"id": "a", "text": "Option A"},
    {"id": "b", "text": "Option B"}
  ],
  "correctAnswer": "a",
  "explanation": "Detailed explanation",
  "subject": "math",
  "topic": "algebra",
  "difficulty": "medium",
  "question_type": "multiple_choice",
  "generated_by": "ai_agent_v1.0",
  "generated_at": "2024-01-01T00:00:00Z",
  "trace_id": "uuid",
  "validation_results": {
    "schema": {"passed": true, "score": 1.0},
    "grounding": {"passed": true, "score": 0.9}
  }
}
```

#### PGVector Corpus Document
```sql
-- langchain_pg_collection table
CREATE TABLE langchain_pg_collection (
    uuid UUID PRIMARY KEY,
    name VARCHAR,
    cmetadata JSONB
);

-- langchain_pg_embedding table
CREATE TABLE langchain_pg_embedding (
    id BIGSERIAL PRIMARY KEY,
    collection_id UUID REFERENCES langchain_pg_collection(uuid),
    embedding VECTOR(1536),  -- OpenAI embedding dimension
    document TEXT,
    cmetadata JSONB
);
```

## Pipeline States and Workflow

### State Machine
```python
class QuestionGenerationState:
    spec: Dict[str, Any] = {}           # Input specification
    retrieved_chunks: List[Dict] = []    # RAG results
    question_candidate: QuestionCandidate = None  # Generated question
    validation_results: Dict[str, ValidationResult] = {}  # Validation outcomes
    status: str = "initialized"         # Current state
    error: Optional[str] = None         # Error information
    trace_id: str                       # Unique trace identifier
    generation_time_ms: int = 0         # Performance metrics
```

### State Transitions
1. `initialized` → `planned` (Planner validates input)
2. `planned` → `retrieved` (Retriever finds context)
3. `retrieved` → `generated` (Generator creates question)
4. `generated` → `success/validation_failed` (Validator checks quality)
5. Any state → `error` (Exception handling)

### Workflow Configuration
```python
workflow = StateGraph(dict)
workflow.add_node("planner", planner_node)
workflow.add_node("retriever", retriever_node)
workflow.add_node("generator", generator_node)
workflow.add_node("validator", validator_node)

workflow.add_edge(START, "planner")
workflow.add_edge("planner", "retriever")
workflow.add_edge("retriever", "generator")
workflow.add_edge("generator", "validator")
workflow.add_edge("validator", END)
```

## Validation Framework

### Validation Pipeline
Each question undergoes comprehensive validation with configurable thresholds:

| Validator | Purpose | Pass Threshold | Key Metrics |
|-----------|---------|----------------|-------------|
| Schema | Structure validation | 0.7 | Field completeness, format compliance |
| Grounding | Citation alignment | 0.6 | Content overlap, source relevance |
| Math Solver | Mathematical accuracy | 0.7 | Expression validity, numerical reasonableness |
| Deduplication | Uniqueness check | 0.6 | Generic pattern detection, similarity analysis |
| Safety | Content appropriateness | 0.8 | PII detection, inappropriate content |
| Difficulty | Complexity estimation | 0.6 | Text complexity, cognitive load |

### Validation Scoring
```python
# Example validation result
ValidationResult(
    validator_name="schema",
    passed=True,
    score=0.95,
    details={
        "issues": [],
        "option_count": 4,
        "stem_length": 45
    }
)
```

## Dependencies

### Core Dependencies (`requirements.txt`)
```txt
# Server Framework
fastapi
uvicorn[standard]

# AI/ML Stack
langchain
langgraph
langchain-openai
langchain-community
openai

# Data Processing
pydantic
pydantic-settings
numpy
sympy

# Database Drivers
psycopg2-binary
pgvector
pymongo
redis

# HTTP Client
httpx
```

### System Dependencies
- **Python**: 3.9+ (required for modern typing features)
- **PostgreSQL**: 12+ with pgvector extension
- **MongoDB**: 4.4+ for document storage
- **Redis**: 6+ for caching and session management

## Configuration

### Environment Configuration (`config.py`)
```python
class Settings(BaseSettings):
    # Database URLs
    postgres_url: str = "postgresql://user:pass@host:5432/db"
    mongo_url: str = "mongodb://user:pass@host:27017/db"
    redis_url: str = "redis://host:6379"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"
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
```

### Prompt Configuration
Prompts are stored in `/src/prompts/` directory:
- `question_generation_system.txt` - System prompt for LLM
- `question_generation_user.txt` - User prompt template
- `explanation_generation_system.txt` - Explanation prompts
- `hint_generation_system.txt` - Hint generation prompts

## Deployment

### Docker Configuration
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY data/ ./data/

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose Integration
```yaml
services:
  agent:
    build: ./agent
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - POSTGRES_URL=postgresql://tutor_user:tutor_password@postgres:5432/tutor_db
      - MONGO_URL=mongodb://admin:admin123@mongodb:27017/tutor_content
    depends_on:
      - postgres
      - mongodb
      - redis
```

### Health Checks
```python
@app.get("/health")
async def health_check():
    return HealthResponse(
        status="healthy",
        services={
            "rag_retriever": "healthy",
            "question_validator": "healthy",
            "question_graph": "healthy"
        },
        version="1.0.0"
    )
```

## Performance Considerations

### Optimization Strategies

**Concurrent Processing**
- Batch generation uses `asyncio.gather()` for parallel processing
- Maximum batch size limited to 10 to prevent resource exhaustion
- Request timeout controls to prevent hanging operations

**Caching Strategy**
- Prompt templates cached in memory after first load
- Vector embeddings stored persistently in PGVector
- Redis used for session and temporary data caching

**Resource Management**
- Connection pooling for database connections
- Async context managers for proper resource cleanup
- Memory-efficient document processing with streaming

### Performance Metrics
| Operation | Target Latency | Throughput |
|-----------|----------------|------------|
| Single question generation | < 10 seconds | 6 questions/minute |
| Batch generation (10 questions) | < 30 seconds | 20 questions/minute |
| Corpus search | < 2 seconds | 30 searches/minute |
| Document ingestion | < 5 seconds | 12 documents/minute |

## Monitoring and Observability

### Logging Strategy
```python
# Structured logging with context
logger = logging.getLogger(__name__)
logger.info("🔄 Planner node executing...", extra={
    "trace_id": trace_id,
    "subject": spec["subject"],
    "difficulty": spec["difficulty"]
})
```

### Tracing Implementation
- Unique trace IDs for request tracking
- Pipeline state logging at each node
- Performance timing for bottleneck identification
- Validation result aggregation for quality metrics

### Health Monitoring
```python
def is_healthy() -> bool:
    checks = [
        rag_retriever.is_healthy(),
        question_validator is not None,
        question_graph is not None
    ]
    return all(checks)
```

## Error Handling

### Exception Hierarchy
```python
# Pipeline-specific exceptions
class QuestionGenerationError(Exception):
    """Base exception for question generation"""

class ValidationError(QuestionGenerationError):
    """Validation failed"""

class RetrievalError(QuestionGenerationError):
    """RAG retrieval failed"""

class GenerationTimeoutError(QuestionGenerationError):
    """Generation exceeded timeout"""
```

### Error Recovery
- Graceful degradation with fallback mock questions
- Retry logic with exponential backoff for transient failures
- Circuit breaker pattern for external service failures
- Comprehensive error logging with context preservation

### HTTP Error Responses
```json
{
  "success": false,
  "error": "Question generation failed: OpenAI API timeout",
  "validation_results": {},
  "metadata": {
    "trace_id": "uuid",
    "error_code": "GENERATION_TIMEOUT",
    "retry_count": 2
  }
}
```

## Security

### API Security
- CORS middleware configured for authorized origins
- Request rate limiting to prevent abuse
- Input validation using Pydantic models
- SQL injection prevention through parameterized queries

### Data Protection
- PII detection in validation pipeline
- Content filtering for inappropriate material
- Secure credential management through environment variables
- Database connection encryption

### Access Control
- Admin-only endpoints for question generation
- API key authentication for OpenAI services
- Database user privilege restrictions
- Audit logging for all generation activities

---

**Document Version**: 1.0  
**Last Updated**: January 2024  
**Maintained By**: GyanSaathiAI Development Team  
**Review Schedule**: Quarterly
