#!/bin/bash

set -e

echo "🐳 Testing TutorNestAI Docker Setup with GraphQL Migration"
echo "========================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "success" ]; then
        echo -e "${GREEN}✅ $message${NC}"
    elif [ "$status" = "error" ]; then
        echo -e "${RED}❌ $message${NC}"
    elif [ "$status" = "warning" ]; then
        echo -e "${YELLOW}⚠️  $message${NC}"
    elif [ "$status" = "info" ]; then
        echo -e "${BLUE}ℹ️  $message${NC}"
    fi
}

# Check if Docker is running
echo "🔍 Checking Docker status..."
if ! docker info >/dev/null 2>&1; then
    print_status "error" "Docker is not running. Please start Docker first."
    exit 1
fi
print_status "success" "Docker is running"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    print_status "error" "docker-compose is not installed or not in PATH"
    exit 1
fi
print_status "success" "docker-compose is available"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    print_status "info" "Creating .env file from template..."
    if [ -f env.example ]; then
        cp env.example .env
        print_status "success" "Created .env file"
    else
        print_status "warning" "No env.example found, creating basic .env"
        cat > .env << EOF
# TutorNestAI Environment Variables
NODE_ENV=development
OPENAI_API_KEY=your-openai-api-key-here
EOF
        print_status "success" "Created basic .env file"
    fi
fi

# Stop any existing containers
echo ""
echo "🛑 Stopping existing containers..."
docker-compose down --remove-orphans
print_status "success" "Stopped existing containers"

# Build and start services
echo ""
echo "🏗️  Building and starting services..."
docker-compose up --build -d

# Wait for services to start
echo ""
echo "⏳ Waiting for services to start..."
sleep 15

# Check service status
echo ""
echo "📊 Checking service status..."
docker-compose ps

# Test backend health
echo ""
echo "🔍 Testing backend health..."
max_attempts=30
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:5000/api/v1/health > /dev/null 2>&1; then
        print_status "success" "Backend API is healthy"
        break
    fi
    if [ $attempt -eq $max_attempts ]; then
        print_status "error" "Backend API failed to become healthy after $max_attempts attempts"
        echo "Backend logs:"
        docker-compose logs backend | tail -20
        exit 1
    fi
    echo "   Attempt $attempt/$max_attempts - Backend not ready yet..."
    sleep 2
    attempt=$((attempt + 1))
done

# Test GraphQL endpoint
echo ""
echo "🔍 Testing GraphQL endpoint..."
if curl -s http://localhost:5000/graphql > /dev/null 2>&1; then
    print_status "success" "GraphQL endpoint is accessible"
else
    print_status "error" "GraphQL endpoint is not accessible"
    echo "Backend logs:"
    docker-compose logs backend | tail -20
    exit 1
fi

# Test GraphQL introspection
echo ""
echo "🔍 Testing GraphQL schema introspection..."
INTROSPECTION_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"query IntrospectionQuery { __schema { types { name } } }"}' \
  http://localhost:5000/graphql)

if echo "$INTROSPECTION_RESPONSE" | grep -q "User\|Question\|QuizAttempt"; then
    print_status "success" "GraphQL schema introspection successful"
    echo "   Found types: $(echo "$INTROSPECTION_RESPONSE" | grep -o '"name":"[^"]*"' | head -5 | sed 's/"name":"//g' | sed 's/"//g' | tr '\n' ' ')"
else
    print_status "error" "GraphQL schema introspection failed"
    echo "   Response: $INTROSPECTION_RESPONSE"
    exit 1
fi

# Test frontend
echo ""
echo "🔍 Testing frontend..."
max_attempts=15
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        print_status "success" "Frontend is accessible"
        break
    fi
    if [ $attempt -eq $max_attempts ]; then
        print_status "error" "Frontend failed to become accessible after $max_attempts attempts"
        echo "Frontend logs:"
        docker-compose logs frontend | tail -20
        exit 1
    fi
    echo "   Attempt $attempt/$max_attempts - Frontend not ready yet..."
    sleep 2
    attempt=$((attempt + 1))
done

# Test agent service
echo ""
echo "🔍 Testing AI agent service..."
max_attempts=20
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        print_status "success" "AI agent service is healthy"
        break
    fi
    if [ $attempt -eq $max_attempts ]; then
        print_status "warning" "AI agent service failed to become healthy after $max_attempts attempts"
        echo "Agent logs:"
        docker-compose logs agent | tail -20
    fi
    echo "   Attempt $attempt/$max_attempts - Agent not ready yet..."
    sleep 2
    attempt=$((attempt + 1))
done

# Test database connections
echo ""
echo "🔍 Testing database connections..."
if docker-compose exec -T postgres pg_isready -U tutor_user -d tutor_db > /dev/null 2>&1; then
    print_status "success" "PostgreSQL is ready"
else
    print_status "error" "PostgreSQL is not ready"
fi

if docker-compose exec -T mongodb mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
    print_status "success" "MongoDB is ready"
else
    print_status "error" "MongoDB is not ready"
fi

if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    print_status "success" "Redis is ready"
else
    print_status "error" "Redis is not ready"
fi

# Final status
echo ""
echo "🎉 Docker setup test completed!"
echo ""
echo "🌐 Access Points:"
echo "  Frontend:      http://localhost:3000"
echo "  Backend API:   http://localhost:5000/api/v1/health"
echo "  GraphQL:       http://localhost:5000/graphql"
echo "  Agent API:     http://localhost:8000/health"
echo "  Full App:      http://localhost (via Nginx)"
echo ""
echo "🗄️  Databases:"
echo "  PostgreSQL:    localhost:5432"
echo "  MongoDB:       localhost:27017"
echo "  Redis:         localhost:6379"
echo ""
echo "📋 Useful Commands:"
echo "  View logs:     docker-compose logs -f [service]"
echo "  Stop all:      docker-compose down"
echo "  Rebuild:       docker-compose up --build"
echo "  Test GraphQL:  ./scripts/test-graphql.sh"
echo ""
echo "🧪 Next Steps:"
echo "  1. Open GraphQL Playground: http://localhost:5000/graphql"
echo "  2. Test the frontend: http://localhost:3000"
echo "  3. Try GraphQL mutations and queries"
echo "  4. Check the migration guide: GRAPHQL_MIGRATION.md"
