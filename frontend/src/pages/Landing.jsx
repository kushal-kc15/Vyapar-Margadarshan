import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Check,
  Camera,
  CornerDownRight,
  Plus,
  TrendingDown,
  TrendingUp,
  Sparkles,
  Shield,
  Zap,
  Clock,
  FileText,
  Users,
  BarChart3,
  Receipt,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';
import Logo from '../components/Logo.jsx';

/* ------------------------------------------------------------------ */
/*  Vyapar Margadarshan · Landing                                     */
/*  Refined, editorial, modern — less AI, more craft.                */
/* ------------------------------------------------------------------ */

const HERO_ENTRIES = [
  { label: 'Stock from M.K. Suppliers', amount: '−₨ 18,400', tone: 'cinnabar' },
  { label: 'Three customers, morning', amount: '+₨ 12,750', tone: 'moss' },
  { label: 'Tea and biscuits', amount: '−₨ 220', tone: 'cinnabar' },
  { label: 'Auto-rickshaw to bank', amount: '−₨ 350', tone: 'cinnabar' },
  { label: 'Customer S. Shrestha', amount: '+₨ 4,500', tone: 'moss' },
  { label: 'Pashmina lot, Asan', amount: '−₨ 7,200', tone: 'cinnabar' },
];

const DAY_BOOK_ENTRIES = [
  { who: 'Sunita R.', label: 'Office stationery', amount: '−₨ 1,840', tone: 'cinnabar' },
  { who: 'Hari K.', label: 'Client lunch · Bota Momo', amount: '−₨ 2,150', tone: 'cinnabar' },
  { who: 'Annapurna', label: 'Office rent, May', amount: '−₨ 24,000', tone: 'cinnabar' },
  { who: 'Invoice #41', label: 'Kankai Hydropower, retainer', amount: '+₨ 85,000', tone: 'moss' },
];

const APPROVAL_QUEUE = [
  { who: 'Prakash Tamang', role: 'Field · Birtamode', what: 'Diesel for delivery van', amount: '₨ 3,200', when: '2h ago' },
  { who: 'Mira Adhikari', role: 'Marketing · KTM', what: 'Meta ads · April', amount: '₨ 18,500', when: '5h ago' },
  { who: 'R. Subedi', role: 'Operations · Pokhara', what: 'Hotel · client visit', amount: '₨ 6,400', when: '1d ago' },
];

const BUDGETS = [
  { name: 'Marketing', spent: 78, total: 100, unit: 'k' },
  { name: 'Office rent', spent: 100, total: 100, unit: 'k' },
  { name: 'Travel', spent: 42, total: 80, unit: 'k' },
  { name: 'Equipment', spent: 19, total: 60, unit: 'k' },
];

/* ----- atoms ------------------------------------------------------ */

function Eyebrow({ children, className = '' }) {
  return <p className={`text-[11px] font-medium tracking-[0.08em] uppercase text-ink-muted ${className}`}>{children}</p>;
}

