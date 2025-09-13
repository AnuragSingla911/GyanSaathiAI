"""
Simplified Question Generator

This service implements a streamlined question generation pipeline:
1. RAG Retrieval → LLM Generation → LLM-based Validation → Persister

Uses only RAG content retrieval and LLM-based validation.
"""

import logging
import asyncio
import uuid
import json
import random
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

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
from .simplified_validator import SimplifiedQuestionValidator

logger = logging.getLogger(__name__)

class EnhancedQuestionGenerator:
    """
    Simplified question generation pipeline using only RAG retrieval and LLM validation.
    """
    
    def __init__(self, rag_retriever, hendrycks_manager, mongo_client, vector_store):
        self.settings = get_settings()
        self.rag_retriever = rag_retriever
        self.mongo_client = mongo_client
        self.vector_store = vector_store
        
        # Initialize simplified validator
        self.validator = SimplifiedQuestionValidator(self.settings, mongo_client)
        
        # Initialize LLM only if LangChain is available
        if LANGCHAIN_AVAILABLE and hasattr(self.settings, 'openai_api_key') and self.settings.openai_api_key:
            self.llm = ChatOpenAI(
                model=getattr(self.settings, 'openai_model', 'gpt-3.5-turbo'),
                temperature=0.6,  # Balanced: some variety but maintains accuracy
                max_tokens=getattr(self.settings, 'max_tokens', 1000),
                openai_api_key=self.settings.openai_api_key,
                model_kwargs={
                    "response_format": {"type": "json_object"},
                    "user": str(uuid.uuid4())[:8]  # Random user ID to break caching
                }
            )
        else:
            self.llm = None
        
        # Anti-duplication tracking
        self.recent_questions = []  # Store recent question stems for duplicate detection
        self.max_recent_questions = 50  # Keep track of last 50 questions
        
        # Setup simplified prompts only if LangChain is available
        if LANGCHAIN_AVAILABLE:
            self._setup_simplified_prompts()
        else:
            self.generation_prompt = None
    
    def _normalize_question(self, question_text: str) -> str:
        """Normalize question text for duplicate detection"""
        return question_text.lower().strip().replace('?', '').replace('.', '').replace(',', '')
    
    def _is_duplicate(self, new_question: str, similarity_threshold: float = 0.85) -> bool:
        """Check if a question is too similar to recently generated ones"""
        if not self.recent_questions:
            return False
        
        normalized_new = self._normalize_question(new_question)
        
        for recent_q in self.recent_questions:
            normalized_recent = self._normalize_question(recent_q)
            similarity = SequenceMatcher(None, normalized_new, normalized_recent).ratio()
            if similarity > similarity_threshold:
                logger.warning(f"🔄 Duplicate detected: {similarity:.2f} similarity")
                return True
        return False
    
    def _add_to_recent_questions(self, question_stem: str):
        """Add question to recent questions list, maintaining max size"""
        self.recent_questions.append(question_stem)
        if len(self.recent_questions) > self.max_recent_questions:
            self.recent_questions.pop(0)  # Remove oldest
    
    def _get_variety_prompt_additions(self, attempt: int = 0) -> str:
        """Generate variety-enhancing prompt additions with increasing strength"""
        import time
        
        # Base variety prompts for original content creation
        variety_prompts = [
            "Create a completely original scenario inspired by the RAG patterns but with new contexts and numbers.",
            "Invent a fresh real-world application using the educational structure from RAG as inspiration only.",
            "Design a unique problem that follows the difficulty pattern shown in RAG but with entirely new content.",
            "Create an original story-based question using the question style patterns from RAG reference material.",
            "Generate a new analytical challenge inspired by the complexity level demonstrated in the RAG context.",
            "Invent a novel scenario that tests the same learning objectives but with completely different examples.",
            "Create original content using the mathematical notation style from RAG but with new formulas and values.",
            "Design a fresh conceptual question inspired by the educational approach shown in the reference material.",
            "Generate a unique multi-step problem using the structure patterns from RAG but with original scenarios.",
            "Create an innovative application question inspired by the difficulty progression shown in the context.",
            "Invent a new comparative analysis using the question framework from RAG as structural inspiration.",
            "Design original content that matches the educational depth of RAG but with completely new subject matter."
        ]
        
        # Add randomness and timestamp
        timestamp_seed = int(time.time() * 1000) % 10000  # Use milliseconds for variety
        random_elements = [
            f"[Creativity Seed: {timestamp_seed}]",
            f"[Uniqueness Factor: {random.randint(100, 999)}]",
            f"[Variation Mode: {random.choice(['analytical', 'applied', 'conceptual', 'practical'])}]"
        ]
        
        base_prompt = random.choice(variety_prompts)
        random_element = random.choice(random_elements)
        
        # Escalate instructions based on attempt number
        if attempt == 0:
            return f"{base_prompt} {random_element}"
        elif attempt == 1:
            return f"IMPORTANT: Generate something COMPLETELY DIFFERENT from the previous attempt! {base_prompt} {random_element} Use different numbers, scenarios, and focus areas."
        else:
            return f"CRITICAL: This is attempt #{attempt + 1} - you MUST create a totally different question! Change the approach, numbers, context, and perspective entirely! {base_prompt} {random_element} Be maximally creative and unique!"
    
    def _setup_simplified_prompts(self):
        """Setup simplified prompts for RAG-inspired generation"""
        if not ChatPromptTemplate:
            self.generation_prompt = None
            return
        self.generation_prompt = ChatPromptTemplate.from_template("""
You are an expert educational item writer and meticulous math checker.

Generate ONE completely NEW and ORIGINAL multiple-choice question using the sanitized RAG context **only** for pattern/style/difficulty guidance.

# Inputs
- Subject: {{subject}}
- Topic: {{topic}}
- Difficulty: {{difficulty}}
- Question Type: {{question_type}}
- Reference Context (sanitized; if anything looks malformed or truncated, IGNORE the specifics and keep only topic/pattern/difficulty):
{{rag_context}}

# Output format (JSON only — no extra keys, no trailing commas)
{{
  "stem": "...",
  "options": [
    {{"id":"a","text":"..."}},
    {{"id":"b","text":"..."}},
    {{"id":"c","text":"..."}},
    {{"id":"d","text":"..."}}
  ],
  "correct_option_ids": ["a"],
  "canonical_solution": "...",
  "explanation": "...",
  "citations": [
    {{"chunk_id":"source_1","text":"Inspired by [concept/pattern] from this source"}}
  ]
}}

# Non-negotiable rules
1) **RAG Inspiration Only**: Do NOT copy numbers, names, or contexts. Invent new clean values. Mirror only the pattern/difficulty/notation style.
2) **Inline LaTeX only**: Use `$...$` (e.g., `$x^2$`, `$\\frac{{3}}{{5}}$`, `$\\%$`). Do NOT use `\\begin{{align}}`, `\\[`, or `$$`.
3) **Options**: Exactly four (a,b,c,d). Mutually exclusive. Similar length. No “All/None of the above”.
4) **Exactly one correct answer** in "correct_option_ids".
5) **Difficulty fit**:
   - Easy: direct application (≈1 step) with exact, clean numbers.
   - Medium: 1–2 steps, still clean numbers.
   - Hard: multi-step/subtle misconception, but still yields an exact answer.
6) **Canonical solution**: Step-by-step, precise, concise. Must lead to the marked correct answer.
7) **Explanation**: One short paragraph on the concept and why the answer is correct.
8) **Citations**: Paraphrase only, e.g., “Inspired by [concept/pattern] from this source”. Do not quote.

# Data hygiene & conflicts
- If RAG contains any malformed lines or inconsistent math, IGNORE them and follow these rules.
- Prefer short stems and clean integers/fractions to avoid arithmetic slop.

# Self-verification (do this before output)
A) Solve your authored problem from scratch.
B) Confirm the computed answer **exactly equals** one option’s "text".
C) If mismatch, regenerate ONLY the options to include the correct answer exactly once.
D) Ensure exactly one correct option remains.

# Variety requirement
Make your question obviously different in context/values/variables from any RAG example, while preserving the learning objective/pattern.

# Dynamic Variety Instructions
{variety_instruction}

# JSON only
Return the JSON object only, no commentary or markdown.
        """)
    
    async def generate_question(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main generation method that orchestrates the simplified pipeline:
        1. RAG Retrieval → 2. LLM Generation → 3. LLM Validation → 4. Persistence
        """
        trace_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        logger.info(f"🚀 [Trace: {trace_id}] Starting simplified question generation")
        logger.info(f"📋 [Trace: {trace_id}] Spec: {spec}")
        
        try:
            # Phase 1: Normalize specification
            normalized_spec = self._normalize_spec(spec)
            
            # Phase 2: RAG Retrieval - Get relevant content
            rag_context = await self._rag_retrieval_phase(normalized_spec, trace_id)
            
            # Phase 3: LLM Question Generation
            generated_question = await self._llm_generation_phase(
                normalized_spec, rag_context, trace_id
            )
            
            # Phase 4: LLM-based Validation
            validation_result, final_question = await self._llm_validation_phase(
                generated_question, normalized_spec, trace_id
            )
            
            # Phase 5: Persistence
            persistence_result = await self._persistence_phase(
                final_question, validation_result, normalized_spec, trace_id
            )
            
            generation_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            logger.info(f"✅ [Trace: {trace_id}] Generation completed in {generation_time}ms")
            
            return {
                "status": "success",
                "question_candidate": final_question,
                "validation_results": validation_result,
                "trace_id": trace_id,
                "generation_time_ms": generation_time,
                "orchestration_path": "simplified_rag_llm",
                "metadata": {
                    "validation_passed": any(v.passed for v in validation_result.values() if hasattr(v, 'passed')),
                    "persistence_id": persistence_result.get("document_id"),
                    "rag_chunks_used": len(rag_context.get("chunks", []))
                }
            }
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] Generation failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "trace_id": trace_id,
                "generation_time_ms": int((datetime.now() - start_time).total_seconds() * 1000)
            }
    
    def _normalize_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate specification"""
        normalized_spec = {
            "subject": spec.get("subject", "").lower().strip(),
            "class_level": spec.get("class_level", ""),
            "topic": spec.get("topic", ""),
            "skills": spec.get("skills", []),
            "difficulty": spec.get("difficulty", "medium"),
            "style": spec.get("style", "standard"),
            "question_type": spec.get("question_type", "multiple_choice"),
            "context": spec.get("context", "")
        }
        
        # Validate required fields
        if not normalized_spec["subject"]:
            raise ValueError("Subject is required")
        
        return normalized_spec
    
    async def _rag_retrieval_phase(self, spec: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Phase 2: RAG Retrieval - Get relevant content chunks with randomization"""
        logger.info(f"🔍 [Trace: {trace_id}] RAG retrieval phase starting")
        
        try:
            # Build search query with randomization
            query_parts = []
            if spec.get("subject"):
                query_parts.append(spec["subject"])
            if spec.get("topic"):
                query_parts.append(spec["topic"])
            if spec.get("skills"):
                query_parts.extend(spec["skills"])
            
            # Add variety to the search query to get different content
            search_variety_terms = [
                "fundamentals", "basics", "concepts", "principles", "theory",
                "applications", "examples", "practice", "advanced", "introduction",
                "methods", "techniques", "problems", "solutions", "analysis"
            ]
            
            # Randomly add 0-1 variety terms (reduced randomization for better quality)
            if query_parts and random.random() < 0.7:  # 70% chance to add variety term
                selected_term = random.choice(search_variety_terms)
                query_parts.append(selected_term)
            
            search_query = " ".join(query_parts) if query_parts else "general knowledge"
            
            logger.info(f"🔍 [Trace: {trace_id}] Randomized search query: '{search_query}'")
            
            # Search RAG corpus with randomized selection
            if self.rag_retriever and self.rag_retriever.is_healthy():
                # Get more chunks than needed, then randomly select
                raw_chunks = await self.rag_retriever.search(
                    query=search_query,
                    subject=spec.get("subject"),
                    class_level=spec.get("class_level"),
                    limit=15  # Get more chunks for randomization
                )
                
                # Select top chunks with some variety (favor quality over randomness)
                if raw_chunks:
                    # Take top 3-4 chunks (highest quality) plus 1-2 random ones for variety
                    top_chunks = raw_chunks[:3]
                    if len(raw_chunks) > 3:
                        additional_chunks = random.sample(raw_chunks[3:], min(2, len(raw_chunks) - 3))
                        chunks = top_chunks + additional_chunks
                    else:
                        chunks = top_chunks
                    logger.info(f"✅ [Trace: {trace_id}] Retrieved {len(raw_chunks)} raw chunks, selected {len(chunks)} (top quality + some variety)")
                else:
                    chunks = raw_chunks
                    logger.info(f"✅ [Trace: {trace_id}] Retrieved {len(chunks)} RAG chunks")
            else:
                logger.warning(f"⚠️ [Trace: {trace_id}] RAG retriever not available, using empty context")
                chunks = []
            
            # Format context for LLM
            context_text = self._format_rag_context(chunks)
            
            return {
                "chunks": chunks,
                "context_text": context_text,
                "query": search_query
            }
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] RAG retrieval failed: {str(e)}")
            return {
                "chunks": [],
                "context_text": f"No specific context available for {spec.get('topic', 'this topic')} in {spec.get('subject', 'this subject')}.",
                "query": search_query if 'search_query' in locals() else ""
            }
    
    async def _llm_generation_phase(self, spec: Dict[str, Any], rag_context: Dict[str, Any], 
                                   trace_id: str) -> QuestionCandidate:
        """Phase 3: LLM Question Generation using RAG context with anti-duplication"""
        logger.info(f"🤖 [Trace: {trace_id}] LLM generation phase starting")
        
        if not LANGCHAIN_AVAILABLE:
            logger.warning(f"⚠️ [Trace: {trace_id}] LangChain not available, using fallback generation")
            return self._create_fallback_question(spec)
        
        if not self.llm:
            logger.warning(f"⚠️ [Trace: {trace_id}] No LLM available, using fallback generation")
            return self._create_fallback_question(spec)
        
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                # Add variety instruction for each attempt (escalating strength)
                variety_instruction = self._get_variety_prompt_additions(attempt)
                
                logger.info(f"🎲 [Trace: {trace_id}] Generation attempt {attempt + 1}/{max_attempts} with variety: {variety_instruction[:100]}...")
                
                # Create a unique LLM instance for each request to break caching
                unique_llm = ChatOpenAI(
                    model=self.llm.model_name,
                    temperature=0.6,  # Balanced temperature for accuracy
                    max_tokens=self.llm.max_tokens,
                    openai_api_key=self.llm.openai_api_key,
                    model_kwargs={
                        "response_format": {"type": "json_object"},
                        "user": f"gen_{trace_id}_{attempt}_{random.randint(1000, 9999)}"
                    }
                )
                
                # Add random elements to break any caching
                import time
                random_seed = random.randint(100000, 999999)
                timestamp = str(int(time.time() * 1000))
                generation_id = f"{trace_id}_{attempt}_{random.randint(1000, 9999)}"
                
                # Create the LangChain chain directly (don't pre-format)
                chain = self.generation_prompt | unique_llm
                try:
                    response = await chain.ainvoke({
                        "subject": spec.get("subject", ""),
                        "topic": spec.get("topic", ""),
                        "difficulty": spec.get("difficulty", ""),
                        "question_type": spec.get("question_type", "multiple_choice"),
                        "rag_context": rag_context.get("context_text", ""),
                        "variety_instruction": variety_instruction or "",
                        "generation_id": generation_id,
                        "timestamp": timestamp,
                        "random_seed": random_seed
                    })
                    logger.debug(f"✅ [Trace: {trace_id}] LLM chain invocation successful")
                except Exception as llm_error:
                    logger.error(f"❌ [Trace: {trace_id}] LLM chain invocation failed: {llm_error}")
                    import traceback
                    logger.error(f"📍 [Trace: {trace_id}] Chain invocation traceback:\n{traceback.format_exc()}")
                    raise llm_error
                
                # Parse the response and check for duplicates
                candidate_question = self._parse_llm_response(response.content, spec, rag_context)
                
                # Log the generated question for debugging
                logger.info(f"📝 [Trace: {trace_id}] Generated: '{candidate_question.stem[:100]}...'")
                logger.info(f"📋 [Trace: {trace_id}] Recent questions cache size: {len(self.recent_questions)}")
                logger.info(f"🎲 [Trace: {trace_id}] Used random seed: {random_seed}, timestamp: {timestamp}")
                
                # Check if this question is a duplicate
                if not self._is_duplicate(candidate_question.stem):
                    logger.info(f"✅ [Trace: {trace_id}] Unique question generated on attempt {attempt + 1}")
                    self._add_to_recent_questions(candidate_question.stem)
                    return candidate_question
                else:
                    logger.warning(f"🔄 [Trace: {trace_id}] Duplicate detected on attempt {attempt + 1}, retrying...")
                    logger.warning(f"🔄 [Trace: {trace_id}] Current question: '{candidate_question.stem[:80]}...'")
                    # Log some recent questions for comparison
                    if self.recent_questions:
                        logger.warning(f"🔄 [Trace: {trace_id}] Recent questions sample: {[q[:50] + '...' for q in self.recent_questions[-3:]]}")
                    if attempt == max_attempts - 1:
                        logger.warning(f"⚠️ [Trace: {trace_id}] Max attempts reached, using last question despite similarity")
                        self._add_to_recent_questions(candidate_question.stem)
                        return candidate_question
                    continue
            
            except Exception as e:
                import traceback
                logger.error(f"❌ [Trace: {trace_id}] LLM generation attempt {attempt + 1} failed: {e}")
                logger.error(f"📍 [Trace: {trace_id}] Full traceback:\n{traceback.format_exc()}")
                if attempt == max_attempts - 1:
                    logger.error(f"❌ [Trace: {trace_id}] All generation attempts failed")
                    return self._create_fallback_question(spec)
                continue
        
        # Fallback if we somehow exit the loop
        return self._create_fallback_question(spec)
    
    async def _llm_validation_phase(self, question: QuestionCandidate, spec: Dict[str, Any], 
                                   trace_id: str) -> Tuple[Dict[str, Any], QuestionCandidate]:
        """Phase 4: LLM-based Validation (5 attempts, 4/5 consensus)"""
        logger.info(f"✅ [Trace: {trace_id}] LLM validation phase starting")
        
        try:
            validation_result = await self.validator.validate_with_llm_consensus(question, spec)
            
            validation_passed = any(v.passed for v in validation_result.values() if hasattr(v, 'passed'))
            logger.info(f"📊 [Trace: {trace_id}] Validation completed: {validation_passed}")
            
            return validation_result, question
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] Validation failed: {str(e)}")
            # Return basic validation result on failure
            return {
                "overall_passed": False,
                "error": str(e),
                "llm_attempts": 0,
                "consensus_score": 0.0
            }, question
    
    def _parse_llm_response(self, response_content: str, spec: Dict[str, Any], 
                           rag_context: Dict[str, Any]) -> QuestionCandidate:
        """Parse LLM response into QuestionCandidate"""
        try:
            question_data = json.loads(response_content)
            
            # Handle both camelCase and snake_case keys from LLM response
            correct_option_ids = (
                question_data.get("correct_option_ids") or 
                question_data.get("correctOptionIds", [])
            )
            canonical_solution = (
                question_data.get("canonical_solution") or 
                question_data.get("canonicalSolution")
            )
            
            # Safely parse options
            try:
                options_data = question_data.get("options", [])
                parsed_options = []
                for i, opt in enumerate(options_data):
                    if isinstance(opt, dict) and "id" in opt and "text" in opt:
                        parsed_options.append({"id": opt["id"], "text": opt["text"]})
                    else:
                        logger.warning(f"⚠️ Invalid option format at index {i}: {opt}")
            except Exception as e:
                logger.error(f"❌ Error parsing options: {e}")
                parsed_options = []
            
            question_candidate = QuestionCandidate(
                stem=question_data.get("stem", ""),
                options=parsed_options,
                correct_option_ids=correct_option_ids,
                question_type=spec.get("question_type", "multiple_choice"),
                canonical_solution=canonical_solution,
                explanation=question_data.get("explanation"),
                citations=question_data.get("citations", []),
                difficulty=spec.get("difficulty", ""),
                tags=[spec.get("subject", ""), spec.get("topic", ""), spec.get("difficulty", "")],
                skill_ids=spec.get("skills", [])
            )
            
            return question_candidate
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing failed: {e}")
            logger.error(f"📄 Raw response content (first 500 chars): {response_content[:500]}")
            
            # Try to extract JSON from response if it has extra text
            cleaned_response = self._extract_json_from_response(response_content)
            if cleaned_response:
                try:
                    question_data = json.loads(cleaned_response)
                    logger.info(f"✅ Recovered JSON after cleaning")
                    # Continue with the same parsing logic...
                    correct_option_ids = (
                        question_data.get("correct_option_ids") or 
                        question_data.get("correctOptionIds", [])
                    )
                    canonical_solution = (
                        question_data.get("canonical_solution") or 
                        question_data.get("canonicalSolution")
                    )
                    
                    question_candidate = QuestionCandidate(
                        stem=question_data.get("stem", ""),
                        options=[
                            {"id": opt["id"], "text": opt["text"]}
                            for opt in question_data.get("options", [])
                        ],
                        correct_option_ids=correct_option_ids,
                        question_type=spec["question_type"],
                        canonical_solution=canonical_solution,
                        explanation=question_data.get("explanation"),
                        citations=question_data.get("citations", []),
                        difficulty=spec.get("difficulty", ""),
                        tags=[spec.get("subject", ""), spec.get("topic", ""), spec.get("difficulty", "")],
                        skill_ids=spec.get("skills", [])
                    )
                    
                    return question_candidate
                except:
                    pass
            
            return self._create_fallback_question(spec)
    
    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON object from LLM response that might have extra text"""
        # Remove common prefixes and suffixes
        response = response.strip()
        
        # Remove markdown code blocks
        if response.startswith('```'):
            lines = response.split('\n')
            # Remove first and last lines if they're code block markers
            if lines and lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            response = '\n'.join(lines)
        
        # Find the JSON object boundaries
        first_brace = response.find('{')
        last_brace = response.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
            potential_json = response[first_brace:last_brace + 1]
            
            # Basic validation - count braces
            open_braces = potential_json.count('{')
            close_braces = potential_json.count('}')
            
            if open_braces == close_braces:
                return potential_json
        
        return None
    
    async def _persistence_phase(self, question: QuestionCandidate, 
                                validation_results: Dict[str, Any],
                                spec: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Phase 5: Persistence to MongoDB and Vector Store"""
        logger.info(f"💾 [Trace: {trace_id}] Persistence phase starting")
        
        try:
            if not self.mongo_client:
                logger.warning(f"⚠️ [Trace: {trace_id}] No MongoDB client, skipping persistence")
                return {"status": "skipped", "reason": "no_mongo_client"}
            
            # Only persist if validation passed
            validation_passed = any(v.passed for v in validation_results.values() if hasattr(v, 'passed'))
            if not validation_passed:
                logger.warning(f"⚠️ [Trace: {trace_id}] Skipping persistence due to validation failure")
                return {"status": "skipped", "reason": "validation_failed"}
            
            # Prepare document for MongoDB (backend 'questions' collection schema)
            db = self.mongo_client.get_default_database()
            collection = db.questions
            
            # Map to backend schema
            content_block = {
                "stem": question.stem,
                "options": [{"id": opt.id, "text": opt.text} for opt in question.options],
                "correctOptionIds": question.correct_option_ids,
                "canonicalSolution": question.canonical_solution,
                "unit": None
            }
            explanations_block = []
            if question.explanation:
                explanations_block.append({
                    "version": 1,
                    "text": question.explanation,
                    "createdAt": datetime.utcnow()
                })
            document = {
                "version": 1,
                "status": "draft",
                "source": "simplified_agent",
                "tags": question.tags or [],
                "skillIds": question.skill_ids or [],
                "content": content_block,
                "explanations": explanations_block,
                "subject": spec.get("subject"),
                "topic": spec.get("topic")
            }
            
            # Insert into MongoDB
            result = collection.insert_one(document)
            document_id = str(result.inserted_id)
            
            # Add to vector store for future retrieval
            if self.vector_store:
                try:
                    from langchain.schema import Document
                    vector_doc = Document(
                        page_content=f"Question: {question.stem}\\nExplanation: {question.explanation or ''}",
                        metadata={
                            "source": "generated_simplified",
                            "subject": spec["subject"],
                            "difficulty": question.difficulty,
                            "type": "generated_question"
                        }
                    )
                    await self.vector_store.aadd_documents([vector_doc])
                    logger.info(f"📚 [Trace: {trace_id}] Added to vector store")
                except Exception as e:
                    logger.warning(f"⚠️ [Trace: {trace_id}] Vector store addition failed: {e}")
            
            logger.info(f"✅ [Trace: {trace_id}] Persisted with ID: {document_id}")
            return {"status": "success", "document_id": document_id}
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] Persistence failed: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def _sanitize_rag_content(self, content: str) -> str:
        """Sanitize RAG content to remove problematic elements"""
        if not content:
            return ""
        
        # Remove display math environments that violate inline-only rule
        import re
        
        # Remove \begin{align}...\end{align} blocks
        content = re.sub(r'\\begin\{align\*?\}.*?\\end\{align\*?\}', '[DISPLAY_MATH_REMOVED]', content, flags=re.DOTALL)
        
        # Remove \[...\] display math
        content = re.sub(r'\\\[.*?\\\]', '[DISPLAY_MATH_REMOVED]', content, flags=re.DOTALL)
        
        # Remove $$...$$ display math  
        content = re.sub(r'\$\$.*?\$\$', '[DISPLAY_MATH_REMOVED]', content, flags=re.DOTALL)
        
        # Remove obvious truncation artifacts
        truncation_patterns = [
            r'Answer:\s*[^}]*\{[^}]*$',  # Truncated "Answer: 120a^{10" 
            r'Solution[:\s]*.*\.\.\.\s*$',  # Truncated "Solution: ... -..."
            r'We als\.\.\.\s*$',  # Truncated "We als..."
            r'\.\.\.\s*-\s*\.\.\.\s*$',  # "... -..."
            r'\.\.\.\s*$'  # Trailing "..."
        ]
        
        for pattern in truncation_patterns:
            content = re.sub(pattern, '[TRUNCATED_CONTENT_REMOVED]', content, flags=re.MULTILINE)
        
        # Remove malformed LaTeX (unclosed braces, etc.)
        # Count braces and remove lines with mismatched braces
        lines = content.split('\n')
        clean_lines = []
        for line in lines:
            # Count braces in math expressions
            math_parts = re.findall(r'\$[^$]*\$', line)
            is_malformed = False
            for math in math_parts:
                if math.count('{') != math.count('}'):
                    is_malformed = True
                    break
            
            if not is_malformed:
                clean_lines.append(line)
            else:
                clean_lines.append('[MALFORMED_MATH_REMOVED]')
        
        content = '\n'.join(clean_lines)
        
        # Remove empty placeholder lines
        content = re.sub(r'\n\s*\[.*?_REMOVED\]\s*\n', '\n', content)
        content = re.sub(r'^\s*\[.*?_REMOVED\]\s*\n', '', content)
        content = re.sub(r'\n\s*\[.*?_REMOVED\]\s*$', '', content)
        
        # Clean up excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        content = content.strip()
        
        return content

    def _format_rag_context(self, chunks: List[Dict]) -> str:
        """Format RAG chunks for LLM prompt with sanitization"""
        if not chunks:
            return "No specific context available."
        
        formatted = []
        for i, chunk in enumerate(chunks[:3], 1):  # Use top 3 chunks
            content = chunk.get('text', '') if isinstance(chunk, dict) else str(chunk)
            
            # Sanitize content first
            original_content = content
            content = self._sanitize_rag_content(content)
            
            # Log if significant changes were made
            if len(original_content) - len(content) > 50:
                logger.info(f"🧹 [Trace: {i}] RAG content sanitized: removed {len(original_content) - len(content)} characters")
            
            # Skip empty/useless content after sanitization
            if not content or len(content.strip()) < 20:
                logger.warning(f"⚠️ [Trace: {i}] RAG chunk {i} discarded after sanitization (too short/empty)")
                continue
                
            # Truncate very long content
            content = content[:400] + "..." if len(content) > 400 else content
            formatted.append(f"Context {i}: {content}")
        
        if not formatted:
            return "No usable context available after sanitization."
            
        return "\\n\\n".join(formatted)
    
    def _create_fallback_question(self, spec: Dict[str, Any]) -> QuestionCandidate:
        """Create a basic fallback question"""
        topic = spec.get("topic", "the subject")
        subject = spec.get("subject", "this area")
        
        return QuestionCandidate(
            stem=f"Which of the following best describes {topic} in {subject}?",
            options=[
                {"id": "a", "text": f"Basic concept in {subject}"},
                {"id": "b", "text": f"Advanced concept in {subject}"},
                {"id": "c", "text": f"Related concept"},
                {"id": "d", "text": f"Unrelated concept"}
            ],
            correct_option_ids=["a"],
            question_type=spec.get("question_type", "multiple_choice"),
            canonical_solution=f"The correct answer relates to fundamental {subject} principles.",
            explanation=f"This question assesses understanding of {topic}.",
            difficulty=spec.get("difficulty", "medium"),
            tags=[subject, topic, spec.get("difficulty", "medium")],
            skill_ids=spec.get("skills", [])
        )
