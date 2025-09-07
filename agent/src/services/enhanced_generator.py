"""
Enhanced Question Generator with Exemplar-Driven Approach

This service orchestrates the v2 question generation pipeline:
1. Planner → Hybrid Retriever → Template Inducer → Distractor Factory → Generator → Validator Suite → Persister

Uses exemplars, templates, and advanced validation with auto-fix capabilities.
"""

import logging
import asyncio
import uuid
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ..models.schemas import QuestionCandidate, ValidationResult
from ..utils.config import get_settings
from ..utils.prompt_manager import prompt_manager
from .hybrid_retriever import HybridRetriever
from .template_inducer import TemplateInducer
from .distractor_factory import DistractorFactory
from .validators import EnhancedQuestionValidator

logger = logging.getLogger(__name__)

class EnhancedQuestionGenerator:
    """
    Orchestrates the v2 exemplar-driven question generation pipeline
    with advanced validation and auto-fix capabilities.
    """
    
    def __init__(self, rag_retriever, hendrycks_manager, mongo_client, vector_store):
        self.settings = get_settings()
        self.rag_retriever = rag_retriever
        self.hendrycks_manager = hendrycks_manager
        self.mongo_client = mongo_client
        self.vector_store = vector_store
        
        # Initialize pipeline components
        self.hybrid_retriever = HybridRetriever(rag_retriever, hendrycks_manager, self.settings)
        self.template_inducer = TemplateInducer(self.settings)
        self.distractor_factory = DistractorFactory(self.settings)
        self.validator = EnhancedQuestionValidator(self.settings, mongo_client)
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.generation_temperature,
            max_tokens=self.settings.max_tokens,
            openai_api_key=self.settings.openai_api_key,
            model_kwargs={"response_format": {"type": "json_object"}}
        ) if self.settings.openai_api_key else None
        
        # Setup enhanced prompts
        self._setup_enhanced_prompts()
    
    def _setup_enhanced_prompts(self):
        """Setup enhanced prompts for exemplar-driven generation"""
        self.exemplar_prompt = ChatPromptTemplate.from_template("""
You are an expert question generator creating high-quality educational questions.

**Generation Context:**
- Subject: {subject}
- Topic: {topic}  
- Difficulty: {difficulty}
- Question Type: {question_type}
- Generation Path: {generation_path}

**Exemplars for Reference:**
{exemplars}

**Concept Context:**
{concepts}

**Template (if applicable):**
{template}

**Distractors (if provided):**
{distractors}

**Instructions:**
1. Create a question that demonstrates understanding of {topic} in {subject}
2. Use the exemplars as quality references but create original content
3. If template is provided, use it as a structural guide
4. Ensure mathematical accuracy and educational value
5. Include detailed solution explanation

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
        
        self.direct_prompt = ChatPromptTemplate.from_template("""
You are an expert question generator creating educational questions.

**Generation Context:**
- Subject: {subject}
- Topic: {topic}
- Difficulty: {difficulty}
- Question Type: {question_type}

**Context Material:**
{context}

**Instructions:**
Create a high-quality {question_type} question about {topic} in {subject}.
- Difficulty level: {difficulty}
- Include clear, educational content
- Provide detailed explanation
- Ensure accuracy and clarity

Only output valid JSON. No prose. Keep concise.

**Required JSON Output Format:**
{{
  "stem": "Main question text",
  "options": [
    {{"id": "a", "text": "Option A"}},
    {{"id": "b", "text": "Option B"}},
    {{"id": "c", "text": "Option C"}},
    {{"id": "d", "text": "Option D"}}
  ],
  "correct_option_ids": ["a"],
  "canonical_solution": "Step-by-step solution",
  "explanation": "Educational explanation"
}}

Generate the question. Respond with JSON only:
        """)
    
    async def generate_question(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main generation method that orchestrates the v2 pipeline
        """
        trace_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        logger.info(f"🚀 [Trace: {trace_id}] Starting enhanced question generation")
        logger.info(f"📋 [Trace: {trace_id}] Spec: {spec}")
        
        try:
            # Phase 1: Planning - Normalize and validate spec
            normalized_spec = await self._planner_phase(spec, trace_id)
            
            # Phase 2: Hybrid Retrieval - Get exemplars, concepts, templates
            retrieval_result = await self._retrieval_phase(normalized_spec, trace_id)
            
            # Phase 3: Template Induction (if template path)
            template_result = await self._template_phase(
                normalized_spec, retrieval_result, trace_id
            )
            
            # Phase 4: Distractor Generation (if template available)
            distractor_result = await self._distractor_phase(
                normalized_spec, template_result, trace_id
            )
            
            # Phase 5: Question Generation
            generation_result = await self._generation_phase(
                normalized_spec, retrieval_result, template_result, distractor_result, trace_id
            )
            
            # Phase 6: Validation with Auto-fix
            # Skip persistence if we had to use fallback generation
            generated_question = generation_result["question"]
            is_fallback = generation_result.get("generation_method") == "fallback"
            validation_result, final_question = await self._validation_phase(
                generated_question, normalized_spec, trace_id
            )
            
            # Phase 7: Persistence
            if is_fallback:
                logger.warning(f"⚠️ [Trace: {trace_id}] Skipping persistence for fallback question")
                persistence_result = {"status": "skipped", "reason": "fallback_generation"}
            else:
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
                "orchestration_path": retrieval_result.get("generation_path", "direct"),
                "retrieval_confidence": retrieval_result.get("confidence_score", 0.0),
                "metadata": {
                    "template_used": template_result is not None,
                    "distractors_generated": distractor_result is not None,
                    "validation_passed": all(v.passed for v in validation_result.values()),
                    "persistence_id": persistence_result.get("document_id")
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
    
    async def _planner_phase(self, spec: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Phase 1: Planning - Normalize and validate specification"""
        logger.info(f"📋 [Trace: {trace_id}] Planner phase starting")
        
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
        
        logger.info(f"✅ [Trace: {trace_id}] Planner phase completed")
        return normalized_spec
    
    async def _retrieval_phase(self, spec: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Phase 2: Hybrid Retrieval - Get exemplars, concepts, and templates"""
        logger.info(f"🔍 [Trace: {trace_id}] Retrieval phase starting")
        
        retrieval_result = await self.hybrid_retriever.retrieve(spec, trace_id)
        
        logger.info(f"✅ [Trace: {trace_id}] Retrieval phase completed")
        logger.info(f"🎯 [Trace: {trace_id}] Path: {retrieval_result.get('generation_path')}, Confidence: {retrieval_result.get('confidence_score', 0):.3f}")
        
        return retrieval_result
    
    async def _template_phase(self, spec: Dict[str, Any], retrieval_result: Dict[str, Any], 
                             trace_id: str) -> Optional[Dict[str, Any]]:
        """Phase 3: Template Induction (if template path selected)"""
        generation_path = retrieval_result.get("generation_path", "direct")
        
        if generation_path != "template":
            logger.info(f"📝 [Trace: {trace_id}] Template phase skipped (direct path)")
            return None
        
        logger.info(f"🎯 [Trace: {trace_id}] Template phase starting")
        
        try:
            template_result = await self.template_inducer.induce_template(
                topic=spec["topic"],
                difficulty=spec["difficulty"],
                subject_hint=spec["subject"]
            )
            
            if template_result:
                logger.info(f"✅ [Trace: {trace_id}] Template induced: {template_result['template_name']}")
            else:
                logger.warning(f"⚠️ [Trace: {trace_id}] Template induction failed, falling back to direct")
            
            return template_result
            
        except Exception as e:
            logger.warning(f"⚠️ [Trace: {trace_id}] Template phase failed: {e}")
            return None
    
    async def _distractor_phase(self, spec: Dict[str, Any], template_result: Optional[Dict[str, Any]], 
                               trace_id: str) -> Optional[Dict[str, Any]]:
        """Phase 4: Distractor Generation (if template available)"""
        if not template_result:
            logger.info(f"🎲 [Trace: {trace_id}] Distractor phase skipped (no template)")
            return None
        
        logger.info(f"🎲 [Trace: {trace_id}] Distractor phase starting")
        
        try:
            # Extract correct answer from template solution
            correct_answer = template_result.get("canonical_solution", {}).get("answer")
            
            if correct_answer is not None:
                question_context = {
                    "subject": spec["subject"],
                    "topic": spec["topic"],
                    "difficulty": spec["difficulty"],
                    "template": template_result
                }
                
                distractors = await self.distractor_factory.generate_distractors(
                    correct_answer=correct_answer,
                    question_context=question_context,
                    count=self.settings.distractor_count
                )
                
                logger.info(f"✅ [Trace: {trace_id}] Generated {len(distractors)} distractors")
                return {"distractors": distractors}
            else:
                logger.warning(f"⚠️ [Trace: {trace_id}] No correct answer in template for distractor generation")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️ [Trace: {trace_id}] Distractor generation failed: {e}")
            return None
    
    async def _generation_phase(self, spec: Dict[str, Any], retrieval_result: Dict[str, Any],
                               template_result: Optional[Dict[str, Any]], 
                               distractor_result: Optional[Dict[str, Any]], 
                               trace_id: str) -> Dict[str, Any]:
        """Phase 5: Question Generation using LLM with exemplars/templates"""
        logger.info(f"🤖 [Trace: {trace_id}] Generation phase starting")
        
        if not self.llm:
            return self._generate_fallback_question(spec, trace_id)
        
        try:
            generation_path = retrieval_result.get("generation_path", "direct")
            
            if generation_path == "template" and template_result:
                question = await self._generate_with_template(
                    spec, retrieval_result, template_result, distractor_result, trace_id
                )
            else:
                question = await self._generate_direct(
                    spec, retrieval_result, trace_id
                )
            
            logger.info(f"✅ [Trace: {trace_id}] Generation phase completed")
            return {"question": question, "generation_method": generation_path}
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] Generation failed: {e}")
            return self._generate_fallback_question(spec, trace_id)
    
    async def _generate_with_template(self, spec: Dict[str, Any], retrieval_result: Dict[str, Any],
                                    template_result: Dict[str, Any], 
                                    distractor_result: Optional[Dict[str, Any]],
                                    trace_id: str) -> QuestionCandidate:
        """Generate question using template and exemplars"""
        logger.info(f"📝 [Trace: {trace_id}] Generating with template: {template_result['template_name']}")
        
        # Prepare prompt inputs
        exemplars_text = self._format_exemplars(retrieval_result.get("exemplars", []))
        concepts_text = self._format_concepts(retrieval_result.get("concepts", []))
        template_text = self._format_template(template_result)
        distractors_text = self._format_distractors(distractor_result) if distractor_result else ""
        
        response = await self.exemplar_prompt.ainvoke({
            "subject": spec["subject"],
            "topic": spec["topic"],
            "difficulty": spec["difficulty"],
            "question_type": spec["question_type"],
            "generation_path": "template",
            "exemplars": exemplars_text,
            "concepts": concepts_text,
            "template": template_text,
            "distractors": distractors_text
        }) | self.llm
        print(f"Response: {response.content}")
        return self._parse_llm_response(response.content, spec, retrieval_result)
    
    async def _generate_direct(self, spec: Dict[str, Any], retrieval_result: Dict[str, Any],
                              trace_id: str) -> QuestionCandidate:
        """Generate question using direct approach with exemplars"""
        logger.info(f"🎯 [Trace: {trace_id}] Generating with direct approach")
        
        # Prepare context from retrieval results
        context_parts = []
        
        # Add exemplars as context
        exemplars = retrieval_result.get("exemplars", [])
        if exemplars:
            exemplar_text = self._format_exemplars(exemplars)
            context_parts.append(f"Reference Examples:\\n{exemplar_text}")
        
        # Add concepts
        concepts = retrieval_result.get("concepts", [])
        if concepts:
            concept_text = self._format_concepts(concepts)
            context_parts.append(f"Relevant Content:\\n{concept_text}")
        
        context = "\\n\\n".join(context_parts) if context_parts else f"General knowledge about {spec['topic']} in {spec['subject']}"
        
        chain = self.direct_prompt | self.llm
        response = await chain.ainvoke({
            "subject": spec["subject"],
            "topic": spec["topic"],
            "difficulty": spec["difficulty"],
            "question_type": spec["question_type"],
            "context": context
        })
        print(f"Response: {response.content}")
        return self._parse_llm_response(response.content, spec, retrieval_result)
    
    def _parse_llm_response(self, response_content: str, spec: Dict[str, Any], 
                           retrieval_result: Dict[str, Any]) -> QuestionCandidate:
        """Parse LLM response into QuestionCandidate"""
        try:
            question_data = json.loads(response_content)
            
            # Log raw response for debugging
            logger.info(f"Raw LLM response keys: {list(question_data.keys())}")
            logger.info(f"Raw correct_option_ids: {question_data.get('correct_option_ids')}")
            logger.info(f"Raw correctOptionIds: {question_data.get('correctOptionIds')}")
            logger.info(f"Raw canonical_solution: {question_data.get('canonical_solution')}")
            logger.info(f"Raw canonicalSolution: {question_data.get('canonicalSolution')}")
            
            # Handle both camelCase and snake_case keys from LLM response
            correct_option_ids = (
                question_data.get("correct_option_ids") or 
                question_data.get("correctOptionIds", [])
            )
            canonical_solution = (
                question_data.get("canonical_solution") or 
                question_data.get("canonicalSolution")
            )
            
            logger.info(f"Final parsed correct_option_ids: {correct_option_ids}")
            logger.info(f"Final parsed canonical_solution: {canonical_solution}")
            
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
            
            # Log the created QuestionCandidate for verification
            logger.info(f"Created QuestionCandidate.correct_option_ids: {question_candidate.correct_option_ids}")
            logger.info(f"Created QuestionCandidate.canonical_solution: {question_candidate.canonical_solution}")
            
            return question_candidate
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Raw response content: {response_content}")
            return self._create_fallback_question(spec)
    
    async def _validation_phase(self, question: QuestionCandidate, spec: Dict[str, Any], 
                               trace_id: str) -> Tuple[Dict[str, ValidationResult], QuestionCandidate]:
        """Phase 6: Validation with Auto-fix"""
        logger.info(f"✅ [Trace: {trace_id}] Validation phase starting")
        
        validation_results, fixed_question = await self.validator.validate_with_autofix(question, spec)
        
        passed_count = sum(1 for result in validation_results.values() if result.passed)
        total_count = len(validation_results)
        
        logger.info(f"📊 [Trace: {trace_id}] Validation: {passed_count}/{total_count} passed")
        
        return validation_results, fixed_question
    
    async def _persistence_phase(self, question: QuestionCandidate, 
                                validation_results: Dict[str, ValidationResult],
                                spec: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Phase 7: Persistence to MongoDB and Vector Store"""
        logger.info(f"💾 [Trace: {trace_id}] Persistence phase starting")
        
        try:
            if not self.mongo_client:
                logger.warning(f"⚠️ [Trace: {trace_id}] No MongoDB client, skipping persistence")
                return {"status": "skipped", "reason": "no_mongo_client"}
            
            # Gate persistence: require all validators to pass and math consistency
            all_passed = all(result.passed for result in validation_results.values())
            math_result = validation_results.get("math")
            math_issues = (math_result.details.get("issues", []) if math_result else [])
            # Look for explicit inconsistency flags from math validator
            inconsistency_markers = [
                "Canonical solution value does not match the marked correct option",
                "Solved answer from stem does not match the marked correct option"
            ]
            has_math_inconsistency = any(marker in math_issues for marker in inconsistency_markers)
            if not all_passed or has_math_inconsistency:
                reason = "validators_not_passed" if not all_passed else "math_inconsistency"
                logger.warning(f"⚠️ [Trace: {trace_id}] Skipping persistence due to validation gating: {reason}")
                return {"status": "skipped", "reason": reason}
            
            # Prepare document for MongoDB (backend 'questions' collection schema)
            db = self.mongo_client.get_default_database()
            collection = db.questions
            
            # Convert validation results to serializable format
            validation_dict = {}
            for name, result in validation_results.items():
                validation_dict[name] = {
                    "validator_name": result.validator_name,
                    "passed": result.passed,
                    "score": result.score,
                    "details": result.details,
                    "error_message": result.error_message
                }
            
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
                "source": "enhanced_agent_v2",
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
                            "source": "generated_v2",
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
    
    # Helper methods for formatting
    def _format_exemplars(self, exemplars: List[Dict]) -> str:
        """Format exemplars for prompt"""
        if not exemplars:
            return "No exemplars available."
        
        formatted = []
        for i, exemplar in enumerate(exemplars[:3], 1):
            formatted.append(f"Exemplar {i}:")
            formatted.append(f"Problem: {exemplar.get('problem', 'N/A')}")
            formatted.append(f"Solution: {exemplar.get('solution', 'N/A')[:200]}...")
            formatted.append("")
        
        return "\\n".join(formatted)
    
    def _format_concepts(self, concepts: List[Dict]) -> str:
        """Format concept chunks for prompt"""
        if not concepts:
            return "No concept context available."
        
        formatted = []
        for i, concept in enumerate(concepts[:3], 1):
            content = concept.get('text', '') if isinstance(concept, dict) else str(concept)
            formatted.append(f"Concept {i}: {content[:300]}...")
        
        return "\\n".join(formatted)
    
    def _format_template(self, template_result: Dict[str, Any]) -> str:
        """Format template for prompt"""
        return f"""
Template: {template_result.get('template_name', 'Unknown')}
Problem Pattern: {template_result.get('instantiated_problem', '')}
LaTeX Pattern: {template_result.get('instantiated_latex', '')}
Solution: {template_result.get('canonical_solution', {})}
        """.strip()
    
    def _format_distractors(self, distractor_result: Dict[str, Any]) -> str:
        """Format distractors for prompt"""
        distractors = distractor_result.get("distractors", [])
        if not distractors:
            return "No distractors provided."
        
        formatted = []
        for i, distractor in enumerate(distractors, 1):
            formatted.append(f"Distractor {i}: {distractor['value']} ({distractor.get('generation_method', 'unknown')})")
        
        return "\\n".join(formatted)
    
    def _generate_fallback_question(self, spec: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Generate fallback question when LLM fails"""
        logger.warning(f"⚠️ [Trace: {trace_id}] Using fallback question generation")
        
        fallback_question = self._create_fallback_question(spec)
        return {"question": fallback_question, "generation_method": "fallback"}
    
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
