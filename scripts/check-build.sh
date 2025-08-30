#!/bin/bash

echo "🔍 Checking if the project can build successfully..."

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Try to build just the frontend to check for compilation errors
echo "🏗️  Attempting to build frontend..."
if docker-compose build frontend 2>&1 | grep -q "ERROR"; then
    echo "❌ Frontend build failed. Check the errors above."
    echo ""
    echo "🔧 Common issues to fix:"
    echo "   1. Missing dependencies in package.json"
    echo "   2. TypeScript compilation errors"
    echo "   3. Missing component files"
    echo "   4. Import/export issues"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Fix the compilation errors shown above"
    echo "   2. Run this script again to verify"
    echo "   3. Once successful, run the full docker-test.sh"
    exit 1
else
    echo "✅ Frontend build successful!"
    echo ""
    echo "🎉 The project should now build successfully!"
    echo "🚀 You can now run: ./scripts/docker-test.sh"
fi
