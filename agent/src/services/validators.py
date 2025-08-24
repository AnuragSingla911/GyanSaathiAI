import re
import sympy
from typing import Dict, Any, List
import logging
from ..models.schemas import QuestionCandidate, ValidationResult

logger = logging.getLogger(__name__)

class QuestionValidator:
    """Comprehensive question validation system"""
    
    def __init__(self):
        self.validators = {
            'schema': self._validate_schema,
            'grounding': self._validate_grounding,
            'math_solver': self._validate_math_solver,
            'dedup': self._validate_deduplication,
            'safety': self._validate_safety,
            'difficulty': self._validate_difficulty
        }
    
    async def validate_all(self, question: QuestionCandidate, spec: Dict[str, Any]) -> Dict[str, ValidationResult]:
        """Run all validators on a question"""
        results = {}
        
        for validator_name, validator_func in self.validators.items():
            try:
                result = await validator_func(question, spec)
                results[validator_name] = result
            except Exception as e:
                logger.error(f"Error in {validator_name} validator: {e}")
                results[validator_name] = ValidationResult(
                    validator_name=validator_name,
                    passed=False,
                    error_message=str(e)
                )
        
        return results
    
    async def _validate_schema(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Validate question schema and structure"""
        issues = []
        score = 1.0
        
        # Check required fields
        if not question.stem or len(question.stem.strip()) < 10:
            issues.append("Question stem too short or missing")
            score -= 0.3
        
        # Check options for multiple choice
        if spec.get("question_type") == "multiple_choice":
            if len(question.options) < 2:
                issues.append("Multiple choice needs at least 2 options")
                score -= 0.4
            
            if not question.correct_option_ids:
                issues.append("No correct answer specified")
                score -= 0.5
            
            # Check if correct answers exist in options
            option_ids = {opt.id for opt in question.options}
            invalid_correct = set(question.correct_option_ids) - option_ids
            if invalid_correct:
                issues.append(f"Invalid correct option IDs: {invalid_correct}")
                score -= 0.3
        
        # Check for reasonable option lengths
        if question.options:
            avg_length = sum(len(opt.text) for opt in question.options) / len(question.options)
            if avg_length > 200:
                issues.append("Options may be too verbose")
                score -= 0.1
        
        passed = score >= 0.7
        
        return ValidationResult(
            validator_name="schema",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "option_count": len(question.options),
                "stem_length": len(question.stem) if question.stem else 0
            }
        )
    
    async def _validate_grounding(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Validate that question is grounded in provided citations"""
        score = 1.0
        issues = []
        
        # Check if citations exist
        if not question.citations:
            issues.append("No citations provided")
            score -= 0.3
        
        # Check if explanation references citations
        if question.explanation and question.citations:
            citation_texts = [cite.get("text", "") for cite in question.citations]
            explanation_lower = question.explanation.lower()
            
            # Simple check: does explanation contain content from citations
            grounded = False
            for cite_text in citation_texts:
                if cite_text and len(cite_text) > 20:
                    # Check for common words (simple grounding check)
                    cite_words = set(cite_text.lower().split())
                    explanation_words = set(explanation_lower.split())
                    overlap = len(cite_words & explanation_words)
                    if overlap >= 3:  # At least 3 common words
                        grounded = True
                        break
            
            if not grounded:
                issues.append("Explanation not well grounded in citations")
                score -= 0.4
        
        # Check citation quality
        if question.citations:
            for i, citation in enumerate(question.citations):
                if not citation.get("chunk_id") or not citation.get("text"):
                    issues.append(f"Citation {i+1} missing required fields")
                    score -= 0.2
        
        passed = score >= 0.6
        
        return ValidationResult(
            validator_name="grounding",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "citation_count": len(question.citations),
                "has_explanation": bool(question.explanation)
            }
        )
    
    async def _validate_math_solver(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Validate mathematical correctness for math questions"""
        if spec.get("subject", "").lower() != "math":
            return ValidationResult(
                validator_name="math_solver",
                passed=True,
                score=1.0,
                details={"message": "Not a math question, skipping math validation"}
            )
        
        score = 1.0
        issues = []
        
        try:
            # Extract mathematical expressions from question and options
            math_expressions = self._extract_math_expressions(question.stem)
            
            if math_expressions:
                # Try to evaluate expressions with SymPy
                for expr in math_expressions:
                    try:
                        sympy.sympify(expr)
                    except Exception as e:
                        issues.append(f"Invalid mathematical expression: {expr}")
                        score -= 0.3
            
            # For multiple choice, check if options are numerically reasonable
            if question.options and question.correct_option_ids:
                numeric_options = []
                for opt in question.options:
                    try:
                        # Try to extract number from option
                        numbers = re.findall(r'-?\d+\.?\d*', opt.text)
                        if numbers:
                            numeric_options.append(float(numbers[0]))
                    except:
                        pass
                
                # Check if correct answer is among reasonable options
                if len(numeric_options) >= 2:
                    correct_opts = [opt for opt in question.options if opt.id in question.correct_option_ids]
                    if correct_opts:
                        try:
                            correct_numbers = re.findall(r'-?\d+\.?\d*', correct_opts[0].text)
                            if correct_numbers:
                                correct_val = float(correct_numbers[0])
                                # Simple reasonableness check
                                if abs(correct_val) > 1000000:  # Very large numbers
                                    issues.append("Answer magnitude seems unreasonable")
                                    score -= 0.2
                        except:
                            pass
        
        except Exception as e:
            issues.append(f"Math validation error: {str(e)}")
            score -= 0.1
        
        passed = score >= 0.7
        
        return ValidationResult(
            validator_name="math_solver",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "math_expressions_found": len(math_expressions) if 'math_expressions' in locals() else 0
            }
        )
    
    async def _validate_deduplication(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Check for near-duplicate questions"""
        # For now, simple implementation
        # In production, this would check against existing questions database
        
        score = 1.0
        issues = []
        
        # Check for very generic question stems
        generic_patterns = [
            r"which of the following",
            r"what is the",
            r"select the correct",
            r"choose the best"
        ]
        
        stem_lower = question.stem.lower() if question.stem else ""
        generic_count = sum(1 for pattern in generic_patterns if re.search(pattern, stem_lower))
        
        if generic_count > 0:
            issues.append("Question uses generic phrasing that may lead to duplicates")
            score -= 0.2
        
        # Check option similarity (basic)
        if len(question.options) > 2:
            option_texts = [opt.text.lower() for opt in question.options]
            similar_pairs = 0
            for i, text1 in enumerate(option_texts):
                for text2 in option_texts[i+1:]:
                    # Simple similarity: common words ratio
                    words1 = set(text1.split())
                    words2 = set(text2.split())
                    if words1 and words2:
                        similarity = len(words1 & words2) / len(words1 | words2)
                        if similarity > 0.8:
                            similar_pairs += 1
            
            if similar_pairs > 0:
                issues.append(f"Found {similar_pairs} pairs of very similar options")
                score -= 0.3
        
        passed = score >= 0.6
        
        return ValidationResult(
            validator_name="dedup",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "generic_patterns_found": generic_count
            }
        )
    
    async def _validate_safety(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Check for safety and appropriateness"""
        score = 1.0
        issues = []
        
        # List of inappropriate content patterns
        inappropriate_patterns = [
            r"\b(violence|weapon|drug|alcohol)\b",
            r"\b(hate|discriminat|racist)\b",
            r"\b(personal|private|secret)\b"
        ]
        
        # Check question stem
        text_to_check = question.stem or ""
        if question.explanation:
            text_to_check += " " + question.explanation
        
        text_lower = text_to_check.lower()
        
        for pattern in inappropriate_patterns:
            if re.search(pattern, text_lower):
                issues.append(f"Potentially inappropriate content detected")
                score -= 0.5
                break
        
        # Check for PII patterns
        pii_patterns = [
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
            r"\b\d{3}-\d{3}-\d{4}\b"  # Phone
        ]
        
        for pattern in pii_patterns:
            if re.search(pattern, text_to_check):
                issues.append("Potential PII detected")
                score -= 0.8
                break
        
        passed = score >= 0.8
        
        return ValidationResult(
            validator_name="safety",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "content_length": len(text_to_check)
            }
        )
    
    async def _validate_difficulty(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Estimate and validate question difficulty"""
        target_difficulty = spec.get("difficulty", "medium")
        score = 1.0
        issues = []
        
        # Simple difficulty heuristics
        difficulty_score = 0
        
        # Text complexity
        if question.stem:
            word_count = len(question.stem.split())
            if word_count > 50:
                difficulty_score += 1  # Longer questions tend to be harder
            
            # Complex vocabulary (simple check)
            complex_words = len([w for w in question.stem.split() if len(w) > 8])
            difficulty_score += min(complex_words / 5, 1)
        
        # Option complexity
        if question.options:
            avg_option_length = sum(len(opt.text) for opt in question.options) / len(question.options)
            if avg_option_length > 30:
                difficulty_score += 0.5
        
        # Map to difficulty levels
        if difficulty_score < 0.5:
            estimated_difficulty = "easy"
        elif difficulty_score < 1.5:
            estimated_difficulty = "medium"
        else:
            estimated_difficulty = "hard"
        
        # Check against target
        difficulty_map = {"easy": 1, "medium": 2, "hard": 3}
        target_level = difficulty_map.get(target_difficulty, 2)
        estimated_level = difficulty_map.get(estimated_difficulty, 2)
        
        if abs(target_level - estimated_level) > 1:
            issues.append(f"Estimated difficulty '{estimated_difficulty}' differs significantly from target '{target_difficulty}'")
            score -= 0.3
        
        passed = score >= 0.6
        
        return ValidationResult(
            validator_name="difficulty",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "estimated_difficulty": estimated_difficulty,
                "target_difficulty": target_difficulty,
                "difficulty_score": difficulty_score
            }
        )
    
    def _extract_math_expressions(self, text: str) -> List[str]:
        """Extract mathematical expressions from text"""
        if not text:
            return []
        
        # Simple patterns for mathematical expressions
        patterns = [
            r'\$[^$]+\$',  # LaTeX math mode
            r'\\[([^]]+)\\]',  # LaTeX display math
            r'\b\d+\s*[+\-*/=]\s*\d+',  # Simple arithmetic
            r'\b[a-zA-Z]\s*[+\-*/=]\s*\d+',  # Algebraic expressions
        ]
        
        expressions = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            expressions.extend(matches)
        
        return expressions
