#!/usr/bin/env python3
"""
Verification script to check if the corpus setup is working correctly
"""

import asyncio
import os
import logging
import psycopg2
import sys
from typing import Dict, Any

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_database_connection():
    """Verify database connection and schema"""
    try:
        postgres_url = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/aitutor")
        
        # Parse connection string
        if postgres_url.startswith("postgresql://"):
            # Extract components
            parts = postgres_url.replace("postgresql://", "").split("@")
            if len(parts) == 2:
                user_pass, host_port_db = parts
                user, password = user_pass.split(":")
                host_port, database = host_port_db.split("/")
                host, port = host_port.split(":")
                
                # Connect to PostgreSQL
                conn = psycopg2.connect(
                    host=host,
                    port=int(port),
                    database=database,
                    user=user,
                    password=password
                )
                
                print("✅ Database connection successful")
                
                # Check if pgvector extension is enabled
                with conn.cursor() as cursor:
                    cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                    if cursor.fetchone():
                        print("✅ pgvector extension is enabled")
                    else:
                        print("❌ pgvector extension not found")
                        return False
                
                # Check if corpus tables exist
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name IN ('corpus_documents', 'corpus_chunks')
                    """)
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    if 'corpus_documents' in tables and 'corpus_chunks' in tables:
                        print("✅ Corpus tables exist")
                    else:
                        print("❌ Corpus tables missing")
                        return False
                
                # Check if embeddings column exists
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'corpus_chunks' 
                        AND column_name = 'embedding'
                    """)
                    if cursor.fetchone():
                        print("✅ Embeddings column exists")
                    else:
                        print("❌ Embeddings column missing")
                        return False
                
                # Check corpus data
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM corpus_documents")
                    doc_count = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM corpus_chunks")
                    chunk_count = cursor.fetchone()[0]
                    
                    print(f"📊 Corpus contains {doc_count} documents and {chunk_count} chunks")
                    
                    if doc_count > 0 and chunk_count > 0:
                        print("✅ Corpus has data")
                    else:
                        print("⚠️  Corpus is empty")
                
                conn.close()
                return True
                
            else:
                print("❌ Invalid connection string format")
                return False
                
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

async def verify_openai_connection():
    """Verify OpenAI API connection"""
    try:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("❌ OPENAI_API_KEY not set")
            return False
        
        if openai_api_key == "your_actual_openai_api_key_here":
            print("❌ OPENAI_API_KEY not configured (still using placeholder)")
            return False
        
        print("✅ OPENAI_API_KEY is configured")
        
        # Test OpenAI connection by importing and testing embeddings
        try:
            from langchain_openai import OpenAIEmbeddings
            
            embeddings = OpenAIEmbeddings(
                openai_api_key=openai_api_key,
                model="text-embedding-3-small"
            )
            
            # Test with a simple text
            test_embedding = await embeddings.aembed_query("test")
            if test_embedding and len(test_embedding) > 0:
                print("✅ OpenAI embeddings working")
                return True
            else:
                print("❌ OpenAI embeddings failed")
                return False
                
        except Exception as e:
            print(f"❌ OpenAI test failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ OpenAI verification failed: {e}")
        return False

async def verify_corpus_ingestion():
    """Verify corpus ingestion is working"""
    try:
        from services.corpus_ingestion import CorpusIngestion
        
        openai_api_key = os.getenv("OPENAI_API_KEY")
        postgres_url = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/aitutor")
        
        ingestion = CorpusIngestion(postgres_url, openai_api_key)
        await ingestion.initialize()
        print("✅ Corpus ingestion service initialized")
        
        await ingestion.close()
        return True
        
    except Exception as e:
        print(f"❌ Corpus ingestion verification failed: {e}")
        return False

async def verify_rag_retriever():
    """Verify RAG retriever is working"""
    try:
        from services.rag_retriever import RAGRetriever
        
        openai_api_key = os.getenv("OPENAI_API_KEY")
        postgres_url = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/aitutor")
        
        retriever = RAGRetriever(postgres_url, openai_api_key)
        await retriever.initialize()
        print("✅ RAG retriever service initialized")
        
        await retriever.close()
        return True
        
    except Exception as e:
        print(f"❌ RAG retriever verification failed: {e}")
        return False

async def main():
    """Run all verification checks"""
    print("🔍 AI Tutor Corpus Setup Verification")
    print("=" * 50)
    
    checks = [
        ("Database Connection", verify_database_connection),
        ("OpenAI Connection", verify_openai_connection),
        ("Corpus Ingestion", verify_corpus_ingestion),
        ("RAG Retriever", verify_rag_retriever)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        print(f"\n🔍 {check_name}...")
        try:
            result = await check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} check failed: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 VERIFICATION SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 All checks passed! Your corpus setup is working correctly.")
        return True
    else:
        print("⚠️  Some checks failed. Please review the issues above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
