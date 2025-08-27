# Dynamic Dashboard Setup

The dashboard has been updated to display real-time progress data instead of static mock data. Here's how to set it up and use it.

## What's New

### ✅ Dynamic Data
- **Real Progress Tracking**: Shows actual quiz attempts, accuracy rates, and mastery levels
- **Live Updates**: Dashboard refreshes with real data from the database
- **Progress Analytics**: Displays subject-wise and topic-wise progress
- **Achievement System**: Dynamic achievements based on actual performance

### ✅ Backend Integration
- **Progress API**: Uses `/api/v1/progress/:userId/progress` endpoint
- **Quiz Attempts**: Tracks completed quizzes and scores
- **Real-time Updates**: Progress updates automatically when quizzes are completed

## Setup Instructions

### 1. Database Setup
The dashboard requires the following tables to be properly set up:

```sql
-- progress_summary table (already exists in migrations)
-- quiz_attempts table (already exists in migrations)
-- users table with first_name, last_name fields
```

### 2. Backend Configuration
Ensure the V1 routes are enabled in `backend/src/index.js`:

```javascript
// V1 API routes
app.use('/api/v1/questions', questionRoutes);
app.use('/api/v1/quiz-attempts', quizRoutes);
app.use('/api/v1/progress', progressRoutes);
app.use('/api/v1/health', healthRoutes);
```

### 3. Start Using the System
That's it! The dashboard will automatically populate with real data as users:
- Take quizzes
- Answer questions
- Complete quiz attempts

No sample data needed - everything is real-time!

## Dashboard Features

### 📊 Statistics Cards
- **Total Quizzes**: Number of quiz attempts
- **Accuracy Rate**: Percentage of correct answers
- **Current Streak**: Consecutive successful attempts
- **Mastery Level**: Overall subject mastery percentage

### 📈 Weekly Progress
- Dynamic weekly goals based on user activity
- Visual progress bar showing completion status
- Motivational messages based on progress

### 🚀 Quick Actions
- Subject-specific quiz buttons based on recent activity
- Direct navigation to quiz creation

### 📝 Recent Activity
- Last 3 quiz attempts with scores
- Date and performance tracking
- Color-coded performance indicators

### 🏆 Achievements
- **First Quiz**: Complete your first quiz
- **Week Warrior**: 7-day streak
- **Perfect Score**: 100% accuracy
- **Speed Demon**: 50+ questions answered

## API Endpoints

### Progress Data
```
GET /api/v1/progress/:userId/progress
```

Returns:
- Overall statistics (attempts, accuracy, streaks)
- Subject-wise progress breakdown
- Topic-wise mastery levels
- Recent activity timeline

### Analytics
```
GET /api/v1/progress/:userId/analytics?timeframe=week|month|year
```

Returns:
- Performance over time
- Subject breakdown
- Difficulty progression

## Frontend Components

### DashboardContext
Provides dashboard data and refresh functionality:

```typescript
const { stats, loading, error, refreshDashboard } = useDashboard();
```

### useDashboardRefresh Hook
Simple hook for refreshing dashboard from anywhere:

```typescript
const refreshDashboard = useDashboardRefresh();
// Call refreshDashboard() after quiz completion
```

## Integration with Quiz System

The dashboard automatically updates when:
- Quiz attempts are completed
- Answers are submitted
- Progress is tracked

To manually refresh the dashboard after quiz completion:

```typescript
import { useDashboardRefresh } from '../hooks/useDashboardRefresh';

const QuizPage = () => {
  const refreshDashboard = useDashboardRefresh();
  
  const handleQuizComplete = async () => {
    // ... quiz completion logic
    await refreshDashboard(); // Refresh dashboard data
  };
};
```

## Troubleshooting

### Dashboard Shows "No Progress Data"
1. Ensure the user has completed at least one quiz
2. Check that the progress_summary table has data
3. Verify the progress API is working

### API Errors
1. Check that V1 routes are enabled
2. Verify database connection
3. Check user authentication

### Missing Fields
1. Ensure users table has first_name, last_name
2. Run database migrations if needed
3. Check table schema matches expected structure

## Performance Considerations

- Dashboard data is cached in context
- Automatic refresh on user login
- Manual refresh available for real-time updates
- Loading states and error handling included

## Future Enhancements

- Real-time WebSocket updates
- Advanced analytics and charts
- Personalized learning recommendations
- Social features and leaderboards
