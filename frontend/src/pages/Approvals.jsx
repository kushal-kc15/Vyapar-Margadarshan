import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  FileText,
  Inbox,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import api from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../components/Toast.jsx";
import { Panel, PanelHeader, PanelTitle } from "../components/Panel.jsx";
import Button from "../components/Button.jsx";
import { Avatar } from "../components/Avatar.jsx";
import { StatusPill } from "../components/StatusPill.jsx";
import { Money } from "../components/Money.jsx";
import { formatDate } from "../lib/date.js";
import { EmptyState, ErrorState, Spinner } from "../components/Feedback.jsx";
import { Modal } from "../components/Modal.jsx";
import { Textarea } from "../components/Field.jsx";
import PaginationControls from "../components/PaginationControls.jsx";
import { cn } from "../lib/utils.js";

const TABS = [
  { value: "PENDING", label: "Waiting" },
  { value: "APPROVED", label: "Approved" },
  { value: "REJECTED", label: "Rejected" },
];

const CATEGORIES = {
  FOOD: "Food & Dining",
  TRANSPORT: "Transportation",
  OFFICE: "Office Supplies",
  UTILITIES: "Utilities",
  SALARY: "Salary & Wages",
  RENT: "Rent",
  MARKETING: "Marketing",
  OTHER: "Other",
};

const personName = (expense) =>
  expense?.submitted_by_name ??
  expense?.user_name ??
  expense?.user_details?.full_name ??
  expense?.user_details?.username ??
  expense?.user_details?.email ??
  "Team member";

const categoryName = (expense) =>
  expense?.category_name ??
  CATEGORIES[expense?.category] ??
  expense?.category ??
  "-";
const expenseTitle = (expense) =>
  expense?.title ??
  expense?.vendor ??
  expense?.description ??
  "Untitled expense";

const emptyCopy = (tab) => {
  if (tab === "PENDING") {
    return {
      title: "No expenses waiting for approval",
      description: "New submissions will appear here.",
    };
  }
  if (tab === "APPROVED") {
    return {
      title: "No approved expenses",
      description: "Approved decisions will appear here.",
    };
  }
  return {
    title: "No rejected expenses",
    description: "Rejected decisions will appear here.",
  };
};

