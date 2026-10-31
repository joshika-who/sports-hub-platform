"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiFetch, NotificationItem, TokenResponse, User } from "@/lib/api";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  unreadCount: number;
  setSession: (tokenResp: TokenResponse) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
  refreshNotifications: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  loading: true,
  unreadCount: 0,
  setSession: () => {},
  logout: () => {},
  refreshUser: async () => {},
  refreshNotifications: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [unreadCount, setUnreadCount] = useState<number>(0);

  const refreshNotifications = useCallback(async () => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("sportshub_jwt") : null;
    if (!saved) {
      setUnreadCount(0);
      return;
    }
    try {
      const notifs = await apiFetch<NotificationItem[]>("/api/v1/notifications/me");
      setUnreadCount(notifs.filter((n) => !n.read).length);
    } catch {
      // ignore if token invalid
    }
  }, []);

  const refreshUser = useCallback(async () => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("sportshub_jwt") : null;
    if (!saved) {
      setUser(null);
      setToken(null);
      setLoading(false);
      return;
    }
    setToken(saved);
    try {
      const me = await apiFetch<User>("/api/v1/auth/me");
      setUser(me);
      await refreshNotifications();
    } catch {
      localStorage.removeItem("sportshub_jwt");
      setUser(null);
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, [refreshNotifications]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const setSession = (tokenResp: TokenResponse) => {
    localStorage.setItem("sportshub_jwt", tokenResp.access_token);
    setToken(tokenResp.access_token);
    setUser(tokenResp.user);
    refreshNotifications();
  };

  const logout = () => {
    localStorage.removeItem("sportshub_jwt");
    setToken(null);
    setUser(null);
    setUnreadCount(0);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        unreadCount,
        setSession,
        logout,
        refreshUser,
        refreshNotifications,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

