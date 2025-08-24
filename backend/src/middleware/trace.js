const { v4: uuidv4 } = require('uuid');

module.exports = (req, res, next) => {
  // Generate trace ID for request tracking
  req.traceId = req.headers['x-trace-id'] || uuidv4();
  
  // Add trace ID to response headers
  res.setHeader('X-Trace-ID', req.traceId);
  
  // Add to req object for use in controllers
  req.meta = {
    traceId: req.traceId,
    timestamp: new Date().toISOString(),
    ip: req.ip,
    userAgent: req.get('User-Agent')
  };
  
  next();
};
