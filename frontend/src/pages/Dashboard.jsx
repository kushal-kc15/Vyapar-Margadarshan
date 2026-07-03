import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, ChevronRight } from "lucide-react";
import api from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { Panel } from "../components/Panel.jsx";
import Button from "../components/Button.jsx";
import { Money } from "../components/Money.jsx";
import { Avatar } from "../components/Avatar.jsx";
import { formatDate } from "../lib/date.js";
import { Skeleton } from "../components/Feedback.jsx";
import { cn } from "../lib/utils.js";
import { formatCurrency } from "../lib/currency.js";
import { formatCategoryLabel } from "../lib/categories.js";

/* ------------------------------------------------------------------ *
 * Dashboard — financial statement, not a SaaS hero.
 * ------------------------------------------------------------------ */

const STATUS_DOT = {
  approved: "bg-moss-500",
  paid: "bg-moss-500",
  settled: "bg-moss-500",
  pending: "bg-saffron-500",
  submitted: "bg-saffron-500",
  draft: "bg-ink-faint",
  rejected: "bg-cinnabar-500",
  reimbursed: "bg-ink-faint",
};

const personName = (e) =>
  e?.submitted_by_name ?? e?.user_name ?? e?.user_details?.username ?? "—";

const categoryName = (v) => (v ? formatCategoryLabel(v) : "—");

const statusName = (v) => {
  if (!v) return "Draft";
  return v
    .toString()
    .toLowerCase()
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

const currentDateString = () =>
  new Date().toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

const greeting = () => {
  const h = new Date().getHours();
  return h < 5
    ? "Late night"
    : h < 12
      ? "Good morning"
      : h < 17
        ? "Good afternoon"
        : "Good evening";
};

const parseCalendarDate = (value) =>
  typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T00:00:00`)
    : new Date(value);

/* ------------------------------------------------------------------ *
 * Reveal — fades a block in on mount with a configurable delay.
 * ------------------------------------------------------------------ */
function Reveal({ delay = 0, className, children }) {
  return (
    <div
      className={cn("animate-fade-in-up", className)}
      style={{ animationDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * useCountUp — animates a number on mount and on target change.
 * ------------------------------------------------------------------ */
function useCountUp(target, duration = 1100) {
  const [v, setV] = useState(0);
  const prev = useRef(0);
  useEffect(() => {
    let raf;
    const start = performance.now();
    const from = prev.current;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setV(from + (target - from) * eased);
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        prev.current = target;
      }
    };
    raf = requestAnimationFrame(tick);
    return () => raf && cancelAnimationFrame(raf);
  }, [target, duration]);
  return v;
}

/* ------------------------------------------------------------------ *
 * AreaChart — minimal SVG area chart with hover crosshair + tooltip.
 * ------------------------------------------------------------------ */
function AreaChart({ data, height = 140, currency = "NPR" }) {
  const [hover, setHover] = useState(-1);
  const ref = useRef(null);
  const [w, setW] = useState(800);
  const id = useId();

  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([entry]) => setW(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  const safe = useMemo(
    () => (data || []).map((d) => ({ ...d, value: Number(d.value) || 0 })),
    [data],
  );

  if (safe.length === 0) {
    return <div ref={ref} style={{ height }} className="w-full" />;
  }

  const max = Math.max(...safe.map((d) => d.value), 1);
  const stepX = w / Math.max(safe.length - 1, 1);
  const padY = 6;
  const innerH = height - padY * 2;
  const points = safe.map((d, i) => ({
    x: i * stepX,
    y: padY + (1 - d.value / max) * innerH,
    value: d.value,
    label: d.label,
  }));

  const line = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${points.at(-1).x.toFixed(1)},${height} L0,${height} Z`;
  const last = points.at(-1);

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      <svg width={w} height={height} className="block overflow-visible">
        <defs>
          <linearGradient id={`area-${id}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#345E48" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#345E48" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill={`url(#area-${id})`} />
        <path
          d={line}
          fill="none"
          stroke="#345E48"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            strokeDasharray: w * 2,
            strokeDashoffset: w * 2,
            animation: "draw 1.4s 0.2s ease-out forwards",
          }}
        />
        {points.map((p, i) => (
          <rect
            key={i}
            x={Math.max(0, p.x - stepX / 2)}
            y={0}
            width={stepX}
            height={height}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(-1)}
          />
        ))}
        {hover >= 0 && points[hover] && (
          <>
            <line
              x1={points[hover].x}
              x2={points[hover].x}
              y1={0}
              y2={height}
              stroke="#cbc3b1"
              strokeWidth={1}
              strokeDasharray="2 3"
            />
            <circle
              cx={points[hover].x}
              cy={points[hover].y}
              r={4}
              fill="#284A39"
            />
            <circle
              cx={points[hover].x}
              cy={points[hover].y}
              r={2}
              fill="#fbfaf7"
            />
          </>
        )}
        {last && hover < 0 && (
          <circle cx={last.x} cy={last.y} r={3} fill="#284A39" />
        )}
      </svg>
      {hover >= 0 && points[hover] && (
          <div
            className="absolute pointer-events-none px-2 py-1 bg-ink text-paper text-[11px] num rounded-xs whitespace-nowrap shadow-sm"
            style={{
              left: points[hover].x,
              top: points[hover].y - 8,
              transform: "translate(-50%, -100%)",
            }}
          >
          {points[hover].label} ·{" "}
          {formatCurrency(points[hover].value, currency)}
        </div>
      )}
    </div>
  );
}

