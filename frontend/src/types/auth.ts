export interface User {
  id: string;
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  role: 'student' | 'admin' | 'teacher';
  gradeLevel: number;
  emailVerified: boolean;
  preferences?: UserPreferences;
  createdAt: string;
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
  username: string;
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  gradeLevel: number;
  preferredSubjects?: string[];
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