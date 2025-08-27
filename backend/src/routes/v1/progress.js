const express = require('express');
const Joi = require('joi');
const { query } = require('../../utils/database');
const { protect, authorize, ownerOrAdmin } = require('../../middleware/auth');
const { getQueueHealth } = require('../../services/progressWorker');

const router = express.Router();

// Validation schemas
const progressFilterSchema = Joi.object({
  scope: Joi.string().valid('subject', 'topic', 'skill').optional(),
  subject: Joi.string().optional(),
  topic: Joi.string().optional(),
  limit: Joi.number().integer().min(1).max(100).default(50)
});

const analyticsFilterSchema = Joi.object({
  timeframe: Joi.string().valid('week', 'month', 'year').default('month'),
  subject: Joi.string().optional()
});

// GET /users/:userId/progress - Get user progress summary
router.get('/:userId/progress', protect, ownerOrAdmin('userId'), async (req, res, next) => {
  try {
    const { error, value } = progressFilterSchema.validate(req.query);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const userId = req.params.userId;
    const { scope, subject, topic, limit } = value;

    // Build base query
    let whereClause = 'WHERE user_id = $1';
    const params = [userId];
    let paramIndex = 2;

    if (subject) {
      whereClause += ` AND subject = $${paramIndex}`;
      params.push(subject);
      paramIndex++;
    }

    if (topic) {
      whereClause += ` AND topic = $${paramIndex}`;
      params.push(topic);
      paramIndex++;
    }

    // Get overall stats
    const overallResult = await query(
      `SELECT 
         COUNT(*) as total_skills,
         SUM(total_questions_answered) as total_questions,
         SUM(correct_answers) as total_correct,
         AVG(mastery_level) as average_mastery,
         MAX(current_streak) as current_streak,
         MAX(best_streak) as best_streak
       FROM user_progress 
       ${whereClause}`,
      params
    );

    const overall = overallResult.rows[0];

    // Get quiz attempt stats
    const quizStatsResult = await query(
      `SELECT 
         COUNT(*) as total_attempts,
         COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_attempts,
         AVG(CASE WHEN status = 'completed' THEN score ELSE NULL END) as average_score
       FROM quizzes 
       WHERE user_id = $1`,
      [userId]
    );

    const quizStats = quizStatsResult.rows[0];

    // Get progress by scope
    let progressData = {};

    if (scope === 'subject' || !scope) {
      const subjectResult = await query(
        `SELECT 
           subject,
           COUNT(*) as skills_count,
           SUM(total_questions_answered) as total_questions,
           SUM(correct_answers) as correct_answers,
           AVG(mastery_level) as average_mastery
         FROM user_progress 
         ${whereClause}
         GROUP BY subject
         ORDER BY average_mastery DESC
         LIMIT $${paramIndex}`,
        [...params, limit]
      );

      progressData.bySubject = subjectResult.rows.reduce((acc, row) => {
        acc[row.subject] = {
          skillsCount: parseInt(row.skills_count),
          totalQuestions: parseInt(row.total_questions),
          correctAnswers: parseInt(row.correct_answers),
          averageMastery: parseFloat(row.average_mastery),
          accuracy: row.total_questions > 0 ? (row.correct_answers / row.total_questions) * 100 : 0
        };
        return acc;
      }, {});
    }

    if (scope === 'topic' || !scope) {
      const topicResult = await query(
        `SELECT 
           subject, topic,
           COUNT(*) as skills_count,
           SUM(total_questions_answered) as total_questions,
           SUM(correct_answers) as correct_answers,
           AVG(mastery_level) as average_mastery,
           MAX(last_practiced) as last_practiced
         FROM user_progress 
         ${whereClause}
         GROUP BY subject, topic
         ORDER BY average_mastery DESC
         LIMIT $${paramIndex}`,
        [...params, limit]
      );

      progressData.byTopic = topicResult.rows.reduce((acc, row) => {
        const key = `${row.subject}_${row.topic}`;
        acc[key] = {
          subject: row.subject,
          topic: row.topic,
          skillsCount: parseInt(row.skills_count),
          totalQuestions: parseInt(row.total_questions),
          correctAnswers: parseInt(row.correct_answers),
          averageMastery: parseFloat(row.average_mastery),
          lastPracticed: row.last_practiced
        };
        return acc;
      }, {});
    }

    if (scope === 'skill' || !scope) {
      const skillResult = await query(
        `SELECT 
           subject, topic, skill,
           total_questions_answered,
           correct_answers,
           mastery_level,
           current_streak,
           best_streak,
           last_practiced
         FROM user_progress 
         ${whereClause}
         ORDER BY mastery_level DESC
         LIMIT $${paramIndex}`,
        [...params, limit]
      );

      progressData.bySkill = skillResult.rows.map(row => ({
        subject: row.subject,
        topic: row.topic,
        skill: row.skill,
        totalQuestions: parseInt(row.total_questions_answered),
        correctAnswers: parseInt(row.correct_answers),
        masteryLevel: parseFloat(row.mastery_level),
        currentStreak: parseInt(row.current_streak),
        bestStreak: parseInt(row.best_streak),
        lastUpdated: row.last_practiced
      }));
    }

    // Get recent activity (last 30 days)
    const recentActivityResult = await query(
      `SELECT 
         DATE(started_at) as date,
         COUNT(*) as attempts,
         SUM(completed_questions) as questions_answered,
         AVG(score) as average_score
       FROM quizzes 
       WHERE user_id = $1 AND started_at >= CURRENT_DATE - INTERVAL '30 days' AND status = 'completed'
       GROUP BY DATE(started_at)
       ORDER BY date DESC`,
      [userId]
    );

    const recentActivity = recentActivityResult.rows.map(row => ({
      date: row.date,
      attempts: parseInt(row.attempts),
      questionsAnswered: parseInt(row.questions_answered) || 0,
      accuracy: row.average_score ? parseFloat(row.average_score) : 0
    }));

    res.json({
      success: true,
      traceId: req.traceId,
      data: {
        overall: {
          totalSkills: parseInt(overall.total_skills) || 0,
          totalQuestions: parseInt(overall.total_questions) || 0,
          totalCorrect: parseInt(overall.total_correct) || 0,
          averageMastery: parseFloat(overall.average_mastery) || 0,
          currentStreak: parseInt(overall.current_streak) || 0,
          bestStreak: parseInt(overall.best_streak) || 0,
          totalAttempts: parseInt(quizStats.total_attempts) || 0,
          completedAttempts: parseInt(quizStats.completed_attempts) || 0,
          averageScore: parseFloat(quizStats.average_score) || 0
        },
        progress: progressData,
        recentActivity
      }
    });
  } catch (error) {
    next(error);
  }
});

