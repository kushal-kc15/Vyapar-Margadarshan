import { useEffect, useMemo, useRef, useState } from 'react';
import { FileImage, Loader2, ScanText, AlertTriangle, CheckCircle2 } from 'lucide-react';
import api from '../lib/api.js';
import Button from './Button.jsx';
import { Modal } from './Modal.jsx';
import { Input, Select, Textarea } from './Field.jsx';
import { Money } from './Money.jsx';
import { cn } from '../lib/utils.js';
import { EXPENSE_CATEGORIES } from '../lib/categories.js';
const PROCESSING = ['PENDING', 'PROCESSING'];

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const REVIEWABLE = ['COMPLETED', 'VERIFIED'];

const todayInputValue = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
};

const readableWarning = (warning) =>
  String(warning || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export function OCRReceiptModal({ open, onClose, onCreated }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [receipt, setReceipt] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const cancelledRef = useRef(false);

  useEffect(() => () => {
    cancelledRef.current = true;
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const reset = () => {
    setFile(null);
    setPreview('');
    setReceipt(null);
    setForm({});
    setBusy(false);
    setError('');
    setDragActive(false);
  };

  const close = () => {
    cancelledRef.current = true;
    reset();
    onClose?.();
  };

  const handleFile = (file) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('Upload a receipt image: JPG, PNG, or WebP.');
      return;
    }
    setFile(file);
    setReceipt(null);
    setForm({});
    setPreview(URL.createObjectURL(file));
    setError('');
    cancelledRef.current = false;
  };

  const pickFile = (e) => {
    const next = e.target.files?.[0];
    if (next) handleFile(next);
    e.target.value = '';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) handleFile(dropped);
  };

  const hydrateForm = (data) => {
    const scan = data.scan || {};
    const vendor = data.vendor_name ?? scan.vendor ?? '';
    const amount = data.total_amount ?? scan.amount ?? '';
    const receiptDate = data.receipt_date ?? scan.date ?? '';
    const category = data.category ?? scan.category ?? 'OTHER';
    const description = data.description ?? scan.notes ?? 'Created from AI receipt scan';
    setReceipt(data);
    setForm({
      vendor_name: vendor,
      total_amount: amount,
      receipt_date: receiptDate,
      expense_date: todayInputValue(),
      category,
      description,
      title: vendor ? `Receipt from ${vendor}` : 'Receipt expense',
    });
  };

  const pollReceipt = async (id) => {
    for (let i = 0; i < 45; i += 1) {
      if (cancelledRef.current) return;
      await wait(1500);
      if (cancelledRef.current) return;
      const res = await api.get(`/receipts/${id}/`);
      if (cancelledRef.current) return;
      hydrateForm(res.data);
      if (!PROCESSING.includes(res.data.status)) return res.data;
    }
    throw new Error(
      'AI receipt scanning is still processing. Keep the receipt saved and try scanning again in a moment, or enter the expense manually.'
    );
  };

  const scan = async () => {
    if (!file) {
      setError('Choose a receipt image first.');
      return;
    }
    cancelledRef.current = false;
    setBusy(true);
    setError('');
    const body = new FormData();
    body.append('image', file);

    try {
      const res = await api.post('/receipts/', body, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      hydrateForm(res.data);
      if (PROCESSING.includes(res.data.status)) await pollReceipt(res.data.id);
    } catch (err) {
      const timedOut = err?.code === 'ECONNABORTED' || String(err?.message || '').toLowerCase().includes('timeout');
      setError(
        timedOut ? 'AI receipt scanning took too long. Try a clearer image or enter details manually.' :
        err?.response?.data?.image?.[0] ||
        err?.response?.data?.message ||
        err?.response?.data?.error ||
        err?.message ||
        'AI receipt scanning failed. Try a clearer image or enter the expense manually.'
      );
    } finally {
      setBusy(false);
    }
  };

  const createExpense = async () => {
    if (!receipt) return;
    if (!form.vendor_name || !form.total_amount || !form.receipt_date || !form.expense_date) {
      setError('Vendor, amount, receipt date, and expense date are required before creating an expense.');
      return;
    }

    setBusy(true);
    setError('');

    try {
      const verified = await api.post(`/receipts/${receipt.id}/verify/`, {
        vendor_name: form.vendor_name,
        total_amount: form.total_amount,
        receipt_date: form.receipt_date,
        category: form.category,
        description: form.description,
      });

      await api.post(`/receipts/${verified.data.id}/create_expense/`, {
        title: form.title,
        amount: form.total_amount,
        vendor: form.vendor_name,
        date: form.expense_date,
        category: form.category,
        description: form.description,
      });

      onCreated?.();
      close();
    } catch (err) {
      setError(
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        'Could not create expense from this receipt.'
      );
    } finally {
      setBusy(false);
    }
  };

  const isProcessing = receipt && PROCESSING.includes(receipt.status);
  const isFailed = receipt?.status === 'FAILED';
  const isReviewable = receipt && REVIEWABLE.includes(receipt.status);
  const canCreate = Boolean(
    isReviewable &&
    form.vendor_name &&
    form.total_amount &&
    form.receipt_date &&
    form.expense_date &&
    !busy
  );
  const warnings = Array.isArray(receipt?.ocr_validation_warnings)
    ? receipt.ocr_validation_warnings
    : [];
  const lineItems = Array.isArray(receipt?.line_items) ? receipt.line_items : [];

  const confidenceSummary = useMemo(() => {
    if (!receipt) return [];
    return [
      ['Vendor', receipt.vendor_confidence],
      ['Amount', receipt.amount_confidence],
      ['Receipt date', receipt.date_confidence],
    ].filter(([, value]) => value !== null && value !== undefined && value !== '');
  }, [receipt]);

  return (
    <Modal
      open={open}
      onClose={close}
      title="Scan receipt with AI"
      description="Upload a receipt image, review the extracted fields, then create the expense."
      size="lg"
      panelClassName="!max-h-[88vh]"
      contentClassName="!py-4"
    >
      <div className="space-y-4">
        <div>
          <label
            className={cn(
              'flex min-h-32 cursor-pointer flex-col items-center justify-center border border-dashed px-4 py-3.5 text-center transition-colors sm:min-h-36 sm:px-5 sm:py-4',
              dragActive ? 'border-cinnabar-500 bg-cinnabar-50' : 'border-rule-strong bg-paper-deep',
              preview && 'bg-paper'
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {preview ? (
              <img src={preview} alt="Receipt preview" className="max-h-36 w-full object-contain sm:max-h-40" />
            ) : (
              <>
                <FileImage size={22} className="text-ink-muted" strokeWidth={1.5} />
                <p className="mt-2.5 text-sm font-medium text-ink">Choose receipt image</p>
                <p className="mt-0.5 text-xs text-ink-muted">JPG, PNG, or WebP</p>
                <p className="mt-1 text-xs text-ink-faint">or drag and drop</p>
              </>
            )}
            <input type="file" accept="image/*" className="hidden" onChange={pickFile} />
          </label>

          {error && (
            <div className="mt-3 flex gap-2 border border-cinnabar-200 bg-cinnabar-50 px-3 py-2 text-sm text-cinnabar-700">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {receipt?.error_message && isFailed && (
            <div className="mt-3 flex gap-2 border border-cinnabar-200 bg-cinnabar-50 px-3 py-2 text-sm text-cinnabar-700">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <span>{receipt.error_message}</span>
            </div>
          )}
        </div>

        <div className="rounded-md border border-rule bg-paper-deep/35 p-4">
          {!receipt ? (
            <div className="flex flex-col gap-3">
              <div>
                <h3 className="font-display text-lg text-ink">Less typing, same control.</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">
                  AI scanning fills the vendor, amount, date, category, and notes. Review before anything enters the book.
                </p>
              </div>
              <Button
                variant="primary"
                onClick={scan}
                disabled={busy || !file}
                iconRight={busy ? <Loader2 size={15} className="animate-spin" /> : <ScanText size={15} />}
                className="w-full sm:w-auto sm:self-start"
              >
                {busy ? 'Scanning receipt with AI...' : 'Scan receipt with AI'}
              </Button>
            </div>
          ) : isProcessing ? (
            <div className="flex items-start gap-3 border border-rule bg-paper-deep p-4">
              <Loader2 size={18} className="mt-0.5 animate-spin text-ink-muted" />
              <div>
                <p className="text-sm font-medium text-ink">Scanning receipt with AI</p>
                <p className="mt-1 text-sm text-ink-muted">
                  Scanning receipt with AI... this may take up to two minutes.
                </p>
              </div>
            </div>
          ) : isFailed ? (
            <div className="flex flex-col justify-between gap-5">
              <div className="flex items-start gap-3 border border-cinnabar-200 bg-cinnabar-50 px-3 py-2">
                <AlertTriangle size={16} className="mt-0.5 text-cinnabar-700" />
                <div>
                  <p className="text-sm font-medium text-cinnabar-800">Receipt scan failed</p>
                  <p className="text-xs text-cinnabar-700">
                    {receipt.error_message ||
                      'AI receipt scanning failed. Try a clearer image or enter the expense manually.'}
                  </p>
                </div>
              </div>
              <div className="flex flex-col-reverse gap-2 border-t border-rule pt-4 sm:flex-row sm:flex-wrap sm:justify-end">
                <Button variant="ghost" onClick={close}>
                  Cancel
                </Button>
                <Button variant="secondary" onClick={reset}>
                  Choose another file
                </Button>
                <Button
                  variant="primary"
                  onClick={scan}
                  disabled={busy || !file}
                  iconRight={busy && <Loader2 size={15} className="animate-spin" />}
                >
                  {busy ? 'Scanning receipt with AI...' : 'Try scan again'}
                </Button>
              </div>
            </div>
          ) : isReviewable ? (
            <div className="space-y-3">
              <div className="flex items-start gap-3 border border-moss-200 bg-moss-50 px-3 py-2">
                <CheckCircle2 size={16} className="mt-0.5 text-moss-700" />
                <div>
                  <p className="text-sm font-medium text-moss-800">Receipt scanned</p>
                  <p className="text-xs text-moss-700">Review the fields before creating the expense.</p>
                </div>
              </div>

              {confidenceSummary.length > 0 && (
                <div className="text-xs text-ink-muted">
                  Confidence:{' '}
                  {confidenceSummary.map(([label, value]) => `${label} ${value}%`).join(' - ')}
                </div>
              )}

              {warnings.length > 0 && (
                <div className="flex gap-2 border border-saffron-200 bg-saffron-50 px-3 py-2 text-sm text-saffron-700">
                  <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                  <div>
                    <p className="font-medium">Review suggested</p>
                    <ul className="mt-1 list-disc pl-4 text-xs">
                      {warnings.map((warning) => (
                        <li key={warning}>{readableWarning(warning)}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              <Input
                label="Title"
                value={form.title ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              />

              <div className="grid grid-cols-1 gap-3">
                <Input
                  label="Vendor"
                  value={form.vendor_name ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, vendor_name: e.target.value }))}
                  required
                />
                <Input
                  type="number"
                  step="0.01"
                  label="Amount"
                  value={form.total_amount ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, total_amount: e.target.value }))}
                  required
                />
              </div>

              <div className="grid grid-cols-1 gap-3">
                <Input
                  type="date"
                  label="Expense date"
                  value={form.expense_date ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, expense_date: e.target.value }))}
                  required
                />
                <Select
                  label="Category"
                  value={form.category ?? 'OTHER'}
                  onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                >
                  {EXPENSE_CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </Select>
              </div>

              <Textarea
                label="Notes"
                rows={2}
                value={form.description ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />

              <p className="text-xs text-ink-muted">
                Receipt date detected: {form.receipt_date || 'Not detected'} · Extracted amount:{' '}
                <Money value={form.total_amount || 0} size="sm" />
              </p>

              {lineItems.length > 0 && (
                <div className="border-t border-rule pt-3">
                  <p className="text-xs font-medium text-ink">Line items</p>
                  <ul className="mt-2 max-h-32 divide-y divide-rule overflow-y-auto text-xs">
                    {lineItems.slice(0, 6).map((item, index) => (
                      <li
                        key={`${item.description ?? 'item'}-${index}`}
                        className="flex items-center justify-between gap-3 py-1.5"
                      >
                        <span className="min-w-0 truncate text-ink-muted">
                          {item.description ?? `Item ${index + 1}`}
                        </span>
                        <span className="num shrink-0 text-ink">
                          <Money value={item.amount ?? item.unit_price ?? 0} size="sm" />
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {!canCreate && (
                <p className="text-xs text-ink-muted">
                  Vendor, amount, receipt date, and expense date are required before creating an expense.
                </p>
              )}

              <div className="flex flex-col-reverse gap-2 border-t border-rule pt-4 sm:flex-row sm:justify-end">
                <Button variant="ghost" onClick={close}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={createExpense} disabled={!canCreate}>
                  {busy ? 'Creating...' : 'Create expense'}
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-3 border border-rule bg-paper-deep p-4">
              <AlertTriangle size={18} className="mt-0.5 text-ink-muted" />
              <div>
                <p className="text-sm font-medium text-ink">Receipt status unavailable</p>
                <p className="mt-1 text-sm text-ink-muted">
                  Choose another image or try scanning again.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
