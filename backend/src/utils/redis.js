const redis = require('redis');

let client;

const connectRedis = async () => {
  try {
    client = redis.createClient({
      url: process.env.REDIS_URL || 'redis://localhost:6379',
      retry_unfulfilled_commands: true,
      retry_delay: (attempt) => Math.min(attempt * 50, 500),
    });

    client.on('error', (error) => {
      console.error('❌ Redis connection error:', error);
    });

    client.on('connect', () => {
      console.log('✅ Connected to Redis');
    });

    client.on('reconnecting', () => {
      console.log('🔄 Reconnecting to Redis...');
    });

    await client.connect();
    
    // Test the connection
    await client.ping();
    
    return client;
  } catch (error) {
    console.error('❌ Error connecting to Redis:', error.message);
    // Redis is optional, so we don't throw here
    console.log('⚠️ Continuing without Redis cache');
    return null;
  }
};

const getClient = () => {
  return client;
};

const get = async (key) => {
  if (!client) return null;
  try {
    return await client.get(key);
  } catch (error) {
    console.error('Redis GET error:', error);
    return null;
  }
};

const set = async (key, value, expireInSeconds = 3600) => {
  if (!client) return false;
  try {
    await client.setEx(key, expireInSeconds, value);
    return true;
  } catch (error) {
    console.error('Redis SET error:', error);
    return false;
  }
};

const del = async (key) => {
  if (!client) return false;
  try {
    await client.del(key);
    return true;
  } catch (error) {
    console.error('Redis DEL error:', error);
    return false;
  }
};

const exists = async (key) => {
  if (!client) return false;
  try {
    const result = await client.exists(key);
    return result === 1;
  } catch (error) {
    console.error('Redis EXISTS error:', error);
    return false;
  }
};

module.exports = {
  connectRedis,
  getClient,
  get,
  set,
  del,
  exists
};