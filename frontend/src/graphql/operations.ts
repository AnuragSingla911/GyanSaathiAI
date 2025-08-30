import { gql } from '@apollo/client';

// Auth Operations
export const LOGIN_USER = gql`
  mutation LoginUser($input: LoginInput!) {
    login(input: $input) {
      user {
        user_id
        email
        role
        createdAt
        updatedAt
      }
      token
    }
  }
`;

export const REGISTER_USER = gql`
  mutation RegisterUser($input: RegisterInput!) {
    register(input: $input) {
      user {
        user_id
        email
        role
        createdAt
        updatedAt
      }
      token
    }
  }
`;

export const GET_CURRENT_USER = gql`
  query GetCurrentUser {
    me {
      user_id
      email
      role
      createdAt
      updatedAt
    }
  }
`;

export const UPDATE_PROFILE = gql`
  mutation UpdateProfile($input: ProfileUpdateInput!) {
    updateProfile(input: $input) {
      user_id
      email
      role
      createdAt
      updatedAt
    }
  }
`;

export const CHANGE_PASSWORD = gql`
  mutation ChangePassword($input: PasswordChangeInput!) {
    changePassword(input: $input)
  }
`;

export const LOGOUT_USER = gql`
  mutation LogoutUser {
    logout
  }
`;

// Question Operations
export const GET_QUESTIONS = gql`
  query GetQuestions(
    $subject: String
    $topic: String
    $difficulty: String
    $status: QuestionStatus
    $limit: Int
    $offset: Int
  ) {
    questions(
      subject: $subject
      topic: $topic
      difficulty: $difficulty
      status: $status
      limit: $limit
      offset: $offset
    ) {
      id
      version
      status
      stem
      options {
        id
        text
      }
      correctOptionIds
      canonicalSolution
      unit
      tags
      subject
      topic
      difficulty
      createdAt
      updatedAt
    }
  }
`;

export const GET_QUESTION = gql`
  query GetQuestion($id: ID!) {
    question(id: $id) {
      id
      version
      status
      stem
      options {
        id
        text
      }
      correctOptionIds
      canonicalSolution
      unit
      tags
      subject
      topic
      difficulty
      createdAt
      updatedAt
    }
  }
`;

export const CREATE_QUESTION = gql`
  mutation CreateQuestion($input: JSON!) {
    createQuestion(input: $input) {
      id
      version
      status
      stem
      options {
        id
        text
      }
      correctOptionIds
      canonicalSolution
      unit
      tags
      subject
      topic
      difficulty
      createdAt
      updatedAt
    }
  }
`;

export const UPDATE_QUESTION = gql`
  mutation UpdateQuestion($id: ID!, $input: JSON!) {
    updateQuestion(id: $id, input: $input) {
      id
      version
      status
      stem
      options {
        id
        text
      }
      correctOptionIds
      canonicalSolution
      unit
      tags
      subject
      topic
      difficulty
      createdAt
      updatedAt
    }
  }
`;

export const PROMOTE_QUESTION = gql`
  mutation PromoteQuestion($id: ID!) {
    promoteQuestion(id: $id) {
      id
      version
      status
      stem
      options {
        id
        text
      }
      correctOptionIds
      canonicalSolution
      unit
      tags
      subject
      topic
      difficulty
      createdAt
      updatedAt
    }
  }
`;

export const RETIRE_QUESTION = gql`
  mutation RetireQuestion($id: ID!) {
    retireQuestion(id: $id) {
      id
      version
      status
      stem
      options {
        id
        text
      }
      correctOptionIds
      canonicalSolution
      unit
      tags
      subject
      topic
      difficulty
      createdAt
      updatedAt
    }
  }
`;

// Quiz Attempt Operations
export const START_QUIZ_ATTEMPT = gql`
  mutation StartQuizAttempt($input: QuizStartInput!) {
    startQuizAttempt(input: $input) {
      attemptId
      subject
      topic
      totalQuestions
      timeLimitSeconds
      startedAt
    }
  }
`;

export const GET_QUIZ_ATTEMPT = gql`
  query GetQuizAttempt($attemptId: ID!) {
    quizAttempt(attemptId: $attemptId) {
      attempt_id
      user_id
      subject
      topic
      totalQuestions
      timeLimitSeconds
      startedAt
      completedAt
      finalScore
      answeredQuestions
      status
      items {
        item_id
        question {
          id
          version
          status
          stem
          options {
            id
            text
          }
          correctOptionIds
          canonicalSolution
          unit
          tags
          subject
          topic
          difficulty
        }
        shown_payload
        userAnswer
        isCorrect
        score
        timeSpent
        hintsUsed
        answeredAt
      }
    }
  }
`;

export const SAVE_ANSWER = gql`
  mutation SaveAnswer(
    $attemptId: ID!
    $itemId: ID!
    $input: AnswerInput!
    $idempotencyKey: String
  ) {
    saveAnswer(
      attemptId: $attemptId
      itemId: $itemId
      input: $input
      idempotencyKey: $idempotencyKey
    ) {
      isCorrect
      score
      correctAnswer
    }
  }
`;

export const SUBMIT_QUIZ_ATTEMPT = gql`
  mutation SubmitQuizAttempt($attemptId: ID!) {
    submitQuizAttempt(attemptId: $attemptId) {
      finalScore
      answeredQuestions
      totalQuestions
    }
  }
`;

// Progress Operations
export const GET_USER_PROGRESS = gql`
  query GetUserProgress($userId: ID!, $scope: String) {
    userProgress(userId: $userId, scope: $scope) {
      user_id
      subject
      topic
      skill
      mastery_level
      totalQuestions
      correctAnswers
      accuracy
      lastPracticed
    }
  }
`;

export const GET_PROGRESS = gql`
  query GetProgress($userId: ID!) {
    progress(userId: $userId) {
      overall {
        totalSkills
        totalQuestions
        totalCorrect
        averageMastery
        currentStreak
        bestStreak
        totalAttempts
        completedAttempts
        averageScore
      }
      progress {
        bySubject {
          subject
          skillsCount
          totalQuestions
          correctAnswers
          averageMastery
          accuracy
        }
        byTopic {
          subject
          topic
          skillsCount
          totalQuestions
          correctAnswers
          averageMastery
          lastPracticed
        }
        bySkill {
          subject
          topic
          skill
          totalQuestions
          correctAnswers
          masteryLevel
          currentStreak
          bestStreak
          lastUpdated
        }
      }
      recentActivity {
        date
        attempts
        questionsAnswered
        accuracy
      }
    }
  }
`;

export const GET_ANALYTICS = gql`
  query GetAnalytics($userId: ID!, $timeframe: String) {
    analytics(userId: $userId, timeframe: $timeframe) {
      timeframe
      performance {
        date
        accuracy
        questionsAnswered
        totalTimeMinutes
      }
      subjectBreakdown {
        subject
        questionsAnswered
        correctAnswers
        accuracy
      }
      difficultyProgression {
        difficulty
        questionsAnswered
        correctAnswers
        accuracy
      }
    }
  }
`;

// Content Operations
export const GET_EXPLANATION = gql`
  query GetExplanation($questionId: ID!, $studentAnswer: String) {
    explanation(questionId: $questionId, studentAnswer: $studentAnswer) {
      questionId
      explanation
      hints
      relatedConcepts
    }
  }
`;

export const SUBMIT_FEEDBACK = gql`
  mutation SubmitFeedback($input: FeedbackInput!) {
    submitFeedback(input: $input)
  }
`;
