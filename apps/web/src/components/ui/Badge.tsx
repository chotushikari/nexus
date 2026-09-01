import type { ReactNode } from "react";
import { type Tone, toneClass } from "@/lib/format";

/**
 * A state badge. Colour never travels alone — the label is always rendered,
 * so the badge stays legible in greyscale and to screen readers.
 */
export function Badge({
  tone = "neutral",
  children,
  dot = true,
  title,
  className = "",
}: {
  tone?: Tone;
  children: ReactNode;
  dot?: boolean;
  title?: string;
  className?: string;
}) {
  return (
    <span className={`badge ${toneClass(tone)} ${className}`.trim()} title={title}>
      {dot && <span className="badge-dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

/**
 * A label/value badge pair, e.g. `RISK · HIGH`. The prefix carries the
 * meaning of the colour in words.
 */
export function LabelledBadge({
  label,
  value,
  tone = "neutral",
  title,
}: {
  label: string;
  value: ReactNode;
  tone?: Tone;
  title?: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5" title={title}>
      <span className="t-label">{label}</span>
      <Badge tone={tone}>{value}</Badge>
    </span>
  );
}
