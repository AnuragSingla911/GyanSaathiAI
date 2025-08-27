import axios, { AxiosResponse } from 'axios';
import toast from 'react-hot-toast';

import { 
  AuthResponse, 
  LoginCredentials, 
  RegisterData, 
  User 
} from '../types/auth';
import { 
  Quiz, 
  QuizSettings, 
  QuizResponse, 
  Explanation, 
  Feedback 
} from '../types/quiz';

// Create axios instance
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 30000, // Increased from 10000 to 30000 (30 seconds)
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('token');
      window.location.href = '/login';
    } else if (error.response?.status >= 500) {
      toast.error('Server error. Please try again later.');
    } else if (error.code === 'ECONNABORTED') {
      toast.error('Request timeout. Please check your connection.');
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse['data']> => {
    const response: AxiosResponse<AuthResponse> = await api.post('/auth/login', credentials);
    return response.data.data;
  },

  register: async (data: RegisterData): Promise<AuthResponse['data']> => {
    const response: AxiosResponse<AuthResponse> = await api.post('/auth/register', data);
    return response.data.data;
  },

  getCurrentUser: async (): Promise<AuthResponse['data']> => {
    const response: AxiosResponse<AuthResponse> = await api.get('/auth/me');
    return response.data.data;
  },

  updateProfile: async (data: Partial<User>): Promise<AuthResponse['data']> => {
    const response: AxiosResponse<AuthResponse> = await api.put('/auth/profile', data);
    return response.data.data;
  },

  changePassword: async (data: { currentPassword: string; newPassword: string }): Promise<void> => {
    await api.put('/auth/change-password', data);
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },
};

// Quiz API
export const quizAPI = {
  // V1 API methods
  startQuizAttempt: async (data: {
    subject: string;
    topic?: string;
    totalQuestions?: number;
    timeLimitSeconds?: number;
    skillFilters?: string[];
  }): Promise<{
    attemptId: string;
    subject: string;
    topic?: string;
    totalQuestions: number;
    timeLimitSeconds?: number;
    startedAt: string;
  }> => {
    const response = await api.post('/v1/quiz-attempts', data);
    return response.data.data;
  },

  getQuizAttempt: async (attemptId: string): Promise<{
    attempt: any;
    items: any[];
  }> => {
    const response = await api.get(`/v1/quiz-attempts/${attemptId}`);
    return response.data.data;
  },

  saveAnswer: async (
    attemptId: string,
    itemId: string,
    data: {
      answer: string;
      timeSpent?: number;
      hintsUsed?: number;
    },
    idempotencyKey?: string
  ): Promise<{
    isCorrect: boolean;
    score: number;
    correctAnswer?: string;
  }> => {
    const headers = idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {};
    const response = await api.put(`/v1/quiz-attempts/${attemptId}/items/${itemId}`, data, { headers });
    return response.data.data;
  },

  submitQuizAttempt: async (attemptId: string): Promise<{
    finalScore: number;
    answeredQuestions: number;
    totalQuestions: number;
  }> => {
    const response = await api.post(`/v1/quiz-attempts/${attemptId}/submit`);
    return response.data.data;
  },

  // Legacy compatibility methods
  createQuiz: async (settings: QuizSettings): Promise<Quiz> => {
    const response = await api.post('/content/generate-quiz', settings);
    return response.data.data;
  },

  getQuiz: async (quizId: string): Promise<Quiz> => {
    const response = await api.get(`/quizzes/${quizId}`);
    return response.data.data;
  },

  getUserQuizzes: async (userId: string): Promise<Quiz[]> => {
    const response = await api.get(`/quizzes?userId=${userId}`);
    return response.data.data;
  },

  submitAnswer: async (data: {
    quizId: string;
    questionId: string;
    answer: string;
    timeSpent: number;
    hintsUsed: number;
  }): Promise<{
    isCorrect: boolean;
    correctAnswer: string;
    explanation?: Explanation;
    feedback?: Feedback;
  }> => {
    const response = await api.post('/quizzes/submit-answer', data);
    return response.data.data;
  },

  completeQuiz: async (quizId: string): Promise<Quiz> => {
    const response = await api.post(`/quizzes/${quizId}/complete`);
    return response.data.data;
  },

  getQuizResults: async (quizId: string): Promise<{
    quiz: Quiz;
    responses: QuizResponse[];
    analytics: {
      totalTime: number;
      averageTimePerQuestion: number;
      correctAnswers: number;
      incorrectAnswers: number;
      hintsUsed: number;
      score: number;
    };
  }> => {
    const response = await api.get(`/quizzes/${quizId}/results`);
    return response.data.data;
  },

  getQuestions: async (params: {
    subject?: string;
    topic?: string;
    difficulty?: string;
    limit?: number;
  }): Promise<any[]> => {
    const response = await api.get('/quizzes/questions', { params });
    return response.data.questions;
  },
};

// Content API
export const contentAPI = {
  getExplanation: async (questionId: string, studentAnswer?: string): Promise<Explanation> => {
    const response = await api.get(`/content/explanation/${questionId}`, {
      params: { studentAnswer },
    });
    return response.data.data;
  },

  submitFeedback: async (data: {
    questionId: string;
    quizId?: string;
    feedbackType: string;
    rating: number;
    comments?: string;
  }): Promise<void> => {
    await api.post('/content/feedback', data);
  },

  getQuestions: async (params: {
    subject?: string;
    topic?: string;
    difficulty?: string;
    questionType?: string;
    limit?: number;
  }): Promise<any[]> => {
    const response = await api.get('/content/questions', { params });
    return response.data.data;
  },
};

// Progress API
export const progressAPI = {
  getUserProgress: async (userId: string): Promise<{
    overall: {
      totalSkills: number;
      totalQuestions: number;
      totalCorrect: number;
      averageMastery: number;
      currentStreak: number;
      bestStreak: number;
      totalAttempts: number;
      completedAttempts: number;
      averageScore: number;
    };
    progress: {
      bySubject?: Record<string, {
        skillsCount: number;
        totalQuestions: number;
        correctAnswers: number;
        averageMastery: number;
        accuracy: number;
      }>;
      byTopic?: Record<string, {
        subject: string;
        topic: string;
        skillsCount: number;
        totalQuestions: number;
        correctAnswers: number;
        averageMastery: number;
        lastPracticed: string;
      }>;
      bySkill?: Array<{
        subject: string;
        topic: string;
        skill: string;
        totalQuestions: number;
        correctAnswers: number;
        masteryLevel: number;
        currentStreak: number;
        bestStreak: number;
        lastUpdated: string;
      }>;
    };
    recentActivity: Array<{
      date: string;
      attempts: number;
      questionsAnswered: number;
      accuracy: number;
    }>;
  }> => {
    const response = await api.get(`/v1/progress/${userId}/progress`);
    // The backend returns { success: true, data: {...} }
    // We need to return the data part directly
    return response.data.data;
  },

  getAnalytics: async (userId: string, timeframe: 'week' | 'month' | 'year' = 'month'): Promise<{
    timeframe: string;
    performance: Array<{
      date: string;
      accuracy: number;
      questionsAnswered: number;
      totalTimeMinutes: number;
    }>;
    subjectBreakdown: Array<{
      subject: string;
      questionsAnswered: number;
      correctAnswers: number;
      accuracy: number;
    }>;
    difficultyProgression: Array<{
      difficulty: string;
      questionsAnswered: number;
      correctAnswers: number;
      accuracy: number;
    }>;
  }> => {
    const response = await api.get(`/v1/progress/${userId}/analytics`, {
      params: { timeframe },
    });
    return response.data.data;
  },
};

export default api;