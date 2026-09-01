"use client";

/**
 * PixelLoader + rotating status phrases.
 *
 * The phrases are tied to a phase (what the system is actually doing), and
 * the rotation is the only "fun" the palette allows — pixel-art blocks in
 * sage/oak, never neon. Phases map 1:1 to real runtime states, so the
 * humour is a lens on real work, not a fake progress bar.
 */

import { useEffect, useState } from "react";
import { OAK, PAPER, SAGE } from "@/lib/pixel/palette";

export type Phase =
  | "booting"
  | "understanding"
  | "clarify"
  | "planning"
  | "executing"
  | "approval"
  | "idle";

const PHRASES: Record<Phase, string[]> = {
  booting: [
    "Raising the blinds…",
    "Waking the workforce…",
    "Unlocking floor 2…",
    "Watering the desk plants…",
  ],
  understanding: [
    "Reading between your lines…",
    "Parsing intent at 60Hz…",
    "Understanding the assignment — for real…",
    "Separating the what from the why…",
  ],
  clarify: [
    "A good chief of staff asks first…",
    "Refusing to guess, professionally…",
    "Three questions now beat thirty later…",
  ],
  planning: [
    "Reticulating deliverables…",
    "Negotiating with the calendar…",
    "Teaching the interns to read…",
    "Sharpening pencils with lasers…",
    "Convincing the copier it's not the enemy…",
    "Drawing the org chart in crayon, then in ink…",
    "Caffeinating the workflow…",
  ],
  executing: [
    "The floor is alive…",
    "Keyboards clattering…",
    "Moving pixels, moving business…",
    "Shipping before the coffee cools…",
    "Synergy, but make it real…",
  ],
  approval: [
    "Someone wants permission to spend money…",
    "An executive decision awaits…",
    "Policy says: ask the human…",
  ],
  idle: [],
};

/** Rotating phrase for a phase — stable order, 3s cadence, gentle fade. */
export function useRotatingPhrase(phase: Phase): string | null {
  const [index, setIndex] = useState(0);
  const phrases = PHRASES[phase] ?? [];
  useEffect(() => setIndex(0), [phase]);
  useEffect(() => {
    if (phrases.length < 2) return;
    const id = setInterval(
      () => setIndex((i) => (i + 1) % phrases.length),
      3200,
    );
    return () => clearInterval(id);
  }, [phase, phrases.length]);
  if (phrases.length === 0) return null;
  return phrases[index % phrases.length];
}

/** 5-block pixel loader — marches like a progress bar made of floors. */
export function PixelLoader({ size = 5 }: { size?: number }) {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setFrame((f) => (f + 1) % 10), 160);
    return () => clearInterval(id);
  }, []);
  const colors = [SAGE[3], SAGE[2], SAGE[1], OAK[1], OAK[0]];
  return (
    <div className="flex items-end gap-1" aria-hidden>
      {colors.map((c, i) => {
        const lit = (frame + i) % 5;
        return (
          <span
            key={i}
            className="inline-block"
            style={{
              width: size,
              height: size * (1 + lit * 0.35),
              background: lit === 4 ? PAPER[4] : c,
              imageRendering: "pixelated",
              transition: "height 120ms steps(3)",
            }}
          />
        );
      })}
    </div>
  );
}

/** Phrase ticker + loader, inline. Use inside any panel that loads. */
export function StatusTicker({
  phase,
  label,
  compact = false,
}: {
  phase: Phase;
  label?: string;
  compact?: boolean;
}) {
  const phrase = useRotatingPhrase(phase);
  if (!phrase && !label) return null;
  return (
    <div
      className="flex items-center gap-2.5"
      style={{ padding: compact ? "4px 0" : "8px 0" }}
    >
      <PixelLoader size={compact ? 4 : 5} />
      {label && (
        <span className="t-label" style={{ color: "var(--ink-2)" }}>
          {label}
        </span>
      )}
      {phrase && (
        <span
          key={phrase}
          className="fade-in t-small italic"
          style={{ color: "var(--ink-2)" }}
        >
          {phrase}
        </span>
      )}
    </div>
  );
}
