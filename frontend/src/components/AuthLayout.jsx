import { Check } from 'lucide-react';
import { Link } from 'react-router-dom';
import Logo from './Logo.jsx';
import { cn } from '../lib/utils.js';

const FEATURES = [
  'AI receipt scanning',
  'Approval workflow',
  'Budget and report insights',
];

export default function AuthLayout({ children, headerAction, cardClassName = '' }) {
  return (
    <div className="grid min-h-screen min-w-0 overflow-x-hidden bg-paper lg:grid-cols-[minmax(20rem,0.85fr)_minmax(0,1.15fr)]">
      <aside className="hidden border-r border-rule bg-paper-deep/70 p-10 lg:flex lg:flex-col xl:p-14">
        <Link to="/" className="w-fit">
          <Logo size={52} showText wordmarkSize="lg" />
        </Link>

        <div className="my-auto max-w-md py-12">
          <h2 className="font-display text-3xl font-medium leading-tight text-ink">
            Expense management that keeps the whole workspace aligned.
          </h2>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-ink-soft">
            Track expenses, approvals, budgets, and reports from one workspace.
          </p>
          <ul className="mt-8 space-y-3">
            {FEATURES.map((feature) => (
              <li key={feature} className="flex items-center gap-3 text-sm text-ink-soft">
                <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-forest-50 text-forest-700">
                  <Check size={13} strokeWidth={2} aria-hidden="true" />
                </span>
                {feature}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-ink-muted">Vyapar Margadarshan · Expense Management</p>
      </aside>

      <main className="flex min-w-0 flex-col px-4 py-5 sm:px-8 sm:py-7 lg:px-12">
        <div className="flex min-h-10 items-center justify-between gap-3">
          <Link to="/" className="min-w-0 lg:hidden">
            <Logo size={34} showText wordmarkSize="sm" />
          </Link>
          <div className="ml-auto shrink-0 text-right">{headerAction}</div>
        </div>

        <div className="flex flex-1 items-center justify-center py-6 sm:py-8">
          <section
            className={cn(
              'w-full max-w-md rounded-lg border border-rule bg-paper p-5 shadow-sm sm:p-7',
              cardClassName,
            )}
          >
            {children}
          </section>
        </div>
      </main>
    </div>
  );
}
