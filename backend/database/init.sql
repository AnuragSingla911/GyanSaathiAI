-- AI Tutor App Database Schema
-- PostgreSQL initialization script

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    role VARCHAR(20) DEFAULT 'student' CHECK (role IN ('student', 'admin', 'teacher')),
    grade_level INTEGER CHECK (grade_level BETWEEN 6 AND 10),
    preferred_subjects TEXT[], -- Array of subjects like ['math', 'science']
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    profile_image_url VARCHAR(500)
);

-- User preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    difficulty_level VARCHAR(20) DEFAULT 'medium' CHECK (difficulty_level IN ('easy', 'medium', 'hard', 'adaptive')),
    preferred_question_types TEXT[], -- ['multiple_choice', 'short_answer', 'problem_solving']
    study_goals TEXT,
    daily_goal_questions INTEGER DEFAULT 10,
    notifications_enabled BOOLEAN DEFAULT true,
    dark_mode BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Quizzes table (metadata about quiz sessions)
CREATE TABLE IF NOT EXISTS quizzes (
    quiz_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(200),
    subject VARCHAR(50) NOT NULL, -- 'math', 'science', etc.
    topic VARCHAR(100), -- 'algebra', 'geometry', 'physics', 'chemistry', etc.
    difficulty_level VARCHAR(20) NOT NULL,
    total_questions INTEGER NOT NULL,
    completed_questions INTEGER DEFAULT 0,
    score DECIMAL(5,2), -- Percentage score
    time_taken INTEGER, -- in seconds
    status VARCHAR(20) DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Quiz responses table (individual question responses)
CREATE TABLE IF NOT EXISTS quiz_responses (
    response_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quiz_id UUID REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    question_id VARCHAR(100) NOT NULL, -- Reference to MongoDB question document
    user_answer TEXT,
    correct_answer TEXT,
    is_correct BOOLEAN,
    time_spent INTEGER, -- in seconds
    difficulty_level VARCHAR(20),
    hints_used INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 1,
    feedback_rating INTEGER CHECK (feedback_rating BETWEEN 1 AND 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Progress tracking table
CREATE TABLE IF NOT EXISTS user_progress (
    progress_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    subject VARCHAR(50) NOT NULL,
    topic VARCHAR(100),
    skill VARCHAR(100),
    mastery_level DECIMAL(3,2) DEFAULT 0.0, -- 0.0 to 1.0
    total_questions_answered INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    average_time_per_question DECIMAL(6,2), -- in seconds
    last_practiced TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, subject, topic, skill)
);

-- Learning sessions table
CREATE TABLE IF NOT EXISTS learning_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    session_type VARCHAR(50) DEFAULT 'quiz', -- 'quiz', 'practice', 'review'
    duration INTEGER, -- in seconds
    questions_answered INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    subjects_covered TEXT[],
    topics_covered TEXT[],
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE
);

-- Achievements table
CREATE TABLE IF NOT EXISTS achievements (
    achievement_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon_url VARCHAR(500),
    criteria JSONB, -- JSON criteria for earning the achievement
    points INTEGER DEFAULT 0,
    category VARCHAR(50), -- 'streak', 'mastery', 'participation', etc.
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User achievements table
CREATE TABLE IF NOT EXISTS user_achievements (
    user_achievement_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    achievement_id UUID REFERENCES achievements(achievement_id) ON DELETE CASCADE,
    earned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    progress DECIMAL(3,2) DEFAULT 1.0, -- For progressive achievements
    UNIQUE(user_id, achievement_id)
);

-- Feedback table
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    question_id VARCHAR(100), -- Reference to MongoDB question
    quiz_id UUID REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
    feedback_type VARCHAR(50), -- 'question_quality', 'explanation_clarity', 'difficulty_rating'
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_quizzes_user_id ON quizzes(user_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_subject ON quizzes(subject);
CREATE INDEX IF NOT EXISTS idx_quizzes_status ON quizzes(status);
CREATE INDEX IF NOT EXISTS idx_quiz_responses_quiz_id ON quiz_responses(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_responses_user_id ON quiz_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_progress_user_id ON user_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_progress_subject_topic ON user_progress(subject, topic);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON learning_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_user_id ON user_achievements(user_id);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_progress_updated_at BEFORE UPDATE ON user_progress
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default achievements
INSERT INTO achievements (name, description, category, points, criteria) VALUES
('First Quiz', 'Complete your first quiz', 'participation', 10, '{"type": "quiz_completion", "count": 1}'),
('Perfect Score', 'Get 100% on any quiz', 'mastery', 50, '{"type": "perfect_score", "count": 1}'),
('Week Warrior', 'Complete quizzes for 7 consecutive days', 'streak', 100, '{"type": "daily_streak", "count": 7}'),
('Math Master', 'Answer 100 math questions correctly', 'mastery', 200, '{"type": "correct_answers", "subject": "math", "count": 100}'),
('Science Scholar', 'Answer 100 science questions correctly', 'mastery', 200, '{"type": "correct_answers", "subject": "science", "count": 100}'),
('Speed Demon', 'Answer 10 questions in under 5 minutes', 'performance', 75, '{"type": "speed_completion", "questions": 10, "time_limit": 300}'),
('Persistent Learner', 'Complete 50 quizzes', 'participation', 300, '{"type": "quiz_completion", "count": 50}')
ON CONFLICT DO NOTHING;

-- Create a sample admin user (password: admin123)
INSERT INTO users (username, email, password_hash, first_name, last_name, role, is_active, email_verified)
VALUES (
    'admin',
    'admin@tutor.app',
    '$2a$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', -- bcrypt hash of 'admin123'
    'Admin',
    'User',
    'admin',
    true,
    true
) ON CONFLICT (email) DO NOTHING;