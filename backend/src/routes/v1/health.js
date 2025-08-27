const express = require('express');
const { query } = require('../../utils/database');
const { mongoose } = require('../../utils/mongodb');
const { getClient } = require('../../utils/redis');

const router = express.Router();

// Health check endpoint
router.get('/', async (req, res) => {
  try {
    const health = {
      status: 'OK',
      timestamp: new Date().toISOString(),
      traceId: req.traceId,
      services: {
        postgres: 'unknown',
        mongodb: 'unknown',
        redis: 'unknown'
      }
    };

    // Check PostgreSQL
    try {
      await query('SELECT 1');
      health.services.postgres = 'healthy';
    } catch (error) {
      health.services.postgres = 'unhealthy';
      health.status = 'DEGRADED';
    }

    // Check MongoDB
    try {
      await mongoose.connection.db.admin().ping();
      health.services.mongodb = 'healthy';
    } catch (error) {
      health.services.mongodb = 'unhealthy';
      health.status = 'DEGRADED';
    }

    // Check Redis
    try {
      const redisClient = getClient();
      if (redisClient && redisClient.isReady) {
        await redisClient.ping();
        health.services.redis = 'healthy';
      } else {
        health.services.redis = 'unhealthy';
        health.status = 'DEGRADED';
      }
    } catch (error) {
      health.services.redis = 'unhealthy';
      health.status = 'DEGRADED';
    }

    const statusCode = health.status === 'OK' ? 200 : 503;
    res.status(statusCode).json(health);
  } catch (error) {
    res.status(500).json({
      status: 'ERROR',
      timestamp: new Date().toISOString(),
      traceId: req.traceId,
      error: error.message
    });
  }
});

module.exports = router;
