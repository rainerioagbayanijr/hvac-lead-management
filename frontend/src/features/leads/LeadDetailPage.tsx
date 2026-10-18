import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { api, ApiError, errorMessage } from '../../lib/api';
import { formatDate } from '../../lib/dates';
import { useAuth } from '../auth/AuthProvider';
import type { LeadDetail } from './types';

export function LeadDetailPage() {
  const { id } = useParams();
  const { expire } = useAuth();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLead(null);
    setError('');
    api<LeadDetail>(`/leads/${encodeURIComponent(id ?? '')}/`, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setLead(value);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError && reason.code === 'not_authenticated') expire();
        else setError(errorMessage(reason));
      });
    return () => controller.abort();
  }, [id, revision, expire]);
  return (
    <>
      <Link className="text-sm font-semibold text-blue-700" to="/app/leads">
        ← All inquiries
      </Link>
      <div className="mt-6">
        {error && (
          <Notice error>
            {error}{' '}
            <button className="underline" onClick={() => setRevision((value) => value + 1)}>
              Try again
            </button>
          </Notice>
        )}
        {!lead && !error && <Notice>Loading inquiry…</Notice>}
        {lead && (
          <>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow">{lead.service_label} inquiry</p>
                <h1 className="page-title break-words">{lead.name}</h1>
                <p className="mt-3 text-sm text-slate-500">
                  Received {formatDate(lead.received_at)} · {lead.source}
                </p>
              </div>
              <span className="rounded-full bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-800">
                {lead.stage_label}
              </span>
            </div>
            <div className="mt-7 grid items-start gap-6 lg:grid-cols-[1.5fr_1fr]">
              <section className="panel">
                <h2 className="text-lg font-semibold">Contact and service details</h2>
                <dl className="mt-5 grid gap-5 sm:grid-cols-2">
                  {[
                    ['Phone', lead.phone],
                    ['Email', lead.email],
                    ['Service location', lead.location],
                    ['Owner', lead.owner_name || 'Unassigned'],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt className="text-sm text-slate-500">{label}</dt>
                      <dd className="mt-1 break-words font-medium">{value || 'Not provided'}</dd>
                    </div>
                  ))}
                </dl>
                <h3 className="mt-7 border-t border-slate-100 pt-5 font-semibold">
                  Service requirements
                </h3>
                <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-600">
                  {lead.requirements || 'No additional requirements provided.'}
                </p>
                <p className="mt-6 break-all text-xs text-slate-500">Reference: {lead.id}</p>
              </section>
              <section className="panel">
                <h2 className="text-lg font-semibold">Activity</h2>
                <ol className="mt-5 space-y-5">
                  {lead.activity.map((event) => (
                    <li key={event.id} className="border-l-2 border-blue-200 pl-4">
                      <p className="text-sm font-medium">
                        {event.event_type === 'created' ? 'Inquiry received' : event.event_type}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">{formatDate(event.occurred_at)}</p>
                    </li>
                  ))}
                </ol>
                {lead.activity.length === 0 && (
                  <p className="mt-4 text-sm text-slate-500">No recorded activity.</p>
                )}
              </section>
            </div>
            <p className="mt-6 text-sm text-slate-500">Read-only inquiry record.</p>
          </>
        )}
      </div>
    </>
  );
}
