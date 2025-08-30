import React, { useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  LinearProgress,
  Chip,
  Avatar,
  Paper,
  Skeleton,
  Alert,
} from '@mui/material';
import {
  TrendingUp,
  Quiz,
  EmojiEvents,
  School,
  PlayArrow,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../contexts/AuthContext';
import { useDashboard } from '../contexts/DashboardContext';

const DashboardPage: React.FC = () => {
  console.log('DashboardPage: Component starting to render');
  
  const navigate = useNavigate();
  const { user } = useAuth();
  const { stats, loading, error, refreshDashboard } = useDashboard();

  console.log('DashboardPage: Hooks initialized', { user, stats, loading, error });

  useEffect(() => {
    console.log('DashboardPage: useEffect triggered', { userId: user?.user_id });
    if (user?.user_id) {
      refreshDashboard();
    }
  }, [user?.user_id, refreshDashboard]);

  console.log('DashboardPage: Before conditional renders', { loading, error, stats });

  // Show loading state
  if (loading) {
    console.log('DashboardPage: Showing loading skeleton');
    return <DashboardSkeleton />;
  }

  // Show error state with retry option
  if (error) {
    console.log('DashboardPage: Showing error state');
    return (
      <Box>
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
          <Button onClick={refreshDashboard} sx={{ ml: 2 }}>
            Retry
          </Button>
        </Alert>
      </Box>
    );
  }

  // Show fallback when no stats (this should not happen with our updated context)
  if (!stats) {
    console.log('DashboardPage: No stats available, showing loading message');
    return (
      <Box>
        <Alert severity="info">
          Loading dashboard data...
        </Alert>
      </Box>
    );
  }

  console.log('DashboardPage: Rendering main dashboard with stats', stats);

  const accuracy = stats.overall.totalQuestions > 0 
    ? Math.round((stats.overall.totalCorrect / stats.overall.totalQuestions) * 100) 
    : 0;

  // Get recent subjects from progress data
  const recentSubjects = stats.progress.bySubject 
    ? Object.keys(stats.progress.bySubject).slice(0, 3)
    : ['Math', 'Physics', 'Chemistry']; // Fallback

  // Get recent activity for display
  const recentActivity = stats.recentActivity.slice(0, 3).map((activity: any) => ({
    subject: 'Quiz', // We don't have subject info in recent activity
    topic: 'Practice',
    score: Math.round(activity.accuracy),
    date: activity.date,
  }));

  // Calculate weekly progress (simplified - using total questions as weekly goal)
  const weeklyGoal = Math.max(10, Math.ceil(stats.overall.totalQuestions / 4)); // Dynamic goal
  const weeklyProgress = Math.min(stats.overall.totalQuestions, weeklyGoal);

  return (
    <Box>
      {/* Welcome Section */}
      <Paper sx={{ p: 3, mb: 3, background: 'linear-gradient(135deg, #1976d2 0%, #42a5f5 100%)', color: 'white' }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={8}>
            <Typography variant="h4" fontWeight="bold" gutterBottom>
              Welcome back, {user?.email}! 👋
            </Typography>
            <Typography variant="h6" sx={{ opacity: 0.9 }}>
              Ready to continue your learning journey? You're doing great!
            </Typography>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box display="flex" justifyContent={{ xs: 'center', md: 'flex-end' }}>
              <Button
                variant="contained"
                size="large"
                startIcon={<PlayArrow />}
                onClick={() => navigate('/quiz')}
                sx={{
                  bgcolor: 'rgba(255, 255, 255, 0.2)',
                  '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.3)' },
                  backdropFilter: 'blur(10px)',
                }}
              >
                Start New Quiz
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      <Grid container spacing={3}>
        {/* Stats Cards */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Total Quizzes
                  </Typography>
                  <Typography variant="h4" fontWeight="bold">
                    {stats.overall.totalAttempts}
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'primary.light' }}>
                  <Quiz />
                </Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Accuracy Rate
                  </Typography>
                  <Typography variant="h4" fontWeight="bold" color="success.main">
                    {accuracy}%
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'success.light' }}>
                  <TrendingUp />
                </Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Current Streak
                  </Typography>
                  <Typography variant="h4" fontWeight="bold" color="warning.main">
                    {stats.overall.currentStreak}
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'warning.light' }}>
                  <EmojiEvents />
                </Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Mastery Level
                  </Typography>
                  <Typography variant="h4" fontWeight="bold" color="info.main">
                    {Math.round(stats.overall.averageMastery * 100)}%
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'info.light' }}>
                  <School />
                </Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Weekly Progress */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Weekly Progress
              </Typography>
              <Box display="flex" alignItems="center" gap={2} mb={2}>
                <Typography variant="body2" color="text.secondary">
                  {weeklyProgress} / {weeklyGoal} questions
                </Typography>
                <Chip 
                  label={`${Math.round((weeklyProgress / weeklyGoal) * 100)}%`}
                  size="small"
                  color="primary"
                />
              </Box>
              <LinearProgress
                variant="determinate"
                value={(weeklyProgress / weeklyGoal) * 100}
                sx={{ height: 8, borderRadius: 4 }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Keep going! You're {weeklyGoal - weeklyProgress} questions away from your weekly goal.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Quick Actions */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quick Start
              </Typography>
              <Box display="flex" flexDirection="column" gap={1}>
                {recentSubjects.map((subject) => (
                  <Button
                    key={subject}
                    variant="outlined"
                    startIcon={<School />}
                    onClick={() => navigate(`/quiz?subject=${subject.toLowerCase()}`)}
                    fullWidth
                  >
                    {subject} Quiz
                  </Button>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Activity */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Activity
              </Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                {recentActivity.length > 0 ? (
                  recentActivity.map((activity, index) => (
                    <Box
                      key={index}
                      display="flex"
                      alignItems="center"
                      justifyContent="space-between"
                      p={2}
                      bgcolor="background.default"
                      borderRadius={2}
                    >
                      <Box>
                        <Typography variant="subtitle2" fontWeight="bold">
                          {activity.subject} - {activity.topic}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(activity.date).toLocaleDateString()}
                        </Typography>
                      </Box>
                      <Chip
                        label={`${activity.score}%`}
                        color={activity.score >= 90 ? 'success' : activity.score >= 70 ? 'warning' : 'error'}
                        size="small"
                      />
                    </Box>
                  ))
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                    No recent activity. Start taking quizzes to see your progress!
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Achievements */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Achievements
              </Typography>
              <Box display="flex" flexDirection="column" gap={1}>
                {getAchievements(stats).map((achievement, index) => (
                  <Box
                    key={index}
                    display="flex"
                    alignItems="center"
                    gap={2}
                    p={1}
                    borderRadius={1}
                    sx={{
                      opacity: achievement.earned ? 1 : 0.5,
                      bgcolor: achievement.earned ? 'success.light' : 'grey.100',
                    }}
                  >
                    <Typography fontSize="1.5rem">{achievement.icon}</Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        textDecoration: achievement.earned ? 'none' : 'line-through',
                      }}
                    >
                      {achievement.name}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

// Helper function to determine achievements based on progress
const getAchievements = (stats: any) => {
  const achievements = [
    { 
      name: 'First Quiz', 
      icon: '🎯', 
      earned: stats.overall.totalAttempts > 0 
    },
    { 
      name: 'Week Warrior', 
      icon: '🔥', 
      earned: stats.overall.currentStreak >= 7 
    },
    { 
      name: 'Perfect Score', 
      icon: '⭐', 
      earned: stats.overall.averageScore >= 100 
    },
    { 
      name: 'Speed Demon', 
      icon: '⚡', 
      earned: stats.overall.totalQuestions >= 50 
    },
  ];
  return achievements;
};

// Loading skeleton component
const DashboardSkeleton: React.FC = () => (
  <Box>
    <Paper sx={{ p: 3, mb: 3 }}>
      <Skeleton variant="text" width="60%" height={40} />
      <Skeleton variant="text" width="40%" height={30} />
    </Paper>
    
    <Grid container spacing={3}>
      {[...Array(4)].map((_, i) => (
        <Grid item xs={12} sm={6} md={3} key={i}>
          <Card>
            <CardContent>
              <Skeleton variant="text" width="50%" height={20} />
              <Skeleton variant="text" width="80%" height={40} />
            </CardContent>
          </Card>
        </Grid>
      ))}
      
      <Grid item xs={12} md={8}>
        <Card>
          <CardContent>
            <Skeleton variant="text" width="30%" height={30} />
            <Skeleton variant="rectangular" width="100%" height={20} sx={{ my: 2 }} />
            <Skeleton variant="text" width="80%" height={20} />
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={4}>
        <Card>
          <CardContent>
            <Skeleton variant="text" width="40%" height={30} />
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} variant="rectangular" width="100%" height={40} sx={{ my: 1 }} />
            ))}
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  </Box>
);

export default DashboardPage;