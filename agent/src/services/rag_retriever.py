import asyncio
from typing import List, Dict, Any, Optional
import logging
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain.schema import Document

logger = logging.getLogger(__name__)

class RAGRetriever:
    """RAG corpus retriever using LangChain's PGVector and OpenAI embeddings"""
    
    def __init__(self, postgres_url: str, openai_api_key: str):
        self.postgres_url = postgres_url
        self.openai_api_key = openai_api_key
        self.embeddings = None
        self.vector_store = None
        self._healthy = False
    
    async def initialize(self):
        """Initialize OpenAI embeddings and PGVector store"""
        try:
            # Initialize OpenAI embeddings
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=self.openai_api_key,
                model="text-embedding-3-small"
            )
            logger.info("✅ Initialized OpenAI embeddings")
            
            # Connect to existing math_exemplars collection (don't drop it!)
            import psycopg2
            conn = psycopg2.connect(self.postgres_url)
            try:
                with conn.cursor() as cursor:
                    # Check if collection exists
                    cursor.execute("""
                        SELECT c.uuid, COUNT(e.uuid) as embedding_count
                        FROM langchain_pg_collection c
                        LEFT JOIN langchain_pg_embedding e ON c.uuid = e.collection_id
                        WHERE c.name = 'math_exemplars'
                        GROUP BY c.uuid
                    """)
                    result = cursor.fetchone()
                    
                    if result:
                        collection_id, embedding_count = result
                        logger.info(f"✅ Found existing math_exemplars collection: {collection_id}")
                        logger.info(f"✅ Collection has {embedding_count} existing embeddings")
                    else:
                        logger.info("⚠️ No math_exemplars collection found - will be created when first used")
                        
            except Exception as e:
                logger.error(f"Error checking collection status: {e}")
            finally:
                conn.close()
            
            # Initialize PGVector store connection to math_exemplars collection
            self.vector_store = PGVector(
                connection_string=self.postgres_url,
                embedding_function=self.embeddings,
                collection_name="math_exemplars"
            )
            logger.info("✅ Connected to PGVector for RAG retrieval")
            
            self._healthy = True
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG retriever: {e}")
            self._healthy = False
            raise
    
    def is_healthy(self) -> bool:
        """Check if retriever is healthy"""
        return self._healthy
    
    async def search(
        self, 
        query: str, 
        subject: Optional[str] = None,
        class_level: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search corpus for relevant chunks using LangChain's vector similarity search"""
        try:
            if not self._healthy:
                raise Exception("RAG retriever not healthy")
            
            logger.info(f"🔍 RAG Search - Query: '{query}'")
            logger.info(f"🔍 RAG Search - Subject: '{subject}'")
            logger.info(f"🔍 RAG Search - Class Level: '{class_level}'")
            
            # Build filter for metadata (using Hendrycks math_exemplars structure)
            filter_dict = {"type": "math_exemplar"}  # Always filter for math exemplars
            if subject and subject != "math":
                # If specific subject is requested (algebra, geometry, etc.), filter by it
                filter_dict["subject"] = subject
            # Note: If subject="math", we search across ALL math subjects in Hendrycks dataset
            # Note: Hendrycks dataset doesn't have class_level, it has difficulty levels
            # We'll ignore class_level for now since we're using high-quality math problems
            
            # Use LangChain's similarity search
            docs = self.vector_store.similarity_search(
                query=query,
                k=limit,
                filter=filter_dict if filter_dict else {}
            )
            
            logger.info(f"🔍 RAG Search - Retrieved {len(docs)} documents")
            
            # Convert LangChain Documents to our format (adapted for Hendrycks exemplars)
            chunks = []
            for doc in docs:
                chunk = {
                    "chunk_id": doc.metadata.get("exemplar_id", doc.metadata.get("index", "unknown")),
                    "text": doc.page_content,
                    "skill_ids": [],  # Hendrycks doesn't have skill_ids
                    "metadata": doc.metadata,
                    "subject": doc.metadata.get("subject", "unknown"),
                    "class_level": doc.metadata.get("level", "unknown"),  # Use level instead of class
                    "chapter": None,  # Hendrycks doesn't have chapters
                    "module": None,   # Hendrycks doesn't have modules
                    "title": f"Math Problem - {doc.metadata.get('subject', 'Unknown Subject')}",
                    "source": doc.metadata.get("source", "hendrycks_math"),
                    "difficulty": doc.metadata.get("difficulty", "unknown"),
                    "relevance_score": 1.0  # LangChain doesn't provide scores by default
                }
                chunks.append(chunk)
            
            logger.info(f"Retrieved {len(chunks)} chunks for query: {query}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error in RAG search: {e}")
            raise
    
    async def close(self):
        """Close any open connections"""
        # PGVector handles its own connections, so nothing to close here
        pass
