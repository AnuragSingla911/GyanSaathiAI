const { query } = require('../utils/database');

class ProgressService {
  // Get user progress summary
  async getUserProgress(userId, { scope, subject, topic, limit = 50 }) {
    try {
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

        progressData.bySubject = subjectResult.rows.map(row => ({
          subject: row.subject,
          skillsCount: parseInt(row.skills_count) || 0,
          totalQuestions: parseInt(row.total_questions) || 0,
          correctAnswers: parseInt(row.correct_answers) || 0,
          averageMastery: parseFloat(row.average_mastery) || 0,
          accuracy: row.total_questions > 0 ? row.correct_answers / row.total_questions : 0
        }));
      }

      if (scope === 'topic' || !scope) {
        const topicResult = await query(
          `SELECT 
             subject,
             topic,
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

        progressData.byTopic = topicResult.rows.map(row => ({
          subject: row.subject,
          topic: row.topic,
          skillsCount: parseInt(row.skills_count) || 0,
          totalQuestions: parseInt(row.total_questions) || 0,
          correctAnswers: parseInt(row.correct_answers) || 0,
          averageMastery: parseFloat(row.average_mastery) || 0,
          lastPracticed: row.last_practiced
        }));
      }

      if (scope === 'skill' || !scope) {
        const skillResult = await query(
          `SELECT 
             subject,
             topic,
             skill,
             total_questions_answered as total_questions,
             correct_answers,
             mastery_level,
             current_streak,
             best_streak,
             updated_at
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
          totalQuestions: parseInt(row.total_questions) || 0,
          correctAnswers: parseInt(row.correct_answers) || 0,
          masteryLevel: parseFloat(row.mastery_level) || 0,
          currentStreak: parseInt(row.current_streak) || 0,
          bestStreak: parseInt(row.best_streak) || 0,
          lastUpdated: row.updated_at
        }));
      }

      // Get recent activity from quiz attempts instead of non-existent user_activity table
      const recentActivityResult = await query(
        `SELECT 
           DATE(started_at) as date,
           COUNT(*) as attempts,
           SUM(total_questions) as questions_answered,
           AVG(CASE WHEN status = 'completed' THEN score ELSE NULL END) as accuracy
         FROM quizzes 
         WHERE user_id = $1
         GROUP BY DATE(started_at)
         ORDER BY date DESC
         LIMIT 7`,
        [userId]
      );

      const recentActivity = recentActivityResult.rows.map(row => ({
        date: row.date,
        attempts: parseInt(row.attempts) || 0,
        questionsAnswered: parseInt(row.questions_answered) || 0,
        accuracy: parseFloat(row.accuracy) || 0
      }));

      return {
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
      };
    } catch (error) {
      console.error('ProgressService: Error getting user progress:', error);
      throw error;
    }
  }

  // Get analytics data
  async getAnalytics(userId, { timeframe = 'month', subject }) {
    try {
      let dateFilter = '';
      const params = [userId];
      let paramIndex = 2;

      switch (timeframe) {
        case 'week':
          dateFilter = 'AND created_at >= NOW() - INTERVAL \'7 days\'';
          break;
        case 'month':
          dateFilter = 'AND created_at >= NOW() - INTERVAL \'30 days\'';
          break;
        case 'year':
          dateFilter = 'AND created_at >= NOW() - INTERVAL \'365 days\'';
          break;
      }

      if (subject) {
        dateFilter += ` AND subject = $${paramIndex}`;
        params.push(subject);
        paramIndex++;
      }

      // Get performance over time from quiz attempts instead of non-existent user_activity table
      const performanceResult = await query(
        `SELECT 
           DATE(started_at) as date,
           AVG(CASE WHEN status = 'completed' THEN score ELSE NULL END) as accuracy,
           COUNT(*) as questions_answered,
           AVG(EXTRACT(EPOCH FROM (completed_at - started_at))/60) as total_time_minutes
         FROM quizzes 
         WHERE user_id = $1 ${dateFilter}
         GROUP BY DATE(started_at)
         ORDER BY date`,
        params
      );

      const performance = performanceResult.rows.map(row => ({
        date: row.date,
        accuracy: parseFloat(row.accuracy) || 0,
        questionsAnswered: parseInt(row.questions_answered) || 0,
        totalTimeMinutes: parseFloat(row.total_time_minutes) || 0
      }));

      // Get subject breakdown
      const subjectResult = await query(
        `SELECT 
           subject,
           COUNT(*) as questions_answered,
           SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_answers,
           AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END) as accuracy
         FROM quiz_responses qr
         JOIN quizzes q ON qr.quiz_id = q.quiz_id
         WHERE q.user_id = $1 ${dateFilter}
         GROUP BY subject`,
        params
      );

      const subjectBreakdown = subjectResult.rows.map(row => ({
        subject: row.subject,
        questionsAnswered: parseInt(row.questions_answered) || 0,
        correctAnswers: parseInt(row.correct_answers) || 0,
        accuracy: parseFloat(row.accuracy) || 0
      }));

      // Get difficulty progression
      const difficultyResult = await query(
        `SELECT 
           difficulty_level as difficulty,
           COUNT(*) as questions_answered,
           SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_answers,
           AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END) as accuracy
         FROM quiz_responses qr
         JOIN quizzes q ON qr.quiz_id = q.quiz_id
         WHERE q.user_id = $1 ${dateFilter}
         GROUP BY difficulty_level
         ORDER BY difficulty_level`,
        params
      );

      const difficultyProgression = difficultyResult.rows.map(row => ({
        difficulty: row.difficulty,
        questionsAnswered: parseInt(row.questions_answered) || 0,
        correctAnswers: parseInt(row.correct_answers) || 0,
        accuracy: parseFloat(row.accuracy) || 0
      }));

      return {
        timeframe,
        performance,
        subjectBreakdown,
        difficultyProgression
      };
    } catch (error) {
      console.error('ProgressService: Error getting analytics:', error);
      throw error;
    }
  }
}

module.exports = new ProgressService();
