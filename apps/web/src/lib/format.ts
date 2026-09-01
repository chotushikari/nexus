/**
 * Shared presentation helpers.
 *
 * Everything that used to be copy-pasted across the operator pages lives
 * here: the runtime-state -> design-token mapping, timestamp formatting and
 * label humanisation. Pages must never re-declare `EVENT_COLORS` or `fmt()`.
 *
 * There are no colour literals in this file. A `Tone` names a semantic slot
 * from globals.css (`--state-*` / `.s-*`); the stylesheet owns the hue.
 */

// ---------------------------------------------------------------------------
// Semantic tones
// ---------------------------------------------------------------------------

export type Tone =
  | "neutral"
  | "active"
  | "comm"
  | "success"
  | "warning"
  | "approval"
  | "danger";

/** Badge class for a tone, e.g. `s-danger`. */
export const toneClass = (tone: Tone): string => `s-${tone}`;

/** `color: var(--state-*)` for a tone — for hairlines, spines and dots. */
export const toneVar = (tone: Tone): string => `var(--state-${tone})`;

// ---------------------------------------------------------------------------
// Event types -> tone. Mirrors nexus_api.schemas.domain.EventType.
// ---------------------------------------------------------------------------

const EVENT_TONE: Record<string, Tone> = {
  MISSION_CREATED: "neutral",
  PLAN_CREATED: "active",
  AGENT_STARTED: "active",
  AGENT_WAITING: "warning",
  AGENT_COMPLETED: "success",
  AGENT_FAILED: "danger",
  AGENT_PAUSED: "warning",
  AGENT_RESUMED: "active",
  TOOL_STARTED: "active",
  TOOL_COMPLETED: "success",
  TOOL_FAILED: "danger",
  AGENT_MESSAGE: "comm",
  MEMORY_READ: "comm",
  MEMORY_WRITE: "comm",
  POLICY_CHECK: "neutral",
  POLICY_ALLOWED: "success",
  POLICY_BLOCKED: "danger",
  APPROVAL_REQUESTED: "approval",
  APPROVAL_GRANTED: "success",
  APPROVAL_DENIED: "danger",
  SECURITY_ALERT: "danger",
  MISSION_PAUSED: "warning",
  MISSION_RESUMED: "active",
  MISSION_COMPLETED: "success",
  MISSION_FAILED: "danger",
  CIRCUIT_BREAKER_TRIPPED: "danger",
};

export const eventTone = (type: string): Tone => EVENT_TONE[type] ?? "neutral";

/** Event types that belong on the Security Center. */
export const SECURITY_EVENT_TYPES = [
  "SECURITY_ALERT",
  "POLICY_BLOCKED",
  "CIRCUIT_BREAKER_TRIPPED",
] as const;

/** Event types that represent a memory access. */
export const MEMORY_EVENT_TYPES = ["MEMORY_READ", "MEMORY_WRITE"] as const;

/** Event types that represent a policy evaluation. */
export const POLICY_EVENT_TYPES = [
  "POLICY_CHECK",
  "POLICY_ALLOWED",
  "POLICY_BLOCKED",
] as const;

// ---------------------------------------------------------------------------
// Domain status -> tone
// ---------------------------------------------------------------------------

const MISSION_TONE: Record<string, Tone> = {
  created: "neutral",
  planning: "active",
  running: "active",
  awaiting_approval: "approval",
  completed: "success",
  failed: "danger",
  paused: "warning",
  terminated: "danger",
};

export const missionTone = (status: string): Tone =>
  MISSION_TONE[status] ?? "neutral";

const TASK_TONE: Record<string, Tone> = {
  pending: "neutral",
  ready: "comm",
  in_progress: "active",
  blocked: "warning",
  completed: "success",
  failed: "danger",
  skipped: "neutral",
};

export const taskTone = (status: string): Tone => TASK_TONE[status] ?? "neutral";

const RUNTIME_TONE: Record<string, Tone> = {
  IDLE: "neutral",
  PLANNING: "active",
  WORKING: "active",
  COMMUNICATING: "comm",
  WAITING: "warning",
  APPROVAL_REQUIRED: "approval",
  BLOCKED: "danger",
  FAILED: "danger",
  COMPLETED: "success",
};

export const runtimeTone = (status: string): Tone =>
  RUNTIME_TONE[status] ?? "neutral";

const APPROVAL_TONE: Record<string, Tone> = {
  pending: "approval",
  granted: "success",
  denied: "danger",
};

export const approvalTone = (status: string): Tone =>
  APPROVAL_TONE[status] ?? "neutral";

const RISK_TONE: Record<string, Tone> = {
  none: "neutral",
  low: "success",
  medium: "warning",
  moderate: "warning",
  high: "danger",
  critical: "danger",
};

