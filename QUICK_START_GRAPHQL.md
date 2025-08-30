# Quick Start: GraphQL Migration Testing

This guide will help you quickly test the GraphQL migration in the Docker environment.

## Prerequisites

- Docker and Docker Compose installed
- Git (to clone the repository)
- Basic understanding of GraphQL

## Quick Setup

### 1. Start the Environment

```bash
# Make scripts executable (if not already done)
chmod +x scripts/*.sh

# Run the comprehensive Docker test
./scripts/docker-test.sh
```

This script will:
- ✅ Check Docker status
- ✅ Build and start all services
- ✅ Test backend health
- ✅ Test GraphQL endpoint
- ✅ Test frontend accessibility
- ✅ Test database connections
- ✅ Provide access URLs and next steps

### 2. Alternative: Manual Start

```bash
# Start all services
docker-compose up --build -d

# Wait for services to be ready
sleep 15

# Check status
docker-compose ps
```

## Testing GraphQL

### 1. Access GraphQL Playground

Open your browser and go to: **http://localhost:5000/graphql**

You should see the Apollo GraphQL Playground interface.

### 2. Test Basic Queries

#### Test Schema Introspection
```graphql
query IntrospectionQuery {
  __schema {
    types {
      name
      description
    }
  }
}
```

#### Test Current User (Unauthenticated)
```graphql
query {
  me {
    user_id
    email
    role
  }
}
```
*Expected: Authentication error*

### 3. Test Authentication

#### Register a New User
```graphql
mutation RegisterUser($input: RegisterInput!) {
  register(input: $input) {
    user {
      user_id
      email
      role
    }
    token
  }
}
```

**Variables:**
```json
{
  "input": {
    "email": "test@example.com",
    "password": "password123",
    "confirmPassword": "password123"
  }
}
```

#### Login with User
```graphql
mutation LoginUser($input: LoginInput!) {
  login(input: $input) {
    user {
      user_id
      email
      role
    }
    token
  }
}
```

**Variables:**
```json
{
  "input": {
    "email": "test@example.com",
    "password": "password123"
  }
}
```

### 4. Test Authenticated Queries

After getting a token, you can test:

#### Get Current User (Authenticated)
```graphql
query {
  me {
    user_id
    email
    role
    createdAt
  }
}
```

#### Get Questions
```graphql
query {
  questions(limit: 5) {
    id
    stem
    status
    subject
    topic
  }
}
```

### 5. Test Quiz Operations

#### Start Quiz Attempt
```graphql
mutation StartQuizAttempt($input: QuizStartInput!) {
  startQuizAttempt(input: $input) {
    attemptId
    subject
    topic
    totalQuestions
    startedAt
  }
}
```

**Variables:**
```json
{
  "input": {
    "subject": "Mathematics",
    "topic": "Algebra",
    "totalQuestions": 5
  }
}
```

## Testing Frontend

### 1. Access Frontend

Open your browser and go to: **http://localhost:3000**

### 2. Test User Registration/Login

- Navigate to the registration page
- Create a new account
- Test login functionality
- Verify GraphQL operations in browser dev tools

### 3. Test Quiz Functionality

- Start a new quiz
- Answer questions
- Submit quiz
- Check progress tracking

## Troubleshooting

### Common Issues

#### 1. GraphQL Endpoint Not Accessible
```bash
# Check backend logs
docker-compose logs backend

# Check if backend is running
docker-compose ps backend
```

#### 2. Frontend Not Loading
```bash
# Check frontend logs
docker-compose logs frontend

# Verify environment variables
docker-compose exec frontend env | grep VITE
```

#### 3. Database Connection Issues
```bash
# Check database status
docker-compose ps postgres mongodb redis

# Test database connections
docker-compose exec postgres pg_isready -U tutor_user -d tutor_db
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"
docker-compose exec redis redis-cli ping
```

### Debug Mode

Enable debug logging in backend:

```bash
# Edit backend environment
docker-compose exec backend sh
# Then edit the environment variables or restart with debug mode
```

## Performance Testing

### 1. Test Query Performance

Use the GraphQL Playground to test complex queries:

```graphql
query ComplexQuery {
  progress(userId: "test-user-id") {
    overall {
      totalSkills
      averageMastery
      currentStreak
    }
    progress {
      bySubject {
        subject
        skillsCount
        accuracy
      }
    }
  }
}
```

### 2. Monitor Resource Usage

```bash
# Check container resource usage
docker stats

# Check specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Next Steps

After successful testing:

1. **Review the Migration Guide**: `GRAPHQL_MIGRATION.md`
2. **Explore the Schema**: Use GraphQL Playground introspection
3. **Test Real Scenarios**: Create actual quiz content and test user flows
4. **Performance Optimization**: Monitor and optimize slow queries
5. **Production Deployment**: Prepare for production environment

## Support

If you encounter issues:

1. Check the logs: `docker-compose logs [service]`
2. Verify environment variables
3. Check the migration documentation
4. Test individual services
5. Review the troubleshooting section above

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (optional - will delete data)
docker-compose down -v

# Remove images (optional)
docker-compose down --rmi all
```

---

**Happy Testing! 🚀**

The GraphQL migration provides a more efficient and scalable API architecture. Use the GraphQL Playground to explore the schema and test all operations before integrating with the frontend.
