import asyncio
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import random

import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    pipeline,
    GenerationConfig
)
import structlog

from ..models.responses import Question, QuestionOption
from ..utils.config import get_settings

logger = structlog.get_logger()

class ContentGeneratorService:
    def __init__(self):
        self.settings = get_settings()
        self.tokenizer = None
        self.model = None
        self.generator = None
        self.is_initialized = False
        
        # Question templates for different subjects and types
        self.question_templates = {
            "math": {
                "algebra": {
                    "multiple_choice": [
                        "Solve for x: {equation}",
                        "What is the value of x in the equation {equation}?",
                        "Find x when {equation}"
                    ],
                    "problem_solving": [
                        "A rectangle has length {length} and width {width}. What is its area?",
                        "If a train travels {distance} km in {time} hours, what is its speed?",
                        "Sarah has {initial} apples. She gives away {given} and buys {bought} more. How many does she have now?"
                    ]
                },
                "geometry": {
                    "multiple_choice": [
                        "What is the area of a circle with radius {radius}?",
                        "A triangle has angles of {angle1}° and {angle2}°. What is the third angle?",
                        "What is the perimeter of a square with side length {side}?"
                    ]
                }
            },
            "science": {
                "physics": {
                    "multiple_choice": [
                        "What is the formula for calculating kinetic energy?",
                        "Which of the following is a unit of force?",
                        "What happens to the volume of a gas when temperature increases at constant pressure?"
                    ],
                    "short_answer": [
                        "Explain Newton's first law of motion",
                        "What is the difference between mass and weight?",
                        "Describe what happens during nuclear fusion"
                    ]
                },
                "chemistry": {
                    "multiple_choice": [
                        "What is the atomic number of {element}?",
                        "Which type of bond forms between a metal and a non-metal?",
                        "What is the pH of a neutral solution?"
                    ]
                }
            }
        }
        
        # Sample answers and explanations
        self.sample_content = {
            "math_options": [
                {"label": "A", "text": "x = 5", "is_correct": True},
                {"label": "B", "text": "x = 3", "is_correct": False},
                {"label": "C", "text": "x = 7", "is_correct": False},
                {"label": "D", "text": "x = 2", "is_correct": False}
            ],
            "science_options": [
                {"label": "A", "text": "Newton (N)", "is_correct": True},
                {"label": "B", "text": "Joule (J)", "is_correct": False},
                {"label": "C", "text": "Watt (W)", "is_correct": False},
                {"label": "D", "text": "Pascal (Pa)", "is_correct": False}
            ]
        }

    async def initialize(self):
        """Initialize the model and tokenizer"""
        try:
            logger.info("Initializing content generator", model=self.settings.model_name)
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.settings.model_name,
                cache_dir=self.settings.model_cache_dir,
                token=self.settings.hf_token if self.settings.hf_token else None
            )
            
            # Add padding token if it doesn't exist
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.settings.model_name,
                cache_dir=self.settings.model_cache_dir,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                token=self.settings.hf_token if self.settings.hf_token else None
            )
            
            # Create generation pipeline
            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if torch.cuda.is_available() else -1,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
            
            self.is_initialized = True
            logger.info("Content generator initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize content generator", error=str(e))
            # Fall back to template-based generation
            self.is_initialized = True
            logger.info("Falling back to template-based generation")

    def is_ready(self) -> bool:
        """Check if the service is ready"""
        return self.is_initialized

    async def generate_question(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        question_type: str,
        grade_level: int,
        keywords: Optional[List[str]] = None,
        learning_objectives: Optional[List[str]] = None
    ) -> Question:
        """Generate a single question"""
        
        if not self.is_initialized:
            raise RuntimeError("Content generator not initialized")
        
        try:
            # For now, use template-based generation with some AI enhancement
            question = await self._generate_template_question(
                subject, topic, difficulty, question_type, grade_level
            )
            
            # If we have a working model, enhance the question
            if self.generator is not None:
                question = await self._enhance_question_with_ai(question)
            
            return question
            
        except Exception as e:
            logger.error("Question generation failed", error=str(e))
            # Fall back to basic template
            return await self._generate_fallback_question(subject, topic, difficulty, question_type, grade_level)

    async def generate_questions_batch(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        question_type: str,
        grade_level: int,
        count: int,
        **kwargs
    ) -> List[Question]:
        """Generate multiple questions"""
        
        if count > self.settings.max_questions_per_batch:
            raise ValueError(f"Cannot generate more than {self.settings.max_questions_per_batch} questions at once")
        
        tasks = []
        for _ in range(count):
            task = self.generate_question(
                subject, topic, difficulty, question_type, grade_level, **kwargs
            )
            tasks.append(task)
        
        questions = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return successful generations
        successful_questions = [q for q in questions if isinstance(q, Question)]
        
        if not successful_questions:
            raise RuntimeError("Failed to generate any questions")
        
        return successful_questions

    async def _generate_template_question(
        self, subject: str, topic: str, difficulty: str, question_type: str, grade_level: int
    ) -> Question:
        """Generate question using templates"""
        
        question_id = str(uuid.uuid4())
        
        # Get template based on subject and topic
        templates = self.question_templates.get(subject, {}).get(topic, {}).get(question_type, [])
        
        if not templates:
            # Use generic templates
            if question_type == "multiple_choice":
                templates = [f"What is the correct answer for this {subject} {topic} question?"]
            else:
                templates = [f"Solve this {subject} {topic} problem."]
        
        # Select random template
        template = random.choice(templates)
        
        # Fill in template variables
        question_text = await self._fill_template_variables(template, subject, topic, difficulty, grade_level)
        
        # Generate options for multiple choice
        options = None
        correct_answer = None
        
        if question_type == "multiple_choice":
            options = await self._generate_options(subject, topic, difficulty)
            correct_answer = next((opt.text for opt in options if opt.is_correct), None)
        else:
            correct_answer = await self._generate_answer(question_text, subject, topic)
        
        # Generate explanation
        explanation = await self._generate_explanation(question_text, correct_answer, subject, topic)
        
        return Question(
            question_id=question_id,
            question_text=question_text,
            question_type=question_type,
            subject=subject,
            topic=topic,
            difficulty_level=difficulty,
            grade_level=grade_level,
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            hints=await self._generate_hints(question_text, correct_answer),
            keywords=[subject, topic],
            learning_objectives=[f"Understand {topic} in {subject}"],
            quality_score=0.8  # Template-based questions get decent quality score
        )

    async def _fill_template_variables(
        self, template: str, subject: str, topic: str, difficulty: str, grade_level: int
    ) -> str:
        """Fill template variables with appropriate values"""
        
        # Simple variable filling based on difficulty and grade level
        variables = {}
        
        if "{equation}" in template:
            if difficulty == "easy":
                variables["equation"] = f"{random.randint(1, 10)}x + {random.randint(1, 10)} = {random.randint(15, 50)}"
            elif difficulty == "medium":
                variables["equation"] = f"{random.randint(2, 5)}x - {random.randint(1, 10)} = {random.randint(10, 30)}"
            else:
                variables["equation"] = f"{random.randint(2, 8)}x² + {random.randint(1, 12)}x - {random.randint(5, 20)} = 0"
        
        if "{radius}" in template:
            variables["radius"] = random.randint(3, 15) if difficulty != "hard" else random.randint(10, 25)
        
        if "{element}" in template:
            elements = ["Hydrogen", "Carbon", "Oxygen", "Nitrogen", "Sodium", "Chlorine"]
            variables["element"] = random.choice(elements)
        
        # Fill in the template
        try:
            return template.format(**variables)
        except KeyError:
            # If variables are missing, return template as-is
            return template

    async def _generate_options(self, subject: str, topic: str, difficulty: str) -> List[QuestionOption]:
        """Generate multiple choice options"""
        
        if subject == "math":
            base_options = [
                {"label": "A", "text": f"{random.randint(1, 20)}", "is_correct": True},
                {"label": "B", "text": f"{random.randint(1, 20)}", "is_correct": False},
                {"label": "C", "text": f"{random.randint(1, 20)}", "is_correct": False},
                {"label": "D", "text": f"{random.randint(1, 20)}", "is_correct": False}
            ]
        else:
            base_options = self.sample_content["science_options"]
        
        return [QuestionOption(**opt) for opt in base_options]

    async def _generate_answer(self, question_text: str, subject: str, topic: str) -> str:
        """Generate answer for non-multiple choice questions"""
        
        # Simple answer generation based on subject
        if subject == "math":
            return f"{random.randint(1, 100)}"
        elif subject == "science":
            return "This depends on the specific scientific principle being tested."
        else:
            return "Answer varies based on the question context."

    async def _generate_explanation(self, question_text: str, answer: str, subject: str, topic: str) -> str:
        """Generate explanation for the answer"""
        
        base_explanation = f"To solve this {subject} problem about {topic}:\n\n"
        
        if subject == "math":
            base_explanation += "1. Identify the given information\n"
            base_explanation += "2. Apply the appropriate mathematical formula or method\n"
            base_explanation += "3. Solve step by step\n"
            base_explanation += f"4. The answer is {answer}"
        else:
            base_explanation += f"This question tests your understanding of {topic}. "
            base_explanation += f"The correct answer is {answer} because it aligns with the fundamental principles of {subject}."
        
        return base_explanation

    async def _generate_hints(self, question_text: str, answer: str) -> List[str]:
        """Generate hints for the question"""
        
        return [
            "Read the question carefully and identify what is being asked",
            "Think about the key concepts related to this topic",
            "Consider the step-by-step approach to solve this problem"
        ]

    async def _enhance_question_with_ai(self, question: Question) -> Question:
        """Enhance question using AI model if available"""
        
        if self.generator is None:
            return question
        
        try:
            # Create prompt for enhancement
            prompt = f"Improve this educational question:\n\nQuestion: {question.question_text}\nSubject: {question.subject}\nTopic: {question.topic}\n\nImproved question:"
            
            # Generate enhanced version
            result = self.generator(
                prompt,
                max_length=self.settings.generation_max_tokens,
                temperature=self.settings.generation_temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
            enhanced_text = result[0]['generated_text'][len(prompt):].strip()
            
            if enhanced_text and len(enhanced_text) > 10:
                question.question_text = enhanced_text
                question.quality_score = 0.9  # AI-enhanced questions get higher score
            
        except Exception as e:
            logger.warning("Failed to enhance question with AI", error=str(e))
        
        return question

    async def _generate_fallback_question(
        self, subject: str, topic: str, difficulty: str, question_type: str, grade_level: int
    ) -> Question:
        """Generate a basic fallback question when all else fails"""
        
        return Question(
            question_id=str(uuid.uuid4()),
            question_text=f"What is an important concept in {subject} related to {topic}?",
            question_type=question_type,
            subject=subject,
            topic=topic,
            difficulty_level=difficulty,
            grade_level=grade_level,
            options=[
                QuestionOption(label="A", text="Concept A", is_correct=True),
                QuestionOption(label="B", text="Concept B", is_correct=False),
                QuestionOption(label="C", text="Concept C", is_correct=False),
                QuestionOption(label="D", text="Concept D", is_correct=False)
            ] if question_type == "multiple_choice" else None,
            correct_answer="Concept A" if question_type == "multiple_choice" else "This is a basic concept.",
            explanation=f"This question tests understanding of {topic} in {subject}.",
            hints=["Think about the basic principles", "Consider what you've learned about this topic"],
            keywords=[subject, topic],
            learning_objectives=[f"Understand {topic}"],
            quality_score=0.5  # Fallback questions get lower quality score
        )