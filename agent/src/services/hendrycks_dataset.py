"""
Hendrycks MATH Dataset Integration Service

This service manages the loading, processing, and storage of the Hendrycks MATH dataset
for use as high-quality exemplars in question generation.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datasets import load_dataset
import json
import hashlib
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class HendrycksDatasetManager:
    """Manages Hendrycks MATH dataset for exemplar-driven question generation"""
    
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.subjects = [
            "algebra",
            "counting_and_probability", 
            "geometry",
            "intermediate_algebra",
            "number_theory",
            "prealgebra",
            "precalculus"
        ]
        
    async def load_all_subjects(self) -> Dict[str, Any]:
        """Load all Hendrycks MATH subject datasets"""
        logger.info("Loading Hendrycks MATH dataset for all subjects...")
        
        datasets = {}
        total_loaded = 0
        
        for subject in self.subjects:
            try:
                logger.info(f"Loading {subject} dataset...")
                dataset = load_dataset("EleutherAI/hendrycks_math", subject)
                datasets[subject] = dataset
                
                train_count = len(dataset['train']) if 'train' in dataset else 0
                test_count = len(dataset['test']) if 'test' in dataset else 0
                total_count = train_count + test_count
                total_loaded += total_count
                
                logger.info(f"✅ Loaded {subject}: {train_count} train + {test_count} test = {total_count} examples")
                
            except Exception as e:
                logger.error(f"❌ Failed to load {subject}: {str(e)}")
                datasets[subject] = None
        
        logger.info(f"✅ Successfully loaded {len([d for d in datasets.values() if d is not None])}/{len(self.subjects)} subjects with {total_loaded} total examples")
        return datasets
    
    def _normalize_latex(self, text: str) -> str:
        """Normalize LaTeX formatting in text"""
        if not text:
            return ""
        
        # Basic LaTeX cleanup
        text = re.sub(r'\$+([^$]+)\$+', r'$\1$', text)  # Normalize dollar signs
        text = re.sub(r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}', r'\\begin{align}\1\\end{align}', text, flags=re.DOTALL)
        text = re.sub(r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}', r'\\begin{equation}\1\\end{equation}', text, flags=re.DOTALL)
        
        # Clean up spacing
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _extract_answer_from_solution(self, solution: str) -> Optional[str]:
        """Extract the final answer from a solution"""
        if not solution:
            return None
        
        # Look for boxed answer
        boxed_match = re.search(r'\\boxed\{([^}]+)\}', solution)
        if boxed_match:
            return boxed_match.group(1)
        
        # Look for "The answer is" pattern
        answer_match = re.search(r'(?:the answer is|answer:|final answer:)\s*([^.\n]+)', solution, re.IGNORECASE)
        if answer_match:
            return answer_match.group(1).strip()
        
        # Look for last mathematical expression
        math_expressions = re.findall(r'\$([^$]+)\$', solution)
        if math_expressions:
            return math_expressions[-1]
        
        return None
    
    def _create_exemplar_document(self, example: Dict, subject: str, split: str, index: int) -> Dict[str, Any]:
        """Create a standardized exemplar document from Hendrycks example"""
        problem = example.get('problem', '')
        solution = example.get('solution', '')
        level = example.get('level', 0)
        
        # Normalize LaTeX
        normalized_problem = self._normalize_latex(problem)
        normalized_solution = self._normalize_latex(solution)
        
        # Extract answer
        extracted_answer = self._extract_answer_from_solution(solution)
        
        # Create unique ID
        content_hash = hashlib.md5(f"{subject}_{problem}_{solution}".encode()).hexdigest()[:12]
        exemplar_id = f"hendrycks_{subject}_{split}_{index}_{content_hash}"
        
        # Determine difficulty based on level (handle string levels)
        try:
            level_int = int(level) if level is not None else 0
        except (ValueError, TypeError):
            level_int = 0
            
        if level_int <= 2:
            difficulty = "easy"
        elif level_int <= 4:
            difficulty = "medium"
        else:
            difficulty = "hard"
        
        return {
            "exemplar_id": exemplar_id,
            "source": "hendrycks_math",
            "subject": "mathematics",
            "math_subject": subject,
            "split": split,
            "level": level,
            "difficulty": difficulty,
            "problem": normalized_problem,
            "solution": normalized_solution,
            "extracted_answer": extracted_answer,
            "original_data": example,
            "metadata": {
                "subject_area": subject,
                "dataset_split": split,
                "index_in_split": index,
                "latex_normalized": True,
                "answer_extracted": extracted_answer is not None
            },
            "ingested_at": datetime.utcnow(),
            "content_hash": content_hash
        }
    
    async def ingest_datasets(self, datasets: Dict[str, Any], max_per_subject: int = 1000, force_reload: bool = False) -> Dict[str, int]:
        """Ingest Hendrycks datasets into MongoDB and vector store"""
        logger.info(f"Starting ingestion of Hendrycks datasets (force_reload={force_reload})...")
        
        ingestion_stats = {}
        total_ingested = 0
        
        for subject, dataset in datasets.items():
            if dataset is None:
                logger.warning(f"Skipping {subject} - dataset not loaded")
                ingestion_stats[subject] = 0
                continue
            
            try:
                logger.info(f"Ingesting {subject} dataset...")
                subject_ingested = 0
                
                # Process train and test splits
                for split_name in ['train', 'test']:
                    if split_name not in dataset:
                        continue
                    
                    split_data = dataset[split_name]
                    split_limit = max_per_subject // 2  # Split evenly between train/test
                    
                    for idx, example in enumerate(split_data):
                        if subject_ingested >= max_per_subject:
                            break
                        
                        if idx >= split_limit:
                            break
                        
                        try:
                            # Create exemplar document
                            exemplar_doc = self._create_exemplar_document(example, subject, split_name, idx)
                            
                            # Check if already exists in vector store (unless force_reload)
                            if not force_reload:
                                existing_results = await self.vector_store.asimilarity_search(
                                    exemplar_doc["exemplar_id"],
                                    k=1,
                                    filter={"exemplar_id": exemplar_doc["exemplar_id"], "type": "math_exemplar"}
                                )
                                if existing_results:
                                    continue
                            
                            # Add to vector store with comprehensive metadata
                            if self.vector_store:
                                try:
                                    from langchain.schema import Document
                                    
                                    # Create rich content for better semantic search
                                    content_parts = [
                                        f"Subject: {exemplar_doc['math_subject']}",
                                        f"Difficulty: {exemplar_doc['difficulty']}",
                                        f"Problem: {exemplar_doc['problem']}",
                                        f"Solution: {exemplar_doc['solution']}"
                                    ]
                                    
                                    if exemplar_doc.get('extracted_answer'):
                                        content_parts.append(f"Answer: {exemplar_doc['extracted_answer']}")
                                    
                                    vector_doc = Document(
                                        page_content="\n".join(content_parts),
                                        metadata={
                                            "exemplar_id": exemplar_doc["exemplar_id"],
                                            "source": "hendrycks_math",
                                            "subject": exemplar_doc["math_subject"],  # Store as 'subject' for filtering
                                            "difficulty": exemplar_doc["difficulty"],
                                            "level": str(exemplar_doc["level"]),
                                            "type": "math_exemplar",
                                            "problem": exemplar_doc["problem"],
                                            "solution": exemplar_doc["solution"],
                                            "extracted_answer": exemplar_doc.get("extracted_answer", ""),
                                            "split": exemplar_doc["split"],
                                            "index": str(idx)
                                        }
                                    )
                                    await self.vector_store.aadd_documents([vector_doc])
                                    logger.debug(f"Added exemplar {exemplar_doc['exemplar_id']} to vector store")
                                except Exception as e:
                                    logger.warning(f"Failed to add exemplar {exemplar_doc['exemplar_id']} to vector store: {e}")
                                    continue
                            
                            subject_ingested += 1
                            
                            if subject_ingested % 50 == 0:
                                logger.info(f"  {subject}: {subject_ingested} exemplars ingested...")
                        
                        except Exception as e:
                            logger.error(f"Failed to process example {idx} from {subject}/{split_name}: {e}")
                            continue
                
                ingestion_stats[subject] = subject_ingested
                total_ingested += subject_ingested
                logger.info(f"✅ Completed {subject}: {subject_ingested} exemplars ingested")
                
            except Exception as e:
                logger.error(f"❌ Failed to ingest {subject}: {str(e)}")
                ingestion_stats[subject] = 0
        
        logger.info(f"✅ Ingestion completed: {total_ingested} total exemplars across {len(ingestion_stats)} subjects")
        
        return ingestion_stats
    
    async def search_exemplars(self, query: str, subject: Optional[str] = None, 
                              difficulty: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant exemplars using semantic similarity"""
        try:
            if not self.vector_store:
                logger.warning("Vector store not available for exemplar search")
                return []
            
            # Build search filter for PostgreSQL/pgvector
            base_filter = {"type": "math_exemplar"}
            if subject:
                base_filter["subject"] = subject
            
            def build_and_run_search(active_difficulty: Optional[str]) -> List[Dict[str, Any]]:
                nonlocal query, limit
                # Compose filter
                search_filter = dict(base_filter)
                if active_difficulty:
                    search_filter["difficulty"] = active_difficulty
                logger.info(f"Exemplar search | query='{query}' | filter={search_filter}")
                return [] if not self.vector_store else []
            
            # Run primary search with provided difficulty
            search_filter = dict(base_filter)
            if difficulty:
                search_filter["difficulty"] = difficulty
            logger.info(f"Exemplar search | query='{query}' | filter={search_filter}")
            
            vector_results = await self.vector_store.asimilarity_search(
                query,
                k=max(limit * 5, 20),  # Broader candidate pool for small datasets
                filter=search_filter
            )
            logger.info(f"Exemplar search | vector_results={len(vector_results)}")
            
            def collect_matches(results: List[Any], subj: Optional[str], diff: Optional[str]) -> List[Dict[str, Any]]:
                collected: List[Dict[str, Any]] = []
                for doc in results:
                    if len(collected) >= limit:
                        break
                    metadata = getattr(doc, 'metadata', {}) or {}
                    if self._matches_criteria_from_metadata(metadata, subj, diff):
                        collected.append({
                            "exemplar_id": metadata.get("exemplar_id"),
                            "source": metadata.get("source", "hendrycks_math"),
                            "math_subject": metadata.get("subject"),
                            "difficulty": metadata.get("difficulty"),
                            "level": metadata.get("level"),
                            "problem": metadata.get("problem", ""),
                            "solution": metadata.get("solution", ""),
                            "extracted_answer": metadata.get("extracted_answer", ""),
                            "split": metadata.get("split", ""),
                            "similarity_score": getattr(doc, 'similarity_score', None),
                            "page_content": getattr(doc, 'page_content', "")
                        })
                return collected
            
            exemplars = collect_matches(vector_results, subject, difficulty)
            logger.info(f"Exemplar search | matches_with_difficulty={len(exemplars)}")
            
            # Fallback 1: retry without difficulty if none found
            if not exemplars and difficulty:
                fallback_filter = dict(base_filter)
                logger.info(f"Exemplar search fallback | removing difficulty. filter={fallback_filter}")
                vector_results = await self.vector_store.asimilarity_search(
                    query,
                    k=max(limit * 5, 20),
                    filter=fallback_filter
                )
                logger.info(f"Exemplar search fallback | vector_results={len(vector_results)}")
                exemplars = collect_matches(vector_results, subject, None)
                logger.info(f"Exemplar search fallback | matches_without_difficulty={len(exemplars)}")
            
            # Fallback 2: retry without subject (broadest) if still none
            if not exemplars:
                broad_filter = {"type": "math_exemplar"}
                logger.info(f"Exemplar search broad fallback | removing subject. filter={broad_filter}")
                vector_results = await self.vector_store.asimilarity_search(
                    query,
                    k=max(limit * 5, 20),
                    filter=broad_filter
                )
                logger.info(f"Exemplar search broad fallback | vector_results={len(vector_results)}")
                exemplars = collect_matches(vector_results, None, None)
                logger.info(f"Exemplar search broad fallback | matches_without_subject={len(exemplars)}")

            # Fallback 3: subject-only with empty query (guarantee at least some exemplars)
            if not exemplars and subject:
                subject_only_filter = {"type": "math_exemplar", "subject": subject}
                logger.info(f"Exemplar search subject-only fallback | empty query. filter={subject_only_filter}")
                vector_results = await self.vector_store.asimilarity_search(
                    "",
                    k=max(limit * 5, 20),
                    filter=subject_only_filter
                )
                logger.info(f"Exemplar search subject-only fallback | vector_results={len(vector_results)}")
                exemplars = collect_matches(vector_results, subject, None)
                logger.info(f"Exemplar search subject-only fallback | matches_subject_only={len(exemplars)}")
            
            logger.info(f"Exemplar search | final_matches={len(exemplars)}")
            return exemplars
            
        except Exception as e:
            logger.error(f"Error searching exemplars: {e}")
            return []
    
    def _matches_criteria_from_metadata(self, metadata: Dict, subject: Optional[str], difficulty: Optional[str]) -> bool:
        """Check if exemplar metadata matches search criteria"""
        if subject and metadata.get("subject") != subject:
            return False
        if difficulty and metadata.get("difficulty") != difficulty:
            return False
        return True
    
    async def get_exemplar_stats(self) -> Dict[str, Any]:
        """Get statistics about ingested exemplars"""
        try:
            if not self.vector_store:
                return {"total_exemplars": 0, "stats": {"subjects": {}}}
            
            # Get all exemplars by subject using vector search
            subject_stats = {}
            total_count = 0
            
            for subject in self.subjects:
                try:
                    # Search with empty query to get all exemplars for this subject
                    results = await self.vector_store.asimilarity_search(
                        "",  # Empty query gets all
                        k=1000,  # Large limit to count all
                        filter={"type": "math_exemplar", "subject": subject}
                    )
                    count = len(results)
                    subject_stats[subject] = count
                    total_count += count
                except Exception as e:
                    logger.warning(f"Failed to count exemplars for {subject}: {e}")
                    subject_stats[subject] = 0
            
            return {
                "total_exemplars": total_count,
                "stats": {
                    "subjects": subject_stats
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting exemplar stats: {e}")
            return {"error": str(e)}
