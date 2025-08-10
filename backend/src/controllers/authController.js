const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const Joi = require('joi');
const { query, transaction } = require('../utils/database');
const redis = require('../utils/redis');

// Validation schemas
const registerSchema = Joi.object({
  username: Joi.string().alphanum().min(3).max(30).required(),
  email: Joi.string().email().required(),
  password: Joi.string().min(6).required(),
  firstName: Joi.string().min(1).max(50).required(),
  lastName: Joi.string().min(1).max(50).required(),
  gradeLevel: Joi.number().integer().min(6).max(10).required(),
  preferredSubjects: Joi.array().items(Joi.string().valid('math', 'science', 'physics', 'chemistry', 'biology')).default([])
});

const loginSchema = Joi.object({
  email: Joi.string().email().required(),
  password: Joi.string().required()
});

const changePasswordSchema = Joi.object({
  currentPassword: Joi.string().required(),
  newPassword: Joi.string().min(6).required()
});

// Generate JWT token
const generateToken = (userId) => {
  return jwt.sign({ id: userId }, process.env.JWT_SECRET, {
    expiresIn: process.env.JWT_EXPIRES_IN || '7d'
  });
};

// @desc    Register user
// @route   POST /api/auth/register
// @access  Public
const register = async (req, res, next) => {
  try {
    // Validate input
    const { error, value } = registerSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message
      });
    }

    const { username, email, password, firstName, lastName, gradeLevel, preferredSubjects } = value;

    // Check if user already exists
    const existingUser = await query(
      'SELECT user_id FROM users WHERE email = $1 OR username = $2',
      [email, username]
    );

    if (existingUser.rows.length > 0) {
      return res.status(400).json({
        success: false,
        message: 'User already exists with this email or username'
      });
    }

    // Hash password
    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(password, salt);

    // Create user in transaction
    const result = await transaction(async (client) => {
      // Insert user
      const userResult = await client.query(
        `INSERT INTO users (username, email, password_hash, first_name, last_name, grade_level)
         VALUES ($1, $2, $3, $4, $5, $6)
         RETURNING user_id, username, email, first_name, last_name, role, grade_level, created_at`,
        [username, email, hashedPassword, firstName, lastName, gradeLevel]
      );

      const user = userResult.rows[0];

      // Insert user preferences
      await client.query(
        `INSERT INTO user_preferences (user_id, preferred_question_types, daily_goal_questions)
         VALUES ($1, $2, $3)`,
        [user.user_id, preferredSubjects, 10]
      );

      return user;
    });

    // Generate token
    const token = generateToken(result.user_id);

    // Cache user data
    await redis.set(`user_${result.user_id}`, JSON.stringify(result), 3600);

    res.status(201).json({
      success: true,
      message: 'User registered successfully',
      data: {
        token,
        user: {
          id: result.user_id,
          username: result.username,
          email: result.email,
          firstName: result.first_name,
          lastName: result.last_name,
          role: result.role,
          gradeLevel: result.grade_level,
          createdAt: result.created_at
        }
      }
    });
  } catch (error) {
    next(error);
  }
};

// @desc    Login user
// @route   POST /api/auth/login
// @access  Public
const login = async (req, res, next) => {
  try {
    // Validate input
    const { error, value } = loginSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message
      });
    }

    const { email, password } = value;

    // Check if user exists
    const result = await query(
      `SELECT user_id, username, email, password_hash, first_name, last_name, role, 
              grade_level, is_active, email_verified
       FROM users WHERE email = $1`,
      [email]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({
        success: false,
        message: 'Invalid credentials'
      });
    }

    const user = result.rows[0];

    // Check if user is active
    if (!user.is_active) {
      return res.status(401).json({
        success: false,
        message: 'Account is deactivated'
      });
    }

    // Check password
    const isPasswordValid = await bcrypt.compare(password, user.password_hash);
    if (!isPasswordValid) {
      return res.status(401).json({
        success: false,
        message: 'Invalid credentials'
      });
    }

    // Update last login
    await query(
      'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = $1',
      [user.user_id]
    );

    // Generate token
    const token = generateToken(user.user_id);

    // Cache user data
    const userData = {
      user_id: user.user_id,
      username: user.username,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      role: user.role,
      grade_level: user.grade_level
    };
    await redis.set(`user_${user.user_id}`, JSON.stringify(userData), 3600);

    res.json({
      success: true,
      message: 'Login successful',
      data: {
        token,
        user: {
          id: user.user_id,
          username: user.username,
          email: user.email,
          firstName: user.first_name,
          lastName: user.last_name,
          role: user.role,
          gradeLevel: user.grade_level,
          emailVerified: user.email_verified
        }
      }
    });
  } catch (error) {
    next(error);
  }
};

// @desc    Get current user
// @route   GET /api/auth/me
// @access  Private
const getMe = async (req, res, next) => {
  try {
    // User is already available from auth middleware
    const user = req.user;

    // Get user preferences
    const prefsResult = await query(
      `SELECT difficulty_level, preferred_question_types, study_goals, 
              daily_goal_questions, notifications_enabled, dark_mode
       FROM user_preferences WHERE user_id = $1`,
      [user.user_id]
    );

    const preferences = prefsResult.rows[0] || {};

    res.json({
      success: true,
      data: {
        user: {
          id: user.user_id,
          username: user.username,
          email: user.email,
          firstName: user.first_name,
          lastName: user.last_name,
          role: user.role,
          gradeLevel: user.grade_level,
          preferences
        }
      }
    });
  } catch (error) {
    next(error);
  }
};

