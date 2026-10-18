import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { api, ApiError, errorMessage } from '../../lib/api';
import { useAuth } from '../auth/AuthProvider';

type Dashboard = {
  generated_at: string;
  pipeline: Record<string, number>;
  new_leads_30d: number;
  awaiting_first_contact: number;
  overdue_followups: number;
  open_quoted_value_sgd: string;
  response_time_30d: {
    median_seconds: number | null;
    responded_count: number;
    eligible_count: number;
  };
  mature_cohort_win_rate_90d: {
    won_count: number;
    eligible_count: number;
    rate: number | null;
    cohort_start: string;
    cohort_end: string;
  };
};

const stages = [
  ['new', 'New'],
  ['contacted', 'Contacted'],
  ['quoted', 'Quoted'],
  ['won', 'Won'],
  ['lost', 'Lost'],
] as const;

function responseLabel(seconds: number | null) {
  if (seconds === null) return 'No responses recorded';
  const hours = Math.round(seconds / 3600);
  return hours < 24 ? `${hours}h median` : `${Math.round(hours / 24)}d median`;
}

function Metric({
  label,
  value,
  detail,
  href,
}: {
  label: string;
  value: string | number;
  detail: string;
  href?: string;
}) {
  const content = (
    <div className="panel h-full">
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{value}</p>
      <p className="mt-2 text-sm text-slate-500">{detail}</p>
    </div>
  );
  return href ? (
    <Link className="block rounded-2xl focus-visible:outline" to={href}>
      {content}
    </Link>
  ) : (
    content
  );
}

export function DashboardPage() {
  const { expire } = useAuth();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    api<Dashboard>('/dashboard/', { signal: controller.signal })
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
  }, [revision, expire]);

  return (
    <>
      <p className="eyebrow">Business overview</p>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="mt-3 text-slate-600">
            A clear view of inquiries, response, and follow-up work.
          </p>
        </div>
        <button
          className="button-secondary"
          onClick={() => setRevision((value) => value + 1)}
          disabled={loading}
        >
          Refresh metrics
        </button>
      </div>
      {loading && (
        <div className="mt-6">
          <Notice>Loading business metrics…</Notice>
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
      {data && (
        <>
          <section
            aria-label="Current business metrics"
            className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
          >
            <Metric
              label="New inquiries · 30 days"
              value={data.new_leads_30d}
              detail="Based on customer receipt time"
              href="/app/leads"
            />
            <Metric
              label="Awaiting first contact"
              value={data.awaiting_first_contact}
              detail="Open leads without a recorded response"
              href="/app/leads?stage=new"
            />
            <Metric
              label="Overdue follow-ups"
              value={data.overdue_followups}
              detail="Pending tasks past their due time"
              href="/app/tasks?due=overdue"
            />
            <Metric
              label="Open quoted value"
              value={`SGD ${Number(data.open_quoted_value_sgd).toLocaleString('en-SG', { minimumFractionDigits: 2 })}`}
              detail="Quotes on leads currently in Quoted stage"
              href="/app/leads?stage=quoted"
            />
          </section>
          <section className="mt-7 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            <div className="panel">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">Current pipeline</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    A live count of leads in each stage.
                  </p>
                </div>
                <Link className="text-sm font-semibold text-blue-700" to="/app/leads">
                  View inquiries
                </Link>
              </div>
              <div className="mt-6 space-y-4">
                {stages.map(([key, label]) => {
                  const count = data.pipeline[key] ?? 0;
                  const total = Math.max(1, ...Object.values(data.pipeline));
                  return (
                    <Link
                      key={key}
                      to={`/app/leads?stage=${key}`}
                      className="grid grid-cols-[6rem_1fr_2rem] items-center gap-3 rounded-md text-sm focus-visible:outline"
                    >
                      <span className="text-slate-700">{label}</span>
                      <span className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <span
                          className="block h-full rounded-full bg-blue-600"
                          style={{ width: `${(count / total) * 100}%` }}
                        />
                      </span>
                      <span className="text-right font-semibold tabular-nums">{count}</span>
                    </Link>
                  );
                })}
              </div>
              {Object.values(data.pipeline).every((count) => count === 0) && (
                <p className="mt-4 text-sm text-slate-500">
                  No inquiries yet. The pipeline will update as customers get in touch.
                </p>
              )}
            </div>
            <div className="space-y-5">
              <Metric
                label="First response · last 30 days"
                value={responseLabel(data.response_time_30d.median_seconds)}
                detail={`${data.response_time_30d.responded_count} responded of ${data.response_time_30d.eligible_count} new inquiries`}
              />
              <Metric
                label="Win rate · mature cohort"
                value={
                  data.mature_cohort_win_rate_90d.rate === null
                    ? 'Not enough data'
                    : `${Math.round(data.mature_cohort_win_rate_90d.rate * 100)}%`
                }
                detail={`${data.mature_cohort_win_rate_90d.won_count} won of ${data.mature_cohort_win_rate_90d.eligible_count} leads received 30–120 days ago`}
              />
            </div>
          </section>
          <p className="mt-5 text-xs text-slate-500">
            Updated{' '}
            {new Date(data.generated_at).toLocaleString('en-SG', { timeZone: 'Asia/Singapore' })} ·
            Win rate uses a 90-day receipt cohort aged at least 30 days.
          </p>
        </>
      )}
    </>
  );
}
