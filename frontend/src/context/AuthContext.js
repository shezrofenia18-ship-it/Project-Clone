import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import api, { apiError } from "@/lib/api";
import { devWarn } from "@/lib/log";

const AuthContext = createContext(null);
const USER_KEY = "bam_user";

const readCachedUser = () => {
  try {
    const v = localStorage.getItem(USER_KEY);
    return v ? JSON.parse(v) : null;
  } catch (e) {
    devWarn("auth.readCachedUser", e);
    return null;
  }
};

const writeCachedUser = (u) => {
  try { localStorage.setItem(USER_KEY, JSON.stringify(u)); }
  catch (e) { devWarn("auth.writeCachedUser - kemungkinan kuota localStorage penuh", e); }
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=not authed
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("bam_token");
    if (!token) {
      setUser(false);
      setLoading(false);
      return;
    }
    const cached = readCachedUser();
    api.get("/auth/me")
      .then((r) => { setUser(r.data); writeCachedUser(r.data); })
      .catch((e) => {
        // A network error means we are offline, NOT that the session is invalid.
        // Logging the cashier out here would make offline selling impossible,
        // so we keep working from the cached profile. Only a real server
        // rejection (401/403) clears the session.
        if (!e.response && cached) {
          setUser(cached);
          return;
        }
        localStorage.removeItem("bam_token");
        localStorage.removeItem(USER_KEY);
        setUser(false);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username, password) => {
    try {
      const { data } = await api.post("/auth/login", { username, password });
      localStorage.setItem("bam_token", data.token);
      writeCachedUser(data.user);
      setUser(data.user);
      return { ok: true, user: data.user };
    } catch (e) {
      return { ok: false, error: apiError(e) };
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("bam_token");
    localStorage.removeItem(USER_KEY);
    setUser(false);
    window.location.href = "/login";
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
