#!/usr/bin/env python3
"""
Migration script to convert from custom corpus tables to LangChain's expected format.
This script will:
1. Drop old corpus tables
2. Create new LangChain-compatible tables
3. Repopulate with fresh data
"""

import asyncio
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'postgres',
    'port': 5432,
    'database': 'tutor_db',
    'user': 'tutor_user',
    'password': 'tutor_password'
}

def create_langchain_tables(conn):
    """Create LangChain's expected table structure"""
    with conn.cursor() as cur:
        # Ensure vector extension is loaded
        logger.info("Ensuring vector extension is loaded...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Drop old tables if they exist
        logger.info("Dropping old corpus tables...")
        cur.execute("""
            DROP TABLE IF EXISTS corpus_chunks CASCADE;
            DROP TABLE IF EXISTS corpus_documents CASCADE;
            DROP TABLE IF EXISTS skills CASCADE;
        """)
        
        # Drop both tables if they exist to start fresh
        logger.info("Dropping existing tables...")
        cur.execute("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE;")
        cur.execute("DROP TABLE IF EXISTS langchain_pg_collection CASCADE;")
        
        # Create LangChain's collection store table with correct structure
        logger.info("Creating langchain_pg_collection table...")
        cur.execute("""
            CREATE TABLE langchain_pg_collection (
                uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR NOT NULL,
                cmetadata JSONB
            );
        """)
        
        # Create LangChain's embedding store table with proper structure
        logger.info("Creating langchain_pg_embedding table...")
        cur.execute("""
            CREATE TABLE langchain_pg_embedding (
                id BIGSERIAL PRIMARY KEY,
                collection_id UUID REFERENCES langchain_pg_collection(uuid) ON DELETE CASCADE,
                embedding vector(1536),
                document VARCHAR,
                cmetadata JSONB,
                custom_id VARCHAR
            );
        """)
        
        # Create indexes for better performance
        logger.info("Creating indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS langchain_pg_embedding_collection_id_idx 
            ON langchain_pg_embedding(collection_id);
            
            CREATE INDEX IF NOT EXISTS langchain_pg_embedding_embedding_idx 
            ON langchain_pg_embedding USING ivfflat (embedding vector_cosine_ops);
        """)
        
        # Insert default collection
        logger.info("Creating default collection...")
        cur.execute("""
            INSERT INTO langchain_pg_collection (uuid, name, cmetadata) 
            VALUES (gen_random_uuid(), 'corpus_chunks', '{"description": "AI Tutor Corpus", "created_at": "2025-01-23"}');
        """)
        
        conn.commit()
        logger.info("✅ LangChain tables created successfully")

def populate_sample_corpus(conn):
    """Populate the corpus with sample educational content"""
    with conn.cursor() as cur:
        # Get the collection ID
        cur.execute("SELECT uuid FROM langchain_pg_collection WHERE name = 'corpus_chunks'")
        collection_id = cur.fetchone()[0]
        
        # Sample educational content for different subjects and levels
        sample_content = [
            # Math - Algebra (Class 7)
            {
                "text": "Algebra is a branch of mathematics that deals with symbols and the rules for manipulating these symbols. In algebra, we use letters like x, y, and z to represent unknown values called variables. For example, in the equation 2x + 3 = 7, x is the variable we need to solve for.",
                "metadata": {
                    "subject": "math",
                    "class": "7",
                    "topic": "algebra",
                    "chapter": "Introduction to Algebra",
                    "module": "Variables and Expressions",
                    "title": "What is Algebra?",
                    "source": "curriculum_guide",
                    "skill_ids": ["alg_001", "alg_002"]
                }
            },
            {
                "text": "Linear equations are equations where the highest power of the variable is 1. They can be written in the form ax + b = c, where a, b, and c are constants and x is the variable. To solve linear equations, we use inverse operations to isolate the variable.",
                "metadata": {
                    "subject": "math",
                    "class": "7",
                    "topic": "algebra",
                    "chapter": "Linear Equations",
                    "module": "Solving Equations",
                    "title": "Linear Equations Basics",
                    "source": "textbook",
                    "skill_ids": ["alg_003", "alg_004"]
                }
            },
            {
                "text": "A quadratic equation is an equation of the form ax² + bx + c = 0, where a, b, and c are constants and a ≠ 0. The solutions to quadratic equations can be found using the quadratic formula: x = (-b ± √(b² - 4ac)) / 2a.",
                "metadata": {
                    "subject": "math",
                    "class": "8",
                    "topic": "algebra",
                    "chapter": "Quadratic Equations",
                    "module": "Solving Quadratics",
                    "title": "Quadratic Formula",
                    "source": "curriculum_guide",
                    "skill_ids": ["alg_005", "alg_006"]
                }
            },
            # Science - Physics (Class 8)
            {
                "text": "Force is a push or pull that can change the motion of an object. Newton's First Law states that an object at rest stays at rest and an object in motion stays in motion unless acted upon by an unbalanced force. This is also known as the law of inertia.",
                "metadata": {
                    "subject": "science",
                    "class": "8",
                    "topic": "physics",
                    "chapter": "Forces and Motion",
                    "module": "Newton's Laws",
                    "title": "Newton's First Law",
                    "source": "textbook",
                    "skill_ids": ["phy_001", "phy_002"]
                }
            },
            {
                "text": "Energy is the ability to do work. There are many forms of energy including kinetic energy (energy of motion), potential energy (stored energy), thermal energy (heat), and electrical energy. Energy can be transformed from one form to another but cannot be created or destroyed.",
                "metadata": {
                    "subject": "science",
                    "class": "8",
                    "topic": "physics",
                    "chapter": "Energy",
                    "module": "Forms of Energy",
                    "title": "Types of Energy",
                    "source": "curriculum_guide",
                    "skill_ids": ["phy_003", "phy_004"]
                }
            },
            # English - Grammar (Class 7)
            {
                "text": "A noun is a word that names a person, place, thing, or idea. Common nouns name general items like 'city' or 'book', while proper nouns name specific items like 'London' or 'Harry Potter'. Nouns can be singular or plural, and they can be countable or uncountable.",
                "metadata": {
                    "subject": "english",
                    "class": "7",
                    "topic": "grammar",
                    "chapter": "Parts of Speech",
                    "module": "Nouns",
                    "title": "Understanding Nouns",
                    "source": "textbook",
                    "skill_ids": ["eng_001", "eng_002"]
                }
            },
            {
                "text": "Verbs are action words that show what someone or something is doing. They can be in different tenses (past, present, future) and can be regular or irregular. For example, 'run' is a regular verb (run, ran, run) while 'go' is irregular (go, went, gone).",
                "metadata": {
                    "subject": "english",
                    "class": "7",
                    "topic": "grammar",
                    "chapter": "Parts of Speech",
                    "module": "Verbs",
                    "title": "Verb Tenses",
                    "source": "curriculum_guide",
                    "skill_ids": ["eng_003", "eng_004"]
                }
            }
        ]
        
        logger.info(f"Inserting {len(sample_content)} sample documents...")
        
        for i, content in enumerate(sample_content):
            # For now, we'll insert with placeholder embeddings (zeros)
            # In a real scenario, these would be generated using OpenAI embeddings
            placeholder_embedding = [0.0] * 1536
            
            cur.execute("""
                INSERT INTO langchain_pg_embedding 
                (collection_id, embedding, document, cmetadata, custom_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                collection_id,
                placeholder_embedding,
                content["text"],
                json.dumps(content["metadata"]),
                f"doc_{i+1:03d}"
            ))
        
        conn.commit()
        logger.info(f"✅ Inserted {len(sample_content)} sample documents")

def main():
    """Main migration function"""
    conn = None
    try:
        logger.info("🚀 Starting migration to LangChain format...")
        
        # Connect to database
        logger.info("Connecting to PostgreSQL...")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        
        # Create new tables
        create_langchain_tables(conn)
        
        # Populate with sample data
        populate_sample_corpus(conn)
        
        logger.info("🎉 Migration completed successfully!")
        
        # Verify the data
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    c.name as collection_name,
                    COUNT(e.id) as total_embeddings
                FROM langchain_pg_collection c
                LEFT JOIN langchain_pg_embedding e ON c.uuid = e.collection_id
                GROUP BY c.uuid, c.name
            """)
            
            result = cur.fetchone()
            logger.info(f"📊 Collection: {result['collection_name']}")
            logger.info(f"📊 Total embeddings: {result['total_embeddings']}")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