function EdgeRule({ tone = 'cinnabar', className = '' }) {
  const colour = tone === 'cinnabar' ? '#c2412a' : tone === 'moss' ? '#5a7a4a' : '#1c1a17';
  return (
    <svg
      aria-hidden
      viewBox="0 0 200 6"
      preserveAspectRatio="none"
      className={`block h-[2px] w-full ${className}`}
    >
      <line x1="0" y1="3" x2="200" y2="3" stroke={colour} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/* ----- Nav -------------------------------------------------------- */

function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-rule/60 bg-paper/80 backdrop-blur-xl supports-[backdrop-filter]:bg-paper/70">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-3.5 flex items-center justify-between gap-4">
        <Link to="/" aria-label="Vyapar Margadarshan home" className="flex shrink-0 items-center">
          <Logo size={32} className="sm:hidden" />
          <Logo size={36} showText wordmarkSize="sm" className="hidden sm:inline-flex" />
        </Link>

        <nav className="hidden md:flex items-center gap-8 text-sm text-ink-soft">
          <a href="#features" className="relative hover:text-ink transition-colors after:absolute after:-bottom-1 after:left-0 after:h-[1.5px] after:w-0 after:bg-cinnabar-500 after:transition-all hover:after:w-full">
            Features
          </a>
          <a href="#pricing" className="relative hover:text-ink transition-colors after:absolute after:-bottom-1 after:left-0 after:h-[1.5px] after:w-0 after:bg-cinnabar-500 after:transition-all hover:after:w-full">
            Pricing
          </a>
          <a href="#testimonials" className="relative hover:text-ink transition-colors after:absolute after:-bottom-1 after:left-0 after:h-[1.5px] after:w-0 after:bg-cinnabar-500 after:transition-all hover:after:w-full">
            Reviews
          </a>
          <a href="#faq" className="relative hover:text-ink transition-colors after:absolute after:-bottom-1 after:left-0 after:h-[1.5px] after:w-0 after:bg-cinnabar-500 after:transition-all hover:after:w-full">
            FAQ
          </a>
        </nav>

        <nav className="flex items-center gap-2">
          <Link
            to="/login"
            className="hidden sm:inline-flex h-9 px-4 items-center text-sm text-ink-soft hover:text-ink transition-colors"
          >
            Sign in
          </Link>
          <Link
            to="/register"
            className="inline-flex h-9 items-center gap-1.5 px-5 rounded-full bg-cinnabar-500 text-paper text-sm font-medium shadow-sm shadow-cinnabar-500/20 hover:bg-cinnabar-600 hover:shadow-cinnabar-500/30 transition-all"
          >
            Get started
            <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
          </Link>
        </nav>
      </div>
    </header>
  );
}

/* ----- Hero ------------------------------------------------------- */

