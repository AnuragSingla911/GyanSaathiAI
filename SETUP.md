# AI Tutor - Simple Setup Guide

## 🚀 Quick Start

### 1. Start Services
```bash
docker-compose up -d
```

### 2. Wait for Services to Be Ready
```bash
# Check all services are running
docker-compose ps

# Wait for PostgreSQL to be ready
docker-compose exec postgres pg_isready -U tutor_user -d tutor_db
```

### 3. Setup Corpus (One-time setup)
```bash
# Ingest sample corpus data
curl -X POST "http://localhost:8000/ingestSampleCorpus"
```

### 4. Generate Questions (Optional)
```bash
# Generate a sample question
curl -X POST "http://localhost:8000/admin/generate/question" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "math",
    "topic": "linear equations",
    "class_level": "8",
    "difficulty": "medium",
    "question_type": "multiple_choice"
  }'
```

### 5. Create Student Account
```bash
# Register a student
curl -X POST "http://localhost:5000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test_student",
    "email": "test@example.com",
    "password": "password123",
    "firstName": "Test",
    "lastName": "Student",
    "gradeLevel": 8,
    "preferredSubjects": ["math"]
  }'
```

## 🎯 What This Does

✅ **Starts all services** (Frontend, Backend, Agent, Databases)  
✅ **Populates corpus** with sample educational content  
✅ **Creates vector embeddings** for semantic search  
✅ **Sets up student account** for testing  

## 🔍 Verify Setup

### Check Service Health
```bash
# Backend health
curl http://localhost:5000/api/v1/health

# Agent health
curl http://localhost:8000/health

# Frontend (via nginx)
curl http://localhost
```

### Test Question Generation
```bash
# Generate a question
curl -X POST "http://localhost:8000/admin/generate/question" \
  -H "Content-Type: application/json" \
  -d '{"subject": "math", "topic": "algebra", "class_level": "8"}'
```

### Test Student Access
```bash
# Login and get token
TOKEN=$(curl -s -X POST "http://localhost:5000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}' | jq -r '.data.token')

# Fetch questions
curl -X GET "http://localhost:5000/api/v1/questions/generate?subject=math&topic=algebra&limit=3" \
  -H "Authorization: Bearer $TOKEN"
```

## 🗄️ Database Status

### Check PostgreSQL Tables
```bash
docker-compose exec postgres psql -U tutor_user -d tutor_db -c "\dt"
```

### Check MongoDB Collections
```bash
docker-compose exec mongodb mongosh --eval "use tutor_content; show collections"
```

### Check Redis
```bash
docker-compose exec redis redis-cli ping
```

## 🧹 Cleanup

### Stop Services
```bash
docker-compose down
```

### Remove All Data
```bash
docker-compose down -v
docker volume prune -f
```

## 📝 Notes

- **First run**: May take 2-3 minutes for all services to start
- **Corpus setup**: Only needed once, unless you want to reset
- **API endpoints**: All functionality available through REST APIs
- **No complex scripts**: Everything done through simple HTTP requests

## 🆘 Troubleshooting

### Service Not Starting
```bash
# Check logs
docker-compose logs <service_name>

# Restart specific service
docker-compose restart <service_name>
```

### Database Connection Issues
```bash
# Check if PostgreSQL is ready
docker-compose exec postgres pg_isready -U tutor_user -d tutor_db

# Check if MongoDB is ready
docker-compose exec mongodb mongosh --eval "db.runCommand('ping')"
```

### Import Errors
- Ensure all services are running: `docker-compose ps`
- Check service logs: `docker-compose logs`
- Restart services if needed: `docker-compose restart`
