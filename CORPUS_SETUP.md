# AI Tutor Corpus Setup with Embeddings

This guide explains how to set up the AI Tutor corpus with OpenAI embeddings using LangChain's pgvector integration.

## Overview

The corpus setup process:
1. **Database Migration**: Adds embeddings column and pgvector support
2. **Corpus Population**: Ingests sample educational content
3. **Embedding Generation**: Creates OpenAI embeddings for all content chunks
4. **RAG Testing**: Verifies the retrieval system works
5. **Question Generation Testing**: Ensures the full pipeline functions

## Prerequisites

- Docker and Docker Compose installed
- OpenAI API key
- Python 3.8+ with pip

## Quick Setup

### 1. Environment Configuration

```bash
# Copy environment template
cp env.template .env

# Edit .env and add your OpenAI API key
OPENAI_API_KEY=your_actual_openai_api_key_here
```

### 2. Run the Setup Script

```bash
# Make script executable (if not already)
chmod +x setup_corpus.sh

# Run the complete setup
./setup_corpus.sh
```

The script will:
- Check environment variables
- Start Docker services if needed
- Install Python dependencies
- Run the complete corpus pipeline

## Manual Setup

If you prefer to run steps manually:

### 1. Start Services

```bash
docker-compose up -d
```

### 2. Install Dependencies

```bash
cd agent
pip install -r requirements.txt
```

### 3. Run Corpus Pipeline

```bash
cd agent
python scripts/setup_corpus_pipeline.py
```

## Individual Components

### Corpus Ingestion

The enhanced `corpus_ingestion.py` uses LangChain's native pgvector integration:

- **OpenAI Embeddings**: Uses `text-embedding-3-small` model
- **PGVector Integration**: Automatically creates tables and manages embeddings
- **Smart Chunking**: Uses LangChain's `RecursiveCharacterTextSplitter`
- **Metadata Preservation**: Maintains subject, class, chapter, and skill information

### Sample Content

The system includes sample educational content for:

- **Mathematics**: Algebra fundamentals, linear/quadratic equations
- **Physics**: Newton's laws, energy, momentum
- **Chemistry**: Atomic structure, chemical bonding

### RAG Retriever

The `rag_retriever.py` provides:

- **Semantic Search**: Finds relevant content using embeddings
- **Metadata Filtering**: Filter by subject, class, chapter
- **Relevance Scoring**: Returns ranked results

### Question Generator

The `question_generator.py` creates:

- **Context-Aware Questions**: Based on retrieved content
- **Multiple Question Types**: Multiple choice, fill-in-the-blank
- **Difficulty Levels**: Easy, medium, hard
- **Explanations**: Detailed explanations for each answer

## Testing

### Test RAG Retriever

```bash
cd agent
python scripts/test_rag.py
```

### Test Question Generator

```bash
cd agent
python scripts/test_question_generator.py
```

## Database Schema

The system creates these tables:

- `corpus_documents`: Document metadata and content hashes
- `corpus_chunks`: Content chunks with embeddings (pgvector)
- `skills`: Skill definitions and mappings

## Troubleshooting

### Common Issues

1. **OpenAI API Key Missing**
   ```
   ❌ OPENAI_API_KEY environment variable is required
   ```
   Solution: Set your API key in the `.env` file

2. **Database Connection Failed**
   ```
   ❌ Failed to connect to database
   ```
   Solution: Ensure Docker services are running with `docker-compose ps`

3. **Embedding Generation Failed**
   ```
   ❌ OpenAI API error
   ```
   Solution: Check your API key and billing status

### Logs

Check logs for detailed error information:
```bash
docker-compose logs postgres
docker-compose logs agent
```

## Customization

### Adding New Content

To add your own educational content:

1. Modify `ingest_sample_corpus()` in `corpus_ingestion.py`
2. Add new documents with proper metadata
3. Run the ingestion again

### Changing Embedding Model

To use a different OpenAI embedding model:

```python
self.embeddings = OpenAIEmbeddings(
    openai_api_key=self.openai_api_key,
    model="text-embedding-3-large"  # Change model here
)
```

### Adjusting Chunk Size

Modify chunking parameters in `_chunk_document()`:

```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,    # Increase for longer chunks
    chunk_overlap=200,   # Increase for more overlap
    # ... other parameters
)
```

## Performance Considerations

- **Embedding Generation**: Can take time for large documents
- **Vector Search**: pgvector provides fast similarity search
- **Memory Usage**: Embeddings are stored in PostgreSQL with pgvector extension

## Security Notes

- Never commit your `.env` file with API keys
- Use environment variables in production
- Consider rate limiting for OpenAI API calls

## Next Steps

After successful setup:

1. **Test the API**: Use the FastAPI endpoints in `agent/src/main.py`
2. **Add Real Content**: Replace sample content with your curriculum
3. **Scale Up**: Add more subjects, classes, and topics
4. **Monitor Usage**: Track API usage and costs

## Support

For issues or questions:
1. Check the logs for error details
2. Verify environment configuration
3. Ensure all services are running
4. Check OpenAI API status and billing
