"""
Simplified Question Validator with LLM-based Consensus Validation

This validator replaces sympy validation with LLM-based validation where the LLM
attempts to answer the question 5 times, and if 4 out of 5 attempts match the
correct answer, the question is considered valid.
"""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Try to import LangChain dependencies, fall back if not available
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None
    ChatPromptTemplate = None

from ..models.schemas import QuestionCandidate, ValidationResult
from ..utils.config import get_settings

logger = logging.getLogger(__name__)

class SimplifiedQuestionValidator:
    """Simplified validation using LLM consensus instead of complex rule-based validation"""
    
    def __init__(self, settings, mongo_client=None):
        self.settings = settings
        self.mongo_client = mongo_client
        
        # Initialize LLM for validation only if LangChain is available
        if LANGCHAIN_AVAILABLE and hasattr(settings, 'openai_api_key') and settings.openai_api_key:
            self.llm = ChatOpenAI(
                model=getattr(settings, 'openai_model', 'gpt-3.5-turbo'),
                temperature=0.1,  # Low temperature for more consistent responses
                max_tokens=getattr(settings, 'max_tokens', 1000),
                openai_api_key=settings.openai_api_key,
                model_kwargs={"response_format": {"type": "json_object"}}
            )
        else:
            self.llm = None
        
        if LANGCHAIN_AVAILABLE:
            self._setup_validation_prompt()
        else:
            self.validation_prompt = None
    
    def _setup_validation_prompt(self):
        """Setup prompt for LLM-based validation"""
        self.validation_prompt = ChatPromptTemplate.from_template("""
You are an expert educator answering a multiple choice question. Your task is to solve the question and choose the correct answer.

**Question:**
{question_stem}

**Options:**
{options_text}

**Instructions:**
1. Read the question carefully
2. Think through the problem step by step
3. Choose the option you believe is correct
4. Provide your reasoning and confidence

**Required JSON Output:**
{{
  "chosen_option_id": "your_choice_letter",
  "reasoning": "step-by-step explanation of your choice",
  "confidence": 0.95
}}

Answer the question now and respond with JSON only:
        """)
    
    async def validate_with_llm_consensus(self, question: QuestionCandidate, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate question using LLM consensus (5 attempts, 4/5 required for pass)
        """
        logger.info("🔍 Starting LLM consensus validation")
        
        if not LANGCHAIN_AVAILABLE:
            logger.warning("⚠️ LangChain not available, falling back to basic validation only")
            return self._fallback_validation(question, spec)
        
        if not self.llm:
            logger.error("❌ No LLM available for validation")
            return {
                "llm_consensus": ValidationResult(
                    validator_name="llm_consensus",
                    passed=False,
                    score=0.0,
                    error_message="No LLM available for validation"
                )
            }
        
        try:
            # Basic schema validation first
            schema_valid, schema_issues = self._validate_basic_schema(question)
            if not schema_valid:
                return {
                    "llm_consensus": ValidationResult(
                        validator_name="llm_consensus",
                        passed=False,
                        score=0.0,
                        error_message=f"Schema validation failed: {', '.join(schema_issues)}",
                        details={"schema_issues": schema_issues}
                    )
                }
            
            # Prepare question for LLM validation
            options_text = "\\n".join([f"{opt.id.upper()}. {opt.text}" for opt in question.options])
            marked_correct = question.correct_option_ids[0] if question.correct_option_ids else "unknown"
            
            # Run 5 LLM validation attempts
            validation_attempts = []
            successful_attempts = 0
            
            print("\n" + "="*80)
            print("🔍 STARTING LLM CONSENSUS VALIDATION")
            print("="*80)
            print(f"📝 Question: {question.stem}")
            print(f"📋 Options:\n{options_text}")
            print(f"✅ Marked Correct: {marked_correct.upper()}")
            print("="*80)
            
            for attempt in range(5):
                try:
                    print(f"\n🤖 ATTEMPT {attempt + 1}/5:")
                    print("-" * 50)
                    logger.info(f"🤖 LLM validation attempt {attempt + 1}/5")
                    
                    # Use the LangChain pipeline correctly
                    chain = self.validation_prompt | self.llm
                    response = await chain.ainvoke({
                        "question_stem": question.stem,
                        "options_text": options_text
                    })

                    # Parse response
                    validation_result = json.loads(response.content)
                    
                    # Add our own comparison logic
                    chosen = validation_result.get('chosen_option_id', 'unknown').lower()
                    matches = chosen == marked_correct.lower()
                    validation_result['matches_marked_correct'] = matches
                    
                    validation_attempts.append(validation_result)
                    successful_attempts += 1

                    # Print detailed results for this attempt
                    chosen_display = chosen.upper()
                    confidence = validation_result.get('confidence', 0.0)
                    reasoning = validation_result.get('reasoning', 'No reasoning provided')
                    
                    print(f"🎯 LLM Chose: {chosen_display}")
                    print(f"✅ Matches Correct: {matches}")
                    print(f"📊 Confidence: {confidence:.2f}")
                    print(f"💭 Reasoning: {reasoning[:200]}{'...' if len(reasoning) > 200 else ''}")
                    print(f"📊 Status: {'✅ CORRECT' if matches else '❌ INCORRECT'}")
                    
                    logger.info(f"✅ Attempt {attempt + 1}: {chosen} "
                              f"(matches: {matches}, confidence: {confidence:.2f})")
                    
                except Exception as e:
                    print(f"❌ ATTEMPT {attempt + 1} FAILED: {str(e)}")
                    logger.warning(f"⚠️ LLM validation attempt {attempt + 1} failed: {e}")
                    validation_attempts.append({
                        "chosen_option_id": "error",
                        "reasoning": f"Validation failed: {str(e)}",
                        "confidence": 0.0,
                        "matches_marked_correct": False
                    })
            
            # Calculate consensus
            consensus_result = self._calculate_consensus(validation_attempts, marked_correct)
            
            # Print final consensus results
            print("\n" + "="*80)
            print("📊 FINAL CONSENSUS RESULTS")
            print("="*80)
            print(f"🎯 Correct Matches: {consensus_result['matches_correct']}/{successful_attempts}")
            print(f"📊 Consensus Score: {consensus_result['consensus_score']:.2f}")
            print(f"📋 Chosen Options: {consensus_result['chosen_options']}")
            print(f"🏆 Most Chosen: {consensus_result['most_chosen']}")
            print(f"📊 Average Confidence: {consensus_result['average_confidence']:.2f}")
            
            # Determine if validation passed (4/5 or 80% consensus required)
            validation_passed = consensus_result['consensus_score'] >= 0.8
            
            print(f"✅ VALIDATION RESULT: {'PASSED' if validation_passed else 'FAILED'}")
            print(f"📝 Threshold: 4/5 (80%) - {'✅ MET' if validation_passed else '❌ NOT MET'}")
            print("="*80)
            
            logger.info(f"📊 Consensus result: {consensus_result['matches_correct']}/{successful_attempts} "
                      f"(score: {consensus_result['consensus_score']:.2f})")
            
            return {
                "llm_consensus": ValidationResult(
                    validator_name="llm_consensus",
                    passed=validation_passed,
                    score=consensus_result['consensus_score'],
                    details={
                        "llm_attempts": successful_attempts,
                        "matches_correct": consensus_result['matches_correct'],
                        "validation_attempts": validation_attempts,
                        "consensus_details": consensus_result,
                        "schema_validation": {
                            "passed": schema_valid,
                            "issues": schema_issues
                        }
                    }
                )
            }
            
        except Exception as e:
            logger.error(f"❌ LLM consensus validation failed: {str(e)}")
            return {
                "llm_consensus": ValidationResult(
                    validator_name="llm_consensus",
                    passed=False,
                    score=0.0,
                    error_message=str(e)
                )
            }
    
    def _validate_basic_schema(self, question: QuestionCandidate) -> Tuple[bool, List[str]]:
        """Basic schema validation to ensure question structure is valid"""
        issues = []
        
        # Check required fields
        if not question.stem or len(question.stem.strip()) < 10:
            issues.append("Question stem too short or missing")
        
        # Check options
        if not question.options or len(question.options) != 4:
            issues.append("Must have exactly 4 options")
        else:
            option_ids = [opt.id.lower() for opt in question.options]
            expected_ids = ['a', 'b', 'c', 'd']
            if set(option_ids) != set(expected_ids):
                issues.append(f"Option IDs must be a,b,c,d, got: {option_ids}")
            
            # Check option text (minimal check - just ensure it exists)
            for opt in question.options:
                if not opt.text or len(opt.text.strip()) == 0:
                    issues.append(f"Option {opt.id} text is completely missing")
        
        # Check correct answer
        if not question.correct_option_ids or len(question.correct_option_ids) != 1:
            issues.append("Must have exactly one correct option ID")
        elif question.correct_option_ids[0].lower() not in ['a', 'b', 'c', 'd']:
            issues.append(f"Correct option ID must be a,b,c,d, got: {question.correct_option_ids[0]}")
        





        # Check explanation (optional - not required for validation)
        # We only need the question, options, and correct answer for LLM validation
        
        return len(issues) == 0, issues
    
    def _calculate_consensus(self, validation_attempts: List[Dict], marked_correct: str) -> Dict[str, Any]:
        """Calculate consensus from validation attempts"""
        
        # Count successful attempts
        successful_attempts = [att for att in validation_attempts if att.get('chosen_option_id') != 'error']
        total_attempts = len(successful_attempts)
        
        if total_attempts == 0:
            return {
                "consensus_score": 0.0,
                "matches_correct": 0,
                "total_attempts": 0,
                "chosen_options": {},
                "average_confidence": 0.0
            }
        
        # Count how many matched the marked correct answer
        matches_correct = sum(1 for att in successful_attempts 
                            if att.get('matches_marked_correct', False))
        
        # Count distribution of chosen options
        chosen_options = {}
        total_confidence = 0.0
        
        for attempt in successful_attempts:
            chosen = attempt.get('chosen_option_id', '').lower()
            confidence = attempt.get('confidence', 0.0)
            
            if chosen in chosen_options:
                chosen_options[chosen] += 1
            else:
                chosen_options[chosen] = 1
            
            total_confidence += confidence
        
        # Calculate consensus score
        consensus_score = matches_correct / total_attempts if total_attempts > 0 else 0.0
        average_confidence = total_confidence / total_attempts if total_attempts > 0 else 0.0
        
        return {
            "consensus_score": consensus_score,
            "matches_correct": matches_correct,
            "total_attempts": total_attempts,
            "chosen_options": chosen_options,
            "average_confidence": average_confidence,
            "most_chosen": max(chosen_options, key=chosen_options.get) if chosen_options else None
        }
    
    def _fallback_validation(self, question: QuestionCandidate, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback validation when LLM is not available - basic schema validation only"""
        logger.info("🔍 Running fallback validation (schema only)")
        
        try:
            # Basic schema validation
            schema_valid, schema_issues = self._validate_basic_schema(question)
            
            return {
                "schema_only": ValidationResult(
                    validator_name="schema_only",
                    passed=schema_valid,
                    score=1.0 if schema_valid else 0.0,
                    details={
                        "method": "fallback_schema_only",
                        "llm_attempts": 0,
                        "schema_issues": schema_issues,
                        "note": "LLM validation not available, schema validation only"
                    }
                )
            }
            
        except Exception as e:
            logger.error(f"❌ Fallback validation failed: {str(e)}")
            return {
                "schema_only": ValidationResult(
                    validator_name="schema_only",
                    passed=False,
                    score=0.0,
                    error_message=str(e),
                    details={
                        "method": "fallback_error",
                        "llm_attempts": 0
                    }
                )
            }
