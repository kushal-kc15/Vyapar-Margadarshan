export default function RiskScoreBar({ score }) {
  const pct = Math.min(100, Math.max(0, score));
  const tone = pct >= 66 ? "bg-cinnabar-500" : pct >= 31 ? "bg-saffron-500" : "bg-forest-500";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-sm bg-paper-deep px-1.5 py-0.5">
      <span className="relative h-1.5 w-10 overflow-hidden rounded-full bg-rule">
        <span className={`absolute inset-y-0 left-0 rounded-full ${tone}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="num text-[11px] text-ink-soft">{score}/100</span>
    </span>
  );
}
