const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const Joi = require('joi');
const { v4: uuidv4 } = require('uuid');
const { query, transaction } = require('../../utils/database');
const redis = require('../../utils/redis');
const { protect, rateLimit } = require('../../middleware/auth');

const router = express.Router();

// Validation schemas
const registerSchema = Joi.object({
  username: Joi.string().alphanum().min(3).max(30).required(),
  email: Joi.string().email().required(),
  password: Joi.string().min(6).required(),
  firstName: Joi.string().min(1).max(50).required(),
  lastName: Joi.string().min(1).max(50).required(),
  gradeLevel: Joi.number().integer().min(6).max(12).optional(),
  role: Joi.string().valid('student', 'parent', 'teacher', 'admin').default('student')
});

const loginSchema = Joi.object({
  email: Joi.string().email().required(),
  password: Joi.string().required()
});

const profileUpdateSchema = Joi.object({
  firstName: Joi.string().min(1).max(50).optional(),
  lastName: Joi.string().min(1).max(50).optional(),
  gradeLevel: Joi.number().integer().min(6).max(12).optional()
});

const passwordChangeSchema = Joi.object({
  currentPassword: Joi.string().required(),
  newPassword: Joi.string().min(6).required()
});

// Generate JWT token
const generateToken = (userId) => {
  return jwt.sign({ id: userId }, process.env.JWT_SECRET, {
    expiresIn: process.env.JWT_EXPIRES_IN || '7d'
  });
};

// Register endpoint
router.post('/register', rateLimit(5, 15 * 60 * 1000), async (req, res, next) => {
  try {
    const { error, value } = registerSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const { username, email, password, firstName, lastName, gradeLevel, role } = value;

    // Check if user already exists
    const existingUser = await query(
      'SELECT user_id FROM users WHERE email = $1 OR username = $2',
      [email, username]
    );

    if (existingUser.rows.length > 0) {
      return res.status(400).json({
        success: false,
        message: 'User already exists with this email or username',
        traceId: req.traceId
      });
    }

    // Hash password
    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(password, salt);

    // Create user
    const result = await transaction(async (client) => {
      const userResult = await client.query(
        `INSERT INTO users (username, email, password_hash, role, grade_level, is_active, email_verified)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         RETURNING user_id, username, email, role, grade_level, created_at`,
        [username, email, hashedPassword, role, gradeLevel, true, true]
      );

      return userResult.rows[0];
    });

    // Generate token
    const token = generateToken(result.user_id);

    // Cache user data
    await redis.set(`user_${result.user_id}`, JSON.stringify(result), 3600);

    res.status(201).json({
      success: true,
      message: 'User registered successfully',
      traceId: req.traceId,
      data: {
        token,
        user: {
          id: result.user_id,
          username: result.username,
          email: result.email,
          firstName,
          lastName,
          role: result.role,
          gradeLevel: result.grade_level,
          createdAt: result.created_at
        }
      }
    });
  } catch (error) {
    next(error);
  }
});

// Login endpoint
router.post('/login', rateLimit(10, 15 * 60 * 1000), async (req, res, next) => {
  try {
    const { error, value } = loginSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const { email, password } = value;

    // Check if user exists
    const result = await query(
      `SELECT user_id, username, email, password_hash, role, grade_level, is_active, email_verified
       FROM users WHERE email = $1`,
      [email]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({
        success: false,
        message: 'Invalid credentials',
        traceId: req.traceId
      });
    }

    const user = result.rows[0];

    // Check if user is active
    if (!user.is_active) {
      return res.status(401).json({
        success: false,
        message: 'Account is deactivated',
        traceId: req.traceId
      });
    }

    // Check password
    const isPasswordValid = await bcrypt.compare(password, user.password_hash);
    if (!isPasswordValid) {
      return res.status(401).json({
        success: false,
        message: 'Invalid credentials',
        traceId: req.traceId
      });
    }

    // Update last login
    await query(
      'UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE user_id = $1',
      [user.user_id]
    );

    // Generate token
    const token = generateToken(user.user_id);

    // Cache user data
    const userData = {
      user_id: user.user_id,
      username: user.username,
      email: user.email,
      role: user.role,
      grade_level: user.grade_level
    };
    await redis.set(`user_${user.user_id}`, JSON.stringify(userData), 3600);

    res.json({
      success: true,
      message: 'Login successful',
      traceId: req.traceId,
      data: {
        token,
        user: {
          id: user.user_id,
          username: user.username,
          email: user.email,
          role: user.role,
          gradeLevel: user.grade_level,
          emailVerified: user.email_verified
        }
      }
    });
  } catch (error) {
    next(error);
  }
});

