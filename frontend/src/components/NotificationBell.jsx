import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Check, Trash2 } from 'lucide-react';
import api from '../lib/api.js';
import { formatDate } from '../lib/date.js';
import { cn } from '../lib/utils.js';
import { Spinner, Skeleton } from './Feedback.jsx';

const POLL_INTERVAL = 5000;

const notificationTime = (notification) => notification?.time_ago || formatDate(notification?.created_at, 'short');
const notificationTitle = (notification) => notification?.title || 'Notification';
const notificationMessage = (notification) => notification?.message || 'No details available.';

const safeInternalPath = (url) => {
  if (!url) return '';
  try {
    const parsed = new URL(url, window.location.origin);
    if (!['http:', 'https:'].includes(parsed.protocol)) return '';
    if (parsed.origin !== window.location.origin) return '';
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return '';
  }
};

export function NotificationBell() {
  const navigate = useNavigate();
  const ref = useRef(null);
  const mounted = useRef(true);
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [markAllLoading, setMarkAllLoading] = useState(false);
  const [clearAllLoading, setClearAllLoading] = useState(false);

  // Load unread count with polling
  useEffect(() => {
    let cancelled = false;

    const loadUnreadCount = () => {
      api.get('/notifications/unread_count/')
        .then((response) => {
          if (cancelled || !mounted.current) return;
          const count = Number(response.data?.unread_count ?? response.data?.count ?? 0);
          setUnreadCount(Math.max(0, count));
        })
        .catch(() => {
          if (!cancelled && mounted.current && open) {
            setError('Notifications are unavailable.');
          }
        });
    };

    loadUnreadCount();
    const timer = setInterval(loadUnreadCount, POLL_INTERVAL);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [open]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // Close on click outside
  useEffect(() => {
    if (!open) return;

    const onClick = (event) => {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const loadRecent = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    return api.get('/notifications/recent/')
      .then((response) => {
        if (cancelled || !mounted.current) return null;
        const data = response.data;
        const list = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
        setNotifications(list);
        return list;
      })
      .catch(() => {
        if (!cancelled && mounted.current) {
          setError('Notifications could not be loaded.');
          setNotifications([]);
        }
        return [];
      })
      .finally(() => {
        if (!cancelled && mounted.current) setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!open) return undefined;

    let cancelled = false;

    const tick = () => {
      if (cancelled) return;
      loadRecent();
    };

    // Initial load when opening
    tick();

    // Lightweight refresh while dropdown is open
    const timer = setInterval(tick, POLL_INTERVAL);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [open, loadRecent]);

  const navigateSafely = (url) => {
    const path = safeInternalPath(url);
    if (!path) return;
    navigate(path);
  };

  const markRead = async (notification) => {
    if (!notification || actionLoadingId) return;
    setActionLoadingId(notification.id);
    setError('');

    try {
      const response = await api.post(`/notifications/${notification.id}/mark_read/`);
      const updated = response.data ?? notification;
      setNotifications((current) =>
        current.map((item) =>
          item.id === notification.id ? { ...item, ...updated, is_read: true } : item
        )
      );
      setUnreadCount((current) => Math.max(0, current - (notification.is_read ? 0 : 1)));
      await loadRecent();

      if (updated.action_url ?? notification.action_url) {
        navigateSafely(updated.action_url ?? notification.action_url);
      }
    } catch {
      if (mounted.current) setError('Could not mark notification as read.');
    } finally {
      if (mounted.current) setActionLoadingId(null);
      setOpen(false);
    }
  };

  const markAllRead = async () => {
    if (markAllLoading) return;
    setMarkAllLoading(true);
    setError('');

    try {
      await api.post('/notifications/mark_all_read/');
      setUnreadCount(0);
      setNotifications((current) =>
        current.map((item) => ({ ...item, is_read: true }))
      );
      await loadRecent();
    } catch {
      if (mounted.current) setError('Could not mark notifications as read.');
    } finally {
      if (mounted.current) setMarkAllLoading(false);
    }
  };

  const clearAll = async () => {
    if (clearAllLoading || notifications.length === 0) return;
    setClearAllLoading(true);
    setError('');

    try {
      await api.delete('/notifications/clear_all/');
      setNotifications([]);
      setUnreadCount(0);
    } catch {
      if (mounted.current) setError('Could not clear notifications.');
    } finally {
      if (mounted.current) setClearAllLoading(false);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="relative h-9 w-9 inline-flex items-center justify-center rounded-sm border border-rule-strong bg-paper text-ink-soft hover:bg-paper-deep hover:text-ink transition-colors"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Notifications"
      >
        <Bell size={17} strokeWidth={1.5} />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[1.1rem] h-4 px-1 inline-flex items-center justify-center rounded-pill bg-cinnabar-500 text-[10px] font-semibold text-paper num">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 w-80 max-w-[calc(100vw-1.5rem)] bg-paper border border-rule rounded-md shadow-lift overflow-hidden animate-drawer">
          <div className="px-3 py-2.5 border-b border-rule flex items-center justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-ink">Notifications</p>
              <p className="text-xs text-ink-muted">{unreadCount} unread</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={markAllRead}
                disabled={markAllLoading || clearAllLoading || unreadCount === 0}
                className="inline-flex items-center gap-1 text-xs font-medium text-ink-soft hover:text-ink disabled:text-ink-faint disabled:cursor-not-allowed transition-colors"
              >
                {markAllLoading ? <Spinner size={12} /> : <Check size={13} strokeWidth={1.5} />}
                Mark all read
              </button>
              <button
                type="button"
                onClick={clearAll}
                disabled={clearAllLoading || markAllLoading || notifications.length === 0}
                className="inline-flex items-center gap-1 text-xs font-medium text-cinnabar-600 hover:text-cinnabar-700 disabled:text-ink-faint disabled:cursor-not-allowed transition-colors"
              >
                {clearAllLoading ? <Spinner size={12} /> : <Trash2 size={13} strokeWidth={1.5} />}
                Clear all
              </button>
            </div>
          </div>

          <div className="max-h-[28rem] overflow-y-auto">
            {loading ? (
              <div className="px-4 py-3 space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="flex items-start gap-2.5">
                    <Skeleton className="h-1.5 w-1.5 rounded-full mt-1.5" />
                    <div className="flex-1 space-y-1.5">
                      <Skeleton className="h-3 w-3/4" />
                      <Skeleton className="h-2.5 w-1/2" />
                      <Skeleton className="h-2 w-1/3" />
                    </div>
                  </div>
                ))}
              </div>
            ) : error ? (
              <div className="px-4 py-6 text-sm text-cinnabar-700">
                <p className="font-medium">Notification issue</p>
                <p className="mt-1 text-cinnabar-600">{error}</p>
              </div>
            ) : notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-ink-muted">
                <Bell size={20} className="mx-auto mb-2 text-ink-faint" strokeWidth={1.5} />
                <p>No notifications yet.</p>
              </div>
            ) : (
              <ul className="divide-y divide-rule">
                {notifications.map((notification) => {
                  const unread = !notification.is_read;
                  const busy = actionLoadingId === notification.id;
                  return (
                    <li key={notification.id}>
                      <button
                        type="button"
                        onClick={() => markRead(notification)}
                        disabled={busy}
                        className={cn(
                          'w-full px-3 py-3 text-left transition-colors disabled:cursor-wait',
                          unread ? 'bg-paper-deep/70 hover:bg-paper-deep' : 'bg-paper hover:bg-paper-deep'
                        )}
                      >
                        <div className="flex items-start gap-2.5">
                          <span
                            className={cn(
                              'mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full',
                              unread ? 'bg-cinnabar-500' : 'bg-ink-faint'
                            )}
                            aria-hidden="true"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-2">
                              <p
                                className={cn(
                                  'text-sm font-medium truncate',
                                  unread ? 'text-ink' : 'text-ink-soft'
                                )}
                              >
                                {notificationTitle(notification)}
                              </p>
                              {busy && <Spinner size={12} className="text-ink-muted shrink-0 mt-0.5" />}
                            </div>
                            <p className="mt-0.5 text-xs text-ink-muted break-words">
                              {notificationMessage(notification)}
                            </p>
                            <p className="mt-1.5 text-[11px] text-ink-faint num">
                              {notificationTime(notification)}
                            </p>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
