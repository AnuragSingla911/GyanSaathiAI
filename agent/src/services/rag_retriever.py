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
            
            # Force recreation of collection by dropping existing one first
            import psycopg2
            conn = psycopg2.connect(self.postgres_url)
            try:
                with conn.cursor() as cursor:
                    # Check if collection exists
                    cursor.execute("""
                        SELECT uuid FROM langchain_pg_collection 
                        WHERE name = 'corpus_chunks'
                    """)
                    existing_collection = cursor.fetchone()
                    
                    if existing_collection:
                        collection_id = existing_collection[0]
                        logger.info(f"Found existing collection: {collection_id}")
                        
                        # Drop all embeddings for this collection
                        cursor.execute("""
                            DELETE FROM langchain_pg_embedding 
                            WHERE collection_id = %s
                        """, (collection_id,))
                        logger.info("✅ Cleared existing embeddings")
                        
                        # Drop the collection
                        cursor.execute("""
                            DELETE FROM langchain_pg_collection 
                            WHERE name = 'corpus_chunks'
                        """)
                        logger.info("✅ Dropped existing collection")
                        
                        conn.commit()
                        logger.info("✅ Collection cleanup completed")
                    else:
                        logger.info("No existing collection found")
                        
            except Exception as e:
                logger.error(f"Error during collection cleanup: {e}")
                conn.rollback()
            finally:
                conn.close()
            
            # Initialize PGVector store with fresh collection
            self.vector_store = PGVector(
                connection_string=self.postgres_url,
                embedding_function=self.embeddings,
                collection_name="corpus_chunks"
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
            
            # Build filter for metadata
            filter_dict = {}
            if subject:
                filter_dict["subject"] = subject
            if class_level:
                filter_dict["class"] = class_level
            
            # Use LangChain's similarity search
            docs = self.vector_store.similarity_search(
                query=query,
                k=limit,
                filter=filter_dict if filter_dict else {}
            )
            
            logger.info(f"🔍 RAG Search - Retrieved {len(docs)} documents")
            
            # Convert LangChain Documents to our format
            chunks = []
            for doc in docs:
                chunk = {
                    "chunk_id": doc.metadata.get("custom_id", "unknown"),
                    "text": doc.page_content,
                    "skill_ids": doc.metadata.get("skill_ids", []),
                    "metadata": doc.metadata,
                    "subject": doc.metadata.get("subject", "unknown"),
                    "class_level": doc.metadata.get("class", "unknown"),
                    "chapter": doc.metadata.get("chapter"),
                    "module": doc.metadata.get("module"),
                    "title": doc.metadata.get("title"),
                    "source": doc.metadata.get("source"),
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
