const jwt = require('jsonwebtoken');
const rateLimit = require('express-rate-limit');
const { query } = require('../utils/database');
const redis = require('../utils/redis');

// JWT protection middleware
const protect = async (req, res, next) => {
  try {
    let token;

    // Get token from header
    if (req.headers.authorization && req.headers.authorization.startsWith('Bearer')) {
      token = req.headers.authorization.split(' ')[1];
    }

    if (!token) {
      return res.status(401).json({
        success: false,
        message: 'Not authorized, no token'
      });
    }

    // Check if token is blacklisted
    const isBlacklisted = await redis.get(`blacklist_${token}`);
    if (isBlacklisted) {
      return res.status(401).json({
        success: false,
        message: 'Token is invalid'
      });
    }

    // Verify token
    const decoded = jwt.verify(token, process.env.JWT_SECRET);

    // Check if user still exists and get from cache or DB
    let user = await redis.get(`user_${decoded.id}`);
    if (user) {
      user = JSON.parse(user);
      console.log('Cached User data:', user);
    } else {
      const result = await query(
        'SELECT user_id, username, email, role, grade_level, is_active FROM users WHERE user_id = $1',
        [decoded.id]
      );

      if (result.rows.length === 0) {
        return res.status(401).json({
          success: false,
          message: 'User not found'
        });
      }

      user = result.rows[0];
      console.log('DB User data:', user);
      // Cache for future requests
      await redis.set(`user_${user.user_id}`, JSON.stringify(user), 3600);
    }

    console.log('user.is_active:', user.is_active, 'type:', typeof user.is_active);
    if (!user.is_active) {
      return res.status(401).json({
        success: false,
        message: 'User account is deactivated'
      });
    }

    req.user = user;
    next();
  } catch (error) {
    if (error.name === 'JsonWebTokenError') {
      return res.status(401).json({
        success: false,
        message: 'Not authorized, token failed'
      });
    }
    next(error);
  }
};

// Role-based access control
const authorize = (...roles) => {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({
        success: false,
        message: 'Not authorized'
      });
    }

    if (!roles.includes(req.user.role)) {
      return res.status(403).json({
        success: false,
        message: 'Not authorized for this resource'
      });
    }

    next();
  };
};

// Owner or admin access
const ownerOrAdmin = (userIdField = 'userId') => {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({
        success: false,
        message: 'Not authorized'
      });
    }

    const targetUserId = req.params[userIdField] || req.body[userIdField];
    
    if (req.user.role === 'admin' || req.user.user_id === targetUserId) {
      next();
    } else {
      return res.status(403).json({
        success: false,
        message: 'Not authorized for this resource'
      });
    }
  };
};

// Rate limiting middleware factory
const createRateLimit = (max, windowMs, message) => {
  return rateLimit({
    windowMs,
    max,
    message: {
      success: false,
      message: message || 'Too many requests, please try again later.'
    },
    standardHeaders: true,
    legacyHeaders: false,
  });
};

// Predefined rate limiters
const userRateLimit = (max, windowMs) => createRateLimit(max, windowMs);

module.exports = {
  protect,
  authorize,
  ownerOrAdmin,
  rateLimit: userRateLimit,
  createRateLimit
};