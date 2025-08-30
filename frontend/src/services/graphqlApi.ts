import { useMutation, useQuery } from '@apollo/client';

import { 
  AuthResponse, 
  LoginCredentials, 
  RegisterData, 
  User 
} from '../types/auth';

// Import GraphQL operations
import {
  LOGIN_USER,
  REGISTER_USER,
  GET_CURRENT_USER,
  UPDATE_PROFILE,
  CHANGE_PASSWORD,
  LOGOUT_USER,
  GET_QUESTIONS,
  GET_QUESTION,
  CREATE_QUESTION,
  UPDATE_QUESTION,
  PROMOTE_QUESTION,
  RETIRE_QUESTION,
  START_QUIZ_ATTEMPT,
  SAVE_ANSWER,
  SUBMIT_QUIZ_ATTEMPT,
  GET_USER_PROGRESS,
  GET_PROGRESS,
  GET_ANALYTICS,
  GET_EXPLANATION,
  SUBMIT_FEEDBACK,
} from '../graphql/operations';

// Auth API hooks
export const useAuthAPI = () => {
  const [loginMutation, { loading: loginLoading }] = useMutation(LOGIN_USER);
  const [registerMutation, { loading: registerLoading }] = useMutation(REGISTER_USER);
  const [updateProfileMutation, { loading: updateProfileLoading }] = useMutation(UPDATE_PROFILE);
  const [changePasswordMutation, { loading: changePasswordLoading }] = useMutation(CHANGE_PASSWORD);
  const [logoutMutation, { loading: logoutLoading }] = useMutation(LOGOUT_USER);

  const login = async (credentials: LoginCredentials): Promise<AuthResponse['data']> => {
    try {
      const { data } = await loginMutation({
        variables: { input: credentials }
      });
      
      if (data?.login?.token) {
        localStorage.setItem('token', data.login.token);
      }
      
      return data.login;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  };

  const register = async (userData: RegisterData): Promise<AuthResponse['data']> => {
    try {
      const { data } = await registerMutation({
        variables: { input: userData }
      });
      
      if (data?.register?.token) {
        localStorage.setItem('token', data.register.token);
      }
      
      return data.register;
    } catch (error) {
      console.error('Registration error:', error);
      throw error;
    }
  };

  const getCurrentUser = () => {
    return useQuery(GET_CURRENT_USER, {
      fetchPolicy: 'cache-and-network',
      errorPolicy: 'all'
    });
  };

  const updateProfile = async (profileData: Partial<User>): Promise<AuthResponse['data']> => {
    try {
      const { data } = await updateProfileMutation({
        variables: { input: profileData }
      });
      return { user: data.updateProfile, token: localStorage.getItem('token') || '' };
    } catch (error) {
      console.error('Profile update error:', error);
      throw error;
    }
  };

  const changePassword = async (passwordData: { currentPassword: string; newPassword: string }): Promise<void> => {
    try {
      await changePasswordMutation({
        variables: { input: passwordData }
      });
    } catch (error) {
      console.error('Password change error:', error);
      throw error;
    }
  };

  const logout = async (): Promise<void> => {
    try {
      await logoutMutation();
    } catch (error) {
      // Even if logout fails on server, continue
      console.error('Logout error:', error);
    }
  };

  return {
    login,
    register,
    getCurrentUser,
    updateProfile,
    changePassword,
    logout,
    loading: {
      login: loginLoading,
      register: registerLoading,
      updateProfile: updateProfileLoading,
      changePassword: changePasswordLoading,
      logout: logoutLoading
    }
  };
};

// Quiz API hooks
export const useQuizAPI = () => {
  const [startQuizAttemptMutation, { loading: startQuizLoading }] = useMutation(START_QUIZ_ATTEMPT);
  const [saveAnswerMutation, { loading: saveAnswerLoading }] = useMutation(SAVE_ANSWER);
  const [submitQuizAttemptMutation, { loading: submitQuizLoading }] = useMutation(SUBMIT_QUIZ_ATTEMPT);

  const startQuizAttempt = async (data: {
    subject: string;
    topic?: string;
    totalQuestions?: number;
    timeLimitSeconds?: number;
    skillFilters?: string[];
  }) => {
    try {
      const { data: result } = await startQuizAttemptMutation({
        variables: { input: data }
      });
      return result.startQuizAttempt;
    } catch (error) {
      console.error('Start quiz error:', error);
      throw error;
    }
  };

  const saveAnswer = async (
    attemptId: string,
    itemId: string,
    data: {
      answer: string;
      timeSpent?: number;
      hintsUsed?: number;
    },
    idempotencyKey?: string
  ) => {
    try {
      const { data: result } = await saveAnswerMutation({
        variables: {
          attemptId,
          itemId,
          input: data,
          idempotencyKey
        }
      });
      return result.saveAnswer;
    } catch (error) {
      console.error('Save answer error:', error);
      throw error;
    }
  };

  const submitQuizAttempt = async (attemptId: string) => {
    try {
      const { data: result } = await submitQuizAttemptMutation({
        variables: { attemptId }
      });
      return result.submitQuizAttempt;
    } catch (error) {
      console.error('Submit quiz error:', error);
      throw error;
    }
  };

  return {
    startQuizAttempt,
    saveAnswer,
    submitQuizAttempt,
    loading: {
      startQuiz: startQuizLoading,
      saveAnswer: saveAnswerLoading,
      submitQuiz: submitQuizLoading
    }
  };
};

// Question API hooks
export const useQuestionAPI = () => {
  const [createQuestionMutation, { loading: createQuestionLoading }] = useMutation(CREATE_QUESTION);
  const [updateQuestionMutation, { loading: updateQuestionLoading }] = useMutation(UPDATE_QUESTION);
  const [promoteQuestionMutation, { loading: promoteQuestionLoading }] = useMutation(PROMOTE_QUESTION);
  const [retireQuestionMutation, { loading: retireQuestionLoading }] = useMutation(RETIRE_QUESTION);

  const getQuestions = (variables: {
    subject?: string;
    topic?: string;
    difficulty?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }) => {
    return useQuery(GET_QUESTIONS, {
      variables,
      fetchPolicy: 'cache-and-network',
      errorPolicy: 'all'
    });
  };

  const getQuestion = (id: string) => {
    return useQuery(GET_QUESTION, {
      variables: { id },
      fetchPolicy: 'cache-and-network',
      errorPolicy: 'all'
    });
  };

  const createQuestion = async (input: any) => {
    try {
      const { data } = await createQuestionMutation({
        variables: { input }
      });
      return data.createQuestion;
    } catch (error) {
      console.error('Create question error:', error);
      throw error;
    }
  };

  const updateQuestion = async (id: string, input: any) => {
    try {
      const { data } = await updateQuestionMutation({
        variables: { id, input }
      });
      return data.updateQuestion;
    } catch (error) {
      console.error('Update question error:', error);
      throw error;
    }
  };

  const promoteQuestion = async (id: string) => {
    try {
      const { data } = await promoteQuestionMutation({
        variables: { id }
      });
      return data.promoteQuestion;
    } catch (error) {
      console.error('Promote question error:', error);
      throw error;
    }
  };

  const retireQuestion = async (id: string) => {
    try {
      const { data } = await retireQuestionMutation({
        variables: { id }
      });
      return data.retireQuestion;
    } catch (error) {
      console.error('Retire question error:', error);
      throw error;
    }
  };

  return {
    getQuestions,
    getQuestion,
    createQuestion,
    updateQuestion,
    promoteQuestion,
    retireQuestion,
    loading: {
      createQuestion: createQuestionLoading,
      updateQuestion: updateQuestionLoading,
      promoteQuestion: promoteQuestionLoading,
      retireQuestion: retireQuestionLoading
    }
  };
};

// Progress API hooks
export const useProgressAPI = () => {
  const getUserProgress = (userId: string, scope?: string) => {
    return useQuery(GET_USER_PROGRESS, {
      variables: { userId, scope },
      fetchPolicy: 'cache-and-network',
      errorPolicy: 'all'
    });
  };

  const getProgress = (userId: string) => {
    return useQuery(GET_PROGRESS, {
      variables: { userId },
      fetchPolicy: 'cache-and-network',
      errorPolicy: 'all'
    });
  };

  const getAnalytics = (userId: string, timeframe: 'week' | 'month' | 'year' = 'month') => {
    return useQuery(GET_ANALYTICS, {
      variables: { userId, timeframe },
      fetchPolicy: 'cache-and-network',
      errorPolicy: 'all'
    });
  };

  return {
    getUserProgress,
    getProgress,
    getAnalytics
  };
};

// Content API hooks
export const useContentAPI = () => {
  const [submitFeedbackMutation, { loading: submitFeedbackLoading }] = useMutation(SUBMIT_FEEDBACK);

  const getExplanation = (questionId: string, studentAnswer?: string) => {
    return useQuery(GET_EXPLANATION, {
      variables: { questionId, studentAnswer },
      fetchPolicy: 'cache-and-network',
      errorPolicy: 'all'
    });
  };

  const submitFeedback = async (data: {
    questionId: string;
    quizId?: string;
    feedbackType: string;
    rating: number;
    comments?: string;
  }) => {
    try {
      await submitFeedbackMutation({
        variables: { input: data }
      });
    } catch (error) {
      console.error('Submit feedback error:', error);
      throw error;
    }
  };

  return {
    getExplanation,
    submitFeedback,
    loading: {
      submitFeedback: submitFeedbackLoading
    }
  };
};
