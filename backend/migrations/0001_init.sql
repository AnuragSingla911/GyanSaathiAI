-- Idempotent: create extensions/tables if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- users
CREATE TABLE IF NOT EXISTS users (
  user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(100) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  first_name VARCHAR(50),
  last_name VARCHAR(50),
  role VARCHAR(20) NOT NULL DEFAULT 'student' CHECK (role IN ('student','parent','teacher','admin')),
  grade_level INT,
  is_active BOOLEAN DEFAULT TRUE,
  email_verified BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- consents
CREATE TABLE IF NOT EXISTS consents (
  consent_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  granted_by VARCHAR(50),
  method VARCHAR(50),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- quiz_attempts
CREATE TABLE IF NOT EXISTS quiz_attempts (
  attempt_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  subject VARCHAR(50) NOT NULL,
  topic VARCHAR(100),
  total_questions INT NOT NULL,
  seed INT,
  status VARCHAR(20) NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress','completed','abandoned')),
  time_limit_seconds INT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_attempts_user_started ON quiz_attempts(user_id, started_at);

-- attempt_items
CREATE TABLE IF NOT EXISTS attempt_items (
  item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  attempt_id UUID NOT NULL REFERENCES quiz_attempts(attempt_id) ON DELETE CASCADE,
  ordinal INT NOT NULL,
  question_id TEXT NOT NULL,
  question_version INT NOT NULL,
  shown_payload JSONB NOT NULL,
  answer_payload JSONB,
  is_correct BOOLEAN,
  score NUMERIC(5,2),
  hints_used INT DEFAULT 0,
  attempts INT DEFAULT 1,
  responded_at TIMESTAMPTZ,
  UNIQUE (attempt_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_items_qid_qv ON attempt_items(question_id, question_version);

-- progress_summary
CREATE TABLE IF NOT EXISTS progress_summary (
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  subject VARCHAR(50) NOT NULL,
  topic VARCHAR(100),
  skill VARCHAR(100),
  mastery_level NUMERIC(4,2) NOT NULL DEFAULT 0.0,
  total_questions_answered INT NOT NULL DEFAULT 0,
  correct_answers INT NOT NULL DEFAULT 0,
  current_streak INT NOT NULL DEFAULT 0,
  best_streak INT NOT NULL DEFAULT 0,
  last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, subject, topic, skill)
);

-- rag corpus
CREATE TABLE IF NOT EXISTS corpus_documents (
  doc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  subject VARCHAR(50),
  class VARCHAR(50),
  chapter VARCHAR(100),
  module VARCHAR(100),
  title VARCHAR(200),
  source VARCHAR(100),
  license VARCHAR(50),
  content_hash VARCHAR(64),
  uri TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS corpus_chunks (
  chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  doc_id UUID NOT NULL REFERENCES corpus_documents(doc_id) ON DELETE CASCADE,
  ordinal INT NOT NULL,
  text TEXT NOT NULL,
  token_count INT,
  skill_ids TEXT[],
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_ordinal ON corpus_chunks(doc_id, ordinal);
