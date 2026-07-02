import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar.jsx';
import { Topbar } from './Topbar.jsx';
import { useEffect, useState } from 'react';
import api from '../lib/api.js';
import { useAuth } from '../context/AuthContext.jsx';

export function AppShell() {
  const location = useLocation();
  const { token, organization } = useAuth();
  const [badges, setBadges] = useState({});
  const [loading, setLoading] = useState(true);
  const organizationId = organization?.id ?? 'none';

  useEffect(() => {
    setBadges({});
    if (!token || !organization?.id) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    api.get('/expenses/pending_approvals/')
      .then((r) => {
        if (cancelled) return;
        const total = r.data?.count ?? r.data?.total ?? r.data?.length ?? 0;
        setBadges((b) => ({ ...b, pendingApprovals: total }));
      })
      .catch(() => {
        // Silently fail – badge is a convenience, not critical.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token, organization?.id]);

  return (
    <div className="flex min-h-screen bg-paper">
      <Sidebar badges={badges} />
      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="min-h-[calc(100vh-4rem)] min-w-0 flex-1 overflow-x-hidden pb-20 md:pb-0">
          <div
            key={`${organizationId}:${location.pathname}`}
            className="min-h-[calc(100vh-4rem)] min-w-0 animate-route-in"
          >
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
