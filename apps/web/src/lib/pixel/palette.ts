/**
 * Pixel-office palette.
 *
 * Single source of truth for the canvas renderer. Mirrors the CSS custom
 * properties in app/globals.css — keep the two in sync when changing either.
 * No dark theme, no violet/indigo, no neon: colour encodes runtime state
 * only, everything else is paper / ink / sage / oak.
 */

export const PAPER = {
  0: "#fbf8f1",
  1: "#f5f0e4",
  2: "#ebe4d4",
  3: "#ded5c0",
  4: "#c4b89e",
} as const;

export const INK = {
  0: "#2b2620",
  1: "#4a4238",
  2: "#6e6355",
  3: "#928676",
} as const;

export const SAGE = {
  0: "#a8bca5",
  1: "#8fa68e",
  2: "#758c74",
  3: "#5c7159",
} as const;

export const OAK = {
  0: "#c69a6d",
  1: "#a97c50",
  2: "#86603c",
  3: "#634528",
} as const;

/** Runtime-state colours, mapped 1:1 to RuntimeStatus on the backend. */
export const STATE: Record<string, string> = {
  IDLE: "#6e6355",
  PLANNING: "#4a6f8a",
  WORKING: "#3f6e63",
  COMMUNICATING: "#4a6f8a",
  WAITING: "#b07d2b",
  TOOL_CALL: "#3f6e63",
  APPROVAL_REQUIRED: "#c8860d",
  BLOCKED: "#a63d2f",
  PAUSED: "#b07d2b",
  FAILED: "#a63d2f",
  COMPLETED: "#4a7c4e",
  OFFLINE: "#928676",
};

/** Human labels for the states above (colour never travels alone — §34). */
export const STATE_LABEL: Record<string, string> = {
  IDLE: "Idle",
  PLANNING: "Planning",
  WORKING: "Working",
  COMMUNICATING: "Messaging",
  WAITING: "Waiting",
  TOOL_CALL: "Tool call",
  APPROVAL_REQUIRED: "Approval",
  BLOCKED: "Blocked",
  PAUSED: "Paused",
  FAILED: "Failed",
  COMPLETED: "Done",
  OFFLINE: "Offline",
};

/** Skin tones — muted, warm, six-step. */
export const SKIN = [
  "#f0c8a0",
  "#e0b088",
  "#c89868",
  "#a87848",
  "#8a5c38",
  "#6e4628",
] as const;

/** Hair colours — natural range plus one grey for variety. */
export const HAIR = [
  "#2b2118",
  "#4a3220",
  "#6e4a28",
  "#8a6838",
  "#a8865c",
  "#8d8579",
  "#3d3630",
] as const;

/** Shirt colours — workwear range, deliberately desaturated. */
export const SHIRT = [
  "#5c7159", // sage
  "#4a6f8a", // steel blue
  "#8a6a4a", // tan
  "#6e6355", // warm grey
  "#7a5c50", // clay
  "#566873", // slate
  "#756a7d", // muted plum-grey (not purple)
  "#4a7c4e", // green
] as const;

/** Deterministic 32-bit hash → stable per-agent visual traits. */
export function hash32(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export interface AgentTraits {
  skin: string;
  hair: string;
  shirt: string;
  hairStyle: 0 | 1 | 2 | 3;
}

/** Stable traits for an agent id — same agent always looks the same. */
export function agentTraits(id: string): AgentTraits {
  const h = hash32(id);
  return {
    skin: SKIN[h % SKIN.length],
    hair: HAIR[(h >> 3) % HAIR.length],
    shirt: SHIRT[(h >> 6) % SHIRT.length],
    hairStyle: ((h >> 9) % 4) as 0 | 1 | 2 | 3,
  };
}
