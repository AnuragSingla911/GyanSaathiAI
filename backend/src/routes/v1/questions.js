const express = require('express');
const Joi = require('joi');
const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');
const VersionedQuestion = require('../../models/question');
const { protect, authorize } = require('../../middleware/auth');

const router = express.Router();

// Validation schemas
const questionCreateSchema = Joi.object({
  source: Joi.string().optional(),
  license: Joi.string().optional(),
  tags: Joi.array().items(Joi.string()).default([]),
  skillIds: Joi.array().items(Joi.string()).default([]),
  subject: Joi.string().required(),
  topic: Joi.string().required(),
  content: Joi.object({
    stem: Joi.string().required(),
    options: Joi.array().items(
      Joi.object({
        id: Joi.string().required(),
        text: Joi.string().required()
      })
    ).default([]),
    correctOptionIds: Joi.array().items(Joi.string()).default([]),
    canonicalSolution: Joi.string().optional(),
    unit: Joi.string().allow(null).optional()
  }).required()
});

const questionFilterSchema = Joi.object({
  subject: Joi.string().optional(),
  topic: Joi.string().optional(),
  skill: Joi.string().optional(),
  status: Joi.string().valid('draft', 'active', 'retired').optional(),
  tags: Joi.string().optional(), // comma-separated
  page: Joi.number().integer().min(1).default(1),
  limit: Joi.number().integer().min(1).max(100).default(20)
});

// Calculate content hash
const calculateContentHash = (content) => {
  return crypto.createHash('sha256').update(JSON.stringify(content)).digest('hex');
};

// GET /questions - List questions with filters (admin only)
router.get('/', protect, authorize('admin', 'teacher'), async (req, res, next) => {
  try {
    const { error, value } = questionFilterSchema.validate(req.query);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const { subject, topic, skill, status, tags, page, limit } = value;
    
    // Build filter
    const filter = {};
    if (subject) filter.subject = subject;
    if (topic) filter.topic = topic;
    if (status) filter.status = status;
    if (skill) filter.skillIds = { $in: [skill] };
    if (tags) {
      const tagArray = tags.split(',').map(t => t.trim());
      filter.tags = { $in: tagArray };
    }

    // Execute query with pagination
    const skip = (page - 1) * limit;
    const questions = await VersionedQuestion.find(filter)
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(limit)
      .lean();

    const total = await VersionedQuestion.countDocuments(filter);

    res.json({
      success: true,
      traceId: req.traceId,
      data: {
        questions,
        pagination: {
          page,
          limit,
          total,
          totalPages: Math.ceil(total / limit)
        }
      }
    });
  } catch (error) {
    next(error);
  }
});

// POST /questions - Create draft question (admin only)
router.post('/', protect, authorize('admin'), async (req, res, next) => {
  try {
    const { error, value } = questionCreateSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const { source, license, tags, skillIds, subject, topic, content } = value;

    // Calculate content hash
    const contentHash = calculateContentHash(content);

    // Check for duplicate content
    const existingQuestion = await VersionedQuestion.findOne({ contentHash });
    if (existingQuestion) {
      return res.status(400).json({
        success: false,
        message: 'Question with identical content already exists',
        traceId: req.traceId,
        data: { existingQuestionId: existingQuestion._id }
      });
    }

    // Create question
    const question = new VersionedQuestion({
      version: 1,
      status: 'draft',
      source,
      license,
      tags,
      skillIds,
      subject,
      topic,
      content,
      contentHash
    });

    await question.save();

    res.status(201).json({
      success: true,
      message: 'Question created successfully',
      traceId: req.traceId,
      data: { question }
    });
  } catch (error) {
    next(error);
  }
});

// GET /questions/:id - Get single question
router.get('/:id', protect, async (req, res, next) => {
  try {
    const questionId = req.params.id;
    const question = await VersionedQuestion.findById(questionId).lean();

    if (!question) {
      return res.status(404).json({
        success: false,
        message: 'Question not found',
        traceId: req.traceId
      });
    }

    // Students can only see active questions
    if (req.user.role === 'student' && question.status !== 'active') {
      return res.status(404).json({
        success: false,
        message: 'Question not found',
        traceId: req.traceId
      });
    }

    res.json({
      success: true,
      traceId: req.traceId,
      data: { question }
    });
  } catch (error) {
    next(error);
  }
});

// POST /questions/:id/promote - Promote question to active (admin only)
router.post('/:id/promote', protect, authorize('admin'), async (req, res, next) => {
  try {
    const questionId = req.params.id;
    const question = await VersionedQuestion.findById(questionId);

    if (!question) {
      return res.status(404).json({
        success: false,
        message: 'Question not found',
        traceId: req.traceId
      });
    }

    if (question.status !== 'draft') {
      return res.status(400).json({
        success: false,
        message: 'Only draft questions can be promoted',
        traceId: req.traceId
      });
    }

    // Validate question has required fields for active status
    if (!question.content.stem || question.content.options.length === 0 || question.content.correctOptionIds.length === 0) {
      return res.status(400).json({
        success: false,
        message: 'Question must have stem, options, and correct answers to be promoted',
        traceId: req.traceId
      });
    }

    question.status = 'active';
    await question.save();

    res.json({
      success: true,
      message: 'Question promoted to active status',
      traceId: req.traceId,
      data: { question }
    });
  } catch (error) {
    next(error);
  }
});

// POST /questions/:id/retire - Retire question (admin only)
router.post('/:id/retire', protect, authorize('admin'), async (req, res, next) => {
  try {
    const questionId = req.params.id;
    const question = await VersionedQuestion.findById(questionId);

    if (!question) {
      return res.status(404).json({
        success: false,
        message: 'Question not found',
        traceId: req.traceId
      });
    }

    if (question.status === 'retired') {
      return res.status(400).json({
        success: false,
        message: 'Question is already retired',
        traceId: req.traceId
      });
    }

    question.status = 'retired';
    await question.save();

    res.json({
      success: true,
      message: 'Question retired successfully',
      traceId: req.traceId,
      data: { question }
    });
  } catch (error) {
    next(error);
  }
});

// Legacy compatibility - GET /questions for quiz generation
router.get('/generate', protect, async (req, res, next) => {
  try {
    const { subject, topic, difficulty, limit = 5 } = req.query;
    
    const filter = { status: 'active' };
    if (subject) filter.subject = subject;
    if (topic) filter.topic = topic;
    if (difficulty) filter.tags = { $in: [difficulty] };

    const questions = await VersionedQuestion.find(filter)
      .limit(parseInt(limit))
      .lean();

    // Transform to expected format for frontend
    const transformedQuestions = questions.map(q => ({
      _id: q._id,
      questionText: q.content.stem,
      options: q.content.options.map(opt => opt.text),
      correctAnswer: q.content.options.find(opt => 
        q.content.correctOptionIds.includes(opt.id)
      )?.text || '',
      subject: q.subject,
      topic: q.topic,
      difficulty: q.tags.find(tag => ['easy', 'medium', 'hard'].includes(tag)) || 'medium'
    }));

    res.json({
      success: true,
      questions: transformedQuestions,
      traceId: req.traceId
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
