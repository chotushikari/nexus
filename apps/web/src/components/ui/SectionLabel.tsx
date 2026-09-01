import type { ReactNode } from "react";

/**
 * Wide-tracked small-caps section heading — the structural rhythm of every
 * operator page. Optional count sits alongside, never inside, the label.
 */
export function SectionLabel({
  children,
  count,
  aside,
  className = "",
}: {
  children: ReactNode;
  count?: number;
  aside?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-2 ${className}`.trim()}>
      <h3 className="t-label">{children}</h3>
      {typeof count === "number" && (
        <span className="t-mono text-ink-3">{count}</span>
      )}
      {aside && <div className="ml-auto">{aside}</div>}
    </div>
  );
}

/** Page-level heading block. One per page. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-6 mb-6">
      <div>
        <h1 className="t-display text-ink-0">{title}</h1>
        {subtitle && <p className="t-body text-ink-2 mt-1.5 max-w-2xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-none">{actions}</div>}
    </div>
  );
}
