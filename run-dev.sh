#!/bin/bash
set -e

echo "🚀 Starting TutorNestAI development environment..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "✏️  Please edit .env file to add your API keys (optional)"
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Build and start all services
echo "🏗️  Building and starting services..."
docker-compose up --build -d

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 10

# Show service status
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "✅ TutorNestAI is running!"
echo ""
echo "🌐 Access Points:"
echo "  Frontend:      http://localhost:3000"
echo "  Backend API:   http://localhost:5000/api/v1/health"
echo "  GraphQL:       http://localhost:5000/graphql"
echo "  Agent API:     http://localhost:8000/health"
echo "  Full App:      http://localhost (via Nginx)"
echo ""
echo "🗄️  Databases:"
echo "  PostgreSQL:    localhost:5432 (aitutor/postgres/postgres)"
echo "  MongoDB:       localhost:27017 (aitutor/admin/admin123)"
echo "  Redis:         localhost:6379"
echo ""
echo "📋 Commands:"
echo "  View logs:     docker-compose logs -f [service]"
echo "  Stop all:      docker-compose down"
echo "  Rebuild:       docker-compose up --build"
echo ""
echo "🧪 Test the AI Pipeline:"
echo "  1. Register: http://localhost:3000"
echo "  2. Create questions: POST http://localhost:5000/api/v1/questions"
echo "  3. Generate AI questions: POST http://localhost:8000/generate/question"
echo "  4. Take quiz: http://localhost:3000/quiz"
echo ""
echo "🔍 GraphQL Testing:"
echo "  1. Open GraphQL Playground: http://localhost:5000/graphql"
echo "  2. Test login mutation:"
echo "     mutation LoginUser(\$input: LoginInput!) {"
echo "       login(input: \$input) {"
echo "         user { user_id email role }"
echo "         token"
echo "       }"
echo "     }"
echo "  3. Test with variables: {\"input\": {\"email\": \"test@example.com\", \"password\": \"password123\"}}"
