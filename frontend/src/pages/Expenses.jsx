import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Download,
  FileText,
  Plus,
  RefreshCw,
  ScanText,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import api from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../components/Toast.jsx";
import { Panel } from "../components/Panel.jsx";
import Button from "../components/Button.jsx";
import { Input, Select, Textarea } from "../components/Field.jsx";
import { Modal } from "../components/Modal.jsx";
import { StatusPill } from "../components/StatusPill.jsx";
import { Money } from "../components/Money.jsx";
import { Avatar } from "../components/Avatar.jsx";
import { formatDate } from "../lib/date.js";
import { cn } from "../lib/utils.js";
import { EmptyState, ErrorState, Spinner } from "../components/Feedback.jsx";
import { OCRReceiptModal } from "../components/OCRReceiptModal.jsx";
import { EXPENSE_CATEGORIES, formatCategoryLabel } from "../lib/categories.js";

const STATUSES = [
  { value: "", label: "All statuses" },
  { value: "PENDING", label: "Pending" },
  { value: "APPROVED", label: "Approved" },
  { value: "REJECTED", label: "Rejected" },
];

const categoryLabel = (value) => formatCategoryLabel(value) ?? "-";

const personName = (expense) =>
  expense?.submitted_by_name ??
  expense?.user_name ??
  expense?.user_details?.full_name ??
  expense?.user_details?.username ??
  expense?.user_details?.email ??
  "Team member";

const expensePayload = (form) => ({
  title: form.title,
  amount: form.amount,
  date: form.date,
  category: form.category,
  vendor: form.vendor,
  description: form.description,
});

