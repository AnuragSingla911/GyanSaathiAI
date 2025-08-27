const express = require('express');
const Joi = require('joi');
const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');
const { query, transaction } = require('../../utils/database');
const VersionedQuestion = require('../../models/question');
const { protect, authorize, ownerOrAdmin } = require('../../middleware/auth');
const { publishProgressEvent } = require('../../services/progressWorker');

const router = express.Router();

// Log all requests to this router
router.use((req, res, next) => {
  console.log(`=== QUIZ-ATTEMPTS ROUTE: ${req.method} ${req.path} ===`);
  console.log('Request body:', req.body);
  console.log('Request params:', req.params);
  console.log('Request query:', req.query);
  next();
});

// Validation schemas
const startAttemptSchema = Joi.object({
  subject: Joi.string().required(),
  topic: Joi.string().optional(),
  totalQuestions: Joi.number().integer().min(1).max(50).default(5),
  timeLimitSeconds: Joi.number().integer().min(60).optional(),
  skillFilters: Joi.array().items(Joi.string()).optional()
});

const saveAnswerSchema = Joi.object({
  answer: Joi.string().required(),
  timeSpent: Joi.number().integer().min(0).optional(),
  hintsUsed: Joi.number().integer().min(0).default(0)
});

// POST /quiz-attempts - Start a new quiz attempt
router.post('/', protect, async (req, res, next) => {
  console.log('🚨 POST /quiz-attempts ROUTE HIT! 🚨');
  console.log('=== startQuizAttempt: FUNCTION ENTERED ===');
  console.log('startQuizAttempt: Request body:', req.body);
  console.log('startQuizAttempt: User:', req.user);
  
  try {
    const { error, value } = startAttemptSchema.validate(req.body);
    if (error) {
      console.log('startQuizAttempt: Validation error:', error.details[0].message);
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const { subject, topic, totalQuestions, skillFilters } = value;
    const userId = req.user.user_id;
    console.log('startQuizAttempt: Validated values:', { subject, topic, totalQuestions, skillFilters, userId });

    // Build question filter - match actual MongoDB schema
    const questionFilter = { status: 'active', subject };
    if (topic) questionFilter.topic = topic;
    if (skillFilters && skillFilters.length > 0) {
      questionFilter.skillIds = { $in: skillFilters };
    }
    console.log('startQuizAttempt: Question filter:', questionFilter);

    // Get available questions - debug MongoDB connection
    console.log('startQuizAttempt: About to query MongoDB...');
    
    // Check if we can find any questions at all
    const allQuestions = await VersionedQuestion.find({}).limit(5).lean();
    console.log('startQuizAttempt: Found questions without filter:', allQuestions.length);
    if (allQuestions.length > 0) {
      console.log('startQuizAttempt: Sample question structure:', allQuestions[0]);
    }
    
    // Try to find questions with the specific filter
    const availableQuestions = await VersionedQuestion.find(questionFilter).lean();
    console.log(`startQuizAttempt: Found ${availableQuestions.length} available questions for filter:`, questionFilter);
    
    // If no questions found, let's try a broader search
    if (availableQuestions.length === 0) {
      console.log('startQuizAttempt: No questions found with filter, trying broader search...');
      const broaderQuestions = await VersionedQuestion.find({ subject: 'math' }).limit(5).lean();
      console.log('startQuizAttempt: Found questions with just subject filter:', broaderQuestions.length);
      if (broaderQuestions.length > 0) {
        console.log('startQuizAttempt: Sample broader question:', broaderQuestions[0]);
      }
    }
    
    // Randomly select questions
    const selectedQuestions = availableQuestions
      .sort(() => 0.5 - Math.random())
      .slice(0, totalQuestions);
    
    console.log(`startQuizAttempt: Selected ${selectedQuestions.length} questions:`, selectedQuestions.map(q => ({
      _id: q._id,
      subject: q.subject,
      topic: q.topic,
      questionText: q.questionText?.substring(0, 50) + '...'
    })));

    // Create quiz attempt in transaction
    const result = await transaction(async (client) => {
      // Create quiz attempt
      const attemptResult = await client.query(
        `INSERT INTO quizzes (user_id, subject, topic, total_questions, difficulty_level, time_taken, status, started_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         RETURNING quiz_id, started_at`,
        [userId, subject, topic, totalQuestions, 'medium', 0, 'in_progress', new Date()]
      );

      const attempt = attemptResult.rows[0];
      console.log(`startQuizAttempt: Created quiz with ID: ${attempt.quiz_id}`);

      // Create attempt items with question snapshots
      for (let i = 0; i < selectedQuestions.length; i++) {
        const question = selectedQuestions[i];
        console.log(`startQuizAttempt: Inserting question ${i + 1}:`, {
          quiz_id: attempt.quiz_id,
          question_id: question._id.toString(),
          question_text: question.questionText?.substring(0, 50) + '...'
        });
        
        try {
          const insertResult = await client.query(
            `INSERT INTO quiz_responses (quiz_id, user_id, question_id, user_answer, correct_answer, is_correct, time_spent, difficulty_level, hints_used, attempts)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
             RETURNING response_id`,
            [attempt.quiz_id, userId, question._id.toString(), null, question.correctAnswer, null, 0, question.difficulty || 'medium', 0, 1]
          );
          console.log(`startQuizAttempt: Successfully inserted question ${i + 1}, response_id: ${insertResult.rows[0]?.response_id}`);
        } catch (insertError) {
          console.error(`startQuizAttempt: Failed to insert question ${i + 1}:`, insertError);
          throw insertError; // Re-throw to rollback transaction
        }
      }
      console.log(`startQuizAttempt: Inserted ${selectedQuestions.length} questions into quiz_responses`);

      return attempt;
    });

    res.status(201).json({
      success: true,
      traceId: req.traceId,
      data: {
        attemptId: result.quiz_id,
        subject,
        topic,
        totalQuestions,
        questions: availableQuestions,
        startedAt: result.started_at
      }
    });
  } catch (error) {
    next(error);
  }
});

// GET /quiz-attempts/:attemptId - Get quiz attempt details
router.get('/:attemptId', protect, async (req, res, next) => {
  try {
    const attemptId = req.params.attemptId;
    console.log(`getQuizAttempt: Starting for attemptId: ${attemptId}`);

    // Get attempt details
    const attemptResult = await query(
      `SELECT qa.*, u.username
       FROM quizzes qa
       JOIN users u ON qa.user_id = u.user_id
       WHERE qa.quiz_id = $1`,
      [attemptId]
    );

    console.log(`getQuizAttempt: Attempt query result rows: ${attemptResult.rows.length}`);

    if (attemptResult.rows.length === 0) {
      console.log(`getQuizAttempt: No attempt found for ID: ${attemptId}`);
      return res.status(404).json({
        success: false,
        message: 'Quiz attempt not found',
        traceId: req.traceId
      });
    }

    const attempt = attemptResult.rows[0];
    console.log(`getQuizAttempt: Found attempt:`, {
      quiz_id: attempt.quiz_id,
      user_id: attempt.user_id,
      subject: attempt.subject,
      topic: attempt.topic,
      total_questions: attempt.total_questions
    });

    // Check ownership (students can only see their own attempts)
    if (req.user.role === 'student' && attempt.user_id !== req.user.user_id) {
      console.log(`getQuizAttempt: Access denied - user ${req.user.user_id} trying to access attempt for user ${attempt.user_id}`);
      return res.status(403).json({
        success: false,
        message: 'Not authorized to view this attempt',
        traceId: req.traceId
      });
    }

    // Get attempt items with full question data
    console.log(`getQuizAttempt: Querying quiz_responses for quiz_id: ${attemptId}`);
    const itemsResult = await query(
      `SELECT qr.response_id as item_id, qr.question_id, qr.user_answer, qr.correct_answer, qr.is_correct, 
              qr.time_spent, qr.hints_used, qr.attempts, qr.created_at as responded_at
       FROM quiz_responses qr
       WHERE qr.quiz_id = $1
       ORDER BY qr.created_at`,
      [attemptId]
    );

    console.log(`getQuizAttempt: quiz_responses query result:`, {
      rowCount: itemsResult.rows.length,
      rows: itemsResult.rows.map(row => ({
        response_id: row.item_id,
        question_id: row.question_id,
        user_answer: row.user_answer
      }))
    });

    // Fetch the actual questions from VersionedQuestion collection
    const items = [];
    for (let i = 0; i < itemsResult.rows.length; i++) {
      const item = itemsResult.rows[i];
      console.log(`getQuizAttempt: Processing item ${i + 1}:`, {
        item_id: item.item_id,
        question_id: item.question_id,
        question_id_type: typeof item.question_id
      });
      
      // Convert string question_id to ObjectId for MongoDB query
      const mongoose = require('mongoose');
      const questionId = new mongoose.Types.ObjectId(item.question_id);
      console.log(`getQuizAttempt: Converted question_id: ${item.question_id} -> ObjectId: ${questionId}`);
      
      // Get the full question from VersionedQuestion collection
      const question = await VersionedQuestion.findById(questionId).lean();
      console.log(`getQuizAttempt: VersionedQuestion.findById result:`, {
        found: !!question,
        question_id: questionId,
        question_text: question ? question.questionText?.substring(0, 50) + '...' : 'null'
      });
      
      if (!question) {
        console.error(`Question not found for ID: ${item.question_id}`);
        continue;
      }

      // Map the MongoDB question to the structure frontend expects
      const mappedQuestion = {
        content: {
          stem: question.questionText,
          options: question.options?.map((opt, index) => ({
            id: index.toString(),
            text: opt
          })) || [],
          correctAnswer: question.correctAnswer
        },
        metadata: {
          subject: question.subject,
          topic: question.topic,
          difficulty: question.difficulty,
          question_type: question.question_type
        }
      };

      // Hide correct answers for in-progress attempts (unless admin/teacher)
      if (attempt.status === 'in_progress' && !['admin', 'teacher'].includes(req.user.role)) {
        // Create a safe copy without correct answers
        const safeQuestion = { ...mappedQuestion };
        if (safeQuestion.content && safeQuestion.content.correctAnswer) {
          delete safeQuestion.content.correctAnswer;
        }
        
        items.push({
          itemId: item.item_id,
          ordinal: i + 1,
          question: safeQuestion,
          userAnswer: item.user_answer,
          isCorrect: item.is_correct,
          score: item.is_correct ? 100 : 0,
          hintsUsed: item.hints_used,
          attempts: item.attempts,
          respondedAt: item.responded_at
        });
      } else {
        items.push({
          itemId: item.item_id,
          ordinal: i + 1,
          question: mappedQuestion,
          userAnswer: item.user_answer,
          isCorrect: item.is_correct,
          score: item.is_correct ? 100 : 0,
          hintsUsed: item.hints_used,
          attempts: item.attempts,
          respondedAt: item.responded_at
        });
      }
    }

    console.log(`getQuizAttempt: Final items array length: ${items.length}`);
    console.log(`getQuizAttempt: Items structure:`, items.map(item => ({
      itemId: item.itemId,
      ordinal: item.ordinal,
      questionStem: item.question?.content?.stem?.substring(0, 50) + '...'
    })));

    res.json({
      success: true,
      traceId: req.traceId,
      data: {
        attempt: {
          attemptId: attempt.quiz_id,
          userId: attempt.user_id,
          username: attempt.username,
          subject: attempt.subject,
          topic: attempt.topic,
          totalQuestions: attempt.total_questions,
          completedQuestions: attempt.completed_questions,
          status: attempt.status,
          timeLimitSeconds: attempt.time_limit_seconds,
          startedAt: attempt.started_at,
          completedAt: attempt.completed_at
        },
        items
      }
    });
  } catch (error) {
    console.error(`getQuizAttempt: Error occurred:`, error);
    next(error);
  }
});

// PUT /quiz-attempts/:attemptId/items/:itemId - Save answer (idempotent)
router.put('/:attemptId/items/:itemId', protect, async (req, res, next) => {
  try {
    const { attemptId, itemId } = req.params;
    const idempotencyKey = req.headers['idempotency-key'];

    const { error, value } = saveAnswerSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const { answer, timeSpent, hintsUsed } = value;

    // Check if attempt exists and belongs to user
    const attemptResult = await query(
      'SELECT status, user_id FROM quizzes WHERE quiz_id = $1',
      [attemptId]
    );

    if (attemptResult.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'Quiz attempt not found',
        traceId: req.traceId
      });
    }

    const attempt = attemptResult.rows[0];

    if (attempt.user_id !== req.user.user_id) {
      return res.status(403).json({
        success: false,
        message: 'Not authorized to modify this attempt',
        traceId: req.traceId
      });
    }

    if (attempt.status !== 'in_progress') {
      return res.status(400).json({
        success: false,
        message: 'Cannot modify completed attempt',
        traceId: req.traceId
      });
    }

    // Check for idempotency
    if (idempotencyKey) {
      const existingResponse = await query(
        'SELECT answer_payload FROM quiz_responses WHERE item_id = $1 AND answer_payload IS NOT NULL',
        [itemId]
      );

      if (existingResponse.rows.length > 0) {
        return res.json({
          success: true,
          message: 'Answer already saved (idempotent)',
          traceId: req.traceId,
          data: { alreadyAnswered: true }
        });
      }
    }

    // Get item details for grading
    const itemResult = await query(
      'SELECT question_id, correct_answer FROM quiz_responses WHERE response_id = $1 AND quiz_id = $2',
      [itemId, attemptId]
    );

    if (itemResult.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'Question not found in this attempt',
        traceId: req.traceId
      });
    }

    const item = itemResult.rows[0];

    // Grade the answer (simplified - you might want to implement more sophisticated grading)
    console.log('saveAnswer: Grading answer:', {
      userAnswer: answer,
      correctAnswer: item.correct_answer,
      userAnswerType: typeof answer,
      correctAnswerType: typeof item.correct_answer,
      comparison: answer === item.correct_answer
    });
    
    const isCorrect = answer === item.correct_answer;
    const score = isCorrect ? 100 : 0;

    // Update item with answer
    await query(
      `UPDATE quiz_responses 
       SET user_answer = $1, is_correct = $2, time_spent = $3, hints_used = $4, 
           attempts = attempts + 1
       WHERE response_id = $5`,
      [answer, isCorrect, timeSpent, hintsUsed, itemId]
    );

    // Update attempt completed questions count
    await query(
      `UPDATE quizzes 
       SET completed_questions = (
         SELECT COUNT(*) FROM quiz_responses 
         WHERE quiz_id = $1 AND user_answer IS NOT NULL
       )
       WHERE quiz_id = $1`,
      [attemptId]
    );

    // Get attempt details for progress tracking
    const attemptDetailsResult = await query(
      'SELECT subject, topic FROM quizzes WHERE quiz_id = $1',
      [attemptId]
    );
    
    if (attemptDetailsResult.rows.length === 0) {
      console.error('saveAnswer: Attempt not found for progress update');
      return res.json({
        success: true,
        message: 'Answer saved successfully',
        traceId: req.traceId,
        data: {
          isCorrect: isCorrect,
          score: score,
          correctAnswer: !isCorrect ? item.correct_answer : undefined
        }
      });
    }

    const attemptDetails = attemptDetailsResult.rows[0];

    // Direct progress update (no queue needed)
    try {
      console.log('saveAnswer: Updating progress for user:', req.user.user_id, 'subject:', attemptDetails.subject, 'topic:', attemptDetails.topic);
      
      // Use UPSERT logic that works with the unique constraint (user_id, subject, topic, skill)
      const progressResult = await query(
        `INSERT INTO user_progress (user_id, subject, topic, skill, total_questions_answered, correct_answers, last_practiced, mastery_level)
         VALUES ($1, $2, $3, $4, 1, $5, $6, $7)
         ON CONFLICT (user_id, subject, topic, skill) 
         DO UPDATE SET 
           total_questions_answered = user_progress.total_questions_answered + 1,
           correct_answers = user_progress.correct_answers + $5,
           last_practiced = $6,
           mastery_level = CASE 
             WHEN user_progress.total_questions_answered + 1 >= 10 THEN 1.0
             ELSE LEAST(ROUND(((user_progress.correct_answers + $5)::DECIMAL / (user_progress.total_questions_answered + 1))::DECIMAL, 3), 1.0)
           END,
           updated_at = CURRENT_TIMESTAMP
         RETURNING progress_id, total_questions_answered, correct_answers, mastery_level`,
        [req.user.user_id, attemptDetails.subject, attemptDetails.topic, attemptDetails.topic, isCorrect ? 1 : 0, new Date(), isCorrect ? 0.1 : 0.0]
      );
      
      console.log('saveAnswer: Progress update result:', progressResult.rows[0]);
    } catch (progressError) {
      console.error('Failed to update progress:', progressError);
      // Don't fail the answer save if progress update fails
    }

    res.json({
      success: true,
      message: 'Answer saved successfully',
      traceId: req.traceId,
      data: {
        isCorrect: isCorrect,
        score: score,
        correctAnswer: !isCorrect ? item.correct_answer : undefined
      }
    });
  } catch (error) {
    next(error);
  }
});

