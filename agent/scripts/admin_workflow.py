#!/usr/bin/env python3
"""
Admin Workflow Script for AI Question Generation
This demonstrates the correct workflow:
1. Generate questions using AI pipeline
2. Store them in MongoDB for student use
3. Students fetch pre-generated questions
"""

import requests
import json
import time

# Configuration
AGENT_URL = "http://localhost:8000"
ADMIN_TOKEN = "your_admin_token_here"  # In production, use proper auth

def generate_and_store_questions():
    """Generate questions using AI pipeline and store them for student use"""
    
    print("🤖 AI Question Generation Workflow")
    print("=" * 50)
    
    # Step 1: Generate question using AI pipeline
    print("\n1️⃣ Generating question using AI pipeline...")
    
    generation_request = {
        "subject": "math",
        "topic": "algebra",
        "class_level": 7,
        "difficulty": "medium",
        "question_type": "multiple_choice",
        "skills": ["variables", "linear_equations"]
    }
    
    try:
        # Call AI generation endpoint
        response = requests.post(
            f"{AGENT_URL}/admin/generate/question",
            json=generation_request,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print("✅ Question generated successfully!")
                print(f"📝 Question: {result['question']['questionText']}")
                
                # Step 2: Store question in database for student use
                print("\n2️⃣ Storing question in database...")
                
                store_response = requests.post(
                    f"{AGENT_URL}/admin/add-question",
                    json=result["question"],
                    headers={"Content-Type": "application/json"}
                )
                
                if store_response.status_code == 200:
                    store_result = store_response.json()
                    print("✅ Question stored successfully!")
                    print(f"🆔 Question ID: {store_result['question_id']}")
                    print("💾 Now students can fetch this question!")
                    
                else:
                    print(f"❌ Failed to store question: {store_response.text}")
                    
            else:
                print(f"❌ AI generation failed: {result['error']}")
        else:
            print(f"❌ AI generation request failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def demonstrate_student_workflow():
    """Show how students would fetch pre-generated questions"""
    
    print("\n" + "=" * 50)
    print("👨‍🎓 Student Workflow Demonstration")
    print("=" * 50)
    
    print("\n📚 Students fetch questions from MongoDB via backend API:")
    print("   GET /api/quizzes/questions")
    print("   - No AI generation involved")
    print("   - Fast response from database")
    print("   - Consistent question quality")
    print("   - Pre-validated content")
    
    print("\n🔄 AI Pipeline is only used by admins to:")
    print("   - Generate new questions")
    print("   - Populate question bank")
    print("   - Update curriculum content")
    print("   - Create specialized questions")

def main():
    """Main workflow"""
    
    print("🚀 AI Tutor Admin Workflow")
    print("=" * 60)
    
    # Check if agent is running
    try:
        health_response = requests.get(f"{AGENT_URL}/health")
        if health_response.status_code == 200:
            print("✅ AI Agent is running")
            generate_and_store_questions()
            demonstrate_student_workflow()
        else:
            print("❌ AI Agent is not responding")
    except Exception as e:
        print(f"❌ Cannot connect to AI Agent: {str(e)}")
        print("   Make sure the agent is running: docker-compose up -d agent")

if __name__ == "__main__":
    main()
