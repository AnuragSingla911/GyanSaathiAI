import React from 'react';
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
} from '@mui/material';
import {
  TrendingUp,
  Quiz,
  EmojiEvents,
  AccessTime,
  School,
  PlayArrow,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../contexts/AuthContext';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Mock data - in real app, this would come from API
  const mockStats = {
    totalQuizzes: 15,
    correctAnswers: 89,
    totalQuestions: 120,
    currentStreak: 7,
    weeklyGoal: 50,
    weeklyProgress: 35,
    recentSubjects: ['Math', 'Physics', 'Chemistry'],
    achievements: [
      { name: 'First Quiz', icon: '🎯', earned: true },
      { name: 'Week Warrior', icon: '🔥', earned: true },
      { name: 'Perfect Score', icon: '⭐', earned: false },
      { name: 'Speed Demon', icon: '⚡', earned: false },
    ],
    recentActivity: [
      { subject: 'Math', topic: 'Algebra', score: 95, date: '2024-01-15' },
      { subject: 'Physics', topic: 'Mechanics', score: 87, date: '2024-01-14' },
      { subject: 'Chemistry', topic: 'Atoms', score: 92, date: '2024-01-13' },
    ]
  };

  const accuracy = Math.round((mockStats.correctAnswers / mockStats.totalQuestions) * 100);

  return (
    <Box>
      {/* Welcome Section */}
      <Paper sx={{ p: 3, mb: 3, background: 'linear-gradient(135deg, #1976d2 0%, #42a5f5 100%)', color: 'white' }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={8}>
            <Typography variant="h4" fontWeight="bold" gutterBottom>
              Welcome back, {user?.firstName}! 👋
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
                    {mockStats.totalQuizzes}
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
                    {mockStats.currentStreak}
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
                    Study Time
                  </Typography>
                  <Typography variant="h4" fontWeight="bold" color="info.main">
                    2.5h
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'info.light' }}>
                  <AccessTime />
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
                  {mockStats.weeklyProgress} / {mockStats.weeklyGoal} questions
                </Typography>
                <Chip 
                  label={`${Math.round((mockStats.weeklyProgress / mockStats.weeklyGoal) * 100)}%`}
                  size="small"
                  color="primary"
                />
              </Box>
              <LinearProgress
                variant="determinate"
                value={(mockStats.weeklyProgress / mockStats.weeklyGoal) * 100}
                sx={{ height: 8, borderRadius: 4 }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Keep going! You're {mockStats.weeklyGoal - mockStats.weeklyProgress} questions away from your weekly goal.
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
                {mockStats.recentSubjects.map((subject) => (
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
                {mockStats.recentActivity.map((activity, index) => (
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
                ))}
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
                {mockStats.achievements.map((achievement, index) => (
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

export default DashboardPage;