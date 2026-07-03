import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Calendar,
  ChevronDown,
  ChevronUp,
  Download,
  Filter,
  Lightbulb,
  RefreshCw,
  ScanSearch,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import api from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { Panel, PanelHeader, PanelTitle } from "../components/Panel.jsx";
import { Modal } from "../components/Modal.jsx";
import { Select, Input } from "../components/Field.jsx";
import { BarChart, DonutChart } from "../components/Charts.jsx";
import { Money } from "../components/Money.jsx";
import { formatCompact } from "../lib/currency.js";
import { formatDate } from "../lib/date.js";
import { EmptyState, ErrorState, Spinner } from "../components/Feedback.jsx";
import Button from "../components/Button.jsx";
import PaginationControls from "../components/PaginationControls.jsx";
import { useToast } from "../components/Toast.jsx";
import {
  EXPENSE_CATEGORIES,
  formatCategoryLabel,
} from "../lib/categories.js";

const PRESETS = [
  { value: "this_month", label: "This month" },
  { value: "last_month", label: "Last month" },
  { value: "last_30_days", label: "Last 30 days" },
  { value: "this_year", label: "This year" },
  { value: "custom", label: "Custom" },
];

const AI_PERIODS = [
  { value: "this_month", label: "This month" },
  { value: "last_month", label: "Last month" },
  { value: "last_3_months", label: "Last 3 months" },
];

const CHART_COLORS = [
  "oklch(0.56 0.17 25)",
  "oklch(0.50 0.08 150)",
  "oklch(0.60 0.12 65)",
  "oklch(0.40 0.05 230)",
  "oklch(0.55 0.10 320)",
  "oklch(0.45 0.05 90)",
];

const DASH = "\u2014";

const padDate = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const monthBounds = (offset = 0) => {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const end =
    offset === 0
      ? now
      : new Date(now.getFullYear(), now.getMonth() + offset + 1, 0);
  return { from: padDate(start), to: padDate(end) };
};

const presetBounds = (preset) => {
  const now = new Date();
  if (preset === "last_month") return monthBounds(-1);
  if (preset === "last_30_days") {
    const start = new Date(now);
    start.setDate(now.getDate() - 29);
    return { from: padDate(start), to: padDate(now) };
  }
  if (preset === "this_year") {
    return {
      from: padDate(new Date(now.getFullYear(), 0, 1)),
      to: padDate(now),
    };
  }
  return monthBounds(0);
};

const personName = (expense) =>
  expense?.user_name ??
  expense?.submitted_by_name ??
  expense?.user_details?.full_name ??
  expense?.user_details?.username ??
  expense?.user_details?.email ??
  "Team member";

const errorMessage = (error) => {
  const data = error?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (typeof data?.error === "string") return data.error;
  if (data && typeof data === "object") {
    const first = Object.values(data)[0];
    if (Array.isArray(first)) return first[0];
    if (typeof first === "string") return first;
  }
  return "Report data could not be loaded. Expense records were not changed.";
};

const trendPeriodForRange = (preset, from, to) => {
  if (preset === "this_year") return "monthly";
  if (preset === "last_30_days") return "daily";
  if (preset !== "custom") return "daily";

  const start = new Date(from);
  const end = new Date(to);
  const days =
    Number.isFinite(start.getTime()) && Number.isFinite(end.getTime())
      ? Math.max(0, Math.ceil((end.getTime() - start.getTime()) / 86400000))
      : 0;
  if (days <= 45) return "daily";
  if (days <= 150) return "weekly";
  return "monthly";
};

const rangeLabel = (from, to) =>
  `${from ? formatDate(from, "short") : DASH} - ${to ? formatDate(to, "short") : DASH}`;

