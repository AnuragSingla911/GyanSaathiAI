import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
import random

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import structlog

from ..models.responses import Explanation, Feedback
from ..utils.config import get_settings

logger = structlog.get_logger()

class ExplanationGeneratorService:
    def __init__(self):
        self.settings = get_settings()
        self.tokenizer = None
        self.model = None
        self.generator = None
        self.is_initialized = False
        
        # Template explanations for different scenarios
        self.explanation_templates = {
            "solution": {
                "math": [
                    "To solve this problem, follow these steps:\n1. {step1}\n2. {step2}\n3. {step3}\nTherefore, the answer is {answer}.",
                    "Let's break this down step by step:\nFirst, {step1}\nNext, {step2}\nFinally, {step3}\nThe solution is {answer}."
                ],
                "science": [
                    "This question involves understanding {concept}.\n\nThe key principle is: {principle}\n\nApplying this principle: {application}\n\nTherefore, {answer} is correct.",
                    "To answer this, we need to consider {concept}:\n1. {step1}\n2. {step2}\n3. {step3}\nThis leads us to {answer}."
                ]
            },
            "mistake_analysis": {
                "common_mistakes": [
                    "A common mistake here is {mistake}. This happens because {reason}.",
                    "Many students incorrectly think {wrong_thinking}. However, {correct_thinking}.",
                    "Be careful not to {mistake}. Instead, remember that {correct_approach}."
                ]
            }
        }
        
        # Feedback templates based on performance
        self.feedback_templates = {
            "correct_first_attempt": [
                "Excellent work! You got it right on the first try!",
                "Perfect! You demonstrated a clear understanding of the concept.",
                "Great job! Your approach was correct and efficient."
            ],
            "correct_multiple_attempts": [
                "Good persistence! You worked through the problem and found the right answer.",
                "Nice work! It's great that you kept trying until you got it right.",
                "Well done! Learning often involves making mistakes and correcting them."
            ],
            "incorrect_close": [
                "You're very close! Your approach is on the right track.",
                "Good thinking! You're almost there - just a small adjustment needed.",
                "Nice try! You understand the concept well, just a minor error to fix."
            ],
            "incorrect_far": [
                "Let's think about this differently. Here's a hint to get you started:",
                "This is a challenging problem. Let me help you break it down:",
                "Don't worry - this concept takes practice. Let's work through it together:"
            ],
            "encouragement": [
                "Remember, making mistakes is part of learning!",
                "Every expert was once a beginner. Keep practicing!",
                "You're building important problem-solving skills."
            ]
        }

    async def initialize(self):
        """Initialize the explanation generation model"""
        try:
            logger.info("Initializing explanation generator")
            
            # For now, we'll use template-based explanations
            # In a full implementation, you'd load a fine-tuned model here
            self.is_initialized = True
            logger.info("Explanation generator initialized (template-based)")
            
        except Exception as e:
            logger.error("Failed to initialize explanation generator", error=str(e))
            # Still mark as initialized to use templates
            self.is_initialized = True

    def is_ready(self) -> bool:
        """Check if the service is ready"""
        return self.is_initialized

    async def generate_explanation(
        self,
        question_text: str,
        correct_answer: str,
        student_answer: Optional[str] = None,
        explanation_type: str = "solution",
        learning_style: str = "step_by_step",
        include_visual_aids: bool = False,
        include_common_mistakes: bool = True
    ) -> Explanation:
        """Generate an explanation for a question"""
        
        if not self.is_initialized:
            raise RuntimeError("Explanation generator not initialized")
        
        try:
            explanation_id = str(uuid.uuid4())
            
            # Determine subject from question context (simple heuristic)
            subject = self._infer_subject(question_text)
            
            # Generate main explanation
            summary = await self._generate_summary(question_text, correct_answer, subject)
            detailed_steps = await self._generate_detailed_steps(
                question_text, correct_answer, subject, learning_style
            )
            
            # Generate common mistakes if requested
            common_mistakes = []
            if include_common_mistakes:
                common_mistakes = await self._generate_common_mistakes(
                    question_text, correct_answer, student_answer, subject
                )
            
            # Generate related concepts
            related_concepts = await self._generate_related_concepts(question_text, subject)
            
            return Explanation(
                explanation_id=explanation_id,
                summary=summary,
                detailed_steps=detailed_steps,
                explanation_type=explanation_type,
                learning_style=learning_style,
                visual_aids=[] if not include_visual_aids else ["diagram_placeholder.png"],
                common_mistakes=common_mistakes,
                related_concepts=related_concepts,
                quality_score=0.8,
                created_at=datetime.now()
            )
            
        except Exception as e:
            logger.error("Explanation generation failed", error=str(e))
            return await self._generate_fallback_explanation(question_text, correct_answer)

    async def generate_feedback(
        self,
        question_text: str,
        student_answer: str,
        correct_answer: str,
        attempt_number: int = 1,
        time_taken: Optional[int] = None,
        hint_used: bool = False,
        previous_attempts: Optional[List[str]] = None
    ) -> Feedback:
        """Generate personalized feedback for a student's answer"""
        
        try:
            feedback_id = str(uuid.uuid4())
            
            # Analyze the student's answer
            is_correct = await self._is_answer_correct(student_answer, correct_answer)
            is_close = await self._is_answer_close(student_answer, correct_answer) if not is_correct else False
            
            # Determine feedback type and message
            if is_correct and attempt_number == 1:
                feedback_type = "encouragement"
                message = random.choice(self.feedback_templates["correct_first_attempt"])
                suggestions = ["Keep up the excellent work!", "Try a similar problem to reinforce your understanding."]
                confidence_score = 0.95
            elif is_correct and attempt_number > 1:
                feedback_type = "encouragement"
                message = random.choice(self.feedback_templates["correct_multiple_attempts"])
                suggestions = ["Persistence pays off!", "Review your approach to solve similar problems faster next time."]
                confidence_score = 0.85
            elif is_close:
                feedback_type = "correction"
                message = random.choice(self.feedback_templates["incorrect_close"])
                suggestions = await self._generate_close_suggestions(student_answer, correct_answer)
                confidence_score = 0.7
            else:
                feedback_type = "hint"
                message = random.choice(self.feedback_templates["incorrect_far"])
                suggestions = await self._generate_hint_suggestions(question_text, correct_answer)
                confidence_score = 0.6
            
            # Add time-based feedback if applicable
            if time_taken:
                time_feedback = await self._generate_time_feedback(time_taken, is_correct)
                if time_feedback:
                    message += f"\n\n{time_feedback}"
            
            # Generate next steps
            next_steps = await self._generate_next_steps(is_correct, attempt_number, question_text)
            
            return Feedback(
                feedback_id=feedback_id,
                feedback_type=feedback_type,
                message=message,
                suggestions=suggestions,
                next_steps=next_steps,
                confidence_score=confidence_score,
                created_at=datetime.now()
            )
            
        except Exception as e:
            logger.error("Feedback generation failed", error=str(e))
            return await self._generate_fallback_feedback(student_answer, correct_answer)

    def _infer_subject(self, question_text: str) -> str:
        """Infer subject from question text using simple keyword matching"""
        
        math_keywords = ["solve", "equation", "calculate", "area", "perimeter", "angle", "x", "y", "formula"]
        science_keywords = ["energy", "force", "atom", "molecule", "reaction", "experiment", "theory", "law"]
        
        question_lower = question_text.lower()
        
        math_score = sum(1 for keyword in math_keywords if keyword in question_lower)
        science_score = sum(1 for keyword in science_keywords if keyword in question_lower)
        
        return "math" if math_score > science_score else "science"

    async def _generate_summary(self, question_text: str, correct_answer: str, subject: str) -> str:
        """Generate a brief summary of the solution"""
        
        if subject == "math":
            return f"This problem requires applying mathematical principles to find that the answer is {correct_answer}."
        else:
            return f"This question tests understanding of scientific concepts, with the correct answer being {correct_answer}."

    async def _generate_detailed_steps(
        self, question_text: str, correct_answer: str, subject: str, learning_style: str
    ) -> List[Dict[str, Any]]:
        """Generate detailed solution steps"""
        
        steps = []
        
        if subject == "math":
            steps = [
                {
                    "step_number": 1,
                    "description": "Identify the given information and what needs to be found",
                    "mathematical_expression": "Given: [problem parameters]"
                },
                {
                    "step_number": 2,
                    "description": "Choose the appropriate formula or method",
                    "mathematical_expression": "[relevant formula]"
                },
                {
                    "step_number": 3,
                    "description": "Substitute the values and solve",
                    "mathematical_expression": f"Result = {correct_answer}"
                }
            ]
        else:
            steps = [
                {
                    "step_number": 1,
                    "description": "Understand the scientific principle involved"
                },
                {
                    "step_number": 2,
                    "description": "Apply the principle to the given scenario"
                },
                {
                    "step_number": 3,
                    "description": f"Conclude that {correct_answer} is correct"
                }
            ]
        
        return steps

    async def _generate_common_mistakes(
        self, question_text: str, correct_answer: str, student_answer: Optional[str], subject: str
    ) -> List[Dict[str, str]]:
        """Generate common mistakes for this type of problem"""
        
        mistakes = []
        
        if subject == "math":
            mistakes = [
                {
                    "mistake_description": "Forgetting to follow order of operations",
                    "explanation": "Remember PEMDAS: Parentheses, Exponents, Multiplication/Division, Addition/Subtraction",
                    "remediation_steps": ["Always identify operations first", "Work from left to right within same precedence"]
                },
                {
                    "mistake_description": "Sign errors in calculations",
                    "explanation": "Be careful with positive and negative numbers",
                    "remediation_steps": ["Double-check signs at each step", "Use parentheses for clarity"]
                }
            ]
        else:
            mistakes = [
                {
                    "mistake_description": "Confusing similar concepts",
                    "explanation": "Make sure you understand the distinction between related terms",
                    "remediation_steps": ["Review definitions", "Practice with examples"]
                }
            ]
        
        return mistakes

    async def _generate_related_concepts(self, question_text: str, subject: str) -> List[str]:
        """Generate related concepts to help with learning"""
        
        if subject == "math":
            return ["algebra", "equations", "problem solving", "mathematical reasoning"]
        else:
            return ["scientific method", "hypothesis testing", "data analysis", "critical thinking"]

    async def _is_answer_correct(self, student_answer: str, correct_answer: str) -> bool:
        """Check if student answer is correct (simple string comparison for now)"""
        
        # Normalize answers for comparison
        student_normalized = student_answer.strip().lower()
        correct_normalized = correct_answer.strip().lower()
        
        return student_normalized == correct_normalized

    async def _is_answer_close(self, student_answer: str, correct_answer: str) -> bool:
        """Check if student answer is close to correct (simple heuristic)"""
        
        try:
            # Try to compare as numbers
            student_num = float(student_answer)
            correct_num = float(correct_answer)
            
            # Consider close if within 10% or difference less than 1
            diff = abs(student_num - correct_num)
            return diff < abs(correct_num * 0.1) or diff < 1
            
        except (ValueError, TypeError):
            # For non-numeric answers, check string similarity
            student_words = set(student_answer.lower().split())
            correct_words = set(correct_answer.lower().split())
            
            if not correct_words:
                return False
            
            overlap = len(student_words.intersection(correct_words))
            return overlap / len(correct_words) > 0.5

    async def _generate_close_suggestions(self, student_answer: str, correct_answer: str) -> List[str]:
        """Generate suggestions when answer is close"""
        
        return [
            "Check your calculation one more time",
            "Make sure you're using the correct units",
            "Double-check any rounding you did"
        ]

    async def _generate_hint_suggestions(self, question_text: str, correct_answer: str) -> List[str]:
        """Generate hint suggestions for incorrect answers"""
        
        return [
            "Re-read the question carefully to understand what's being asked",
            "Think about the key concepts related to this topic",
            "Try breaking the problem down into smaller steps"
        ]

    async def _generate_time_feedback(self, time_taken: int, is_correct: bool) -> Optional[str]:
        """Generate feedback based on time taken"""
        
        if time_taken < 30:
            if is_correct:
                return "Impressive speed! You solved this quickly and correctly."
            else:
                return "You answered quickly - sometimes it helps to take a bit more time to think through the problem."
        elif time_taken > 300:  # 5 minutes
            return "You took your time with this problem, which shows good patience and persistence."
        
        return None

    async def _generate_next_steps(self, is_correct: bool, attempt_number: int, question_text: str) -> List[str]:
        """Generate next steps for the student"""
        
        if is_correct:
            return [
                "Try a similar problem to reinforce your understanding",
                "Move on to the next topic when you're ready",
                "Consider helping a classmate with this type of problem"
            ]
        elif attempt_number < 3:
            return [
                "Try again with the hints provided",
                "Think about the problem from a different angle",
                "Review the relevant concepts if needed"
            ]
        else:
            return [
                "Review the explanation carefully",
                "Practice similar problems",
                "Ask for help if you're still confused"
            ]

    async def _generate_fallback_explanation(self, question_text: str, correct_answer: str) -> Explanation:
        """Generate a basic fallback explanation"""
        
        return Explanation(
            explanation_id=str(uuid.uuid4()),
            summary=f"The correct answer is {correct_answer}.",
            detailed_steps=[
                {
                    "step_number": 1,
                    "description": "This is a basic explanation for the given question."
                }
            ],
            explanation_type="solution",
            quality_score=0.5,
            created_at=datetime.now()
        )

    async def _generate_fallback_feedback(self, student_answer: str, correct_answer: str) -> Feedback:
        """Generate basic fallback feedback"""
        
        is_correct = student_answer.strip().lower() == correct_answer.strip().lower()
        
        return Feedback(
            feedback_id=str(uuid.uuid4()),
            feedback_type="basic",
            message="Thank you for your answer!" if is_correct else "Keep trying - you're learning!",
            suggestions=["Keep practicing!"],
            next_steps=["Continue to the next question"],
            confidence_score=0.5,
            created_at=datetime.now()
        )