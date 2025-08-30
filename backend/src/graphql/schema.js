const { gql } = require('apollo-server-express');

const typeDefs = gql`
  scalar DateTime
  scalar JSON

  type User {
    user_id: ID!
    username: String!
    email: String!
    firstName: String
    lastName: String
    role: String!
    gradeLevel: Int
    isActive: Boolean!
    emailVerified: Boolean!
    createdAt: DateTime
    updatedAt: DateTime
    lastLogin: DateTime
    profileImageUrl: String
  }

  type Question {
    id: ID!
    version: Int!
    status: QuestionStatus!
    stem: String!
    options: [QuestionOption!]!
    correctOptionIds: [String!]!
    canonicalSolution: String!
    unit: String
    tags: [String!]!
    subject: String
    topic: String
    difficulty: String
    createdAt: DateTime
    updatedAt: DateTime
  }

  type QuestionOption {
    id: ID!
    text: String!
  }

  enum QuestionStatus {
    draft
    active
    retired
  }

  type QuizAttempt {
    attempt_id: ID!
    user_id: ID!
    subject: String!
    topic: String
    totalQuestions: Int!
    timeLimitSeconds: Int
    startedAt: DateTime!
    completedAt: DateTime
    finalScore: Float
    answeredQuestions: Int
    status: QuizAttemptStatus!
    items: [AttemptItem!]!
  }

  type AttemptItem {
    item_id: ID!
    question: Question!
    shown_payload: JSON
    userAnswer: String
    isCorrect: Boolean
    score: Float
    timeSpent: Int
    hintsUsed: Int
    answeredAt: DateTime
  }

  enum QuizAttemptStatus {
    in_progress
    completed
    abandoned
  }

  type ProgressSummary {
    user_id: ID!
    subject: String
    topic: String
    skill: String
    mastery_level: Float!
    totalQuestions: Int!
    correctAnswers: Int!
    accuracy: Float!
    lastPracticed: DateTime
  }

  type OverallProgress {
    totalSkills: Int!
    totalQuestions: Int!
    totalCorrect: Int!
    averageMastery: Float!
    currentStreak: Int!
    bestStreak: Int!
    totalAttempts: Int!
    completedAttempts: Int!
    averageScore: Float!
  }

  type SubjectProgress {
    subject: String!
    skillsCount: Int!
    totalQuestions: Int!
    correctAnswers: Int!
    averageMastery: Float!
    accuracy: Float!
  }

  type TopicProgress {
    subject: String!
    topic: String!
    skillsCount: Int!
    totalQuestions: Int!
    correctAnswers: Int!
    averageMastery: Float!
    lastPracticed: DateTime
  }

  type SkillProgress {
    subject: String!
    topic: String!
    skill: String!
    totalQuestions: Int!
    correctAnswers: Int!
    masteryLevel: Float!
    currentStreak: Int!
    bestStreak: Int!
    lastUpdated: DateTime
  }

  type RecentActivity {
    date: String!
    attempts: Int!
    questionsAnswered: Int!
    accuracy: Float!
  }

  type ProgressData {
    overall: OverallProgress!
    progress: ProgressBreakdown!
    recentActivity: [RecentActivity!]!
  }

  type ProgressBreakdown {
    bySubject: [SubjectProgress!]
    byTopic: [TopicProgress!]
    bySkill: [SkillProgress!]
  }

  type AnalyticsData {
    timeframe: String!
    performance: [PerformanceData!]!
    subjectBreakdown: [SubjectAnalytics!]!
    difficultyProgression: [DifficultyAnalytics!]!
  }

  type PerformanceData {
    date: String!
    accuracy: Float!
    questionsAnswered: Int!
    totalTimeMinutes: Int!
  }

  type SubjectAnalytics {
    subject: String!
    questionsAnswered: Int!
    correctAnswers: Int!
    accuracy: Float!
  }

  type DifficultyAnalytics {
    difficulty: String!
    questionsAnswered: Int!
    correctAnswers: Int!
    accuracy: Float!
  }

  type AuthResponse {
    user: User!
    token: String!
  }

  type QuizStartResponse {
    attemptId: String!
    subject: String!
    topic: String
    totalQuestions: Int!
    timeLimitSeconds: Int
    startedAt: String!
  }

  type AnswerResponse {
    isCorrect: Boolean!
    score: Float!
    correctAnswer: String
  }

  type QuizSubmitResponse {
    finalScore: Float!
    answeredQuestions: Int!
    totalQuestions: Int!
  }

  type Explanation {
    questionId: String!
    explanation: String!
    hints: [String!]
    relatedConcepts: [String!]
  }

  type Feedback {
    questionId: String!
    feedbackType: String!
    rating: Int!
    comments: String
  }

  input LoginInput {
    email: String!
    password: String!
  }

  input RegisterInput {
    username: String!
    email: String!
    password: String!
    firstName: String!
    lastName: String!
    gradeLevel: Int
    role: String
  }

  input ProfileUpdateInput {
    email: String
    role: String
  }

  input PasswordChangeInput {
    currentPassword: String!
    newPassword: String!
  }

  input QuizStartInput {
    subject: String!
    topic: String
    totalQuestions: Int
    timeLimitSeconds: Int
    skillFilters: [String!]
  }

  input AnswerInput {
    answer: String!
    timeSpent: Int
    hintsUsed: Int
  }

  input FeedbackInput {
    questionId: String!
    quizId: String
    feedbackType: String!
    rating: Int!
    comments: String
  }

  type Query {
    # Auth
    me: User
    
    # Questions
    questions(
      subject: String
      topic: String
      difficulty: String
      status: QuestionStatus
      limit: Int
      offset: Int
    ): [Question!]!
    
    question(id: ID!): Question
    
    # Quiz Attempts
    quizAttempt(attemptId: ID!): QuizAttempt
    
    # Progress
    userProgress(userId: ID!, scope: String): [ProgressSummary!]!
    progress(userId: ID!): ProgressData!
    analytics(userId: ID!, timeframe: String): AnalyticsData!
    
    # Content
    explanation(questionId: ID!, studentAnswer: String): Explanation
  }

  type Mutation {
    # Auth
    register(input: RegisterInput!): AuthResponse!
    login(input: LoginInput!): AuthResponse!
    logout: Boolean!
    updateProfile(input: ProfileUpdateInput!): User!
    changePassword(input: PasswordChangeInput!): Boolean!
    
    # Questions
    createQuestion(input: JSON!): Question!
    updateQuestion(id: ID!, input: JSON!): Question!
    promoteQuestion(id: ID!): Question!
    retireQuestion(id: ID!): Question!
    
    # Quiz Attempts
    startQuizAttempt(input: QuizStartInput!): QuizStartResponse!
    saveAnswer(
      attemptId: ID!
      itemId: ID!
      input: AnswerInput!
      idempotencyKey: String
    ): AnswerResponse!
    submitQuizAttempt(attemptId: ID!): QuizSubmitResponse!
    
    # Content
    submitFeedback(input: FeedbackInput!): Boolean!
  }

  type Subscription {
    quizProgress(userId: ID!): QuizAttempt!
    questionUpdated(questionId: ID!): Question!
  }
`;

module.exports = typeDefs;
