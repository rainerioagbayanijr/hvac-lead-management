import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { api, ApiError, errorMessage } from '../../lib/api';

const keyName = 'service-desk-inquiry-key';
type Fields = {
  name: string;
  phone: string;
  email: string;
  location: string;
  service_type: string;
  requirements: string;
  company_website: string;
  privacy_acknowledged: boolean;
};
const initialFields: Fields = {
  name: '',
  phone: '',
  email: '',
  location: '',
  service_type: 'maintenance',
  requirements: '',
  company_website: '',
  privacy_acknowledged: false,
};
function submissionKey() {
  try {
    const saved = sessionStorage.getItem(keyName);
    if (saved) return saved;
    const value = crypto.randomUUID();
    sessionStorage.setItem(keyName, value);
    return value;
  } catch {
    return crypto.randomUUID();
  }
}

export function InquiryPage() {
  const [demoMode, setDemoMode] = useState<boolean | null>(null);
  const [fields, setFields] = useState<Fields>(initialFields);
  const [key, setKey] = useState(submissionKey);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[] | string>>({});
  const [conflict, setConflict] = useState(false);
  const [reference, setReference] = useState('');
  const busyRef = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    api<{ demo_mode: boolean }>('/public-config/', { signal: controller.signal })
      .then((config) => {
        if (!controller.signal.aborted) setDemoMode(config.demo_mode);
      })
      .catch(() => {
        if (!controller.signal.aborted) setDemoMode(false);
      });
    return () => controller.abort();
  }, []);
  function update(name: keyof Fields, value: string | boolean) {
    setFields((current) => ({ ...current, [name]: value }));
  }
  function startAnother() {
    try {
      sessionStorage.removeItem(keyName);
    } catch {
      /* Memory-only storage is also supported. */
    }
    setKey(submissionKey());
    setFields(initialFields);
    setReference('');
    setUncertain(false);
    setError('');
    setConflict(false);
    setFieldErrors({});
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError('');
    setFieldErrors({});
    try {
      const result = await api<{ reference: string }>('/inquiries/', {
        method: 'POST',
        body: JSON.stringify({ ...fields, submission_key: key }),
      });
      if (!result.reference) throw new Error('Missing confirmation reference.');
      setReference(result.reference);
      try {
        sessionStorage.removeItem(keyName);
      } catch {
        /* No customer fields are stored in the browser. */
      }
    } catch (reason) {
      const unknownOutcome =
        !(reason instanceof ApiError) || reason.status >= 500 || reason.code === 'invalid_response';
      if (unknownOutcome) setUncertain(true);
      setError(
        unknownOutcome
          ? 'We could not confirm the result. Your inquiry may have been saved. Retry the same details to check safely.'
          : errorMessage(reason),
      );
      if (reason instanceof ApiError) {
        setFieldErrors(reason.fields);
        setConflict(reason.status === 409);
      }
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  const inputFields = [
    ['name', 'Your name', 'text', 'name', 120],
    ['phone', 'Phone number', 'tel', 'tel', 40],
    ['email', 'Email address', 'email', 'email', 254],
    ['location', 'Service location or area (optional)', 'text', 'off', 250],
  ] as const;
  function fieldError(name: string) {
    const message = fieldErrors[name];
    return (
      message && (
        <p id={`${name}-error`} className="mt-2 text-sm text-red-800">
          {Array.isArray(message) ? message.join(' ') : message}
        </p>
      )
    );
  }

  if (demoMode === null) return <Notice>Preparing service inquiry form…</Notice>;
  if (demoMode)
    return (
      <div className="mx-auto max-w-2xl">
        <p className="eyebrow">Portfolio demonstration</p>
        <h1 className="page-title">Synthetic customer workspace</h1>
        <p className="mt-4 leading-7 text-slate-600">
          This read-only public demo uses fictional customer records. Public inquiry intake is
          disabled here. Sign in with the demo account to explore lead ownership, follow-ups, and
          reporting.
        </p>
        <Link className="button-primary mt-6" to="/login">
          Open demo workspace
        </Link>
      </div>
    );
  if (reference)
    return (
      <div className="mx-auto max-w-2xl panel">
        <p className="eyebrow">Inquiry received</p>
        <h1 className="page-title">Thank you. You're on our list.</h1>
        <p className="mt-4 leading-7 text-slate-600">
          Your inquiry is saved for the team to review and contact you. This confirmation does not
          book a service appointment.
        </p>
        <div role="status" className="mt-6 rounded-xl bg-green-50 p-5 text-green-900">
          <p className="text-sm font-semibold">Your inquiry reference</p>
          <p className="mt-2 break-all font-mono text-sm">{reference}</p>
        </div>
        <button className="button-secondary mt-6" onClick={startAnother}>
          Submit another inquiry
        </button>
      </div>
    );

  return (
    <div className="grid items-start gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:gap-14">
      <section>
        <p className="eyebrow">Air-conditioning service</p>
        <h1 className="page-title leading-tight">Comfort starts with a conversation.</h1>
        <p className="mt-5 max-w-lg leading-7 text-slate-600">
          Tell us about your installation, maintenance, or repair needs. Our team will review your
          inquiry and get in touch to discuss the next step.
        </p>
        <ul className="mt-7 space-y-4 text-sm text-slate-600">
          <li>✓ Installation and replacement inquiries</li>
          <li>✓ Routine servicing and maintenance</li>
          <li>✓ Troubleshooting and repair inquiries</li>
        </ul>
        <div className="mt-8 rounded-xl border border-blue-100 bg-blue-50 p-5 text-sm leading-6 text-blue-900">
          Development preview: please use fictional contact details. This form is not monitored for
          real service requests.
        </div>
        <Link to="/login" className="mt-6 inline-block text-sm font-semibold text-blue-700">
          Staff member? Log in →
        </Link>
      </section>
      <form className="panel space-y-5" onSubmit={submit}>
        <div>
          <h2 className="text-xl font-semibold">Request a service</h2>
          <p className="mt-2 text-sm text-slate-500">
            Provide your name and at least one way to contact you.
          </p>
        </div>
        {error && <Notice error>{error}</Notice>}
        {uncertain && (
          <p className="text-sm text-slate-600">
            Details are locked until this submission is confirmed. Retrying uses the same reference
            key.
          </p>
        )}
        <fieldset disabled={busy || uncertain} className="space-y-5">
          <div>
            <label className="field-label" htmlFor="service_type">
              Service needed
            </label>
            <select
              id="service_type"
              className="field-input"
              value={fields.service_type}
              onChange={(event) => update('service_type', event.target.value)}
            >
              <option value="maintenance">Maintenance</option>
              <option value="installation">Installation</option>
              <option value="repair">Repair</option>
            </select>
            {fieldError('service_type')}
          </div>
          {inputFields.map(([name, label, type, autocomplete, maxLength]) => (
            <div key={name}>
              <label className="field-label" htmlFor={name}>
                {label}
                {name === 'name' && ' *'}
              </label>
              <input
                id={name}
                name={name}
                className="field-input"
                type={type}
                autoComplete={autocomplete}
                value={fields[name]}
                onChange={(event) => update(name, event.target.value)}
                required={name === 'name'}
                maxLength={maxLength}
                aria-invalid={Boolean(fieldErrors[name])}
                aria-describedby={fieldErrors[name] ? `${name}-error` : undefined}
              />
              {fieldError(name)}
            </div>
          ))}
          <div>
            <label className="field-label" htmlFor="requirements">
              How can we help? (optional)
            </label>
            <textarea
              id="requirements"
              className="field-input min-h-28"
              value={fields.requirements}
              maxLength={4000}
              onChange={(event) => update('requirements', event.target.value)}
              aria-invalid={Boolean(fieldErrors.requirements)}
              aria-describedby={fieldErrors.requirements ? 'requirements-error' : undefined}
            />
            {fieldError('requirements')}
          </div>
          <div className="absolute -left-[10000px]" aria-hidden="true">
            <label htmlFor="company_website">Leave this field empty</label>
            <input
              id="company_website"
              tabIndex={-1}
              autoComplete="off"
              value={fields.company_website}
              onChange={(event) => update('company_website', event.target.value)}
            />
          </div>
          <div
            id="privacy-notice"
            className="rounded-lg bg-slate-50 p-4 text-sm leading-6 text-slate-600"
          >
            We use these details to review and respond to your service inquiry. They are visible to
            authorized company staff. No marketing consent is requested. Use synthetic data in this
            development version.
          </div>
          <div>
            <label className="flex items-start gap-3 text-sm leading-6">
              <input
                className="mt-1 h-4 w-4 shrink-0"
                type="checkbox"
                required
                checked={fields.privacy_acknowledged}
                onChange={(event) => update('privacy_acknowledged', event.target.checked)}
                aria-describedby="privacy-notice"
              />
              I have read the inquiry privacy notice.
            </label>
            {fieldError('privacy_acknowledged')}
          </div>
        </fieldset>
        <button className="button-primary w-full" disabled={busy || conflict}>
          {busy ? 'Sending inquiry…' : uncertain ? 'Retry same inquiry' : 'Send inquiry'}
        </button>
        {conflict && (
          <>
            <p className="text-sm text-slate-600">
              An earlier request may already be saved. Start another only if this is a separate
              service inquiry.
            </p>
            <button type="button" className="button-secondary" onClick={startAnother}>
              Start a separate inquiry
            </button>
          </>
        )}
      </form>
    </div>
  );
}
