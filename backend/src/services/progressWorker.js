const Queue = require('bull');
const { query, transaction } = require('../utils/database');
const redis = require('../utils/redis');

// Create progress processing queue
const progressQueue = new Queue('progress processing', {
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT || 6379,
    db: process.env.REDIS_DB || 0
  }
});

// Progress event types
const EVENT_TYPES = {
  ANSWER_SAVED: 'ANSWER_SAVED',
  ATTEMPT_COMPLETED: 'ATTEMPT_COMPLETED',
  BULK_UPDATE: 'BULK_UPDATE'
};

// Process progress events
progressQueue.process('updateProgress', 10, async (job) => {
  const { type, userId, ...eventData } = job.data;
  
  try {
    switch (type) {
      case EVENT_TYPES.ANSWER_SAVED:
        await processAnswerSaved(userId, eventData);
        break;
      case EVENT_TYPES.ATTEMPT_COMPLETED:
        await processAttemptCompleted(userId, eventData);
        break;
      case EVENT_TYPES.BULK_UPDATE:
        await processBulkUpdate(userId, eventData);
        break;
      default:
        console.warn(`Unknown progress event type: ${type}`);
    }
  } catch (error) {
    console.error('Error processing progress event:', error);
    throw error; // Re-throw to trigger retry
  }
});

// Process individual answer saved
async function processAnswerSaved(userId, eventData) {
  const { subject, topic, skillIds, isCorrect, score } = eventData;
  
  // Update progress for each skill
  const skills = skillIds || [topic]; // Fallback to topic if no skills
  
  for (const skill of skills) {
    await updateProgressSummary(userId, subject, topic, skill, {
      totalQuestions: 1,
      correctAnswers: isCorrect ? 1 : 0,
      scoreSum: score
    });
  }
}

// Process completed attempt
async function processAttemptCompleted(userId, eventData) {
  const { attemptId, finalScore, answeredCount, totalQuestions } = eventData;
  
  // Get detailed attempt data for comprehensive progress update
  const attemptResult = await query(
    `SELECT qa.subject, qa.topic, ai.is_correct, ai.shown_payload
     FROM quiz_attempts qa
     JOIN attempt_items ai ON qa.attempt_id = ai.attempt_id
     WHERE qa.attempt_id = $1 AND ai.answer_payload IS NOT NULL`,
    [attemptId]
  );
  
  const items = attemptResult.rows;
  const groupedBySkill = {};
  
  // Group answers by skill
  items.forEach(item => {
    const metadata = item.shown_payload.metadata;
    const skills = metadata.skillIds || [metadata.topic];
    
    skills.forEach(skill => {
      if (!groupedBySkill[skill]) {
        groupedBySkill[skill] = {
          subject: metadata.subject,
          topic: metadata.topic,
          correct: 0,
          total: 0
        };
      }
      
      groupedBySkill[skill].total++;
      if (item.is_correct) {
        groupedBySkill[skill].correct++;
      }
    });
  });
  
  // Update progress for each skill
  for (const [skill, stats] of Object.entries(groupedBySkill)) {
    await updateProgressSummary(userId, stats.subject, stats.topic, skill, {
      totalQuestions: stats.total,
      correctAnswers: stats.correct,
      scoreSum: stats.correct // Simple scoring
    });
  }
  
  // Update streaks
  await updateStreaks(userId, finalScore >= 70); // 70% threshold for streak
}

// Process bulk updates (for data migrations or corrections)
async function processBulkUpdate(userId, eventData) {
  const { updates } = eventData;
  
  for (const update of updates) {
    await updateProgressSummary(
      userId, 
      update.subject, 
      update.topic, 
      update.skill, 
      update.stats
    );
  }
}

// Core progress summary update function
async function updateProgressSummary(userId, subject, topic, skill, stats) {
  await transaction(async (client) => {
    // Get or create progress entry
    const existingResult = await client.query(
      'SELECT * FROM progress_summary WHERE user_id = $1 AND subject = $2 AND topic = $3 AND skill = $4',
      [userId, subject, topic, skill]
    );
    
    if (existingResult.rows.length === 0) {
      // Create new progress entry
      await client.query(
        `INSERT INTO progress_summary 
         (user_id, subject, topic, skill, total_questions_answered, correct_answers, mastery_level, last_updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP)`,
        [userId, subject, topic, skill, stats.totalQuestions, stats.correctAnswers, 
         calculateMasteryLevel(stats.correctAnswers, stats.totalQuestions)]
      );
    } else {
      // Update existing progress
      const existing = existingResult.rows[0];
      const newTotal = existing.total_questions_answered + stats.totalQuestions;
      const newCorrect = existing.correct_answers + stats.correctAnswers;
      const newMastery = calculateMasteryLevel(newCorrect, newTotal);
      
      // Update streak logic
      const lastCorrect = stats.correctAnswers === stats.totalQuestions;
      const newCurrentStreak = lastCorrect ? existing.current_streak + 1 : 0;
      const newBestStreak = Math.max(existing.best_streak, newCurrentStreak);
      
      await client.query(
        `UPDATE progress_summary 
         SET total_questions_answered = $1, correct_answers = $2, mastery_level = $3,
             current_streak = $4, best_streak = $5, last_updated_at = CURRENT_TIMESTAMP
         WHERE user_id = $6 AND subject = $7 AND topic = $8 AND skill = $9`,
        [newTotal, newCorrect, newMastery, newCurrentStreak, newBestStreak,
         userId, subject, topic, skill]
      );
    }
  });
}

// Update user streaks
async function updateStreaks(userId, wasSuccessful) {
  // This could be expanded to track daily, weekly streaks etc.
  const streakKey = `user_streak_${userId}`;
  
  if (wasSuccessful) {
    await redis.incr(streakKey);
    await redis.expire(streakKey, 86400 * 7); // 7 day expiry
  } else {
    await redis.del(streakKey);
  }
}

// Calculate mastery level (0.0 to 1.0)
function calculateMasteryLevel(correct, total) {
  if (total === 0) return 0.0;
  
  const accuracy = correct / total;
  
  // Apply learning curve - more questions = higher confidence in mastery
  const confidenceMultiplier = Math.min(1.0, total / 20); // Full confidence after 20 questions
  
  return Math.round(accuracy * confidenceMultiplier * 100) / 100;
}

// Public interface for publishing events
async function publishProgressEvent(eventData) {
  try {
    await progressQueue.add('updateProgress', eventData, {
      attempts: 3,
      backoff: {
        type: 'exponential',
        delay: 2000,
      },
      removeOnComplete: 100,
      removeOnFail: 50
    });
  } catch (error) {
    console.error('Failed to publish progress event:', error);
    // Don't throw - progress tracking shouldn't break the main flow
  }
}

// Health check for progress queue
async function getQueueHealth() {
  try {
    const waiting = await progressQueue.getWaiting();
    const active = await progressQueue.getActive();
    const completed = await progressQueue.getCompleted();
    const failed = await progressQueue.getFailed();
    
    return {
      waiting: waiting.length,
      active: active.length,
      completed: completed.length,
      failed: failed.length,
      status: 'healthy'
    };
  } catch (error) {
    return {
      status: 'unhealthy',
      error: error.message
    };
  }
}

module.exports = {
  progressQueue,
  publishProgressEvent,
  getQueueHealth,
  EVENT_TYPES
};
