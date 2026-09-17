import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "./api";

type Me = { kind: string; role: string; actor: string; user?: any } | null;

const Ctx = createContext<{
  me: Me; loading: boolean;
  login: (identifier: string, password: string, otp?: string) => Promise<void>;
  logout: () => Promise<void>;
}>(null as any);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try { setMe((await api.get("/auth/me")).data); }
    catch { setMe(null); }
    finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);

  const login = async (identifier: string, password: string, otp?: string) => {
    await api.post("/auth/login", { identifier, password, otp });
    await refresh();
  };
  const logout = async () => { await api.post("/auth/logout"); setMe(null); };

  return <Ctx.Provider value={{ me, loading, login, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
