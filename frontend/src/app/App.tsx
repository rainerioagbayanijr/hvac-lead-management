import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router';
import type { ReactNode } from 'react';
import { AuthProvider, useAuth } from '../features/auth/AuthProvider';
import { LoginPage } from '../features/auth/LoginPage';
import { InquiryPage } from '../features/inquiries/InquiryPage';
import { LeadListPage } from '../features/leads/LeadListPage';
import { LeadDetailPage } from '../features/leads/LeadDetailPage';
import { NewLeadPage } from '../features/leads/NewLeadPage';
import { TaskListPage } from '../features/tasks/TaskListPage';
import { Notice } from '../components/ui/Notice';
import { AppShell } from './AppShell';

function Protected({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.loading) return <Notice>Checking your session…</Notice>;
  if (auth.error)
    return (
      <Notice error>
        {auth.error}{' '}
        <button className="underline" onClick={auth.reload}>
          Try again
        </button>
      </Notice>
    );
  if (!auth.session?.authenticated)
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />;
  return children;
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppShell>
          <Routes>
            <Route path="/" element={<InquiryPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/app/leads"
              element={
                <Protected>
                  <LeadListPage />
                </Protected>
              }
            />
            <Route
              path="/app/leads/:id"
              element={
                <Protected>
                  <LeadDetailPage />
                </Protected>
              }
            />
            <Route
              path="/app/leads/new"
              element={
                <Protected>
                  <NewLeadPage />
                </Protected>
              }
            />
            <Route
              path="/app/tasks"
              element={
                <Protected>
                  <TaskListPage />
                </Protected>
              }
            />
            <Route
              path="*"
              element={
                <>
                  <h1 className="page-title">Page not found</h1>
                  <Link className="mt-5 inline-block text-blue-700" to="/">
                    Return to service inquiry
                  </Link>
                </>
              }
            />
          </Routes>
        </AppShell>
      </AuthProvider>
    </BrowserRouter>
  );
}
