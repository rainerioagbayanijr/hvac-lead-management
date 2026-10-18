import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { api, ApiError, errorMessage } from '../../lib/api';
import { formatDate } from '../../lib/dates';
import { useAuth } from '../auth/AuthProvider';
import type { LeadPage } from './types';

export function LeadListPage() {
  const [search, setSearch] = useSearchParams();
  const rawPage = Number(search.get('page') ?? 1);
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const [data, setData] = useState<LeadPage | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const { expire } = useAuth();
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setData(null);
    api<LeadPage>(`/leads/?page=${page}`, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
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
  }, [page, revision, expire]);
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Staff workspace</p>
          <h1 className="page-title">Service inquiries</h1>
          <p className="mt-3 text-slate-600">
            Review the latest requests from prospective customers.
          </p>
        </div>
        <button
          className="button-secondary"
          onClick={() => setRevision((value) => value + 1)}
          disabled={loading}
        >
          Refresh inquiries
        </button>
      </div>
      <p className="mt-5 text-sm text-slate-500">
        All team inquiries, newest first. Open a customer to view contact and service details.
      </p>
      <div className="mt-6">
        {loading && <Notice>Loading inquiries…</Notice>}
        {error && (
          <Notice error>
            {error}{' '}
            <button className="underline" onClick={() => setRevision((value) => value + 1)}>
              Try again
            </button>
            {page > 1 && (
              <Link className="ml-3 underline" to="/app/leads">
                Return to first page
              </Link>
            )}
          </Notice>
        )}
        {data && data.count === 0 && (
          <div className="panel py-12 text-center">
            <h2 className="text-lg font-semibold">No inquiries yet</h2>
            <p className="mt-2 text-slate-600">
              Submit a fictional request through the public form to see it here.
            </p>
            <Link className="button-primary mt-5" to="/">
              Open inquiry form
            </Link>
          </div>
        )}
        {data && data.count > 0 && (
          <>
            <div className="hidden overflow-hidden rounded-xl border border-slate-200 bg-white md:block">
              <table className="w-full table-fixed text-left text-sm">
                <caption className="sr-only">Customer service inquiries, newest first</caption>
                <thead className="bg-slate-100 text-xs uppercase tracking-wider text-slate-600">
                  <tr>
                    {['Customer', 'Service', 'Stage', 'Owner', 'Received (SGT)'].map((title) => (
                      <th key={title} scope="col" className="px-5 py-4">
                        {title}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.results.map((lead) => (
                    <tr key={lead.id} className="hover:bg-slate-50">
                      <td className="px-5 py-5">
                        <Link className="font-semibold text-blue-700" to={`/app/leads/${lead.id}`}>
                          {lead.name}
                        </Link>
                        <p className="mt-1 text-xs text-slate-500">{lead.email || lead.phone}</p>
                      </td>
                      <td className="px-5 py-5">{lead.service_label}</td>
                      <td className="px-5 py-5">
                        <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800">
                          {lead.stage_label}
                        </span>
                      </td>
                      <td className="px-5 py-5 text-slate-600">
                        {lead.owner_name || 'Unassigned'}
                      </td>
                      <td className="px-5 py-5 text-slate-600">{formatDate(lead.received_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="space-y-3 md:hidden">
              {data.results.map((lead) => (
                <li key={lead.id} className="panel">
                  <div className="flex items-start justify-between gap-3">
                    <Link className="font-semibold text-blue-700" to={`/app/leads/${lead.id}`}>
                      {lead.name}
                    </Link>
                    <span className="rounded-full bg-blue-50 px-3 py-1 text-xs text-blue-800">
                      {lead.stage_label}
                    </span>
                  </div>
                  <p className="mt-3 text-sm">
                    {lead.service_label} · {lead.owner_name || 'Unassigned'}
                  </p>
                  <p className="mt-2 text-sm text-slate-500">{formatDate(lead.received_at)}</p>
                </li>
              ))}
            </ul>
            <nav
              aria-label="Inquiry pagination"
              className="mt-5 flex flex-wrap items-center justify-between gap-3 text-sm"
            >
              <p className="text-slate-500">
                Showing {(page - 1) * 25 + 1}–{Math.min(page * 25, data.count)} of {data.count}{' '}
                inquiries
              </p>
              <div className="flex gap-3">
                <button
                  className="button-secondary"
                  disabled={!data.previous}
                  onClick={() => setSearch({ page: String(page - 1) })}
                >
                  Previous
                </button>
                <button
                  className="button-secondary"
                  disabled={!data.next}
                  onClick={() => setSearch({ page: String(page + 1) })}
                >
                  Next
                </button>
              </div>
            </nav>
          </>
        )}
      </div>
    </>
  );
}
