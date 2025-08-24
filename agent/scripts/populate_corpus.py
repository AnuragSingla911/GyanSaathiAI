#!/usr/bin/env python3
"""
Script to populate the RAG corpus with sample educational content
This creates a foundation for AI-powered question generation
"""

import asyncio
import psycopg2
import json
import hashlib
from typing import List, Dict, Any
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'postgres',  # Use Docker container hostname
    'port': 5432,
    'database': 'tutor_db',
    'user': 'tutor_user',
    'password': 'tutor_password'
}

# Sample syllabus content for different subjects and classes
SAMPLE_CORPUS = {
    "math": {
        6: {
            "arithmetic": [
                {
                    "title": "Basic Operations",
                    "content": "Addition, subtraction, multiplication, and division are the four basic operations in arithmetic. Addition combines numbers, subtraction finds differences, multiplication is repeated addition, and division is sharing or grouping.",
                    "skills": ["basic_operations", "number_sense", "mental_math"]
                },
                {
                    "title": "Fractions and Decimals",
                    "content": "Fractions represent parts of a whole, written as a/b where a is numerator and b is denominator. Decimals are fractions with denominators of powers of 10. Converting between them helps in calculations.",
                    "skills": ["fractions", "decimals", "conversion", "comparison"]
                },
                {
                    "title": "Factors and Multiples",
                    "content": "Factors are numbers that divide another number exactly. Multiples are numbers that are products of a given number. Understanding factors helps in simplifying fractions and finding common denominators.",
                    "skills": ["factors", "multiples", "prime_numbers", "factorization"]
                }
            ],
            "geometry": [
                {
                    "title": "Basic Shapes",
                    "content": "Basic geometric shapes include triangles, quadrilaterals, circles, and polygons. Triangles have three sides, quadrilaterals have four sides. Understanding properties helps in classification and measurement.",
                    "skills": ["geometric_shapes", "properties", "classification", "measurement"]
                },
                {
                    "title": "Perimeter and Area",
                    "content": "Perimeter is the total distance around a shape, calculated by adding all side lengths. Area is the space inside a shape, measured in square units. Different formulas apply to different shapes.",
                    "skills": ["perimeter", "area", "formulas", "measurement"]
                }
            ]
        },
        7: {
            "algebra": [
                {
                    "title": "Introduction to Variables",
                    "content": "Variables are symbols (usually letters) that represent unknown values. They allow us to write general rules and solve problems with unknown quantities. Basic operations work the same way with variables.",
                    "skills": ["variables", "algebraic_expressions", "substitution", "evaluation"]
                },
                {
                    "title": "Linear Equations",
                    "content": "Linear equations have variables with power 1 and can be solved using inverse operations. The goal is to isolate the variable on one side. Solutions can be verified by substitution.",
                    "skills": ["linear_equations", "solving", "inverse_operations", "verification"]
                }
            ],
            "geometry": [
                {
                    "title": "Angles and Lines",
                    "content": "Angles are formed when two lines meet. They are measured in degrees. Parallel lines never meet, perpendicular lines form right angles. Understanding angles helps in geometric proofs.",
                    "skills": ["angles", "lines", "parallel", "perpendicular", "measurement"]
                }
            ]
        }
    },
    "science": {
        6: {
            "physics": [
                {
                    "title": "Motion and Force",
                    "content": "Motion is the change in position of an object over time. Force is a push or pull that can cause motion or change in motion. Newton's laws describe how forces affect motion.",
                    "skills": ["motion", "force", "newton_laws", "measurement"]
                },
                {
                    "title": "Energy and Work",
                    "content": "Energy is the ability to do work. Work is done when a force moves an object. Different forms of energy include kinetic, potential, thermal, and electrical energy.",
                    "skills": ["energy", "work", "energy_forms", "conservation"]
                }
            ],
            "chemistry": [
                {
                    "title": "Matter and Its Properties",
                    "content": "Matter is anything that has mass and takes up space. Properties include physical properties (color, density) and chemical properties (reactivity). Matter exists in solid, liquid, and gas states.",
                    "skills": ["matter", "properties", "states", "classification"]
                },
                {
                    "title": "Atoms and Elements",
                    "content": "Atoms are the smallest units of elements. Elements are pure substances made of one type of atom. The periodic table organizes elements by their properties and atomic structure.",
                    "skills": ["atoms", "elements", "periodic_table", "atomic_structure"]
                }
            ]
        },
        7: {
            "biology": [
                {
                    "title": "Cell Structure",
                    "content": "Cells are the basic units of life. They contain organelles that perform specific functions. Plant and animal cells have similarities and differences in their structures.",
                    "skills": ["cells", "organelles", "structure", "function", "comparison"]
                },
                {
                    "title": "Living Systems",
                    "content": "Living systems are organized from cells to tissues to organs to organ systems. Each level has specific functions that contribute to the survival of the organism.",
                    "skills": ["organization", "systems", "hierarchy", "function"]
                }
            ]
        }
    }
}

