const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
require('dotenv').config();

const { connectPostgres } = require('./utils/database');
const { connectMongoDB } = require('./utils/mongodb');
const { connectRedis } = require('./utils/redis');
const errorHandler = require('./middleware/errorHandler');
// const traceMiddleware = require('./middleware/trace');

// Route imports (using original routes temporarily)
const authRoutes = require('./routes/auth');
const questionRoutes = require('./routes/v1/questions');
const quizRoutes = require('./routes/v1/quiz-attempts');
const progressRoutes = require('./routes/v1/progress');
const healthRoutes = require('./routes/v1/health');

const app = express();
const PORT = process.env.PORT || 5000;

// Security middleware
app.use(helmet());
app.use(cors({
  origin: process.env.NODE_ENV === 'production' 
    ? process.env.FRONTEND_URL 
    : ['http://localhost:3000', 'http://localhost:80', 'http://localhost'],
  credentials: true
}));

// Global rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP, please try again later.'
});
app.use('/api/', limiter);

// General middleware
app.use(compression());
app.use(morgan(process.env.NODE_ENV === 'production' ? 'combined' : 'dev'));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Tracing middleware (temporarily disabled)
// app.use(traceMiddleware);

// API routes (simplified for now)
app.use('/api/auth', authRoutes);
app.use('/api/content', require('./routes/content'));
// app.use('/api/quizzes', require('./routes/quizzes')); // REMOVED - conflicting with v1 route
app.use('/api/progress', require('./routes/progress'));
app.use('/api/users', require('./routes/users'));

// V1 API routes
app.use('/api/v1/questions', questionRoutes);
app.use('/api/v1/quiz-attempts', quizRoutes);
app.use('/api/v1/progress', progressRoutes);
app.use('/api/v1/health', healthRoutes);

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    success: false,
    message: 'Route not found'
  });
});

// Global error handler
app.use(errorHandler);

// Database connections and server startup
async function startServer() {
  try {
    // Connect to databases
    await connectPostgres();
    await connectMongoDB();
    await connectRedis();
    
    console.log('✅ All database connections established');
    
    // Start server
    app.listen(PORT, '0.0.0.0', () => {
      console.log(`🚀 Server running on port ${PORT} in ${process.env.NODE_ENV} mode`);
      console.log(`📊 Health check: http://localhost:${PORT}/api/v1/health`);
    });
  } catch (error) {
    console.error('❌ Failed to start server:', error.message);
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down gracefully');
  process.exit(0);
});

startServer();

module.exports = app;