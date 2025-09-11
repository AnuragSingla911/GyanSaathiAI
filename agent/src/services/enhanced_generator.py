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
                temperature=0.95,  # Maximum temperature for variety
                max_tokens=getattr(self.settings, 'max_tokens', 1000),
                openai_api_key=self.settings.openai_api_key,
                model_kwargs={
                    "response_format": {"type": "json_object"},
                    "seed": None,  # Disable seed to prevent caching
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
        self.generation_prompt = ChatPromptTemplate.from_template("""
You are an expert educational item writer. Generate ONE completely NEW and ORIGINAL multiple-choice question using the RAG context as REFERENCE and INSPIRATION only.

# Inputs
- Subject: {subject}
- Topic: {topic}
- Difficulty: {difficulty}
- Question Type: {question_type}
- Reference Context (for patterns, structure, and syllabus guidance):
{rag_context}

# CRITICAL: Content Creation Approach
- USE the RAG context to understand: question patterns, difficulty levels, topic scope, mathematical notation styles, and educational approaches
- DO NOT copy numbers, specific examples, or exact scenarios from the RAG context
- CREATE entirely new scenarios, problems, and examples that fit the same educational pattern
- INVENT new numerical values, names, situations, and contexts while maintaining the learning objective
- FOLLOW the educational structure and complexity level demonstrated in the reference material

# Hard Rules (must follow)
1) Output **valid JSON only** (no markdown, no explanations outside JSON, no trailing commas).
2) JSON must match this exact structure and keys:
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
       {{"chunk_id":"source_1","text":"..."}}
     ]
   }}
3) Options: exactly four (a,b,c,d). Mutually exclusive. Similar length and granularity. No "All/None of the above".
4) Exactly ONE correct option in "correct_option_ids".
5) Keep language clear and concise. Prefer Grade-appropriate phrasing. Max ~280 chars for "stem" when reasonable.
6) Math: use inline LaTeX for symbols, e.g., $\\frac{{3}}{{5}}$, $x^2$, $\\%$. Avoid display math.
7) "canonical_solution": step-by-step reasoning to reach the correct answer; precise, mathematically accurate.
8) "explanation": short, learner-friendly concept explanation (what idea this problem tests and why the correct option is right).
9) "citations": reference the RAG context that inspired your approach. Format: [{{"chunk_id":"source_X","text":"Inspired by [concept/pattern] from this source"}}]. Do NOT quote verbatim.
10) CREATE entirely original content - if RAG shows "solve 2x + 3 = 7", create something like "solve 4y - 5 = 11" or use completely different contexts.

# Quality Guidance for Original Content Creation
- Align difficulty with the requested level by adjusting numbers and required steps (easy: direct recall/application; medium: 1–2 steps; hard: multi-step or subtle misconception).
- Craft plausible distractors that reflect common misconceptions implied by the context, not random errors.
- For numerical items, pick clean numbers consistent with the context; avoid awkward decimals unless the context uses them.
- Prefer "why/what" stems over "which of the following is true" unless the context necessitates it.

# Originality Requirements
- INVENT new scenarios: If RAG shows "a store sells apples", create "a factory produces widgets" or "a school organizes events"
- CHANGE numerical values: If RAG uses numbers like 5, 10, 15, use different values like 8, 12, 18
- VARY contexts: If RAG focuses on geometry, use different shapes/measurements; if algebra, use different variables/equations
- CREATE new names: Instead of copying "John" from RAG, use "Maria", "Ahmed", or "Chen"
- ADAPT patterns: Learn the question structure from RAG, but apply it to completely new subject matter

# Variety Requirement
{variety_instruction}

# Randomization Context
Generation ID: {generation_id}
Timestamp: {timestamp}
Randomization Seed: {random_seed}

# JSON Output Only (repeat: JSON only)
Generate the question now and return ONLY the JSON object with these exact keys and constraints.
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
            
            # Randomly add 1-2 variety terms to diversify search results
            if query_parts:
                num_variety_terms = random.randint(1, 2)
                selected_terms = random.sample(search_variety_terms, num_variety_terms)
                query_parts.extend(selected_terms)
            
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
                
                # Randomly select 3-5 chunks from the results to add variety
                if raw_chunks:
                    num_chunks = random.randint(3, min(5, len(raw_chunks)))
                    chunks = random.sample(raw_chunks, num_chunks)
                    logger.info(f"✅ [Trace: {trace_id}] Retrieved {len(raw_chunks)} raw chunks, randomly selected {len(chunks)}")
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
                    temperature=0.95,
                    max_tokens=self.llm.max_tokens,
                    openai_api_key=self.llm.openai_api_key,
                    model_kwargs={
                        "response_format": {"type": "json_object"},
                        "seed": None,
                        "user": f"gen_{trace_id}_{attempt}_{random.randint(1000, 9999)}"
                    }
                )
                
                # Add random elements to break any caching
                import time
                random_seed = random.randint(100000, 999999)
                timestamp = str(int(time.time() * 1000))
                generation_id = f"{trace_id}_{attempt}_{random.randint(1000, 9999)}"
                
                chain = self.generation_prompt | unique_llm
                response = await chain.ainvoke({
                    "subject": spec["subject"],
                    "topic": spec["topic"],
                    "difficulty": spec["difficulty"],
                    "question_type": spec["question_type"],
                    "rag_context": rag_context["context_text"],
                    "variety_instruction": variety_instruction,
                    "generation_id": generation_id,
                    "timestamp": timestamp,
                    "random_seed": random_seed
                })
                
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
                logger.error(f"❌ [Trace: {trace_id}] LLM generation attempt {attempt + 1} failed: {e}")
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
                difficulty=spec["difficulty"],
                tags=[spec["subject"], spec.get("topic", ""), spec["difficulty"]],
                skill_ids=spec["skills"]
            )
            
            return question_candidate
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Raw response content: {response_content}")
            return self._create_fallback_question(spec)
    
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
    
    def _format_rag_context(self, chunks: List[Dict]) -> str:
        """Format RAG chunks for LLM prompt"""
        if not chunks:
            return "No specific context available."
        
        formatted = []
        for i, chunk in enumerate(chunks[:3], 1):  # Use top 3 chunks
            content = chunk.get('text', '') if isinstance(chunk, dict) else str(chunk)
            # Truncate very long content
            content = content[:400] + "..." if len(content) > 400 else content
            formatted.append(f"Context {i}: {content}")
        
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
