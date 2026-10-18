import { expect, test, type Page } from '@playwright/test';

const admin = {
  username: process.env.E2E_ADMIN_USERNAME ?? 'demo_admin',
  password: process.env.E2E_ADMIN_PASSWORD ?? '',
};
const staff = {
  username: process.env.E2E_STAFF_USERNAME ?? 'demo_staff',
  password: process.env.E2E_STAFF_PASSWORD ?? '',
};

test.beforeEach(async ({ page }) => {
  page.on('pageerror', (error) => console.error(`Browser page error: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') console.error(`Browser console error: ${message.text()}`);
  });
  page.on('response', (response) => {
    if (response.status() >= 400) {
      console.error(`Browser request failed: ${response.status()} ${response.url()}`);
    }
  });
});

async function login(page: Page, username: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page).toHaveURL(/\/app\//);
}

function singaporeInputInFuture(days = 3) {
  const date = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T10:00`;
}

test('customer inquiry flows into assignment and scheduled follow-up', async ({ page }) => {
  test.skip(!admin.password, 'Set E2E_ADMIN_PASSWORD to run browser tests.');
  await page.goto('/');
  await page.getByLabel('Your name').fill('E2E Synthetic Customer');
  await page.getByLabel('Phone number').fill('+65 8000 0999');
  await page.getByLabel('Email address').fill('e2e.customer@example.test');
  await page.getByLabel('How can we help? (optional)').fill('Synthetic Playwright workflow.');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Send inquiry' }).click();
  const confirmation = page.getByRole('status');
  await expect(confirmation.getByText('Your inquiry reference')).toBeVisible();
  const reference = (await confirmation.innerText()).split('\n').at(-1)?.trim();
  expect(reference).toMatch(/^[0-9a-f-]{36}$/i);
  await login(page, admin.username, admin.password);
  await page.goto(`/app/leads/${reference}`);
  await page.getByRole('button', { name: 'Claim this inquiry' }).click();
  await expect(page.getByText('Current owner:')).toContainText('Demo Owner');
  await page.getByLabel('Task').fill('E2E confirm installation dates');
  await page.getByLabel('Due date and time (Singapore time)').fill(singaporeInputInFuture());
  await page.getByRole('button', { name: 'Schedule follow-up' }).click();
  await expect(page.getByRole('heading', { name: 'E2E confirm installation dates' })).toBeVisible();
});

test('staff can reschedule overdue work and complete a follow-up', async ({ page }) => {
  test.skip(!staff.password, 'Set E2E_STAFF_PASSWORD to run browser tests.');
  await login(page, staff.username, staff.password);
  await page.goto('/app/tasks?status=pending&due=overdue');
  await expect(
    page
      .getByRole('listitem')
      .filter({ hasText: 'Call to confirm service date' })
      .getByText('Overdue', { exact: true }),
  ).toBeVisible();
  const overdueTask = page
    .getByRole('listitem')
    .filter({ hasText: 'Call to confirm service date' });
  await overdueTask
    .getByLabel('New due time for Call to confirm service date')
    .fill(singaporeInputInFuture());
  await overdueTask.getByRole('button', { name: 'Reschedule' }).click();
  await expect(overdueTask).toHaveCount(0);

  await page.goto('/app/tasks?status=pending&due=all');
  const quoteTask = page.getByRole('listitem').filter({ hasText: 'Send quote reminder' });
  await quoteTask.getByRole('button', { name: 'Complete' }).click();
  await page.getByLabel('Status').selectOption('completed');
  await expect(page.getByText('Send quote reminder')).toBeVisible();
  await expect(page.getByText('completed', { exact: true })).toBeVisible();
});

test('staff can view team leads but cannot edit a lead owned by another colleague', async ({
  page,
}) => {
  test.skip(!staff.password, 'Set E2E_STAFF_PASSWORD to run browser tests.');
  await login(page, staff.username, staff.password);
  await page.goto('/app/leads');
  await page.getByRole('link', { name: 'Sofia Ong' }).click();
  await expect(page.getByText('This inquiry belongs to another staff member.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Record customer contact' })).toHaveCount(0);
});

test('admin can safely retry a recorded simulated notification failure', async ({ page }) => {
  test.skip(!admin.password, 'Set E2E_ADMIN_PASSWORD to run browser tests.');
  await login(page, admin.username, admin.password);
  await page.goto('/app/integrations');
  const failedExecution = page.getByRole('listitem').filter({ hasText: 'Priya Nair' });
  await expect(failedExecution.getByText('Needs review')).toHaveCount(0);
  await failedExecution.getByRole('button', { name: 'Retry safely' }).click();
  await expect(failedExecution.getByText('Pending')).toBeVisible();
  await expect(failedExecution.getByRole('button', { name: 'Retry safely' })).toHaveCount(0);
});
