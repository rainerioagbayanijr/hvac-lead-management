const formatter = new Intl.DateTimeFormat('en-SG', {
  timeZone: 'Asia/Singapore',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});
export function formatDate(value: string) {
  return formatter.format(new Date(value));
}

export function singaporeDateAtNine(daysFromNow = 1) {
  const date = new Date(Date.now() + daysFromNow * 24 * 60 * 60 * 1000);
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Singapore',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return `${values.year}-${values.month}-${values.day}T09:00`;
}

export function singaporeInputToIso(value: string) {
  return new Date(`${value}:00+08:00`).toISOString();
}
