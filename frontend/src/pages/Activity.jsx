import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Edit3, FileText, Plus, Receipt, RefreshCw, Search, Trash2, XCircle } from 'lucide-react';
import api from '../lib/api.js';
import { useAuth } from '../context/AuthContext.jsx';
import { Panel, PanelHeader, PanelTitle } from '../components/Panel.jsx';
import { Avatar } from '../components/Avatar.jsx';
import { formatDate } from '../lib/date.js';
import { EmptyState, ErrorState, Spinner } from '../components/Feedback.jsx';
import { Money } from '../components/Money.jsx';
import PaginationControls from '../components/PaginationControls.jsx';
import Button from '../components/Button.jsx';
import { Select } from '../components/Field.jsx';
import { cn } from '../lib/utils.js';

const VERB_ICON = {
  created: Plus,
  submitted: FileText,
  approved: CheckCircle2,
  rejected: XCircle,
  updated: Edit3,
  deleted: Trash2,
  removed: Trash2,
  paid: CheckCircle2,
  reimbursed: CheckCircle2,
};

const normalizeVerb = (row) => {
  const action = row?.action_type ?? row?.action ?? row?.verb;
  if (!action) return 'created';
  return String(action).toLowerCase();
};
const actionKind = (verb) => verb.split('_').filter(Boolean).at(-1) ?? verb;
const actorName = (row) => [
  row?.user_name,
  row?.actor_name,
  row?.actor?.username,
  row?.user?.username,
  row?.user_email,
].find((value) => String(value ?? '').trim()) ?? 'System user';
const actorEmail = (row) => row?.user_email ?? row?.actor?.email ?? row?.user?.email ?? '';
const objectText = (row) => row?.description ?? row?.object_repr ?? row?.target ?? 'an expense';
const eventTime = (row) => row?.timestamp ?? row?.created_at ?? row?.date ?? null;
const metadataItems = (row) => {
  const metadata = row?.metadata;
  if (!metadata || typeof metadata !== 'object') return [];
  const details = [];
  if (metadata.expense_id != null) details.push(`Expense #${metadata.expense_id}`);
  if (metadata.budget_id != null) details.push(`Budget #${metadata.budget_id}`);
  if (metadata.member_id != null) details.push(`Member #${metadata.member_id}`);
  if (metadata.status) details.push(`Status: ${readableVerb(String(metadata.status).toLowerCase())}`);
  if (metadata.role) details.push(`Role: ${readableVerb(String(metadata.role).toLowerCase())}`);
  return details;
};

const readableVerb = (verb) => {
  if (!verb) return 'Created';
  return verb
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
};

const eventTone = (kind) => {
  if (kind === 'approved' || kind === 'paid' || kind === 'reimbursed') return 'moss';
  if (kind === 'rejected' || kind === 'deleted' || kind === 'removed') return 'cinnabar';
  if (kind === 'created' || kind === 'updated' || kind === 'joined' || kind === 'invited') return 'forest';
  return 'ink';
};

