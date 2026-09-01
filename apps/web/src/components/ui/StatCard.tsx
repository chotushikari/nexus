import type { ReactNode } from "react";
import { type Tone, toneVar } from "@/lib/format";

/**
 * A single figure with a wide-tracked label. Deliberately plain: the number
 * carries the emphasis, not a coloured tile.
 */
export function StatCard({
  label,
  value,
  hint,
  tone,
  emphasis = false,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  /** Tints only the figure, and only when the figure is meaningful. */
  tone?: Tone;
  /** Draw a left rule to pull the eye — use for at most one card in a row. */
  emphasis?: boolean;
}) {
  return (
    <div
      className={`panel px-4 py-3 ${emphasis ? "border-l-2" : ""}`}
      style={emphasis && tone ? { borderLeftColor: toneVar(tone) } : undefined}
    >
      <div className="t-label">{label}</div>
      <div
        className="mt-1 text-[22px] font-semibold leading-none tabular-nums"
        style={tone ? { color: toneVar(tone) } : { color: "var(--ink-0)" }}
      >
        {value}
      </div>
      {hint && <div className="t-small text-ink-2 mt-1.5">{hint}</div>}
    </div>
  );
}

/** Compact inline metric for toolbars and headers. */
export function InlineStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: ReactNode;
  tone?: Tone;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span
        className="t-mono font-semibold"
        style={tone ? { color: toneVar(tone) } : { color: "var(--ink-0)" }}
      >
        {value}
      </span>
      <span className="t-label">{label}</span>
    </span>
  );
}
