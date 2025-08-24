#!/bin/bash

echo "🚀 Setting up AI Tutor Corpus with Embeddings"
echo "=============================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env.template .env
    echo "⚠️  Please edit .env file and add your OPENAI_API_KEY"
    echo "   Then run this script again"
    exit 1
fi

# Check if OPENAI_API_KEY is set
if ! grep -q "OPENAI_API_KEY=" .env || grep -q "OPENAI_API_KEY=your_actual_openai_api_key_here" .env; then
    echo "❌ Please set your OPENAI_API_KEY in the .env file"
    echo "   Edit .env and add: OPENAI_API_KEY=your_actual_key_here"
    exit 1
fi

# Load environment variables
echo "📋 Loading environment variables..."
export $(cat .env | grep -v '^#' | xargs)

# Check if services are running
echo "🔍 Checking if services are running..."
if ! docker-compose ps | grep -q "Up"; then
    echo "⚠️  Services are not running. Starting them..."
    docker-compose up -d
    echo "⏳ Waiting for services to be ready..."
    sleep 10
fi

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
until docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    echo "   Waiting for PostgreSQL..."
    sleep 2
done
echo "✅ PostgreSQL is ready"

# Install Python dependencies in the agent container
echo "📦 Installing Python dependencies in agent container..."
docker-compose exec -T agent pip install -r requirements.txt

# Run the corpus setup pipeline in the agent container
echo "🎯 Running corpus setup pipeline..."
docker-compose exec -T agent python scripts/setup_corpus_pipeline.py

# Verify the setup
echo "🔍 Verifying setup..."
docker-compose exec -T agent python scripts/verify_setup.py

echo "✅ Setup complete!"
