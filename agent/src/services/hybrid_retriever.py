"""
Hybrid Retriever for Exemplar-Driven Question Generation

This service combines retrieval from multiple sources:
1. MCQ exemplars (Hendrycks MATH dataset)
2. Concept corpus (existing RAG content)
3. Template patterns (mathematical structures)

Features reranking and confidence scoring for path selection.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import re
import json

logger = logging.getLogger(__name__)

class HybridRetriever:
    """
    Hybrid retrieval system that combines exemplars, concepts, and templates
    with confidence-based routing and reranking.
    """
    
    def __init__(self, rag_retriever, hendrycks_manager, settings):
        self.rag_retriever = rag_retriever
        self.hendrycks_manager = hendrycks_manager
        self.settings = settings
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        
    async def retrieve(self, spec: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """
        Main retrieval method that combines multiple sources and returns
        reranked results with confidence scoring.
        """
        logger.info(f"🔍 [Trace: {trace_id}] Starting hybrid retrieval")
        logger.info(f"🔍 [Trace: {trace_id}] Spec: {spec}")
        
        try:
            # Extract search parameters
            subject = spec.get("subject", "")
            topic = spec.get("topic", "")
            difficulty = spec.get("difficulty", "medium")
            skills = spec.get("skills", [])
            
            # Build search query
            query_parts = [subject]
            if topic:
                query_parts.append(topic)
            if skills:
                query_parts.extend(skills)
            search_query = " ".join(query_parts)
            
            logger.info(f"🔍 [Trace: {trace_id}] Search query: '{search_query}'")
            
            # Parallel retrieval from multiple sources
            tasks = [
                self._retrieve_exemplars(search_query, subject, difficulty, trace_id, topic),
                self._retrieve_concepts(search_query, spec, trace_id),
                self._extract_templates(search_query, subject, topic, trace_id)
            ]
            
            exemplars, concepts, templates = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle any exceptions
            if isinstance(exemplars, Exception):
                logger.error(f"❌ [Trace: {trace_id}] Exemplar retrieval failed: {exemplars}")
                exemplars = []
            
            if isinstance(concepts, Exception):
                logger.error(f"❌ [Trace: {trace_id}] Concept retrieval failed: {concepts}")
                concepts = []
            
            if isinstance(templates, Exception):
                logger.error(f"❌ [Trace: {trace_id}] Template extraction failed: {templates}")
                templates = []
            
            logger.info(f"✅ [Trace: {trace_id}] Retrieved {len(exemplars)} exemplars, {len(concepts)} concepts, {len(templates)} templates")
            
            # Rerank and merge results
            merged_results = await self._rerank_and_merge(
                search_query, exemplars, concepts, templates, trace_id
            )
            
            # Calculate confidence score for path selection
            confidence_score = self._calculate_confidence_score(merged_results, spec)
            
            # Determine generation path
            generation_path = "template" if confidence_score >= self.settings.retrieval_tau else "direct"
            
            logger.info(f"🎯 [Trace: {trace_id}] Confidence: {confidence_score:.3f}, Path: {generation_path}")
            
            return {
                "exemplars": exemplars[:self.settings.exemplar_k],
                "concepts": concepts[:3],  # Top 3 concept chunks
                "templates": templates[:2] if generation_path == "template" else [],
                "merged_chunks": merged_results[:5],  # Top 5 reranked results
                "confidence_score": confidence_score,
                "generation_path": generation_path,
                "retrieval_metadata": {
                    "query": search_query,
                    "total_candidates": len(exemplars) + len(concepts) + len(templates),
                    "reranked_count": len(merged_results),
                    "path_reason": f"Confidence {confidence_score:.3f} {'≥' if confidence_score >= self.settings.retrieval_tau else '<'} threshold {self.settings.retrieval_tau}"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] Hybrid retrieval failed: {str(e)}")
            return {
                "exemplars": [],
                "concepts": [],
                "templates": [],
                "merged_chunks": [],
                "confidence_score": 0.0,
                "generation_path": "direct",
                "error": str(e)
            }
    
    async def _retrieve_exemplars(self, query: str, subject: str, difficulty: str, trace_id: str, topic: str = "") -> List[Dict]:
        """Retrieve relevant exemplars from Hendrycks dataset"""
        try:
            logger.info(f"🔍 [Trace: {trace_id}] Retrieving exemplars...")
            
            # Map general subjects to math subjects (now returns list)
            math_subjects = self._map_to_math_subject(subject, topic)
            logger.info(f"🔍 [Trace: {trace_id}] Mapped to math subjects: {math_subjects}")
            
            all_exemplars = []
            
            # Search across all relevant math subjects
            for math_subject in math_subjects:
                exemplars = await self.hendrycks_manager.search_exemplars(
                    query=query,
                    subject=math_subject,
                    difficulty=difficulty,
                    limit=self.settings.rerank_top_k // len(math_subjects)  # Distribute limit
                )
                all_exemplars.extend(exemplars)
                logger.info(f"🔍 [Trace: {trace_id}] Found {len(exemplars)} exemplars from {math_subject}")
            
            # Remove duplicates by exemplar_id
            seen_ids = set()
            unique_exemplars = []
            for exemplar in all_exemplars:
                exemplar_id = exemplar.get('exemplar_id')
                if exemplar_id and exemplar_id not in seen_ids:
                    seen_ids.add(exemplar_id)
                    unique_exemplars.append(exemplar)
            
            logger.info(f"✅ [Trace: {trace_id}] Found {len(unique_exemplars)} unique exemplars")
            return unique_exemplars[:self.settings.rerank_top_k]  # Limit total results
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] Exemplar retrieval error: {e}")
            return []
    
    async def _retrieve_concepts(self, query: str, spec: Dict, trace_id: str) -> List[Dict]:
        """Retrieve relevant concept chunks from RAG corpus"""
        try:
            logger.info(f"🔍 [Trace: {trace_id}] Retrieving concept chunks...")
            
            if not self.rag_retriever:
                logger.warning(f"⚠️ [Trace: {trace_id}] RAG retriever not available")
                return []
            
            concepts = await self.rag_retriever.search(
                query=query,
                subject=spec.get("subject"),
                class_level=spec.get("class"),
                limit=self.settings.rerank_top_k
            )
            
            logger.info(f"✅ [Trace: {trace_id}] Found {len(concepts)} concept chunks")
            return concepts
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] Concept retrieval error: {e}")
            return []
    
    async def _extract_templates(self, query: str, subject: str, topic: str, trace_id: str) -> List[Dict]:
        """Extract mathematical templates from query and subject"""
        try:
            logger.info(f"🔍 [Trace: {trace_id}] Extracting math templates...")
            
            templates = []
            
            # Only extract templates for math subjects
            if not self._is_math_subject(subject):
                logger.info(f"📝 [Trace: {trace_id}] Non-math subject, skipping template extraction")
                return templates
            
            # Template patterns for different math topics
            template_patterns = {
                "algebra": [
                    {"pattern": "ax + b = c", "variables": ["a", "b", "c"], "type": "linear_equation"},
                    {"pattern": "ax² + bx + c = 0", "variables": ["a", "b", "c"], "type": "quadratic_equation"},
                    {"pattern": "(x + a)(x + b) = 0", "variables": ["a", "b"], "type": "factored_quadratic"}
                ],
                "geometry": [
                    {"pattern": "A = πr²", "variables": ["r"], "type": "circle_area"},
                    {"pattern": "a² + b² = c²", "variables": ["a", "b", "c"], "type": "pythagorean"},
                    {"pattern": "A = ½bh", "variables": ["b", "h"], "type": "triangle_area"}
                ],
                "calculus": [
                    {"pattern": "d/dx[f(x)] = f'(x)", "variables": ["f"], "type": "derivative"},
                    {"pattern": "∫f(x)dx = F(x) + C", "variables": ["f", "F"], "type": "integral"}
                ]
            }
            
            # Find relevant patterns
            topic_lower = topic.lower() if topic else ""
            for template_type, patterns in template_patterns.items():
                if template_type in topic_lower or any(keyword in topic_lower for keyword in ["equation", "formula", "solve"]):
                    for pattern in patterns:
                        templates.append({
                            "template_id": f"{template_type}_{pattern['type']}",
                            "pattern": pattern["pattern"],
                            "variables": pattern["variables"],
                            "type": pattern["type"],
                            "subject": template_type,
                            "confidence": 0.8,  # Default template confidence
                            "metadata": {
                                "source": "built_in_templates",
                                "applicable_topics": [topic_lower]
                            }
                        })
            
            logger.info(f"✅ [Trace: {trace_id}] Extracted {len(templates)} templates")
            return templates
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] Template extraction error: {e}")
            return []
    
    async def _rerank_and_merge(self, query: str, exemplars: List, concepts: List, 
                               templates: List, trace_id: str) -> List[Dict]:
        """Rerank and merge results from all sources using hybrid scoring"""
        try:
            logger.info(f"🔄 [Trace: {trace_id}] Reranking and merging results...")
            
            all_candidates = []
            
            # Add exemplars with source tagging
            for exemplar in exemplars:
                all_candidates.append({
                    "content": f"{exemplar.get('problem', '')} {exemplar.get('solution', '')}",
                    "source": "exemplar",
                    "data": exemplar,
                    "base_score": 1.0  # High base score for exemplars
                })
            
            # Add concepts with source tagging
            for concept in concepts:
                content = concept.get('text', '') if isinstance(concept, dict) else str(concept)
                all_candidates.append({
                    "content": content,
                    "source": "concept",
                    "data": concept,
                    "base_score": 0.8  # Medium base score for concepts
                })
            
            # Add templates with source tagging
            for template in templates:
                all_candidates.append({
                    "content": f"{template.get('pattern', '')} {template.get('type', '')}",
                    "source": "template",
                    "data": template,
                    "base_score": 0.6  # Lower base score for templates
                })
            
            if not all_candidates:
                logger.warning(f"⚠️ [Trace: {trace_id}] No candidates to rerank")
                return []
            
            # Calculate similarity scores
            contents = [query] + [candidate["content"] for candidate in all_candidates]
            
            try:
                # Use TF-IDF for text similarity
                tfidf_matrix = self.tfidf_vectorizer.fit_transform(contents)
                similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
                
                # Combine with base scores
                for i, candidate in enumerate(all_candidates):
                    text_score = similarities[i]
                    base_score = candidate["base_score"]
                    
                    # Weighted combination
                    final_score = (
                        self.settings.text_embedding_weight * text_score +
                        (1 - self.settings.text_embedding_weight) * base_score
                    )
                    
                    candidate["similarity_score"] = text_score
                    candidate["final_score"] = final_score
                
            except Exception as e:
                logger.warning(f"⚠️ [Trace: {trace_id}] TF-IDF scoring failed: {e}, using base scores")
                for candidate in all_candidates:
                    candidate["similarity_score"] = 0.5
                    candidate["final_score"] = candidate["base_score"]
            
            # Sort by final score
            all_candidates.sort(key=lambda x: x["final_score"], reverse=True)
            
            # Return top candidates with metadata
            reranked_results = []
            for candidate in all_candidates[:10]:  # Top 10
                reranked_results.append({
                    "source": candidate["source"],
                    "data": candidate["data"],
                    "scores": {
                        "similarity": candidate["similarity_score"],
                        "base": candidate["base_score"],
                        "final": candidate["final_score"]
                    }
                })
            
            logger.info(f"✅ [Trace: {trace_id}] Reranked {len(reranked_results)} candidates")
            return reranked_results
            
        except Exception as e:
            logger.error(f"❌ [Trace: {trace_id}] Reranking error: {e}")
            return []
    
    def _calculate_confidence_score(self, merged_results: List[Dict], spec: Dict) -> float:
        """Calculate confidence score for path selection"""
        try:
            if not merged_results:
                return 0.0
            
            # Factors affecting confidence
            factors = []
            
            # 1. Top result score
            top_score = merged_results[0]["scores"]["final"] if merged_results else 0.0
            factors.append(top_score)
            
            # 2. Number of high-quality results
            high_quality_count = sum(1 for r in merged_results if r["scores"]["final"] > 0.7)
            quality_factor = min(high_quality_count / 3.0, 1.0)  # Normalize to 0-1
            factors.append(quality_factor)
            
            # 3. Source diversity
            sources = set(r["source"] for r in merged_results)
            diversity_factor = len(sources) / 3.0  # Max 3 sources
            factors.append(diversity_factor)
            
            # 4. Math subject bonus
            if self._is_math_subject(spec.get("subject", "")):
                factors.append(0.8)  # Bonus for math subjects
            
            # Weighted average
            weights = [0.4, 0.3, 0.2, 0.1]  # Prioritize top score
            confidence = sum(f * w for f, w in zip(factors, weights)) / sum(weights[:len(factors)])
            
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"Confidence calculation error: {e}")
            return 0.0
    
    def _map_to_math_subject(self, subject: str, topic: str = "") -> List[str]:
        """Map general subjects and topics to Hendrycks math subjects"""
        subject_lower = subject.lower()
        topic_lower = topic.lower()
        
        # Topic-based mapping (more specific)
        topic_mapping = {
            "quadratic": ["algebra", "intermediate_algebra"],
            "linear": ["algebra", "prealgebra"],
            "polynomial": ["algebra", "intermediate_algebra"],
            "equation": ["algebra", "intermediate_algebra"],
            "factor": ["algebra", "intermediate_algebra"],
            "graph": ["algebra", "intermediate_algebra", "precalculus"],
            "function": ["algebra", "intermediate_algebra", "precalculus"],
            "triangle": ["geometry"],
            "circle": ["geometry"],
            "area": ["geometry"],
            "volume": ["geometry"],
            "angle": ["geometry"],
            "probability": ["counting_and_probability"],
            "permutation": ["counting_and_probability"],
            "combination": ["counting_and_probability"],
            "statistics": ["counting_and_probability"],
            "prime": ["number_theory"],
            "divisibility": ["number_theory"],
            "modular": ["number_theory"],
            "trigonometry": ["precalculus"],
            "logarithm": ["precalculus"],
            "exponential": ["precalculus"],
            "limit": ["precalculus"],
            "derivative": ["precalculus"],
            "integral": ["precalculus"]
        }
        
        # Check topic keywords first
        subjects = []
        for keyword, math_subjects in topic_mapping.items():
            if keyword in topic_lower:
                subjects.extend(math_subjects)
        
        # Subject-based mapping (fallback)
        subject_mapping = {
            "math": ["algebra", "geometry"],  # Default to common subjects
            "mathematics": ["algebra", "geometry"],
            "algebra": ["algebra", "intermediate_algebra"],
            "geometry": ["geometry"], 
            "calculus": ["precalculus"],
            "statistics": ["counting_and_probability"],
            "probability": ["counting_and_probability"],
            "number_theory": ["number_theory"],
            "pre-algebra": ["prealgebra"],
            "prealgebra": ["prealgebra"]
        }
        
        # Add subject-based mappings if no topic match
        if not subjects:
            for key, math_subjects in subject_mapping.items():
                if key in subject_lower:
                    subjects.extend(math_subjects)
        
        # Remove duplicates and return
        return list(set(subjects)) if subjects else ["algebra"]  # Default fallback
    
    def _is_math_subject(self, subject: str) -> bool:
        """Check if subject is mathematics-related"""
        math_keywords = [
            "math", "mathematics", "algebra", "geometry", "calculus", 
            "statistics", "probability", "arithmetic", "trigonometry",
            "precalculus", "number theory"
        ]
        
        subject_lower = subject.lower()
        return any(keyword in subject_lower for keyword in math_keywords)