# Sample skills for different subjects
SAMPLE_SKILLS = [
    # Math skills
    {"skill_id": "basic_operations", "name": "Basic Arithmetic Operations", "description": "Addition, subtraction, multiplication, division", "subject": "math", "class_level": 6, "difficulty_level": "easy"},
    {"skill_id": "fractions", "name": "Understanding Fractions", "description": "Working with fractions and their operations", "subject": "math", "class_level": 6, "difficulty_level": "medium"},
    {"skill_id": "variables", "name": "Introduction to Variables", "description": "Understanding and working with algebraic variables", "subject": "math", "class_level": 7, "difficulty_level": "medium"},
    {"skill_id": "linear_equations", "name": "Solving Linear Equations", "description": "Solving equations with one variable", "subject": "math", "class_level": 7, "difficulty_level": "medium"},
    
    # Science skills
    {"skill_id": "motion", "name": "Understanding Motion", "description": "Basic concepts of motion and forces", "subject": "science", "class_level": 6, "difficulty_level": "easy"},
    {"skill_id": "energy", "name": "Energy Concepts", "description": "Understanding different forms of energy", "subject": "science", "class_level": 6, "difficulty_level": "medium"},
    {"skill_id": "matter", "name": "Properties of Matter", "description": "Understanding matter and its states", "subject": "science", "class_level": 6, "difficulty_level": "easy"},
    {"skill_id": "cells", "name": "Cell Biology", "description": "Understanding cell structure and function", "subject": "science", "class_level": 7, "difficulty_level": "medium"},
]

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

def create_content_hash(content: str) -> str:
    """Create SHA256 hash of content"""
    return hashlib.sha256(content.encode()).hexdigest()

def insert_skills(conn, skills: List[Dict[str, Any]]):
    """Insert skills into the database"""
    cursor = conn.cursor()
    
    for skill in skills:
        try:
            cursor.execute("""
                INSERT INTO skills (skill_id, name, description, subject, class_level, difficulty_level)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (skill_id) DO NOTHING
            """, (
                skill["skill_id"],
                skill["name"],
                skill["description"],
                skill["subject"],
                skill["class_level"],
                skill["difficulty_level"]
            ))
        except Exception as e:
            logger.error(f"Failed to insert skill {skill['skill_id']}: {e}")
    
    conn.commit()
    cursor.close()
    logger.info(f"Inserted {len(skills)} skills")

def insert_corpus_documents(conn, corpus_data: Dict[str, Any]):
    """Insert corpus documents and chunks"""
    cursor = conn.cursor()
    
    for subject, classes in corpus_data.items():
        for class_level, topics in classes.items():
            for topic, documents in topics.items():
                for doc in documents:
                    try:
                        # Insert document
                        cursor.execute("""
                            INSERT INTO corpus_documents (subject, class, chapter, title, source, content_hash)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING doc_id
                        """, (
                            subject,
                            class_level,
                            topic,
                            doc["title"],
                            "Sample Curriculum",
                            create_content_hash(doc["content"])
                        ))
                        
                        doc_id = cursor.fetchone()[0]
                        
                        # Insert chunk (without embedding for now)
                        cursor.execute("""
                            INSERT INTO corpus_chunks (doc_id, text, skill_ids, chunk_index)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            doc_id,
                            doc["content"],
                            doc["skills"],
                            0
                        ))
                        
                        logger.info(f"Inserted document: {doc['title']} ({subject}, Class {class_level})")
                        
                    except Exception as e:
                        logger.error(f"Failed to insert document {doc['title']}: {e}")
    
    conn.commit()
    cursor.close()
    logger.info("Corpus documents and chunks inserted")

def main():
    """Main function to populate the corpus"""
    logger.info("Starting corpus population...")
    
    conn = None
    try:
        conn = get_db_connection()
        
        # Insert skills first
        logger.info("Inserting skills...")
        insert_skills(conn, SAMPLE_SKILLS)
        
        # Insert corpus documents and chunks
        logger.info("Inserting corpus documents...")
        insert_corpus_documents(conn, SAMPLE_CORPUS)
        
        logger.info("✅ Corpus population completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to populate corpus: {e}")
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
