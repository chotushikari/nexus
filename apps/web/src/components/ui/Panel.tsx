import type { ReactNode } from "react";

/** Raised paper surface. The only container primitive on the operator pages. */
export function Panel({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article" | "aside";
}) {
  return <Tag className={`panel ${className}`.trim()}>{children}</Tag>;
}

/** Hairline-separated panel header. `meta` sits hard right. */
export function PanelHeader({
  title,
  subtitle,
  meta,
  actions,
  className = "",
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={`flex items-start justify-between gap-4 px-5 py-4 border-b border-paper-3 ${className}`.trim()}
    >
      <div className="min-w-0">
        <div className="t-title text-ink-0">{title}</div>
        {subtitle && <div className="t-small text-ink-2 mt-0.5">{subtitle}</div>}
      </div>
      {(meta || actions) && (
        <div className="flex items-center gap-3 flex-none">
          {meta}
          {actions}
        </div>
      )}
    </header>
  );
}

export function PanelBody({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`p-5 ${className}`.trim()}>{children}</div>;
}

/** Recessed sub-surface for nested detail inside a panel. */
export function Inset({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`inset p-3 ${className}`.trim()}>{children}</div>;
}
