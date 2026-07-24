import { useState } from "react";
import { Link } from "react-router-dom";
import { Lightbulb } from "lucide-react";

import { Money } from "../Money.jsx";
import RiskScoreBar from "./RiskScoreBar.jsx";

const ANOMALY_TONES = {
  HIGH: "bg-cinnabar-50 text-cinnabar-700 ring-cinnabar-200",
  MEDIUM: "bg-saffron-50 text-saffron-700 ring-saffron-200",
  LOW: "bg-forest-50 text-forest-700 ring-forest-200",
};

const SEVERITY_TONES = {
  HIGH: "border-cinnabar-200 bg-cinnabar-50 text-cinnabar-700",
  MEDIUM: "border-saffron-200 bg-saffron-50 text-saffron-700",
  LOW: "border-forest-200 bg-forest-50 text-forest-700",
};

const REASON_LABELS = {
  HIGH_CATEGORY_AMOUNT: "Higher than usual category spending",
  HIGH_VENDOR_AMOUNT: "Higher than usual vendor spending",
  HIGH_AMOUNT: "High-value expense",
  HIGH_AMOUNT_CRITICAL: "High-value expense (critical)",
  HIGH_AMOUNT_ELEVATED: "High-value expense (elevated)",
  HIGH_AMOUNT_ROUTINE: "High-value expense (routine check)",
  CATEGORY_OUTLIER: "Statistical outlier for this category",
  DUPLICATE_CANDIDATE: "Possible duplicate",
  NEW_VENDOR: "New vendor",
  MISSING_RECEIPT: "No receipt attached",
  MISSING_VENDOR: "Missing vendor information",
  WEAK_DESCRIPTION: "Description needs more detail",
  BUDGET_PRESSURE: "Budget is close to its limit",
  BUDGET_EXCEEDED: "Budget limit would be exceeded",
  OLD_PENDING_EXPENSE: "Waiting for review for several days",
};

export { ANOMALY_TONES, SEVERITY_TONES, REASON_LABELS };

export default function AnomalyCard({ expense, currency }) {
  const [expanded, setExpanded] = useState(false);
  const triggeredRules = expense.triggered_rules ?? [];
  const reasons = expense.reasons ?? [];
  const displayRules = triggeredRules.length > 0 ? triggeredRules : reasons;
  const riskScore = expense.risk_score ?? expense.score ?? 0;
  const firstRule = displayRules[0];
  const extraCount = Math.max(0, displayRules.length - 1);

  return (
    <div className="min-w-0">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-ink">{expense.title || "Untitled expense"}</p>
          <p className="mt-0.5 truncate text-[11px] text-ink-muted">{expense.vendor || "No vendor"}</p>
        </div>
        <Money value={expense.amount} currency={currency} className="shrink-0 text-xs font-semibold" />
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <span className={`rounded-sm px-1.5 py-0.5 text-[11px] font-semibold ring-1 ${ANOMALY_TONES[expense.severity] ?? ANOMALY_TONES.LOW}`}>{expense.severity}</span>
        <RiskScoreBar score={riskScore} />
        <span className="rounded-sm bg-paper-deep px-1.5 py-0.5 text-[11px] capitalize text-ink-muted">{String(expense.status || "").toLowerCase()}</span>
      </div>

      {firstRule && (
        <div className="mt-1.5 text-[11px] text-ink-muted">
          <span className="block min-w-0 truncate">{REASON_LABELS[firstRule.code] ?? firstRule.message}{extraCount > 0 ? ` +${extraCount} more` : ""}</span>
          {extraCount > 0 && <button type="button" onClick={() => setExpanded((value) => !value)} className="mt-1 block font-medium text-forest-700 hover:text-forest-600">{expanded ? "Hide breakdown" : "Score breakdown"}</button>}
        </div>
      )}

      {expanded && (
        <div className="mt-2 space-y-2 border-t border-rule pt-2">
          <ul className="space-y-1.5">
            {displayRules.map((rule) => (
              <li key={rule.code} className="flex items-start gap-1.5 text-[11px]">
                <span className={`mt-0.5 shrink-0 rounded-sm border px-1 py-px font-semibold tabular-nums ${SEVERITY_TONES[rule.severity] ?? SEVERITY_TONES.LOW}`}>+{rule.score}</span>
                <div className="min-w-0">
                  <span className="font-medium text-ink">{rule.name ?? REASON_LABELS[rule.code] ?? rule.code}</span>
                  <span className="ml-1 text-ink-muted">{rule.message}</span>
                </div>
              </li>
            ))}
          </ul>
          {expense.recommendations?.length > 0 && (
            <div className="rounded-sm border border-forest-200 bg-forest-50 px-2 py-1.5">
              <p className="flex items-center gap-1 text-[11px] font-medium text-forest-700"><Lightbulb size={11} /> Recommendation</p>
              <p className="mt-0.5 text-[11px] leading-snug text-forest-700/80">{expense.recommendations[0]}</p>
            </div>
          )}
        </div>
      )}

      <Link
        to={`/approvals?expense_id=${encodeURIComponent(expense.expense_id)}`}
        className="ml-auto mt-1.5 flex w-fit text-xs font-semibold text-forest-700 transition-colors hover:text-forest-600"
      >
        Review expense
      </Link>
    </div>
  );
}
