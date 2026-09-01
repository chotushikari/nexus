import type { ReactNode } from "react";

export interface KeyValueRow {
  label: string;
  value: ReactNode;
  /** Render the value in the mono/tabular face — ids, principals, tools. */
  mono?: boolean;
  /** Stack label above value instead of side by side (for long values). */
  stacked?: boolean;
}

/**
 * Definition list for identity and record detail. Fixed label column keeps a
 * scannable left edge; values wrap and break so a service-account principal
 * never blows out the layout.
 */
export function KeyValue({
  rows,
  labelWidth = "9.5rem",
  className = "",
}: {
  rows: KeyValueRow[];
  labelWidth?: string;
  className?: string;
}) {
  const visible = rows.filter(
    (row) => row.value !== null && row.value !== undefined && row.value !== "",
  );
  if (visible.length === 0) return null;

  return (
    <dl className={`divide-y divide-paper-3 ${className}`.trim()}>
      {visible.map((row) => (
        <div
          key={row.label}
          className={
            row.stacked
              ? "py-2 first:pt-0 last:pb-0"
              : "flex gap-4 py-2 first:pt-0 last:pb-0"
          }
        >
          <dt
            className="t-label pt-0.5 flex-none"
            style={row.stacked ? undefined : { width: labelWidth }}
          >
            {row.label}
          </dt>
          <dd
            className={`${row.mono ? "t-mono" : "t-body"} text-ink-1 min-w-0 break-words ${
              row.stacked ? "mt-1" : "flex-1"
            }`}
          >
            {row.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
