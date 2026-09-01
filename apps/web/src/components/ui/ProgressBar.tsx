import { type Tone, toneVar } from "@/lib/format";

/**
 * Determinate progress. Always accompanied by a textual ratio by the caller —
 * the bar alone is decoration.
 */
export function ProgressBar({
  value,
  max,
  tone = "active",
  label,
}: {
  value: number;
  max: number;
  tone?: Tone;
  label?: string;
}) {
  const safeMax = max > 0 ? max : 1;
  const pct = Math.max(0, Math.min(100, Math.round((value / safeMax) * 100)));
  return (
    <div
      className="h-1.5 w-full rounded-full bg-paper-2 overflow-hidden"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label ?? "Progress"}
    >
      <div
        className="h-full rounded-full transition-[width] duration-300"
        style={{ width: `${pct}%`, background: toneVar(tone) }}
      />
    </div>
  );
}
