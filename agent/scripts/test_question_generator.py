#!/usr/bin/env python3
"""
Test script for question generator with RAG retriever
"""

import asyncio
import os
import logging
import sys

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.question_generator import create_question_generation_graph
from services.rag_retriever import RAGRetriever
from services.validators import QuestionValidator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_question_generation():
    """Test the question generation with RAG retriever"""
    
    # Get OpenAI API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("❌ OPENAI_API_KEY environment variable is required")
        return
    
    try:
        # Initialize RAG retriever
        retriever = RAGRetriever(
            postgres_url=os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/aitutor"),
            openai_api_key=openai_api_key
        )
        await retriever.initialize()
        print("✅ RAG retriever initialized")
        
        # Initialize question validator
        validator = QuestionValidator()
        print("✅ Question validator initialized")
        
        # Create question generation graph
        question_graph = create_question_generation_graph(retriever, validator)
        print("✅ Question generation graph created")
        
        # Test question generation
        test_topics = [
            {
                "subject": "math",
                "topic": "linear equations",
                "difficulty": "medium",
                "question_type": "multiple_choice"
            },
            {
                "subject": "science",
                "topic": "Newton's laws",
                "difficulty": "medium",
                "question_type": "multiple_choice"
            }
        ]
        
        for topic in test_topics:
            print(f"\n🎯 Testing question generation for: {topic['subject']} - {topic['topic']}")
            print("-" * 60)
            
            try:
                # Create a mock request
                from models.schemas import QuestionGenerationRequest
                
                request = QuestionGenerationRequest(
                    subject=topic["subject"],
                    topic=topic["topic"],
                    difficulty=topic["difficulty"],
                    question_type=topic["question_type"],
                    num_questions=2,
                    seed=42
                )
                
                # Generate questions
                result = await question_graph.ainvoke(request.dict())
                
                if result and result.get("questions"):
                    print(f"✅ Generated {len(result['questions'])} questions:")
                    for i, question in enumerate(result["questions"], 1):
                        print(f"\n{i}. Question: {question.get('question_text', 'N/A')}")
                        if question.get("options"):
                            print("   Options:")
                            for j, option in enumerate(question["options"], 1):
                                print(f"      {j}. {option}")
                        print(f"   Correct Answer: {question.get('correct_answer', 'N/A')}")
                        if question.get("explanation"):
                            print(f"   Explanation: {question['explanation'][:100]}...")
                else:
                    print("❌ No questions generated")
                    
            except Exception as e:
                print(f"❌ Error generating questions for {topic['topic']}: {e}")
        
        print("\n✅ Question generation test completed!")
        
    except Exception as e:
        print(f"❌ Failed to test question generation: {e}")
    finally:
        if 'retriever' in locals():
            await retriever.close()

if __name__ == "__main__":
    asyncio.run(test_question_generation())
