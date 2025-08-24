#!/usr/bin/env python3
"""
Complete corpus setup pipeline:
1. Clear existing corpus data
2. Run database migrations
3. Populate corpus with sample data and embeddings
4. Test RAG retriever
5. Test question generator
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_corpus_pipeline():
    """Run the complete corpus setup pipeline"""
    
    print("🚀 Starting AI Tutor Corpus Setup Pipeline")
    print("=" * 60)
    
    # Check environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("❌ OPENAI_API_KEY environment variable is required")
        print("Please set it in your .env file or environment")
        return False
    
    postgres_url = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/aitutor")
    print(f"📊 Using PostgreSQL: {postgres_url}")
    
    try:
        # Step 1: Clear existing corpus
        print("\n1️⃣ Clearing existing corpus data...")
        from services.corpus_ingestion import CorpusIngestion
        
        # Create ingestion instance but don't initialize yet
        ingestion = CorpusIngestion(postgres_url, openai_api_key)
        
        # Clear corpus first (this will drop existing tables)
        await ingestion.clear_corpus()
        print("✅ Corpus cleared")
        
        # Now initialize (this will create fresh tables)
        await ingestion.initialize()
        print("✅ Corpus ingestion initialized")
        
        # Step 2: Populate with sample data and embeddings
        print("\n2️⃣ Populating corpus with sample data and embeddings...")
        await ingestion.ingest_sample_corpus()
        print("✅ Sample corpus ingested with embeddings")
        
        await ingestion.close()
        
        # Step 3: Test RAG retriever
        print("\n3️⃣ Testing RAG retriever...")
        from test_rag import test_rag_retriever
        await test_rag_retriever()
        
        # Step 4: Test question generator
        print("\n4️⃣ Testing question generator...")
        from test_question_generator import test_question_generation
        await test_question_generation()
        
        print("\n🎉 Corpus setup pipeline completed successfully!")
        print("=" * 60)
        print("✅ Corpus populated with embeddings")
        print("✅ RAG retriever working")
        print("✅ Question generator working")
        print("\nYou can now use the AI Tutor system!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        logger.error(f"Pipeline error: {e}", exc_info=True)
        return False

def main():
    """Main entry point"""
    try:
        success = asyncio.run(run_corpus_pipeline())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
