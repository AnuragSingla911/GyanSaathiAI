"""
Template Inducer for Parametric LaTeX Pattern Generation

This service analyzes mathematical topics and generates parametric LaTeX templates
that can be instantiated with specific values to create consistent problem types.
Uses SymPy for mathematical computation and validation.
"""

import logging
import random
import re
import sympy as sp
from sympy import symbols, solve, simplify, expand, factor, latex
from typing import Dict, List, Any, Optional, Tuple, Union
import signal
import asyncio
from contextlib import contextmanager
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

@contextmanager
def timeout(seconds):
    """Context manager for timing out SymPy operations"""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    # Set the signal handler and a timeout alarm
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Restore the old handler and cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)
        signal.alarm(0)

class TemplateInducer:
    """
    Generates parametric mathematical templates from topic specifications.
    Creates LaTeX patterns with variables that can be instantiated with specific values.
    """
    
    def __init__(self, settings):
        self.settings = settings
        self.template_registry = self._build_template_registry()
        
    def _build_template_registry(self) -> Dict[str, List[Dict]]:
        """Build registry of mathematical templates organized by topic"""
        return {
            "algebra": [
                {
                    "name": "linear_equation",
                    "pattern": "{a}x + {b} = {c}",
                    "latex_pattern": r"{a}x + {b} = {c}",
                    "variables": ["a", "b", "c"],
                    "constraints": {"a": "a != 0", "b": "True", "c": "True"},
                    "solution_method": "linear_solve",
                    "difficulty_factors": {"easy": {"a": (1, 5), "b": (1, 10), "c": (1, 20)},
                                          "medium": {"a": (2, 10), "b": (-10, 10), "c": (-20, 20)},
                                          "hard": {"a": (-15, 15), "b": (-25, 25), "c": (-50, 50)}}
                },
                {
                    "name": "quadratic_equation",
                    "pattern": "{a}x² + {b}x + {c} = 0",
                    "latex_pattern": r"{a}x^2 + {b}x + {c} = 0",
                    "variables": ["a", "b", "c"],
                    "constraints": {"a": "a != 0", "b": "True", "c": "True"},
                    "solution_method": "quadratic_solve",
                    "difficulty_factors": {"easy": {"a": (1, 3), "b": (-5, 5), "c": (-6, 6)},
                                          "medium": {"a": (1, 5), "b": (-10, 10), "c": (-15, 15)},
                                          "hard": {"a": (-8, 8), "b": (-20, 20), "c": (-25, 25)}}
                },
                {
                    "name": "system_linear",
                    "pattern": "{a}x + {b}y = {c}\\n{d}x + {e}y = {f}",
                    "latex_pattern": r"\begin{{align}} {a}x + {b}y &= {c} \\ {d}x + {e}y &= {f} \end{{align}}",
                    "variables": ["a", "b", "c", "d", "e", "f"],
                    "constraints": {"a": "a != 0", "b": "b != 0", "d": "d != 0", "e": "e != 0"},
                    "solution_method": "system_solve",
                    "difficulty_factors": {"easy": {"a": (1, 3), "b": (1, 3), "c": (1, 10), "d": (1, 3), "e": (1, 3), "f": (1, 10)},
                                          "medium": {"a": (1, 5), "b": (1, 5), "c": (-15, 15), "d": (1, 5), "e": (1, 5), "f": (-15, 15)},
                                          "hard": {"a": (-8, 8), "b": (-8, 8), "c": (-25, 25), "d": (-8, 8), "e": (-8, 8), "f": (-25, 25)}}
                }
            ],
            "geometry": [
                {
                    "name": "circle_area",
                    "pattern": "Find the area of a circle with radius {r}",
                    "latex_pattern": r"A = \pi r^2 \text{{ where }} r = {r}",
                    "variables": ["r"],
                    "constraints": {"r": "r > 0"},
                    "solution_method": "circle_area_calc",
                    "difficulty_factors": {"easy": {"r": (1, 5)},
                                          "medium": {"r": (3, 12)},
                                          "hard": {"r": (5, 25)}}
                },
                {
                    "name": "pythagorean",
                    "pattern": "Right triangle with legs {a} and {b}",
                    "latex_pattern": r"c^2 = a^2 + b^2 \text{{ where }} a = {a}, b = {b}",
                    "variables": ["a", "b"],
                    "constraints": {"a": "a > 0", "b": "b > 0"},
                    "solution_method": "pythagorean_calc",
                    "difficulty_factors": {"easy": {"a": (3, 8), "b": (4, 10)},
                                          "medium": {"a": (5, 15), "b": (6, 18)},
                                          "hard": {"a": (8, 25), "b": (10, 30)}}
                },
                {
                    "name": "triangle_area",
                    "pattern": "Triangle with base {b} and height {h}",
                    "latex_pattern": r"A = \frac{{1}}{{2}}bh \text{{ where }} b = {b}, h = {h}",
                    "variables": ["b", "h"],
                    "constraints": {"b": "b > 0", "h": "h > 0"},
                    "solution_method": "triangle_area_calc",
                    "difficulty_factors": {"easy": {"b": (2, 8), "h": (2, 8)},
                                          "medium": {"b": (4, 15), "h": (3, 12)},
                                          "hard": {"b": (8, 25), "h": (6, 20)}}
                }
            ],
            "calculus": [
                {
                    "name": "power_rule",
                    "pattern": "Derivative of {a}x^{n}",
                    "latex_pattern": r"\frac{{d}}{{dx}}[{a}x^{{{n}}}]",
                    "variables": ["a", "n"],
                    "constraints": {"a": "a != 0", "n": "n > 0"},
                    "solution_method": "power_rule_calc",
                    "difficulty_factors": {"easy": {"a": (1, 5), "n": (1, 4)},
                                          "medium": {"a": (1, 10), "n": (2, 8)},
                                          "hard": {"a": (-15, 15), "n": (1, 12)}}
                },
                {
                    "name": "basic_integral",
                    "pattern": "Integral of {a}x^{n}",
                    "latex_pattern": r"\int {a}x^{{{n}}} dx",
                    "variables": ["a", "n"],
                    "constraints": {"a": "a != 0", "n": "n != -1"},
                    "solution_method": "basic_integral_calc",
                    "difficulty_factors": {"easy": {"a": (1, 5), "n": (1, 4)},
                                          "medium": {"a": (1, 10), "n": (0, 8)},
                                          "hard": {"a": (-15, 15), "n": (-5, 12)}}
                }
            ],
            "precalculus": [
                {
                    "name": "exponential_equation",
                    "pattern": "{a}^x = {b}",
                    "latex_pattern": r"{a}^x = {b}",
                    "variables": ["a", "b"],
                    "constraints": {"a": "a > 0 and a != 1", "b": "b > 0"},
                    "solution_method": "exponential_solve",
                    "difficulty_factors": {"easy": {"a": (2, 5), "b": (2, 25)},
                                          "medium": {"a": (2, 10), "b": (1, 100)},
                                          "hard": {"a": (2, 15), "b": (1, 1000)}}
                },
                {
                    "name": "log_equation",
                    "pattern": "log_{a}(x) = {b}",
                    "latex_pattern": r"\log_{{{a}}}(x) = {b}",
                    "variables": ["a", "b"],
                    "constraints": {"a": "a > 0 and a != 1", "b": "True"},
                    "solution_method": "log_solve",
                    "difficulty_factors": {"easy": {"a": (2, 5), "b": (1, 4)},
                                          "medium": {"a": (2, 10), "b": (0, 6)},
                                          "hard": {"a": (2, 15), "b": (-3, 8)}}
                }
            ]
        }
    
    async def induce_template(self, topic: str, difficulty: str = "medium", 
                             subject_hint: str = "") -> Optional[Dict[str, Any]]:
        """
        Generate a parametric template for the given topic and difficulty.
        Returns template with instantiated values and canonical solution.
        """
        logger.info(f"🎯 Inducing template for topic: {topic}, difficulty: {difficulty}")
        
        try:
            # Find matching templates
            matching_templates = self._find_matching_templates(topic, subject_hint)
            
            if not matching_templates:
                logger.warning(f"⚠️ No templates found for topic: {topic}")
                return None
            
            # Select best template
            selected_template = self._select_best_template(matching_templates, difficulty)
            
            # Generate parameter values
            parameters = self._generate_parameters(selected_template, difficulty)
            
            # Instantiate template
            instantiated = self._instantiate_template(selected_template, parameters)
            
            # Compute canonical solution
            solution = await self._compute_canonical_solution(selected_template, parameters)
            
            template_result = {
                "template_id": f"{selected_template['name']}_{difficulty}",
                "template_name": selected_template["name"],
                "topic": topic,
                "difficulty": difficulty,
                "pattern": selected_template["pattern"],
                "latex_pattern": selected_template["latex_pattern"],
                "parameters": parameters,
                "instantiated_problem": instantiated["problem"],
                "instantiated_latex": instantiated["latex"],
                "canonical_solution": solution,
                "metadata": {
                    "generated_at": datetime.utcnow(),
                    "method": selected_template["solution_method"],
                    "confidence": self._calculate_template_confidence(selected_template, topic)
                }
            }
            
            logger.info(f"✅ Template induced successfully: {template_result['template_id']}")
            return template_result
            
        except Exception as e:
            logger.error(f"❌ Template induction failed: {str(e)}")
            return None
    
    def _find_matching_templates(self, topic: str, subject_hint: str = "") -> List[Dict]:
        """Find templates that match the given topic"""
        matching = []
        topic_lower = topic.lower()
        subject_lower = subject_hint.lower()
        
        # Direct subject match
        if subject_lower in self.template_registry:
            matching.extend(self.template_registry[subject_lower])
        
        # Keyword matching across all subjects
        keywords = topic_lower.split()
        for subject, templates in self.template_registry.items():
            for template in templates:
                template_keywords = template["name"].split("_") + [subject]
                if any(keyword in template_keywords for keyword in keywords):
                    if template not in matching:
                        matching.append(template)
        
        # Fuzzy matching for common math terms
        math_term_mapping = {
            "equation": ["linear_equation", "quadratic_equation", "exponential_equation", "log_equation"],
            "solve": ["linear_equation", "quadratic_equation", "system_linear"],
            "area": ["circle_area", "triangle_area"],
            "derivative": ["power_rule"],
            "integral": ["basic_integral"],
            "triangle": ["pythagorean", "triangle_area"],
            "circle": ["circle_area"],
            "system": ["system_linear"]
        }
        
        for term, template_names in math_term_mapping.items():
            if term in topic_lower:
                for subject, templates in self.template_registry.items():
                    for template in templates:
                        if template["name"] in template_names and template not in matching:
                            matching.append(template)
        
        return matching
    
    def _select_best_template(self, templates: List[Dict], difficulty: str) -> Dict:
        """Select the best template based on difficulty and other factors"""
        if len(templates) == 1:
            return templates[0]
        
        # Score templates based on difficulty availability and complexity
        scored_templates = []
        for template in templates:
            score = 0
            
            # Check if template has difficulty factors
            if difficulty in template.get("difficulty_factors", {}):
                score += 2
            
            # Prefer templates with appropriate complexity for difficulty
            var_count = len(template.get("variables", []))
            if difficulty == "easy" and var_count <= 2:
                score += 1
            elif difficulty == "medium" and 2 <= var_count <= 4:
                score += 1
            elif difficulty == "hard" and var_count >= 3:
                score += 1
            
            scored_templates.append((template, score))
        
        # Sort by score and return best
        scored_templates.sort(key=lambda x: x[1], reverse=True)
        return scored_templates[0][0]
    
    def _generate_parameters(self, template: Dict, difficulty: str) -> Dict[str, Any]:
        """Generate parameter values based on template constraints and difficulty"""
        parameters = {}
        difficulty_factors = template.get("difficulty_factors", {}).get(difficulty, {})
        
        for var in template["variables"]:
            if var in difficulty_factors:
                # Use difficulty-specific range
                min_val, max_val = difficulty_factors[var]
                value = random.randint(min_val, max_val)
            else:
                # Default range based on difficulty
                if difficulty == "easy":
                    value = random.randint(1, 5)
                elif difficulty == "medium":
                    value = random.randint(1, 10)
                else:  # hard
                    value = random.randint(-15, 15)
                    if value == 0:
                        value = random.choice([-1, 1])
            
            # Apply constraints
            constraints = template.get("constraints", {})
            if var in constraints:
                constraint = constraints[var]
                max_attempts = 50
                attempt = 0
                
                while not self._check_constraint(value, var, constraint) and attempt < max_attempts:
                    if difficulty == "easy":
                        value = random.randint(1, 5)
                    elif difficulty == "medium":
                        value = random.randint(1, 10)
                    else:
                        value = random.randint(-15, 15)
                        if value == 0:
                            value = random.choice([-1, 1])
                    attempt += 1
                
                if attempt >= max_attempts:
                    # Fallback to safe value
                    value = 1 if "!= 0" in constraint else random.randint(1, 5)
            
            parameters[var] = value
        
        return parameters
    
    def _check_constraint(self, value: int, var: str, constraint: str) -> bool:
        """Check if a value satisfies the given constraint"""
        try:
            # Replace variable name with actual value in constraint
            eval_constraint = constraint.replace(var, str(value))
            return eval(eval_constraint)
        except:
            return True  # If constraint can't be evaluated, assume it's satisfied
    
    def _instantiate_template(self, template: Dict, parameters: Dict) -> Dict[str, str]:
        """Instantiate the template with specific parameter values"""
        problem = template["pattern"]
        latex = template["latex_pattern"]
        
        # Replace placeholders with actual values
        for var, value in parameters.items():
            placeholder = "{" + var + "}"
            problem = problem.replace(placeholder, str(value))
            latex = latex.replace(placeholder, str(value))
        
        # Clean up formatting
        problem = self._clean_mathematical_text(problem)
        latex = self._clean_latex(latex)
        
        return {
            "problem": problem,
            "latex": latex
        }
    
    async def _compute_canonical_solution(self, template: Dict, parameters: Dict) -> Dict[str, Any]:
        """Compute the canonical solution using SymPy"""
        method = template.get("solution_method", "")
        
        try:
            with timeout(self.settings.sympy_timeout_seconds):
                if method == "linear_solve":
                    return self._solve_linear(parameters)
                elif method == "quadratic_solve":
                    return self._solve_quadratic(parameters)
                elif method == "system_solve":
                    return self._solve_system(parameters)
                elif method == "circle_area_calc":
                    return self._calc_circle_area(parameters)
                elif method == "pythagorean_calc":
                    return self._calc_pythagorean(parameters)
                elif method == "triangle_area_calc":
                    return self._calc_triangle_area(parameters)
                elif method == "power_rule_calc":
                    return self._calc_power_rule(parameters)
                elif method == "basic_integral_calc":
                    return self._calc_basic_integral(parameters)
                elif method == "exponential_solve":
                    return self._solve_exponential(parameters)
                elif method == "log_solve":
                    return self._solve_log(parameters)
                else:
                    return {"error": f"Unknown solution method: {method}"}
                    
        except TimeoutError:
            logger.error(f"⏰ SymPy computation timed out for method: {method}")
            return {"error": "Computation timed out"}
        except Exception as e:
            logger.error(f"❌ SymPy computation failed: {str(e)}")
            return {"error": str(e)}
    
    def _solve_linear(self, params: Dict) -> Dict[str, Any]:
        """Solve linear equation ax + b = c"""
        a, b, c = params['a'], params['b'], params['c']
        x = symbols('x')
        equation = a*x + b - c
        solution = solve(equation, x)
        
        return {
            "solution": solution[0] if solution else "No solution",
            "steps": [
                f"Given: {a}x + {b} = {c}",
                f"Subtract {b} from both sides: {a}x = {c - b}",
                f"Divide by {a}: x = {(c - b)/a}" if a != 0 else "Cannot divide by zero"
            ],
            "answer": float(solution[0]) if solution else None
        }
    
    def _solve_quadratic(self, params: Dict) -> Dict[str, Any]:
        """Solve quadratic equation ax² + bx + c = 0"""
        a, b, c = params['a'], params['b'], params['c']
        x = symbols('x')
        equation = a*x**2 + b*x + c
        solutions = solve(equation, x)
        
        return {
            "solution": solutions,
            "steps": [
                f"Given: {a}x² + {b}x + {c} = 0",
                "Using quadratic formula: x = (-b ± √(b² - 4ac)) / 2a",
                f"Discriminant: {b}² - 4({a})({c}) = {b**2 - 4*a*c}"
            ],
            "answer": [float(sol.evalf()) for sol in solutions] if solutions else None
        }
    
    def _solve_system(self, params: Dict) -> Dict[str, Any]:
        """Solve system of linear equations"""
        a, b, c, d, e, f = params['a'], params['b'], params['c'], params['d'], params['e'], params['f']
        x, y = symbols('x y')
        eq1 = a*x + b*y - c
        eq2 = d*x + e*y - f
        solution = solve([eq1, eq2], [x, y])
        
        return {
            "solution": solution,
            "steps": [
                f"Equation 1: {a}x + {b}y = {c}",
                f"Equation 2: {d}x + {e}y = {f}",
                "Solving system using substitution or elimination"
            ],
            "answer": {
                "x": float(solution[x].evalf()) if solution and x in solution else None,
                "y": float(solution[y].evalf()) if solution and y in solution else None
            } if solution else None
        }
    
    def _calc_circle_area(self, params: Dict) -> Dict[str, Any]:
        """Calculate circle area"""
        r = params['r']
        area = sp.pi * r**2
        
        return {
            "solution": area,
            "steps": [
                f"Given radius: r = {r}",
                "Formula: A = πr²",
                f"A = π × {r}² = {r**2}π"
            ],
            "answer": float(area.evalf())
        }
    
    def _calc_pythagorean(self, params: Dict) -> Dict[str, Any]:
        """Calculate hypotenuse using Pythagorean theorem"""
        a, b = params['a'], params['b']
        c = sp.sqrt(a**2 + b**2)
        
        return {
            "solution": c,
            "steps": [
                f"Given legs: a = {a}, b = {b}",
                "Pythagorean theorem: c² = a² + b²",
                f"c² = {a}² + {b}² = {a**2} + {b**2} = {a**2 + b**2}",
                f"c = √{a**2 + b**2}"
            ],
            "answer": float(c.evalf())
        }
    
    def _calc_triangle_area(self, params: Dict) -> Dict[str, Any]:
        """Calculate triangle area"""
        b, h = params['b'], params['h']
        area = sp.Rational(1, 2) * b * h
        
        return {
            "solution": area,
            "steps": [
                f"Given base: b = {b}, height: h = {h}",
                "Formula: A = ½bh",
                f"A = ½ × {b} × {h} = {float(area)}"
            ],
            "answer": float(area)
        }
    
    def _calc_power_rule(self, params: Dict) -> Dict[str, Any]:
        """Calculate derivative using power rule"""
        a, n = params['a'], params['n']
        x = symbols('x')
        function = a * x**n
        derivative = sp.diff(function, x)
        
        return {
            "solution": derivative,
            "steps": [
                f"Given function: f(x) = {a}x^{n}",
                "Power rule: d/dx[ax^n] = nax^(n-1)",
                f"f'(x) = {n} × {a}x^({n}-1) = {a*n}x^{n-1}"
            ],
            "answer": str(derivative)
        }
    
    def _calc_basic_integral(self, params: Dict) -> Dict[str, Any]:
        """Calculate basic integral"""
        a, n = params['a'], params['n']
        x = symbols('x')
        function = a * x**n
        integral = sp.integrate(function, x)
        
        return {
            "solution": integral,
            "steps": [
                f"Given function: f(x) = {a}x^{n}",
                "Power rule for integration: ∫ax^n dx = (a/(n+1))x^(n+1) + C",
                f"∫{a}x^{n} dx = {a/(n+1)}x^{n+1} + C"
            ],
            "answer": str(integral) + " + C"
        }
    
    def _solve_exponential(self, params: Dict) -> Dict[str, Any]:
        """Solve exponential equation"""
        a, b = params['a'], params['b']
        x = symbols('x')
        equation = a**x - b
        solution = solve(equation, x)
        
        return {
            "solution": solution[0] if solution else "No solution",
            "steps": [
                f"Given: {a}^x = {b}",
                f"Take log base {a} of both sides: x = log_{a}({b})",
                f"x = ln({b})/ln({a})"
            ],
            "answer": float(solution[0].evalf()) if solution else None
        }
    
    def _solve_log(self, params: Dict) -> Dict[str, Any]:
        """Solve logarithmic equation"""
        a, b = params['a'], params['b']
        x = symbols('x')
        solution = a**b  # If log_a(x) = b, then x = a^b
        
        return {
            "solution": solution,
            "steps": [
                f"Given: log_{a}(x) = {b}",
                f"Convert to exponential form: x = {a}^{b}",
                f"x = {solution}"
            ],
            "answer": float(solution)
        }
    
    def _calculate_template_confidence(self, template: Dict, topic: str) -> float:
        """Calculate confidence score for template selection"""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for exact name matches
        if template["name"].lower() in topic.lower():
            confidence += 0.3
        
        # Boost for keyword matches
        template_keywords = template["name"].split("_")
        topic_words = topic.lower().split()
        matches = sum(1 for word in topic_words if any(keyword in word for keyword in template_keywords))
        confidence += min(matches * 0.1, 0.2)
        
        return min(confidence, 1.0)
    
    def _clean_mathematical_text(self, text: str) -> str:
        """Clean up mathematical text formatting"""
        # Replace common formatting issues
        text = text.replace("\\n", " ")
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text
    
    def _clean_latex(self, latex: str) -> str:
        """Clean up LaTeX formatting"""
        # Ensure proper spacing around operators
        latex = re.sub(r'(\d)([+\-])', r'\1 \2 ', latex)
        latex = re.sub(r'([+\-])(\d)', r'\1 \2', latex)
        latex = re.sub(r'\s+', ' ', latex)
        latex = latex.strip()
        return latex
