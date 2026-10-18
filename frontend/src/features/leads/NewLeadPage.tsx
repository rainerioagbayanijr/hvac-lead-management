import { useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { api, ApiError, errorMessage } from '../../lib/api';
import { useAuth } from '../auth/AuthProvider';
import type { LeadDetail } from './types';

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}

function singaporeNow() {
  const values = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Singapore',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date());
  return values.replace(' ', 'T');
}

function fieldError(error: unknown) {
  if (!(error instanceof ApiError)) return '';
  const message = Object.values(error.fields ?? {})
    .flatMap((value) => (Array.isArray(value) ? value : [value]))
    .find((value) => typeof value === 'string');
  return message ?? errorMessage(error);
}

export function NewLeadPage() {
  const navigate = useNavigate();
  const { expire } = useAuth();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [location, setLocation] = useState('');
  const [serviceType, setServiceType] = useState('maintenance');
  const [requirements, setRequirements] = useState('');
  const [source, setSource] = useState('phone');
  const [receivedAt, setReceivedAt] = useState(singaporeNow);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const lead = await api<LeadDetail>('/leads/', {
        method: 'POST',
        body: JSON.stringify({
          name,
          phone,
          email,
          location,
          service_type: serviceType,
          requirements,
          source,
          received_at: new Date(`${receivedAt}:00+08:00`).toISOString(),
        }),
      });
      navigate(`/app/leads/${encodeURIComponent(lead.id)}`);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === 'not_authenticated') expire();
      else setError(fieldError(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Link className="text-sm font-semibold text-blue-700" to="/app/leads">
        ← All inquiries
      </Link>
      <div className="mx-auto mt-6 max-w-3xl">
        <p className="eyebrow">Staff workspace</p>
        <h1 className="page-title">Add an inquiry</h1>
        <p className="mt-3 text-slate-600">
          Record a phone call, email, referral, or another request received outside the website
          form.
        </p>
        {error && (
          <div className="mt-5">
            <Notice error>{error}</Notice>
          </div>
        )}
        <form className="panel mt-6 space-y-5" onSubmit={(event) => void submit(event)}>
          <Field label="Customer name">
            <input
              className="field-input"
              autoComplete="name"
              maxLength={120}
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Phone (enter a phone number or email)">
              <input
                className="field-input"
                type="tel"
                autoComplete="tel"
                maxLength={40}
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
            </Field>
            <Field label="Email">
              <input
                className="field-input"
                type="email"
                autoComplete="email"
                maxLength={254}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
          </div>
          <Field label="Service location">
            <input
              className="field-input"
              maxLength={250}
              value={location}
              onChange={(event) => setLocation(event.target.value)}
            />
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Service type">
              <select
                className="field-input"
                value={serviceType}
                onChange={(event) => setServiceType(event.target.value)}
              >
                <option value="installation">Installation</option>
                <option value="maintenance">Maintenance</option>
                <option value="repair">Repair</option>
              </select>
            </Field>
            <Field label="Lead source">
              <select
                className="field-input"
                value={source}
                onChange={(event) => setSource(event.target.value)}
              >
                <option value="phone">Phone</option>
                <option value="email">Email</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="referral">Referral</option>
                <option value="website">Website</option>
                <option value="other">Other</option>
              </select>
            </Field>
          </div>
          <Field label="Received at (Singapore time)">
            <input
              className="field-input"
              type="datetime-local"
              required
              value={receivedAt}
              onChange={(event) => setReceivedAt(event.target.value)}
            />
          </Field>
          <Field label="Service requirements">
            <textarea
              className="field-input min-h-28"
              maxLength={4000}
              value={requirements}
              onChange={(event) => setRequirements(event.target.value)}
            />
          </Field>
          <div className="flex flex-wrap gap-3">
            <button className="button-primary" disabled={busy}>
              {busy ? 'Saving inquiry…' : 'Save inquiry'}
            </button>
            <Link className="button-secondary" to="/app/leads">
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </>
  );
}
