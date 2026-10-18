import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { api, ApiError, errorMessage } from '../../lib/api';
import { formatDate } from '../../lib/dates';
import { useAuth } from '../auth/AuthProvider';
import type { Lead, LeadPage } from './types';

const stages = [
  ['new', 'New'],
  ['contacted', 'Contacted'],
  ['quoted', 'Quoted'],
  ['won', 'Won'],
  ['lost', 'Lost'],
] as const;

export function PipelinePage() {
  const { expire } = useAuth();
  const [leads, setLeads] = useState<Record<string, Lead[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    Promise.all(
      stages.map(async ([stage]) => {
        const page = await api<LeadPage>(`/leads/?stage=${stage}`, { signal: controller.signal });
        return [stage, page] as const;
      }),
    )
      .then((pages) => {
        if (!controller.signal.aborted)
          setLeads(Object.fromEntries(pages.map(([stage, page]) => [stage, page.results])));
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

  return (
    <>
      <p className="eyebrow">Sales workflow</p>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Pipeline</h1>
          <p className="mt-3 text-slate-600">
            Review leads by stage. Open a lead to record a stage change.
          </p>
        </div>
        <div className="flex gap-3">
          <Link className="button-secondary" to="/app/leads">
            List view
          </Link>
          <button
            className="button-secondary"
            disabled={loading}
            onClick={() => setRevision((value) => value + 1)}
          >
            Refresh pipeline
          </button>
        </div>
      </div>
      {loading && (
        <div className="mt-6">
          <Notice>Loading pipeline…</Notice>
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
      {Object.keys(leads).length > 0 && (
        <div className="mt-7 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {stages.map(([stage, label]) => (
            <section
              key={stage}
              aria-labelledby={`stage-${stage}`}
              className="min-w-0 rounded-2xl border border-slate-200 bg-slate-100 p-3"
            >
              <div className="flex items-center justify-between gap-2 px-1 py-2">
                <h2 id={`stage-${stage}`} className="font-semibold">
                  {label}
                </h2>
                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold tabular-nums">
                  {leads[stage]?.length ?? 0}
                </span>
              </div>
              <ul className="mt-2 space-y-3">
                {(leads[stage] ?? []).map((lead) => (
                  <li
                    key={lead.id}
                    className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
                  >
                    <Link
                      className="font-semibold text-blue-700 hover:underline"
                      to={`/app/leads/${lead.id}`}
                    >
                      {lead.name}
                    </Link>
                    <p className="mt-2 text-sm text-slate-600">{lead.service_label}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {lead.owner_name || 'Unassigned'} · {formatDate(lead.received_at)}
                    </p>
                  </li>
                ))}
              </ul>
              {(leads[stage] ?? []).length === 0 && (
                <p className="px-1 py-5 text-sm text-slate-500">No leads in this stage.</p>
              )}
              <Link
                className="mt-3 inline-block px-1 text-sm font-semibold text-blue-700"
                to={`/app/leads?stage=${stage}`}
              >
                Open stage list
              </Link>
            </section>
          ))}
        </div>
      )}
      {Object.values(leads).some((items) => items.length === 25) && (
        <p className="mt-4 text-sm text-slate-500">
          Each column shows the 25 most recently received leads in that stage. Use “Open stage list”
          to browse all results.
        </p>
      )}
    </>
  );
}