// POST /quiz-attempts/:attemptId/submit - Submit attempt
router.post('/:attemptId/submit', protect, async (req, res, next) => {
  try {
    const attemptId = req.params.attemptId;

    // Get attempt details
    const attemptResult = await query(
      'SELECT user_id, status, total_questions, completed_questions, subject, topic FROM quizzes WHERE quiz_id = $1',
      [attemptId]
    );

    if (attemptResult.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'Quiz attempt not found',
        traceId: req.traceId
      });
    }

    const attempt = attemptResult.rows[0];

    if (attempt.user_id !== req.user.user_id) {
      return res.status(403).json({
        success: false,
        message: 'Not authorized to submit this attempt',
        traceId: req.traceId
      });
    }

    if (attempt.status !== 'in_progress') {
      return res.status(400).json({
        success: false,
        message: 'Attempt is not in progress',
        traceId: req.traceId
      });
    }

    // Calculate final score
    const scoreResult = await query(
      'SELECT AVG(CASE WHEN is_correct THEN 100 ELSE 0 END) as average_score, COUNT(*) as answered_count, COUNT(CASE WHEN is_correct THEN 1 END) as correct_count FROM quiz_responses WHERE quiz_id = $1 AND user_answer IS NOT NULL',
      [attemptId]
    );

    const stats = scoreResult.rows[0];
    const finalScore = stats.average_score ? parseFloat(stats.average_score) : 0;
    const correctCount = parseInt(stats.correct_count) || 0;

    // Update attempt status
    await query(
      `UPDATE quizzes 
       SET status = 'completed', completed_at = CURRENT_TIMESTAMP
       WHERE quiz_id = $1`,
      [attemptId]
    );

    // Direct progress update for completed attempt (no queue needed)
    try {
      console.log('submitQuizAttempt: Updating progress for completed attempt');
      
      // Use UPSERT logic that works with the unique constraint (user_id, subject, topic, skill)
      const progressResult = await query(
        `INSERT INTO user_progress (user_id, subject, topic, skill, total_questions_answered, correct_answers, last_practiced, mastery_level)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         ON CONFLICT (user_id, subject, topic, skill) 
         DO UPDATE SET 
           total_questions_answered = user_progress.total_questions_answered + $5,
           correct_answers = user_progress.correct_answers + $6,
           last_practiced = $7,
           mastery_level = CASE 
             WHEN user_progress.total_questions_answered + $5 >= 10 THEN 1.0
             ELSE LEAST(ROUND(((user_progress.correct_answers + $6)::DECIMAL / (user_progress.total_questions_answered + $5))::DECIMAL, 3), 1.0)
           END,
           updated_at = CURRENT_TIMESTAMP
         RETURNING progress_id, total_questions_answered, correct_answers, mastery_level`,
        [req.user.user_id, attempt.subject, attempt.topic, attempt.topic, parseInt(stats.answered_count), correctCount, new Date(), Math.min(finalScore / 100, 1.0)]
      );
      
      console.log('submitQuizAttempt: Progress update result:', progressResult.rows[0]);
    } catch (progressError) {
      console.error('Failed to update progress for completed attempt:', progressError);
      // Don't fail the submission if progress update fails
    }

    res.json({
      success: true,
      message: 'Quiz attempt submitted successfully',
      traceId: req.traceId,
      data: {
        finalScore,
        answeredQuestions: parseInt(stats.answered_count),
        totalQuestions: attempt.total_questions
      }
    });
  } catch (error) {
    next(error);
  }
});

// Catch-all route to see if this router is being hit
router.use('*', (req, res) => {
  console.log(`🚨 CATCH-ALL ROUTE HIT: ${req.method} ${req.path}`);
  res.status(404).json({
    success: false,
    message: 'Route not found in quiz-attempts router'
  });
});

module.exports = router;
