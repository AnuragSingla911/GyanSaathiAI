#!/bin/bash

# Integration tests script

echo "Running integration tests..."

# Test Backend API endpoints
echo "Testing Backend API..."

# Health check
echo "✅ Testing health endpoint..."
curl -f http://localhost:5000/health || exit 1

# Test user registration (should fail without proper data, but endpoint should be accessible)
echo "✅ Testing auth endpoints accessibility..."
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{}' \
  -w "%{http_code}" -o /dev/null -s | grep -q "400" || exit 1

# Test ML Service endpoints
echo "Testing ML Service..."

# Health check
echo "✅ Testing ML service health endpoint..."
curl -f http://localhost:8001/health || exit 1

# Test metrics endpoint
echo "✅ Testing ML service metrics endpoint..."
curl -f http://localhost:8001/metrics || exit 1

# Test Frontend accessibility
echo "Testing Frontend..."

# Check if frontend is serving content
echo "✅ Testing frontend accessibility..."
curl -f http://localhost:3000 || exit 1

# Test database connections
echo "Testing Database Connections..."

# Test PostgreSQL connection
echo "✅ Testing PostgreSQL connection..."
docker-compose exec -T postgres psql -U tutor_user -d tutor_db -c "SELECT 1;" || exit 1

# Test MongoDB connection
echo "✅ Testing MongoDB connection..."
docker-compose exec -T mongodb mongosh tutor_content --eval "db.runCommand({ping: 1})" || exit 1

# Test Redis connection
echo "✅ Testing Redis connection..."
docker-compose exec -T redis redis-cli ping || exit 1

echo "All integration tests passed! ✅"