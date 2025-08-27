import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react';
import { progressAPI } from '../services/api';

interface DashboardStats {
  overall: {
    totalSkills: number;
    totalQuestions: number;
    totalCorrect: number;
    averageMastery: number;
    currentStreak: number;
    bestStreak: number;
    totalAttempts: number;
    completedAttempts: number;
    averageScore: number;
  };
  progress: {
    bySubject?: Record<string, any>;
    byTopic?: Record<string, any>;
    bySkill?: any[];
  };
  recentActivity: Array<{
    date: string;
    attempts: number;
    questionsAnswered: number;
    accuracy: number;
  }>;
}

interface DashboardContextType {
  stats: DashboardStats | null;
  loading: boolean;
  error: string | null;
  refreshDashboard: () => Promise<void>;
  clearError: () => void;
}

const DashboardContext = createContext<DashboardContextType | undefined>(undefined);

export const useDashboard = () => {
  const context = useContext(DashboardContext);
  if (context === undefined) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
};

interface DashboardProviderProps {
  children: ReactNode;
  userId: string;
}

export const DashboardProvider: React.FC<DashboardProviderProps> = ({ children, userId }) => {
  console.log('DashboardProvider: Initializing with userId:', userId);
  
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshDashboard = useCallback(async () => {
    console.log('DashboardProvider: refreshDashboard called with userId:', userId);
    if (!userId) {
      console.log('DashboardProvider: No userId, returning early');
      return;
    }
    
    try {
      console.log('DashboardProvider: Starting API call');
      setLoading(true);
      setError(null);
      const response = await progressAPI.getUserProgress(userId);
      console.log('DashboardProvider: API response received:', response);
      
      // Handle the response structure correctly
      if (response && response.overall) {
        console.log('DashboardProvider: Setting stats from API response');
        setStats(response);
      } else {
        console.log('DashboardProvider: No valid response, setting default stats');
        // If no data, set default empty stats
        setStats({
          overall: {
            totalSkills: 0,
            totalQuestions: 0,
            totalCorrect: 0,
            averageMastery: 0,
            currentStreak: 0,
            bestStreak: 0,
            totalAttempts: 0,
            completedAttempts: 0,
            averageScore: 0
          },
          progress: {
            bySubject: {},
            byTopic: {},
            bySkill: []
          },
          recentActivity: []
        });
      }
    } catch (err: any) {
      console.error('DashboardProvider: Failed to fetch dashboard data:', err);
      setError('Failed to load dashboard data. Please try again later.');
      
      // Set default empty stats on error
      setStats({
        overall: {
          totalSkills: 0,
          totalQuestions: 0,
          totalCorrect: 0,
          averageMastery: 0,
          currentStreak: 0,
          bestStreak: 0,
          totalAttempts: 0,
          completedAttempts: 0,
          averageScore: 0
        },
        progress: {
          bySubject: {},
          byTopic: {},
          bySkill: []
        },
        recentActivity: []
      });
    } finally {
      console.log('DashboardProvider: Setting loading to false');
      setLoading(false);
    }
  }, [userId]);

  // Auto-refresh on mount
  useEffect(() => {
    console.log('DashboardProvider: useEffect triggered, userId:', userId);
    if (userId) {
      refreshDashboard();
    }
  }, [userId, refreshDashboard]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value: DashboardContextType = {
    stats,
    loading,
    error,
    refreshDashboard,
    clearError,
  };

  console.log('DashboardProvider: Rendering with value:', value);

  return (
    <DashboardContext.Provider value={value}>
      {children}
    </DashboardContext.Provider>
  );
};
