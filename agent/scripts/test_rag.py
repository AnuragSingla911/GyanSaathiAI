#!/usr/bin/env python3
"""
Test script for RAG retriever with embeddings
"""

import asyncio
import os
import logging
import sys

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.rag_retriever import RAGRetriever

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_rag_retriever():
    """Test the RAG retriever with sample queries"""
    
    # Get OpenAI API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("❌ OPENAI_API_KEY environment variable is required")
        return
    
    # Initialize RAG retriever
    retriever = RAGRetriever(
        postgres_url=os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/aitutor"),
        openai_api_key=openai_api_key
    )
    
    try:
        await retriever.initialize()
        print("✅ RAG retriever initialized successfully")
        
        # Test queries
        test_queries = [
            "How do I solve linear equations?",
            "What are Newton's laws of motion?",
            "Explain atomic structure and bonding",
            "What is the quadratic formula?",
            "How does energy conservation work?"
        ]
        
        for query in test_queries:
            print(f"\n🔍 Testing query: '{query}'")
            print("-" * 50)
            
            try:
                results = await retriever.search(query, limit=3)
                
                if results:
                    print(f"Found {len(results)} relevant chunks:")
                    for i, result in enumerate(results, 1):
                        print(f"\n{i}. Score: {result.get('relevance_score', 'N/A')}")
                        print(f"   Subject: {result.get('subject', 'N/A')}")
                        print(f"   Class: {result.get('class_level', 'N/A')}")
                        print(f"   Chapter: {result.get('chapter', 'N/A')}")
                        print(f"   Text: {result.get('text', 'N/A')[:200]}...")
                else:
                    print("No results found")
                    
            except Exception as e:
                print(f"❌ Error searching for '{query}': {e}")
        
        print("\n✅ RAG retriever test completed!")
        
    except Exception as e:
        print(f"❌ Failed to test RAG retriever: {e}")
    finally:
        await retriever.close()

if __name__ == "__main__":
    asyncio.run(test_rag_retriever())