/** A 6px dot that encodes status. */
function StatusDot({ status }) {
  const tone =
    STATUS_DOT[(status ?? "").toString().toLowerCase()] ?? "bg-ink-faint";
  return (
    <span
      aria-hidden
      className={cn("inline-block h-1.5 w-1.5 rounded-full shrink-0", tone)}
    />
  );
}

/* ------------------------------------------------------------------ *
 * The page.
 * ------------------------------------------------------------------ */
export default function Dashboard() {
  const { organization, currency, user, role: authRole } = useAuth();

  const rawRole = authRole ?? null;
  const normalizedRole =
    typeof rawRole === "string" ? rawRole.toLowerCase() : "";
  const isOwner = normalizedRole === "owner";
  const isStaff = normalizedRole === "staff";
  const showAwaitingReview = isOwner || !rawRole;
  const showBudgets = isOwner || !rawRole;

  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [recent, setRecent] = useState([]);
  const [pending, setPending] = useState([]);
  const [budgets, setBudgets] = useState([]);
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const finish = () => {
      if (!cancelled) setLoading(false);
    };
    const maxWait = setTimeout(finish, 2500);

    api
      .get("/expenses/dashboard_metrics/")
      .then((r) => {
        if (!cancelled)
          setSummary((s) => ({ ...(s ?? {}), ...(r.data ?? {}) }));
        finish();
      })
      .catch(() => finish());

    api
      .get("/expenses/", { params: { page_size: 8 } })
      .then((r) => {
        if (!cancelled) setRecent(r.data?.results ?? r.data ?? []);
      })
      .catch(() => {});

    api
      .get("/expenses/pending_approvals/")
      .then((r) => {
        if (!cancelled) setPending(r.data?.results ?? r.data ?? []);
      })
      .catch(() => {});

    api
      .get("/budgets/", { params: { active: true, page_size: 6 } })
      .then((r) => {
        if (!cancelled) setBudgets(r.data?.results ?? r.data ?? []);
      })
      .catch(() => {});

    api
      .get("/analytics/category-breakdown/")
      .then((r) => {
        if (!cancelled) {
          const data =
            r.data?.breakdown ??
            r.data?.categories ??
            r.data?.results ??
            r.data ??
            [];
          setCategories(Array.isArray(data) ? data : []);
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      clearTimeout(maxWait);
    };
  }, []);

  const monthSeries = useMemo(() => {
    const points = summary?.daily_trend ?? [];
    if (
      !Array.isArray(points) ||
      points.length === 0 ||
      Number(summary?.month?.count ?? 0) === 0
    ) {
      return [];
    }
    return points.map((point) => ({
      label: parseCalendarDate(point.date).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      }),
      value: Number(point.amount) || 0,
    }));
  }, [summary]);

  const todaySpend = summary?.today?.total ?? 0;
  const weekSpend = summary?.week?.total ?? 0;
  const monthSpend = summary?.month?.total ?? 0;
  const previousMonthSpend = summary?.month?.previous_total ?? 0;
  const pendingAmount = pending.reduce(
    (s, e) => s + (Number(e.amount) || 0),
    0,
  );
  const monthDelta = summary?.month?.growth ?? null;
  const spendingDays = useMemo(
    () => monthSeries.filter((point) => point.value > 0),
    [monthSeries],
  );
  const highestSpendingDay = useMemo(
    () =>
      spendingDays.reduce(
        (highest, point) =>
          !highest || point.value > highest.value ? point : highest,
        null,
      ),
    [spendingDays],
  );
  const comparisonLabel = useMemo(() => {
    if (previousMonthSpend <= 0 || monthDelta == null) return null;
    if (monthDelta <= -90) return "Significantly lower than last month";
    if (monthDelta >= 200) return "Significantly higher than last month";
    if (Math.abs(monthDelta) < 1) return "About same as last month";
    return `${monthDelta > 0 ? "Up" : "Down"} ${Math.abs(monthDelta)}% vs last month`;
  }, [monthDelta, previousMonthSpend]);

  const topCategories = useMemo(() => {
    const byCat = new Map();
    (Array.isArray(categories) ? categories : []).forEach((c) => {
      const key = categoryName(c.category ?? c.name ?? c.label);
      const value = Number(c.total ?? c.amount ?? c.total_amount) || 0;
      byCat.set(key, (byCat.get(key) || 0) + value);
    });
    const total = Array.from(byCat.values()).reduce((s, v) => s + v, 0) || 1;
    return Array.from(byCat.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, value]) => ({
        name,
        value,
        pct: Math.max(2, Math.round((value / total) * 100)),
      }));
  }, [categories]);

  const animatedMonth = useCountUp(monthSpend);

  if (loading) return <DashboardSkeleton />;

  return (
    <div className="px-4 sm:px-5 lg:px-8 py-3 sm:py-4 max-w-[1400px] mx-auto w-full">
      {/* Command bar */}
      <Reveal delay={0}>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-3 sm:mb-4 pb-2.5 border-b border-rule gap-3 sm:gap-4">
          <p className="text-sm text-ink-muted min-w-0 sm:truncate leading-relaxed">
            <span className="text-ink font-medium">
              {greeting()}
              {user?.first_name ? `, ${user.first_name}` : ""}
            </span>
            <span className="mx-2 text-ink-faint">·</span>
            <span className="num">{currentDateString()}</span>
            <span className="mx-2 text-ink-faint">·</span>
            <span className="text-ink">
              {organization?.name ?? "Workspace"}
            </span>
          </p>
          <div className="flex w-full flex-wrap items-center gap-2 shrink-0 sm:w-auto sm:justify-end">
            <Button as={Link} to="/expenses" variant="ghost" size="sm">
              All expenses
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="sm:w-auto"
              iconLeft={<Plus size={14} strokeWidth={2} />}
              onClick={() => navigate("/expenses?new=1")}
            >
              Add expense
            </Button>
          </div>
        </div>
      </Reveal>

      {/* HERO — Month-to-date spend */}
      <Reveal delay={80}>
        <Panel variant="default" className="mb-2 border-t-2 border-t-rule-strong p-4 lg:p-5">
          <div className="mb-3 flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-baseline">
            <div>
              <p className="text-micro uppercase tracking-eyebrow text-ink-muted">
                Month-to-date spend
              </p>
              <p className="mt-0.5 text-xs text-ink-muted">
                Approved expenses this month.
              </p>
            </div>
            {showBudgets && (
              <Link
                to="/budgets"
                className="text-xs text-ink-muted hover:text-ink hover:underline"
              >
                Manage budgets
              </Link>
            )}
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(15rem,0.38fr)] lg:gap-5">
            <div className="min-w-0">
              <div className="max-w-full break-words text-[2.1rem] font-semibold leading-none tracking-tight text-ink tabular-nums min-[380px]:text-[2.4rem] sm:text-[2.75rem]">
                {formatCurrency(animatedMonth, currency)}
              </div>
              <p className="mt-1.5 text-xs font-medium text-ink-muted">
                {comparisonLabel ??
                  (monthSpend > 0
                    ? "No approved spend last month for comparison"
                    : "Current month")}
              </p>

              {spendingDays.length >= 2 ? (
                <div className="mt-3 border-t border-rule pt-3">
                  <AreaChart data={monthSeries} height={76} currency={currency} />
                </div>
              ) : spendingDays.length === 1 ? (
                <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-rule pt-3 text-xs text-ink-muted">
                  <span>One approved spending day recorded this month.</span>
                  <span className="rounded-pill bg-paper-deep px-2 py-1 font-medium text-ink">
                    {spendingDays[0].label} · {formatCurrency(spendingDays[0].value, currency)}
                  </span>
                </div>
              ) : (
                <p className="mt-3 border-t border-rule pt-3 text-xs text-ink-muted">
                  No approved expenses recorded this month yet.
                </p>
              )}
            </div>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-t border-rule pt-3 lg:grid-cols-1 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0">
              <div>
                <dt className="text-[11px] text-ink-muted">Previous month</dt>
                <dd className="mt-0.5 text-sm font-medium text-ink tabular-nums">
                  {formatCurrency(previousMonthSpend, currency)}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-ink-muted">Spending days this month</dt>
                <dd className="mt-0.5 text-sm font-medium text-ink tabular-nums">
                  {spendingDays.length}
                </dd>
              </div>
              <div className="col-span-2 lg:col-span-1">
                <dt className="text-[11px] text-ink-muted">Highest spending day</dt>
                <dd className="mt-0.5 text-sm font-medium text-ink">
                  {highestSpendingDay
                    ? `${highestSpendingDay.label} · ${formatCurrency(highestSpendingDay.value, currency)}`
                    : "—"}
                </dd>
              </div>
            </dl>
          </div>
        </Panel>
      </Reveal>

      {/* STAT ROW */}
      <Reveal delay={160}>
        <Panel className="mb-3">
          <div className="flex flex-wrap divide-y sm:divide-y-0 sm:divide-x divide-rule">
            <Stat
              label="Approved spend this week"
              value={<Money value={weekSpend} currency={currency} size="xl" />}
              hint={
                todaySpend > 0 ? (
                  <>
                    incl.{" "}
                    <Money
                      value={todaySpend}
                      currency={currency}
                      size="xs"
                      muted
                    />{" "}
                    today
                  </>
                ) : (
                  "no spend yet"
                )
              }
            />
            {showAwaitingReview && (
              <Stat
                label="Expenses awaiting approval"
                value={
                  <span className="text-2xl font-semibold num text-ink leading-none tabular-nums">
                    {pending.length}
                  </span>
                }
                hint={
                  pendingAmount > 0 ? (
                    <Money
                      value={pendingAmount}
                      currency={currency}
                      size="sm"
                      muted
                    />
                  ) : (
                    "all clear"
                  )
                }
              />
            )}
            <Stat
              label={
                <span className="inline-flex items-center gap-1.5">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-moss-500 opacity-60" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-moss-500" />
                  </span>
                  <span>Approved spend today</span>
                </span>
              }
              value={<Money value={todaySpend} currency={currency} size="xl" />}
              hint={todaySpend > 0 ? "logged today" : "no spend yet"}
            />
          </div>
        </Panel>
      </Reveal>

      {/* DAY BOOK + SIDE RAIL */}
      <div className="grid grid-cols-12 gap-3 mb-3">
        <Reveal delay={240} className="col-span-12 lg:col-span-8">
          <Panel className="overflow-hidden h-full">
            <div className="px-4 sm:px-5 py-3.5 border-b border-rule flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-sm font-medium text-ink">
                  {isStaff ? "My recent expenses" : "Recent expenses"}
                </h3>
                <p className="mt-0.5 text-xs text-ink-muted">
                  {isStaff
                    ? "Latest submissions and status."
                    : "Latest expense records across all statuses."}
                </p>
              </div>
              <Link
                to="/expenses"
                className="text-xs text-ink-muted hover:text-ink inline-flex items-center gap-0.5 transition-colors shrink-0 pt-0.5"
              >
                View all expenses <ChevronRight size={12} />
              </Link>
            </div>
            {recent.length === 0 ? (
              <EmptyState
                title={
                  isStaff
                    ? "No submitted expenses yet"
                    : "No ledger entries yet"
                }
                description={
                  isStaff
                    ? "Submit an expense to start tracking its status."
                    : "Add the first workspace expense to start the ledger."
                }
                action={
                  <Button
                    variant="primary"
                    size="sm"
                    iconLeft={<Plus size={14} strokeWidth={2} />}
                    onClick={() => navigate("/expenses?new=1")}
                  >
                    Add expense
                  </Button>
                }
              />
            ) : (
              <table className="w-full text-sm block sm:table">
                <thead className="hidden sm:table-header-group">
                  <tr className="text-left text-[10px] uppercase tracking-eyebrow text-ink-faint">
                    <th className="px-5 py-2 font-medium w-16">Date</th>
                    <th className="py-2 font-medium">Expense</th>
                    <th className="py-2 font-medium hidden md:table-cell">
                      Category
                    </th>
                    <th className="py-2 font-medium w-4"></th>
                    <th className="py-2 font-medium text-right pr-5">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule block sm:table-row-group">
                  {recent.slice(0, 7).map((e, i) => (
                    <tr
                      key={e.id}
                      onClick={() => navigate("/expenses")}
                      className="group block sm:table-row cursor-pointer hover:bg-paper-deep/60 transition-colors animate-fade-in px-4 py-3 sm:p-0"
                      style={{ animationDelay: `${300 + i * 40}ms` }}
                    >
                      <td className="flex items-center justify-between gap-4 sm:table-cell sm:px-5 sm:py-2.5 text-[11px] text-ink-faint num tabular-nums">
                        <span className="sm:hidden uppercase tracking-eyebrow text-ink-faint">
                          Date
                        </span>
                        <span>
                          {formatDate(e.date ?? e.created_at, "short")}
                        </span>
                      </td>
                      <td className="block sm:table-cell py-2 sm:py-2.5 min-w-0">
                        <span className="text-ink truncate block">
                          {e.title ?? e.description ?? categoryName(e.category)}
                        </span>
                        <span className="text-[11px] text-ink-muted truncate block">
                          {personName(e)}
                        </span>
                      </td>
                      <td className="flex items-center justify-between gap-4 sm:table-cell sm:py-2.5 text-ink-muted">
                        <span className="sm:hidden text-[11px] uppercase tracking-eyebrow text-ink-faint">
                          Category
                        </span>
                        <span>{categoryName(e.category)}</span>
                      </td>
                      <td className="flex items-center justify-between gap-4 sm:table-cell sm:py-2.5">
                        <span className="sm:hidden text-[11px] uppercase tracking-eyebrow text-ink-faint">
                          Status
                        </span>
                        <span className="inline-flex items-center gap-2 text-xs text-ink-muted">
                          <StatusDot status={e.status} />
                          <span className="sm:hidden">
                            {statusName(e.status)}
                          </span>
                        </span>
                      </td>
                      <td className="flex items-center justify-between gap-4 sm:table-cell sm:py-2.5 num sm:text-right sm:pr-5 text-ink">
                        <span className="sm:hidden text-[11px] uppercase tracking-eyebrow text-ink-faint">
                          Amount
                        </span>
                        <Money
                          value={e.amount}
                          currency={e.currency ?? currency}
                          size="sm"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </Reveal>

        <div className="col-span-12 lg:col-span-4 space-y-3">
          <Reveal delay={300}>
            <Panel>
              <div className="px-4 sm:px-5 py-3.5 border-b border-rule flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-medium text-ink">
                    Top expense categories
                  </h3>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    Share of all approved spending.
                  </p>
                </div>
                <Link
                  to="/reports"
                  className="shrink-0 pt-0.5 text-xs text-ink-muted transition-colors hover:text-ink"
                >
                  View reports
                </Link>
              </div>
              {topCategories.length === 0 ? (
                <EmptyState
                  compact
                  title="No category data yet"
                  description="Categorized expenses will appear here once spending is recorded."
                />
              ) : (
                <ul className="px-4 sm:px-5 py-4 space-y-3.5">
                  {topCategories.map((c, i) => (
                    <li key={c.name} className="space-y-1.5">
                      <div className="flex items-baseline justify-between text-xs">
                        <span className="min-w-0 break-words text-ink">
                          {c.name}
                        </span>
                        <span className="num text-ink-muted flex items-baseline gap-2">
                          <Money
                            value={c.value}
                            currency={currency}
                            size="xs"
                            muted
                          />
                          <span className="text-ink-faint num tabular-nums w-7 text-right">
                            {c.pct}%
                          </span>
                        </span>
                      </div>
                      <div className="h-1 bg-rule rounded-full overflow-hidden">
                        <div
                          className="h-full bg-ink rounded-full transition-[width] duration-700 ease-out"
                          style={{
                            width: `${c.pct}%`,
                            transitionDelay: `${400 + i * 60}ms`,
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </Reveal>

          <Reveal delay={360}>
            {showAwaitingReview ? (
              <Panel>
                <div className="px-4 sm:px-5 py-3.5 border-b border-rule flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-medium text-ink">
                      Expenses awaiting approval
                    </h3>
                    <p className="mt-0.5 text-xs text-ink-muted">
                      Expenses waiting for a decision.
                    </p>
                  </div>
                  {pending.length > 0 && (
                    <Link
                      to="/approvals"
                      className="text-xs text-ink-muted hover:text-ink transition-colors shrink-0 pt-0.5"
                    >
                      View all
                    </Link>
                  )}
                </div>
                {pending.length === 0 ? (
                  <EmptyState
                    compact
                    title="No approval work"
                    description="Pending expenses appear here when they need a decision."
                  />
                ) : (
                  <ul className="divide-y divide-rule">
                    {pending.slice(0, 5).map((e, i) => (
                      <li
                        key={e.id}
                        className="px-4 py-2.5 flex items-center gap-3 hover:bg-paper-deep/40 transition-colors cursor-pointer animate-fade-in sm:px-5"
                        style={{ animationDelay: `${400 + i * 40}ms` }}
                        onClick={() => navigate("/approvals")}
                      >
                        <Avatar name={personName(e)} size={28} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-ink truncate">
                            {e.title ?? e.description}
                          </p>
                          <p className="text-[11px] text-ink-muted truncate">
                            {personName(e)}
                          </p>
                        </div>
                        <span className="num shrink-0 text-right text-sm text-ink">
                          <Money
                            value={e.amount}
                            currency={e.currency ?? currency}
                            size="sm"
                          />
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            ) : (
              <Panel>
                <div className="px-4 sm:px-5 py-3.5 border-b border-rule">
                  <h3 className="text-sm font-medium text-ink">
                    Staff actions
                  </h3>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    Submit a new expense and track it from the ledger.
                  </p>
                </div>
                <div className="px-4 sm:px-5 py-5">
                  <p className="text-sm text-ink-muted">
                    Use the expense form for receipts, purchases, travel, and
                    business costs.
                  </p>
                  <Button
                    variant="primary"
                    size="sm"
                    className="mt-4"
                    iconLeft={<Plus size={14} strokeWidth={2} />}
                    onClick={() => navigate("/expenses?new=1")}
                  >
                    New expense
                  </Button>
                </div>
              </Panel>
            )}
          </Reveal>
        </div>
      </div>

      {/* BUDGETS */}
      <Reveal delay={420}>
        {showBudgets && (
          <Panel>
            <div className="px-4 sm:px-5 py-3.5 border-b border-rule flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-medium text-ink">
                  Budget usage
                </h3>
                <p className="mt-0.5 text-xs text-ink-muted">
                  Approved spend against each budget period.
                </p>
              </div>
              <Link
                to="/budgets"
                className="text-xs text-ink-muted hover:text-ink transition-colors inline-flex items-center gap-0.5 shrink-0 pt-0.5"
              >
                Manage budgets <ChevronRight size={12} />
              </Link>
            </div>
            {budgets.length === 0 ? (
              <EmptyState
                title="No active budgets"
                description="Set a limit to compare approved spend."
                action={
                  <Button as={Link} to="/budgets" variant="primary" size="sm">
                    Set up budget
                  </Button>
                }
              />
            ) : (
              <table className="w-full text-sm block sm:table">
                <thead className="hidden sm:table-header-group">
                  <tr className="text-left text-[10px] uppercase tracking-eyebrow text-ink-faint">
                    <th className="px-5 py-2 font-medium">Category</th>
                    <th className="py-2 font-medium hidden sm:table-cell">
                      Period
                    </th>
                    <th className="py-2 font-medium">Usage</th>
                    <th className="py-2 font-medium text-right">Spent</th>
                    <th className="px-5 py-2 font-medium text-right">Budget</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule block sm:table-row-group">
                  {budgets.map((b, i) => {
                    const spent = Number(b.spent_amount ?? b.spent) || 0;
                    const total = Number(b.amount) || 0;
                    const pct = Number(
                      b.percentage_used ??
                        (total > 0
                          ? Math.min(100, Math.round((spent / total) * 100))
                          : 0),
                    );
                    const overPct = pct >= 85;
                    return (
                      <tr
                        key={b.id}
                        className="block sm:table-row hover:bg-paper-deep/40 transition-colors animate-fade-in px-4 py-3 sm:p-0"
                        style={{ animationDelay: `${460 + i * 40}ms` }}
                      >
                        <td className="block sm:table-cell sm:px-5 sm:py-2.5 text-ink font-medium sm:font-normal">
                          {b.name || categoryName(b.category)}
                        </td>
                        <td className="flex items-center justify-between gap-4 sm:table-cell sm:py-2.5 text-ink-muted">
                          <span className="sm:hidden text-[11px] uppercase tracking-eyebrow text-ink-faint">
                            Period
                          </span>
                          <span>{b.period ?? "Monthly"}</span>
                        </td>
                        <td className="block sm:table-cell py-2 sm:py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 sm:h-1 flex-1 sm:max-w-[120px] bg-rule rounded-full overflow-hidden">
                              <div
                                className={cn(
                                  "h-full rounded-full transition-[width] duration-700 ease-out",
                                  overPct ? "bg-cinnabar-500" : "bg-ink",
                                )}
                                style={{ width: `${Math.min(100, pct)}%` }}
                              />
                            </div>
                            <span
                              className={cn(
                                "num text-[11px] tabular-nums w-8 text-right",
                                overPct
                                  ? "text-cinnabar-700"
                                  : "text-ink-muted",
                              )}
                            >
                              {pct}%
                            </span>
                          </div>
                        </td>
                        <td className="flex items-center justify-between gap-4 sm:table-cell sm:py-2.5 num sm:text-right text-ink">
                          <span className="sm:hidden text-[11px] uppercase tracking-eyebrow text-ink-faint">
                            Spent
                          </span>
                          <Money value={spent} currency={currency} size="sm" />
                        </td>
                        <td className="flex items-center justify-between gap-4 sm:table-cell sm:px-5 sm:py-2.5 num sm:text-right text-ink-muted">
                          <span className="sm:hidden text-[11px] uppercase tracking-eyebrow text-ink-faint">
                            Budget
                          </span>
                          <Money value={total} currency={currency} size="sm" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </Panel>
        )}
      </Reveal>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Stat — one cell of the tight stat row.
 * ------------------------------------------------------------------ */
function Stat({ label, value, hint }) {
  return (
    <div className="p-4 lg:p-5 flex flex-col gap-1.5 min-w-0 basis-full min-[420px]:basis-1/2 lg:basis-1/4 flex-1">
      <div className="text-micro uppercase tracking-eyebrow text-ink-muted">
        {label}
      </div>
      <div className="min-w-0">{value}</div>
      {hint != null && (
        <div className="text-xs text-ink-muted truncate">{hint}</div>
      )}
    </div>
  );
}

function EmptyState({ title, description, action, compact = false }) {
  return (
    <div
      className={cn("px-5 text-center", compact ? "py-8" : "py-12 sm:py-14")}
    >
      <p className="text-sm font-medium text-ink">{title}</p>
      {description && (
        <p className="mt-1.5 mx-auto max-w-sm text-sm text-ink-muted leading-relaxed">
          {description}
        </p>
      )}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div
      className="px-4 sm:px-5 lg:px-8 py-4 sm:py-5 max-w-[1400px] mx-auto w-full"
      aria-busy="true"
      aria-label="Loading dashboard"
    >
      <Skeleton className="h-10 w-full mb-4" />
      <Skeleton className="h-60 w-full mb-3" />
      <Skeleton className="h-24 w-full mb-3" />
      <div className="grid grid-cols-12 gap-3 mb-3">
        <Skeleton className="col-span-12 lg:col-span-8 h-80" />
        <div className="col-span-12 lg:col-span-4 space-y-3">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
      <Skeleton className="h-40" />
    </div>
  );
}