export default function Approvals() {
  const { currency, role } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState("PENDING");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [selected, setSelected] = useState(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const [approvalPage, setApprovalPage] = useState(1);
  const approvalPageSize = 10;

  const isExplicitStaff = String(role ?? "").toUpperCase() === "STAFF";

  useEffect(() => {
    setLoading(true);
    setLoadError("");
    setSelected(null);
    setNote("");
    setApprovalPage(1);

    const request =
      tab === "PENDING"
        ? api.get("/expenses/pending_approvals/")
        : api.get("/expenses/", { params: { status: tab, page_size: 50 } });

    request
      .then((response) => {
        const data = response.data?.results ?? response.data ?? [];
        const list = Array.isArray(data) ? data : [];
        setRows(list);
        setSelected(list[0] ?? null);
      })
      .catch(() => {
        setRows([]);
        setSelected(null);
        setLoadError(
          "Approval records could not be loaded. No decisions were changed.",
        );
      })
      .finally(() => setLoading(false));
  }, [tab, refreshKey]);

  const totalAmount = useMemo(
    () => rows.reduce((sum, row) => sum + (Number(row.amount) || 0), 0),
    [rows],
  );

  const pagedRows = useMemo(() => {
    const start = (approvalPage - 1) * approvalPageSize;
    const end = start + approvalPageSize;
    return rows.slice(start, end);
  }, [rows, approvalPage]);

  useEffect(() => {
    if (!selected) return;
    const onPage = pagedRows.some((r) => r.id === selected.id);
    if (!onPage) {
      setSelected(pagedRows[0] ?? null);
      setNote("");
      setConfirming(null);
    }
  }, [pagedRows]);

  const selectedAmount = selected ? (
    <Money value={selected.amount} currency={selected.currency ?? currency} />
  ) : null;

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  const decide = async (decision) => {
    if (!selected) return;
    setBusy(true);
    try {
      const endpoint = decision === "APPROVE" ? "approve" : "reject";
      const payload = decision === "REJECT" ? { reason: note } : {};
      await api.post(`/expenses/${selected.id}/${endpoint}/`, payload);
      toast.success(
        decision === "APPROVE" ? "Expense approved." : "Expense rejected.",
      );

      const response =
        tab === "PENDING"
          ? await api.get("/expenses/pending_approvals/")
          : await api.get("/expenses/", {
              params: { status: tab, page_size: 50 },
            });
      const data = response.data?.results ?? response.data ?? [];
      const list = Array.isArray(data) ? data : [];
      setRows(list);
      setSelected(list[0] ?? null);
      setNote("");
      setConfirming(null);
    } catch (err) {
      const d = err?.response?.data;
      const msg =
        d?.detail ||
        d?.error ||
        d?.message ||
        (Array.isArray(d?.non_field_errors)
          ? d.non_field_errors[0]
          : d?.non_field_errors) ||
        "Could not save your decision. Please review the expense and try again.";
      toast.error(String(msg));
    } finally {
      setBusy(false);
    }
  };

  const openDecision = (decision) => {
    if (!selected || busy) return;
    setConfirming(decision);
  };

  const pageActions = useMemo(
    () => (
      <Button
        variant="secondary"
        size="sm"
        iconLeft={<RefreshCw size={14} />}
        onClick={refresh}
        disabled={loading || busy}
      >
        Refresh
      </Button>
    ),
    [refresh, loading, busy],
  );

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-6 pt-2 sm:px-6 lg:px-8">
      <div className="mb-2 flex flex-wrap items-center justify-end gap-1.5 border-b border-rule pb-2" aria-label="Approval actions">
        {pageActions}
      </div>

      <div className="flex flex-col gap-2 border-b border-rule sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-1" role="tablist" aria-label="Approval status">
          {TABS.map((item) => {
            const active = item.value === tab;
            return (
              <button
                key={item.value}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setTab(item.value)}
                className={cn(
                  "h-9 shrink-0 rounded-t-sm px-3 text-sm transition-colors",
                    active
                    ? "-mb-px border-b-2 border-moss-500 bg-paper-deep/70 font-semibold text-ink"
                    : "text-ink-muted hover:text-ink",
                )}
              >
                {item.label}
              </button>
            );
          })}
        </div>
        <div className="pb-1.5 text-xs text-ink-muted sm:text-right">
          {rows.length} {rows.length === 1 ? "expense" : "expenses"} -{" "}
          <span className="num text-ink">
            <Money value={totalAmount} currency={currency} />
          </span>
        </div>
      </div>

      {isExplicitStaff && (
        <div className="mt-3 flex items-start gap-2 rounded-sm border border-rule bg-paper-deep px-3 py-2 text-sm text-ink-soft">
          <ShieldCheck
            size={16}
            className="mt-0.5 shrink-0 text-ink-muted"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <p>Owner workflow. Backend permissions still apply.</p>
        </div>
      )}

      <div className="mt-3 grid grid-cols-12 gap-4 lg:gap-5">
        <div className="col-span-12 lg:col-span-5">
          <Panel className="overflow-hidden">
            <PanelHeader className="!py-3">
              <div>
                <PanelTitle>
                  {tab === "PENDING"
                    ? "Waiting for decision"
                    : `${TABS.find((item) => item.value === tab)?.label} expenses`}
                </PanelTitle>
              </div>
            </PanelHeader>

            {loading ? (
              <LoadingQueue />
            ) : loadError ? (
              <ErrorState
                title="Approvals are unavailable"
                description={loadError}
                action={
                  <Button variant="secondary" onClick={refresh}>
                    Try again
                  </Button>
                }
              />
            ) : rows.length === 0 ? (
              <EmptyState
                icon={Inbox}
                title={emptyCopy(tab).title}
                description={emptyCopy(tab).description}
              />
            ) : (
              <>
                <ul className="divide-y divide-rule">
                  {pagedRows.map((expense) => (
                    <ApprovalQueueItem
                      key={expense.id}
                      expense={expense}
                      currency={currency}
                      active={selected?.id === expense.id}
                      onSelect={() => {
                        setSelected(expense);
                        setNote("");
                      }}
                    />
                  ))}
                </ul>

                <PaginationControls
                  page={approvalPage}
                  setPage={setApprovalPage}
                  pageSize={approvalPageSize}
                  totalItems={rows.length}
                />
              </>
            )}
          </Panel>
        </div>

        <div className="col-span-12 lg:col-span-7">
          {selected ? (
            <ApprovalDetail
              selected={selected}
              tab={tab}
              note={note}
              setNote={setNote}
              busy={busy}
              currency={currency}
              onApprove={() => openDecision("APPROVE")}
              onReject={() => openDecision("REJECT")}
            />
          ) : (
            <div className="h-full min-h-[14rem] flex items-center justify-center text-sm text-ink-muted py-10 border border-dashed border-rule rounded-sm">
              <div className="text-center">
                <Inbox
                  size={22}
                  className="mx-auto text-ink-faint"
                  strokeWidth={1.5}
                />
                <p className="mt-2">
                  {loading
                    ? "Loading details..."
                    : "Select an expense to review."}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {confirming && selected && (
        <DecisionDialog
          decision={confirming}
          expense={selected}
          amount={selectedAmount}
          note={note}
          busy={busy}
          onClose={() => !busy && setConfirming(null)}
          onConfirm={() => decide(confirming)}
        />
      )}
    </div>
  );
}

function LoadingQueue() {
  return (
    <div className="py-10 flex flex-col items-center justify-center gap-3 text-sm text-ink-muted">
      <Spinner className="text-ink-muted" />
      <span>Loading approval queue...</span>
    </div>
  );
}

function ApprovalQueueItem({ expense, currency, active, onSelect }) {
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className={cn(
          "w-full px-4 py-3.5 text-left transition-colors",
          active ? "bg-forest-50 ring-1 ring-inset ring-forest-200" : "hover:bg-paper-deep/60",
        )}
      >
        <div className="flex items-start gap-3">
          <Avatar name={personName(expense)} size={30} />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="break-words text-sm font-semibold text-ink sm:truncate">
                  {expenseTitle(expense)}
                </p>
                <p className="mt-0.5 text-xs text-ink-muted truncate">
                  {personName(expense)}
                </p>
              </div>
              <p className="num shrink-0 text-right text-sm text-ink">
                <Money
                  value={expense.amount}
                  currency={expense.currency ?? currency}
                />
              </p>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
              <span>
                {formatDate(expense.date ?? expense.created_at, "short")}
              </span>
              <span>{categoryName(expense)}</span>
              <span>{expense.vendor || "No vendor"}</span>
              {expense.receipt ? (
                <span className="inline-flex items-center gap-1 text-ink-soft">
                  <FileText size={13} strokeWidth={1.5} aria-hidden="true" />
                  Receipt
                </span>
              ) : (
                <span>No receipt</span>
              )}
            </div>
          </div>
        </div>
      </button>
    </li>
  );
}

