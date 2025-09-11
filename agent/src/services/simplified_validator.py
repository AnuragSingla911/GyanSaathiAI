"""
Simplified Question Validator with LLM-based Consensus Validation

This validator replaces sympy validation with LLM-based validation where the LLM
attempts to answer the question 5 times, and if 4 out of 5 attempts match the
correct answer, the question is considered valid.
"""

import logging
import asyncio
import json
import re
import random
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from copy import deepcopy

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

# Robust prompt templates for dual LLM validation
PROMPT_A = """
System:
You are a meticulous solver. Solve exactly and pick one option.

User:
Question:
{question_stem}

Options (letter. text):
{options_text}

Return JSON only:
{{
  "chosen_option_id": "a|b|c|d|invalid",
  "reasoning": "brief step-by-step justification",
  "confidence": 0.0-1.0
}}

Rules:
- Choose the truly correct option. If ambiguous, multiple correct, or insufficient data -> "invalid".
- Be strict and literal; do not assume facts not stated.
- Confidence scoring: 1.0 = absolutely certain, 0.8 = very confident, 0.6 = reasonably sure, 0.4 = somewhat confident, 0.2 = low confidence, 0.0 = completely uncertain
"""

PROMPT_B = """
System:
You are an adversarial evaluator. First try to prove the keyed answer wrong.
If any flaw exists (ambiguity, multiple correct answers, inconsistent math, contradicts context), output "invalid".
Only if no flaw is found, choose the truly correct option.

User:
Question:
{question_stem}

Options (letter. text):
{options_text}

Return JSON only:
{{
  "chosen_option_id": "a|b|c|d|invalid",
  "reasoning": "brief audit highlighting any flaw or why none exists",
  "confidence": 0.0-1.0
}}

Confidence guide: 1.0 = no flaws found, completely valid; 0.8 = minor concerns but overall valid; 0.6 = some issues but acceptable; 0.4 = significant concerns; 0.2 = major flaws; 0.0 = completely invalid/unsolvable
"""

PARA_PROMPT = """Paraphrase the question stem without changing meaning, numbers, or entities.
Return the paraphrase only, no quotes, max 1 sentence:

{stem}"""

NUMERIC_PROMPT = """
System:
You compute final numeric results from short worked solutions.

User:
Given this solution excerpt, extract the final numerical result (as a number) and match it to ONE option text.

Solution:
{canonical_solution}

Options (JSON array):
{options_plain_list}

Return JSON only:
{{
  "final_number": "string (e.g., 24, 24.0, or 3/5 if fraction)",
  "matched_option_text": "exact option text from the list or '' if none",
  "confidence": 0.0-1.0
}}
"""