export default function Reports() {
  const { currency, organization } = useAuth();
  const toast = useToast();
  const requestRef = useRef(0);
  const exportMenuRef = useRef(null);

  const initialRange = useMemo(() => presetBounds("this_month"), []);
  const [preset, setPreset] = useState("this_month");
  const [from, setFrom] = useState(initialRange.from);
  const [to, setTo] = useState(initialRange.to);
  const [category, setCategory] = useState("");
  const [vendor, setVendor] = useState("");
  const [vendorInput, setVendorInput] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [expensePage, setExpensePage] = useState(1);

  const organizationId = organization?.id ?? "";
  const pageSize = 10;

  useEffect(() => {
    if (preset === "custom") return;
    const range = presetBounds(preset);
    setFrom(range.from);
    setTo(range.to);
  }, [preset]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setVendor(vendorInput.trim());
    }, 350);
    return () => window.clearTimeout(timeout);
  }, [vendorInput]);

  useEffect(() => {
    setExpensePage(1);
  }, [preset, from, to, category, vendor, organizationId]);

  useEffect(() => {
    if (!exportMenuOpen) return undefined;

    const closeMenu = (event) => {
      if (!exportMenuRef.current?.contains(event.target)) {
        setExportMenuOpen(false);
      }
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setExportMenuOpen(false);
    };

    document.addEventListener("mousedown", closeMenu);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeMenu);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [exportMenuOpen]);

  const trendPeriod = useMemo(
    () => trendPeriodForRange(preset, from, to),
    [preset, from, to],
  );

  const params = useMemo(
    () => ({
      start_date: from,
      end_date: to,
      period: trendPeriod,
      ...(category ? { category } : {}),
      ...(vendor ? { vendor } : {}),
    }),
    [from, to, trendPeriod, category, vendor],
  );

  const loadReports = useCallback(() => {
    if (!organizationId || !from || !to) {
      setData(null);
      setLoading(false);
      setLoadError("");
      return;
    }

    const requestId = requestRef.current + 1;
    requestRef.current = requestId;
    setLoading(true);
    setLoadError("");
    setData(null);

    api
      .get("/analytics/report-detail/", { params })
      .then((response) => {
        if (requestRef.current !== requestId) return;
        setData(response.data ?? null);
      })
      .catch((error) => {
        if (requestRef.current !== requestId) return;
        setData(null);
        setLoadError(errorMessage(error));
      })
      .finally(() => {
        if (requestRef.current === requestId) setLoading(false);
      });
  }, [organizationId, from, to, params]);

  useEffect(() => {
    loadReports();
  }, [loadReports, refreshKey]);

  const summary = data?.summary ?? {};
  const expenses = data?.expenses ?? [];
  const categories = data?.categories ?? [];
  const vendors = data?.vendors ?? [];
  const trends = data?.trends ?? [];
  const comparison = data?.comparison ?? null;
  const total = Number(summary.total) || 0;
  const count = Number(summary.count) || 0;
  const average = Number(summary.average) || 0;
  const topCategory = data?.top_category ?? null;
  const topVendor = data?.top_vendor ?? null;
  const hasFilters = Boolean(category || vendor || preset !== "this_month");
  const hasReportData = count > 0;
  const selectedPresetLabel =
    PRESETS.find((item) => item.value === preset)?.label ?? "Selected range";

  const expensePageRows = useMemo(() => {
    const start = (expensePage - 1) * pageSize;
    return expenses.slice(start, start + pageSize);
  }, [expenses, expensePage]);

  const trendData = useMemo(
    () =>
      trends.map((item) => {
        const raw = item.period_start ?? item.period ?? item.date;
        const date = raw ? new Date(raw) : null;
        const valid = date && !Number.isNaN(date.getTime());
        const label = valid
          ? trendPeriod === "monthly"
            ? date.toLocaleDateString(undefined, { month: "short", year: "numeric" })
            : date.toLocaleDateString(undefined, { month: "short", day: "2-digit" })
          : item.label ?? raw ?? DASH;
        return { label, value: Number(item.total) || 0 };
      }),
    [trends, trendPeriod],
  );

  const categorySegments = useMemo(
    () =>
      categories.slice(0, 6).map((item, index) => ({
        label: formatCategoryLabel(item.category),
        value: Number(item.total) || 0,
        color: CHART_COLORS[index % CHART_COLORS.length],
      })),
    [categories],
  );

  const clearFilters = () => {
    setPreset("this_month");
    const range = presetBounds("this_month");
    setFrom(range.from);
    setTo(range.to);
    setCategory("");
    setVendor("");
    setVendorInput("");
  };

  const exportReport = useCallback(async (format) => {
    if (exporting || loading || !hasReportData || !organizationId || !from || !to) {
      return;
    }

    setExportMenuOpen(false);
    setExporting(format);
    try {
      const response = await api.get(`/analytics/export-${format}/`, {
        params,
        responseType: "blob",
      });
      const contentType =
        format === "pdf" ? "application/pdf" : "text/csv;charset=utf-8";
      const blob =
        response.data instanceof Blob
          ? response.data
          : new Blob([response.data], { type: contentType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download =
        format === "csv"
          ? `approved-expense-report_${from}_${to}.csv`
          : `Vyapar_Margadarshan_Report_${from}_to_${to}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success(
        format === "csv"
          ? "Approved expense report exported."
          : "PDF expense report exported.",
      );
    } catch {
      toast.error(`Could not export the ${format.toUpperCase()} expense report.`);
    } finally {
      setExporting(false);
    }
  }, [exporting, loading, hasReportData, organizationId, from, to, params, toast]);

  const pageActions = useMemo(
    () => (
      <>
        <div ref={exportMenuRef} className="relative">
          <Button
            variant="secondary"
            size="sm"
            iconLeft={<Download size={14} />}
            onClick={() => setExportMenuOpen((open) => !open)}
            disabled={exporting || loading || !hasReportData || !organizationId}
            aria-haspopup="menu"
            aria-expanded={exportMenuOpen}
          >
            <span className="inline-flex items-center gap-1.5">
              {exporting ? "Exporting..." : "Export"}
              <ChevronDown size={13} aria-hidden="true" />
            </span>
          </Button>
          {exportMenuOpen ? (
            <div
              role="menu"
              className="absolute right-0 z-30 mt-1.5 w-44 overflow-hidden rounded-md border border-rule bg-paper py-1 shadow-lg"
            >
              <button
                type="button"
                role="menuitem"
                className="block w-full px-3 py-2 text-left text-sm text-ink transition-colors hover:bg-paper-deep focus:bg-paper-deep focus:outline-none"
                onClick={() => exportReport("csv")}
              >
                Export as CSV
              </button>
              <button
                type="button"
                role="menuitem"
                className="block w-full px-3 py-2 text-left text-sm text-ink transition-colors hover:bg-paper-deep focus:bg-paper-deep focus:outline-none"
                onClick={() => exportReport("pdf")}
              >
                Export as PDF
              </button>
            </div>
          ) : null}
        </div>
        <Button
          variant="secondary"
          size="sm"
          iconLeft={<RefreshCw size={14} />}
          onClick={() => setRefreshKey((key) => key + 1)}
          disabled={loading || !organizationId}
        >
          Refresh
        </Button>
      </>
    ),
    [
      exportMenuOpen,
      exportReport,
      exporting,
      loading,
      hasReportData,
      organizationId,
    ],
  );

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-5 pt-2 sm:px-6 lg:px-8">
      <div className="mb-2 flex flex-wrap items-center justify-end gap-1.5 border-b border-rule pb-2" aria-label="Report actions">
        {pageActions}
      </div>

      <section
        className="rounded-md border border-rule bg-paper-deep/60 px-3 py-2"
        aria-label="Report filters"
      >
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-[minmax(8rem,12rem)_minmax(0,1fr)_auto] lg:items-end">
          <div className="flex min-w-0 items-center gap-2 lg:self-center">
              <Filter size={14} strokeWidth={1.5} className="text-ink-muted" aria-hidden="true" />
            <div className="min-w-0">
              <p className="text-xs font-medium text-ink">Filters</p>
              <p className="truncate text-xs text-ink-muted">
                {rangeLabel(from, to)} - {data?.scope === "personal" ? "own data" : "workspace data"}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-12 lg:items-end">
            <div className="lg:col-span-3">
              <Select
                label="Date range"
                className="md:h-9"
                value={preset}
                onChange={(event) => setPreset(event.target.value)}
                disabled={loading}
              >
                {PRESETS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </div>

            {preset === "custom" && (
              <>
                <div className="lg:col-span-2">
                  <Input
                    label="Start"
                    type="date"
                    className="md:h-9"
                    value={from}
                    onChange={(event) => setFrom(event.target.value)}
                    disabled={loading}
                  />
                </div>
                <div className="lg:col-span-2">
                  <Input
                    label="End"
                    type="date"
                    className="md:h-9"
                    value={to}
                    onChange={(event) => setTo(event.target.value)}
                    disabled={loading}
                  />
                </div>
              </>
            )}

            <div className={preset === "custom" ? "lg:col-span-2" : "lg:col-span-3"}>
              <Select
                label="Category"
                className="md:h-9"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                disabled={loading}
              >
                <option value="">All categories</option>
                {EXPENSE_CATEGORIES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </div>

            <div className={preset === "custom" ? "lg:col-span-3" : "lg:col-span-4"}>
              <label className="field-label" htmlFor="report-vendor-search">
                Vendor
              </label>
              <div className="relative">
                <Search
                  size={14}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
                  strokeWidth={1.5}
                  aria-hidden="true"
                />
                <input
                  id="report-vendor-search"
                  type="search"
                  value={vendorInput}
                  onChange={(event) => setVendorInput(event.target.value)}
                  placeholder="Search vendor"
                  disabled={loading}
                  className="h-10 w-full rounded-md border border-rule bg-paper pl-9 pr-3 text-sm text-ink placeholder:text-ink-muted transition-colors focus:border-moss-500 focus:outline-none focus:ring-2 focus:ring-moss-500/15 disabled:cursor-not-allowed disabled:opacity-60 md:h-9"
                />
              </div>
            </div>

            <div className={preset === "custom" ? "lg:col-span-1" : "lg:col-span-2"}>
              <div className="hidden h-9 min-w-0 items-center gap-2 rounded-md bg-paper px-3 text-xs text-ink-muted ring-1 ring-rule lg:flex">
                <Calendar size={13} strokeWidth={1.5} aria-hidden="true" />
                <span className="truncate">{selectedPresetLabel}</span>
              </div>
            </div>
          </div>

          {hasFilters && (
            <div className="flex justify-start lg:justify-end">
              <Button variant="ghost" size="xs" onClick={clearFilters}>
                Clear filters
              </Button>
            </div>
          )}
        </div>
      </section>

      <div className="mt-3 min-w-0">
      {!organizationId ? (
        <EmptyState
          title="Select a workspace"
          description="Reports load after an active organization is selected."
          className="py-12"
        />
      ) : loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-12 text-sm text-ink-muted">
          <Spinner className="text-ink-muted" />
          <span>Loading approved expense report...</span>
        </div>
      ) : loadError ? (
        <ErrorState
          title="Reports are unavailable"
          description={loadError}
          action={
            <Button variant="secondary" onClick={() => setRefreshKey((key) => key + 1)}>
              Try again
            </Button>
          }
        />
      ) : !hasReportData ? (
        <EmptyState
          title="No approved expenses found for this period."
          description={
            hasFilters
              ? "Change the date, category, or vendor filters to widen the report."
              : "Approve expenses in this workspace to start building report insights."
          }
          action={
            hasFilters ? (
              <Button variant="secondary" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : null
          }
          className="py-12"
        />
      ) : (
        <>
          <section className="mt-2 grid grid-cols-12 gap-2 lg:gap-3" aria-label="Analytics dashboard">
            <Panel className="col-span-12 overflow-hidden lg:col-span-8">
              <div className="flex flex-col gap-2 border-b border-rule px-4 py-2.5 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-forest-50 text-forest-700 ring-1 ring-forest-100">
                      <BarChart3 size={16} aria-hidden="true" />
                    </span>
                    <div>
                      <PanelTitle className="!text-base">Spend over time</PanelTitle>
                      <p className="mt-0.5 text-xs text-ink-muted">
                        Approved spend grouped by {trendPeriod}.
                      </p>
                    </div>
                  </div>
                </div>
                <div className="text-left sm:text-right">
                  <p className="text-xs text-ink-muted">Report total</p>
                  <p className="num text-base font-semibold text-ink">
                    <Money value={total} currency={currency} />
                  </p>
                </div>
              </div>
              {trendData.length > 0 ? (
                <div className="px-3 pb-3 pt-3 sm:px-4">
                  <BarChart
                    data={trendData}
                    height={230}
                    currency={currency}
                    highlightIndex={trendData.length - 1}
                    className="rounded-md bg-paper-deep/40 p-2.5 ring-1 ring-rule"
                  />
                </div>
              ) : (
                <EmptyState
                  title="No trend data"
                  description="No grouped spending exists for this range."
                  className="py-10"
                />
              )}
            </Panel>

            <div className="col-span-12 grid grid-cols-1 gap-3 lg:col-span-4">
              <Panel className="overflow-hidden">
                <PanelHeader className="!px-4 !py-2.5">
                  <PanelTitle className="!text-base">Period summary</PanelTitle>
                </PanelHeader>
                <div className="space-y-2 px-4 py-2.5">
                  <div className="grid grid-cols-2 gap-2">
                    <CompactFact
                      label="Approved"
                      value={count || DASH}
                    />
                    <CompactFact
                      label="Average"
                      value={count > 0 ? <Money value={average} currency={currency} /> : DASH}
                    />
                  </div>
                  <ComparisonRow
                    label="Current"
                    start={comparison?.current_period?.start}
                    end={comparison?.current_period?.end}
                    total={comparison?.current_period?.total}
                    count={comparison?.current_period?.count}
                    currency={currency}
                  />
                  <ComparisonRow
                    label="Previous"
                    start={comparison?.previous_period?.start}
                    end={comparison?.previous_period?.end}
                    total={comparison?.previous_period?.total}
                    count={comparison?.previous_period?.count}
                    currency={currency}
                  />
                  <ChangeLine value={comparison?.change_percentage} />
                </div>
              </Panel>

              <Panel className="overflow-hidden">
                <PanelHeader className="!px-4 !py-2.5">
                  <PanelTitle className="!text-base">Spend leaders</PanelTitle>
                </PanelHeader>
                <div className="space-y-1 px-4 py-2.5">
                  <InsightLine
                    label="Category"
                    name={topCategory ? formatCategoryLabel(topCategory.category) : DASH}
                    value={topCategory?.total}
                    currency={currency}
                  />
                  <InsightLine
                    label="Vendor"
                    name={topVendor?.vendor || DASH}
                    value={topVendor?.total}
                    currency={currency}
                  />
                </div>
              </Panel>
            </div>
          </section>

          <section className="mt-3 grid grid-cols-12 gap-3 lg:gap-4" aria-label="Supporting analytics">
            <Panel className="col-span-12 lg:col-span-5">
              <PanelHeader className="!px-4 !py-3">
                <PanelTitle className="!text-base">Category mix</PanelTitle>
              </PanelHeader>
              {categorySegments.length > 0 ? (
                <div className="px-4 py-4">
                  <DonutChart
                    segments={categorySegments}
                    size={160}
                    thickness={18}
                    centerLabel="Total"
                    centerValue={formatCompact(total, currency)}
                    className="items-start"
                  />
                </div>
              ) : (
                <EmptyState
                  title="No category mix"
                  description="No category share was returned."
                  className="py-8"
                />
              )}
            </Panel>

            <Panel className="col-span-12 lg:col-span-7">
              <PanelHeader className="!px-4 !py-3">
                <PanelTitle className="!text-base">Category breakdown</PanelTitle>
              </PanelHeader>
              <BreakdownList
                rows={categories}
                currency={currency}
                labelFor={(row) => formatCategoryLabel(row.category)}
                emptyTitle="No category data"
              />
            </Panel>

            <Panel className="col-span-12">
              <PanelHeader className="!px-4 !py-3">
                <PanelTitle className="!text-base">Vendor breakdown</PanelTitle>
              </PanelHeader>
              <BreakdownList
                rows={vendors}
                currency={currency}
                labelFor={(row) => row.vendor || "Unnamed vendor"}
                emptyTitle="No vendor data"
                columns={2}
              />
            </Panel>
          </section>

          <Panel className="mt-3 overflow-hidden">
            <PanelHeader
              className="!px-4 !py-3 sm:!px-5"
              action={
                <div className="flex items-center gap-2 rounded-sm bg-paper-deep px-2 py-1 text-xs text-ink-muted">
                  <AlertTriangle size={14} strokeWidth={1.5} aria-hidden="true" />
                  <span>Pending and rejected expenses are excluded.</span>
                </div>
              }
            >
              <div>
                <PanelTitle className="!text-base">Approved expenses included</PanelTitle>
                <p className="mt-0.5 text-xs text-ink-muted">
                  {data?.scope === "personal"
                    ? "Only your approved expenses in the active workspace."
                    : "Approved expenses in the active workspace."}
                </p>
              </div>
            </PanelHeader>

            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[54rem] text-sm">
                <thead>
                  <tr className="border-b border-rule bg-paper-deep/45 text-left text-micro uppercase tracking-eyebrow text-ink-muted">
                    <th className="py-2.5 pl-5 font-medium">Date</th>
                    <th className="py-2.5 font-medium">Expense</th>
                    <th className="py-2.5 font-medium">Category</th>
                    <th className="py-2.5 font-medium">Vendor</th>
                    <th className="py-2.5 font-medium">Submitted by</th>
                    <th className="py-2.5 pr-5 text-right font-medium">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule/60">
                  {expensePageRows.map((expense) => (
                    <tr key={expense.id ?? expense.expense_id} className="hover:bg-paper-deep/45">
                      <td className="whitespace-nowrap py-3 pl-5 text-xs text-ink-soft">
                        {formatDate(expense.date, "short")}
                      </td>
                      <td className="max-w-sm py-3">
                        <p className="truncate font-medium text-ink">{expense.title || DASH}</p>
                        {expense.description && (
                          <p className="mt-0.5 truncate text-xs text-ink-muted">
                            {expense.description}
                          </p>
                        )}
                      </td>
                      <td className="py-3 text-ink-soft">
                        {formatCategoryLabel(expense.category)}
                      </td>
                      <td className="max-w-[11rem] py-3 text-ink-soft">
                        <span className="block truncate">{expense.vendor || DASH}</span>
                      </td>
                      <td className="max-w-[11rem] py-3 text-ink-soft">
                        <span className="block truncate">{personName(expense)}</span>
                      </td>
                      <td className="py-3 pr-5 text-right text-ink">
                        <Money value={expense.amount} currency={currency} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="divide-y divide-rule md:hidden">
              {expensePageRows.map((expense) => (
                <div key={expense.id ?? expense.expense_id} className="px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink">
                        {expense.title || DASH}
                      </p>
                      <p className="mt-1 text-xs text-ink-muted">
                        {formatDate(expense.date, "short")} - {formatCategoryLabel(expense.category)}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-ink-muted">
                        {expense.vendor || DASH} - {personName(expense)}
                      </p>
                    </div>
                    <p className="shrink-0 text-sm text-ink">
                      <Money value={expense.amount} currency={currency} />
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <PaginationControls
              page={expensePage}
              setPage={setExpensePage}
              pageSize={pageSize}
              totalItems={expenses.length}
            />
          </Panel>
        </>
      )}
      </div>
    </div>
  );
}

const RULE_TONES = {
  danger: "bg-cinnabar-50 text-cinnabar-700 ring-cinnabar-200",
  warning: "bg-saffron-50 text-saffron-700 ring-saffron-200",
  info: "bg-forest-50 text-forest-700 ring-forest-200",
  success: "bg-moss-50 text-moss-700 ring-moss-200",
};

const advisoryKey = (advisory) =>
  `${advisory.code}-${advisory.evidence?.budget_id ?? advisory.title}`;

function RuleBasedAdviceCard({ advisories, hadAdvisories, loading, error, currency, onClear, onShowAll }) {
  const visibleAdvisories = advisories.slice(0, 3);

  return (
    <Panel className="overflow-hidden" aria-label="Rule-Based Spending Advice">
      <header className="border-b border-rule px-4 py-3">
        <div className="flex items-start gap-2.5">
          <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest-50 text-forest-700 ring-1 ring-forest-200">
            <ShieldCheck size={14} aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-1.5">
              <PanelTitle className="!text-sm">Rule-Based Spending Advice</PanelTitle>
              <span className="inline-flex rounded-sm bg-forest-50 px-1.5 py-0.5 text-[11px] font-medium text-forest-700 ring-1 ring-forest-200">
                Fixed rules
              </span>
            </div>
            <p className="mt-1 text-xs leading-snug text-ink-muted">
              Deterministic checks based on approved expenses and budget usage.
            </p>
          </div>
        </div>
      </header>

      <div className="px-4 py-2.5">
        {loading ? (
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <Spinner className="h-4 w-4" />
            <span>Checking approved spending and budgets...</span>
          </div>
        ) : error ? (
          <p className="text-sm text-cinnabar-700">{error}</p>
        ) : advisories.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-ink-soft">
            <ShieldCheck size={16} className="shrink-0 text-moss-600" aria-hidden="true" />
            <span>{hadAdvisories ? "All advice cleared for this report." : "No rule-based warnings for the selected period."}</span>
          </div>
        ) : (
          <>
            <ul className="divide-y divide-rule">
              {visibleAdvisories.map((advisory) => (
                <li key={advisoryKey(advisory)} className="py-2.5 first:pt-0 last:pb-0">
                  <AdviceItem advisory={advisory} currency={currency} onClear={onClear} compact />
                </li>
              ))}
            </ul>
            {advisories.length > 3 && (
              <button
                type="button"
                onClick={onShowAll}
                className="mt-2 w-full border-t border-rule pt-2 text-left text-xs font-semibold text-forest-700 hover:text-forest-600"
              >
                Show all {advisories.length} advice checks
              </button>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}

function AdviceItem({ advisory, currency, onClear, compact = false }) {
  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-1.5">
        <p className={`${compact ? "text-xs" : "text-sm"} min-w-0 flex-1 font-semibold leading-snug text-ink`}>
          {advisory.title}
        </p>
        <div className="flex shrink-0 items-center gap-1">
          <span className={`inline-flex rounded-sm px-1.5 py-0.5 text-[11px] font-semibold capitalize ring-1 ${RULE_TONES[advisory.severity] ?? RULE_TONES.info}`}>
            {advisory.severity}
          </span>
          <button
            type="button"
            onClick={() => onClear(advisory)}
            className="inline-flex h-6 items-center gap-1 rounded-sm px-1.5 text-[11px] font-medium text-ink-muted transition-colors hover:bg-paper-deep hover:text-ink"
            aria-label={`Clear ${advisory.title}`}
            title="Clear this advice until report filters change"
          >
            <X size={12} aria-hidden="true" />
            Clear
          </button>
        </div>
      </div>
      <p className={`${compact ? "text-xs" : "text-sm"} mt-1 leading-snug text-ink-soft`}>{advisory.message}</p>
      <p className="mt-1.5 flex gap-1.5 text-xs leading-snug text-ink-muted">
        <Lightbulb size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
        <span>{advisory.recommendation}</span>
      </p>
      <RuleEvidence evidence={advisory.evidence} currency={currency} />
    </div>
  );
}

function RuleAdviceModal({ open, onClose, advisories, currency, onClear }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="All Rule-Based Spending Advice"
      description="Review or clear individual checks for the current report period."
      size="xl"
      contentClassName="!py-2"
    >
      {advisories.length === 0 ? (
        <div className="flex items-center gap-2 py-6 text-sm text-ink-soft">
          <ShieldCheck size={17} className="text-moss-600" aria-hidden="true" />
          <span>All advice has been cleared for this report.</span>
        </div>
      ) : (
        <ul className="divide-y divide-rule">
          {advisories.map((advisory) => (
            <li key={advisoryKey(advisory)} className="py-3.5">
              <AdviceItem advisory={advisory} currency={currency} onClear={onClear} />
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}

function RuleEvidence({ evidence, currency }) {
  if (!evidence) return null;
  const percentage = evidence.percentage_used ?? evidence.percentage ?? evidence.increase_percentage;
  const amount = evidence.spent_amount ?? evidence.amount ?? evidence.current_total;
  if (percentage == null && amount == null) return null;

  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-muted">
      {percentage != null && <span className="num rounded-sm bg-paper-deep px-1.5 py-0.5">{Number(percentage).toFixed(1)}%</span>}
      {amount != null && (
        <span className="num rounded-sm bg-paper-deep px-1.5 py-0.5">
          <Money value={Number(amount)} currency={currency} />
        </span>
      )}
    </div>
  );
}

const ANOMALY_TONES = {
  HIGH: "bg-cinnabar-50 text-cinnabar-700 ring-cinnabar-200",
  MEDIUM: "bg-saffron-50 text-saffron-700 ring-saffron-200",
  LOW: "bg-forest-50 text-forest-700 ring-forest-200",
};

const ANOMALY_REASON_LABELS = {
  HIGH_CATEGORY_AMOUNT: "Higher than usual category spending",
  HIGH_VENDOR_AMOUNT: "Higher than usual vendor spending",
  DUPLICATE_CANDIDATE: "Possible duplicate",
  NEW_VENDOR: "New vendor",
  WEEKEND_EXPENSE: "Weekend expense",
};

function UnusualExpenseCard({ data, loading, error, currency }) {
  const anomalies = data?.anomalies ?? [];
  const visible = anomalies.slice(0, 5);
  const hiddenCount = Math.max(0, anomalies.length - visible.length);

  return (
    <Panel className="overflow-hidden" aria-label="Unusual Expense Detection">
      <header className="border-b border-rule px-4 py-3">
        <div className="flex items-start gap-2.5">
          <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-saffron-50 text-saffron-700 ring-1 ring-saffron-200">
            <ScanSearch size={14} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <PanelTitle className="!text-sm">Unusual Expense Detection</PanelTitle>
            <p className="mt-1 text-xs leading-snug text-ink-muted">
              Weighted rule-based checks for unusual approved or pending expenses.
            </p>
          </div>
        </div>
      </header>

      <div className="px-4 py-2.5">
        {loading ? (
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <Spinner className="h-4 w-4" />
            <span>Checking expense patterns...</span>
          </div>
        ) : error ? (
          <p className="text-xs text-cinnabar-700">{error}</p>
        ) : anomalies.length === 0 ? (
          <div className="flex items-center gap-2 text-xs text-ink-soft">
            <ShieldCheck size={15} className="shrink-0 text-moss-600" aria-hidden="true" />
            <span>No unusual expenses detected for this period.</span>
          </div>
        ) : (
          <>
            <ul className="divide-y divide-rule">
              {visible.map((expense) => (
                <li key={expense.expense_id} className="py-2.5 first:pt-0 last:pb-0">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-ink">{expense.title || "Untitled expense"}</p>
                      <p className="mt-0.5 truncate text-[11px] text-ink-muted">{expense.vendor || "No vendor"}</p>
                    </div>
                    <Money value={expense.amount} currency={currency} className="shrink-0 text-xs font-semibold" />
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <span className={`rounded-sm px-1.5 py-0.5 text-[11px] font-semibold ring-1 ${ANOMALY_TONES[expense.severity] ?? ANOMALY_TONES.LOW}`}>
                      {expense.severity}
                    </span>
                    <span className="num rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] font-medium text-ink-soft">
                      Anomaly Score {expense.score}
                    </span>
                    <span className="rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] capitalize text-ink-muted">
                      {String(expense.status || "").toLowerCase()}
                    </span>
                  </div>
                  <ul className="mt-1.5 space-y-0.5 text-[11px] leading-snug text-ink-muted">
                    {(expense.reasons ?? []).slice(0, 3).map((reason) => (
                      <li key={reason.code}>• {ANOMALY_REASON_LABELS[reason.code] ?? reason.message}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
            {hiddenCount > 0 && (
              <p className="mt-2 border-t border-rule pt-2 text-xs font-medium text-ink-muted">
                +{hiddenCount} more unusual {hiddenCount === 1 ? "expense" : "expenses"}
              </p>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}

function AIInsightsCard({
  period,
  onPeriodChange,
  data,
  loading,
  error,
  expanded,
  onToggle,
  onGenerate,
}) {
  const hasResult = Boolean(data || error);
  const insights = data?.insights ?? [];
  const warnings = data?.warnings ?? [];
  const recommendations = data?.recommendations ?? [];

  return (
    <Panel className="overflow-hidden">
      <div className="flex flex-col gap-3 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-saffron-50 text-saffron-700 ring-1 ring-saffron-200">
            <Sparkles size={16} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <PanelTitle className="!text-sm">AI Expense Insights</PanelTitle>
              {hasResult && (
                <button
                  type="button"
                  onClick={onToggle}
                  aria-expanded={expanded}
                  aria-label={expanded ? "Collapse AI insights" : "Expand AI insights"}
                  className="inline-flex h-6 w-6 items-center justify-center rounded-sm text-ink-muted hover:bg-paper-deep hover:text-ink"
                >
                  {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              )}
            </div>
            <p className="mt-0.5 text-xs text-ink-muted">
              Generate business-friendly insights from approved expenses.
            </p>
          </div>
        </div>

        <div className="flex min-w-0 items-center gap-2">
          <label className="sr-only" htmlFor="ai-insight-period">Insight period</label>
          <select
            id="ai-insight-period"
            value={period}
            onChange={onPeriodChange}
            disabled={loading}
            className="h-8 min-w-0 flex-1 rounded-md border border-rule bg-paper px-2 text-xs text-ink focus:border-saffron-500 focus:outline-none focus:ring-2 focus:ring-saffron-500/15 disabled:opacity-60"
          >
            {AI_PERIODS.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
          <Button
            variant="secondary"
            size="xs"
            iconLeft={<Sparkles size={13} />}
            onClick={onGenerate}
            disabled={loading}
          >
            {loading ? "Analyzing..." : "Generate insights"}
          </Button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 border-t border-rule px-4 py-3 text-xs text-ink-muted">
          <Spinner className="h-4 w-4" />
          <span>Analyzing approved expenses...</span>
        </div>
      )}

      {!loading && expanded && (
        <div className="border-t border-rule px-4 py-3 text-sm">
          {error ? (
            <p className="text-cinnabar-700">{error}</p>
          ) : !data?.enough_data ? (
            <p className="text-ink-muted">Not enough approved expenses to generate insights.</p>
          ) : (
            <div className="grid gap-3">
              <div className="min-w-0">
                <p className="text-sm leading-relaxed text-ink-soft">{data.summary}</p>
                {insights.length > 0 && (
                  <ul className="mt-2 grid gap-1 text-xs text-ink-soft">
                    {insights.slice(0, 4).map((item) => (
                      <li key={item} className="flex gap-1.5">
                        <Sparkles size={12} className="mt-0.5 shrink-0 text-saffron-600" aria-hidden="true" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="grid gap-2 text-xs">
                {warnings.length > 0 && (
                  <div>
                    <p className="flex items-center gap-1.5 font-medium text-cinnabar-700">
                      <AlertTriangle size={13} aria-hidden="true" /> Warnings
                    </p>
                    <ul className="mt-1 space-y-1 text-ink-soft">
                      {warnings.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                )}
                {recommendations.length > 0 && (
                  <div>
                    <p className="flex items-center gap-1.5 font-medium text-forest-700">
                      <Lightbulb size={13} aria-hidden="true" /> Recommendations
                    </p>
                    <ul className="mt-1 space-y-1 text-ink-soft">
                      {recommendations.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

function ComparisonRow({ label, start, end, total, count, currency }) {
  return (
    <div className="rounded-sm bg-paper-deep/55 px-3 py-1.5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-ink-muted">{label}</p>
        <p className="num text-sm font-semibold text-ink">
          <Money value={Number(total) || 0} currency={currency} />
        </p>
      </div>
      <p className="mt-0.5 text-xs text-ink-muted">
        {start ? formatDate(start, "short") : DASH} to {end ? formatDate(end, "short") : DASH}
        {" "}- {Number(count) || 0} approved
      </p>
    </div>
  );
}

function CompactFact({ label, value }) {
  return (
    <div className="rounded-sm bg-paper-deep/55 px-3 py-1.5">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 truncate text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function ChangeLine({ value }) {
  const numeric = Number(value);
  const available = Number.isFinite(numeric);
  const positive = numeric > 0;
  const Icon = positive ? ArrowUpRight : ArrowDownRight;

  return (
    <div className="flex items-center justify-between border-t border-rule pt-3">
      <div>
        <p className="text-xs text-ink-muted">Change vs previous</p>
        <p className="mt-0.5 text-xs text-ink-muted">Same report scope</p>
      </div>
      <span className="inline-flex items-center gap-1 rounded-sm bg-paper px-2 py-1 text-sm font-semibold text-ink ring-1 ring-rule">
        {available && numeric !== 0 && <Icon size={14} aria-hidden="true" />}
        {available ? `${numeric.toFixed(1)}%` : DASH}
      </span>
    </div>
  );
}

function InsightLine({ label, name, value, currency }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-rule/70 py-2 last:border-b-0">
      <div className="min-w-0">
        <p className="text-xs text-ink-muted">{label}</p>
        <p className="truncate text-sm font-medium text-ink">{name || DASH}</p>
      </div>
      <p className="shrink-0 text-sm text-ink">
        {value == null ? DASH : <Money value={value} currency={currency} />}
      </p>
    </div>
  );
}

function BreakdownList({ rows, currency, labelFor, emptyTitle, columns = 1 }) {
  if (!rows?.length) {
    return (
      <EmptyState
        title={emptyTitle}
        description="No approved spend was returned for this section."
        className="py-8"
      />
    );
  }

  const maxTotal = Math.max(1, ...rows.map((row) => Number(row.total) || 0));

  return (
    <div className={`grid grid-cols-1 ${columns > 1 ? "lg:grid-cols-2" : ""}`}>
      {rows.map((row, index) => {
        const total = Number(row.total) || 0;
        const width = Math.max(3, Math.round((total / maxTotal) * 100));
        return (
          <div key={`${labelFor(row)}-${index}`} className="border-b border-rule/70 px-4 py-3 last:border-b-0">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{labelFor(row)}</p>
                <p className="mt-0.5 text-xs text-ink-muted">
                  {Number(row.count) || 0} approved - {Number(row.percentage) || 0}% share
                </p>
              </div>
              <p className="shrink-0 text-sm font-medium text-ink">
                <Money value={row.total} currency={currency} />
              </p>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-pill bg-paper-deep">
              <div
                className="h-full rounded-pill bg-forest-600"
                style={{ width: `${width}%` }}
                aria-hidden="true"
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