function ApprovalDetail({
  selected,
  tab,
  note,
  setNote,
  busy,
  currency,
  onApprove,
  onReject,
}) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader className="!py-3" action={<StatusPill status={selected.status} />}>
        <div>
          <PanelTitle>{expenseTitle(selected)}</PanelTitle>
          <p className="mt-1 text-xs text-ink-muted break-words">
            Filed by {personName(selected)},{" "}
            {formatDate(
              selected.submitted_at ?? selected.created_at,
              "relative",
            )}
          </p>
        </div>
      </PanelHeader>

      <div className="p-4 sm:p-5">
        <dl className="grid grid-cols-1 gap-y-3.5 gap-x-6 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
              Amount
            </dt>
            <dd className="num text-2xl text-ink mt-0.5">
              <Money
                value={selected.amount}
                currency={selected.currency ?? currency}
              />
            </dd>
          </div>
          <div>
            <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
              Date
            </dt>
            <dd className="text-ink mt-0.5">
              {formatDate(selected.date ?? selected.created_at, "long")}
            </dd>
          </div>
          <div>
            <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
              Category
            </dt>
            <dd className="text-ink mt-0.5">{categoryName(selected)}</dd>
          </div>
          <div>
            <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
              Vendor
            </dt>
            <dd className="text-ink mt-0.5 break-words">
              {selected.vendor || "No vendor recorded"}
            </dd>
          </div>
          <div>
            <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
              Submitter
            </dt>
            <dd className="mt-1 flex items-center gap-2 text-ink">
              <Avatar name={personName(selected)} size={22} />
              <span className="min-w-0 break-words">
                {personName(selected)}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
              Receipt
            </dt>
            <dd className="mt-1">
              {selected.receipt ? (
                <a
                  href={selected.receipt}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-ink-muted hover:text-ink hover:underline"
                >
                  <FileText size={14} strokeWidth={1.5} aria-hidden="true" />
                  Open receipt
                </a>
              ) : (
                <span className="text-ink-muted">No receipt attached</span>
              )}
            </dd>
          </div>
          {selected.description && (
            <div className="sm:col-span-2">
              <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
                Notes
              </dt>
              <dd className="text-ink-soft mt-1 leading-relaxed break-words">
                {selected.description}
              </dd>
            </div>
          )}
        </dl>

        {(tab === "APPROVED" || tab === "REJECTED") && (
          <div className="mt-5 border-t border-rule pt-4 space-y-3">
            <p className="text-sm font-medium text-ink">Decision details</p>

            <dl className="grid grid-cols-1 gap-y-2.5 gap-x-6 text-sm sm:grid-cols-2">
              <div className="sm:col-span-2">
                <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
                  Status
                </dt>
                <dd className="text-ink mt-0.5">
                  {tab === "APPROVED" ? "Approved" : "Rejected"}
                </dd>
              </div>

              <div>
                <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
                  Reviewed by
                </dt>
                <dd className="text-ink mt-0.5">
                  {selected.reviewed_by_details?.username ??
                    selected.reviewed_by_details?.business_name ??
                    "—"}
                </dd>
              </div>

              <div>
                <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
                  Reviewed at
                </dt>
                <dd className="text-ink mt-0.5">
                  {selected.reviewed_at
                    ? formatDate(selected.reviewed_at, "long")
                    : "—"}
                </dd>
              </div>

              {tab === "REJECTED" && (
                <div className="sm:col-span-2">
                  <dt className="text-micro uppercase tracking-eyebrow text-ink-muted">
                    Rejection reason
                  </dt>
                  <dd className="text-ink-soft mt-0.5 break-words leading-relaxed">
                    {selected.rejection_reason?.trim()
                      ? selected.rejection_reason
                      : "No reason provided."}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        )}

        {tab === "PENDING" && (
          <div className="mt-5 border-t border-rule pt-4 space-y-3">
            <Textarea
              label="Rejection reason"
              rows={3}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Optional reason (shown only if you reject)"
            />
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-ink-muted">
                Check amount and receipt before deciding.
              </p>
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
                <Button
                  variant="danger"
                  onClick={onReject}
                  disabled={busy}
                  iconLeft={<X size={14} />}
                >
                  Reject
                </Button>
                <Button
                  variant="primary"
                  onClick={onApprove}
                  disabled={busy}
                  iconLeft={<Check size={14} />}
                >
                  Approve
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

function DecisionDialog({
  decision,
  expense,
  amount,
  note,
  busy,
  onClose,
  onConfirm,
}) {
  const approving = decision === "APPROVE";
  return (
    <Modal
      open
      onClose={onClose}
      title={approving ? "Approve expense?" : "Reject expense?"}
      description={
        approving
          ? "This will mark the expense as approved and remove it from the pending queue."
          : "This will send the expense back to the submitter for correction."
      }
      size="sm"
    >
      <div className="space-y-4">
        <div className="rounded-sm border border-rule bg-paper-deep px-3 py-3 text-sm">
          <p className="font-medium text-ink">{expenseTitle(expense)}</p>
          <p className="mt-1 text-xs text-ink-muted">
            {personName(expense)} - {categoryName(expense)}
          </p>
          <p className="mt-2 num text-ink">{amount}</p>
        </div>
        {!approving && note && (
          <div className="rounded-sm border border-rule bg-paper-deep px-3 py-3 text-sm">
            <p className="text-micro uppercase tracking-eyebrow text-ink-muted">
              Rejection note
            </p>
            <p className="mt-1 text-ink-soft break-words">{note}</p>
          </div>
        )}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={approving ? "primary" : "danger"}
            onClick={onConfirm}
            disabled={busy}
            iconLeft={approving ? <Check size={14} /> : <X size={14} />}
          >
            {busy
              ? "Saving..."
              : approving
                ? "Approve expense"
                : "Reject expense"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
