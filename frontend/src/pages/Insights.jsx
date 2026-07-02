import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Calendar,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import api from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { Panel, PanelTitle } from "../components/Panel.jsx";
import { Modal } from "../components/Modal.jsx";
import { Money } from "../components/Money.jsx";
import { Spinner } from "../components/Feedback.jsx";
import Button from "../components/Button.jsx";

const DATE_PRESETS = [
  { value: "this_month", label: "This month" },
  { value: "last_month", label: "Last month" },
  { value: "last_3_months", label: "Last 3 months" },
];

const AI_PERIODS = [
  { value: "this_month", label: "This month" },
  { value: "last_month", label: "Last month" },
  { value: "last_3_months", label: "Last 3 months" },
];

const padDate = (date) => date.toISOString().slice(0, 10);

const monthBounds = (offset = 0) => {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const end = offset === 0 ? now : new Date(now.getFullYear(), now.getMonth() + offset + 1, 0);
  return { from: padDate(start), to: padDate(end) };
};

const presetBounds = (preset) => {
  const now = new Date();
  if (preset === "last_month") return monthBounds(-1);
  if (preset === "last_3_months") {
    return {
      from: padDate(new Date(now.getFullYear(), now.getMonth() - 2, 1)),
      to: padDate(now),
    };
  }
  return monthBounds(0);
};

export default function Insights() {
  const { organization, currency } = useAuth();
  const organizationId = organization?.id ?? "";
  const initialRange = useMemo(() => monthBounds(0), []);
  const [preset, setPreset] = useState("this_month");
  const [from, setFrom] = useState(initialRange.from);
  const [to, setTo] = useState(initialRange.to);

  const [ruleAdvice, setRuleAdvice] = useState(null);
  const [ruleLoading, setRuleLoading] = useState(true);
  const [ruleError, setRuleError] = useState("");
  const [dismissedAdviceKeys, setDismissedAdviceKeys] = useState([]);
  const [ruleModalOpen, setRuleModalOpen] = useState(false);

  const [anomalyData, setAnomalyData] = useState(null);
  const [anomalyLoading, setAnomalyLoading] = useState(true);
  const [anomalyError, setAnomalyError] = useState("");

  const [insightPeriod, setInsightPeriod] = useState("this_month");
  const [aiInsights, setAiInsights] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiExpanded, setAiExpanded] = useState(false);

  useEffect(() => {
    const range = presetBounds(preset);
    setFrom(range.from);
    setTo(range.to);
  }, [preset]);

  useEffect(() => {
    if (!organizationId || !from || !to) return undefined;
    let cancelled = false;
    setRuleLoading(true);
    setRuleError("");
    setDismissedAdviceKeys([]);
    setRuleModalOpen(false);
    api.get("/analytics/rule-based-advice/", { params: { start_date: from, end_date: to } })
      .then((response) => {
        if (!cancelled) setRuleAdvice(response.data ?? null);
      })
      .catch(() => {
        if (!cancelled) {
          setRuleAdvice(null);
          setRuleError("Rule-based advice could not be loaded.");
        }
      })
      .finally(() => {
        if (!cancelled) setRuleLoading(false);
      });
    return () => { cancelled = true; };
  }, [organizationId, from, to]);

  useEffect(() => {
    if (!organizationId || !from || !to) return undefined;
    let cancelled = false;
    setAnomalyLoading(true);
    setAnomalyError("");
    api.get("/analytics/anomalies/", { params: { start_date: from, end_date: to, limit: 20 } })
      .then((response) => {
        if (!cancelled) setAnomalyData(response.data ?? null);
      })
      .catch(() => {
        if (!cancelled) {
          setAnomalyData(null);
          setAnomalyError("Unusual expense checks could not be loaded.");
        }
      })
      .finally(() => {
        if (!cancelled) setAnomalyLoading(false);
      });
    return () => { cancelled = true; };
  }, [organizationId, from, to]);

  useEffect(() => {
    setAiInsights(null);
    setAiError("");
    setAiExpanded(false);
  }, [organizationId]);

  const generateInsights = async () => {
    if (aiLoading || !organizationId) return;
    setAiLoading(true);
    setAiError("");
    try {
      const response = await api.get("/analytics/ai-insights/", { params: { period: insightPeriod } });
      setAiInsights(response.data ?? null);
      setAiExpanded(true);
    } catch {
      setAiInsights(null);
      setAiExpanded(true);
      setAiError("Could not generate the AI spending summary right now. Try again later.");
    } finally {
      setAiLoading(false);
    }
  };

  const activeAdvisories = (ruleAdvice?.advisories ?? []).filter(
    (advisory) => !dismissedAdviceKeys.includes(advisoryKey(advisory)),
  );
  const clearAdvice = (advisory) => {
    const key = advisoryKey(advisory);
    setDismissedAdviceKeys((current) => current.includes(key) ? current : [...current, key]);
  };

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-6 pt-2 sm:px-6 lg:px-8">
      <PageHeader
        title="Spending Intelligence"
        byline="Expense review"
        lede="Review budget pressure, unusual expense patterns, and AI-generated spending summaries."
        compact
        className="-mx-4 mb-3 sm:-mx-6 lg:-mx-8"
      />

      <InsightFilters preset={preset} setPreset={setPreset} />

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(19rem,22rem)] xl:items-start">
        <main className="min-w-0 space-y-3">
          <AIInsightsCard
            period={insightPeriod}
            onPeriodChange={(event) => {
              setInsightPeriod(event.target.value);
              setAiInsights(null);
              setAiError("");
              setAiExpanded(false);
            }}
            data={aiInsights}
            loading={aiLoading}
            error={aiError}
            expanded={aiExpanded}
            onToggle={() => setAiExpanded((value) => !value)}
            onGenerate={generateInsights}
          />
          <RuleBasedAdviceCard
            advisories={activeAdvisories}
            hadAdvisories={Boolean(ruleAdvice?.advisories?.length)}
            loading={ruleLoading}
            error={ruleError}
            currency={currency}
            onClear={clearAdvice}
            onShowAll={() => setRuleModalOpen(true)}
          />
        </main>

        <aside className="min-w-0 space-y-3 xl:sticky xl:top-20 xl:self-start">
          <UnusualExpenseCard data={anomalyData} loading={anomalyLoading} error={anomalyError} currency={currency} />
          <HowInsightsWork />
        </aside>
      </div>

      <RuleAdviceModal
        open={ruleModalOpen}
        onClose={() => setRuleModalOpen(false)}
        advisories={activeAdvisories}
        currency={currency}
        onClear={clearAdvice}
      />
    </div>
  );
}

