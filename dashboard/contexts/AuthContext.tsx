"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import axios from "axios";

export interface AuthUser {
  email: string;
  name: string;
  role: string;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
}

const AuthContext = React.createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEY = "mednexa_staff_session";
const TOKEN_KEY = "mednexa_staff_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const router = useRouter();

  React.useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setUser(JSON.parse(stored));
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(TOKEN_KEY);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
      const res = await axios.post(`${BASE_URL}/auth/login`, { email, password });
      const { access_token, user: staffUser } = res.data;

      setUser(staffUser);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(staffUser));
      localStorage.setItem(TOKEN_KEY, access_token);
      return { success: true };
    } catch (err: any) {
      // Fallback for offline demo mode
      if (email.trim().toLowerCase() === "admin@hospital.com" && password === "admin123") {
        const staffUser: AuthUser = {
          email: "admin@hospital.com",
          name: "Dr. Admin",
          role: "Hospital Staff",
        };
        setUser(staffUser);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(staffUser));
        return { success: true };
      }

      const msg =
        err.response?.data?.detail ??
        err.message ??
        "Invalid credentials. Use admin@hospital.com / admin123";
      return {
        success: false,
        error: msg,
      };
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(TOKEN_KEY);
    router.replace("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