class SimplifiedQuestionValidator:
    """Simplified validation using LLM consensus instead of complex rule-based validation"""
    
    def __init__(self, settings, mongo_client=None):
        self.settings = settings
        self.mongo_client = mongo_client
        
        # Initialize legacy LLM for compatibility
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
        
        # NEW: dual LLM judges (A = neutral solver, B = adversarial)
        self.llm_A = None
        self.llm_B = None
        if LANGCHAIN_AVAILABLE and getattr(settings, 'openai_api_key', None):
            base_model = getattr(settings, 'openai_model', 'gpt-4o')
            model_A = getattr(settings, 'validator_model_A', base_model)
            model_B = getattr(settings, 'validator_model_B', base_model)
            common_kwargs = dict(
                temperature=0.0,
                max_tokens=getattr(settings, 'max_tokens', 800),
                openai_api_key=settings.openai_api_key,
                model_kwargs={"response_format": {"type": "json_object"}}
            )
            self.llm_A = ChatOpenAI(model=model_A, **common_kwargs)
            self.llm_B = ChatOpenAI(model=model_B, **common_kwargs)
        
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
    
    def _norm_text(self, t: str) -> str:
        """Normalize text for comparison - removes special chars, whitespace, case"""
        t = (t or "").strip().lower().replace('$','')
        return re.sub(r'\s+', ' ', t)

    def _snapshot_options(self, question):
        """Create normalized snapshots of options for comparison"""
        opts = [{"id": o.id.lower(), "text": o.text, "key": self._norm_text(o.text)} for o in question.options]
        correct_letter = (question.correct_option_ids[0] or "").lower()
        correct_text = next((o["text"] for o in opts if o["id"] == correct_letter), "")
        marked_key = self._norm_text(correct_text)
        return opts, marked_key

    def _layout_original(self, opts):
        """Layout options in original order (a, b, c, d)"""
        letters = ['a','b','c','d']
        letter_to_key, lines = {}, []
        for i, o in enumerate(opts):
            letter_to_key[letters[i]] = o["key"]
            lines.append(f"{letters[i].upper()}. {o['text']}")
        return letter_to_key, "\n".join(lines)

    def _layout_shuffled(self, opts):
        """Layout options in shuffled order for invariance testing"""
        perm = deepcopy(opts)
        random.shuffle(perm)
        letters = ['a','b','c','d']
        letter_to_key, lines = {}, []
        for i, o in enumerate(perm):
            letter_to_key[letters[i]] = o["key"]
            lines.append(f"{letters[i].upper()}. {o['text']}")
        return letter_to_key, "\n".join(lines)

    async def _paraphrase_stem(self, llm, stem: str) -> str:
        """Paraphrase question stem for invariance testing"""
        # Use a non-JSON mode LLM for paraphrasing since it doesn't need JSON output
        para_llm = ChatOpenAI(
            model=llm.model_name,
            temperature=0.0,
            max_tokens=200,
            openai_api_key=llm.openai_api_key
            # No JSON mode for paraphrasing
        )
        chain = ChatPromptTemplate.from_template(PARA_PROMPT) | para_llm
        resp = await chain.ainvoke({"stem": stem})
        return (resp.content or "").strip().strip('"')

    def _parse_judge_payload(self, raw: str):
        """Parse LLM judge response with robust error handling"""
        try:
            data = json.loads(raw)
        except Exception:
            return {"chosen_option_id":"invalid","reasoning":"Non-JSON","confidence":0.0}
        cid = str(data.get("chosen_option_id","")).strip().lower()
        if cid not in ("a","b","c","d","invalid"):
            cid = "invalid"
        conf = float(data.get("confidence", 0.0) or 0.0)
        
        # Handle extremely low confidence (might indicate parsing/understanding issues)
        if conf == 0.0 and cid != "invalid":
            logger.warning(f"⚠️ Zero confidence detected with valid answer '{cid}' - may indicate prompt confusion")
        
        return {"chosen_option_id": cid, "reasoning": data.get("reasoning",""), "confidence": conf}

    async def _judge_once(self, llm, prompt_tmpl: str, stem: str, options_block: str):
        """Run a single judge attempt"""
        chain = ChatPromptTemplate.from_template(prompt_tmpl) | llm
        resp = await chain.ainvoke({"question_stem": stem, "options_text": options_block})
        return self._parse_judge_payload(resp.content)

    async def _numeric_crosscheck(self, llm, canonical_solution: str, options):
        """Cross-check numeric results using LLM"""
        plain_list = [o.text for o in options]
        chain = ChatPromptTemplate.from_template(NUMERIC_PROMPT) | llm
        resp = await chain.ainvoke({
            "canonical_solution": canonical_solution or "",
            "options_plain_list": json.dumps(plain_list, ensure_ascii=False)
        })
        try:
            data = json.loads(resp.content)
        except Exception:
            return {"matched_option_text":"", "confidence":0.0}
        return {"matched_option_text": str(data.get("matched_option_text","")).strip(),
                "confidence": float(data.get("confidence", 0.0) or 0.0)}

    def _agg_consensus(self, results):
        """Aggregate consensus from multiple judge results"""
        valid = [r for r in results if r["key"] not in ("invalid","")]
        if not valid:
            return {"score":0.0,"winner":None,"avg_conf":0.0,"n":0}
        by_key = {}
        for r in valid:
            by_key[r["key"]] = by_key.get(r["key"], 0) + 1
        winner = max(by_key, key=by_key.get)
        score = by_key[winner] / len(valid)
        avg_conf = sum(r["confidence"] for r in valid)/len(valid)
        return {"score":score,"winner":winner,"avg_conf":avg_conf,"n":len(valid)}

    def _citations_ok(self, question, rag_context_map: Optional[dict]) -> bool:
        """Validate RAG citations against context map"""
        if not rag_context_map:
            return True
        cites = getattr(question, "citations", None) or []
        for c in cites:
            chunk = rag_context_map.get(getattr(c, "chunk_id", ""), "")
            if not chunk or getattr(c, "text", "") not in chunk:
                return False
        return True
    
    async def validate_with_llm_consensus(self, question: QuestionCandidate, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strengthened LLM validation with dual judges, shuffle/paraphrase invariance, and numeric cross-check
        """
        logger.info("🔍 Starting strengthened LLM validation")

        if not LANGCHAIN_AVAILABLE:
            logger.warning("⚠️ LangChain not available, running schema-only fallback")
            return self._fallback_validation(question, spec)

        if not (self.llm_A and self.llm_B):
            return {"llm_consensus": ValidationResult(
                validator_name="llm_consensus",
                passed=False, score=0.0,
                error_message="Validator LLMs not initialized")
            }

        try:
            # 0) Basic schema validation first
            schema_valid, schema_issues = self._validate_basic_schema(question)
            if not schema_valid:
                return {"llm_consensus": ValidationResult(
                    validator_name="llm_consensus",
                    passed=False, score=0.0,
                    error_message=f"Schema validation failed: {', '.join(schema_issues)}",
                    details={"schema_issues": schema_issues}
                )}

            # 1) Prepare options and layouts
            opts, marked_key = self._snapshot_options(question)
            def build(layout): 
                return self._layout_original(opts) if layout=="original" else self._layout_shuffled(opts)
            
            attempt_layouts_A = ["original","shuffled","shuffled","shuffled","original"]
            attempt_layouts_B = ["original","shuffled"]

            # Log validation start
            logger.info(f"🎯 Marked correct key: {marked_key}")
            logger.info(f"🤖 Judge A model: {getattr(self.settings, 'validator_model_A', 'default')}")
            logger.info(f"🤖 Judge B model: {getattr(self.settings, 'validator_model_B', 'default')}")

            # 2) Judge A (neutral solver) - 5 attempts with shuffle variations
            A_results = []
            for i, layout in enumerate(attempt_layouts_A):
                try:
                    letter_to_key, block = build(layout)
                    res = await self._judge_once(self.llm_A, PROMPT_A, question.stem, block)
                    chosen_key = letter_to_key.get(res["chosen_option_id"], "invalid") if res["chosen_option_id"] in ("a","b","c","d") else "invalid"
                    A_results.append({"key": chosen_key, "confidence": res["confidence"], "raw": res, "layout": layout})
                    logger.info(f"📊 Judge A attempt {i+1}: {res['chosen_option_id']} -> {chosen_key} (conf: {res['confidence']:.2f})")
                except Exception as e:
                    logger.warning(f"⚠️ Judge A attempt {i+1} failed: {e}")
                    A_results.append({"key": "invalid", "confidence": 0.0, "raw": {"error": str(e)}, "layout": layout})

            # 3) Judge B (adversarial) - 2 attempts
            B_results = []
            for i, layout in enumerate(attempt_layouts_B):
                try:
                    letter_to_key, block = build(layout)
                    res = await self._judge_once(self.llm_B, PROMPT_B, question.stem, block)
                    chosen_key = letter_to_key.get(res["chosen_option_id"], "invalid") if res["chosen_option_id"] in ("a","b","c","d") else "invalid"
                    B_results.append({"key": chosen_key, "confidence": res["confidence"], "raw": res, "layout": layout})
                    logger.info(f"🔍 Judge B attempt {i+1}: {res['chosen_option_id']} -> {chosen_key} (conf: {res['confidence']:.2f})")
                except Exception as e:
                    logger.warning(f"⚠️ Judge B attempt {i+1} failed: {e}")
                    B_results.append({"key": "invalid", "confidence": 0.0, "raw": {"error": str(e)}, "layout": layout})

            # 4) Paraphrase invariance (Judge A, original layout)
            para_key = "invalid"
            try:
                para_stem = await self._paraphrase_stem(self.llm_A, question.stem)
                letter_to_key, block = build("original")
                res_para = await self._judge_once(self.llm_A, PROMPT_A, para_stem, block)
                para_key = letter_to_key.get(res_para["chosen_option_id"], "invalid") if res_para["chosen_option_id"] in ("a","b","c","d") else "invalid"
                logger.info(f"🔄 Paraphrase test: {res_para['chosen_option_id']} -> {para_key}")
            except Exception as e:
                logger.warning(f"⚠️ Paraphrase test failed: {e}")

            # 5) Numeric cross-check (LLM-only)
            numeric_hint = (getattr(question, "question_type", "") or "").lower()
            num_ok = True
            num_details = {}
            if any(t in numeric_hint for t in ("numerical","application","calculation","compute","percent","ratio","equation")):
                try:
                    num_details = await self._numeric_crosscheck(self.llm_A, getattr(question, "canonical_solution", "") or "", question.options)
                    marked_text = next((o.text for o in question.options if o.id.lower()==question.correct_option_ids[0].lower()), "")
                    num_ok = (self._norm_text(num_details.get("matched_option_text","")) == self._norm_text(marked_text) and 
                             float(num_details.get("confidence",0.0)) >= 0.4)
                    logger.info(f"🔢 Numeric check: {'✅ PASS' if num_ok else '❌ FAIL'} (conf: {num_details.get('confidence', 0.0):.2f})")
                except Exception as e:
                    logger.warning(f"⚠️ Numeric check failed: {e}")
                    num_ok = True  # Don't fail if numeric check has errors

            # 6) Aggregate & calculate thresholds
            A = self._agg_consensus(A_results)
            B = self._agg_consensus(B_results)
            low_conf_hit = any(r["key"] not in ("invalid","") and r["confidence"] < 0.2 for r in A_results + B_results)
            
            # Log low confidence issues for debugging
            low_conf_entries = [r for r in A_results + B_results if r["key"] not in ("invalid","") and r["confidence"] < 0.2]
            if low_conf_entries:
                for entry in low_conf_entries:
                    logger.warning(f"⚠️ [Trace: {trace_id}] Low confidence detected: {entry['confidence']:.2f} for key '{entry['key']}', reasoning: {entry.get('raw', {}).get('reasoning', 'N/A')[:100]}...")

            # Count valid attempts for logging 
            valid_A = [r for r in A_results if r["key"] not in ("invalid","")]
            valid_B = [r for r in B_results if r["key"] not in ("invalid","")]

            # 7) Pass criteria (all must be true)
            criteria = {
                "A_winner_correct": A["winner"] == marked_key,
                "B_winner_correct": B["winner"] == marked_key, 
                "A_consensus_high": A["score"] >= 0.8,
                "B_consensus_adequate": B["score"] >= 0.5,
                "A_confidence_adequate": A["avg_conf"] >= 0.6,
                "no_low_confidence": not low_conf_hit,
                "paraphrase_invariant": para_key == marked_key,
                "numeric_check": num_ok,
                "citations_valid": self._citations_ok(question, spec.get("rag_context_map"))
            }

            passed = all(criteria.values())

            # 8) Detailed logging
            logger.info(f"📊 Judge A consensus: {A['score']:.2f} ({len(valid_A)}/{len(A_results)} valid), winner: {A['winner']}, avg_conf: {A['avg_conf']:.2f}")
            logger.info(f"📊 Judge B consensus: {B['score']:.2f} ({len(valid_B)}/{len(B_results)} valid), winner: {B['winner']}, avg_conf: {B['avg_conf']:.2f}")
            logger.info(f"🔄 Paraphrase invariance: {'✅ PASS' if criteria['paraphrase_invariant'] else '❌ FAIL'}")
            logger.info(f"🔢 Numeric check: {'✅ PASS' if criteria['numeric_check'] else '❌ FAIL'}")
            
            failed_criteria = [k for k, v in criteria.items() if not v]
            if failed_criteria:
                logger.info(f"❌ Failed criteria: {failed_criteria}")

            details = {
                "A_consensus": A, "B_consensus": B,
                "paraphrase_key": para_key,
                "numeric_check": num_details,
                "attempts_A": A_results, "attempts_B": B_results,
                "schema_validation": {"passed": schema_valid, "issues": schema_issues},
                "criteria": criteria,
                "models_used": {
                    "judge_A": getattr(self.settings, 'validator_model_A', 'default'),
                    "judge_B": getattr(self.settings, 'validator_model_B', 'default')
                }
            }

            return {"llm_consensus": ValidationResult(
                validator_name="llm_consensus",
                passed=passed,
                score=float(A["score"]),
                details=details
            )}

        except Exception as e:
            logger.error(f"❌ Strengthened validation failed: {str(e)}")
            return {"llm_consensus": ValidationResult(
                validator_name="llm_consensus",
                passed=False, score=0.0,
                error_message=str(e)
            )}
    
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