export default function Expenses() {
  const { currency, role, user } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [q, setQ] = useState(params.get("search") ?? params.get("q") ?? "");
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [category, setCategory] = useState(params.get("category") ?? "");
  const [categories] = useState(EXPENSE_CATEGORIES);
  const [page, setPage] = useState(1);

  const [refreshKey, setRefreshKey] = useState(0);
  const pageSize = 25;

  const [modalOpen, setModalOpen] = useState(params.get("new") === "1");
  const [ocrOpen, setOcrOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [detail, setDetail] = useState(null);

  const isStaff = String(role ?? "").toUpperCase() === "STAFF";
  const hasFilters = Boolean(q || status || category);
  const totalPages = Math.max(1, Math.ceil(count / pageSize));

  useEffect(() => {
    setLoading(true);
    setLoadError("");

    const next = new URLSearchParams();
    if (q) next.set("search", q);
    if (status) next.set("status", status);
    if (category) next.set("category", category);
    next.set("page", String(page));
    next.set("page_size", String(pageSize));
    setParams(next, { replace: true });

    api
      .get("/expenses/", { params: Object.fromEntries(next) })
      .then((r) => {
        const data = r.data;
        const list = data?.results ?? data ?? [];
        setRows(Array.isArray(list) ? list : []);
        setCount(data?.count ?? (Array.isArray(list) ? list.length : 0));
      })
      .catch(() => {
        setRows([]);
        setCount(0);
        setLoadError(
          "Expenses could not be loaded. Your saved records were not changed.",
        );
      })
      .finally(() => setLoading(false));
  }, [q, status, category, page, refreshKey]);

  const totalAmount = useMemo(
    () => rows.reduce((sum, row) => sum + (Number(row.amount) || 0), 0),
    [rows],
  );

  const closeModal = useCallback(() => {
    setModalOpen(false);
    setEditing(null);
  }, []);
  const openNew = useCallback(() => {
    setEditing(null);
    setModalOpen(true);
  }, []);
  const retryLoad = useCallback(() => setRefreshKey((key) => key + 1), []);
  const clearFilters = () => {
    setQ("");
    setStatus("");
    setCategory("");
    setPage(1);
  };

  const exportFilename = (response) => {
    const disposition = response?.headers?.["content-disposition"];
    const match = /filename="?([^";]+)"?/.exec(disposition || "");
    return match
      ? match[1]
      : `expenses_${new Date().toISOString().slice(0, 10)}.csv`;
  };

  const exportCsv = useCallback(async () => {
    const next = new URLSearchParams();
    if (q) next.set("search", q);
    if (status) next.set("status", status);
    if (category) next.set("category", category);

    try {
      const response = await api.get("/expenses/export_csv/", {
        params: Object.fromEntries(next),
        responseType: "blob",
      });
      const blob =
        response.data instanceof Blob
          ? response.data
          : new Blob([response.data], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = exportFilename(response);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success("Expense CSV exported.");
    } catch {
      toast.error("Could not export expenses.");
    }
  }, [q, status, category, toast]);

  const onSaved = () => {
    closeModal();
    const wasRejected = String(editing?.status ?? "").toUpperCase() === "REJECTED";
    toast.success(
      editing
        ? wasRejected
          ? "Expense resubmitted for approval."
          : "Expense updated."
        : "Expense added.",
    );
    setRefreshKey((key) => key + 1);
  };

  const handleOcrCreated = useCallback(() => {
    setPage(1);
    setRefreshKey((key) => key + 1);
    if (status === "") {
      toast.success("Expense created from receipt scan.");
    } else {
      toast.success(
        "Expense created from receipt scan. Showing page 1; change filters if you do not see it.",
      );
    }
  }, [status, toast]);

  const pageActions = useMemo(
    () => (
      <>
        <Button
          variant="secondary"
          size="sm"
          iconLeft={<Download size={14} />}
          onClick={exportCsv}
          disabled={loading || count === 0}
        >
          Export CSV
        </Button>
        <Button
          variant="secondary"
          size="sm"
          iconRight={<ScanText size={14} />}
          onClick={() => setOcrOpen(true)}
        >
          Scan receipt with AI
        </Button>
        <Button
          variant="secondary"
          size="sm"
          iconLeft={<RefreshCw size={14} />}
          onClick={retryLoad}
          disabled={loading}
        >
          Refresh
        </Button>
        <Button
          variant="primary"
          size="sm"
          iconRight={<Plus size={14} />}
          onClick={openNew}
        >
          Add expense
        </Button>
      </>
    ),
    [exportCsv, loading, count, retryLoad, openNew],
  );

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-6 pt-2 sm:px-6 lg:px-8">
      <div className="mb-2 flex flex-wrap items-center justify-end gap-1.5 border-b border-rule pb-2" aria-label="Expense actions">
        {pageActions}
      </div>

      <section
        className="rounded-md border border-rule bg-paper-deep/50"
        aria-label="Expense filters"
      >
        <div className="flex flex-col gap-2 px-3 py-2 sm:px-4">
          <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-baseline gap-2">
              <p className="shrink-0 text-xs font-medium text-ink">Filter ledger</p>
              <p className="truncate text-xs text-ink-muted">
                {hasFilters
                  ? "Matching expenses."
                  : "Search expenses by title, vendor, notes, or submitter."}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
              <SlidersHorizontal
                size={14}
                strokeWidth={1.5}
                aria-hidden="true"
              />
              <span>
                {count} {count === 1 ? "entry" : "entries"}
              </span>
              {hasFilters && (
                <Button variant="ghost" size="xs" onClick={clearFilters}>
                  Clear filters
                </Button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 md:grid-cols-12">
            <div className="md:col-span-6">
              <label className="field-label" htmlFor="expense-search">
                Search
              </label>
              <div className="relative">
                <Search
                  size={14}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
                  strokeWidth={1.5}
                  aria-hidden="true"
                />
                <input
                  id="expense-search"
                  type="search"
                  placeholder="Search title, vendor, notes, or submitter"
                  value={q}
                  onChange={(event) => {
                    setQ(event.target.value);
                    setPage(1);
                  }}
                  className="w-full h-10 md:h-9 pl-9 pr-3 bg-paper border border-rule rounded-sm text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:border-moss-500 focus:ring-2 focus:ring-moss-500/15 transition-colors"
                />
              </div>
            </div>
            <div className="md:col-span-3">
              <Select
                label="Status"
                className="md:h-9"
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value);
                  setPage(1);
                }}
              >
                {STATUSES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="md:col-span-3">
              <Select
                label="Category"
                className="md:h-9"
                value={category}
                onChange={(event) => {
                  setCategory(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All categories</option>
                {categories.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        </div>
      </section>

      <Panel className="mt-3 overflow-hidden">
        <div className="flex items-center justify-between border-b border-rule px-4 py-3 sm:px-5">
          <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
            <h2 className="font-display text-sm font-semibold text-ink">
              Expense ledger
            </h2>
            <span className="text-xs text-ink-muted hidden sm:inline">-</span>
            <span className="text-xs text-ink-muted">
              {rows.length} of {count} shown - Total{" "}
              <span className="num text-ink">
                <Money value={totalAmount} currency={currency} />
              </span>
            </span>
          </div>
        </div>

        {loading ? (
          <div className="py-14 flex flex-col items-center justify-center gap-3 text-sm text-ink-muted">
            <Spinner className="text-ink-muted" />
            <span>Loading expense records...</span>
          </div>
        ) : loadError ? (
          <ErrorState
            title="Expenses are unavailable"
            description={loadError}
            action={
              <Button variant="secondary" onClick={retryLoad}>
                Try again
              </Button>
            }
          />
        ) : rows.length === 0 ? (
          <EmptyState
            title={
              hasFilters
                ? "No expenses match these filters"
                : "No expenses recorded yet"
            }
            description={
              hasFilters
                ? "Clear one or more filters to return to the full ledger."
                : isStaff
                  ? "Submit your first expense."
                  : "Add an expense or scan a receipt."
            }
            action={
              hasFilters ? (
                <Button variant="secondary" onClick={clearFilters}>
                  Clear filters
                </Button>
              ) : (
                <Button
                  variant="primary"
                  iconRight={<Plus size={14} />}
                  onClick={openNew}
                >
                  Add expense
                </Button>
              )
            }
          />
        ) : (
          <>
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-micro uppercase tracking-eyebrow text-ink-muted border-b border-rule">
                    <th className="py-2.5 pl-5 font-semibold">Date</th>
                    <th className="py-2.5 font-semibold">Expense</th>
                    <th className="py-2.5 font-semibold">Category</th>
                    <th className="py-2.5 font-semibold">Status</th>
                    <th className="py-2.5 pr-5 font-semibold text-right">
                      Amount
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule/50">
                  {rows.map((expense) => (
                    <tr
                      key={expense.id}
                      onClick={() => setDetail(expense)}
                      className="cursor-pointer transition-colors hover:bg-paper-deep/50"
                    >
                      <td className="w-28 whitespace-nowrap py-3 pl-5 text-xs text-ink-soft">
                        {formatDate(
                          expense.date ?? expense.created_at,
                          "short",
                        )}
                      </td>
                      <td className="min-w-0 py-3 pr-4">
                        <div className="flex min-w-0 items-center gap-1.5">
                          <p className="min-w-0 truncate font-medium text-ink">
                            {expense.title ?? expense.description ?? "-"}
                          </p>
                          {expense.receipt && (
                            <span
                              className="shrink-0 text-ink-muted"
                              title="Receipt attached"
                            >
                              <FileText
                                size={13}
                                strokeWidth={1.5}
                                aria-hidden="true"
                              />
                              <span className="sr-only">Receipt attached</span>
                            </span>
                          )}
                        </div>
                        <p className="truncate text-[11px] text-ink-muted">
                          {[expense.vendor || "No vendor", expense.description, personName(expense)]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      </td>
                      <td className="py-3 pr-4 text-xs text-ink-soft">
                        {categoryLabel(expense.category)}
                      </td>
                      <td className="py-3 pr-4">
                        <StatusPill status={expense.status} />
                      </td>
                      <td className="whitespace-nowrap py-3 pr-5 text-right font-medium text-ink tabular-nums">
                        <Money
                          value={expense.amount}
                          currency={expense.currency ?? currency}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="md:hidden divide-y divide-rule/50">
              {rows.map((expense) => (
                <button
                  key={expense.id}
                  type="button"
                  onClick={() => setDetail(expense)}
                  className="w-full px-4 py-3.5 text-left hover:bg-paper-deep/40 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex min-w-0 items-center gap-1.5">
                        <p className="min-w-0 truncate text-sm font-medium text-ink">
                          {expense.title ?? expense.description ?? "-"}
                        </p>
                        {expense.receipt && (
                          <span
                            className="shrink-0 text-ink-muted"
                            title="Receipt attached"
                          >
                            <FileText
                              size={13}
                              strokeWidth={1.5}
                              aria-hidden="true"
                            />
                            <span className="sr-only">Receipt attached</span>
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 truncate text-xs text-ink-muted">
                        {expense.vendor || "No vendor"} · {categoryLabel(expense.category)}
                      </p>
                      <p className="mt-1 text-xs text-ink-muted">
                        {formatDate(
                          expense.date ?? expense.created_at,
                          "short",
                        )}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="num text-sm text-ink">
                        <Money
                          value={expense.amount}
                          currency={expense.currency ?? currency}
                        />
                      </p>
                      <div className="mt-1">
                        <StatusPill status={expense.status} />
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}

        {count > pageSize && (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-5 py-3 border-t border-rule">
            <span className="text-xs text-ink-muted">
              Page {page} of {totalPages}
            </span>
            <div className="flex w-full items-center gap-1 sm:w-auto">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((current) => current - 1)}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={page * pageSize >= count}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Panel>

      {modalOpen && (
        <ExpenseEditor
          editing={editing}
          categories={categories}
          defaultCurrency={currency}
          role={role}
          onClose={closeModal}
          onSaved={onSaved}
          onCreated={handleOcrCreated}
        />
      )}

      {detail && (
        <ExpenseDetail
          row={detail}
          currency={currency}
          currentUserId={user?.id}
          onClose={() => setDetail(null)}
          onEdit={() => {
            const submitterId = detail.user ?? detail.user_details?.id;
            const isSubmitter =
              user?.id != null &&
              submitterId != null &&
              Number(submitterId) === Number(user.id);
            const isPending =
              String(detail.status ?? "").toUpperCase() === "PENDING";
            const isRejected =
              String(detail.status ?? "").toUpperCase() === "REJECTED";

            if (!isSubmitter || (!isPending && !isRejected)) return;

            setEditing(detail);
            setDetail(null);
            setModalOpen(true);
          }}
        />
      )}

      <OCRReceiptModal
        open={ocrOpen}
        onClose={() => setOcrOpen(false)}
        onCreated={handleOcrCreated}
      />
    </div>
  );
}

/* ---------- Expense Editor Modal ---------- */

function ExpenseEditor({
  editing,
  categories,
  defaultCurrency,
  role,
  onClose,
  onSaved,
  onCreated,
}) {
  const toast = useToast();
  const [form, setForm] = useState(() => ({
    title: editing?.title ?? editing?.description ?? "",
    description: editing?.description ?? "",
    amount: editing?.amount ?? "",
    date: editing?.date ?? new Date().toISOString().slice(0, 10),
    category: editing?.category ?? "",
    vendor: editing?.vendor ?? "",
  }));
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState({});
  const [ocrOpen, setOcrOpen] = useState(false);
  const isStaff = String(role ?? "").toUpperCase() === "STAFF";

  const update = (key) => (event) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event?.preventDefault();
    setSubmitting(true);
    setErr({});

    try {
      let saved;
      if (editing) {
        const res = await api.patch(
          `/expenses/${editing.id}/`,
          expensePayload(form),
        );
        saved = res.data;
      } else {
        const res = await api.post("/expenses/", expensePayload(form));
        saved = res.data;
      }
      onSaved(saved);
    } catch (error) {
      const data = error?.response?.data;
      if (data && typeof data === "object") {
        const fieldErrors = {};
        Object.entries(data).forEach(([key, value]) => {
          fieldErrors[key] = Array.isArray(value) ? value[0] : String(value);
        });
        setErr(fieldErrors);
      } else {
        toast.error("Could not save the expense.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={
        editing
          ? String(editing.status ?? "").toUpperCase() === "REJECTED"
            ? "Correct and resubmit"
            : "Edit expense"
          : "Add expense"
      }
      description={
        editing
          ? String(editing.status ?? "").toUpperCase() === "REJECTED"
            ? "Update the rejected expense. Saving sends it back for owner review."
            : "Update this expense."
          : "Record a business cost."
      }
      size="lg"
    >
      <form onSubmit={submit} className="space-y-5" noValidate>
        {(err.detail || err.error || err.non_field_errors) && (
          <div className="rounded-sm border border-cinnabar-200 bg-cinnabar-50 px-3 py-2 text-sm text-cinnabar-700">
            {err.detail || err.error || err.non_field_errors}
          </div>
        )}

        {String(editing?.status ?? "").toUpperCase() === "REJECTED" && (
          <div className="rounded-sm border border-saffron-200 bg-saffron-50 px-3 py-2.5 text-sm text-saffron-800">
            <p className="font-medium">Owner requested correction</p>
            <p className="mt-1 text-xs leading-relaxed">
              {editing.rejection_reason?.trim()
                ? editing.rejection_reason
                : "No reason was provided. Update the details and resubmit for review."}
            </p>
          </div>
        )}

        {editing?.receipt && (
          <div className="rounded-md border border-rule bg-paper-deep/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink">Receipt attached</p>
                <p className="mt-1 text-xs text-ink-muted">
                  A receipt is on file for this expense.
                </p>
              </div>
              <a
                href={editing.receipt}
                target="_blank"
                rel="noreferrer"
                className="inline-flex shrink-0 items-center gap-1.5 rounded-sm border border-rule bg-paper px-3 py-1.5 text-xs text-ink hover:bg-paper-deep transition-colors"
              >
                <FileText size={13} strokeWidth={1.5} aria-hidden="true" />
                Open receipt
              </a>
            </div>
          </div>
        )}

        {!editing && (
          <div className="rounded-md border border-rule bg-paper-deep/60 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink">Scan receipt with AI</p>
                <p className="mt-1 text-xs leading-relaxed text-ink-muted">
                  Upload a receipt and review extracted details.
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                iconRight={<ScanText size={14} />}
                onClick={() => setOcrOpen(true)}
              >
                Scan receipt with AI
              </Button>
            </div>
            <div className="mt-3 flex items-center gap-3 text-xs text-ink-muted">
              <span className="h-px flex-1 bg-rule" />
              <span>or enter details manually</span>
              <span className="h-px flex-1 bg-rule" />
            </div>
          </div>
        )}

        <Input
          label="Expense title"
          value={form.title}
          onChange={update("title")}
          required
          placeholder="e.g. Lunch with supplier"
          error={err.title}
          help="Use a short, recognizable name."
        />

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Input
            type="number"
            step="0.01"
            min="0"
            label="Amount"
            value={form.amount}
            onChange={update("amount")}
            required
            error={err.amount}
          />
          <Select label="Currency" value={defaultCurrency} disabled>
            {["NPR", "INR", "USD", "EUR"].map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
          <Input
            type="date"
            label="Expense date"
            value={form.date}
            onChange={update("date")}
            required
            error={err.date}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="Category"
            value={form.category}
            onChange={update("category")}
            error={err.category}
          >
            <option value="">Select category</option>
            {categories.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
          <Input
            label="Vendor"
            value={form.vendor}
            onChange={update("vendor")}
            placeholder="Supplier or shop name"
            error={err.vendor}
          />
        </div>

        <Textarea
          label="Notes"
          rows={3}
          value={form.description}
          onChange={update("description")}
          placeholder="Add context or approval notes."
          error={err.description}
        />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-t border-rule pt-4">
          <p className="text-xs text-ink-muted">
            {String(editing?.status ?? "").toUpperCase() === "REJECTED"
              ? "Saving will move this expense back to Pending."
              : isStaff
              ? "Saved expenses go to the owner for approval."
              : "Approval handling follows backend rules."}
          </p>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
            <Button variant="ghost" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              disabled={submitting}
              iconRight={!submitting && <ArrowRight size={14} />}
            >
              {submitting
                ? "Saving..."
                : editing
                  ? String(editing.status ?? "").toUpperCase() === "REJECTED"
                    ? "Resubmit expense"
                    : "Update expense"
                  : "Save expense"}
            </Button>
          </div>
        </div>
      </form>
      <OCRReceiptModal
        open={ocrOpen}
        onClose={() => setOcrOpen(false)}
        onCreated={() => {
          onCreated?.();
          setOcrOpen(false);
          onClose();
        }}
      />
    </Modal>
  );
}

/* ---------- Expense Detail Modal ---------- */

function ExpenseDetail({ row, currency, currentUserId, onClose, onEdit }) {
  const [receiptPreviewFailed, setReceiptPreviewFailed] = useState(false);
  const receiptUrl = row?.receipt || null;
  const submitterId = row?.user ?? row?.user_details?.id;
  const isSubmitter =
    currentUserId != null &&
    submitterId != null &&
    Number(submitterId) === Number(currentUserId);
  const isPending = String(row?.status ?? "").toUpperCase() === "PENDING";
  const isRejected = String(row?.status ?? "").toUpperCase() === "REJECTED";
  const canEdit = isSubmitter && (isPending || isRejected);
  const receiptIsImage = Boolean(
    receiptUrl &&
      /\.(avif|bmp|gif|jpe?g|png|svg|webp)(?:[?#].*)?$/i.test(receiptUrl),
  );
  const showReceiptPreview = receiptIsImage && !receiptPreviewFailed;

  useEffect(() => {
    setReceiptPreviewFailed(false);
  }, [receiptUrl]);

  return (
    <Modal open onClose={onClose} title="Expense details" size="xl">
      <div className="grid gap-4 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <section
          className="flex flex-col rounded-md border border-rule bg-paper-deep/60 p-3.5"
          aria-labelledby="receipt-panel-title"
        >
          <div>
            <h3
              id="receipt-panel-title"
              className="text-sm font-medium text-ink"
            >
              Receipt
            </h3>
            <p className="mt-0.5 text-xs text-ink-muted">
              {receiptUrl ? "Receipt attached" : "No receipt attached"}
            </p>
          </div>

          {receiptUrl ? (
            <div className="mt-3 flex flex-1 flex-col">
              {showReceiptPreview ? (
                <div className="flex h-48 items-center justify-center overflow-hidden rounded-sm border border-rule bg-paper sm:h-52">
                  <img
                    src={receiptUrl}
                    alt={`Receipt for ${row.title || "expense"}`}
                    className="h-full w-full object-contain"
                    onError={() => setReceiptPreviewFailed(true)}
                  />
                </div>
              ) : (
                <div className="flex h-48 flex-col items-center justify-center rounded-sm border border-dashed border-rule-strong bg-paper px-4 py-5 text-center sm:h-52">
                  <FileText
                    size={26}
                    strokeWidth={1.25}
                    className="text-ink-muted"
                    aria-hidden="true"
                  />
                  <p className="mt-2.5 text-sm font-medium text-ink">
                    Receipt document
                  </p>
                  <p className="mt-1 max-w-52 text-xs leading-snug text-ink-muted">
                    A preview is not available for this file. Open it to view
                    the attachment.
                  </p>
                </div>
              )}

              <Button
                as="a"
                href={receiptUrl}
                target="_blank"
                rel="noreferrer"
                variant="secondary"
                size="sm"
                iconLeft={<FileText size={14} strokeWidth={1.5} />}
                className="mt-2.5 self-start"
              >
                Open receipt
              </Button>
            </div>
          ) : (
            <div className="mt-3 flex h-40 flex-col items-center justify-center rounded-sm border border-dashed border-rule-strong bg-paper px-4 py-5 text-center sm:h-44">
              <FileText
                size={26}
                strokeWidth={1.25}
                className="text-ink-faint"
                aria-hidden="true"
              />
              <p className="mt-2.5 text-sm font-medium text-ink">
                No receipt attached
              </p>
              <p className="mt-1 max-w-52 text-xs leading-snug text-ink-muted">
                This expense does not have a receipt on file.
              </p>
            </div>
          )}
        </section>

        <section className="min-w-0" aria-labelledby="expense-overview-title">
          <div className="flex flex-col gap-3 border-b border-rule pb-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h3
                id="expense-overview-title"
                className="font-display text-xl text-ink break-words"
              >
                {row.title ?? row.description ?? "Untitled expense"}
              </h3>
              <p className="mt-0.5 text-xs text-ink-muted">Expense overview</p>
            </div>
            <div className="shrink-0 sm:text-right">
              <p className="num text-xl font-medium text-ink">
                <Money value={row.amount} currency={row.currency ?? currency} />
              </p>
              <div className="mt-1">
                <StatusPill status={row.status} />
              </div>
            </div>
          </div>

          <dl className="grid grid-cols-1 gap-x-5 gap-y-2.5 py-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-ink-muted">Expense date</dt>
              <dd className="mt-0.5 text-ink">
                {formatDate(row.date ?? row.created_at, "long")}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Category</dt>
              <dd className="mt-0.5 text-ink">
                {categoryLabel(row.category)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Vendor</dt>
              <dd className="mt-0.5 break-words text-ink">
                {row.vendor || "No vendor"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Submitted by</dt>
              <dd className="mt-0.5 flex items-center gap-1.5 text-ink">
                <Avatar name={personName(row)} size={20} />
                <span className="min-w-0 break-words">{personName(row)}</span>
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs text-ink-muted">Created</dt>
              <dd className="mt-0.5 text-ink">
                {formatDate(row.submitted_at ?? row.created_at, "long")}
              </dd>
            </div>
          </dl>

          <div className="rounded-sm border border-rule bg-paper-deep/40 px-3 py-2.5">
            <h4 className="text-xs text-ink-muted">Description</h4>
            <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-snug text-ink-soft">
              {row.description || "No description provided."}
            </p>
          </div>

          {isRejected && (
            <div className="mt-3 rounded-sm border border-saffron-200 bg-saffron-50 px-3 py-2.5">
              <h4 className="text-xs font-medium text-saffron-800">Correction requested</h4>
              <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-snug text-saffron-800">
                {row.rejection_reason?.trim()
                  ? row.rejection_reason
                  : "No reason was provided. Update and resubmit this expense if needed."}
              </p>
            </div>
          )}
        </section>
      </div>

      <div className="mt-4 flex flex-col gap-2.5 border-t border-rule pt-3 sm:flex-row sm:items-center sm:justify-between">
        {!canEdit && (
          <p className="text-[11px] leading-snug text-ink-muted">
            Only pending or rejected expenses submitted by you can be edited.
          </p>
        )}
        <div className="flex flex-col-reverse gap-2 sm:ml-auto sm:flex-row sm:items-center sm:justify-end">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          {canEdit && (
            <Button variant="primary" onClick={onEdit}>
              {isRejected ? "Correct & resubmit" : "Edit"}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}
