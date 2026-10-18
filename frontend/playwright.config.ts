import { defineConfig } from '@playwright/test';

const backendPort = process.env.E2E_BACKEND_PORT ?? '8001';
const djangoCommand =
  process.env.E2E_BACKEND_COMMAND ??
  (process.platform === 'win32'
    ? `..\\.venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:${backendPort}`
    : `python manage.py runserver 127.0.0.1:${backendPort}`);

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: djangoCommand,
      cwd: process.env.E2E_BACKEND_CWD ?? '../backend',
      url: `http://127.0.0.1:${backendPort}/health/`,
      env: {
        DJANGO_CSRF_TRUSTED_ORIGINS: [
          process.env.DJANGO_CSRF_TRUSTED_ORIGINS,
          'http://127.0.0.1:5174',
        ]
          .filter(Boolean)
          .join(','),
      },
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: 'npm run dev -- --force --host 127.0.0.1 --port 5174',
      url: 'http://127.0.0.1:5174/',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
