import { useEffect, useState } from "react";
import { BookOpen, Filter, Shield } from "lucide-react";

import api from "../lib/api.js";
import { PageHeader } from "../components/PageHeader.jsx";
import { Panel, PanelTitle } from "../components/Panel.jsx";
import { Spinner } from "../components/Feedback.jsx";

const SEVERITY_TONES = {
  HIGH: "border-cinnabar-200 bg-cinnabar-50 text-cinnabar-700",
  MEDIUM: "border-saffron-200 bg-saffron-50 text-saffron-700",
  LOW: "border-forest-200 bg-forest-50 text-forest-700",
};

const CATEGORY_ICONS = {
  SPENDING_PATTERN: "chart",
  FINANCIAL_RISK: "alert",
  DUPLICATE: "copy",
  COMPLIANCE: "shield",
  VENDOR: "store",
  BUDGET: "wallet",
  APPROVAL: "clock",
};

export default function RuleKnowledgeBase() {
  const [rules, setRules] = useState([]);
  const [categories, setCategories] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .get("/analytics/rules/")
      .then((response) => {
        if (!cancelled) {
          setRules(response.data?.rules ?? []);
          setCategories(response.data?.categories ?? {});
        }
      })
      .catch(() => {
        if (!cancelled) setError("Could not load the rule knowledge base.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const filtered = rules.filter((rule) => {
    if (categoryFilter && rule.category !== categoryFilter) return false;
    if (severityFilter && rule.severity !== severityFilter) return false;
    return true;
  });

  const categoryOptions = Object.entries(categories);
  const enabledCount = rules.filter((r) => r.enabled).length;

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-6 pt-2 sm:px-6 lg:px-8">
      <PageHeader
        title="Rule Knowledge Base"
        byline="Expert system"
        lede="The rules that drive anomaly detection and expense risk scoring. Each rule contributes a score when its condition is met."
        compact
        className="-mx-4 mb-3 sm:-mx-6 lg:-mx-8"
      />

      <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label="Total Rules" value={rules.length} />
        <StatCard label="Active Rules" value={enabledCount} />
        <StatCard label="Rule Categories" value={categoryOptions.length} />
      </div>

      <Panel className="overflow-hidden">
        <header className="flex flex-col gap-3 border-b border-rule px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-forest-50 text-forest-700 ring-1 ring-forest-200">
              <BookOpen size={16} />
            </span>
            <div>
              <PanelTitle className="!text-base">Expense Review Rules</PanelTitle>
              <p className="mt-0.5 text-xs text-ink-muted">
                {filtered.length} rule{filtered.length !== 1 ? "s" : ""} shown
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Filter size={13} className="text-ink-muted" />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="h-8 rounded-md border border-rule bg-paper px-2 text-xs text-ink"
            >
              <option value="">All categories</option>
              {categoryOptions.map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="h-8 rounded-md border border-rule bg-paper px-2 text-xs text-ink"
            >
              <option value="">All severities</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
        </header>

        <div className="px-4 py-3 sm:px-5">
          {loading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-ink-muted">
              <Spinner className="h-4 w-4" />
              <span>Loading rule definitions...</span>
            </div>
          ) : error ? (
            <p className="py-4 text-sm text-cinnabar-700">{error}</p>
          ) : filtered.length === 0 ? (
            <p className="py-4 text-sm text-ink-muted">No rules match the selected filters.</p>
          ) : (
            <ul className="divide-y divide-rule">
              {filtered.map((rule) => (
                <li key={rule.code} className="py-3 first:pt-0 last:pb-0">
                  <RuleRow rule={rule} categories={categories} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </Panel>

      <Panel className="mt-3 overflow-hidden">
        <header className="border-b border-rule px-4 py-2.5 sm:px-5">
          <PanelTitle className="!text-sm">How the scoring works</PanelTitle>
        </header>
        <div className="space-y-2 px-4 py-3 text-xs text-ink-soft sm:px-5">
          <p>Each pending expense is evaluated against all enabled rules. When a rule's condition is met, its score is added to the total risk score (capped at 100).</p>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-sm border border-forest-200 bg-forest-50 px-2.5 py-2">
              <p className="font-semibold text-forest-700">LOW (0-30)</p>
              <p className="text-forest-700/80">Routine check. Manager approval sufficient.</p>
            </div>
            <div className="rounded-sm border border-saffron-200 bg-saffron-50 px-2.5 py-2">
              <p className="font-semibold text-saffron-700">MEDIUM (31-65)</p>
              <p className="text-saffron-700/80">Elevated risk. Review with rule explanation.</p>
            </div>
            <div className="rounded-sm border border-cinnabar-200 bg-cinnabar-50 px-2.5 py-2">
              <p className="font-semibold text-cinnabar-700">HIGH (66-100)</p>
              <p className="text-cinnabar-700/80">High risk. Detailed verification required.</p>
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="rounded-md border border-rule bg-paper px-4 py-3">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-ink">{value}</p>
    </div>
  );
}

function RuleRow({ rule, categories }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-ink">{rule.name}</p>
            {!rule.enabled && (
              <span className="rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] text-ink-muted">Disabled</span>
            )}
          </div>
          <p className="mt-0.5 text-xs text-ink-muted">{rule.description}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className={`rounded-sm border px-1.5 py-0.5 text-[11px] font-semibold tabular-nums ${SEVERITY_TONES[rule.severity] ?? SEVERITY_TONES.LOW}`}>
            +{rule.score}
          </span>
          <span className={`rounded-sm border px-1.5 py-0.5 text-[11px] font-medium ${SEVERITY_TONES[rule.severity] ?? SEVERITY_TONES.LOW}`}>
            {rule.severity}
          </span>
        </div>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <span className="rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] text-ink-muted">
          {rule.category_label ?? rule.category}
        </span>
        <span className="rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] font-mono text-ink-muted">
          {rule.code}
        </span>
        <span className="rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] text-ink-muted">
          v{rule.version}
        </span>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-[11px] font-medium text-forest-700 hover:text-forest-600"
        >
          {expanded ? "Less" : "More"}
        </button>
      </div>
      {expanded && (
        <div className="mt-2 rounded-sm border border-rule bg-paper-deep/50 px-3 py-2">
          <div className="flex items-start gap-1.5 text-xs">
            <Shield size={12} className="mt-0.5 shrink-0 text-forest-600" />
            <div>
              <p className="font-medium text-ink">Recommendation</p>
              <p className="mt-0.5 text-ink-soft">{rule.recommendation}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
