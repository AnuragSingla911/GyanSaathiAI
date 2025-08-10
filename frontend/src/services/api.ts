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
  timeout: 10000,
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
      totalQuizzes: number;
      totalQuestions: number;
      correctAnswers: number;
      averageScore: number;
      totalTimeSpent: number;
      currentStreak: number;
      bestStreak: number;
    };
    bySubject: Record<string, {
      totalQuestions: number;
      correctAnswers: number;
      averageScore: number;
      masteryLevel: number;
    }>;
    byTopic: Record<string, {
      subject: string;
      totalQuestions: number;
      correctAnswers: number;
      masteryLevel: number;
      lastPracticed: string;
    }>;
    recentActivity: Array<{
      date: string;
      quizzes: number;
      questions: number;
      correctAnswers: number;
    }>;
  }> => {
    const response = await api.get(`/progress/user/${userId}`);
    return response.data.data;
  },

  getAnalytics: async (userId: string, timeframe: 'week' | 'month' | 'year' = 'month'): Promise<{
    performance: Array<{
      date: string;
      score: number;
      questionsAnswered: number;
      timeSpent: number;
    }>;
    subjectBreakdown: Array<{
      subject: string;
      questionsAnswered: number;
      correctAnswers: number;
      averageScore: number;
    }>;
    difficultyProgression: Array<{
      difficulty: string;
      questionsAnswered: number;
      correctAnswers: number;
      averageScore: number;
    }>;
    achievements: Array<{
      name: string;
      description: string;
      earnedAt: string;
      points: number;
    }>;
  }> => {
    const response = await api.get(`/progress/analytics/${userId}`, {
      params: { timeframe },
    });
    return response.data.data;
  },
};

export default api;