const express = require('express');
const {
  register,
  login,
  getMe,
  updateProfile,
  changePassword,
  logout
} = require('../controllers/authController');
const { protect, rateLimit: userRateLimit } = require('../middleware/auth');

const router = express.Router();

// Public routes
router.post('/register', userRateLimit(5, 15 * 60 * 1000), register); // 5 registrations per 15 minutes
router.post('/login', userRateLimit(10, 15 * 60 * 1000), login); // 10 login attempts per 15 minutes

// Protected routes
router.get('/me', protect, getMe);
router.put('/profile', protect, updateProfile);
router.put('/change-password', protect, userRateLimit(3, 60 * 60 * 1000), changePassword); // 3 password changes per hour
router.post('/logout', protect, logout);

module.exports = router;