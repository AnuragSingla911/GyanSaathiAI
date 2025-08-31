#!/bin/bash
set -e

echo "🏗️  Building GyanSaathiAI single container..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Build the image
echo "📦 Building Docker image..."
docker build -t ai-tutor:latest .

echo "✅ Build complete!"
echo ""
echo "🚀 To run the container:"
echo "docker run -d -p 80:80 --name ai-tutor ai-tutor:latest"
echo ""
echo "📊 Health check will be available at: http://localhost/api/v1/health"
echo "🌐 Frontend will be available at: http://localhost"
echo "🤖 Agent API will be available at: http://localhost/agent"
echo ""
echo "📝 To view logs:"
echo "docker logs -f ai-tutor"
echo ""
echo "🛑 To stop:"
echo "docker stop ai-tutor && docker rm ai-tutor"
