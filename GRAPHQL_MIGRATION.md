# GraphQL Migration Guide

This document outlines the migration from REST API to GraphQL for the AI Tutor application.

## Overview

The application has been migrated from a REST-based architecture to GraphQL, providing:

- **Single endpoint**: All data operations go through `/graphql`
- **Type safety**: Strong typing with GraphQL schema
- **Efficient queries**: Clients can request exactly what they need
- **Real-time updates**: Support for subscriptions (future enhancement)
- **Better developer experience**: GraphQL Playground for testing

## Backend Changes

### New Dependencies

```json
{
  "apollo-server-express": "^3.13.0",
  "graphql": "^16.8.1",
  "graphql-tag": "^2.12.6"
}
```

### GraphQL Server Setup

- **Location**: `backend/src/graphql/`
- **Schema**: `schema.js` - Defines all types and operations
- **Resolvers**: `resolvers.js` - Implements business logic
- **Server**: `server.js` - Apollo Server configuration

### Key Features

1. **Authentication**: JWT token-based auth with context extraction
2. **Error Handling**: Comprehensive error formatting and logging
3. **Scalar Types**: Custom DateTime and JSON scalar resolvers
4. **Performance**: Request logging and caching strategies

### Schema Structure

```graphql
# Core Types
User, Question, QuizAttempt, ProgressSummary

# Operations
Query: me, questions, quizAttempt, progress, analytics
Mutation: login, register, startQuizAttempt, saveAnswer
Subscription: quizProgress, questionUpdated (future)
```

## Frontend Changes

### New Dependencies

```json
{
  "@apollo/client": "^3.8.8",
  "graphql": "^16.8.1"
}
```

### Apollo Client Setup

- **Location**: `frontend/src/graphql/`
- **Client**: `client.ts` - Apollo Client configuration
- **Operations**: `operations.ts` - All GraphQL queries/mutations
- **API Service**: `graphqlApi.ts` - React hooks for GraphQL operations

### Key Features

1. **Authentication**: Automatic token injection via auth link
2. **Error Handling**: Global error handling with user-friendly messages
3. **Caching**: Intelligent cache policies for different data types
4. **Type Safety**: Full TypeScript support with generated types

### Migration from REST

| REST Endpoint | GraphQL Operation | Notes |
|---------------|-------------------|-------|
| `POST /api/auth/login` | `mutation LoginUser` | Direct replacement |
| `GET /api/v1/quiz-attempts/:id` | `query GetQuizAttempt` | More efficient data fetching |
| `PUT /api/v1/quiz-attempts/:id/items/:itemId` | `mutation SaveAnswer` | Better error handling |
| `GET /api/v1/progress/:userId` | `query GetProgress` | Flexible field selection |

## Environment Configuration

### Backend

```bash
# .env
JWT_SECRET=your-secret-key
NODE_ENV=development
```

### Frontend

```bash
# .env
VITE_GRAPHQL_URL=http://localhost:5000/graphql
VITE_API_URL=http://localhost:5000/api  # Fallback
```

## Development Workflow

### 1. Start Backend

```bash
cd backend
npm install
npm run dev
```

GraphQL Playground will be available at: `http://localhost:5000/graphql`

### 2. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Test GraphQL Operations

Use the GraphQL Playground to test queries and mutations:

```graphql
# Test login
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

# Variables
{
  "input": {
    "email": "test@example.com",
    "password": "password123"
  }
}
```

## Benefits of Migration

### 1. **Performance**
- Reduced over-fetching and under-fetching
- Efficient data loading with field selection
- Better caching strategies

### 2. **Developer Experience**
- Single endpoint for all operations
- Strong typing and validation
- Interactive documentation (GraphQL Playground)
- Better error messages

### 3. **Scalability**
- Easier to evolve API without breaking changes
- Better support for mobile and web clients
- Real-time capabilities with subscriptions

### 4. **Maintenance**
- Centralized schema management
- Easier to track API usage
- Better testing and debugging tools

## Future Enhancements

### 1. **Subscriptions**
- Real-time quiz progress updates
- Live question notifications
- Collaborative features

### 2. **Federation**
- Microservices architecture
- Service-specific schemas
- Unified GraphQL gateway

### 3. **Performance**
- Query complexity analysis
- Rate limiting per operation
- Advanced caching strategies

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Check JWT token in localStorage
   - Verify JWT_SECRET in backend .env
   - Check token expiration

2. **CORS Issues**
   - Verify CORS configuration in backend
   - Check frontend environment variables
   - Ensure proper origin settings

3. **Schema Errors**
   - Restart backend after schema changes
   - Check GraphQL Playground for errors
   - Verify resolver implementations

### Debug Mode

Enable debug logging in backend:

```javascript
// backend/src/graphql/server.js
const apolloServer = new ApolloServer({
  // ... other options
  debug: process.env.NODE_ENV === 'development',
  introspection: process.env.NODE_ENV !== 'production',
});
```

## Rollback Plan

If issues arise, the REST API endpoints remain available:

1. **Temporary**: Use REST endpoints while debugging GraphQL
2. **Configuration**: Switch via environment variable
3. **Gradual**: Migrate endpoints one by one

## Support

For issues or questions:

1. Check GraphQL Playground for schema validation
2. Review backend logs for resolver errors
3. Verify frontend Apollo Client configuration
4. Check network tab for GraphQL requests

## Conclusion

The GraphQL migration provides a more efficient, scalable, and developer-friendly API architecture. The benefits include better performance, improved developer experience, and future extensibility for real-time features and microservices.