function InsightFilters({ preset, setPreset }) {
  return (
    <section className="rounded-md border border-rule bg-paper-deep/60 px-3 py-2" aria-label="Insight filters">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="flex min-w-0 items-center gap-2 sm:mr-auto">
          <Calendar size={14} className="text-ink-muted" aria-hidden="true" />
          <p className="text-xs font-medium text-ink">Period</p>
        </div>
        <p className="text-xs text-ink-muted sm:mr-2">Applies to health checks and expenses needing review.</p>
        <label className="sr-only" htmlFor="insight-period">Period</label>
          <select id="insight-period" value={preset} onChange={(event) => setPreset(event.target.value)} className="h-8 w-full rounded-md border border-rule bg-paper px-2 text-xs text-ink sm:w-40">
            {DATE_PRESETS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
      </div>
    </section>
  );
}

const RULE_TONES = {
  danger: "bg-cinnabar-50 text-cinnabar-700 ring-cinnabar-200",
  warning: "bg-saffron-50 text-saffron-700 ring-saffron-200",
  info: "bg-forest-50 text-forest-700 ring-forest-200",
  success: "bg-moss-50 text-moss-700 ring-moss-200",
};

const advisoryKey = (advisory) => `${advisory.code}-${advisory.evidence?.budget_id ?? advisory.title}`;

function RuleBasedAdviceCard({ advisories, hadAdvisories, loading, error, currency, onClear, onShowAll }) {
  const visible = advisories.slice(0, 4);
  const hiddenCount = Math.max(0, advisories.length - visible.length);
  return (
    <Panel className="overflow-hidden" aria-label="Spending Health Checks">
      <InsightCardHeader icon={ShieldCheck} tone="forest" title="Spending Health Checks" subtitle="Checks approved expenses against budget limits and spending patterns." label="Fixed checks" />
      <div className="px-4 py-2.5 sm:px-5">
        {loading ? <LoadingLine text="Checking approved spending and budgets..." /> :
          error ? <p className="text-sm text-cinnabar-700">{error}</p> :
          advisories.length === 0 ? <EmptyLine text={hadAdvisories ? "All health checks cleared for this period." : "No spending concerns found for this period."} /> : (
            <>
              <ul className="divide-y divide-rule">
                {visible.map((advisory) => <li key={advisoryKey(advisory)} className="py-2.5 first:pt-0 last:pb-0"><AdviceItem advisory={advisory} currency={currency} onClear={onClear} /></li>)}
              </ul>
              {hiddenCount > 0 && <button type="button" onClick={onShowAll} className="mt-3 border-t border-rule pt-2 text-sm font-semibold text-forest-700 hover:text-forest-600">+{hiddenCount} more health checks — Show all</button>}
            </>
          )}
      </div>
    </Panel>
  );
}

function AdviceItem({ advisory, currency, onClear }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-sm font-semibold text-ink">{advisory.title}</p>
        <div className="flex items-center gap-1">
          <span className={`rounded-sm px-1.5 py-0.5 text-[11px] font-semibold capitalize ring-1 ${RULE_TONES[advisory.severity] ?? RULE_TONES.info}`}>{advisory.severity}</span>
          <button type="button" onClick={() => onClear(advisory)} className="inline-flex h-6 items-center gap-1 rounded-sm px-1.5 text-[11px] text-ink-muted hover:bg-paper-deep hover:text-ink" aria-label={`Clear ${advisory.title}`}><X size={12} /> Clear</button>
        </div>
      </div>
      <p className="mt-1 truncate text-xs text-ink-soft">{advisory.message}</p>
      <RuleEvidence evidence={advisory.evidence} currency={currency} />
      {advisory.recommendation && (
        <button type="button" onClick={() => setExpanded((value) => !value)} className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-forest-700 hover:text-forest-600">
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />} {expanded ? "Hide details" : "View advice"}
        </button>
      )}
      {expanded && <p className="mt-1 flex gap-1.5 text-xs leading-snug text-ink-muted"><Lightbulb size={12} className="mt-0.5 shrink-0" /><span>{advisory.recommendation}</span></p>}
    </div>
  );
}

