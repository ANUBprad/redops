import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatar_url?: string | null;
  status: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (email: string, displayName: string, password: string) => Promise<void>;
  isLoading: boolean;
  accessToken: string | null;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem("redops-access-token");
    const storedUser = localStorage.getItem("redops-user");
    if (storedToken && storedUser) {
      try {
        setAccessToken(storedToken);
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem("redops-access-token");
        localStorage.removeItem("redops-user");
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error("Login failed");
      const data = await res.json();
      setAccessToken(data.access_token);
      localStorage.setItem("redops-access-token", data.access_token);
      localStorage.setItem("redops-refresh-token", data.refresh_token);

      const meRes = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (meRes.ok) {
        const me = await meRes.json();
        setUser(me);
        localStorage.setItem("redops-user", JSON.stringify(me));
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (email: string, displayName: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, display_name: displayName, password }),
      });
      if (!res.ok) throw new Error("Registration failed");
      const data = await res.json();
      setAccessToken(data.access_token);
      localStorage.setItem("redops-access-token", data.access_token);
      localStorage.setItem("redops-refresh-token", data.refresh_token);

      const meRes = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (meRes.ok) {
        const me = await meRes.json();
        setUser(me);
        localStorage.setItem("redops-user", JSON.stringify(me));
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setAccessToken(null);
    localStorage.removeItem("redops-access-token");
    localStorage.removeItem("redops-refresh-token");
    localStorage.removeItem("redops-user");
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, register, isLoading, accessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useRequireAuth() {
  const { user, isLoading } = useAuth();
  return { user, isLoading, isAuthenticated: !!user };
}
