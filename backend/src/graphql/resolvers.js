const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { v4: uuidv4 } = require('uuid');

// Import existing services and models
const { connectPostgres } = require('../utils/database');
const { connectMongoDB } = require('../utils/mongodb');
const { connectRedis } = require('../utils/redis');

// Import the Question model
const VersionedQuestion = require('../models/question');

// Import services
const quizService = require('../services/quizService');
const progressService = require('../services/progressService');
const userService = require('../services/userService');

// Database connection instances
let postgresClient = null;
let mongoClient = null;
let redisClient = null;

// Initialize database connections
async function initDB() {
  try {
    postgresClient = await connectPostgres();
    mongoClient = await connectMongoDB();
    redisClient = await connectRedis();
    console.log('GraphQL: Database connections initialized');
  } catch (error) {
    console.error('GraphQL: Failed to initialize database connections:', error);
  }
}

// Initialize connections on startup
initDB();

const resolvers = {
  Query: {
    // Auth queries
    me: async (_, __, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        return await userService.getCurrentUser(user.user_id);
      } catch (error) {
        console.error('GraphQL: Error getting current user:', error);
        throw new Error('Failed to get user data');
      }
    },

    // Question queries
    questions: async (_, { subject, topic, difficulty, status, limit = 50, offset = 0 }) => {
      try {
        // Build filter object
        const filter = {};
        if (subject) filter.subject = subject;
        if (topic) filter.topic = topic;
        if (difficulty) filter.difficulty = difficulty;
        if (status) filter.status = status;
        
        // Query MongoDB for real questions
        const questions = await VersionedQuestion.find(filter)
          .limit(limit)
          .skip(offset)
          .lean();
        
        // Transform to match GraphQL schema
        return questions.map(q => ({
          id: q._id.toString(),
          version: q.version,
          status: q.status,
          subject: q.subject,
          topic: q.topic,
          difficulty: q.difficulty || 'medium',
          stem: q.content?.stem || q.stem,
          options: q.content?.options || [],
          correctOptionIds: q.content?.correctOptionIds || [],
          canonicalSolution: q.content?.canonicalSolution,
          unit: q.content?.unit,
          tags: q.tags || []
        }));
      } catch (error) {
        console.error('GraphQL: Error fetching questions:', error);
        throw new Error('Failed to fetch questions');
      }
    },

    question: async (_, { id }) => {
      try {
        const question = await VersionedQuestion.findById(id).lean();
        if (!question) return null;
        
        return {
          id: question._id.toString(),
          version: question.version,
          status: question.status,
          subject: question.subject,
          topic: question.topic,
          difficulty: question.difficulty || 'medium',
          stem: question.content?.stem || question.stem,
          options: question.content?.options || [],
          correctOptionIds: question.content?.correctOptionIds || [],
          canonicalSolution: question.content?.canonicalSolution,
          unit: question.content?.unit,
          tags: question.tags || []
        };
      } catch (error) {
        console.error('GraphQL: Error fetching question:', error);
        throw new Error('Failed to fetch question');
      }
    },

    // Quiz attempt queries
    quizAttempt: async (_, { attemptId }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        return await quizService.getQuizAttempt(attemptId, user.user_id);
      } catch (error) {
        console.error('GraphQL: Error fetching quiz attempt:', error);
        throw error;
      }
    },

    // Progress queries
    userProgress: async (_, { userId, scope }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        const progress = await progressService.getUserProgress(userId, { scope });
        return progress.progress.bySkill || [];
      } catch (error) {
        console.error('GraphQL: Error fetching user progress:', error);
        throw error;
      }
    },

    progress: async (_, { userId }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        return await progressService.getUserProgress(userId, {});
      } catch (error) {
        console.error('GraphQL: Error fetching progress:', error);
        throw error;
      }
    },

    analytics: async (_, { userId, timeframe = 'month' }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        return await progressService.getAnalytics(userId, { timeframe });
      } catch (error) {
        console.error('GraphQL: Error fetching analytics:', error);
        throw error;
      }
    },

    // Content queries
    explanation: async (_, { questionId, studentAnswer }) => {
      // Mock explanation - replace with actual AI service call
      return {
        questionId,
        explanation: 'This is a detailed explanation of the concept...',
        hints: ['Try breaking it down into smaller parts', 'Remember the formula'],
        relatedConcepts: ['Linear equations', 'Variable isolation']
      };
    }
  },

  Mutation: {
    // Auth mutations
    register: async (_, { input }) => {
      try {
        return await userService.register(input);
      } catch (error) {
        console.error('GraphQL: Registration error:', error);
        throw new Error(error.message || 'Registration failed');
      }
    },

    login: async (_, { input }) => {
      try {
        return await userService.login(input);
      } catch (error) {
        console.error('GraphQL: Login error:', error);
        throw new Error(error.message || 'Login failed');
      }
    },

    // Question mutations
    createQuestion: async (_, { input }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        // Create question in MongoDB
        const question = new VersionedQuestion({
          ...input,
          status: 'draft',
          version: 1
        });
        
        await question.save();
        
        return {
          id: question._id.toString(),
          version: question.version,
          status: question.status,
          subject: question.subject,
          topic: question.topic,
          difficulty: question.difficulty,
          stem: question.content?.stem,
          options: question.content?.options || [],
          correctOptionIds: question.content?.correctOptionIds || [],
          canonicalSolution: question.content?.canonicalSolution,
          unit: question.content?.unit,
          tags: question.tags || []
        };
      } catch (error) {
        console.error('GraphQL: Error creating question:', error);
        throw new Error('Failed to create question');
      }
    },

    updateQuestion: async (_, { id, input }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        const question = await VersionedQuestion.findByIdAndUpdate(
          id,
          { ...input },
          { new: true, runValidators: true }
        ).lean();
        
        if (!question) {
          throw new Error('Question not found');
        }
        
        return {
          id: question._id.toString(),
          version: question.version,
          status: question.status,
          subject: question.subject,
          topic: question.topic,
          difficulty: question.difficulty,
          stem: question.content?.stem,
          options: question.content?.options || [],
          correctOptionIds: question.content?.correctOptionIds || [],
          canonicalSolution: question.content?.canonicalSolution,
          unit: question.content?.unit,
          tags: question.tags || []
        };
      } catch (error) {
        console.error('GraphQL: Error updating question:', error);
        throw new Error('Failed to update question');
      }
    },

    promoteQuestion: async (_, { id }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        const question = await VersionedQuestion.findByIdAndUpdate(
          id,
          { status: 'active' },
          { new: true }
        ).lean();
        
        if (!question) {
          throw new Error('Question not found');
        }
        
        return {
          id: question._id.toString(),
          status: question.status
        };
      } catch (error) {
        console.error('GraphQL: Error promoting question:', error);
        throw new Error('Failed to promote question');
      }
    },

    retireQuestion: async (_, { id }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        const question = await VersionedQuestion.findByIdAndUpdate(
          id,
          { status: 'retired' },
          { new: true }
        ).lean();
        
        if (!question) {
          throw new Error('Question not found');
        }
        
        return {
          id: question._id.toString(),
          status: question.status
        };
      } catch (error) {
        console.error('GraphQL: Error retiring question:', error);
        throw new Error('Failed to retire question');
      }
    },

    // Quiz attempt mutations
    startQuizAttempt: async (_, { input }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        console.log('GraphQL: Starting quiz attempt for user:', user.user_id);
        console.log('GraphQL: Input:', input);
        
        const result = await quizService.startQuizAttempt(user.user_id, input);
        console.log('GraphQL: QuizService result:', result);
        
        const response = {
          attemptId: result.attemptId,
          subject: result.subject,
          topic: result.topic,
          totalQuestions: result.totalQuestions,
          timeLimitSeconds: result.timeLimitSeconds,
          startedAt: result.startedAt ? new Date(result.startedAt).toISOString() : new Date().toISOString()
        };
        
        console.log('GraphQL: Returning response:', response);
        return response;
      } catch (error) {
        console.error('GraphQL: Error starting quiz attempt:', error);
        throw error;
      }
    },

    saveAnswer: async (_, { attemptId, itemId, input, idempotencyKey }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        return await quizService.saveAnswer(attemptId, itemId, user.user_id, input);
      } catch (error) {
        console.error('GraphQL: Error saving answer:', error);
        throw error;
      }
    },

    submitQuizAttempt: async (_, { attemptId }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      try {
        return await quizService.submitQuizAttempt(attemptId, user.user_id);
      } catch (error) {
        console.error('GraphQL: Error submitting quiz attempt:', error);
        throw error;
      }
    },

    // Content mutations
    submitFeedback: async (_, { input }, { user }) => {
      if (!user) {
        throw new Error('Not authenticated');
      }
      
      // Mock feedback submission - replace with actual database save
      return true;
    }
  },

  Subscription: {
    quizProgress: {
      subscribe: (_, { userId }) => {
        // Mock subscription - replace with actual pub/sub implementation
        return {
          next: () => ({ value: { attempt_id: 'mock-id', user_id: userId } })
        };
      }
    },
    
    questionUpdated: {
      subscribe: (_, { questionId }) => {
        // Mock subscription - replace with actual pub/sub implementation
        return {
          next: () => ({ value: { id: questionId, status: 'active' } })
        };
      }
    }
  }
};

module.exports = resolvers;