/**
 * Shared event/mission presentation helpers.
 *
 * Colour comes from the design tokens only (globals.css). Event types map
 * to the semantic state palette — no decoration colours.
 */

export const EVENT_COLOR: Record<string, string> = {
  MISSION_CREATED: "var(--ink-2)",
  PLAN_CREATED: "var(--state-comm)",
  AGENT_STARTED: "var(--state-active)",
  AGENT_COMPLETED: "var(--state-success)",
  AGENT_FAILED: "var(--state-danger)",
  AGENT_PAUSED: "var(--state-warning)",
  AGENT_RESUMED: "var(--state-active)",
  TOOL_STARTED: "var(--ink-1)",
  TOOL_COMPLETED: "var(--ink-2)",
  POLICY_CHECK: "var(--ink-1)",
  POLICY_ALLOWED: "var(--state-success)",
  POLICY_BLOCKED: "var(--state-danger)",
  APPROVAL_REQUESTED: "var(--state-approval)",
  APPROVAL_GRANTED: "var(--state-success)",
  APPROVAL_DENIED: "var(--state-danger)",
  SECURITY_ALERT: "var(--state-danger)",
  AGENT_MESSAGE: "var(--state-comm)",
  CIRCUIT_BREAKER_TRIPPED: "var(--state-approval)",
  MISSION_COMPLETED: "var(--state-success)",
  MISSION_FAILED: "var(--state-danger)",
};

export const MISSION_BADGE_CLASS: Record<string, string> = {
  running: "s-active",
  planning: "s-comm",
  created: "s-neutral",
  awaiting_approval: "s-approval",
  completed: "s-success",
  failed: "s-danger",
  paused: "s-warning",
  terminated: "s-danger",
};

export function eventColor(type: string): string {
  return EVENT_COLOR[type] ?? "var(--ink-3)";
}

export function fmtTime(ts: string): string {
  return new Date(ts).toLocaleTimeString("en-GB", { hour12: false });
}

export function fmtDateTime(ts: string): string {
  return new Date(ts).toLocaleString("en-GB", {
    dateStyle: "short",
    timeStyle: "medium",
  });
}
