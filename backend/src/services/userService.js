const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { v4: uuidv4 } = require('uuid');
const { query, transaction } = require('../utils/database');
const redis = require('../utils/redis');

class UserService {
  // Generate JWT token
  generateToken(userId) {
    return jwt.sign({ user_id: userId }, process.env.JWT_SECRET || 'your-secret-key', {
      expiresIn: process.env.JWT_EXPIRES_IN || '7d'
    });
  }

  // Register a new user
  async register({ username, email, password, firstName, lastName, gradeLevel, role = 'student' }) {
    try {
      // Check if user already exists
      const existingUser = await query(
        'SELECT user_id FROM users WHERE email = $1 OR username = $2',
        [email, username]
      );

      if (existingUser.rows.length > 0) {
        throw new Error('User already exists with this email or username');
      }

      // Hash password
      const salt = await bcrypt.genSalt(10);
      const hashedPassword = await bcrypt.hash(password, salt);

      // Create user
      const result = await transaction(async (client) => {
        const userResult = await client.query(
          `INSERT INTO users (username, email, password_hash, first_name, last_name, role, grade_level, is_active, email_verified)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           RETURNING user_id, username, email, first_name, last_name, role, grade_level, created_at`,
          [username, email, hashedPassword, firstName, lastName, role, gradeLevel, true, true]
        );

        return userResult.rows[0];
      });

      // Generate token
      const token = this.generateToken(result.user_id);

      // Cache user data
      await redis.set(`user_${result.user_id}`, JSON.stringify(result), 3600);

      return {
        user: {
          user_id: result.user_id,
          username: result.username,
          email: result.email,
          firstName: result.first_name,
          lastName: result.last_name,
          role: result.role,
          gradeLevel: result.grade_level,
          createdAt: result.created_at
        },
        token
      };
    } catch (error) {
      console.error('UserService: Error registering user:', error);
      throw error;
    }
  }

  // Login user
  async login({ email, password }) {
    try {
      // Find user by email
      const userResult = await query(
        'SELECT user_id, username, email, password_hash, first_name, last_name, role, grade_level FROM users WHERE email = $1 AND is_active = true',
        [email]
      );

      if (userResult.rows.length === 0) {
        throw new Error('Invalid credentials');
      }

      const user = userResult.rows[0];

      // Check password
      const isPasswordValid = await bcrypt.compare(password, user.password_hash);
      if (!isPasswordValid) {
        throw new Error('Invalid credentials');
      }

      // Generate token
      const token = this.generateToken(user.user_id);

      // Cache user data
      await redis.set(`user_${user.user_id}`, JSON.stringify(user), 3600);

      // Update last login
      await query(
        'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = $1',
        [user.user_id]
      );

      return {
        user: {
          user_id: user.user_id,
          username: user.username,
          email: user.email,
          firstName: user.first_name,
          lastName: user.last_name,
          role: user.role,
          gradeLevel: user.grade_level
        },
        token
      };
    } catch (error) {
      console.error('UserService: Error logging in user:', error);
      throw error;
    }
  }

  // Get current user
  async getCurrentUser(userId) {
    try {
      // Try to get from cache first
      const cachedUser = await redis.get(`user_${userId}`);
      if (cachedUser) {
        return JSON.parse(cachedUser);
      }

      // Get from database
      const userResult = await query(
        'SELECT user_id, username, email, first_name, last_name, role, grade_level, created_at FROM users WHERE user_id = $1 AND is_active = true',
        [userId]
      );

      if (userResult.rows.length === 0) {
        return null;
      }

      const user = userResult.rows[0];

      // Cache user data
      await redis.set(`user_${userId}`, JSON.stringify(user), 3600);

      return {
        user_id: user.user_id,
        username: user.username,
        email: user.email,
        firstName: user.first_name,
        lastName: user.last_name,
        role: user.role,
        gradeLevel: user.grade_level,
        createdAt: user.created_at
      };
    } catch (error) {
      console.error('UserService: Error getting current user:', error);
      throw error;
    }
  }

  // Update user profile
  async updateProfile(userId, updates) {
    try {
      const allowedFields = ['first_name', 'last_name', 'grade_level'];
      const updateFields = [];
      const values = [];
      let paramIndex = 1;

      for (const [key, value] of Object.entries(updates)) {
        if (allowedFields.includes(key) && value !== undefined) {
          updateFields.push(`${key} = $${paramIndex}`);
          values.push(value);
          paramIndex++;
        }
      }

      if (updateFields.length === 0) {
        throw new Error('No valid fields to update');
      }

      values.push(userId);
      updateFields.push('updated_at = CURRENT_TIMESTAMP');

      const result = await query(
        `UPDATE users SET ${updateFields.join(', ')} WHERE user_id = $${paramIndex} RETURNING *`,
        values
      );

      if (result.rows.length === 0) {
        throw new Error('User not found');
      }

      const updatedUser = result.rows[0];

      // Update cache
      await redis.set(`user_${userId}`, JSON.stringify(user), 3600);

      return {
        user_id: updatedUser.user_id,
        username: updatedUser.username,
        email: updatedUser.email,
        firstName: updatedUser.first_name,
        lastName: updatedUser.last_name,
        role: updatedUser.role,
        gradeLevel: updatedUser.grade_level,
        updatedAt: updatedUser.updated_at
      };
    } catch (error) {
      console.error('UserService: Error updating profile:', error);
      throw error;
    }
  }

  // Change password
  async changePassword(userId, { currentPassword, newPassword }) {
    try {
      // Get current password hash
      const userResult = await query(
        'SELECT password_hash FROM users WHERE user_id = $1',
        [userId]
      );

      if (userResult.rows.length === 0) {
        throw new Error('User not found');
      }

      const user = userResult.rows[0];

      // Verify current password
      const isCurrentPasswordValid = await bcrypt.compare(currentPassword, user.password_hash);
      if (!isCurrentPasswordValid) {
        throw new Error('Current password is incorrect');
      }

      // Hash new password
      const salt = await bcrypt.genSalt(10);
      const newPasswordHash = await bcrypt.hash(newPassword, salt);

      // Update password
      await query(
        'UPDATE users SET password_hash = $1, updated_at = CURRENT_TIMESTAMP WHERE user_id = $1',
        [newPasswordHash, userId]
      );

      return true;
    } catch (error) {
      console.error('UserService: Error changing password:', error);
      throw error;
    }
  }
}

module.exports = new UserService();