function Hero() {
  const today = new Date();
  const dateLabel = today.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const issueLabel = `Vol. 2 · No. ${String(today.getDate()).padStart(2, '0')}`;

  return (
    <section className="relative border-b border-rule overflow-hidden bg-gradient-to-b from-paper-deep/30 to-paper">
      <div className="absolute -top-40 -right-40 h-[600px] w-[600px] rounded-full bg-cinnabar-500/5 blur-3xl pointer-events-none" />
      <div className="absolute -bottom-60 -left-60 h-[600px] w-[600px] rounded-full bg-moss-500/5 blur-3xl pointer-events-none" />

      <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-10 sm:py-12 lg:py-10 xl:py-12 relative">
        <div className="grid grid-cols-12 gap-x-10 gap-y-10 lg:items-center">

          {/* Copy column */}
          <div className="col-span-12 lg:col-span-6">
            <div className="inline-flex items-center gap-3 mb-5 text-xs text-ink-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-moss-500 animate-pulse" />
              <span className="text-cinnabar-600 font-medium tracking-wider">{issueLabel}</span>
              <span className="text-ink-faint">·</span>
              <span className="text-ink-soft">{dateLabel}</span>
            </div>

            <h1 className="font-display font-medium text-[2.45rem] sm:text-[3.15rem] lg:text-[3.7rem] xl:text-[4rem] leading-[1.03] tracking-[-0.035em] text-ink text-balance">
              Manage Business Expenses with{' '}
              <span className="relative inline-block">
                <span className="relative z-10">Clarity</span>
                <svg
                  aria-hidden
                  viewBox="0 0 220 10"
                  preserveAspectRatio="none"
                  className="absolute left-0 right-0 -bottom-1 w-full h-[7px] text-cinnabar-500"
                >
                  <path
                    d="M2 5 C 40 2, 80 8, 120 4 S 180 3, 218 5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                  />
                </svg>
              </span>
            </h1>

            <p className="mt-4 max-w-[48ch] text-base sm:text-lg text-ink-soft leading-[1.6] text-pretty">
              Vyapar Margadarshan helps small businesses record expenses, organize receipts,
              monitor budgets, and review spending through a simple web-based system.
            </p>

            <div className="mt-7 flex flex-wrap items-center gap-3 sm:gap-4">
              <Link
                to="/register"
                className="group inline-flex h-11 sm:h-12 items-center gap-2 px-6 sm:px-7 rounded-full bg-cinnabar-500 text-paper text-sm sm:text-base font-medium shadow-md shadow-cinnabar-500/25 hover:bg-cinnabar-600 hover:shadow-cinnabar-500/40 transition-all"
              >
                Get Started
                <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                to="/login"
                className="inline-flex h-11 sm:h-12 items-center gap-1.5 px-2 text-sm sm:text-base text-ink-soft border-b-2 border-transparent hover:border-cinnabar-500/40 hover:text-ink transition-all"
              >
                View Demo
              </Link>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-muted">
              <span className="flex items-center gap-1.5">
                <span className="h-1 w-1 rounded-full bg-moss-500" />
                Final year project
              </span>
              <span className="text-ink-faint">·</span>
              <span>Web-based system</span>
              <span className="text-ink-faint">·</span>
              <span>NPR · INR · USD · EUR</span>
            </div>
          </div>

          {/* Ledger card — elevated */}
          <div className="col-span-12 lg:col-span-5 lg:col-start-8 self-center pt-0 lg:-translate-y-2">
            <div className="relative">
              {/* Accent rule */}
              <div className="absolute -top-px left-0 right-0 hidden lg:block">
                <EdgeRule tone="cinnabar" />
              </div>

              <div className="bg-paper border border-rule shadow-[0_8px_40px_-12px_rgba(0,0,0,0.12)] rounded-xl p-5 relative overflow-hidden hover:shadow-[0_12px_48px_-16px_rgba(0,0,0,0.16)] transition-shadow duration-300">
                {/* Decorative corner */}
                <div className="absolute -top-8 -right-8 h-20 w-20 rounded-full bg-cinnabar-500/5" />

                {/* Header */}
                <div className="flex items-center justify-between gap-3 border-b border-rule/70 pb-3 mb-1">
                  <div>
                    <Eyebrow>Day book</Eyebrow>
                    <p className="font-display text-base mt-0.5 text-ink">Mero Pasal, Kathmandu</p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-moss-50 text-moss-700 text-[11px] font-medium border border-moss-200/30">
                    <span className="h-1.5 w-1.5 rounded-full bg-moss-500" aria-hidden />
                    in balance
                  </span>
                </div>

                {/* Entries */}
                <ul className="text-sm divide-y divide-rule/50">
                  {HERO_ENTRIES.map((e, i) => (
                    <li
                      key={i}
                      className="flex items-center justify-between gap-3 py-2 hover:bg-paper-deep/30 px-1 -mx-1 rounded transition-colors"
                    >
                      <span className="text-ink truncate">{e.label}</span>
                      <span
                        className={`num shrink-0 tabular-nums font-medium ${e.tone === 'cinnabar' ? 'text-cinnabar-600' : 'text-moss-600'}`}
                      >
                        {e.amount}
                      </span>
                    </li>
                  ))}
                </ul>

                {/* Total */}
                <div className="mt-3 -mx-5">
                  <div className="px-5">
                    <EdgeRule tone="cinnabar" />
                  </div>
                </div>

                <div className="pt-3 flex items-baseline justify-between">
                  <Eyebrow>Net today</Eyebrow>
                  <span className="num text-lg text-ink font-semibold tracking-tight">−₨ 8,920</span>
                </div>

                <p className="mt-3 text-[11px] text-ink-faint text-right italic border-t border-rule/30 pt-2.5">
                  A working page from a real ledger.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ----- Social proof strip ----------------------------------------- */

function ProofStrip() {
  return (
    <div className="border-b border-rule bg-paper-deep/40">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-3.5 flex flex-wrap items-center justify-center sm:justify-between gap-3 text-xs text-ink-muted">
        <span className="flex items-center gap-2">
          <span className="flex -space-x-1.5">
            {['#c2412a', '#5a7a4a', '#8b6b4b', '#2d4a5a'].map((c, i) => (
              <span
                key={i}
                className="h-6 w-6 rounded-full border-2 border-paper"
                style={{ backgroundColor: c }}
              />
            ))}
          </span>
          <span>Designed for small business expense management.</span>
        </span>
        <div className="flex items-center gap-5">
          <span className="flex items-center gap-1.5">
            <span className="text-moss-600 font-semibold">Expenses</span> organized in one place
          </span>
          <span className="hidden sm:inline text-ink-faint">·</span>
          <span className="hidden sm:flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-ink-faint" />
            Records · Receipts · Budgets
          </span>
        </div>
      </div>
    </div>
  );
}

/* ----- Instruments ------------------------------------------------ */

function Instruments() {
  return (
    <section id="features" className="border-b border-rule py-16 sm:py-24 bg-paper">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        {/* Section header */}
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-14">
          <div>
            <Eyebrow className="mb-3 text-cinnabar-600">System functions</Eyebrow>
            <h2 className="font-display font-medium text-3xl sm:text-4xl lg:text-5xl leading-[1.05] tracking-[-0.03em] text-ink text-balance max-w-[14ch]">
              Core{' '}
              <span className="text-ink-muted">Features</span>
            </h2>
          </div>
          <p className="text-ink-soft text-base leading-relaxed max-w-[40ch] lg:text-right">
            The system includes the main tools needed to manage daily business
            expenses and financial records.
          </p>
        </div>

        <div className="grid grid-cols-12 gap-5">
          {/* 1 — Day book */}
          <article className="col-span-12 md:col-span-6 bg-paper border border-rule rounded-xl p-5 sm:p-6 shadow-xs hover:shadow-sm transition-shadow duration-200">
            <div className="flex items-start justify-between gap-3 pb-4 mb-1">
              <div>
                <Eyebrow>Record</Eyebrow>
                <h3 className="font-display text-xl mt-1 text-ink">Expense Tracking</h3>
                <p className="text-sm text-ink-soft mt-0.5">Record expenses with complete details.</p>
              </div>
              <div className="h-9 w-9 rounded-lg bg-paper-deep border border-rule flex items-center justify-center text-ink-faint shrink-0">
                <CornerDownRight size={15} aria-hidden />
              </div>
            </div>
            <div className="border-t border-rule/60 pt-3">
              <ul className="divide-y divide-rule/50 text-sm">
                {DAY_BOOK_ENTRIES.map((e, i) => (
                  <li key={i} className="py-3 flex items-start gap-3 hover:bg-paper-deep/20 px-1 -mx-1 rounded transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="text-ink">{e.label}</p>
                      <p className="text-[11px] text-ink-muted mt-0.5">{e.who}</p>
                    </div>
                    <span
                      className={`num shrink-0 tabular-nums text-sm font-medium ${e.tone === 'cinnabar' ? 'text-cinnabar-600' : 'text-moss-600'}`}
                    >
                      {e.amount}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="pt-3 mt-1 border-t border-rule/60 flex items-baseline justify-between">
                <Eyebrow>Net today</Eyebrow>
                <span className="num text-ink font-semibold tabular-nums">+₨ 57,010</span>
              </div>
            </div>
          </article>

          {/* 2 — Receipts / OCR */}
          <article className="col-span-12 md:col-span-6 bg-paper border border-rule rounded-xl p-5 sm:p-6 shadow-xs hover:shadow-sm transition-shadow duration-200">
            <div className="flex items-start justify-between gap-3 pb-4 mb-1">
              <div>
                <Eyebrow>Capture</Eyebrow>
                <h3 className="font-display text-xl mt-1 text-ink">Receipt Management</h3>
                <p className="text-sm text-ink-soft mt-0.5">Keep receipts linked with expense records.</p>
              </div>
              <div className="h-9 w-9 rounded-lg bg-paper-deep border border-rule flex items-center justify-center text-ink-faint shrink-0">
                <Camera size={15} aria-hidden />
              </div>
            </div>

            <div className="border-t border-rule/60 pt-4 grid grid-cols-12 gap-4">
              {/* Receipt mockup */}
              <div className="col-span-5">
                <div className="bg-paper-deep/60 border border-rule rounded-lg p-3 text-[10px] leading-snug font-mono text-ink-soft relative shadow-inner">
                  <p className="text-center text-ink font-semibold text-[11px] tracking-wide">BOTA MOMO HOUSE</p>
                  <p className="text-center text-ink-faint text-[9px]">Jhamsikhel, Lalitpur</p>
                  <p className="text-ink-faint mt-1.5">14/05/2026 · 13:42</p>
                  <div className="my-1.5 border-t border-dashed border-rule-strong" />
                  <div className="space-y-0.5">
                    <div className="flex justify-between"><span>2× Momo</span><span>320</span></div>
                    <div className="flex justify-between"><span>1× Chowmein</span><span>180</span></div>
                    <div className="flex justify-between"><span>3× Coke</span><span>240</span></div>
                    <div className="flex justify-between"><span>Service</span><span>74</span></div>
                  </div>
                  <div className="my-1.5 border-t border-dashed border-rule-strong" />
                  <div className="flex justify-between text-ink font-semibold">
                    <span>TOTAL</span><span>₨ 814</span>
                  </div>
                  <span
                    className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-cinnabar-500 text-paper text-[10px] font-bold flex items-center justify-center shadow-sm"
                    aria-hidden
                  >
                    ✓
                  </span>
                </div>
              </div>

              {/* Extracted fields */}
              <div className="col-span-7 space-y-2.5 text-sm">
                {[
                  ['Vendor', 'Bota Momo House'],
                  ['Date', '14 May 2026'],
                  ['Category', 'Food & Dining'],
                  ['Amount', '₨ 814'],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    className="flex items-baseline justify-between border-b border-rule/40 pb-1.5 last:border-0 last:pb-0"
                  >
                    <span className="text-ink-muted text-[10px] uppercase tracking-wider">{label}</span>
                    <span className={label === 'Amount' ? 'num text-ink font-semibold' : 'text-ink text-xs'}>
                      {value}
                    </span>
                  </div>
                ))}
                <button
                  type="button"
                  className="mt-2 w-full h-8 inline-flex items-center justify-center gap-1.5 text-xs font-medium rounded-lg bg-cinnabar-500 text-paper hover:bg-cinnabar-600 transition-colors shadow-sm shadow-cinnabar-500/20"
                >
                  <Plus size={11} aria-hidden />
                  File in the book
                </button>
              </div>
            </div>
          </article>

          {/* 3 — Approvals */}
          <article className="col-span-12 md:col-span-7 bg-paper border border-rule rounded-xl p-5 sm:p-6 shadow-xs hover:shadow-sm transition-shadow duration-200">
            <div className="flex items-start justify-between gap-3 pb-4 mb-1">
              <div>
                <Eyebrow>Review</Eyebrow>
                <h3 className="font-display text-xl mt-1 text-ink">Approval Workflow</h3>
                <p className="text-sm text-ink-soft mt-0.5">Review, approve, or reject submitted expenses.</p>
              </div>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-cinnabar-50 text-cinnabar-700 text-[11px] font-medium border border-cinnabar-200/30">
                <span className="h-1.5 w-1.5 rounded-full bg-cinnabar-500 animate-pulse" aria-hidden />
                3 waiting
              </span>
            </div>
            <div className="border-t border-rule/60 pt-2">
              <ul className="divide-y divide-rule/50">
                {APPROVAL_QUEUE.map((a, i) => (
                  <li key={i} className="py-3 flex items-center gap-3 hover:bg-paper-deep/20 px-1 -mx-1 rounded transition-colors">
                    <div
                      aria-hidden
                      className="h-9 w-9 rounded-full bg-paper-deep text-ink-soft text-xs font-semibold flex items-center justify-center border border-rule shrink-0"
                    >
                      {a.who
                        .split(' ')
                        .map((p) => p[0])
                        .join('')
                        .slice(0, 2)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-ink font-medium truncate">{a.who}</p>
                      <p className="text-xs text-ink-muted truncate">{a.what}</p>
                    </div>
                    <span className="num text-sm text-ink shrink-0 hidden sm:inline tabular-nums font-medium">
                      {a.amount}
                    </span>
                    <span className="text-xs text-ink-faint shrink-0 hidden md:inline">{a.when}</span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        type="button"
                        className="h-7 px-3.5 text-xs font-medium rounded-lg bg-ink text-paper hover:bg-ink-soft transition-colors"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="h-7 px-3 text-xs font-medium rounded-lg border border-rule-strong text-ink-soft hover:text-ink hover:border-ink-muted transition-colors"
                      >
                        Decline
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </article>

          {/* 4 — Budgets */}
          <article className="col-span-12 md:col-span-5 bg-paper border border-rule rounded-xl p-5 sm:p-6 shadow-xs hover:shadow-sm transition-shadow duration-200">
            <div className="flex items-start justify-between gap-3 pb-4 mb-1">
              <div>
                <Eyebrow>Track</Eyebrow>
                <h3 className="font-display text-xl mt-1 text-ink">Budget Monitoring</h3>
                <p className="text-sm text-ink-soft mt-0.5">Compare actual spending with planned limits.</p>
              </div>
              <div className="h-9 w-9 rounded-lg bg-paper-deep border border-rule flex items-center justify-center text-ink-faint shrink-0">
                <BarChart3 size={15} aria-hidden />
              </div>
            </div>
            <div className="border-t border-rule/60 pt-4">
              <ul className="space-y-4">
                {BUDGETS.map((b) => {
                  const pct = Math.min(100, Math.round((b.spent / b.total) * 100));
                  const warn = pct >= 85;
                  return (
                    <li key={b.name}>
                      <div className="flex items-baseline justify-between text-sm mb-2">
                        <span className="text-ink font-medium">{b.name}</span>
                        <span className="num tabular-nums text-xs">
                          <span className={warn ? 'text-cinnabar-600 font-semibold' : 'text-ink-soft'}>
                            {pct}%
                          </span>
                          <span className="text-ink-faint ml-1">of ₨{b.total}{b.unit}</span>
                        </span>
                      </div>
                      <div className="h-1.5 bg-rule/60 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${warn ? 'bg-cinnabar-500' : 'bg-ink/60'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
              <p className="mt-5 text-xs text-ink-muted leading-relaxed border-t border-rule/60 pt-4 flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-cinnabar-500" aria-hidden />
                Budget indicators show when spending approaches the planned limit.
              </p>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}

/* ----- Pricing ---------------------------------------------------- */

const PLANS = [
  {
    name: 'Starter',
    price: 'Free',
    note: 'For a single workspace during the beta.',
    features: ['Staff submissions', 'Receipt attachment', 'Owner approval queue', 'Basic report preview'],
    icon: Sparkles,
  },
  {
    name: 'Business',
    price: 'Team',
    note: 'For small teams that handle expenses every week.',
    features: ['Receipt OCR', 'Budget tracking', 'CSV exports', 'Workspace roles'],
    featured: true,
    icon: Users,
  },
  {
    name: 'Institution',
    price: 'Custom',
    note: 'For larger organizations and setup support.',
    features: ['Team management', 'Advanced reports', 'Budget monitoring', 'Dedicated setup'],
    icon: Shield,
  },
];

function Pricing() {
  return (
    <section id="pricing" className="border-b border-rule bg-paper-deep/20 py-16 sm:py-20">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5 mb-12">
          <div>
            <Eyebrow className="mb-3 text-cinnabar-600">Pricing</Eyebrow>
            <h2 className="font-display font-medium text-3xl sm:text-4xl leading-[1.05] tracking-[-0.025em] text-ink">
              Plans for different business needs.
            </h2>
          </div>
          <p className="text-ink-soft leading-relaxed max-w-[42ch] lg:text-right text-sm">
            Choose a plan based on the size and requirements of the organization.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {PLANS.map((plan) => {
            const Icon = plan.icon;
            return (
              <article
                key={plan.name}
                className={`relative border rounded-xl p-6 flex flex-col transition-all duration-200 hover:-translate-y-1 ${
                  plan.featured
                    ? 'bg-ink text-paper border-ink shadow-[0_8px_40px_-12px_rgba(0,0,0,0.3)]'
                    : 'bg-paper border-rule shadow-xs hover:shadow-sm'
                }`}
              >
                {plan.featured && (
                  <span className="absolute -top-2.5 left-6 inline-block px-3 py-0.5 rounded-full bg-cinnabar-500 text-paper text-[10px] font-semibold tracking-wider uppercase">
                    Most popular
                  </span>
                )}
                <div className="flex items-start justify-between gap-3 pb-4 border-b border-rule/20">
                  <div>
                    <div
                      className={`inline-flex h-10 w-10 items-center justify-center rounded-xl mb-3 ${
                        plan.featured ? 'bg-paper/10' : 'bg-paper-deep'
                      }`}
                    >
                      <Icon size={18} className={plan.featured ? 'text-paper/80' : 'text-ink-soft'} />
                    </div>
                    <h3 className={`font-display text-xl ${plan.featured ? 'text-paper' : 'text-ink'}`}>
                      {plan.name}
                    </h3>
                    <p className={`mt-1 text-xs ${plan.featured ? 'text-paper/60' : 'text-ink-muted'}`}>
                      {plan.note}
                    </p>
                  </div>
                  <span
                    className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${
                      plan.featured
                        ? 'bg-paper/10 text-paper'
                        : 'bg-paper-deep text-ink-soft'
                    }`}
                  >
                    {plan.price}
                  </span>
                </div>

                <ul className="mt-5 space-y-3 flex-1">
                  {plan.features.map((feature) => (
                    <li
                      key={feature}
                      className={`flex items-center gap-2.5 text-sm ${plan.featured ? 'text-paper/85' : 'text-ink-soft'}`}
                    >
                      <Check size={13} className={`shrink-0 ${plan.featured ? 'text-cinnabar-300' : 'text-cinnabar-500'}`} aria-hidden />
                      {feature}
                    </li>
                  ))}
                </ul>

                <Link
                  to={plan.name === 'Institution' ? '/login' : '/register'}
                  className={`mt-7 inline-flex h-10 w-full items-center justify-center rounded-lg border text-sm font-medium transition-all ${
                    plan.featured
                      ? 'bg-paper text-ink border-paper hover:bg-paper-deep'
                      : 'bg-cinnabar-500 text-paper border-cinnabar-500 hover:bg-cinnabar-600 shadow-sm shadow-cinnabar-500/20'
                  }`}
                >
                  {plan.name === 'Institution' ? 'Discuss setup' : 'Create account'}
                </Link>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ----- Testimonials ----------------------------------------------- */

const TESTIMONIALS = [
  {
    quote: 'The approval queue made pending staff expenses clear without opening a spreadsheet.',
    name: 'Suman Adhikari',
    role: 'Store manager',
    initial: 'SA',
  },
  {
    quote: 'Receipts stayed attached to the expense, so monthly review was much less confusing.',
    name: 'Anita Sharma',
    role: 'Small business owner',
    initial: 'AS',
  },
  {
    quote: 'The budget view helped us explain spending clearly during the project review.',
    name: 'Bishal Karki',
    role: 'Project reviewer',
    initial: 'BK',
  },
];

function Testimonials() {
  return (
    <section id="testimonials" className="border-b border-rule bg-paper py-16 sm:py-20">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5 mb-12">
          <div>
            <Eyebrow className="mb-3 text-cinnabar-600">Testimonials</Eyebrow>
            <h2 className="font-display font-medium text-3xl sm:text-4xl leading-[1.05] tracking-[-0.025em] text-ink">
              Practical feedback from users.
            </h2>
          </div>
          <p className="text-ink-soft text-sm leading-relaxed max-w-[40ch] lg:text-right">
            Feedback on expense submission, review, budgets, and reports.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {TESTIMONIALS.map((item, idx) => (
            <figure
              key={item.name}
              className="bg-paper border border-rule rounded-xl p-6 flex flex-col justify-between transition-all duration-200 hover:shadow-sm hover:-translate-y-0.5"
            >
              <blockquote className="font-display text-[1.1rem] leading-[1.5] text-ink text-balance">
                        “{item.quote}”
              </blockquote>
              <figcaption className="mt-6 pt-4 border-t border-rule/60 flex items-center gap-3">
                <div className="h-9 w-9 rounded-full bg-paper-deep border border-rule text-xs font-semibold text-ink-soft flex items-center justify-center shrink-0">
                  {item.initial}
                </div>
                <div>
                  <p className="text-sm font-medium text-ink">{item.name}</p>
                  <p className="text-xs text-ink-muted">{item.role}</p>
                </div>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ----- FAQ -------------------------------------------------------- */

const FAQS = [
  ['Can staff submit expenses?', 'Yes. Staff can file an expense, attach the receipt, and follow whether it is pending, approved, or returned.'],
  ['Can owners approve or return expenses?', 'Yes. Owners review staff expenses from a queue and can return an expense with a reason.'],
  ['Does receipt scanning work?', 'Yes. Receipt OCR can fill common fields — vendor, date, amount, and category — before the expense is submitted.'],
  ['Can reports be exported?', 'Yes. Approved expenses can be reviewed by period and exported as CSV.'],
  ['Is it only for large companies?', 'No. The workflow is designed for small teams first, then scales to a larger workspace.'],
];

function FAQ() {
  return (
    <section id="faq" className="border-b border-rule bg-paper-deep/20 py-16 sm:py-20">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        <div className="grid grid-cols-12 gap-x-10 gap-y-10">
          <div className="col-span-12 lg:col-span-4">
            <Eyebrow className="mb-3 text-cinnabar-600">FAQ</Eyebrow>
            <h2 className="font-display font-medium text-3xl sm:text-4xl leading-[1.05] tracking-[-0.025em] text-ink">
              Common questions about the system.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-ink-muted max-w-[28ch]">
              Practical answers about submissions, approvals, scanning, and reports.
            </p>
          </div>

          <div className="col-span-12 lg:col-span-7 lg:col-start-6">
            <div className="space-y-1">
              {FAQS.map(([question, answer], idx) => (
                <details
                  key={question}
                  className="group border-b border-rule/60 last:border-0"
                >
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-5 py-4 text-ink select-none hover:text-ink-soft transition-colors">
                    <span className="font-medium text-sm sm:text-base">{question}</span>
                    <span className="text-cinnabar-500 text-lg leading-none transition-transform duration-300 group-open:rotate-45 shrink-0 font-light">
                      +
                    </span>
                  </summary>
                  <p className="pb-4 max-w-[60ch] text-sm leading-relaxed text-ink-soft">{answer}</p>
                </details>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ----- Closer ----------------------------------------------------- */

function Closer() {
  return (
    <section className="bg-paper border-b border-rule">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-16 sm:py-20">
        <div className="relative overflow-hidden rounded-2xl border border-rule bg-gradient-to-br from-paper-deep/30 to-paper px-8 sm:px-12 py-10 sm:py-12 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-8">
          {/* Decorative */}
          <div className="absolute -top-20 -right-20 h-60 w-60 rounded-full bg-cinnabar-500/5 blur-2xl pointer-events-none" />
          <div className="absolute -bottom-20 -left-20 h-60 w-60 rounded-full bg-moss-500/5 blur-2xl pointer-events-none" />

          <div className="relative">
            <Eyebrow className="mb-3 text-cinnabar-600">Project objective</Eyebrow>
            <p className="font-display text-2xl sm:text-3xl lg:text-4xl leading-[1.15] tracking-[-0.025em] text-ink max-w-[22ch]">
              A Practical Expense Management System
              <span className="text-ink-muted"> for small businesses.</span>
            </p>
          </div>
          <div className="relative flex flex-col sm:items-end gap-3 shrink-0">
            <Link
              to="/register"
              className="group inline-flex h-12 items-center gap-2 px-7 rounded-full bg-cinnabar-500 text-paper text-base font-medium shadow-md shadow-cinnabar-500/25 hover:bg-cinnabar-600 hover:shadow-cinnabar-500/40 transition-all"
            >
              Get Started
              <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
            </Link>
            <p className="text-xs text-ink-muted">Manage records and review spending from one place.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ----- Footer ----------------------------------------------------- */

function Footer() {
  return (
    <footer className="bg-paper">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs text-ink-muted">
        <div className="flex items-center gap-6">
          <span>© {new Date().getFullYear()} Vyapar Margadarshan</span>
          <a href="#" className="hover:text-ink transition-colors">Privacy</a>
          <a href="#" className="hover:text-ink transition-colors">Terms</a>
        </div>
        <span className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-moss-500" />
          Final year project for small business expense management.
        </span>
      </div>
    </footer>
  );
}

/* ----- Page ------------------------------------------------------- */

export default function Landing() {
  return (
    <div className="landing-light min-h-screen bg-paper text-ink antialiased">
      <Nav />
      <main>
        <Hero />
        <ProofStrip />
        <Instruments />
        <Pricing />
        <Testimonials />
        <FAQ />
        <Closer />
      </main>
      <Footer />
    </div>
  );
}
