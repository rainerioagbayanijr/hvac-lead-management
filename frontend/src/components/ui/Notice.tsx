import { useEffect, useRef, type ReactNode } from 'react';
export function Notice({ children, error = false }: { children: ReactNode; error?: boolean }) {
  const notice = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (error) notice.current?.focus();
  }, [error]);
  return (
    <div
      ref={notice}
      tabIndex={error ? -1 : undefined}
      role={error ? 'alert' : 'status'}
      className={`rounded-xl border p-4 text-sm leading-6 ${error ? 'border-red-200 bg-red-50 text-red-900' : 'border-blue-200 bg-blue-50 text-blue-900'}`}
    >
      {children}
    </div>
  );
}
