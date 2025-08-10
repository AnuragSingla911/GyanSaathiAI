import React from 'react';
import { Box, Typography, Card, CardContent, Button, Chip } from '@mui/material';
import { Quiz, PlayArrow } from '@mui/icons-material';

const QuizPage: React.FC = () => {
  return (
    <Box>
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <Quiz color="primary" />
        <Typography variant="h4" fontWeight="bold">
          Take a Quiz
        </Typography>
      </Box>

      <Card>
        <CardContent sx={{ textAlign: 'center', py: 8 }}>
          <Quiz sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            Quiz Feature Coming Soon!
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            We're working hard to bring you an amazing quiz experience with AI-generated questions,
            real-time feedback, and adaptive difficulty levels.
          </Typography>
          <Box display="flex" gap={1} justifyContent="center" mb={3}>
            <Chip label="AI-Generated Questions" color="primary" />
            <Chip label="Adaptive Difficulty" color="secondary" />
            <Chip label="Real-time Feedback" color="success" />
          </Box>
          <Button
            variant="contained"
            startIcon={<PlayArrow />}
            disabled
            size="large"
          >
            Start Quiz (Coming Soon)
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
};

export default QuizPage;