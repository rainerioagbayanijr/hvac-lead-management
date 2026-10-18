import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { api, ApiError, errorMessage } from '../../lib/api';
import { formatDate } from '../../lib/dates';
import { useAuth } from '../auth/AuthProvider';

type Execution = {
  id: string;
  lead_id: string;
  lead_name: string;
  status: string;
  adapter: 'fake' | 'resend';
  recipient: string;
  subject: string;
  attempt_count: number;
  accepted_at: string | null;
  delivered_at: string | null;
  last_error_code: string;
  last_error_message: string;
  created_at: string;
  attempts: {
    attempt_number: number;
    status: string;
    started_at: string;
    finished_at: string | null;
    http_status: number | null;
    error_code: string;
    error_message: string;
  }[];
};
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
type IntegrationStatus = {
  adapter: string;
  counts: Record<string, number>;
  latest_execution_at: string | null;
  worker_last_success_at: string | null;
  worker_fresh: boolean;
  live_ready: boolean;
};

function Status({ value }: { value: string }) {
  const colors: Record<string, string> = {
    delivered: 'bg-emerald-50 text-emerald-800',
    accepted: 'bg-blue-50 text-blue-800',
    pending: 'bg-amber-50 text-amber-800',
    processing: 'bg-amber-50 text-amber-800',
    failed: 'bg-red-50 text-red-800',
    review: 'bg-red-50 text-red-800',
  };
  const label = value === 'review' ? 'Needs review' : value[0].toUpperCase() + value.slice(1);
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold ${colors[value] ?? 'bg-slate-100 text-slate-700'}`}
    >
      {label}
    </span>
  );
}

export function IntegrationPage() {
  const auth = useAuth();
  const { expire } = auth;
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [executions, setExecutions] = useState<Page<Execution> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    Promise.all([
      api<IntegrationStatus>('/integrations/status/', { signal: controller.signal }),
      api<Page<Execution>>('/integrations/executions/', { signal: controller.signal }),
    ])
      .then(([summary, history]) => {
        if (!controller.signal.aborted) {
          setStatus(summary);
          setExecutions(history);
        }
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError && reason.code === 'not_authenticated') expire();
        else setError(errorMessage(reason));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision, expire]);

  async function retry(execution: Execution) {
    setBusy(execution.id);
    setError('');
    try {
      await api(`/integrations/executions/${execution.id}/retry/`, { method: 'POST', body: '{}' });
      setRevision((value) => value + 1);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === 'not_authenticated') expire();
      else setError(errorMessage(reason));
    } finally {
      setBusy('');
    }
  }

  if (auth.session?.authenticated && auth.session.user.role !== 'admin') {
    return <Notice error>Integration history is available to business admins.</Notice>;
  }

  return (
    <>
      <p className="eyebrow">Admin settings</p>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Email integration</h1>
          <p className="mt-3 text-slate-600">
            Review inquiry alert delivery and retry safe failures.
          </p>
        </div>
        <button
          className="button-secondary"
          disabled={loading}
          onClick={() => setRevision((value) => value + 1)}
        >
          Refresh history
        </button>
      </div>
      {loading && (
        <div className="mt-6">
          <Notice>Loading integration status…</Notice>
        </div>
      )}
      {error && (
        <div className="mt-6">
          <Notice error>
            {error}{' '}
            <button className="underline" onClick={() => setRevision((value) => value + 1)}>
              Try again
            </button>
          </Notice>
        </div>
      )}
      {status && (
        <section
          aria-label="Email service status"
          className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          <div className="panel">
            <p className="text-sm text-slate-500">Active adapter</p>
            <p className="mt-2 font-semibold">
              {status.adapter === 'fake' ? 'Demo simulation' : 'Resend email'}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              {status.adapter === 'fake'
                ? 'No email is sent outside the application.'
                : status.live_ready
                  ? 'Live credentials are configured.'
                  : 'Live sender credentials are incomplete.'}
            </p>
          </div>
          <div className="panel">
            <p className="text-sm text-slate-500">Worker status</p>
            <p className="mt-2 font-semibold">
              {status.worker_fresh ? 'Running' : 'Waiting or unavailable'}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              Last success:{' '}
              {status.worker_last_success_at
                ? formatDate(status.worker_last_success_at)
                : 'No run recorded'}
            </p>
          </div>
          <div className="panel">
            <p className="text-sm text-slate-500">Delivered</p>
            <p className="mt-2 text-3xl font-semibold">{status.counts.delivered ?? 0}</p>
          </div>
          <div className="panel">
            <p className="text-sm text-slate-500">Needs attention</p>
            <p className="mt-2 text-3xl font-semibold">
              {(status.counts.failed ?? 0) + (status.counts.review ?? 0)}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              Review uncertain outcomes before retrying.
            </p>
          </div>
        </section>
      )}
      <section className="mt-7">
        <div className="mb-4">
          <h2 className="text-lg font-semibold">Execution history</h2>
          <p className="mt-1 text-sm text-slate-500">
            Each inquiry alert records its attempts and provider outcome.
          </p>
        </div>
        {executions?.count === 0 && (
          <div className="panel py-10 text-center">
            <h3 className="font-semibold">No alerts have run yet</h3>
            <p className="mt-2 text-sm text-slate-600">
              New website inquiries create a notification automatically.
            </p>
          </div>
        )}
        {executions && executions.results.length > 0 && (
          <ul className="space-y-3">
            {executions.results.map((execution) => (
              <li key={execution.id} className="panel">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="font-semibold">{execution.subject}</h3>
                      <Status value={execution.status} />
                    </div>
                    <p className="mt-2 text-sm text-slate-600">
                      <Link
                        className="font-medium text-blue-700 hover:underline"
                        to={`/app/leads/${execution.lead_id}`}
                      >
                        {execution.lead_name}
                      </Link>{' '}
                      · {execution.adapter === 'fake' ? 'Simulated' : 'Resend'} ·{' '}
                      {execution.attempt_count} attempt{execution.attempt_count === 1 ? '' : 's'}
                    </p>
                  </div>
                  <p className="text-sm text-slate-500">{formatDate(execution.created_at)}</p>
                </div>
                {execution.last_error_message && (
                  <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-900">
                    {execution.last_error_message}{' '}
                    <span className="font-mono text-xs">({execution.last_error_code})</span>
                  </p>
                )}
                <details className="mt-4">
                  <summary className="cursor-pointer text-sm font-semibold text-slate-700">
                    Attempt history
                  </summary>
                  <ol className="mt-3 space-y-2">
                    {execution.attempts.map((attempt) => (
                      <li
                        key={attempt.attempt_number}
                        className="rounded-lg bg-slate-50 p-3 text-sm"
                      >
                        <div className="flex flex-wrap justify-between gap-2">
                          <span>
                            Attempt {attempt.attempt_number} · {attempt.status}
                          </span>
                          <span className="text-slate-500">
                            {formatDate(attempt.started_at)}
                            {attempt.http_status ? ` · HTTP ${attempt.http_status}` : ''}
                          </span>
                        </div>
                        {attempt.error_message && (
                          <p className="mt-1 text-slate-600">{attempt.error_message}</p>
                        )}
                      </li>
                    ))}
                  </ol>
                </details>
                {execution.status === 'failed' &&
                  execution.attempt_count < 5 &&
                  ['temporary_failure', 'timeout', 'rate_limited'].includes(
                    execution.last_error_code,
                  ) && (
                    <button
                      className="button-secondary mt-4"
                      disabled={busy === execution.id}
                      onClick={() => void retry(execution)}
                    >
                      {busy === execution.id ? 'Queuing retry…' : 'Retry safely'}
                    </button>
                  )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
