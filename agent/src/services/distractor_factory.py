"""
Distractor Factory for MCQ Option Generation

This service generates plausible but incorrect answer choices (distractors) 
for multiple choice questions using mathematical misconception patterns,
systematic errors, and domain-specific strategies.
"""

import logging
import random
import math
import re
from typing import Dict, List, Any, Optional, Union, Tuple
import sympy as sp
from sympy import symbols, simplify, N
from fractions import Fraction
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

class DistractorFactory:
    """
    Generates plausible wrong answers for mathematical MCQs using
    systematic error patterns and misconception modeling.
    """
    
    def __init__(self, settings):
        self.settings = settings
        self.misconception_patterns = self._build_misconception_patterns()
        
    def _build_misconception_patterns(self) -> Dict[str, List[Dict]]:
        """Build a registry of common mathematical misconceptions"""
        return {
            "arithmetic": [
                {"name": "sign_error", "description": "Wrong sign in result", "method": "flip_sign"},
                {"name": "operation_error", "description": "Wrong operation used", "method": "wrong_operation"},
                {"name": "decimal_place", "description": "Decimal place error", "method": "shift_decimal"},
                {"name": "fraction_error", "description": "Fraction misconception", "method": "fraction_mistake"}
            ],
            "algebra": [
                {"name": "distribute_error", "description": "Distribution error", "method": "distribute_wrong"},
                {"name": "combine_terms", "description": "Wrong term combination", "method": "combine_wrong"},
                {"name": "exponent_rule", "description": "Exponent rule error", "method": "exponent_mistake"},
                {"name": "factoring_error", "description": "Factoring mistake", "method": "factor_wrong"}
            ],
            "geometry": [
                {"name": "formula_confusion", "description": "Wrong formula used", "method": "formula_mix"},
                {"name": "unit_error", "description": "Wrong units or scaling", "method": "unit_mistake"},
                {"name": "dimension_error", "description": "Dimension confusion", "method": "dimension_wrong"}
            ],
            "calculus": [
                {"name": "power_rule_error", "description": "Power rule mistake", "method": "power_rule_wrong"},
                {"name": "chain_rule_miss", "description": "Forgot chain rule", "method": "chain_rule_forget"},
                {"name": "constant_rule", "description": "Constant handling error", "method": "constant_wrong"}
            ]
        }
    
    async def generate_distractors(self, correct_answer: Union[str, float, int], 
                                 question_context: Dict[str, Any], 
                                 count: int = None) -> List[Dict[str, Any]]:
        """
        Generate plausible distractors for the given correct answer.
        
        Args:
            correct_answer: The correct answer (numerical or algebraic)
            question_context: Context about the question (subject, type, parameters, etc.)
            count: Number of distractors to generate (default from settings)
            
        Returns:
            List of distractor dictionaries with values and explanations
        """
        if count is None:
            count = self.settings.distractor_count
            
        logger.info(f"🎯 Generating {count} distractors for answer: {correct_answer}")
        logger.info(f"📝 Question context: {question_context}")
        
        try:
            # Analyze the correct answer
            answer_analysis = self._analyze_answer(correct_answer, question_context)
            
            # Generate distractors using multiple strategies
            distractor_candidates = []
            
            # Strategy 1: Misconception-based distractors
            misconception_distractors = self._generate_misconception_distractors(
                correct_answer, question_context, answer_analysis
            )
            distractor_candidates.extend(misconception_distractors)
            
            # Strategy 2: Numerical variation distractors
            numerical_distractors = self._generate_numerical_distractors(
                correct_answer, question_context, answer_analysis
            )
            distractor_candidates.extend(numerical_distractors)
            
            # Strategy 3: Common wrong methods
            method_distractors = self._generate_method_distractors(
                correct_answer, question_context, answer_analysis
            )
            distractor_candidates.extend(method_distractors)
            
            # Strategy 4: Off-by-one and systematic errors
            systematic_distractors = self._generate_systematic_distractors(
                correct_answer, question_context, answer_analysis
            )
            distractor_candidates.extend(systematic_distractors)
            
            # Filter and rank distractors
            filtered_distractors = self._filter_distractors(
                distractor_candidates, correct_answer, question_context
            )
            
            # Select best distractors
            selected_distractors = self._select_best_distractors(
                filtered_distractors, count
            )
            
            logger.info(f"✅ Generated {len(selected_distractors)} distractors")
            return selected_distractors
            
        except Exception as e:
            logger.error(f"❌ Distractor generation failed: {str(e)}")
            # Fallback: generate simple numerical distractors
            return self._generate_fallback_distractors(correct_answer, count)
    
    def _analyze_answer(self, answer: Union[str, float, int], context: Dict) -> Dict[str, Any]:
        """Analyze the correct answer to inform distractor generation"""
        analysis = {
            "type": "unknown",
            "value": answer,
            "magnitude": 0,
            "decimal_places": 0,
            "is_integer": False,
            "is_fraction": False,
            "sign": 1,
            "special_values": []
        }
        
        try:
            # Handle different answer types
            if isinstance(answer, (int, float)):
                analysis.update(self._analyze_numeric_answer(answer))
            elif isinstance(answer, str):
                analysis.update(self._analyze_string_answer(answer))
            else:
                # Try to convert to float
                try:
                    numeric_val = float(answer)
                    analysis.update(self._analyze_numeric_answer(numeric_val))
                except:
                    analysis["type"] = "symbolic"
            
            # Add context-specific analysis
            subject = context.get("subject", "").lower()
            if "geometry" in subject:
                analysis["domain"] = "geometry"
                analysis["likely_positive"] = True
            elif "algebra" in subject:
                analysis["domain"] = "algebra"
            elif "calculus" in subject:
                analysis["domain"] = "calculus"
            
            return analysis
            
        except Exception as e:
            logger.warning(f"Answer analysis failed: {e}")
            return analysis
    
    def _analyze_numeric_answer(self, value: float) -> Dict[str, Any]:
        """Analyze a numeric answer"""
        return {
            "type": "numeric",
            "magnitude": abs(value),
            "decimal_places": len(str(value).split('.')[-1]) if '.' in str(value) else 0,
            "is_integer": value == int(value),
            "is_fraction": False,  # Could be enhanced to detect simple fractions
            "sign": 1 if value >= 0 else -1,
            "order_of_magnitude": math.floor(math.log10(abs(value))) if value != 0 else 0,
            "is_zero": value == 0,
            "is_one": value == 1,
            "is_small": abs(value) < 1,
            "is_large": abs(value) > 100
        }
    
    def _analyze_string_answer(self, value: str) -> Dict[str, Any]:
        """Analyze a string/symbolic answer"""
        analysis = {"type": "string"}
        
        # Check if it contains numbers
        numbers = re.findall(r'-?\d+\.?\d*', value)
        if numbers:
            analysis["contains_numbers"] = True
            analysis["numbers"] = [float(n) for n in numbers]
        
        # Check for common mathematical expressions
        if 'π' in value or 'pi' in value:
            analysis["contains_pi"] = True
        if '√' in value or 'sqrt' in value:
            analysis["contains_sqrt"] = True
        if any(op in value for op in ['+', '-', '*', '/', '^']):
            analysis["is_expression"] = True
        
        return analysis
    
    def _generate_misconception_distractors(self, correct_answer: Any, 
                                          context: Dict, analysis: Dict) -> List[Dict]:
        """Generate distractors based on common misconceptions"""
        distractors = []
        subject = context.get("subject", "").lower()
        
        # Get relevant misconceptions for the subject
        subject_key = self._map_subject_to_misconception_key(subject)
        if subject_key not in self.misconception_patterns:
            return distractors
        
        misconceptions = self.misconception_patterns[subject_key]
        
        for misconception in misconceptions[:3]:  # Limit to top 3 misconceptions
            try:
                method = misconception["method"]
                distractor_value = self._apply_misconception_method(
                    method, correct_answer, context, analysis
                )
                
                if distractor_value is not None and distractor_value != correct_answer:
                    distractors.append({
                        "value": distractor_value,
                        "generation_method": "misconception",
                        "misconception_type": misconception["name"],
                        "explanation": misconception["description"],
                        "plausibility": 0.8  # Misconceptions are typically very plausible
                    })
                    
            except Exception as e:
                logger.warning(f"Misconception method {method} failed: {e}")
                continue
        
        return distractors
    
    def _generate_numerical_distractors(self, correct_answer: Any, 
                                      context: Dict, analysis: Dict) -> List[Dict]:
        """Generate distractors by numerical variations"""
        distractors = []
        
        if analysis["type"] != "numeric":
            return distractors
        
        value = analysis["value"]
        
        # Strategy 1: Scale by common factors
        factors = [0.5, 2, 3, 4, 0.1, 10]
        for factor in factors[:2]:  # Limit to 2 factors
            distractor_value = value * factor
            if self._is_reasonable_distractor(distractor_value, value, context):
                distractors.append({
                    "value": self._format_number(distractor_value, analysis),
                    "generation_method": "scaling",
                    "scale_factor": factor,
                    "plausibility": 0.6
                })
        
        # Strategy 2: Add/subtract related values
        if abs(value) > 1:
            modifications = [1, -1, value * 0.1, -value * 0.1]
            for mod in modifications[:2]:
                distractor_value = value + mod
                if self._is_reasonable_distractor(distractor_value, value, context):
                    distractors.append({
                        "value": self._format_number(distractor_value, analysis),
                        "generation_method": "modification",
                        "modification": mod,
                        "plausibility": 0.5
                    })
        
        # Strategy 3: Round to different precision
        if analysis["decimal_places"] > 0:
            # Round to integer
            rounded = round(value)
            if rounded != value:
                distractors.append({
                    "value": rounded,
                    "generation_method": "rounding",
                    "round_type": "integer",
                    "plausibility": 0.7
                })
        
        return distractors
    
    def _generate_method_distractors(self, correct_answer: Any, 
                                   context: Dict, analysis: Dict) -> List[Dict]:
        """Generate distractors from common wrong solution methods"""
        distractors = []
        
        # Use template information if available
        template = context.get("template")
        if not template:
            return distractors
        
        template_name = template.get("template_name", "")
        parameters = template.get("parameters", {})
        
        try:
            # Generate method-specific wrong answers
            if "linear_equation" in template_name:
                distractors.extend(self._linear_equation_wrong_methods(parameters, analysis))
            elif "quadratic_equation" in template_name:
                distractors.extend(self._quadratic_equation_wrong_methods(parameters, analysis))
            elif "area" in template_name:
                distractors.extend(self._area_calculation_wrong_methods(parameters, analysis))
            elif "pythagorean" in template_name:
                distractors.extend(self._pythagorean_wrong_methods(parameters, analysis))
                
        except Exception as e:
            logger.warning(f"Method distractor generation failed: {e}")
        
        return distractors
    
    def _generate_systematic_distractors(self, correct_answer: Any, 
                                       context: Dict, analysis: Dict) -> List[Dict]:
        """Generate distractors from systematic errors"""
        distractors = []
        
        if analysis["type"] == "numeric":
            value = analysis["value"]
            
            # Off-by-one errors
            for offset in [1, -1]:
                distractor_value = value + offset
                if self._is_reasonable_distractor(distractor_value, value, context):
                    distractors.append({
                        "value": self._format_number(distractor_value, analysis),
                        "generation_method": "off_by_one",
                        "offset": offset,
                        "plausibility": 0.4
                    })
            
            # Sign errors
            if value != 0:
                sign_error_value = -value
                distractors.append({
                    "value": self._format_number(sign_error_value, analysis),
                    "generation_method": "sign_error",
                    "plausibility": 0.6
                })
            
            # Order of magnitude errors
            if abs(value) > 1:
                for factor in [0.1, 10]:
                    mag_error_value = value * factor
                    if self._is_reasonable_distractor(mag_error_value, value, context):
                        distractors.append({
                            "value": self._format_number(mag_error_value, analysis),
                            "generation_method": "magnitude_error",
                            "factor": factor,
                            "plausibility": 0.5
                        })
        
        return distractors
    
    def _apply_misconception_method(self, method: str, answer: Any, 
                                  context: Dict, analysis: Dict) -> Any:
        """Apply a specific misconception method to generate a distractor"""
        if analysis["type"] != "numeric":
            return None
        
        value = analysis["value"]
        
        if method == "flip_sign":
            return -value if value != 0 else None
        
        elif method == "wrong_operation":
            # Simulate using wrong operation (e.g., + instead of -, * instead of /)
            template = context.get("template", {})
            params = template.get("parameters", {})
            
            if "a" in params and "b" in params:
                a, b = params["a"], params["b"]
                # If correct involved addition, try subtraction
                return abs(a - b) if value == a + b else a + b
        
        elif method == "shift_decimal":
            return value * 10 if abs(value) < 10 else value / 10
        
        elif method == "distribute_wrong":
            # Common algebra distribution errors
            if abs(value) > 1:
                return value * 2  # Common error: (a+b)² = a² + b² instead of a² + 2ab + b²
        
        elif method == "exponent_mistake":
            # Common exponent errors
            if value > 1:
                return value ** 0.5  # Square root instead of square
        
        elif method == "formula_mix":
            # Use wrong formula (common in geometry)
            if "area" in context.get("template", {}).get("template_name", ""):
                # Use perimeter-like calculation instead of area
                params = context.get("template", {}).get("parameters", {})
                if "r" in params:
                    return 2 * math.pi * params["r"]  # Circumference instead of area
        
        return None
    
    def _linear_equation_wrong_methods(self, params: Dict, analysis: Dict) -> List[Dict]:
        """Generate wrong answers for linear equations"""
        distractors = []
        a, b, c = params.get("a", 1), params.get("b", 0), params.get("c", 0)
        
        # Common error: forget to move constant
        wrong1 = (c - b) if a != 0 else None  # Forgot to divide by a
        if wrong1 is not None:
            distractors.append({
                "value": wrong1,
                "generation_method": "linear_error",
                "error_type": "forgot_division",
                "plausibility": 0.7
            })
        
        # Common error: wrong sign when moving terms
        wrong2 = (c + b) / a if a != 0 else None  # Wrong sign when moving b
        if wrong2 is not None:
            distractors.append({
                "value": self._format_number(wrong2, analysis),
                "generation_method": "linear_error", 
                "error_type": "sign_error",
                "plausibility": 0.8
            })
        
        return distractors
    
    def _quadratic_equation_wrong_methods(self, params: Dict, analysis: Dict) -> List[Dict]:
        """Generate wrong answers for quadratic equations"""
        distractors = []
        a, b, c = params.get("a", 1), params.get("b", 0), params.get("c", 0)
        
        # Common error: wrong discriminant calculation
        try:
            wrong_discriminant = b**2 + 4*a*c  # + instead of -
            if wrong_discriminant >= 0:
                wrong_root = (-b + math.sqrt(wrong_discriminant)) / (2*a)
                distractors.append({
                    "value": self._format_number(wrong_root, analysis),
                    "generation_method": "quadratic_error",
                    "error_type": "discriminant_sign",
                    "plausibility": 0.6
                })
        except:
            pass
        
        # Common error: forget the 2 in denominator
        try:
            discriminant = b**2 - 4*a*c
            if discriminant >= 0:
                wrong_root = (-b + math.sqrt(discriminant)) / a  # Missing factor of 2
                distractors.append({
                    "value": self._format_number(wrong_root, analysis),
                    "generation_method": "quadratic_error",
                    "error_type": "denominator_error", 
                    "plausibility": 0.7
                })
        except:
            pass
        
        return distractors
    
    def _area_calculation_wrong_methods(self, params: Dict, analysis: Dict) -> List[Dict]:
        """Generate wrong answers for area calculations"""
        distractors = []
        
        if "r" in params:  # Circle area
            r = params["r"]
            # Common errors: use diameter instead of radius, forget π, use circumference formula
            wrong1 = math.pi * (2*r)**2  # Used diameter instead of radius
            wrong2 = r**2  # Forgot π
            wrong3 = 2 * math.pi * r  # Used circumference formula
            
            for wrong_val, error_type in [(wrong1, "diameter_error"), (wrong2, "forgot_pi"), (wrong3, "wrong_formula")]:
                distractors.append({
                    "value": self._format_number(wrong_val, analysis),
                    "generation_method": "area_error",
                    "error_type": error_type,
                    "plausibility": 0.7
                })
        
        elif "b" in params and "h" in params:  # Triangle area
            b, h = params["b"], params["h"]
            # Common error: forget the 1/2
            wrong_val = b * h
            distractors.append({
                "value": wrong_val,
                "generation_method": "area_error",
                "error_type": "forgot_half",
                "plausibility": 0.8
            })
        
        return distractors
    
    def _pythagorean_wrong_methods(self, params: Dict, analysis: Dict) -> List[Dict]:
        """Generate wrong answers for Pythagorean theorem"""
        distractors = []
        a, b = params.get("a", 3), params.get("b", 4)
        
        # Common errors: add instead of square root of sum of squares, forget to square
        wrong1 = a + b  # Added legs instead of using theorem
        wrong2 = math.sqrt(a + b)  # Square root of sum instead of sum of squares
        wrong3 = a**2 + b**2  # Forgot to take square root
        
        error_types = ["addition_error", "wrong_sqrt", "no_sqrt"]
        for wrong_val, error_type in zip([wrong1, wrong2, wrong3], error_types):
            distractors.append({
                "value": self._format_number(wrong_val, analysis),
                "generation_method": "pythagorean_error",
                "error_type": error_type,
                "plausibility": 0.6
            })
        
        return distractors
    
    def _filter_distractors(self, candidates: List[Dict], correct_answer: Any, 
                          context: Dict) -> List[Dict]:
        """Filter distractors to ensure they are distinct and plausible"""
        filtered = []
        seen_values = {correct_answer}  # Track to avoid duplicates
        
        for distractor in candidates:
            value = distractor["value"]
            
            # Skip if duplicate
            if value in seen_values:
                continue
            
            # Skip if too close to correct answer (for numeric values)
            if isinstance(value, (int, float)) and isinstance(correct_answer, (int, float)):
                if abs(value - correct_answer) < 0.001:  # Very close
                    continue
            
            # Skip unreasonable values
            if not self._is_reasonable_distractor(value, correct_answer, context):
                continue
            
            filtered.append(distractor)
            seen_values.add(value)
        
        return filtered
    
    def _is_reasonable_distractor(self, distractor_value: Any, correct_answer: Any, 
                                context: Dict) -> bool:
        """Check if a distractor value is reasonable for the given context"""
        try:
            # Basic sanity checks for numeric values
            if isinstance(distractor_value, (int, float)):
                # Check for extreme values
                if abs(distractor_value) > 1e6 or (distractor_value != 0 and abs(distractor_value) < 1e-6):
                    return False
                
                # For geometry problems, negative areas/lengths are unreasonable
                subject = context.get("subject", "").lower()
                if "geometry" in subject and distractor_value < 0:
                    return False
                
                # Check if value is within reasonable range of correct answer
                if isinstance(correct_answer, (int, float)) and correct_answer != 0:
                    ratio = abs(distractor_value / correct_answer)
                    if ratio > 100 or ratio < 0.01:  # Too far from correct answer
                        return False
            
            return True
            
        except:
            return False
    
    def _select_best_distractors(self, filtered_distractors: List[Dict], 
                               count: int) -> List[Dict]:
        """Select the best distractors based on plausibility and diversity"""
        if len(filtered_distractors) <= count:
            return filtered_distractors
        
        # Sort by plausibility score
        sorted_distractors = sorted(filtered_distractors, 
                                  key=lambda x: x.get("plausibility", 0.5), 
                                  reverse=True)
        
        # Select diverse set
        selected = []
        generation_methods_used = set()
        
        for distractor in sorted_distractors:
            if len(selected) >= count:
                break
            
            # Prefer diversity in generation methods
            method = distractor.get("generation_method", "unknown")
            if method in generation_methods_used and len(selected) < count // 2:
                continue  # Skip if we already have this method and haven't filled half the slots
            
            selected.append(distractor)
            generation_methods_used.add(method)
        
        # Fill remaining slots if needed
        for distractor in sorted_distractors:
            if len(selected) >= count:
                break
            if distractor not in selected:
                selected.append(distractor)
        
        return selected[:count]
    
    def _generate_fallback_distractors(self, correct_answer: Any, count: int) -> List[Dict]:
        """Generate simple fallback distractors when other methods fail"""
        distractors = []
        
        try:
            if isinstance(correct_answer, (int, float)):
                value = correct_answer
                
                # Simple numerical variations
                variations = [
                    value * 2,
                    value / 2,
                    value + 1,
                    value - 1,
                    -value if value != 0 else 1
                ]
                
                for i, var in enumerate(variations[:count]):
                    distractors.append({
                        "value": var,
                        "generation_method": "fallback",
                        "plausibility": 0.3
                    })
            else:
                # For non-numeric answers, create generic distractors
                for i in range(count):
                    distractors.append({
                        "value": f"Option {chr(65 + i + 1)}",  # B, C, D, etc.
                        "generation_method": "fallback",
                        "plausibility": 0.3
                    })
        
        except:
            # Last resort: generate alphabetic options
            for i in range(count):
                distractors.append({
                    "value": f"Option {chr(65 + i + 1)}",
                    "generation_method": "fallback",
                    "plausibility": 0.3
                })
        
        return distractors
    
    def _format_number(self, value: float, analysis: Dict) -> Union[int, float]:
        """Format a number consistently with the original answer style"""
        try:
            # If original was integer, try to return integer
            if analysis.get("is_integer", False) and abs(value - round(value)) < 0.001:
                return int(round(value))
            
            # Match decimal places of original
            decimal_places = analysis.get("decimal_places", 2)
            if decimal_places == 0:
                return int(round(value))
            else:
                return round(value, min(decimal_places, 4))  # Limit to 4 decimal places
            
        except:
            return value
    
    def _map_subject_to_misconception_key(self, subject: str) -> str:
        """Map subject to misconception pattern key"""
        subject_lower = subject.lower()
        
        if any(term in subject_lower for term in ["algebra", "equation", "solve"]):
            return "algebra"
        elif any(term in subject_lower for term in ["geometry", "area", "triangle", "circle"]):
            return "geometry"
        elif any(term in subject_lower for term in ["calculus", "derivative", "integral"]):
            return "calculus"
        else:
            return "arithmetic"
