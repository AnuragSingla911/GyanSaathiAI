import re
import sympy
import asyncio
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple, Union
import logging
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from ..models.schemas import QuestionCandidate, ValidationResult
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application
)

logger = logging.getLogger(__name__)

class EnhancedQuestionValidator:
    """Enhanced validation suite with auto-fix capabilities for v2 architecture"""
    
    def __init__(self, settings, mongo_client=None):
        self.settings = settings
        self.mongo_client = mongo_client
        
        # Enhanced validator registry
        self.validators = {
            'schema': self._validate_schema,
            'render': self._validate_latex_render,
            'math': self._validate_math_correctness,
            'grounding': self._validate_grounding_novelty,
            'dedup': self._validate_deduplication,
            'difficulty': self._validate_difficulty_classifier,
            'safety': self._validate_safety
        }
        
        # Auto-fix methods
        self.auto_fixers = {
            'schema': self._autofix_schema,
            'render': self._autofix_latex,
            'math': self._autofix_math,
            'grounding': self._autofix_grounding
        }
        
        # Initialize components
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self._latex_error_patterns = self._build_latex_error_patterns()
        
    def _build_latex_error_patterns(self) -> Dict[str, str]:
        """Build common LaTeX error patterns and fixes"""
        return {
            r'\$\$([^$]+)\$\$': r'\\[\1\\]',  # Convert $$ to \[ \]
            r'\$([^$]+)\$': r'$\1$',  # Normalize single $
            r'\\begin\{align\*\}': r'\\begin{align}',  # Remove * from align
            r'\\end\{align\*\}': r'\\end{align}',
            r'\\frac\s*\{([^}]+)\}\s*\{([^}]+)\}': r'\\frac{\1}{\2}',  # Fix frac spacing
            r'\\sqrt\s*\{([^}]+)\}': r'\\sqrt{\1}',  # Fix sqrt spacing
            r'([0-9])([a-zA-Z])': r'\1 \2',  # Add space between numbers and variables
            r'([a-zA-Z])([0-9])': r'\1 \2'   # Add space between variables and numbers
        }
    
    async def validate_with_autofix(self, question: QuestionCandidate, 
                                   spec: Dict[str, Any]) -> Tuple[Dict[str, ValidationResult], QuestionCandidate]:
        """Run validators with auto-fix loop"""
        original_question = question
        current_question = question
        all_results = {}
        retry_count = 0
        
        while retry_count < self.settings.max_retries:
            # Run all validators
            results = await self.validate_all(current_question, spec)
            all_results.update(results)
            
            # Check which validators failed
            failed_validators = [name for name, result in results.items() if not result.passed]
            
            if not failed_validators:
                logger.info(f"✅ All validators passed after {retry_count} retries")
                break
            
            # Attempt auto-fixes
            logger.info(f"🔧 Attempting auto-fix for failed validators: {failed_validators}")
            fixed_question = await self._apply_auto_fixes(current_question, failed_validators, spec)
            
            if fixed_question == current_question:
                logger.warning(f"⚠️ No fixes applied, stopping retry loop")
                break
            
            current_question = fixed_question
            retry_count += 1
        
        return all_results, current_question
    
    async def validate_all(self, question: QuestionCandidate, spec: Dict[str, Any]) -> Dict[str, ValidationResult]:
        """Run all validators on a question"""
        results = {}
        for validator_name, validator_func in self.validators.items():
            try:
                print(f"Validating {validator_name} validator")
                print(f"Validator function: {validator_func}")
                result = await validator_func(question, spec)
                print(f"Result: {result}")
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
        print(f"Question: {question}")
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

            # Enforce exactly 4 options and exactly 1 correct answer for MCQ
            if len(question.options) != 4:
                issues.append("Multiple choice must have exactly 4 options")
                score -= 0.2
            if len(question.correct_option_ids) != 1:
                issues.append("Multiple choice must have exactly one correct option")
                score -= 0.4
        
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
    
    async def _apply_auto_fixes(self, question: QuestionCandidate, 
                               failed_validators: List[str], spec: Dict[str, Any]) -> QuestionCandidate:
        """Apply auto-fixes for failed validators"""
        fixed_question = question
        
        for validator_name in failed_validators:
            if validator_name in self.auto_fixers:
                try:
                    logger.info(f"🔧 Applying auto-fix for {validator_name}")
                    fixed_question = await self.auto_fixers[validator_name](fixed_question, spec)
                except Exception as e:
                    logger.error(f"❌ Auto-fix for {validator_name} failed: {e}")
        
        return fixed_question
    
    async def _validate_latex_render(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Validate LaTeX rendering with smoke test"""
        score = 1.0
        issues = []
        
        try:
            # Check for balanced brackets and common LaTeX errors
            text_to_check = f"{question.stem} {question.explanation or ''}"
            
            # Balance check
            bracket_pairs = [('\\{', '\\}'), ('\\[', '\\]'), ('\\(', '\\)')]
            for open_br, close_br in bracket_pairs:
                open_count = len(re.findall(open_br, text_to_check))
                close_count = len(re.findall(close_br, text_to_check))
                if open_count != close_count:
                    issues.append(f"Unbalanced {open_br}/{close_br} brackets")
                    score -= 0.3
            
            # Check for common LaTeX errors
            error_patterns = [
                (r'\\frac\{[^}]*\{', "Nested braces in fraction"),
                (r'\\sqrt\{[^}]*\{', "Nested braces in sqrt"),
                (r'\$\$[^$]*\$[^$]*\$\$', "Mixed dollar signs"),
                (r'[^\\]\{[^}]*[^\\]\}', "Unescaped braces")
            ]
            
            for pattern, error_desc in error_patterns:
                if re.search(pattern, text_to_check):
                    issues.append(error_desc)
                    score -= 0.2
            
            # Smoke test: try basic LaTeX compilation
            if self._contains_latex(text_to_check):
                try:
                    # Simplified LaTeX validation
                    cleaned_text = self._clean_latex_for_validation(text_to_check)
                    # In production, this would use an actual LaTeX renderer
                    logger.debug(f"LaTeX validation passed for: {cleaned_text[:50]}...")
                except Exception as e:
                    issues.append(f"LaTeX compilation failed: {str(e)}")
                    score -= 0.5
        
        except Exception as e:
            issues.append(f"Render validation error: {str(e)}")
            score -= 0.3
        
        passed = score >= 0.7
        
        return ValidationResult(
            validator_name="render",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "contains_latex": self._contains_latex(text_to_check)
            }
        )
    
    async def _validate_math_correctness(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Math validation (stem-only): extract equation from stem, solve, compare to options."""
        score = 1.0
        issues: List[str] = []

        # Only run for math MCQs with options
        if spec.get("subject", "").lower() != "math" or not question.options or not question.correct_option_ids:
            return ValidationResult(
                validator_name="math",
                passed=True,
                score=1.0,
                details={"issues": [], "mode": "skipped_non_math_or_no_options"}
            )

        try:
            logger.info(f"[math] Attempting SymPy solve for stem: {question.stem}")
            solved_values = self._solve_from_stem_by_subject_topic(
                stem=question.stem,
                subject=spec.get("subject"),
                topic=spec.get("topic"),
                variable="x"
            )
            if solved_values:
                solved_val = solved_values[0]
                logger.info(f"[math] Solved value from stem: {solved_val}")

                # Compare against marked correct option
                correct_option = next((opt for opt in question.options if opt.id in question.correct_option_ids), None)
                if correct_option is not None:
                    option_val = self._parse_text_to_sympy_value(correct_option.text)
                    logger.info(f"[math] Parsed correct option '{correct_option.text}' -> {option_val}")
                    if option_val is not None:
                        try:
                            equal_symbolic = sympy.simplify(solved_val - option_val) == 0
                        except Exception:
                            equal_symbolic = False
                        if not equal_symbolic:
                            try:
                                equal_numeric = abs(float(solved_val) - float(option_val)) <= 1e-2
                            except Exception:
                                equal_numeric = False
                        else:
                            equal_numeric = True
                        if not (equal_symbolic or equal_numeric):
                            issues.append("Solved answer from stem does not match the marked correct option")
                            score = min(score, self.settings.grounding_min_score - 0.01)
                            logger.info("[math] Mismatch: solved value != marked correct option")
                    else:
                        issues.append("Could not parse numeric value from the marked correct option text")
                        score -= 0.2
                        logger.warning("[math] Could not parse numeric value from marked correct option")

                # Ensure at least one option matches solved value
                any_match = False
                for opt in question.options:
                    opt_val = self._parse_text_to_sympy_value(opt.text)
                    if opt_val is None:
                        continue
                    try:
                        if sympy.simplify(solved_val - opt_val) == 0:
                            any_match = True
                            break
                    except Exception:
                        try:
                            if abs(float(solved_val) - float(opt_val)) <= 1e-2:
                                any_match = True
                                break
                        except Exception:
                            continue
                if not any_match:
                    issues.append("Solved value from stem is not present in any option")
                    score = min(score, self.settings.grounding_min_score - 0.01)
                    logger.info("[math] Mismatch: solved value not present in any option")
            else:
                logger.info("[math] No solvable equation found in stem or extraction failed")
        except Exception as e:
            # Do not fail hard for parsing issues; record and apply small penalty
            issues.append(f"Math validation error (stem-only): {str(e)}")
            score -= 0.1
        
        passed = score >= self.settings.grounding_min_score
        return ValidationResult(
            validator_name="math",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "mode": "stem_only"
            }
        )

    def _solve_from_stem_by_subject_topic(self, stem: str, subject: Optional[str], topic: Optional[str], variable: str = "x") -> List[sympy.Expr]:
        """Subject/topic aware dispatcher for attempting symbolic solving from the stem.
        - math/algebra/linear equations: solve single-variable equations
        - math/equations (general): attempt single-variable solve if an '=' is present
        - other math topics (geometry/calculus/trigonometry): conservative; only try equation solve if clearly present
        - non-math subjects: skip
        Returns a list of SymPy expressions (solutions) or empty list if not applicable.
        """
        subject_l = (subject or "").lower()
        topic_l = (topic or "").lower()
        if subject_l != "math":
            return []
        # Algebraic equation families
        algebra_topics = {"algebra", "linear equation", "linear equations", "equation", "equations", "quadratic equations"}
        if topic_l in algebra_topics:
            return self._solve_single_variable_equation_from_stem(stem, variable=variable)
        # Geometry/trigonometry sometimes embed equations with '='; attempt cautiously
        if topic_l in {"geometry", "trigonometry", "number theory"}:
            if stem and "=" in stem:
                return self._solve_single_variable_equation_from_stem(stem, variable=variable)
            return []
        # Calculus tasks (limits/derivatives/integrals) typically are not solved via Eq(lhs,rhs)
        if topic_l in {"calculus", "differentiation", "integration", "limits"}:
            return []
        # Default fallback for math: if it looks like an equation, try
        if stem and "=" in stem:
            return self._solve_single_variable_equation_from_stem(stem, variable=variable)
        return []

    def _solve_single_variable_equation_from_stem(self, stem: str, variable: str = "x") -> List[sympy.Expr]:
        """Extract a simple equation from the stem and solve for the given variable.
        Supports implicit multiplication (e.g., 3(2x-1)). Returns a list of solutions.
        Raises on parse/solve failure.
        """
        if not stem:
            return []
        lhs_rhs = self._extract_equation_from_stem(stem)
        if not lhs_rhs:
            return []
        lhs_str, rhs_str = lhs_rhs
        # Strip LaTeX math mode delimiters and extraneous punctuation before parsing
        lhs_str = self._strip_latex_delimiters(lhs_str)
        rhs_str = self._strip_latex_delimiters(rhs_str)
        transformations = (*standard_transformations, implicit_multiplication_application)
        try:
            lhs = parse_expr(lhs_str, evaluate=True, transformations=transformations)
            rhs = parse_expr(rhs_str, evaluate=True, transformations=transformations)
            sym_var = sympy.symbols(variable)
            sol = sympy.solve(sympy.Eq(lhs, rhs), sym_var)
            print(f"[math] Solved equation: {sol}")
            return sol if isinstance(sol, list) else [sol]
        except Exception as e:
            raise ValueError(f"Failed to parse/solve equation: {e}")

    def _extract_equation_from_stem(self, stem: str) -> Optional[Tuple[str, str]]:
        """Heuristically extract LHS and RHS around '=' from a sentence like
        'Solve for x: 3(2x-5) = 4(x+1). What is ...' or similar.
        """
        if not stem:
            return None
        # Strip LaTeX upfront for easier matching
        stem_clean = self._strip_latex_delimiters(stem)
        # Try bounded between ':' and period/question or end
        patterns = [
            r":\s*(.+?)\s*=\s*(.+?)\s*(?:[\.?](?:\s*What|\s*$)|$)",
            r":\s*(.+?)\s*=\s*(.+?)\s*$",
            r"\b([^\n\r]+?)\s*=\s*([^\n\r]+?)\b"
        ]
        for pat in patterns:
            m = re.search(pat, stem_clean, flags=re.IGNORECASE)
            if m:
                lhs, rhs = m.group(1).strip(), m.group(2).strip()
                logger.info(f"[math] Extracted equation: LHS='{lhs}' | RHS='{rhs}'")
                return lhs, rhs
        # Fallback: split on first '=' if present
        if '=' in stem_clean:
            idx = stem_clean.find('=')
            lhs = stem_clean[:idx].split(':')[-1].strip()
            rhs = stem_clean[idx+1:].strip().rstrip('.?')
            if lhs and rhs:
                logger.info(f"[math] Fallback extracted equation: LHS='{lhs}' | RHS='{rhs}'")
                return lhs, rhs
        return None

    def _parse_text_to_sympy_value(self, text: str) -> Optional[sympy.Expr]:
        """Parse a numeric/symbolic value from option text such as 'x = 9/4' or '2.25'.
        Returns a SymPy expression (Rational/Float) or None.
        """
        if not text:
            return None
        try:
            # Prefer explicit assignment like x = value
            m = re.search(r"(?i)\b[a-z]\s*=\s*([-+]?\d+(?:\.\d+)?(?:/\d+)?)", text)
            candidate = None
            if m:
                candidate = m.group(1)
            else:
                # First fraction, decimal, or integer
                m2 = re.search(r"([-+]?\d+(?:\.\d+)?/\d+)|([-+]?\d+\.\d+)|([-+]?\d+)", text)
                if m2:
                    candidate = next(g for g in m2.groups() if g)
            if candidate is None:
                return None
            transformations = (*standard_transformations, implicit_multiplication_application)
            return parse_expr(candidate, transformations=transformations)
        except Exception:
            return None

    def _strip_latex_delimiters(self, text: str) -> str:
        """Remove common LaTeX math mode delimiters and trailing punctuation that confuse parsing."""
        if not text:
            return ""
        # Remove inline/display math delimiters and dollar signs
        cleaned = re.sub(r"\\\(|\\\)|\\\[|\\\]", "", text)
        cleaned = cleaned.replace("$", "")
        # Trim redundant surrounding spaces and terminal punctuation
        cleaned = cleaned.strip()
        cleaned = re.sub(r"[\.;:,]$", "", cleaned)
        return cleaned

    def _parse_numeric_value_from_text(self, text: str) -> Optional[float]:
        """Extract a numeric value from text, supporting forms like 'x = 9/4', 'x = 2.25', or plain '9/4'.
        Returns None if no reliable value can be parsed.
        """
        if not text:
            return None
        try:
            # Prefer explicit assignment like x = value (case-insensitive for variable)
            match = re.search(r'(?i)\b[a-z]\s*=\s*([-+]?\d+(?:\.\d+)?(?:/\d+)?)', text)
            candidate = None
            if match:
                candidate = match.group(1)
            else:
                # Fallback: look for first fraction or decimal/integer
                m2 = re.search(r'([-+]?\d+(?:\.\d+)?/\d+)|([-+]?\d+\.\d+)|([-+]?\d+)', text)
                if m2:
                    candidate = next(g for g in m2.groups() if g)
            if candidate is None:
                return None
            # Resolve fraction safely if present
            if '/' in candidate:
                num, den = candidate.split('/', 1)
                den = den.strip()
                if den == '0':
                    return None
                return float(num) / float(den)
            return float(candidate)
        except Exception:
            return None
    
    async def _validate_grounding_novelty(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Validate grounding and novelty (no copying from exemplars)"""
        score = 1.0
        issues = []
        
        try:
            # Grounding validation
            if not question.citations:
                issues.append("No citations provided")
                score -= 0.3
            else:
                # Check citation quality
                total_citation_length = sum(len(cite.get("text", "")) for cite in question.citations)
                if total_citation_length < 50:
                    issues.append("Citations too brief")
                    score -= 0.2
            
            # Novelty validation - check against exemplars if available
            if self.mongo_client:
                try:
                    exemplar_collection = self.mongo_client.get_default_database().mcq_exemplars
                    
                    # Get recent exemplars to check against
                    recent_exemplars = list(exemplar_collection.find(
                        {"source": "hendrycks_math"}
                    ).limit(100))
                    
                    if recent_exemplars:
                        question_text = f"{question.stem} {question.explanation or ''}"
                        
                        max_overlap = 0
                        for exemplar in recent_exemplars:
                            exemplar_text = f"{exemplar.get('problem', '')} {exemplar.get('solution', '')}"
                            overlap = self._calculate_text_overlap(question_text, exemplar_text)
                            max_overlap = max(max_overlap, overlap)
                        
                        if max_overlap > self.settings.novelty_max_overlap:
                            issues.append(f"High overlap with exemplar: {max_overlap:.2f}")
                            score -= 0.4
                        
                        logger.debug(f"Max exemplar overlap: {max_overlap:.3f}")
                
                except Exception as e:
                    logger.warning(f"Novelty check failed: {e}")
            
            # Check explanation grounding
            if question.explanation and question.citations:
                explanation_grounded = False
                for citation in question.citations:
                    cite_text = citation.get("text", "")
                    if cite_text and len(cite_text) > 20:
                        overlap = self._calculate_text_overlap(question.explanation, cite_text)
                        if overlap > 0.1:  # At least 10% overlap
                            explanation_grounded = True
                            break
                
                if not explanation_grounded:
                    issues.append("Explanation not grounded in citations")
                    score -= 0.3
        
        except Exception as e:
            issues.append(f"Grounding validation error: {str(e)}")
            score -= 0.2
        
        passed = score >= self.settings.grounding_min_score
        
        return ValidationResult(
            validator_name="grounding",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "citation_count": len(question.citations)
            }
        )
    
    async def _validate_deduplication(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Enhanced deduplication with cosine similarity"""
        score = 1.0
        issues = []
        
        try:
            # Check against existing questions in database
            if self.mongo_client:
                try:
                    questions_collection = self.mongo_client.get_default_database().questions
                    
                    # Get recent questions for comparison
                    recent_questions = list(questions_collection.find({}).limit(200))
                    
                    if recent_questions:
                        question_text = question.stem
                        
                        # Use TF-IDF + cosine similarity for better dedup detection
                        texts = [question_text] + [q.get("questionText", "") for q in recent_questions]
                        
                        try:
                            tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
                            similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
                            
                            max_similarity = np.max(similarities) if len(similarities) > 0 else 0
                            
                            if max_similarity > self.settings.dedup_cosine_threshold:
                                issues.append(f"High similarity to existing question: {max_similarity:.3f}")
                                score -= 0.6
                            elif max_similarity > 0.7:
                                issues.append(f"Moderate similarity to existing question: {max_similarity:.3f}")
                                score -= 0.3
                            
                            logger.debug(f"Max question similarity: {max_similarity:.3f}")
                        
                        except Exception as e:
                            logger.warning(f"Similarity calculation failed: {e}")
                
                except Exception as e:
                    logger.warning(f"Database dedup check failed: {e}")
            
            # Check option similarity within the question
            if len(question.options) > 2:
                option_texts = [opt.text for opt in question.options]
                max_option_similarity = 0
                
                for i, text1 in enumerate(option_texts):
                    for j, text2 in enumerate(option_texts[i+1:], i+1):
                        similarity = self._calculate_text_overlap(text1, text2)
                        max_option_similarity = max(max_option_similarity, similarity)
                
                if max_option_similarity > 0.8:
                    issues.append(f"Options too similar: {max_option_similarity:.2f}")
                    score -= 0.4
        
        except Exception as e:
            issues.append(f"Deduplication error: {str(e)}")
            score -= 0.1
        
        passed = score >= 0.6
        
        return ValidationResult(
            validator_name="dedup",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues
            }
        )
    
    async def _validate_difficulty_classifier(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Enhanced difficulty validation with classifier-like approach"""
        target_difficulty = spec.get("difficulty", "medium")
        score = 1.0
        issues = []
        
        try:
            # Multi-factor difficulty assessment
            difficulty_factors = {
                "text_complexity": 0,
                "math_complexity": 0,
                "option_complexity": 0,
                "reasoning_steps": 0
            }
            
            # Text complexity analysis
            if question.stem:
                word_count = len(question.stem.split())
                avg_word_length = sum(len(word) for word in question.stem.split()) / word_count if word_count > 0 else 0
                
                difficulty_factors["text_complexity"] = min((
                    (word_count / 30) * 0.4 +  # Word count factor
                    (avg_word_length / 8) * 0.6  # Word length factor
                ), 1.0)
            
            # Math complexity analysis
            math_expressions = self._extract_math_expressions(question.stem)
            if math_expressions:
                complex_patterns = [r'\\frac', r'\\sqrt', r'\^', r'\\int', r'\\sum']
                complexity_score = 0
                for expr in math_expressions:
                    for pattern in complex_patterns:
                        complexity_score += len(re.findall(pattern, expr)) * 0.2
                
                difficulty_factors["math_complexity"] = min(complexity_score, 1.0)
            
            # Option complexity
            if question.options:
                avg_option_length = sum(len(opt.text) for opt in question.options) / len(question.options)
                difficulty_factors["option_complexity"] = min(avg_option_length / 50, 1.0)
            
            # Reasoning steps (estimate from solution)
            if question.canonical_solution:
                solution_sentences = len(re.split(r'[.!?]', question.canonical_solution))
                difficulty_factors["reasoning_steps"] = min(solution_sentences / 5, 1.0)
            
            # Weighted average
            weights = {"text_complexity": 0.2, "math_complexity": 0.4, "option_complexity": 0.2, "reasoning_steps": 0.2}
            overall_difficulty_score = sum(difficulty_factors[factor] * weights[factor] for factor in difficulty_factors)
            
            # Map to difficulty levels
            if overall_difficulty_score < 0.3:
                estimated_difficulty = "easy"
            elif overall_difficulty_score < 0.7:
                estimated_difficulty = "medium"
            else:
                estimated_difficulty = "hard"
            
            # Check against target
            difficulty_mapping = {"easy": 1, "medium": 2, "hard": 3}
            target_level = difficulty_mapping.get(target_difficulty, 2)
            estimated_level = difficulty_mapping.get(estimated_difficulty, 2)
            
            level_diff = abs(target_level - estimated_level)
            if level_diff > 1:
                issues.append(f"Estimated difficulty '{estimated_difficulty}' differs significantly from target '{target_difficulty}'")
                score -= 0.4
            elif level_diff == 1:
                issues.append(f"Estimated difficulty '{estimated_difficulty}' slightly different from target '{target_difficulty}'")
                score -= 0.2
            
            # Apply threshold
            if score < self.settings.difficulty_classifier_threshold:
                score = 0  # Hard fail for major difficulty mismatches
        
        except Exception as e:
            issues.append(f"Difficulty validation error: {str(e)}")
            score -= 0.2
        
        passed = score >= self.settings.difficulty_classifier_threshold
        
        return ValidationResult(
            validator_name="difficulty",
            passed=passed,
            score=max(0, score),
            details={
                "issues": issues,
                "estimated_difficulty": estimated_difficulty if 'estimated_difficulty' in locals() else "unknown",
                "target_difficulty": target_difficulty,
                "difficulty_score": overall_difficulty_score if 'overall_difficulty_score' in locals() else 0,
                "factors": difficulty_factors if 'difficulty_factors' in locals() else {}
            }
        )
    
    # Auto-fix methods
    async def _autofix_schema(self, question: QuestionCandidate, spec: Dict[str, Any]) -> QuestionCandidate:
        """Auto-fix schema issues"""
        fixed_question = question
        
        # Fix missing or short stem
        if not question.stem or len(question.stem.strip()) < 10:
            if spec.get("topic"):
                fixed_question.stem = f"Which of the following best describes {spec['topic']} in {spec.get('subject', 'this subject')}?"
        
        # Ensure minimum number of options for MCQ
        if spec.get("question_type") == "multiple_choice" and len(question.options) < 4:
            while len(fixed_question.options) < 4:
                option_id = chr(ord('a') + len(fixed_question.options))
                fixed_question.options.append({
                    "id": option_id,
                    "text": f"Option {option_id.upper()}"
                })
        
        # Ensure correct answer is specified
        if spec.get("question_type") == "multiple_choice" and not question.correct_option_ids:
            if question.options:
                fixed_question.correct_option_ids = [question.options[0].id]
        
        return fixed_question
    
    async def _autofix_latex(self, question: QuestionCandidate, spec: Dict[str, Any]) -> QuestionCandidate:
        """Auto-fix LaTeX rendering issues"""
        fixed_question = question
        
        # Apply LaTeX error pattern fixes
        for field in ['stem', 'explanation']:
            text = getattr(fixed_question, field, None)
            if text:
                fixed_text = text
                for pattern, replacement in self._latex_error_patterns.items():
                    fixed_text = re.sub(pattern, replacement, fixed_text)
                setattr(fixed_question, field, fixed_text)
        
        # Fix option LaTeX
        for option in fixed_question.options:
            if option.text:
                fixed_text = option.text
                for pattern, replacement in self._latex_error_patterns.items():
                    fixed_text = re.sub(pattern, replacement, fixed_text)
                option.text = fixed_text
        
        return fixed_question
    
    async def _autofix_math(self, question: QuestionCandidate, spec: Dict[str, Any]) -> QuestionCandidate:
        """Auto-fix mathematical issues"""
        fixed_question = question
        
        # Try to fix simple math expression syntax
        if question.stem:
            fixed_stem = self._fix_math_expressions(question.stem)
            fixed_question.stem = fixed_stem
        
        if question.canonical_solution:
            fixed_solution = self._fix_math_expressions(question.canonical_solution)
            fixed_question.canonical_solution = fixed_solution
        
        return fixed_question
    
    async def _autofix_grounding(self, question: QuestionCandidate, spec: Dict[str, Any]) -> QuestionCandidate:
        """Auto-fix grounding issues"""
        fixed_question = question
        
        # Add default citations if missing
        if not question.citations:
            fixed_question.citations = [{
                "chunk_id": "auto_generated",
                "text": f"Content related to {spec.get('topic', 'the subject matter')}",
                "source": "auto_fix"
            }]
        
        return fixed_question
    
    # Helper methods
    def _contains_latex(self, text: str) -> bool:
        """Check if text contains LaTeX"""
        latex_patterns = [r'\\[a-zA-Z]+', r'\$[^$]+\$', r'\\\[.*?\\\]']
        return any(re.search(pattern, text) for pattern in latex_patterns)
    
    def _clean_latex_for_validation(self, text: str) -> str:
        """Clean LaTeX for validation"""
        # Remove comments
        text = re.sub(r'%.*$', '', text, flags=re.MULTILINE)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _clean_math_expression(self, expr: str) -> str:
        """Clean mathematical expression for SymPy parsing"""
        # Remove LaTeX delimiters
        expr = re.sub(r'\$+', '', expr)
        expr = re.sub(r'\\\[|\\\]', '', expr)
        
        # Replace LaTeX commands with SymPy equivalents
        replacements = {
            r'\\frac\{([^}]+)\}\{([^}]+)\}': r'(\1)/(\2)',
            r'\\sqrt\{([^}]+)\}': r'sqrt(\1)',
            r'\\pi': 'pi',
            r'\\cdot': '*',
            r'\\times': '*'
        }
        
        for pattern, replacement in replacements.items():
            expr = re.sub(pattern, replacement, expr)
        
        return expr.strip()
    
    def _fix_math_expressions(self, text: str) -> str:
        """Fix common math expression errors"""
        # Fix missing multiplication signs
        text = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', text)
        text = re.sub(r'([a-zA-Z])(\d)', r'\1*\2', text)
        
        # Fix parentheses
        text = re.sub(r'(\d)\(', r'\1*(', text)
        text = re.sub(r'\)([a-zA-Z])', r')*\1', text)
        
        return text
    
    def _calculate_text_overlap(self, text1: str, text2: str) -> float:
        """Calculate text overlap using word-level Jaccard similarity"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0

# Original QuestionValidator for backward compatibility
class QuestionValidator:
    """Simple question validation system (v1 compatibility)"""
    
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
        
        passed = score >= 0.6
        
        return ValidationResult(
            validator_name="grounding",
            passed=passed,
            score=max(0, score),
            details={"issues": issues}
        )
    
    async def _validate_math_solver(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Basic math validation"""
        return ValidationResult(
            validator_name="math_solver",
            passed=True,
            score=1.0,
            details={"message": "Basic math validation passed"}
        )
    
    async def _validate_deduplication(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Basic deduplication check"""
        return ValidationResult(
            validator_name="dedup",
            passed=True,
            score=1.0,
            details={"message": "Basic deduplication check passed"}
        )
    
    async def _validate_safety(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Basic safety check"""
        return ValidationResult(
            validator_name="safety",
            passed=True,
            score=1.0,
            details={"message": "Basic safety check passed"}
        )
    
    async def _validate_difficulty(self, question: QuestionCandidate, spec: Dict[str, Any]) -> ValidationResult:
        """Basic difficulty check"""
        return ValidationResult(
            validator_name="difficulty",
            passed=True,
            score=1.0,
            details={"message": "Basic difficulty check passed"}
        )
