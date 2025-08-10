#!/bin/bash

# Wait for services to be ready

echo "Waiting for services to be ready..."

# Wait for PostgreSQL
echo "Checking PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U tutor_user -d tutor_db; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "PostgreSQL is ready!"

# Wait for MongoDB
echo "Checking MongoDB..."
until docker-compose exec -T mongodb mongosh --eval "db.adminCommand('ismaster')" >/dev/null 2>&1; do
  echo "MongoDB is unavailable - sleeping"
  sleep 2
done
echo "MongoDB is ready!"

# Wait for Backend API
echo "Checking Backend API..."
until curl -f http://localhost:5000/health >/dev/null 2>&1; do
  echo "Backend API is unavailable - sleeping"
  sleep 2
done
echo "Backend API is ready!"

# Wait for ML Service
echo "Checking ML Service..."
until curl -f http://localhost:8001/health >/dev/null 2>&1; do
  echo "ML Service is unavailable - sleeping"
  sleep 2
done
echo "ML Service is ready!"

# Wait for Frontend
echo "Checking Frontend..."
until curl -f http://localhost:3000 >/dev/null 2>&1; do
  echo "Frontend is unavailable - sleeping"
  sleep 2
done
echo "Frontend is ready!"

echo "All services are ready! 🚀"