/** Tone for a risk level. Unknown values fall back to neutral rather than
 *  inventing a severity the backend never claimed. */
export const riskTone = (risk: string | null | undefined): Tone =>
  RISK_TONE[(risk ?? "").trim().toLowerCase()] ?? "neutral";

const ROSTER_STATUS_TONE: Record<string, Tone> = {
  approved: "success",
  experimental: "warning",
  retired: "neutral",
  registered_only: "neutral",
};

export const rosterStatusTone = (status: string): Tone =>
  ROSTER_STATUS_TONE[status] ?? "neutral";

const POLICY_OUTCOME_TONE: Record<string, Tone> = {
  ALLOW: "success",
  DENY: "danger",
  REQUIRE_APPROVAL: "approval",
};

export const policyOutcomeTone = (outcome: string): Tone =>
  POLICY_OUTCOME_TONE[outcome] ?? "neutral";

// ---------------------------------------------------------------------------
// Tiers
// ---------------------------------------------------------------------------

export const TIER_LABELS: Record<number, string> = {
  1: "Core",
  2: "Extended",
  3: "Registry",
};

export const TIER_DESCRIPTIONS: Record<number, string> = {
  1: "Executes missions end to end with live tool access.",
  2: "Specialists invoked on demand by a core agent.",
  3: "Registered and governed, not yet wired to live tools.",
};

export const tierLabel = (tier: number): string =>
  TIER_LABELS[tier] ?? `Tier ${tier}`;

// ---------------------------------------------------------------------------
// Plan provenance — must never overstate what ran.
// ---------------------------------------------------------------------------

export const planSourceLabel = (source: string | null | undefined): string =>
  source === "gemini" ? "Gemini" : "Deterministic fallback";

export const planSourceTone = (source: string | null | undefined): Tone =>
  source === "gemini" ? "active" : "neutral";

// ---------------------------------------------------------------------------
// Timestamps
// ---------------------------------------------------------------------------

function toDate(ts: string | null | undefined): Date | null {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** `14:32:07` — for dense timelines. */
export function fmtTime(ts: string | null | undefined): string {
  const d = toDate(ts);
  if (!d) return "—";
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/** `12 Mar 2026, 14:32` — for record headers. */
export function fmtDateTime(ts: string | null | undefined): string {
  const d = toDate(ts);
  if (!d) return "—";
  return d.toLocaleString([], {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** `4m ago` — relative, coarse on purpose. */
export function fmtRelative(ts: string | null | undefined): string {
  const d = toDate(ts);
  if (!d) return "—";
  const seconds = Math.round((Date.now() - d.getTime()) / 1000);
  if (seconds < 0) return "just now";
  if (seconds < 45) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/** Elapsed time between two ISO stamps, e.g. `1.4s`, `2m 05s`. */
export function fmtElapsed(
  from: string | null | undefined,
  to: string | null | undefined,
): string | null {
  const a = toDate(from);
  const b = toDate(to);
  if (!a || !b) return null;
  const ms = b.getTime() - a.getTime();
  if (ms < 0) return null;
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

// ---------------------------------------------------------------------------
// Text
// ---------------------------------------------------------------------------

/** `POLICY_BLOCKED` -> `Policy blocked`; `awaiting_approval` -> `Awaiting approval`. */
export function humanize(value: string | null | undefined): string {
  if (!value) return "";
  const spaced = value.replace(/[_\-.]+/g, " ").trim().toLowerCase();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Initials for an avatar tile, max two letters. */
export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/** Stable 2-space JSON, with a readable fallback for cyclic input. */
export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? "null";
  } catch {
    return String(value);
  }
}

export const hasEntries = (value: object | null | undefined): boolean =>
  !!value && Object.keys(value).length > 0;

/** Read a string field out of loosely-typed event metadata. */
export function metaString(
  metadata: Record<string, unknown> | undefined,
  ...keys: string[]
): string | null {
  if (!metadata) return null;
  for (const key of keys) {
    const raw = metadata[key];
    if (typeof raw === "string" && raw.trim() !== "") return raw;
    if (typeof raw === "number" || typeof raw === "boolean") return String(raw);
  }
  return null;
}

/** Read a string-list field out of loosely-typed event metadata. */
export function metaList(
  metadata: Record<string, unknown> | undefined,
  ...keys: string[]
): string[] {
  if (!metadata) return [];
  for (const key of keys) {
    const raw = metadata[key];
    if (Array.isArray(raw)) return raw.map((item) => String(item));
  }
  return [];
}

/** Last path segment of a document path, for compact display. */
export function basename(path: string | null | undefined): string {
  if (!path) return "";
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? path;
}
