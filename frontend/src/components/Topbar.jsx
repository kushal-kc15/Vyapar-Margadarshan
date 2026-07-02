import { Moon, Sun } from 'lucide-react';
import { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { NotificationBell } from './NotificationBell.jsx';
import { OrgSwitcher } from './OrgSwitcher.jsx';
import { UserMenu } from './UserMenu.jsx';
import Logo from './Logo.jsx';
import { useTheme } from '../context/ThemeContext.jsx';

const PAGE_CONTEXT = [
  { path: '/dashboard', title: 'Overview', subtitle: 'Workspace snapshot' },
  { path: '/expenses', title: 'Expenses', subtitle: 'Record and track spending' },
  { path: '/approvals', title: 'Approvals', subtitle: 'Review pending expenses' },
  { path: '/budgets', title: 'Budgets', subtitle: 'Track spending against budgets' },
  { path: '/reports', title: 'Reports', subtitle: 'Approved expense insights' },
  { path: '/insights', title: 'Spending Intelligence', subtitle: 'Review budget pressure, unusual expense patterns, and AI-generated spending summaries.' },
  { path: '/vendors', title: 'Vendors', subtitle: 'Vendor spending history' },
  { path: '/team', title: 'Team', subtitle: 'Members and invitations' },
  { path: '/activity', title: 'Activity', subtitle: 'Workspace activity' },
  { path: '/settings', title: 'Settings', subtitle: 'Account and workspace preferences' },
];

const contextForPath = (pathname) =>
  PAGE_CONTEXT.find((item) => pathname === item.path || pathname.startsWith(`${item.path}/`)) ??
  PAGE_CONTEXT[0];

export function Topbar() {
  const location = useLocation();
  const { resolvedTheme, setTheme } = useTheme();
  const switchTo = resolvedTheme === 'dark' ? 'light' : 'dark';
  const themeLabel = `Switch to ${switchTo} mode`;
  const page = useMemo(() => contextForPath(location.pathname), [location.pathname]);

  return (
    <header className="sticky top-0 z-30 bg-paper/90 backdrop-blur border-b border-rule transition-shadow duration-200">
      <div className="flex h-16 items-center gap-2 px-3 sm:gap-3 sm:px-6">
        <div className="md:hidden shrink-0">
          <Logo size={32} />
        </div>

        <div className="min-w-0 flex-1 pr-2">
          <div className="flex min-w-0 items-baseline gap-1.5">
            <h1 className="truncate text-lg font-semibold leading-tight text-ink sm:text-xl">
              {page.title}
            </h1>
            <span className="hidden text-xs text-ink-faint sm:inline" aria-hidden="true">
              -
            </span>
            <p className="hidden min-w-0 truncate text-sm text-ink-muted sm:block">
              {page.subtitle}
            </p>
          </div>
        </div>

        <div className="flex min-w-0 shrink-0 items-center gap-2">
          <OrgSwitcher />
          <button
            type="button"
            onClick={() => setTheme(switchTo)}
            aria-label={themeLabel}
            title={themeLabel}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-sm border border-rule-strong bg-paper text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2"
          >
            {resolvedTheme === 'dark' ? (
              <Sun size={16} strokeWidth={1.6} aria-hidden="true" />
            ) : (
              <Moon size={16} strokeWidth={1.6} aria-hidden="true" />
            )}
          </button>
          <NotificationBell />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