function RuleEvidence({ evidence, currency }) {
  if (!evidence) return null;
  const percentage = evidence.percentage_used ?? evidence.percentage ?? evidence.increase_percentage;
  const amount = evidence.spent_amount ?? evidence.amount ?? evidence.current_total;
  if (percentage == null && amount == null) return null;
  return <div className="mt-1.5 flex flex-wrap gap-1.5 text-[11px] text-ink-muted">
    {percentage != null && <span className="num rounded-sm bg-paper-deep px-1.5 py-0.5">{Number(percentage).toFixed(1)}%</span>}
    {amount != null && <span className="rounded-sm bg-paper-deep px-1.5 py-0.5"><Money value={Number(amount)} currency={currency} className="text-[11px]" /></span>}
  </div>;
}

function RuleAdviceModal({ open, onClose, advisories, currency, onClear }) {
  return <Modal open={open} onClose={onClose} title="All Spending Health Checks" description="Review or clear individual checks for the selected period." size="xl" contentClassName="!py-2">
    {advisories.length === 0 ? <EmptyLine text="All health checks have been cleared for this period." /> : <ul className="divide-y divide-rule">{advisories.map((advisory) => <li key={advisoryKey(advisory)} className="py-3.5"><AdviceItem advisory={advisory} currency={currency} onClear={onClear} /></li>)}</ul>}
  </Modal>;
}

