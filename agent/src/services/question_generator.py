import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

# Setup logging
logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ..models.schemas import QuestionCandidate, ValidationResult
from ..utils.config import get_settings
from ..utils.prompt_manager import prompt_manager

# Graph state
class QuestionGenerationState:
    def __init__(self):
        self.spec: Dict[str, Any] = {}
        self.retrieved_chunks: List[Dict] = []
        self.question_candidate: Optional[QuestionCandidate] = None
        self.validation_results: Dict[str, ValidationResult] = {}
        self.status: str = "initialized"
        self.error: Optional[str] = None
        self.trace_id: str = str(uuid.uuid4())
        self.generation_time_ms: int = 0
        self.model_version: str = ""
        self.prompt_version: str = ""

def create_question_generation_graph(rag_retriever, question_validator):
    """Create the LangGraph question generation pipeline"""
    
    settings = get_settings()
    
    # Initialize LLM with JSON response format
    llm = ChatOpenAI(
        model="gpt-4-turbo-preview",
        temperature=0.7,
        openai_api_key=settings.openai_api_key,
        model_kwargs={
            "response_format": {"type": "json_object"}
        }
    ) if settings.openai_api_key else None
    
    # Define graph
    workflow = StateGraph(dict)
    
    # Planner node
    async def planner_node(state: dict) -> dict:
        """Normalize and validate the generation specification"""
        logger.info("🔄 Planner node executing...")
        try:
            spec = state.get("spec", {})
            
            # Normalize spec
            normalized_spec = {
                "subject": spec.get("subject", "").lower().strip(),
                "class": spec.get("class", ""),
                "topic": spec.get("topic", ""),
                "skills": spec.get("skills", []),
                "difficulty": spec.get("difficulty", "medium"),
                "style": spec.get("style", "standard"),
                "question_type": spec.get("question_type", "multiple_choice")
            }
            
            # Validate required fields
            if not normalized_spec["subject"]:
                return {
                    **state,
                    "status": "error",
                    "error": "Subject is required"
                }
            
            logger.info(f"✅ Planner node completed - Status: planned, Spec: {normalized_spec}")
            return {
                **state,
                "spec": normalized_spec,
                "status": "planned"
            }
        except Exception as e:
            return {
                **state,
                "status": "error",
                "error": f"Planning error: {str(e)}"
            }
    
    # Retriever node
    async def retriever_node(state: dict) -> dict:
        """Query RAG corpus for relevant content"""
        logger.info("🔄 Retriever node executing...")
        try:
            if state.get("status") != "planned":
                logger.info(f"❌ Retriever node skipped - Status: {state.get('status')}")
                return state
            
            spec = state["spec"]
            
            # Build search query - use more flexible approach
            # For math, search by subject and topic separately to get broader results
            if spec["subject"] == "math" and spec.get("topic"):
                # For math, search by topic first, then fall back to subject
                search_query = spec["topic"]
                fallback_query = spec["subject"]
            else:
                # For other subjects, use the original approach
                query_parts = [spec["subject"]]
                if spec["topic"]:
                    query_parts.append(spec["topic"])
                if spec["skills"]:
                    query_parts.extend(spec["skills"])
                search_query = " ".join(query_parts)
                fallback_query = None
            
            # Debug: Log search parameters
            logger.info(f"🔍 Retriever - Search Query: '{search_query}'")
            logger.info(f"🔍 Retriever - Subject: '{spec['subject']}'")
            logger.info(f"🔍 Retriever - Class Level: '{spec.get('class')}'")
            logger.info(f"🔍 Retriever - RAG Retriever Available: {rag_retriever is not None}")
            
            # Search corpus with fallback strategy
            chunks = []
            if rag_retriever:
                # Try primary search
                chunks = await rag_retriever.search(
                    query=search_query,
                    subject=spec["subject"],
                    class_level=spec.get("class"),
                    limit=5
                )
                
                # If no results and we have a fallback query, try that
                if not chunks and fallback_query:
                    logger.info(f"🔍 Retriever - Primary search returned 0 chunks, trying fallback: '{fallback_query}'")
                    chunks = await rag_retriever.search(
                        query=fallback_query,
                        subject=spec["subject"],
                        class_level=spec.get("class"),
                        limit=5
                    )
                
                # If still no results, try broader search without subject constraint
                if not chunks:
                    logger.info(f"🔍 Retriever - Fallback search returned 0 chunks, trying broader search")
                    chunks = await rag_retriever.search(
                        query=search_query,
                        subject=None,  # Remove subject constraint
                        class_level=spec.get("class"),
                        limit=5
                    )
            else:
                # Fallback: mock chunks for demo
                chunks = [
                    {
                        "chunk_id": "demo_chunk_1",
                        "text": f"Sample content for {spec['subject']} related to {spec.get('topic', 'general concepts')}",
                        "subject": spec["subject"],
                        "skill_ids": spec["skills"]
                    }
                ]
            
            logger.info(f"✅ Retriever node completed - Retrieved {len(chunks)} chunks")
            return {
                **state,
                "retrieved_chunks": chunks,
                "status": "retrieved"
            }
        except Exception as e:
            return {
                **state,
                "status": "error",
                "error": f"Retrieval error: {str(e)}"
            }
    
    # Generator node
    async def generator_node(state: dict) -> dict:
        """Generate question using LLM"""
        try:
            if state.get("status") != "retrieved":
                return state
            
            start_time = datetime.now()
            spec = state["spec"]
            chunks = state.get("retrieved_chunks", [])
            
            # Debug: Log the current state
            logger.info(f"Generator node - Status: {state.get('status')}")
            logger.info(f"Generator node - LLM available: {llm is not None}")
            logger.info(f"Generator node - Spec: {spec}")
            logger.info(f"Generator node - Chunks: {len(chunks)}")
            
            # Prepare context from retrieved chunks
            context = "\n\n".join([
                f"Source {i+1}: {chunk.get('text', '')}" 
                for i, chunk in enumerate(chunks[:3])
            ])
            
            if llm:
                logger.info("Using LLM for question generation")
                # Load prompt template from files
                prompt_template = prompt_manager.get_question_generation_template()
                
                # Generate question
                chain = prompt_template | llm
                
                response = await chain.ainvoke({
                    "question_type": spec["question_type"],
                    "subject": spec["subject"],
                    "topic": spec.get("topic", "general"),
                    "difficulty": spec["difficulty"],
                    "skills": ", ".join(spec["skills"]) if spec["skills"] else "general knowledge",
                    "context": context or f"General {spec['subject']} knowledge"
                })
                
                # Parse response - OpenAI JSON mode guarantees valid JSON
                try:
                    logger.info(f"LLM Response (first 200 chars): {response.content[:200]}...")
                    question_data = json.loads(response.content)
                    logger.info(f"✅ Successfully parsed JSON: {question_data.get('stem', 'No stem')}")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON Parse Error (this should not happen with JSON mode): {str(e)}")
                    logger.error(f"Raw response: {response.content}")
                    
                    # This should rarely happen with JSON mode, but keep fallback for safety
                    question_data = {
                        "stem": f"Error parsing LLM response for {spec['subject']} {spec.get('topic', 'question')}",
                        "options": [
                            {"id": "a", "text": "Option A"},
                            {"id": "b", "text": "Option B"},
                            {"id": "c", "text": "Option C"},
                            {"id": "d", "text": "Option D"}
                        ],
                        "correct_option_ids": ["a"],
                        "canonical_solution": "Unable to parse LLM response",
                        "explanation": "This is a fallback question due to parsing error"
                    }
            else:
                logger.info("LLM not available, using fallback mock question")
                # Fallback: generate mock question
                question_data = {
                    "stem": f"Which of the following best describes {spec.get('topic', 'the main concept')} in {spec['subject']}?",
                    "options": [
                        {"id": "a", "text": f"Basic concept in {spec['subject']}"},
                        {"id": "b", "text": f"Advanced concept in {spec['subject']}"},
                        {"id": "c", "text": f"Unrelated concept"},
                        {"id": "d", "text": f"Incorrect information"}
                    ],
                    "correct_option_ids": ["a"],
                    "canonical_solution": f"The correct answer relates to fundamental {spec['subject']} principles.",
                    "explanation": f"This question assesses understanding of {spec.get('topic', 'core concepts')}.",
                    "citations": [{"chunk_id": chunk.get("chunk_id"), "text": chunk.get("text", "")[:100]} for chunk in chunks[:2]]
                }
            
            # Create question candidate
            question_candidate = QuestionCandidate(
                stem=question_data.get("stem", ""),
                options=[
                    {"id": opt["id"], "text": opt["text"]} 
                    for opt in question_data.get("options", [])
                ],
                correct_option_ids=question_data.get("correct_option_ids", []),
                question_type=spec["question_type"],
                canonical_solution=question_data.get("canonical_solution"),
                explanation=question_data.get("explanation"),
                citations=question_data.get("citations", []),
                difficulty=spec["difficulty"],
                tags=[spec["subject"], spec.get("topic", ""), spec["difficulty"]],
                skill_ids=spec["skills"]
            )
            
            generation_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            logger.info(f"✅ Generator node completed - Status: generated, Question: {question_candidate.stem[:50]}...")
            return {
                **state,
                "question_candidate": question_candidate,
                "generation_time_ms": generation_time,
                "status": "generated"
            }
        except Exception as e:
            return {
                **state,
                "status": "error",
                "error": f"Generation error: {str(e)}"
            }
    
    # Validator node
    async def validator_node(state: dict) -> dict:
        """Run all validators on the generated question"""
        logger.info("🔄 Validator node executing...")
        try:
            if state.get("status") != "generated":
                logger.info(f"❌ Validator node skipped - Status: {state.get('status')}")
                return state
            
            question = state.get("question_candidate")
            if not question:
                return {
                    **state,
                    "status": "error",
                    "error": "No question to validate"
                }
            
            # Run validators
            validation_results = {}
            
            if question_validator:
                validation_results = await question_validator.validate_all(question, state["spec"])
            else:
                # Mock validation for demo
                validation_results = {
                    "schema": ValidationResult(
                        validator_name="schema",
                        passed=True,
                        score=1.0,
                        details={"message": "Schema validation passed"}
                    ),
                    "grounding": ValidationResult(
                        validator_name="grounding",
                        passed=True,
                        score=0.9,
                        details={"message": "Question is well grounded in context"}
                    ),
                    "difficulty": ValidationResult(
                        validator_name="difficulty",
                        passed=True,
                        score=0.8,
                        details={"estimated_difficulty": state["spec"]["difficulty"]}
                    )
                }
            
            # Check if validation passed
            all_passed = all(result.passed for result in validation_results.values())
            
            logger.info(f"✅ Validator node completed - Status: {'success' if all_passed else 'validation_failed'}")
            return {
                **state,
                "validation_results": validation_results,
                "status": "success" if all_passed else "validation_failed"
            }
        except Exception as e:
            return {
                **state,
                "status": "error",
                "error": f"Validation error: {str(e)}"
            }
    
    # Add nodes to workflow
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("generator", generator_node)
    workflow.add_node("validator", validator_node)
    
    # Add edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "generator")
    workflow.add_edge("generator", "validator")
    workflow.add_edge("validator", END)
    
    # Compile graph
    compiled_graph = workflow.compile()
    logger.info("✅ Question generation graph compiled successfully")
    logger.info(f"Graph nodes: {list(compiled_graph.nodes.keys())}")
    return compiled_graph
