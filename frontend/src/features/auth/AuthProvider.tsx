import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { api, ApiError, errorMessage } from '../../lib/api';

type User = { id: number; username: string; display_name: string; role: 'admin' | 'staff' };
export type Session =
  | { authenticated: false }
  | {
      authenticated: true;
      user: User;
      capabilities: {
        view_leads: boolean;
        manage_accounts: boolean;
        assign_leads: boolean;
      };
    };
type AuthState = {
  session: Session | null;
  loading: boolean;
  error: string;
  reload: () => void;
  expire: () => void;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const pendingSession = useRef<AbortController | null>(null);
  const expire = useCallback(() => {
    pendingSession.current?.abort();
    setLoading(false);
    setError('');
    setSession({ authenticated: false });
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    pendingSession.current = controller;
    setLoading(true);
    setError('');
    api<Session>('/auth/session/', { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setSession(value);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(reason));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);
  async function login(username: string, password: string) {
    const value = await api<Session>('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    pendingSession.current?.abort();
    setLoading(false);
    setError('');
    setSession(value);
  }
  async function logout() {
    try {
      await api<Session>('/auth/logout/', { method: 'POST' });
    } catch (reason) {
      if (!(reason instanceof ApiError && reason.code === 'not_authenticated')) throw reason;
    }
    expire();
  }
  return (
    <AuthContext.Provider
      value={{
        session,
        loading,
        error,
        expire,
        reload: () => setRevision((value) => value + 1),
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('AuthProvider is missing.');
  return context;
}
