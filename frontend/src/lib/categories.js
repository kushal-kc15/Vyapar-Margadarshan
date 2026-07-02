// Shared frontend category definitions.
// Mirrors backend/expenses/categories.py. Keep codes in sync with the backend.

export const EXPENSE_CATEGORIES = [
  { value: 'FOOD', label: 'Food & Dining' },
  { value: 'TRANSPORT', label: 'Transportation' },
  { value: 'TRAVEL', label: 'Travel & Accommodation' },
  { value: 'OFFICE', label: 'Office Supplies' },
  { value: 'UTILITIES', label: 'Utilities' },
  { value: 'SALARY', label: 'Salary & Wages' },
  { value: 'RENT', label: 'Rent' },
  { value: 'MARKETING', label: 'Marketing & Advertising' },
  { value: 'OTHER', label: 'Other' },
];

// Budget-only category that means "any category".
// NOT allowed in expense forms.
export const BUDGET_ONLY_CATEGORIES = [
  { value: 'ALL', label: 'All Categories' },
];

export const BUDGET_CATEGORIES = [
  ...BUDGET_ONLY_CATEGORIES,
  ...EXPENSE_CATEGORIES,
];

export const CATEGORY_LABELS = EXPENSE_CATEGORIES.reduce((acc, item) => {
  acc[item.value] = item.label;
  return acc;
}, {});

// Add budget-only labels to the lookup so display helpers can format "ALL" too.
BUDGET_ONLY_CATEGORIES.forEach((item) => {
  CATEGORY_LABELS[item.value] = item.label;
});

/**
 * Returns a friendly label for a category code.
 * - Known codes: returns the mapped label.
 * - Unknown / null / undefined: returns the code if truthy, else "Other".
 */
export function formatCategoryLabel(code) {
  if (code == null || code === '') return 'Other';
  const label = CATEGORY_LABELS[code];
  if (label) return label;
  return String(code);
}
