export interface User {
  user_id: string;
  email: string;
  role: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface UserPreferences {
  difficultyLevel: 'easy' | 'medium' | 'hard' | 'adaptive';
  preferredQuestionTypes: string[];
  studyGoals?: string;
  dailyGoalQuestions: number;
  notificationsEnabled: boolean;
  darkMode: boolean;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  confirmPassword: string;
}

export interface AuthResponse {
  success: boolean;
  message: string;
  data: {
    token: string;
    user: User;
  };
}

export interface ApiError {
  success: false;
  error: string;
  message?: string;
}