// GET /users/:userId/analytics - Get detailed analytics
router.get('/:userId/analytics', protect, ownerOrAdmin('userId'), async (req, res, next) => {
  try {
    const { error, value } = analyticsFilterSchema.validate(req.query);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const userId = req.params.userId;
    const { timeframe, subject } = value;

    // Calculate date range
    let dateFilter = '';
    switch (timeframe) {
      case 'week':
        dateFilter = "started_at >= CURRENT_DATE - INTERVAL '7 days'";
        break;
      case 'month':
        dateFilter = "started_at >= CURRENT_DATE - INTERVAL '30 days'";
        break;
      case 'year':
        dateFilter = "started_at >= CURRENT_DATE - INTERVAL '365 days'";
        break;
    }

    // Performance over time
    const performanceResult = await query(
      `SELECT 
         DATE(qa.started_at) as date,
         AVG(CASE WHEN ai.is_correct THEN 1 ELSE 0 END) * 100 as accuracy,
         COUNT(ai.response_id) as questions_answered,
         SUM(EXTRACT(EPOCH FROM (ai.created_at - qa.started_at))/60) as total_time_minutes
       FROM quizzes qa
       JOIN quiz_responses ai ON qa.quiz_id = ai.quiz_id
       WHERE qa.user_id = $1 AND ${dateFilter} AND ai.user_answer IS NOT NULL
       ${subject ? 'AND qa.subject = $2' : ''}
       GROUP BY DATE(qa.started_at)
       ORDER BY date`,
      subject ? [userId, subject] : [userId]
    );

    // Subject breakdown
    const subjectBreakdownResult = await query(
      `SELECT 
         qa.subject,
         COUNT(ai.response_id) as questions_answered,
         SUM(CASE WHEN ai.is_correct THEN 1 ELSE 0 END) as correct_answers,
         AVG(CASE WHEN ai.is_correct THEN 1 ELSE 0 END) * 100 as accuracy
       FROM quizzes qa
       JOIN quiz_responses ai ON qa.quiz_id = ai.quiz_id
       WHERE qa.user_id = $1 AND ${dateFilter} AND ai.user_answer IS NOT NULL
       GROUP BY qa.subject
       ORDER BY accuracy DESC`,
      [userId]
    );

    // Difficulty progression
    const difficultyResult = await query(
      `SELECT 
         COALESCE(
           ai.difficulty_level,
           'medium'
         ) as difficulty,
         COUNT(ai.response_id) as questions_answered,
         SUM(CASE WHEN ai.is_correct THEN 1 ELSE 0 END) as correct_answers,
         AVG(CASE WHEN ai.is_correct THEN 1 ELSE 0 END) * 100 as accuracy
       FROM quizzes qa
       JOIN quiz_responses ai ON qa.quiz_id = ai.quiz_id
       WHERE qa.user_id = $1 AND ${dateFilter} AND ai.user_answer IS NOT NULL
       GROUP BY difficulty
       ORDER BY 
         CASE difficulty 
           WHEN 'easy' THEN 1 
           WHEN 'medium' THEN 2 
           WHEN 'hard' THEN 3 
           ELSE 4 
         END`,
      [userId]
    );

    res.json({
      success: true,
      traceId: req.traceId,
      data: {
        timeframe,
        performance: performanceResult.rows.map(row => ({
          date: row.date,
          accuracy: parseFloat(row.accuracy) || 0,
          questionsAnswered: parseInt(row.questions_answered),
          totalTimeMinutes: parseFloat(row.total_time_minutes) || 0
        })),
        subjectBreakdown: subjectBreakdownResult.rows.map(row => ({
          subject: row.subject,
          questionsAnswered: parseInt(row.questions_answered),
          correctAnswers: parseInt(row.correct_answers),
          accuracy: parseFloat(row.accuracy) || 0
        })),
        difficultyProgression: difficultyResult.rows.map(row => ({
          difficulty: row.difficulty,
          questionsAnswered: parseInt(row.questions_answered),
          correctAnswers: parseInt(row.correct_answers),
          accuracy: parseFloat(row.accuracy) || 0
        }))
      }
    });
  } catch (error) {
    next(error);
  }
});

// GET /progress/queue-health - Check progress processing queue health (admin only)
router.get('/queue-health', protect, authorize('admin'), async (req, res, next) => {
  try {
    const health = await getQueueHealth();
    
    res.json({
      success: true,
      traceId: req.traceId,
      data: { queue: health }
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
