import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Receipt,
  CheckSquare,
  Wallet,
  BarChart3,
  BrainCircuit,
  BookOpen,
  Store,
  Users,
  Bell,
  Settings as SettingsIcon,
  FolderTree,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext.jsx';
import Logo from './Logo.jsx';
import { cn } from '../lib/utils.js';
import Badge from './Badge.jsx'; // our refined Badge

const PRIMARY = [
  { key: 'dashboard', to: '/dashboard', label: 'Overview', icon: LayoutDashboard, ownerOnly: false },
  { key: 'expenses', to: '/expenses', label: 'Expenses', icon: Receipt, ownerOnly: false },
  { key: 'approvals', to: '/approvals', label: 'Approvals', icon: CheckSquare, ownerOnly: true, badgeKey: 'pendingApprovals' },
  { key: 'budgets', to: '/budgets', label: 'Budgets', icon: Wallet, ownerOnly: true },
  { key: 'reports', to: '/reports', label: 'Reports', icon: BarChart3, ownerOnly: true },
  { key: 'insights', to: '/insights', label: 'Insights', icon: BrainCircuit, ownerOnly: true },
  { key: 'rules', to: '/rules', label: 'Rules', icon: BookOpen, ownerOnly: true },
  { key: 'vendors', to: '/vendors', label: 'Vendors', icon: Store, ownerOnly: true },
];

const SECONDARY = [
  { key: 'team', to: '/team', label: 'Team', icon: Users, ownerOnly: false },
  { key: 'activity', to: '/activity', label: 'Activity', icon: Bell, ownerOnly: false },
  { key: 'settings', to: '/settings', label: 'Settings', icon: SettingsIcon, ownerOnly: false },
];

export function Sidebar({ badges = {} }) {
  const { role } = useAuth();
  const isOwner = String(role ?? '').toUpperCase() === 'OWNER';
  const mobileItems = [...PRIMARY, ...SECONDARY].filter((item) => !item.ownerOnly || isOwner);

  const Item = ({ item }) => {
    const Icon = item.icon;
    const badge = item.badgeKey ? badges[item.badgeKey] : null;
    return (
      <NavLink
        to={item.to}
        className={({ isActive }) =>
          cn(
            'group flex h-9 items-center gap-2.5 rounded-sm pl-2.5 pr-3 text-sm transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2',
            isActive
              ? 'bg-ink text-paper font-medium shadow-sm'
              : 'text-ink-soft hover:bg-paper-deep hover:text-ink'
          )
        }
      >
        {({ isActive }) => (
          <>
            <Icon size={16} strokeWidth={1.5} className={cn('shrink-0 transition-colors', isActive ? 'text-paper' : 'text-ink-muted group-hover:text-ink')} />
            <span className="truncate">{item.label}</span>
            {badge != null && badge > 0 && (
              <Badge tone="cinnabar" className="ml-auto text-[10px] px-1.5 py-0.5">
                {badge}
              </Badge>
            )}
          </>
        )}
      </NavLink>
    );
  };

  return (
    <>
      <aside className="hidden md:flex md:flex-col w-60 shrink-0 border-r border-rule bg-paper h-screen sticky top-0">
        <div className="px-5 py-5 border-b border-rule">
          <Logo size={34} showText wordmarkSize="sm" />
        </div>
        <nav className="flex-1 px-2.5 py-4 overflow-y-auto">
          <ul className="space-y-0.5">
            {PRIMARY.map((item) => (!item.ownerOnly || isOwner) && (
              <li key={item.key}><Item item={item} /></li>
            ))}
          </ul>
          <div className="mt-6 pt-4 border-t border-rule">
            <div className="px-2.5 mb-2 flex items-center gap-1.5 text-micro uppercase tracking-eyebrow text-ink-muted">
              <FolderTree size={12} strokeWidth={1.5} />
              <span>Workspace</span>
            </div>
            <ul className="space-y-0.5">
              {SECONDARY.map((item) => (!item.ownerOnly || isOwner) && (
                <li key={item.key}><Item item={item} /></li>
              ))}
            </ul>
          </div>
        </nav>
        <div className="px-5 py-3 border-t border-rule flex items-center justify-between text-[10px] uppercase tracking-eyebrow text-ink-faint">
          <span>{role ?? 'Member'}</span>
          <span>v2.0</span>
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-paper/95 backdrop-blur supports-[padding:max(0px)]:pb-[max(env(safe-area-inset-bottom),0px)]">
        <ul className="flex items-stretch overflow-x-auto px-1.5 py-1.5">
          {mobileItems.map((item) => {
            const Icon = item.icon;
            const badge = item.badgeKey ? badges[item.badgeKey] : null;
            return (
              <li key={item.key} className="min-w-[4.25rem] flex-1">
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'relative flex min-h-12 flex-col items-center justify-center gap-0.5 rounded-full px-2 text-[11px] font-medium transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2',
                      isActive
                        ? 'bg-ink text-paper shadow-sm'
                        : 'text-ink-muted hover:bg-paper-deep hover:text-ink'
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon size={17} strokeWidth={1.6} className={isActive ? 'text-paper' : 'text-ink-muted'} />
                      <span className="max-w-full truncate">{item.label}</span>
                      {badge != null && badge > 0 && (
                        <span
                          className={cn(
                            'absolute -right-1 -top-1 min-w-4 rounded-full px-1 text-[10px] font-semibold leading-tight',
                            isActive ? 'bg-paper/20 text-paper' : 'bg-cinnabar-500 text-paper'
                          )}
                        >
                          {badge > 99 ? '99+' : badge}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