// Get current user
router.get('/me', protect, async (req, res, next) => {
  try {
    const user = req.user;

    res.json({
      success: true,
      traceId: req.traceId,
      data: {
        user: {
          id: user.user_id,
          username: user.username,
          email: user.email,
          role: user.role,
          gradeLevel: user.grade_level
        }
      }
    });
  } catch (error) {
    next(error);
  }
});

// Update profile
router.put('/me/profile', protect, async (req, res, next) => {
  try {
    const { error, value } = profileUpdateSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const userId = req.user.user_id;
    const { firstName, lastName, gradeLevel } = value;

    const updateFields = [];
    const values = [];
    let paramIndex = 1;

    if (firstName) {
      updateFields.push(`username = $${paramIndex++}`);
      values.push(firstName);
    }
    if (gradeLevel) {
      updateFields.push(`grade_level = $${paramIndex++}`);
      values.push(gradeLevel);
    }

    if (updateFields.length === 0) {
      return res.status(400).json({
        success: false,
        message: 'No fields to update',
        traceId: req.traceId
      });
    }

    updateFields.push(`updated_at = CURRENT_TIMESTAMP`);
    values.push(userId);

    await query(
      `UPDATE users SET ${updateFields.join(', ')} WHERE user_id = $${paramIndex}`,
      values
    );

    // Clear cache
    await redis.del(`user_${userId}`);

    res.json({
      success: true,
      message: 'Profile updated successfully',
      traceId: req.traceId
    });
  } catch (error) {
    next(error);
  }
});

// Change password
router.put('/me/password', protect, async (req, res, next) => {
  try {
    const { error, value } = passwordChangeSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message,
        traceId: req.traceId
      });
    }

    const { currentPassword, newPassword } = value;
    const userId = req.user.user_id;

    // Get current password hash
    const result = await query(
      'SELECT password_hash FROM users WHERE user_id = $1',
      [userId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'User not found',
        traceId: req.traceId
      });
    }

    // Verify current password
    const isCurrentPasswordValid = await bcrypt.compare(currentPassword, result.rows[0].password_hash);
    if (!isCurrentPasswordValid) {
      return res.status(400).json({
        success: false,
        message: 'Current password is incorrect',
        traceId: req.traceId
      });
    }

    // Hash new password
    const salt = await bcrypt.genSalt(10);
    const hashedNewPassword = await bcrypt.hash(newPassword, salt);

    // Update password
    await query(
      'UPDATE users SET password_hash = $1, updated_at = CURRENT_TIMESTAMP WHERE user_id = $2',
      [hashedNewPassword, userId]
    );

    res.json({
      success: true,
      message: 'Password changed successfully',
      traceId: req.traceId
    });
  } catch (error) {
    next(error);
  }
});

// Logout
router.post('/logout', protect, async (req, res, next) => {
  try {
    // Get token from header
    const token = req.headers.authorization?.split(' ')[1];
    
    if (token) {
      // Add token to blacklist
      const decoded = jwt.decode(token);
      const expiresIn = decoded.exp - Math.floor(Date.now() / 1000);
      
      if (expiresIn > 0) {
        await redis.set(`blacklist_${token}`, 'true', expiresIn);
      }
    }

    // Clear user cache
    await redis.del(`user_${req.user.user_id}`);

    res.json({
      success: true,
      message: 'Logged out successfully',
      traceId: req.traceId
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
