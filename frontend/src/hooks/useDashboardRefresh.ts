import { useCallback } from 'react';
import { useDashboard } from '../contexts/DashboardContext';

export const useDashboardRefresh = () => {
  const { refreshDashboard } = useDashboard();
  
  const refresh = useCallback(async () => {
    try {
      await refreshDashboard();
    } catch (error) {
      console.error('Failed to refresh dashboard:', error);
    }
  }, [refreshDashboard]);
  
  return refresh;
};
