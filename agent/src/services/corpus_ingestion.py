import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

# LangChain imports for pgvector and embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
import psycopg2

logger = logging.getLogger(__name__)

class CorpusIngestion:
    """RAG corpus ingestion pipeline using LangChain's pgvector integration"""
    
    def __init__(self, postgres_url: str, openai_api_key: str):
        self.postgres_url = postgres_url
        self.openai_api_key = openai_api_key
        self.embeddings = None
        self.vector_store = None
        
    async def _create_tables_manually(self):
        """Create the required tables manually with the correct schema"""
        try:
            conn = psycopg2.connect(self.postgres_url)
            
            with conn.cursor() as cursor:
                # First, check if tables already exist
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name IN ('langchain_pg_collection', 'langchain_pg_embedding')
                """)
                existing_tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"Existing tables before creation: {existing_tables}")
                
                # Drop existing tables first to ensure clean slate
                if 'langchain_pg_embedding' in existing_tables:
                    cursor.execute("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE")
                    logger.info("✅ Dropped existing langchain_pg_embedding table")
                
                if 'langchain_pg_collection' in existing_tables:
                    cursor.execute("DROP TABLE IF EXISTS langchain_pg_collection CASCADE")
                    logger.info("✅ Dropped existing langchain_pg_collection table")
                
                # Create the collection table
                cursor.execute("""
                    CREATE TABLE langchain_pg_collection (
                        uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name VARCHAR NOT NULL UNIQUE,
                        cmetadata JSONB
                    )
                """)
                logger.info("✅ Created langchain_pg_collection table")
                
                # Create the embedding table
                cursor.execute("""
                    CREATE TABLE langchain_pg_embedding (
                        uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        collection_id UUID REFERENCES langchain_pg_collection(uuid) ON DELETE CASCADE,
                        embedding vector(1536),
                        document TEXT,
                        cmetadata JSONB,
                        custom_id VARCHAR
                    )
                """)
                logger.info("✅ Created langchain_pg_embedding table")
                
                # Insert the collection record
                cursor.execute("""
                    INSERT INTO langchain_pg_collection (name, cmetadata) 
                    VALUES (%s, %s)
                """, ("corpus_chunks", "{}"))
                logger.info("✅ Inserted collection record")
                
                # Verify tables were created
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name IN ('langchain_pg_collection', 'langchain_pg_embedding')
                """)
                final_tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"Final tables after creation: {final_tables}")
                
                # Verify collection record exists
                cursor.execute("SELECT COUNT(*) FROM langchain_pg_collection WHERE name = %s", ("corpus_chunks",))
                collection_count = cursor.fetchone()[0]
                logger.info(f"Collection records: {collection_count}")
                
                conn.commit()
                logger.info("✅ Successfully created all LangChain tables")
                
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to create tables manually: {e}")
            if 'conn' in locals():
                try:
                    conn.rollback()
                except:
                    pass
                conn.close()
            raise

    async def _verify_tables_exist(self):
        """Verify that the required tables exist and are accessible"""
        try:
            conn = psycopg2.connect(self.postgres_url)
            
            with conn.cursor() as cursor:
                # Check if tables exist
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name IN ('langchain_pg_collection', 'langchain_pg_embedding')
                """)
                tables = [row[0] for row in cursor.fetchall()]
                
                if len(tables) != 2:
                    raise Exception(f"Expected 2 tables, found {len(tables)}: {tables}")
                
                # Check if collection exists
                cursor.execute("SELECT COUNT(*) FROM langchain_pg_collection WHERE name = %s", ("corpus_chunks",))
                collection_count = cursor.fetchone()[0]
                
                if collection_count == 0:
                    raise Exception("Collection 'corpus_chunks' not found")
                
                logger.info("✅ Table verification successful")
                
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Table verification failed: {e}")
            return False

    async def initialize(self):
        """Initialize OpenAI embeddings and PGVector store"""
        try:
            # Initialize OpenAI embeddings
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=self.openai_api_key,
                model="text-embedding-3-small"
            )
            logger.info("✅ Initialized OpenAI embeddings")
            
            # Create tables manually first
            await self._create_tables_manually()
            
            # Verify tables exist
            if not await self._verify_tables_exist():
                raise Exception("Failed to verify tables exist")
            
            # Initialize PGVector store with a fixed collection name
            self.vector_store = PGVector(
                connection_string=self.postgres_url,
                embedding_function=self.embeddings,
                collection_name="corpus_chunks"
            )
            logger.info("✅ Connected to PGVector for RAG corpus")
            
        except Exception as e:
            logger.error(f"Failed to initialize corpus ingestion: {e}")
            raise
    
    async def clear_corpus(self):
        """Clear all existing corpus data from LangChain tables"""
        try:
            # Connect directly to PostgreSQL to clear LangChain tables
            conn = psycopg2.connect(self.postgres_url)
            
            with conn.cursor() as cursor:
                # First check what tables exist
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name IN ('langchain_pg_collection', 'langchain_pg_embedding')
                """)
                existing_tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"Found existing tables: {existing_tables}")
                
                # Drop all LangChain tables to start fresh
                if 'langchain_pg_embedding' in existing_tables:
                    cursor.execute("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE")
                    logger.info("✅ Dropped langchain_pg_embedding table")
                
                if 'langchain_pg_collection' in existing_tables:
                    cursor.execute("DROP TABLE IF EXISTS langchain_pg_collection CASCADE")
                    logger.info("✅ Dropped langchain_pg_collection table")
                
                # Verify tables were dropped
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name IN ('langchain_pg_collection', 'langchain_pg_embedding')
                """)
                remaining_tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"Remaining tables after drop: {remaining_tables}")
                
                if len(remaining_tables) > 0:
                    logger.warning(f"⚠️ Some tables still exist: {remaining_tables}")
                else:
                    logger.info("✅ All LangChain tables successfully dropped")
                
                conn.commit()
                
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to clear corpus: {e}")
            if 'conn' in locals():
                try:
                    conn.rollback()
                except:
                    pass
                conn.close()
            raise

    async def ingest_document(
        self, 
        content: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """Ingest a single document into the corpus with embeddings"""
        try:
            # Chunk the document using LangChain's text splitter
            chunks = await self._chunk_document(content, metadata)
            
            # Create LangChain Documents with metadata
            documents = []
            for i, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk["text"],
                    metadata={
                        "doc_id": f"doc_{hashlib.md5(content.encode()).hexdigest()[:8]}",
                        "ordinal": i + 1,
                        "subject": metadata.get("subject"),
                        "class": metadata.get("class"),
                        "chapter": metadata.get("chapter"),
                        "module": metadata.get("module"),
                        "title": metadata.get("title"),
                        "source": metadata.get("source"),
                        "skill_ids": chunk["skill_ids"],
                        "token_count": chunk["token_count"],
                        "chunk_metadata": chunk.get("metadata", {})
                    }
                )
                documents.append(doc)
            
            # Add documents to vector store (this will generate and store embeddings)
            await self.vector_store.aadd_documents(documents)
            
            logger.info(f"Ingested document with {len(chunks)} chunks and embeddings")
            return f"doc_{hashlib.md5(content.encode()).hexdigest()[:8]}"
        
        except Exception as e:
            logger.error(f"Error ingesting document: {e}")
            raise
    
    async def _chunk_document(
        self, 
        content: str, 
        metadata: Dict[str, Any],
        chunk_size: int = 800,
        overlap: int = 100
    ) -> List[Dict[str, Any]]:
        """Chunk document using LangChain's RecursiveCharacterTextSplitter"""
        
        # Clean and normalize content
        content = self._clean_text(content)
        
        # Use LangChain's text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Split text
        text_chunks = text_splitter.split_text(content)
        
        # Process chunks
        chunks = []
        for chunk_text in text_chunks:
            if len(chunk_text.strip()) < 50:  # Skip very short chunks
                continue
            
            chunk = {
                "text": chunk_text,
                "token_count": self._estimate_tokens(chunk_text),
                "skill_ids": self._extract_skills(chunk_text, metadata),
                "metadata": {
                    "has_equations": bool(re.search(r'\$.*?\$|\\[.*?\\]', chunk_text)),
                    "has_code": bool(re.search(r'```|`[^`]+`', chunk_text))
                }
            }
            chunks.append(chunk)
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Normalize common patterns
        text = re.sub(r'([.!?])\s*\n\s*', r'\1 ', text)  # Join sentences
        text = re.sub(r'\n\s*\n\s*', '\n\n', text)  # Normalize paragraphs
        
        # Preserve mathematical notation
        text = re.sub(r'\$\s+', '$', text)
        text = re.sub(r'\s+\$', '$', text)
        
        return text.strip()
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (simple approximation)"""
        # Rough approximation: 1 token ≈ 0.75 words
        word_count = len(text.split())
        return int(word_count / 0.75)
    
    def _extract_skills(self, text: str, metadata: Dict[str, Any]) -> List[str]:
        """Extract relevant skills from text content"""
        skills = []
        
        # Subject-based skill extraction
        subject = metadata.get("subject", "").lower()
        
        if subject == "math":
            math_skills = [
                "algebra", "geometry", "calculus", "statistics", 
                "arithmetic", "trigonometry", "probability"
            ]
            for skill in math_skills:
                if skill in text.lower():
                    skills.append(skill)
        
        elif subject == "science":
            science_skills = [
                "physics", "chemistry", "biology", "mechanics",
                "thermodynamics", "genetics", "ecology"
            ]
            for skill in science_skills:
                if skill in text.lower():
                    skills.append(skill)
        
        # Add topic as skill if present
        if metadata.get("topic"):
            skills.append(metadata["topic"].lower())
        
        # Remove duplicates
        return list(set(skills))
    
    async def ingest_sample_corpus(self):
        """Ingest sample educational content with embeddings"""
        sample_documents = [
            {
                "content": """
                # Algebra Fundamentals
                
                ## Linear Equations
                A linear equation is an equation that makes a straight line when graphed. 
                The general form is y = mx + b, where m is the slope and b is the y-intercept.
                
                ### Solving Linear Equations
                To solve ax + b = c:
                1. Subtract b from both sides: ax = c - b
                2. Divide both sides by a: x = (c - b) / a
                
                Example: Solve 2x + 3 = 7
                - Subtract 3: 2x = 4
                - Divide by 2: x = 2
                
                ## Quadratic Equations
                A quadratic equation has the form ax² + bx + c = 0 where a ≠ 0.
                The quadratic formula is: x = (-b ± √(b² - 4ac)) / 2a
                
                Example: Solve x² - 5x + 6 = 0
                Using the formula: x = (5 ± √(25 - 24)) / 2 = (5 ± 1) / 2
                So x = 3 or x = 2
                """,
                "metadata": {
                    "subject": "math",
                    "class": "8",
                    "chapter": "Algebra",
                    "module": "Linear and Quadratic Equations",
                    "title": "Introduction to Algebraic Equations",
                    "source": "Sample Math Curriculum",
                    "license": "CC-BY"
                }
            },
            {
                "content": """
                # Basic Physics: Motion and Forces
                
                ## Newton's Laws of Motion
                
                ### First Law (Inertia)
                An object at rest stays at rest, and an object in motion stays in motion 
                unless acted upon by an external force.
                
                ### Second Law (Force and Acceleration)
                The acceleration of an object is directly proportional to the net force 
                acting on it and inversely proportional to its mass: F = ma
                
                ### Third Law (Action-Reaction)
                For every action, there is an equal and opposite reaction.
                
                ## Energy and Work
                Energy is the ability to do work. Work is done when a force moves an object.
                
                ### Kinetic Energy
                KE = ½mv² where m is mass and v is velocity
                
                ### Potential Energy
                PE = mgh where m is mass, g is gravitational acceleration, and h is height
                
                ## Momentum
                Momentum is the product of mass and velocity: p = mv
                In a closed system, total momentum is conserved.
                """,
                "metadata": {
                    "subject": "science",
                    "class": "9",
                    "chapter": "Mechanics",
                    "module": "Newton's Laws and Energy",
                    "title": "Fundamentals of Classical Mechanics",
                    "source": "Sample Physics Curriculum",
                    "license": "CC-BY"
                }
            },
            {
                "content": """
                # Chemistry: Atomic Structure and Bonding
                
                ## Atomic Structure
                Atoms consist of a nucleus containing protons and neutrons, 
                surrounded by electrons in energy levels.
                
                ### Subatomic Particles
                - Protons: Positive charge, mass ≈ 1 amu
                - Neutrons: No charge, mass ≈ 1 amu  
                - Electrons: Negative charge, mass ≈ 1/1836 amu
                
                ## Chemical Bonding
                
                ### Ionic Bonds
                Formed by the transfer of electrons between atoms, 
                creating positively and negatively charged ions.
                
                Example: NaCl (Sodium Chloride)
                - Na loses 1 electron → Na⁺
                - Cl gains 1 electron → Cl⁻
                
                ### Covalent Bonds
                Formed by sharing electrons between atoms.
                
                Example: H₂O (Water)
                - Oxygen shares electrons with two hydrogen atoms
                - Creates a bent molecular structure
                
                ## Periodic Table
                Elements are arranged by increasing atomic number.
                Groups (columns) have similar chemical properties.
                Periods (rows) show energy levels.
                """,
                "metadata": {
                    "subject": "science",
                    "class": "9",
                    "chapter": "Chemistry",
                    "module": "Atomic Structure",
                    "title": "Introduction to Atomic Theory",
                    "source": "Sample Chemistry Curriculum",
                    "license": "CC-BY"
                }
            }
        ]
        
        for doc in sample_documents:
            await self.ingest_document(doc["content"], doc["metadata"])
        
        logger.info(f"✅ Ingested {len(sample_documents)} sample documents with embeddings")
    
    async def close(self):
        """Close any open connections"""
        # PGVector handles its own connections, so nothing to close here
        pass

# CLI for running ingestion
async def main():
    """Main function for running corpus ingestion"""
    import sys
    
    # Get OpenAI API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("❌ OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    
    ingestion = CorpusIngestion(
        postgres_url=os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/aitutor"),
        openai_api_key=openai_api_key
    )
    
    await ingestion.initialize()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "clear":
            await ingestion.clear_corpus()
            print("✅ Cleared existing corpus")
        elif sys.argv[1] == "sample":
            await ingestion.ingest_sample_corpus()
            print("✅ Ingested sample corpus with embeddings")
        else:
            print("Usage: python -m corpus_ingestion [clear|sample]")
    else:
        print("Usage: python -m corpus_ingestion [clear|sample]")
    
    await ingestion.close()

if __name__ == "__main__":
    asyncio.run(main())
