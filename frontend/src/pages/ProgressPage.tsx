import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
} from '@mui/material';
import { TrendingUp, Assessment } from '@mui/icons-material';

const ProgressPage: React.FC = () => {
  return (
    <Box>
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <TrendingUp color="primary" />
        <Typography variant="h4" fontWeight="bold">
          Your Progress
        </Typography>
      </Box>

      <Card>
        <CardContent sx={{ textAlign: 'center', py: 8 }}>
          <Assessment sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            Progress Tracking Coming Soon!
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            Track your learning journey with detailed analytics, performance insights,
            and personalized recommendations to help you improve.
          </Typography>
          <Box display="flex" gap={1} justifyContent="center" mb={3}>
            <Chip label="Performance Analytics" color="primary" />
            <Chip label="Learning Insights" color="secondary" />
            <Chip label="Goal Tracking" color="success" />
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default ProgressPage;