#!/bin/bash

echo "🧪 Testing GraphQL Setup..."

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
until curl -s http://localhost:5000/api/v1/health > /dev/null; do
    echo "   Backend not ready yet, waiting..."
    sleep 2
done

echo "✅ Backend is ready!"

# Test GraphQL endpoint
echo "🔍 Testing GraphQL endpoint..."
if curl -s http://localhost:5000/graphql > /dev/null; then
    echo "✅ GraphQL endpoint is accessible"
else
    echo "❌ GraphQL endpoint is not accessible"
    exit 1
fi

# Test GraphQL introspection
echo "🔍 Testing GraphQL introspection..."
INTROSPECTION_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"query IntrospectionQuery { __schema { types { name } } }"}' \
  http://localhost:5000/graphql)

if echo "$INTROSPECTION_RESPONSE" | grep -q "User\|Question\|QuizAttempt"; then
    echo "✅ GraphQL schema introspection successful"
    echo "   Found types: $(echo "$INTROSPECTION_RESPONSE" | grep -o '"name":"[^"]*"' | head -5 | sed 's/"name":"//g' | sed 's/"//g' | tr '\n' ' ')"
else
    echo "❌ GraphQL schema introspection failed"
    echo "   Response: $INTROSPECTION_RESPONSE"
    exit 1
fi

# Test simple query
echo "🔍 Testing simple GraphQL query..."
QUERY_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"query { __typename }"}' \
  http://localhost:5000/graphql)

if echo "$QUERY_RESPONSE" | grep -q "Query"; then
    echo "✅ Basic GraphQL query successful"
else
    echo "❌ Basic GraphQL query failed"
    echo "   Response: $QUERY_RESPONSE"
    exit 1
fi

echo ""
echo "🎉 GraphQL setup is working correctly!"
echo ""
echo "🌐 You can now:"
echo "   1. Open GraphQL Playground: http://localhost:5000/graphql"
echo "   2. Test queries and mutations"
echo "   3. Use the frontend with GraphQL API"
echo ""
echo "📚 Example queries to try:"
echo "   - Get current user: query { me { user_id email role } }"
echo "   - Get questions: query { questions(limit: 5) { id stem status } }"
echo "   - Login: mutation { login(input: {email: \"test@example.com\", password: \"password123\"}) { user { email } token } }"
