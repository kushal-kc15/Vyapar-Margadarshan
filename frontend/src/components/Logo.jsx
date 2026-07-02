/**
 * Vyapar Margadarshan logo.
 *
 * Shared image mark with an optional wordmark for wider navigation spaces.
 */
export default function Logo({
  size = 32,
  className = '',
  showText,
  withWordmark = false,
  wordmarkSize = 'md',
}) {
  const shouldShowText = showText ?? withWordmark;
  const wordmarkSizes = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
  };

  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span
        className="relative block shrink-0 overflow-hidden"
        style={{ width: size, height: size }}
      >
        <img
          src="/vyapar-logo.png"
          alt="Vyapar Margadarshan"
          className="absolute inset-0 block h-full w-full scale-[1.55] object-contain"
          draggable="false"
        />
      </span>

      {shouldShowText && (
        <span className="min-w-0 leading-none">
          <span className={`block truncate font-display font-medium text-ink ${wordmarkSizes[wordmarkSize] || wordmarkSizes.md}`}>
            Vyapar Margadarshan
          </span>
          <span className="mt-0.5 block truncate text-[0.62rem] font-semibold uppercase tracking-[0.15em] text-ink-muted">
            Expense Management
          </span>
        </span>
      )}
    </span>
  );
}
