const express = require('express');
const Joi = require('joi');
const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');
const { query, transaction } = require('../../utils/database');
const VersionedQuestion = require('../../models/question');
const { protect, authorize, ownerOrAdmin } = require('../../middleware/auth');
const { publishProgressEvent } = require('../../services/progressWorker');

const router = express.Router();

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
  try {
    const { error, value } = startAttemptSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const { subject, topic, totalQuestions, timeLimitSeconds, skillFilters } = value;
    const userId = req.user.user_id;

    // Build question filter
    const questionFilter = { status: 'active', subject };
    if (topic) questionFilter.topic = topic;
    if (skillFilters && skillFilters.length > 0) {
      questionFilter.skillIds = { $in: skillFilters };
    }

    // Get available questions
    const availableQuestions = await VersionedQuestion.find(questionFilter).lean();
    
    if (availableQuestions.length < totalQuestions) {
      return res.status(400).json({
        success: false,
        message: `Only ${availableQuestions.length} questions available for the specified criteria`,
        traceId: req.traceId
      });
    }

    // Randomly select questions
    const selectedQuestions = availableQuestions
      .sort(() => 0.5 - Math.random())
      .slice(0, totalQuestions);

    // Generate seed for reproducibility
    const seed = Math.floor(Math.random() * 1000000);

    // Create quiz attempt in transaction
    const result = await transaction(async (client) => {
      // Create quiz attempt
      const attemptResult = await client.query(
        `INSERT INTO quiz_attempts (user_id, subject, topic, total_questions, seed, time_limit_seconds, status)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         RETURNING attempt_id, started_at`,
        [userId, subject, topic, totalQuestions, seed, timeLimitSeconds, 'in_progress']
      );

      const attempt = attemptResult.rows[0];

      // Create attempt items with question snapshots
      for (let i = 0; i < selectedQuestions.length; i++) {
        const question = selectedQuestions[i];
        const shownPayload = {
          questionId: question._id.toString(),
          version: question.version,
          stem: question.content.stem,
          options: question.content.options,
          metadata: {
            subject: question.subject,
            topic: question.topic,
            tags: question.tags,
            skillIds: question.skillIds
          }
        };

        await client.query(
          `INSERT INTO attempt_items (attempt_id, ordinal, question_id, question_version, shown_payload)
           VALUES ($1, $2, $3, $4, $5)`,
          [attempt.attempt_id, i + 1, question._id.toString(), question.version, JSON.stringify(shownPayload)]
        );
      }

      return attempt;
    });

    res.status(201).json({
      success: true,
      message: 'Quiz attempt started successfully',
      traceId: req.traceId,
      data: {
        attemptId: result.attempt_id,
        subject,
        topic,
        totalQuestions,
        timeLimitSeconds,
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

    // Get attempt details
    const attemptResult = await query(
      `SELECT qa.*, u.username
       FROM quiz_attempts qa
       JOIN users u ON qa.user_id = u.user_id
       WHERE qa.attempt_id = $1`,
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

    // Check ownership (students can only see their own attempts)
    if (req.user.role === 'student' && attempt.user_id !== req.user.user_id) {
      return res.status(403).json({
        success: false,
        message: 'Not authorized to view this attempt',
        traceId: req.traceId
      });
    }

    // Get attempt items
    const itemsResult = await query(
      `SELECT item_id, ordinal, shown_payload, answer_payload, is_correct, 
              score, hints_used, attempts, responded_at
       FROM attempt_items
       WHERE attempt_id = $1
       ORDER BY ordinal`,
      [attemptId]
    );

    const items = itemsResult.rows.map(item => {
      const shownPayload = item.shown_payload;
      
      // Hide correct answers for in-progress attempts (unless admin/teacher)
      if (attempt.status === 'in_progress' && !['admin', 'teacher'].includes(req.user.role)) {
        // Remove correctOptionIds from shown options if present
        if (shownPayload.options) {
          shownPayload.options = shownPayload.options.map(opt => ({
            id: opt.id,
            text: opt.text
          }));
        }
      }

      return {
        itemId: item.item_id,
        ordinal: item.ordinal,
        question: shownPayload,
        userAnswer: item.answer_payload,
        isCorrect: item.is_correct,
        score: item.score,
        hintsUsed: item.hints_used,
        attempts: item.attempts,
        respondedAt: item.responded_at
      };
    });

    res.json({
      success: true,
      traceId: req.traceId,
      data: {
        attempt: {
          attemptId: attempt.attempt_id,
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
      'SELECT status, user_id FROM quiz_attempts WHERE attempt_id = $1',
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
        'SELECT answer_payload FROM attempt_items WHERE item_id = $1 AND answer_payload IS NOT NULL',
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
      'SELECT shown_payload, question_id, question_version FROM attempt_items WHERE item_id = $1 AND attempt_id = $2',
      [itemId, attemptId]
    );

    if (itemResult.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'Quiz item not found',
        traceId: req.traceId
      });
    }

    const item = itemResult.rows[0];
    const shownPayload = item.shown_payload;

    // Get correct answer from original question
    const originalQuestion = await VersionedQuestion.findById(item.question_id);
    if (!originalQuestion) {
      return res.status(500).json({
        success: false,
        message: 'Original question not found for grading',
        traceId: req.traceId
      });
    }

    // Grade the answer
    const correctAnswers = originalQuestion.content.correctOptionIds;
    const selectedOption = shownPayload.options.find(opt => opt.text === answer);
    const isCorrect = selectedOption && correctAnswers.includes(selectedOption.id);
    const score = isCorrect ? 1.0 : 0.0;

    // Save answer
    const result = await transaction(async (client) => {
      // Update item with answer
      await client.query(
        `UPDATE attempt_items 
         SET answer_payload = $1, is_correct = $2, score = $3, hints_used = $4, 
             attempts = attempts + 1, responded_at = CURRENT_TIMESTAMP
         WHERE item_id = $5`,
        [JSON.stringify({ answer, timeSpent }), isCorrect, score, hintsUsed, itemId]
      );

      // Update attempt completed questions count
      await client.query(
        `UPDATE quiz_attempts 
         SET completed_questions = (
           SELECT COUNT(*) FROM attempt_items 
           WHERE attempt_id = $1 AND answer_payload IS NOT NULL
         )
         WHERE attempt_id = $1`,
        [attemptId]
      );

      return { isCorrect, score };
    });

    // Publish progress event for background processing
    await publishProgressEvent({
      type: 'ANSWER_SAVED',
      userId: req.user.user_id,
      attemptId,
      itemId,
      subject: shownPayload.metadata.subject,
      topic: shownPayload.metadata.topic,
      skillIds: shownPayload.metadata.skillIds,
      isCorrect,
      score,
      timestamp: new Date().toISOString()
    });

    res.json({
      success: true,
      message: 'Answer saved successfully',
      traceId: req.traceId,
      data: {
        isCorrect: result.isCorrect,
        score: result.score,
        correctAnswer: !isCorrect ? originalQuestion.content.options.find(opt => 
          correctAnswers.includes(opt.id)
        )?.text : undefined
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
      'SELECT user_id, status, total_questions, completed_questions FROM quiz_attempts WHERE attempt_id = $1',
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
      'SELECT AVG(score) as average_score, COUNT(*) as answered_count FROM attempt_items WHERE attempt_id = $1 AND answer_payload IS NOT NULL',
      [attemptId]
    );

    const stats = scoreResult.rows[0];
    const finalScore = stats.average_score ? parseFloat(stats.average_score) * 100 : 0;

    // Update attempt status
    await query(
      `UPDATE quiz_attempts 
       SET status = 'completed', completed_at = CURRENT_TIMESTAMP
       WHERE attempt_id = $1`,
      [attemptId]
    );

    // Publish completion event for progress tracking
    await publishProgressEvent({
      type: 'ATTEMPT_COMPLETED',
      userId: req.user.user_id,
      attemptId,
      finalScore,
      answeredCount: parseInt(stats.answered_count),
      totalQuestions: attempt.total_questions,
      timestamp: new Date().toISOString()
    });

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

module.exports = router;
