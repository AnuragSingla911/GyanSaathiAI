import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
} from '@mui/material';
import { Person, AccountCircle } from '@mui/icons-material';

const ProfilePage: React.FC = () => {
  return (
    <Box>
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <Person color="primary" />
        <Typography variant="h4" fontWeight="bold">
          Profile & Settings
        </Typography>
      </Box>

      <Card>
        <CardContent sx={{ textAlign: 'center', py: 8 }}>
          <AccountCircle sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            Profile Management Coming Soon!
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            Customize your learning experience with personalized settings,
            preferences, and profile management features.
          </Typography>
          <Box display="flex" gap={1} justifyContent="center" mb={3}>
            <Chip label="Personal Settings" color="primary" />
            <Chip label="Learning Preferences" color="secondary" />
            <Chip label="Account Management" color="success" />
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default ProfilePage;