import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, AuthUser } from "../api/client";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  authConfigured: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authConfigured, setAuthConfigured] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const status = await api.authStatus();
      setAuthConfigured(status.configured);
      if (!status.configured) {
        setUser(null);
        return;
      }
      await api.csrf().catch(() => null);
      const me = await api.me();
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  async function signIn(email: string, password: string) {
    const loggedIn = await api.login(email, password);
    await api.csrf().catch(() => null);
    setUser(loggedIn);
  }

  async function signUp(email: string, password: string) {
    const result = await api.signup(email, password);
    if (result && "id" in result) {
      setUser(result);
    }
  }

  async function signOut() {
    await api.logout();
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, authConfigured, signIn, signUp, signOut, refresh }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
