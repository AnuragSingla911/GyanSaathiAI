const express = require('express');
const { protect, authorize, optionalAuth } = require('../middleware/auth');
const { Question } = require('../utils/mongodb');

const router = express.Router();

router.post('/test', (req, res) => {
  console.log('TEST req.body', req.body);
  res.json({ success: true, body: req.body });
});

router.use((req, res, next) => {
  console.log('CONTENT ROUTER:', req.method, req.path);
  next();
});


router.post('*', (req, res, next) => {
  console.log('POST to:', req.path);
  next();
});

// Placeholder for content generation routes
// router.get('/questions', protect, (req, res) => {
//   res.json({ success: true, message: 'Get questions route - placeholder' });
// });

// router.post('/generate-quiz', protect, (req, res) => {
//   res.json({ success: true, message: 'Generate quiz route - placeholder' });
// });

// router.get('/explanation/:questionId', optionalAuth, (req, res) => {
//   res.json({ success: true, message: 'Get explanation route - placeholder' });
// });

// router.post('/feedback', protect, (req, res) => {
//   res.json({ success: true, message: 'Submit feedback route - placeholder' });
// });

// Admin routes for content management
// POST /api/content/questions - Admin: Insert a new question
router.post('/add-questions', async (req, res) => {
  try {
    console.log('req.body', req.body);
    const { questionText, options, correctAnswer, subject, topic, difficulty } = req.body;
    if (!questionText || !options || !correctAnswer) {
      console.log('Missing required fields', req.body);
      return res.status(400).json({ success: false, message: 'Missing required fields' });
    }
    const question = await Question.create({
      questionText,
      options,
      correctAnswer,
      subject,
      topic,
      difficulty
    });
    res.status(200).json({ success: true, question });
    console.log('Question created:', question);
  } catch (error) {
    res.status(500).json({ success: false, message: 'Failed to insert question', error: error.message });
  }
});

router.put('/questions/:questionId', protect, authorize('admin'), (req, res) => {
  res.json({ success: true, message: 'Update question route - placeholder' });
});

router.delete('/questions/:questionId', protect, authorize('admin'), (req, res) => {
  res.json({ success: true, message: 'Delete question route - placeholder' });
});

module.exports = router;