const ANOMALY_TONES = {
  HIGH: "bg-cinnabar-50 text-cinnabar-700 ring-cinnabar-200",
  MEDIUM: "bg-saffron-50 text-saffron-700 ring-saffron-200",
  LOW: "bg-forest-50 text-forest-700 ring-forest-200",
};
const REASON_LABELS = {
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
  return <Panel className="overflow-hidden" aria-label="Expenses Needing Review">
    <InsightCardHeader icon={ScanSearch} tone="saffron" title="Expenses Needing Review" subtitle="Highlights expenses with unusual amount, vendor, date, or duplicate patterns." label="Review signals" />
    <div className="px-4 py-2.5">
      {loading ? <LoadingLine text="Checking expense patterns..." /> : error ? <p className="text-xs text-cinnabar-700">{error}</p> : anomalies.length === 0 ? <EmptyLine text="No expenses need review for this period." /> : <>
        <ul className="divide-y divide-rule">{visible.map((expense) => <li key={expense.expense_id} className="py-2.5 first:pt-0 last:pb-0"><AnomalyItem expense={expense} currency={currency} /></li>)}</ul>
        {hiddenCount > 0 && <p className="mt-2 border-t border-rule pt-2 text-xs font-medium text-ink-muted">+{hiddenCount} more unusual {hiddenCount === 1 ? "expense" : "expenses"}</p>}
      </>}
    </div>
  </Panel>;
}

function AnomalyItem({ expense, currency }) {
  const [expanded, setExpanded] = useState(false);
  const reasons = expense.reasons ?? [];
  const firstReason = reasons[0];
  const extraCount = Math.max(0, reasons.length - 1);
  return (
    <div className="min-w-0">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-ink">{expense.title || "Untitled expense"}</p>
          <p className="mt-0.5 truncate text-[11px] text-ink-muted">{expense.vendor || "No vendor"}</p>
        </div>
        <Money value={expense.amount} currency={currency} className="shrink-0 text-xs font-semibold" />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        <span className={`rounded-sm px-1.5 py-0.5 text-[11px] font-semibold ring-1 ${ANOMALY_TONES[expense.severity] ?? ANOMALY_TONES.LOW}`}>{expense.severity}</span>
        <span className="num rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] text-ink-soft">Review score {expense.score}</span>
        <span className="rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] capitalize text-ink-muted">{String(expense.status || "").toLowerCase()}</span>
      </div>
      {firstReason && (
        <div className="mt-1.5 flex items-center justify-between gap-2 text-[11px] text-ink-muted">
          <span className="min-w-0 truncate">{REASON_LABELS[firstReason.code] ?? firstReason.message}{extraCount > 0 ? ` +${extraCount} more` : ""}</span>
          {extraCount > 0 && <button type="button" onClick={() => setExpanded((value) => !value)} className="shrink-0 font-medium text-forest-700 hover:text-forest-600">{expanded ? "Hide" : "Details"}</button>}
        </div>
      )}
      {expanded && <ul className="mt-1 space-y-0.5 text-[11px] text-ink-muted">{reasons.slice(1).map((reason) => <li key={reason.code}>• {REASON_LABELS[reason.code] ?? reason.message}</li>)}</ul>}
    </div>
  );
}

