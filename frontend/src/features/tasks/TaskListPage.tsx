import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { api, ApiError, errorMessage } from '../../lib/api';
import { formatDate, singaporeDateAtNine, singaporeInputToIso } from '../../lib/dates';
import { useAuth } from '../auth/AuthProvider';
import type { FollowUpTask } from '../leads/types';

type TaskPage = {
  count: number;
  next: string | null;
  previous: string | null;
  results: FollowUpTask[];
};

export function TaskListPage() {
  const { expire } = useAuth();
  const [status, setStatus] = useState('pending');
  const [due, setDue] = useState('all');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<TaskPage | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [revision, setRevision] = useState(0);
  const [rescheduleValues, setRescheduleValues] = useState<Record<string, string>>({});
  const retryKeys = useRef<Record<string, string>>({});

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    api<TaskPage>(`/tasks/?status=${status}&due=${due}&page=${page}`, { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
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
  }, [status, due, page, revision, expire]);

  async function updateTask(task: FollowUpTask, action: 'complete' | 'cancel' | 'reschedule') {
    const due_at =
      action === 'reschedule' ? singaporeInputToIso(rescheduleValues[task.id] ?? '') : undefined;
    const payload = { action, task: task.id, due_at };
    const retryKey = `${task.id}:${JSON.stringify(payload)}`;
    const actionKey = (retryKeys.current[retryKey] ??= crypto.randomUUID());
    setBusy(retryKey);
    setError('');
    try {
      await api(`/leads/${encodeURIComponent(task.lead_id)}/tasks/${task.id}/${action}/`, {
        method: 'POST',
        body: JSON.stringify({
          action_key: actionKey,
          expected_version: task.lead_version,
          ...(due_at ? { due_at } : {}),
        }),
      });
      retryKeys.current = {};
      setRevision((value) => value + 1);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status < 500) delete retryKeys.current[retryKey];
      if (reason instanceof ApiError && reason.code === 'not_authenticated') expire();
      else setError(errorMessage(reason));
    } finally {
      setBusy('');
    }
  }

  return (
    <>
      <p className="eyebrow">Team workspace</p>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Follow-ups</h1>
          <p className="mt-3 text-slate-600">Keep promised calls and next steps from slipping.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <label className="block">
            <span className="field-label">Status</span>
            <select
              className="field-input min-w-36"
              value={status}
              onChange={(event) => {
                const value = event.target.value;
                setStatus(value);
                if (value !== 'pending' && due === 'overdue') setDue('all');
                setPage(1);
              }}
            >
              <option value="pending">Open</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </label>
          <label className="block">
            <span className="field-label">Due</span>
            <select
              className="field-input min-w-36"
              value={due}
              onChange={(event) => {
                setDue(event.target.value);
                setPage(1);
              }}
            >
              <option value="all">Any date</option>
              {status === 'pending' && <option value="overdue">Overdue</option>}
              {status === 'pending' && <option value="today">Today</option>}
            </select>
          </label>
        </div>
      </div>

      <div className="mt-7">
        {error && (
          <Notice error>
            {error}{' '}
            <button className="underline" onClick={() => setRevision((value) => value + 1)}>
              Refresh follow-ups
            </button>
          </Notice>
        )}
        {loading && <Notice>Loading follow-ups…</Notice>}
        {data && data.results.length === 0 && !error && (
          <div className="panel py-12 text-center">
            <h2 className="text-lg font-semibold">No follow-ups here</h2>
            <p className="mt-2 text-slate-600">
              Schedule the next customer touchpoint from a lead’s details.
            </p>
            <Link className="button-primary mt-5" to="/app/leads">
              View inquiries
            </Link>
          </div>
        )}
        {data && data.results.length > 0 && (
          <>
            <ul className="space-y-3">
              {data.results.map((task) => {
                const retryPrefix = `${task.id}:`;
                return (
                  <li className="panel" key={task.id}>
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="font-semibold">{task.title}</h2>
                          {task.is_overdue && (
                            <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-800">
                              Overdue
                            </span>
                          )}
                          {task.status !== 'pending' && (
                            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold capitalize text-slate-700">
                              {task.status}
                            </span>
                          )}
                        </div>
                        <p className="mt-2 text-sm text-slate-600">
                          <Link
                            className="font-medium text-blue-700 hover:underline"
                            to={`/app/leads/${task.lead_id}`}
                          >
                            {task.lead_name}
                          </Link>
                          {' · '}
                          {task.lead_stage}
                          {' · '}
                          {task.owner_name || 'Unassigned'}
                        </p>
                        {task.details && (
                          <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                            {task.details}
                          </p>
                        )}
                        <p
                          className={`mt-3 text-sm ${task.is_overdue ? 'font-semibold text-rose-700' : 'text-slate-500'}`}
                        >
                          Due {formatDate(task.due_at)}
                        </p>
                      </div>
                      {task.status === 'pending' && (
                        <div className="flex flex-wrap items-end gap-2">
                          <label className="block">
                            <span className="field-label">New due time</span>
                            <input
                              className="field-input"
                              type="datetime-local"
                              value={rescheduleValues[task.id] ?? singaporeDateAtNine()}
                              onChange={(event) =>
                                setRescheduleValues((values) => ({
                                  ...values,
                                  [task.id]: event.target.value,
                                }))
                              }
                              aria-label={`New due time for ${task.title}`}
                            />
                          </label>
                          <button
                            className="button-secondary"
                            disabled={Boolean(busy) || !rescheduleValues[task.id]}
                            onClick={() => void updateTask(task, 'reschedule')}
                          >
                            Reschedule
                          </button>
                          <button
                            className="button-primary"
                            disabled={Boolean(busy)}
                            onClick={() => void updateTask(task, 'complete')}
                          >
                            {busy.startsWith(retryPrefix) ? 'Saving…' : 'Complete'}
                          </button>
                          <button
                            className="button-secondary"
                            disabled={Boolean(busy)}
                            onClick={() => void updateTask(task, 'cancel')}
                          >
                            Cancel
                          </button>
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
            <div className="mt-5 flex items-center justify-between text-sm text-slate-600">
              <span>
                {data.count} follow-up{data.count === 1 ? '' : 's'}
              </span>
              <div className="flex gap-2">
                <button
                  className="button-secondary"
                  disabled={!data.previous || loading}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                >
                  Previous
                </button>
                <button
                  className="button-secondary"
                  disabled={!data.next || loading}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
