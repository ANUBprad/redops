import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

interface AuthContextValue {
  user: { id: string; email: string; name: string } | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthContextValue["user"]>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("redops-user");
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        localStorage.removeItem("redops-user");
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (_email: string, _password: string) => {
    setIsLoading(true);
    try {
      const mockUser = { id: "user-1", email: _email, name: _email.split("@")[0] ?? "User" };
      setUser(mockUser);
      localStorage.setItem("redops-user", JSON.stringify(mockUser));
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("redops-user");
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
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