function AIInsightsCard({ period, onPeriodChange, data, loading, error, expanded, onToggle, onGenerate }) {
  const insights = data?.insights ?? [];
  const warnings = data?.warnings ?? [];
  const recommendations = data?.recommendations ?? [];
  const hasResult = Boolean(data || error);
  return <Panel className="overflow-hidden">
    <div className="flex flex-col gap-3 border-b border-rule px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
      <div className="flex min-w-0 items-center gap-2.5"><span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-saffron-50 text-saffron-700 ring-1 ring-saffron-200"><Sparkles size={16} /></span><div><div className="flex items-center gap-2"><PanelTitle className="!text-base">AI Spending Summary</PanelTitle>{hasResult && <button type="button" onClick={onToggle} aria-label={expanded ? "Collapse AI spending summary" : "Expand AI spending summary"} className="rounded-sm p-1 text-ink-muted hover:bg-paper-deep">{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button>}</div><p className="mt-0.5 text-xs text-ink-muted">Gemini summarizes approved spending into observations and suggestions.</p></div></div>
      <div className="flex items-center gap-2"><select value={period} onChange={onPeriodChange} disabled={loading} className="h-8 rounded-md border border-rule bg-paper px-2 text-xs text-ink">{AI_PERIODS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><Button variant="secondary" size="xs" iconLeft={<Sparkles size={13} />} onClick={onGenerate} disabled={loading}>{loading ? "Analyzing..." : "Generate insights"}</Button></div>
    </div>
    {loading && <div className="px-5 py-3"><LoadingLine text="Analyzing approved expenses..." /></div>}
    {!loading && expanded && <div className="px-4 py-4 sm:px-5">{error ? <p className="text-sm text-cinnabar-700">{error}</p> : !data?.enough_data ? <p className="text-sm text-ink-muted">Not enough approved expenses to generate insights.</p> : <div className="space-y-3"><p className="text-sm leading-relaxed text-ink-soft">{data.summary}</p>{insights.length > 0 && <ul className="grid gap-1 text-xs text-ink-soft sm:grid-cols-2">{insights.map((item) => <li key={item} className="flex gap-1.5"><Sparkles size={12} className="mt-0.5 shrink-0 text-saffron-600" />{item}</li>)}</ul>}<div className="grid gap-3 text-xs sm:grid-cols-2">{warnings.length > 0 && <div><p className="flex items-center gap-1.5 font-medium text-cinnabar-700"><AlertTriangle size={13} /> Warnings</p><ul className="mt-1 space-y-1 text-ink-soft">{warnings.map((item) => <li key={item}>{item}</li>)}</ul></div>}{recommendations.length > 0 && <div><p className="flex items-center gap-1.5 font-medium text-forest-700"><Lightbulb size={13} /> Recommendations</p><ul className="mt-1 space-y-1 text-ink-soft">{recommendations.map((item) => <li key={item}>{item}</li>)}</ul></div>}</div></div>}</div>}
  </Panel>;
}

function HowInsightsWork() {
  return <Panel className="overflow-hidden"><header className="border-b border-rule px-4 py-2.5"><PanelTitle className="!text-sm">How this page works</PanelTitle></header><ul className="space-y-1.5 px-4 py-3 text-xs text-ink-soft"><li>Health checks use fixed budget and spending conditions.</li><li>Review signals use weighted scoring from expense patterns.</li><li>AI summary explains approved spending in simple language.</li></ul></Panel>;
}

function InsightCardHeader({ icon: Icon, tone, title, subtitle, label }) {
  const styles = tone === "saffron" ? "bg-saffron-50 text-saffron-700 ring-saffron-200" : "bg-forest-50 text-forest-700 ring-forest-200";
  return <header className="border-b border-rule px-4 py-3 sm:px-5"><div className="flex items-start gap-2.5"><span className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md ring-1 ${styles}`}><Icon size={14} /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-start justify-between gap-1.5"><PanelTitle className="!text-sm">{title}</PanelTitle><span className={`rounded-sm px-1.5 py-0.5 text-[11px] font-medium ring-1 ${styles}`}>{label}</span></div><p className="mt-1 text-xs leading-snug text-ink-muted">{subtitle}</p></div></div></header>;
}

function LoadingLine({ text }) {
  return <div className="flex items-center gap-2 text-xs text-ink-muted"><Spinner className="h-4 w-4" /><span>{text}</span></div>;
}

function EmptyLine({ text }) {
  return <div className="flex items-center gap-2 py-2 text-sm text-ink-soft"><ShieldCheck size={16} className="shrink-0 text-moss-600" /><span>{text}</span></div>;
}
