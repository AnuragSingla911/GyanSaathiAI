export interface QuizQuestion {
  question_id: string;
  question_text: string;
  question_type: 'multiple_choice' | 'short_answer' | 'true_false' | 'fill_in_blank' | 'problem_solving';
  subject: string;
  topic: string;
  difficulty_level: 'easy' | 'medium' | 'hard';
  grade_level: number;
  options?: QuestionOption[];
  hints?: string[];
  keywords?: string[];
  learning_objectives?: string[];
  created_at: string;
}

export interface QuestionOption {
  label: string;
  text: string;
}

export interface Quiz {
  quiz_id: string;
  title: string;
  subject: string;
  topic: string;
  difficulty_level: string;
  total_questions: number;
  completed_questions: number;
  score?: number;
  time_taken?: number;
  status: 'in_progress' | 'completed' | 'abandoned';
  started_at: string;
  completed_at?: string;
  questions: QuizQuestion[];
}

export interface QuizResponse {
  response_id: string;
  quiz_id: string;
  question_id: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  time_spent: number;
  hints_used: number;
  attempts: number;
  created_at: string;
}

export interface QuizSettings {
  subject: string;
  topic?: string;
  difficulty_level: 'easy' | 'medium' | 'hard' | 'adaptive';
  question_count: number;
  question_types?: string[];
  time_limit?: number;
}

export interface Explanation {
  explanation_id: string;
  summary: string;
  detailed_steps: ExplanationStep[];
  explanation_type: string;
  learning_style?: string;
  visual_aids?: string[];
  common_mistakes?: CommonMistake[];
  related_concepts?: string[];
  created_at: string;
}

export interface ExplanationStep {
  step_number: number;
  description: string;
  mathematical_expression?: string;
  visual_aid_url?: string;
}

export interface CommonMistake {
  mistake_description: string;
  explanation: string;
  remediation_steps: string[];
}

export interface Feedback {
  feedback_id: string;
  feedback_type: string;
  message: string;
  suggestions?: string[];
  next_steps?: string[];
  confidence_score?: number;
  created_at: string;
}