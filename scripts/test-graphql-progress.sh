#!/bin/bash

echo "🧪 Testing GraphQL Progress Query"
echo "=================================="

# Test the progress query
echo "📊 Testing progress query for user a1cf6dec-aa62-4ed0-92d5-1d4d55b62fdd..."
echo ""

response=$(curl -s -X POST http://localhost:5000/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { progress(userId: \"a1cf6dec-aa62-4ed0-92d5-1d4d55b62fdd\") { overall { totalSkills totalQuestions totalCorrect averageMastery currentStreak bestStreak totalAttempts completedAttempts averageScore } progress { bySubject { subject skillsCount totalQuestions correctAnswers averageMastery accuracy } } recentActivity { date attempts questionsAnswered accuracy } } }"
  }')

echo "Response:"
echo "$response" | jq '.' 2>/dev/null || echo "$response"

echo ""
echo "✅ GraphQL Progress Query Test Complete!"
echo ""
echo "🌐 Next Steps:"
echo "   1. Open http://localhost:3000 in your browser"
echo "   2. Check the browser console for any GraphQL errors"
echo "   3. Try to access the dashboard to see if progress loads"
echo "   4. Check the Network tab to see GraphQL requests"
