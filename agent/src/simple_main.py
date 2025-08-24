from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import os
import random

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Tutor Agent - Simple Version",
    description="Simplified AI agent for question generation",
    version="1.0.0"
)

# Basic response models
class HealthResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, str]

class QuestionRequest(BaseModel):
    subject: str
    topic: Optional[str] = None
    difficulty: str = "medium"
    question_type: str = "multiple_choice"

class QuestionResponse(BaseModel):
    success: bool
    question: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        services={
            "question_generator": "healthy",
            "api": "healthy"
        }
    )

@app.post("/generate/question", response_model=QuestionResponse)
async def generate_question(request: QuestionRequest):
    """Generate a sample question - simplified version"""
    try:
        logger.info(f"Generating question for: {request.subject}/{request.topic}")
        
        # Sample questions for demo
        sample_questions = {
            "math": {
                "arithmetic": [
                    {
                        "questionText": "What is 25 × 4?",
                        "options": ["90", "100", "110", "120"],
                        "correctAnswer": "100",
                        "explanation": "25 × 4 = 100. You can think of this as 25 × 4 = (20 + 5) × 4 = 20×4 + 5×4 = 80 + 20 = 100"
                    },
                    {
                        "questionText": "What is 144 ÷ 12?",
                        "options": ["10", "11", "12", "13"],
                        "correctAnswer": "12",
                        "explanation": "144 ÷ 12 = 12. You can verify: 12 × 12 = 144"
                    }
                ],
                "algebra": [
                    {
                        "questionText": "Solve for x: 3x + 5 = 20",
                        "options": ["x = 4", "x = 5", "x = 6", "x = 7"],
                        "correctAnswer": "x = 5",
                        "explanation": "3x + 5 = 20 → 3x = 15 → x = 5"
                    }
                ]
            },
            "science": {
                "chemistry": [
                    {
                        "questionText": "What is the chemical symbol for water?",
                        "options": ["H2O", "CO2", "NaCl", "O2"],
                        "correctAnswer": "H2O",
                        "explanation": "Water is composed of 2 hydrogen atoms and 1 oxygen atom, hence H2O"
                    }
                ],
                "physics": [
                    {
                        "questionText": "What is the unit of force?",
                        "options": ["Joule", "Newton", "Watt", "Pascal"],
                        "correctAnswer": "Newton",
                        "explanation": "The Newton (N) is the SI unit of force, named after Isaac Newton"
                    }
                ]
            }
        }
        
        # Get questions for the subject/topic
        subject_questions = sample_questions.get(request.subject.lower(), {})
        topic_questions = subject_questions.get(request.topic.lower() if request.topic else "general", [])
        
        if not topic_questions:
            # Fallback to any questions from the subject
            all_subject_questions = []
            for topic_list in subject_questions.values():
                all_subject_questions.extend(topic_list)
            topic_questions = all_subject_questions
        
        if not topic_questions:
            # Ultimate fallback
            topic_questions = [{
                "questionText": f"Sample {request.subject} question: What is a key concept in {request.topic or request.subject}?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correctAnswer": "Option A",
                "explanation": f"This is a generated sample question for {request.subject}."
            }]
        
        # Select a random question
        question = random.choice(topic_questions)
        
        return QuestionResponse(
            success=True,
            question={
                **question,
                "subject": request.subject,
                "topic": request.topic,
                "difficulty": request.difficulty,
                "question_type": request.question_type,
                "generated_by": "ai_agent_v1.0"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating question: {str(e)}")
        return QuestionResponse(
            success=False,
            error=f"Question generation failed: {str(e)}"
        )

@app.get("/generate/explanation")
async def generate_explanation(
    question: str,
    student_answer: Optional[str] = None,
    correct_answer: Optional[str] = None
):
    """Generate explanation for a question"""
    try:
        explanation = f"Explanation for: {question}\n\n"
        
        if student_answer and correct_answer:
            if student_answer.lower() == correct_answer.lower():
                explanation += "✅ Correct! "
            else:
                explanation += f"❌ Incorrect. The correct answer is: {correct_answer}\n\n"
        
        explanation += "This is a sample explanation generated by the AI tutor agent. In a full implementation, this would provide detailed step-by-step reasoning."
        
        return {
            "success": True,
            "explanation": explanation,
            "generated_by": "ai_agent_v1.0"
        }
        
    except Exception as e:
        logger.error(f"Error generating explanation: {str(e)}")
        return {
            "success": False,
            "error": f"Explanation generation failed: {str(e)}"
        }

# CORS middleware for development
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
