// Auth state — persisted to localStorage
// Path: frontend/src/store/authStore.ts
"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";

interface AuthState {
  user:            User | null;
  accessToken:     string | null;
  refreshToken:    string | null;
  isAuthenticated: boolean;
  login:  (user: User, access: string, refresh: string) => void;
  logout: () => void;
  updateUser: (u: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null, accessToken: null, refreshToken: null, isAuthenticated: false,
      login: (user, access, refresh) => {
        if (typeof window !== "undefined") {
          localStorage.setItem("access_token",  access);
          localStorage.setItem("refresh_token", refresh);
        }
        set({ user, accessToken: access, refreshToken: refresh, isAuthenticated: true });
      },
      logout: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
        }
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
      },
      updateUser: (u) => set((s) => ({ user: s.user ? { ...s.user, ...u } : null })),
    }),
    {
      name: "tradeai-auth",
      partialize: (s) => ({ user: s.user, accessToken: s.accessToken, refreshToken: s.refreshToken, isAuthenticated: s.isAuthenticated }),
    }
  )
);
