/**
 * Vyapar Margadarshan charts.
 *
 * Hand-rolled SVG charts. No recharts/visx/nivo. We don't need 80% of what
 * chart libraries ship with, and what we need we want to look like a real
 * accountant's bar-and-line graph, not a marketing dashboard.
 *
 *   Sparkline  — small inline trend, no axes, no labels, no grid.
 *   BarChart   — vertical bars with a single x-axis label row.
 *   DonutChart — single donut with center label and inline legend.
 *
 * All charts use the cinnabar accent for the highlighted series and
 * paper-deep for the comparison series. Muted ink for axes.
 */

import { useMemo } from 'react';
import { cn } from '../lib/utils.js';
import { formatCurrency, formatCompact } from '../lib/currency.js';

const ACCENT = 'oklch(0.56 0.17 25)';
const ACCENT_SOFT = 'oklch(0.92 0.04 28)';
const INK = 'oklch(0.20 0.012 260)';
const INK_MUTED = 'oklch(0.50 0.008 260)';
const INK_FAINT = 'oklch(0.78 0.008 80)';

export function Sparkline({ values = [], width = 80, height = 24, tone = 'cinnabar', className }) {
  const stroke = tone === 'moss' ? 'oklch(0.50 0.08 150)' : tone === 'saffron' ? 'oklch(0.60 0.12 65)' : ACCENT;
  const path = useMemo(() => {
    if (!values.length) return '';
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const stepX = width / Math.max(values.length - 1, 1);
    return values
      .map((v, i) => {
        const x = i * stepX;
        const y = height - ((v - min) / range) * (height - 2) - 1;
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(' ');
  }, [values, width, height]);

  if (!values.length) return null;

  return (
    <svg width={width} height={height} className={cn('overflow-visible', className)} aria-hidden="true">
      <path d={path} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function BarChart({
  data = [],
  height = 220,
  currency = 'NPR',
  format = 'compact',
  highlightIndex = -1,
  onBarClick,
  className,
}) {
  const max = useMemo(() => Math.max(1, ...data.map((d) => Number(d.value) || 0)), [data]);
  const fmt = (n) => (format === 'compact' ? formatCompact(n, currency) : formatCurrency(n, currency));
  return (
    <div className={cn('w-full min-w-0 overflow-hidden', className)}>
      <div className="relative" style={{ height }}>
        {/* Faint horizontal guides */}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <div
            key={p}
            className="absolute left-0 right-0 h-px bg-rule"
            style={{ top: `${(1 - p) * 100}%` }}
            aria-hidden
          />
        ))}
        <div className="absolute inset-0 flex items-end justify-between gap-1.5 px-1">
          {data.map((d, i) => {
            const h = (Number(d.value) / max) * 100;
            const highlight = i === highlightIndex;
            return (
              <button
                key={d.label ?? i}
                type="button"
                onClick={() => onBarClick?.(d, i)}
                className="group flex-1 h-full flex flex-col justify-end focus:outline-none"
                aria-label={`${d.label}: ${fmt(d.value)}`}
              >
                <div
                  className={cn(
                    'w-full transition-colors rounded-t-xs',
                    highlight ? 'bg-cinnabar-500' : 'bg-rule-strong group-hover:bg-ink-faint'
                  )}
                  style={{ height: `${h}%`, minHeight: 2 }}
                />
                <div className="mt-1.5 -translate-y-7 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  <div className="px-1.5 py-0.5 bg-ink text-paper text-[10px] num rounded-xs whitespace-nowrap mx-auto">
                    {fmt(d.value)}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
      <div className="mt-2 flex justify-between gap-1 text-[10px] uppercase tracking-eyebrow text-ink-muted">
        {data.map((d) => (
          <span key={d.label} className="min-w-0 flex-1 truncate text-center">{d.label}</span>
        ))}
      </div>
    </div>
  );
}

export function DonutChart({
  segments = [], // [{ value, color, label }]
  size = 160,
  thickness = 14,
  centerLabel,
  centerValue,
  className,
}) {
  const total = segments.reduce((s, x) => s + Number(x.value || 0), 0) || 1;
  const radius = size / 2 - thickness;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <div className={cn('flex min-w-0 flex-col items-center gap-4 sm:flex-row sm:gap-5', className)}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0" role="img" aria-label="Distribution chart">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="oklch(0.92 0.005 80)"
          strokeWidth={thickness}
        />
        {segments.map((s, i) => {
          const v = Number(s.value || 0) / total;
          const dash = v * circumference;
          const gap = circumference - dash;
          const seg = (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={s.color}
              strokeWidth={thickness}
              strokeDasharray={`${dash} ${gap}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              strokeLinecap="butt"
            />
          );
          offset += dash;
          return seg;
        })}
        {(centerLabel || centerValue) && (
          <g>
            {centerValue && (
              <text x="50%" y="48%" textAnchor="middle" className="num" fontSize="20" fontWeight="600" fill={INK} fontFamily="Inter, ui-sans-serif, system-ui, sans-serif">
                {centerValue}
              </text>
            )}
            {centerLabel && (
              <text x="50%" y="65%" textAnchor="middle" fontSize="9" letterSpacing="1.2" fill={INK_MUTED} fontFamily="Inter, ui-sans-serif, system-ui, sans-serif">
                {centerLabel.toUpperCase()}
              </text>
            )}
          </g>
        )}
      </svg>
      <ul className="space-y-1.5 text-sm min-w-0">
        {segments.map((s, i) => (
          <li key={i} className="flex items-center gap-2.5">
            <span aria-hidden className="h-2 w-2 rounded-pill" style={{ background: s.color }} />
            <span className="text-ink-soft truncate">{s.label}</span>
            <span className="ml-auto num text-ink-muted">{Math.round((s.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
