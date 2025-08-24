const express = require('express');
const { protect } = require('../middleware/auth');
const { Question } = require('../utils/mongodb');

const router = express.Router();

// GET /api/quizzes/questions - Fetch quiz questions (optionally by subject, topic, difficulty)
router.get('/questions', protect, async (req, res) => {
  try {
    const { subject, topic, difficulty, limit = 10 } = req.query;
    const filter = {};
    if (subject) filter.subject = subject;
    if (topic) filter.topic = topic;
    if (difficulty) filter.difficulty = difficulty;
    const questions = await Question.find(filter).limit(Number(limit));
    res.json({ success: true, questions });
  } catch (error) {
    res.status(500).json({ success: false, message: 'Failed to fetch questions', error: error.message });
  }
});

module.exports = router;