// @desc    Update user profile
// @route   PUT /api/auth/profile
// @access  Private
const updateProfile = async (req, res, next) => {
  try {
    const userId = req.user.user_id;
    const { firstName, lastName, gradeLevel, preferences } = req.body;

    const result = await transaction(async (client) => {
      // Update user basic info
      if (firstName || lastName || gradeLevel) {
        const updateFields = [];
        const values = [];
        let paramIndex = 1;

        if (firstName) {
          updateFields.push(`first_name = $${paramIndex++}`);
          values.push(firstName);
        }
        if (lastName) {
          updateFields.push(`last_name = $${paramIndex++}`);
          values.push(lastName);
        }
        if (gradeLevel) {
          updateFields.push(`grade_level = $${paramIndex++}`);
          values.push(gradeLevel);
        }

        values.push(userId);
        
        await client.query(
          `UPDATE users SET ${updateFields.join(', ')}, updated_at = CURRENT_TIMESTAMP 
           WHERE user_id = $${paramIndex}`,
          values
        );
      }

      // Update preferences
      if (preferences) {
        const {
          difficultyLevel,
          preferredQuestionTypes,
          studyGoals,
          dailyGoalQuestions,
          notificationsEnabled,
          darkMode
        } = preferences;

        const prefUpdateFields = [];
        const prefValues = [];
        let prefParamIndex = 1;

        if (difficultyLevel) {
          prefUpdateFields.push(`difficulty_level = $${prefParamIndex++}`);
          prefValues.push(difficultyLevel);
        }
        if (preferredQuestionTypes) {
          prefUpdateFields.push(`preferred_question_types = $${prefParamIndex++}`);
          prefValues.push(preferredQuestionTypes);
        }
        if (studyGoals) {
          prefUpdateFields.push(`study_goals = $${prefParamIndex++}`);
          prefValues.push(studyGoals);
        }
        if (dailyGoalQuestions) {
          prefUpdateFields.push(`daily_goal_questions = $${prefParamIndex++}`);
          prefValues.push(dailyGoalQuestions);
        }
        if (notificationsEnabled !== undefined) {
          prefUpdateFields.push(`notifications_enabled = $${prefParamIndex++}`);
          prefValues.push(notificationsEnabled);
        }
        if (darkMode !== undefined) {
          prefUpdateFields.push(`dark_mode = $${prefParamIndex++}`);
          prefValues.push(darkMode);
        }

        if (prefUpdateFields.length > 0) {
          prefValues.push(userId);
          
          await client.query(
            `UPDATE user_preferences SET ${prefUpdateFields.join(', ')}, updated_at = CURRENT_TIMESTAMP 
             WHERE user_id = $${prefParamIndex}`,
            prefValues
          );
        }
      }

      // Get updated user data
      const userResult = await client.query(
        `SELECT u.user_id, u.username, u.email, u.first_name, u.last_name, u.role, u.grade_level,
                p.difficulty_level, p.preferred_question_types, p.study_goals, 
                p.daily_goal_questions, p.notifications_enabled, p.dark_mode
         FROM users u
         LEFT JOIN user_preferences p ON u.user_id = p.user_id
         WHERE u.user_id = $1`,
        [userId]
      );

      return userResult.rows[0];
    });

    // Update cache
    await redis.del(`user_${userId}`);

    res.json({
      success: true,
      message: 'Profile updated successfully',
      data: {
        user: {
          id: result.user_id,
          username: result.username,
          email: result.email,
          firstName: result.first_name,
          lastName: result.last_name,
          role: result.role,
          gradeLevel: result.grade_level,
          preferences: {
            difficultyLevel: result.difficulty_level,
            preferredQuestionTypes: result.preferred_question_types,
            studyGoals: result.study_goals,
            dailyGoalQuestions: result.daily_goal_questions,
            notificationsEnabled: result.notifications_enabled,
            darkMode: result.dark_mode
          }
        }
      }
    });
  } catch (error) {
    next(error);
  }
};

// @desc    Change password
// @route   PUT /api/auth/change-password
// @access  Private
const changePassword = async (req, res, next) => {
  try {
    // Validate input
    const { error, value } = changePasswordSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        success: false,
        message: error.details[0].message
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
        message: 'User not found'
      });
    }

    // Verify current password
    const isCurrentPasswordValid = await bcrypt.compare(currentPassword, result.rows[0].password_hash);
    if (!isCurrentPasswordValid) {
      return res.status(400).json({
        success: false,
        message: 'Current password is incorrect'
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
      message: 'Password changed successfully'
    });
  } catch (error) {
    next(error);
  }
};

// @desc    Logout user
// @route   POST /api/auth/logout
// @access  Private
const logout = async (req, res, next) => {
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
      message: 'Logged out successfully'
    });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  register,
  login,
  getMe,
  updateProfile,
  changePassword,
  logout
};