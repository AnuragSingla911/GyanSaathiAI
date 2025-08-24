-- Migration to add embeddings column for pgvector support
-- This migration adds the necessary column for storing OpenAI embeddings

-- Add embeddings column to corpus_chunks table
ALTER TABLE corpus_chunks 
ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Create index on embeddings for similarity search
CREATE INDEX IF NOT EXISTS idx_corpus_chunks_embedding 
ON corpus_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Add metadata columns for better filtering
ALTER TABLE corpus_chunks 
ADD COLUMN IF NOT EXISTS subject VARCHAR(50),
ADD COLUMN IF NOT EXISTS class_level VARCHAR(50),
ADD COLUMN IF NOT EXISTS chapter VARCHAR(100),
ADD COLUMN IF NOT EXISTS module VARCHAR(100);

-- Create indexes for metadata filtering
CREATE INDEX IF NOT EXISTS idx_corpus_chunks_subject ON corpus_chunks(subject);
CREATE INDEX IF NOT EXISTS idx_corpus_chunks_class ON corpus_chunks(class_level);
CREATE INDEX IF NOT EXISTS idx_corpus_chunks_chapter ON corpus_chunks(chapter);
CREATE INDEX IF NOT EXISTS idx_corpus_chunks_module ON corpus_chunks(module);
