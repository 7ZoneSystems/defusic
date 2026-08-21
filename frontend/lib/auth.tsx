"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { API_BASE } from "./config";

interface CohesivityUser {
  id: number;
  email: string;
  name: string | null;
  picture: string | null;
}

interface AuthContextType {
  user: CohesivityUser | null;
  loading: boolean;
  login: (returnTo?: string) => void;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  keepSignedIn: boolean;
  setKeepSignedIn: (v: boolean) => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: () => {},
  logout: async () => {},
  refresh: async () => {},
  keepSignedIn: true,
  setKeepSignedIn: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CohesivityUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [keepSignedIn, setKeepSignedInState] = useState(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("hearbeat_keep_signed_in");
      return stored !== null ? stored === "true" : true;
    }
    return true;
  });

  const setKeepSignedIn = useCallback((v: boolean) => {
    setKeepSignedInState(v);
    localStorage.setItem("hearbeat_keep_signed_in", String(v));
  }, []);

  const checkAuth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (!user || loading) return;
    const stored = localStorage.getItem("hearbeat_keep_signed_in");
    if (stored === "true") {
      fetch(`${API_BASE}/auth/keep-session?keep=true`, {
        method: "POST",
        credentials: "include",
      }).catch(() => {});
    }
  }, [user, loading]);

  const login = useCallback((returnTo?: string) => {
    const rt = returnTo || window.location.pathname;
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = `${API_BASE}/auth/login?return_to=${encodeURIComponent(rt)}`;
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      setUser(null);
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/";
    }
  }, []);

  const refresh = useCallback(async () => {
    await checkAuth();
  }, [checkAuth]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh, keepSignedIn, setKeepSignedIn }}>
      {children}
    </AuthContext.Provider>
  );
}
