import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { errorMessage } from '../../lib/api';
import { useAuth } from './AuthProvider';

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const target = (location.state as { from?: string } | null)?.from;
  const destination = target?.startsWith('/app/') ? target : '/app/leads';
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (auth.session?.authenticated) return <Navigate to={destination} replace />;
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await auth.login(username, password);
      setPassword('');
      navigate(destination, { replace: true });
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="mx-auto max-w-md">
      <p className="eyebrow">Staff workspace</p>
      <h1 className="page-title">Welcome back</h1>
      <p className="mt-3 text-slate-600">Log in to review your team's service inquiries.</p>
      <form onSubmit={submit} className="panel mt-7 space-y-5">
        {error && <Notice error>{error}</Notice>}
        <div>
          <label className="field-label" htmlFor="username">
            Username
          </label>
          <input
            id="username"
            className="field-input"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            maxLength={150}
            required
            disabled={busy}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            className="field-input"
            autoComplete="current-password"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            maxLength={1024}
            required
            disabled={busy}
          />
          <label className="mt-3 flex min-h-11 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showPassword}
              onChange={(event) => setShowPassword(event.target.checked)}
            />
            Show password
          </label>
        </div>
        <button className="button-primary w-full" disabled={busy}>
          {busy ? 'Logging in…' : 'Log in'}
        </button>
        <p className="text-sm leading-6 text-slate-500">
          Accounts are created by your administrator. Contact them if you need access or a password
          reset.
        </p>
      </form>
      <Link to="/" className="mt-5 inline-block text-sm font-medium text-blue-700">
        ← Back to service inquiry
      </Link>
    </div>
  );
}
