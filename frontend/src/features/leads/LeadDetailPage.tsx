import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useParams } from 'react-router';
import { Notice } from '../../components/ui/Notice';
import { api, ApiError, errorMessage } from '../../lib/api';
import { formatDate, singaporeDateAtNine, singaporeInputToIso } from '../../lib/dates';
import { useAuth } from '../auth/AuthProvider';
import type { LeadDetail } from './types';

type TeamMember = { id: number; display_name: string; role: 'admin' | 'staff' };

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}

function actionError(error: unknown) {
  if (error instanceof ApiError) {
    const value = Object.values(error.fields ?? {})
      .flatMap((field) => (Array.isArray(field) ? field : [field]))
      .find((field) => typeof field === 'string');
    if (value) return value;
  }
  return errorMessage(error);
}

export function LeadDetailPage() {
  const { id } = useParams();
  const { expire, session } = useAuth();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [selectedOwner, setSelectedOwner] = useState('');
  const [contactMethod, setContactMethod] = useState('phone');
  const [contactSummary, setContactSummary] = useState('');
  const [quoteAmount, setQuoteAmount] = useState('');
  const [lossReason, setLossReason] = useState('');
  const [reopenStage, setReopenStage] = useState('new');
  const [note, setNote] = useState('');
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDetails, setTaskDetails] = useState('');
  const [taskDue, setTaskDue] = useState(singaporeDateAtNine());
  const [taskDueChanges, setTaskDueChanges] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState('');
  const retryKeys = useRef<Record<string, string>>({});
  const isAdmin = session?.authenticated === true && session.user.role === 'admin';

  useEffect(() => {
    const controller = new AbortController();
    setLead(null);
    setError('');
    api<LeadDetail>(`/leads/${encodeURIComponent(id ?? '')}/`, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) {
          setLead(value);
          setSelectedOwner(value.owner_id === null ? '' : String(value.owner_id));
        }
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError && reason.code === 'not_authenticated') expire();
        else setError(errorMessage(reason));
      });
    return () => controller.abort();
  }, [id, revision, expire]);

  useEffect(() => {
    if (!isAdmin) return;
    const controller = new AbortController();
    api<TeamMember[]>('/team/', { signal: controller.signal })
      .then((members) => {
        if (!controller.signal.aborted) setTeam(members);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(reason));
      });
    return () => controller.abort();
  }, [isAdmin, revision]);

  async function runAction(action: string, values: Record<string, string | number | null>) {
    if (!lead) return;
    setBusy(action);
    setError('');
    const requestKey = `${action}:${JSON.stringify(values)}`;
    const actionKey = (retryKeys.current[requestKey] ??= crypto.randomUUID());
    try {
      await api(`/leads/${encodeURIComponent(id ?? '')}/${action}/`, {
        method: 'POST',
        body: JSON.stringify({ ...values, action_key: actionKey, expected_version: lead.version }),
      });
      retryKeys.current = {};
      if (action === 'contact') setContactSummary('');
      if (action === 'notes') setNote('');
      if (action === 'tasks') {
        setTaskTitle('');
        setTaskDetails('');
        setTaskDue(singaporeDateAtNine());
      }
      if (action === 'stage') {
        setQuoteAmount('');
        setLossReason('');
      }
      setRevision((value) => value + 1);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status < 500) delete retryKeys.current[requestKey];
      if (reason instanceof ApiError && reason.code === 'not_authenticated') expire();
      else setError(actionError(reason));
    } finally {
      setBusy('');
    }
  }

  const canEdit = Boolean(
    lead &&
    !lead.archived_at &&
    session?.authenticated &&
    (isAdmin || lead.owner_id === session.user.id),
  );
  const isOpen = Boolean(lead && !['won', 'lost'].includes(lead.stage));
  const actionButton = (
    text: string,
    action: string,
    values: Record<string, string | number | null>,
  ) => (
    <button
      className="button-primary"
      disabled={Boolean(busy)}
      onClick={() => void runAction(action, values)}
    >
      {busy === action ? 'Saving…' : text}
    </button>
  );

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
              Refresh lead
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
              <div className="flex flex-wrap items-center gap-3">
                {isAdmin && (
                  <button
                    className="button-secondary"
                    disabled={Boolean(busy)}
                    onClick={() => void runAction(lead.archived_at ? 'restore' : 'archive', {})}
                  >
                    {busy === (lead.archived_at ? 'restore' : 'archive')
                      ? 'Saving…'
                      : lead.archived_at
                        ? 'Restore inquiry'
                        : 'Archive inquiry'}
                  </button>
                )}
                <span className="rounded-full bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-800">
                  {lead.stage_label}
                </span>
              </div>
            </div>
            {lead.archived_at && (
              <div className="mt-5">
                <Notice>This inquiry is archived. Restore it before making changes.</Notice>
              </div>
            )}

            <div className="mt-7 grid items-start gap-6 lg:grid-cols-[1.45fr_1fr]">
              <div className="space-y-6">
                <section className="panel">
                  <h2 className="text-lg font-semibold">Customer and service</h2>
                  <dl className="mt-5 grid gap-5 sm:grid-cols-2">
                    {[
                      ['Phone', lead.phone],
                      ['Email', lead.email],
                      ['Service location', lead.location],
                      ['Lead source', lead.source],
                      [
                        'First contacted',
                        lead.first_contact_at ? formatDate(lead.first_contact_at) : 'Not recorded',
                      ],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <dt className="text-sm text-slate-500">{label}</dt>
                        <dd className="mt-1 break-words font-medium">{value || 'Not provided'}</dd>
                      </div>
                    ))}
                  </dl>
                  {lead.quote_amount && (
                    <p className="mt-5 rounded-lg bg-slate-50 p-4 text-sm">
                      Current quote <strong>SGD {lead.quote_amount}</strong>
                    </p>
                  )}
                  {lead.loss_reason && (
                    <p className="mt-5 rounded-lg bg-amber-50 p-4 text-sm text-amber-900">
                      Lost reason: {lead.loss_reason}
                    </p>
                  )}
                  <h3 className="mt-7 border-t border-slate-100 pt-5 font-semibold">
                    Service requirements
                  </h3>
                  <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-600">
                    {lead.requirements || 'No additional requirements provided.'}
                  </p>
                  <p className="mt-6 break-all text-xs text-slate-500">Reference: {lead.id}</p>
                </section>

                <section className="panel">
                  <h2 className="text-lg font-semibold">Lead ownership</h2>
                  <p className="mt-2 text-sm text-slate-600">
                    Current owner: <strong>{lead.owner_name || 'Unassigned'}</strong>
                  </p>
                  {!lead.archived_at &&
                    !lead.owner_id &&
                    isOpen &&
                    actionButton('Claim this inquiry', 'claim', {})}
                  {isAdmin && !lead.archived_at && (
                    <div className="mt-5 flex flex-wrap items-end gap-3">
                      <Field label="Assign to">
                        <select
                          className="field-input min-w-52"
                          value={selectedOwner}
                          disabled={Boolean(busy)}
                          onChange={(event) => {
                            setSelectedOwner(event.target.value);
                          }}
                        >
                          <option value="">Unassigned</option>
                          {team.map((member) => (
                            <option key={member.id} value={member.id}>
                              {member.display_name} · {member.role}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <button
                        className="button-secondary"
                        disabled={Boolean(busy) || String(lead.owner_id ?? '') === selectedOwner}
                        onClick={() =>
                          void runAction('assignment', {
                            owner_id: selectedOwner ? Number(selectedOwner) : null,
                          })
                        }
                      >
                        {busy === 'assignment' ? 'Saving…' : 'Save owner'}
                      </button>
                    </div>
                  )}
                  {!canEdit && lead.owner_id !== null && (
                    <p className="mt-4 text-sm text-slate-500">
                      This inquiry belongs to another staff member. You can still see its history.
                    </p>
                  )}
                  {canEdit && (
                    <p className="mt-4 text-xs text-slate-500">
                      Changes save together with a dated activity entry.
                    </p>
                  )}
                </section>

                {canEdit && isOpen && (
                  <>
                    <section className="panel">
                      <h2 className="text-lg font-semibold">Record customer contact</h2>
                      <p className="mt-1 text-sm text-slate-600">
                        The first contact time is kept for response reporting.
                      </p>
                      <form
                        className="mt-5 space-y-4"
                        onSubmit={(event: FormEvent) => {
                          event.preventDefault();
                          void runAction('contact', {
                            method: contactMethod,
                            summary: contactSummary.trim(),
                          });
                        }}
                      >
                        <Field label="Contact method">
                          <select
                            className="field-input"
                            value={contactMethod}
                            onChange={(event) => {
                              setContactMethod(event.target.value);
                            }}
                          >
                            <option value="phone">Phone call</option>
                            <option value="email">Email</option>
                            <option value="whatsapp">WhatsApp</option>
                            <option value="other">Other</option>
                          </select>
                        </Field>
                        <Field label="Brief contact note (optional)">
                          <textarea
                            className="field-input min-h-24"
                            maxLength={1000}
                            value={contactSummary}
                            onChange={(event) => {
                              setContactSummary(event.target.value);
                            }}
                            placeholder="Outcome or next step"
                          />
                        </Field>
                        <button className="button-primary" disabled={Boolean(busy)}>
                          {busy === 'contact' ? 'Saving…' : 'Save contact'}
                        </button>
                      </form>
                    </section>

                    <section className="panel">
                      <h2 className="text-lg font-semibold">Update pipeline stage</h2>
                      {lead.tasks.some((task) => task.status === 'pending') && (
                        <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                          Marking this inquiry Won or Lost will cancel{' '}
                          {lead.tasks.filter((task) => task.status === 'pending').length} open
                          follow-up(s). You can schedule new work if an admin reopens it.
                        </p>
                      )}
                      {lead.stage === 'contacted' && (
                        <form
                          className="mt-5 space-y-4"
                          onSubmit={(event: FormEvent) => {
                            event.preventDefault();
                            void runAction('stage', {
                              stage: 'quoted',
                              quote_amount: quoteAmount,
                              loss_reason: '',
                            });
                          }}
                        >
                          <Field label="Quote amount (SGD)">
                            <input
                              className="field-input"
                              type="number"
                              min="0.01"
                              max="99999999.99"
                              step="0.01"
                              required
                              value={quoteAmount}
                              onChange={(event) => {
                                setQuoteAmount(event.target.value);
                              }}
                            />
                          </Field>
                          <button className="button-primary" disabled={Boolean(busy)}>
                            {busy === 'stage' ? 'Saving…' : 'Save quote and move to Quoted'}
                          </button>
                        </form>
                      )}
                      {lead.stage === 'quoted' && (
                        <div className="mt-5">
                          {actionButton('Mark as Won', 'stage', {
                            stage: 'won',
                            loss_reason: '',
                          })}
                        </div>
                      )}
                      <form
                        className="mt-5 border-t border-slate-100 pt-5"
                        onSubmit={(event: FormEvent) => {
                          event.preventDefault();
                          void runAction('stage', {
                            stage: 'lost',
                            loss_reason: lossReason.trim(),
                          });
                        }}
                      >
                        <Field label="Reason for loss">
                          <textarea
                            className="field-input min-h-20"
                            maxLength={500}
                            required
                            value={lossReason}
                            onChange={(event) => {
                              setLossReason(event.target.value);
                            }}
                            placeholder="For example, customer postponed the project"
                          />
                        </Field>
                        <button
                          className="button-secondary mt-3"
                          disabled={Boolean(busy) || !lossReason.trim()}
                        >
                          {busy === 'stage' ? 'Saving…' : 'Mark as Lost'}
                        </button>
                      </form>
                    </section>
                  </>
                )}

                {isAdmin && !lead.archived_at && !isOpen && (
                  <section className="panel">
                    <h2 className="text-lg font-semibold">Reopen lead</h2>
                    <p className="mt-2 text-sm text-slate-600">
                      Reopening keeps the previous closure in activity history.
                    </p>
                    <div className="mt-4 flex flex-wrap items-end gap-3">
                      <Field label="Open at stage">
                        <select
                          className="field-input"
                          value={reopenStage}
                          onChange={(event) => {
                            setReopenStage(event.target.value);
                          }}
                        >
                          <option value="new">New</option>
                          <option value="contacted">Contacted</option>
                          {lead.quote_amount && <option value="quoted">Quoted</option>}
                        </select>
                      </Field>
                      {actionButton('Reopen', 'reopen', { stage: reopenStage })}
                    </div>
                  </section>
                )}

                <section className="panel">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold">Follow-up tasks</h2>
                      <p className="mt-1 text-sm text-slate-600">
                        Plan the next call or customer update. Reminders are manual in this
                        milestone.
                      </p>
                    </div>
                    <Link
                      className="text-sm font-semibold text-blue-700 hover:underline"
                      to="/app/tasks"
                    >
                      All follow-ups
                    </Link>
                  </div>
                  {lead.tasks.length > 0 ? (
                    <ul className="mt-5 space-y-3">
                      {lead.tasks.map((task) => (
                        <li className="rounded-xl border border-slate-200 p-4" key={task.id}>
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-medium">{task.title}</h3>
                                {task.is_overdue && (
                                  <span className="rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-800">
                                    Overdue
                                  </span>
                                )}
                                {task.status !== 'pending' && (
                                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize text-slate-700">
                                    {task.status}
                                  </span>
                                )}
                              </div>
                              {task.details && (
                                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">
                                  {task.details}
                                </p>
                              )}
                              <p className="mt-2 text-sm text-slate-500">
                                Due {formatDate(task.due_at)}
                              </p>
                            </div>
                            {canEdit && task.status === 'pending' && (
                              <div className="flex flex-wrap items-end gap-2">
                                <label className="block">
                                  <span className="field-label">New due time</span>
                                  <input
                                    className="field-input"
                                    type="datetime-local"
                                    aria-label={`New due time for ${task.title}`}
                                    value={taskDueChanges[task.id] ?? singaporeDateAtNine()}
                                    onChange={(event) =>
                                      setTaskDueChanges((values) => ({
                                        ...values,
                                        [task.id]: event.target.value,
                                      }))
                                    }
                                  />
                                </label>
                                <button
                                  className="button-secondary"
                                  disabled={Boolean(busy) || !taskDueChanges[task.id]}
                                  onClick={() =>
                                    void runAction(`tasks/${task.id}/reschedule`, {
                                      due_at: singaporeInputToIso(taskDueChanges[task.id] ?? ''),
                                    })
                                  }
                                >
                                  Reschedule
                                </button>
                                <button
                                  className="button-primary"
                                  disabled={Boolean(busy)}
                                  onClick={() => void runAction(`tasks/${task.id}/complete`, {})}
                                >
                                  Complete
                                </button>
                                <button
                                  className="button-secondary"
                                  disabled={Boolean(busy)}
                                  onClick={() => void runAction(`tasks/${task.id}/cancel`, {})}
                                >
                                  Cancel
                                </button>
                              </div>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-4 text-sm text-slate-500">No follow-ups scheduled.</p>
                  )}
                  {canEdit && isOpen && (
                    <form
                      className="mt-5 space-y-4 border-t border-slate-100 pt-5"
                      onSubmit={(event: FormEvent) => {
                        event.preventDefault();
                        void runAction('tasks', {
                          title: taskTitle.trim(),
                          details: taskDetails.trim(),
                          due_at: singaporeInputToIso(taskDue),
                        });
                      }}
                    >
                      <h3 className="font-semibold">Schedule a follow-up</h3>
                      <Field label="Task">
                        <input
                          className="field-input"
                          maxLength={120}
                          required
                          value={taskTitle}
                          onChange={(event) => setTaskTitle(event.target.value)}
                          placeholder="Call customer about installation dates"
                        />
                      </Field>
                      <Field label="Due date and time (Singapore time)">
                        <input
                          className="field-input"
                          type="datetime-local"
                          required
                          value={taskDue}
                          onChange={(event) => setTaskDue(event.target.value)}
                        />
                      </Field>
                      <Field label="Details (optional)">
                        <textarea
                          className="field-input min-h-20"
                          maxLength={500}
                          value={taskDetails}
                          onChange={(event) => setTaskDetails(event.target.value)}
                          placeholder="Anything to prepare before following up"
                        />
                      </Field>
                      <button
                        className="button-primary"
                        disabled={Boolean(busy) || !taskTitle.trim()}
                      >
                        {busy === 'tasks' ? 'Scheduling…' : 'Schedule follow-up'}
                      </button>
                    </form>
                  )}
                </section>

                {canEdit && (
                  <section className="panel">
                    <h2 className="text-lg font-semibold">Add a note</h2>
                    <form
                      className="mt-5 space-y-4"
                      onSubmit={(event: FormEvent) => {
                        event.preventDefault();
                        void runAction('notes', { body: note.trim() });
                      }}
                    >
                      <Field label="Internal note">
                        <textarea
                          className="field-input min-h-28"
                          maxLength={2000}
                          required
                          value={note}
                          onChange={(event) => {
                            setNote(event.target.value);
                          }}
                          placeholder="Only your team can see this note"
                        />
                      </Field>
                      <button className="button-primary" disabled={Boolean(busy) || !note.trim()}>
                        {busy === 'notes' ? 'Saving…' : 'Save note'}
                      </button>
                    </form>
                  </section>
                )}
              </div>

              <section className="panel">
                <h2 className="text-lg font-semibold">Activity history</h2>
                <ol className="mt-5 space-y-5">
                  {[...lead.activity].reverse().map((event) => (
                    <li key={event.id} className="border-l-2 border-blue-200 pl-4">
                      <p className="whitespace-pre-wrap break-words text-sm font-medium">
                        {event.summary}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {formatDate(event.occurred_at)}
                        {event.actor_name ? ` · ${event.actor_name}` : ''}
                      </p>
                    </li>
                  ))}
                </ol>
                {lead.activity.length === 0 && (
                  <p className="mt-4 text-sm text-slate-500">No recorded activity.</p>
                )}
              </section>
            </div>
            <p className="mt-6 text-sm text-slate-500">
              Calls, messages, and quotes are recorded by staff; the app does not contact customers.
            </p>
          </>
        )}
      </div>
    </>
  );
}