export default function Activity() {
  const { currency } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [q, setQ] = useState('');
  const [verbFilter, setVerbFilter] = useState('');

  const activityPageSize = 15;
  const [activityPage, setActivityPage] = useState(1);

  const loadActivity = useCallback(() => {
    setLoading(true);
    setLoadError('');
    api.get('/activity-logs/', { params: { page_size: 100 } })
      .then((response) => {
        const data = response.data?.results ?? response.data ?? [];
        setRows(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        setRows([]);
        setLoadError('Activity logs could not be loaded. No workspace data was changed.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadActivity(); }, [loadActivity]);

  useEffect(() => {
    setActivityPage(1);
  }, [q, verbFilter]);

  const normalizedRows = useMemo(
    () => rows.map((row, index) => {
      const verb = normalizeVerb(row);
      const kind = actionKind(verb);
      return {
        key: row?.id ?? `${verb}-${index}`,
        row,
        verb,
        kind,
        actionLabel: readableVerb(verb),
        actor: actorName(row),
        actorEmail: actorEmail(row),
        object: objectText(row),
        metadata: metadataItems(row),
        timestamp: eventTime(row),
        amount: row?.amount,
        currency: row?.currency ?? currency,
      };
    }),
    [rows, currency]
  );

  const actionTypes = useMemo(
    () => Array.from(new Set(normalizedRows.map((event) => event.verb))).filter(Boolean).sort(),
    [normalizedRows]
  );

  const filteredRows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return normalizedRows.filter((event) => {
      const matchesVerb = !verbFilter || event.verb === verbFilter;
      const haystack = `${event.actor} ${event.actorEmail} ${event.verb} ${event.actionLabel} ${event.object} ${event.row?.description ?? ''}`.toLowerCase();
      const matchesSearch = !needle || haystack.includes(needle);
      return matchesVerb && matchesSearch;
    });
  }, [normalizedRows, q, verbFilter]);

  const pagedFilteredRows = useMemo(() => {
    const start = (activityPage - 1) * activityPageSize;
    const end = start + activityPageSize;
    return filteredRows.slice(start, end);
  }, [filteredRows, activityPage]);

  const latestTimestamp = normalizedRows
    .map((event) => event.timestamp)
    .filter(Boolean)
    .sort()
    .at(-1);
  const hasFilters = Boolean(q.trim() || verbFilter);
  const mostCommonAction = useMemo(() => {
    if (normalizedRows.length === 0) return 'No activity';
    const counts = normalizedRows.reduce((map, event) => {
      map.set(event.verb, (map.get(event.verb) ?? 0) + 1);
      return map;
    }, new Map());
    const [verb] = Array.from(counts.entries()).sort((a, b) => b[1] - a[1])[0] ?? [];
    return readableVerb(verb);
  }, [normalizedRows]);
  const activeFilterLabel = hasFilters
    ? [q.trim() ? 'Search' : null, verbFilter ? readableVerb(verbFilter) : null].filter(Boolean).join(' + ')
    : 'None';

  const clearFilters = () => {
    setQ('');
    setVerbFilter('');
  };
  const pageActions = useMemo(
    () => (
      <Button variant="secondary" size="sm" iconLeft={<RefreshCw size={14} />} onClick={loadActivity} disabled={loading}>
        Refresh
      </Button>
    ),
    [loadActivity, loading],
  );

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-6 pt-2 sm:px-6 lg:px-8">
      <div className="mb-2 flex flex-wrap items-center justify-end gap-1.5 border-b border-rule pb-2" aria-label="Activity actions">
        {pageActions}
      </div>

      {!loading && !loadError && normalizedRows.length > 0 && (
        <section className="pt-2" aria-label="Activity summary">
          <div className="grid grid-cols-2 overflow-hidden rounded-md border border-rule bg-paper lg:grid-cols-4">
            <SummaryMetric label="Shown" value={filteredRows.length} helper={`${normalizedRows.length} loaded`} />
            <SummaryMetric label="Common action" value={mostCommonAction} />
            <SummaryMetric label="Latest" value={latestTimestamp ? formatDate(latestTimestamp, 'relative') : 'Unavailable'} />
            <SummaryMetric label="Filters" value={activeFilterLabel} />
          </div>
        </section>
      )}

      <section className="mt-3 rounded-md border border-rule bg-paper-deep/60 px-3 py-2.5" aria-label="Activity filters">
        <div className="grid grid-cols-1 gap-2.5 md:grid-cols-12 md:items-end">
          <div className="md:col-span-6">
            <label className="field-label" htmlFor="activity-search">Search activity</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" strokeWidth={1.5} aria-hidden="true" />
              <input
                id="activity-search"
                type="search"
                value={q}
                onChange={(event) => setQ(event.target.value)}
                placeholder="Search actor, action, or description"
                className="w-full h-10 pl-9 pr-3 bg-paper-deep border border-rule rounded-sm text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:bg-paper focus:border-cinnabar-500 focus:ring-2 focus:ring-cinnabar-500/15 transition-colors"
              />
            </div>
          </div>
          <div className="md:col-span-3">
            <Select label="Action type" value={verbFilter} onChange={(event) => setVerbFilter(event.target.value)}>
              <option value="">All actions</option>
              {actionTypes.map((verb) => <option key={verb} value={verb}>{readableVerb(verb)}</option>)}
            </Select>
          </div>
          <div className="md:col-span-3 flex items-end justify-between gap-3">
            <p className="pb-2 text-xs font-medium text-ink-muted">{filteredRows.length} shown</p>
            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>Clear</Button>
            )}
          </div>
        </div>
      </section>

      <Panel className="mt-3 overflow-hidden">
        <PanelHeader className="!py-3">
          <div>
            <PanelTitle>Audit trail</PanelTitle>
            <p className="mt-0.5 text-xs text-ink-muted">Workspace actions in newest-first order.</p>
          </div>
        </PanelHeader>
        {loading ? (
          <div className="py-10 flex flex-col items-center justify-center gap-3 text-sm text-ink-muted">
            <Spinner className="text-ink-muted" />
            <span>Loading activity...</span>
          </div>
        ) : loadError ? (
          <ErrorState
            title="Activity is unavailable"
            description={loadError}
            action={<Button variant="secondary" onClick={loadActivity}>Try again</Button>}
          />
        ) : normalizedRows.length === 0 ? (
          <EmptyState
            title="No activity yet"
            description="Workspace activity will appear here."
          />
        ) : filteredRows.length === 0 ? (
          <EmptyState
            title="No activity matches this view"
            description="Clear filters to show all activity."
            action={<Button variant="secondary" onClick={clearFilters}>Clear filters</Button>}
          />
        ) : (
          <>
            <ol className="relative divide-y divide-rule md:before:absolute md:before:bottom-5 md:before:left-9 md:before:top-5 md:before:w-px md:before:bg-rule">
              {pagedFilteredRows.map((event) => (
                <ActivityItem key={event.key} event={event} />
              ))}
            </ol>

            <PaginationControls
              page={activityPage}
              setPage={setActivityPage}
              pageSize={activityPageSize}
              totalItems={filteredRows.length}
            />
          </>
        )}
      </Panel>
    </div>
  );
}

function ActivityItem({ event }) {
  const Icon = VERB_ICON[event.kind] ?? Receipt;
  const tone = eventTone(event.kind);
  const toneClass = tone === 'moss'
    ? 'border-moss-200 bg-moss-50 text-moss-700'
    : tone === 'cinnabar'
      ? 'border-cinnabar-200 bg-cinnabar-50 text-cinnabar-700'
      : tone === 'forest'
        ? 'border-forest-200 bg-forest-50 text-forest-700'
        : 'border-rule bg-paper-deep text-ink-soft';

  return (
    <li className="relative px-4 py-3.5 transition-colors hover:bg-paper-deep/35 md:pl-16 md:pr-5">
      <span className={cn('mb-3 flex h-8 w-8 items-center justify-center rounded-pill border md:absolute md:left-5 md:top-3.5', toneClass)}>
        <Icon size={14} strokeWidth={1.5} aria-hidden="true" />
      </span>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Avatar name={event.actor} size={22} />
            <span className="min-w-0 break-words text-sm font-semibold text-ink">{event.actor}</span>
            {event.actorEmail && event.actorEmail !== event.actor && (
              <span className="truncate text-xs text-ink-muted">{event.actorEmail}</span>
            )}
            <span className={cn('rounded-sm border px-1.5 py-0.5 text-[11px] font-medium', toneClass)}>{event.actionLabel}</span>
          </div>
          <p className="mt-1.5 max-w-3xl break-words text-sm leading-relaxed text-ink-soft">
            {event.object}
          </p>
          {event.metadata.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {event.metadata.map((item) => (
                <span key={item} className="rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] text-ink-muted">{item}</span>
              ))}
            </div>
          )}
        </div>
        <div className="shrink-0 sm:text-right">
          <p className="text-xs font-medium text-ink-muted" title={event.timestamp ? formatDate(event.timestamp, 'long') : undefined}>
            {event.timestamp ? formatDate(event.timestamp, 'relative') : 'Time unavailable'}
          </p>
          {event.timestamp && <p className="mt-0.5 text-[11px] text-ink-muted">{formatDate(event.timestamp, 'long')}</p>}
          {event.amount != null && (
            <p className="mt-1.5 text-sm text-ink tabular-nums">
              <Money value={event.amount} currency={event.currency} />
            </p>
          )}
        </div>
      </div>
    </li>
  );
}

function SummaryMetric({ label, value, helper }) {
  return (
    <div className="border-b border-rule px-3 py-2.5 odd:border-r even:border-r-0 lg:border-b-0 lg:border-r lg:px-4 lg:last:border-r-0">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 break-words text-base font-semibold text-ink sm:text-lg">{value}</p>
      {helper && <p className="mt-0.5 text-[11px] text-ink-muted">{helper}</p>}
    </div>
  );
}
