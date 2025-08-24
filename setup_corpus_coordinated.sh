#!/bin/bash

echo "🚀 Starting Coordinated Corpus Setup"
echo "====================================="

# Step 1: Stop the agent service to avoid collection conflicts
echo "1️⃣ Stopping agent service..."
docker-compose stop agent
echo "✅ Agent service stopped"

# Step 2: Wait a moment for cleanup
sleep 2

# Step 3: Run the corpus setup pipeline directly on host
echo "2️⃣ Running corpus setup pipeline..."
docker-compose exec -T postgres psql -U tutor_user -d tutor_db -c "SELECT 1;" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL is not ready, starting services..."
    docker-compose up -d postgres
    echo "⏳ Waiting for PostgreSQL to be ready..."
    until docker-compose exec -T postgres pg_isready -U tutor_user -d tutor_db; do
        sleep 1
    done
fi

# Run the corpus setup directly on host (since agent is stopped)
echo "⏳ Running corpus setup on host..."
cd agent && python scripts/setup_corpus_pipeline.py
if [ $? -eq 0 ]; then
    echo "✅ Corpus setup completed successfully"
else
    echo "❌ Corpus setup failed"
    exit 1
fi
cd ..

# Step 4: Start the agent service to use the populated collection
echo "3️⃣ Starting agent service..."
docker-compose up -d agent

# Step 5: Wait for agent to be ready
echo "⏳ Waiting for agent service to be ready..."
until curl -s http://localhost:8000/health > /dev/null; do
    sleep 2
done

echo "✅ Agent service is ready"

# Step 6: Test the generateQuestion endpoint
echo "4️⃣ Testing generateQuestion endpoint..."
curl -X POST "http://localhost:8000/admin/generate/question" \
  -H "Content-Type: application/json" \
  -d '{"subject": "math", "topic": "linear equations", "class_level": "8", "difficulty": "medium", "question_type": "multiple_choice"}' \
  | jq '.success, .error // "No error"'

echo ""
echo "🎉 Coordinated setup completed!"
echo "====================================="
echo "✅ Corpus populated with embeddings"
echo "✅ Agent service running with populated collection"
echo "✅ generateQuestion endpoint should now work"
