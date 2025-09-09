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
from typing import Dict, List, Any, Optional, Tuple
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
                temperature=getattr(self.settings, 'generation_temperature', 0.7),
                max_tokens=getattr(self.settings, 'max_tokens', 1000),
                openai_api_key=self.settings.openai_api_key,
                model_kwargs={"response_format": {"type": "json_object"}}
            )
        else:
            self.llm = None
        
        # Setup simplified prompts only if LangChain is available
        if LANGCHAIN_AVAILABLE:
            self._setup_simplified_prompts()
        else:
            self.generation_prompt = None
    
    def _setup_simplified_prompts(self):
        """Setup simplified prompts for RAG-based generation"""
        self.generation_prompt = ChatPromptTemplate.from_template("""
You are an expert question generator creating high-quality educational questions.

**Generation Context:**
- Subject: {subject}
- Topic: {topic}  
- Difficulty: {difficulty}
- Question Type: {question_type}

**Relevant Context from RAG:**
{rag_context}

**Instructions:**
1. Create a question that demonstrates understanding of {topic} in {subject}
2. Use the provided context as reference material
3. Ensure mathematical accuracy and educational value
4. Include detailed solution explanation
5. Create exactly 4 multiple choice options with one correct answer

Only output valid JSON. No prose.
Keep the answer concise.
Limit options to exactly four.

**Required JSON Output Format:**
{{
  "stem": "Main question text (use LaTeX for math: $...$)",
  "options": [
    {{"id": "a", "text": "Option A text"}},
    {{"id": "b", "text": "Option B text"}},
    {{"id": "c", "text": "Option C text"}},
    {{"id": "d", "text": "Option D text"}}
  ],
  "correct_option_ids": ["a"],
  "canonical_solution": "Step-by-step solution",
  "explanation": "Educational explanation of the concept",
  "citations": [
    {{"chunk_id": "source_1", "text": "Supporting content excerpt"}}
  ]
}}

Generate the question now. Respond with JSON only:
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
        """Phase 2: RAG Retrieval - Get relevant content chunks"""
        logger.info(f"🔍 [Trace: {trace_id}] RAG retrieval phase starting")
        
        try:
            # Build search query
            query_parts = []
            if spec.get("subject"):
                query_parts.append(spec["subject"])
            if spec.get("topic"):
                query_parts.append(spec["topic"])
            if spec.get("skills"):
                query_parts.extend(spec["skills"])
            
            search_query = " ".join(query_parts) if query_parts else "general knowledge"
            
            logger.info(f"🔍 [Trace: {trace_id}] Search query: '{search_query}'")
            
            # Search RAG corpus
            if self.rag_retriever and self.rag_retriever.is_healthy():
                chunks = await self.rag_retriever.search(
                    query=search_query,
                    subject=spec.get("subject"),
                    class_level=spec.get("class_level"),
                    limit=5  # Get top 5 chunks
                )
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
        """Phase 3: LLM Question Generation using RAG context"""
        logger.info(f"🤖 [Trace: {trace_id}] LLM generation phase starting")
        
        if not LANGCHAIN_AVAILABLE:
            logger.warning(f"⚠️ [Trace: {trace_id}] LangChain not available, using fallback generation")
            return self._create_fallback_question(spec)
        
        if not self.llm:
            logger.warning(f"⚠️ [Trace: {trace_id}] No LLM available, using fallback generation")
            return self._create_fallback_question(spec)
        
        try:
            chain = self.generation_prompt | self.llm
            response = await chain.ainvoke({
                "subject": spec["subject"],
                "topic": spec["topic"],
                "difficulty": spec["difficulty"],
                "question_type": spec["question_type"],
                "rag_context": rag_context["context_text"]
            })
            
            logger.info(f"✅ [Trace: {trace_id}] LLM generation completed")
            return self._parse_llm_response(response.content, spec, rag_context)
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] LLM generation failed: {e}")
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
