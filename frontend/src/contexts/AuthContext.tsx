import React, { createContext, useContext, useEffect, useState } from 'react';
import toast from 'react-hot-toast';

import { useAuthAPI } from '../services/graphqlApi';
import { User, LoginCredentials, RegisterData } from '../types/auth';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  
  const {
    login: loginMutation,
    register: registerMutation,
    getCurrentUser,
    updateProfile: updateProfileMutation,
    logout: logoutMutation,
    loading: apiLoading
  } = useAuthAPI();

  // Check if user is authenticated on mount
  const { data: userData, loading: userLoading, error: userError } = getCurrentUser();

  // Initialize loading state
  useEffect(() => {
    if (!localStorage.getItem('token')) {
      setLoading(false);
    }
  }, []);

  // Handle user data changes
  useEffect(() => {
    if (userData?.me) {
      setUser(userData.me);
      setLoading(false);
    } else if (userError) {
      setUser(null);
      setLoading(false);
      // Remove token if it exists but is invalid
      localStorage.removeItem('token');
    }
  }, [userData, userError]);

  const login = async (credentials: LoginCredentials) => {
    try {
      const result = await loginMutation(credentials);
      setUser(result.user);
      toast.success('Welcome back!');
    } catch (error: any) {
      toast.error(error.message || 'Login failed');
      throw error;
    }
  };

  const register = async (data: RegisterData) => {
    try {
      const result = await registerMutation(data);
      setUser(result.user);
      toast.success('Account created successfully!');
    } catch (error: any) {
      toast.error(error.message || 'Registration failed');
      throw error;
    }
  };

  const logout = async () => {
    try {
      await logoutMutation();
      setUser(null);
      toast.success('Logged out successfully');
    } catch (error) {
      // Even if logout fails on server, clear local state
      setUser(null);
      toast.success('Logged out successfully');
    }
  };

  const updateProfile = async (data: Partial<User>) => {
    try {
      const result = await updateProfileMutation(data);
      setUser(result.user);
      toast.success('Profile updated successfully');
    } catch (error: any) {
      toast.error(error.message || 'Failed to update profile');
      throw error;
    }
  };

  const value: AuthContextType = {
    user,
    loading: loading || userLoading || apiLoading.login || apiLoading.register || apiLoading.updateProfile || apiLoading.logout,
    login,
    register,
    logout,
    updateProfile,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};