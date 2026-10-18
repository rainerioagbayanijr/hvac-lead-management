export type HealthResult = { status: 'ok' | 'unavailable' };

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, string[] | string> = {},
    public requestId?: string,
    public retryAfter?: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body) headers.set('Content-Type', 'application/json');
  const method = options.method ?? 'GET';
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) {
    const csrf = await api<{ csrf_token: string }>('/auth/csrf/');
    headers.set('X-CSRFToken', csrf.csrf_token);
  }
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (options.signal?.aborted) cancel();
  options.signal?.addEventListener('abort', cancel, { once: true });
  const timeout = window.setTimeout(cancel, 15000);
  try {
    const response = await fetch(`/api/v1${path}`, {
      ...options,
      headers,
      credentials: 'same-origin',
      mode: 'same-origin',
      cache: 'no-store',
      signal: controller.signal,
    });
    const data = await response.json().catch(() => {
      throw new ApiError(
        response.status,
        'invalid_response',
        'The server response could not be read.',
      );
    });
    if (!response.ok)
      throw new ApiError(
        response.status,
        data.code ?? 'request_error',
        data.message ?? 'The request failed.',
        data.fields,
        data.request_id,
        response.headers.get('Retry-After') ?? undefined,
      );
    return data as T;
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener('abort', cancel);
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError)
    return error.retryAfter
      ? `${error.message} Try again in ${error.retryAfter} seconds.`
      : error.message;
  return 'The server could not be reached. Check your connection and try again.';
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResult> {
  const response = await fetch('/api/v1/health/', {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    cache: 'no-store',
    signal,
  });
  const data: unknown = await response.json();
  if (
    data !== null &&
    typeof data === 'object' &&
    'status' in data &&
    ((response.status === 200 && data.status === 'ok') ||
      (response.status === 503 && data.status === 'unavailable'))
  ) {
    return { status: data.status };
  }
  throw new Error('Unexpected readiness response.');
}
