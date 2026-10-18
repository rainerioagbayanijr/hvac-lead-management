import { useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router';
import { useAuth } from '../features/auth/AuthProvider';
import { errorMessage } from '../lib/api';
import { Notice } from '../components/ui/Notice';

export function AppShell({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function logout() {
    setBusy(true);
    setError('');
    try {
      await auth.logout();
      navigate('/login');
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <Link className="flex items-center gap-3 rounded-sm font-semibold tracking-tight" to="/">
            <span
              aria-hidden="true"
              className="grid h-10 w-10 place-items-center rounded-xl bg-blue-700 text-white"
            >
              S
            </span>
            <span>
              ServiceDesk <span className="font-normal text-slate-500">Leads</span>
            </span>
          </Link>
          <nav
            aria-label="Main navigation"
            className="flex flex-wrap items-center gap-5 text-sm font-medium"
          >
            <Link className="text-slate-600 hover:text-blue-700" to="/">
              Service inquiry
            </Link>
            {auth.session?.authenticated ? (
              <>
                <Link className="text-blue-700" to="/app/leads">
                  Leads
                </Link>
                <span className="text-slate-500">{auth.session.user.display_name}</span>
                <button className="button-secondary" onClick={() => void logout()} disabled={busy}>
                  {busy ? 'Logging out…' : 'Log out'}
                </button>
              </>
            ) : (
              <Link className="button-secondary" to="/login">
                Staff login
              </Link>
            )}
          </nav>
        </div>
      </header>
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto max-w-6xl px-5 py-9 sm:px-8 sm:py-12"
      >
        {error && (
          <div className="mb-5">
            <Notice error>{error}</Notice>
          </div>
        )}
        {children}
      </main>
      <footer className="mx-auto max-w-6xl px-5 pb-8 text-sm text-slate-500 sm:px-8">
        Development preview · Use fictional customer details only · Times shown in Singapore time
      </footer>
    </div>
  );
}
