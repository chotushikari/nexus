/**
 * NEXUS API client.
 *
 * The backend origin is resolved here and NOWHERE else. Every consumer —
 * pages, the top bar, the SSE hook — must import `API_BASE` or `apiUrl()`
 * instead of re-declaring `http://localhost:8000`, otherwise a deployed
 * build silently talks to the developer's laptop.
 *
 * `NEXT_PUBLIC_API_URL` accepts either form:
 *   http://localhost:8000        -> http://localhost:8000/api
 *   http://localhost:8000/api    -> http://localhost:8000/api
 */

const DEFAULT_ORIGIN = "http://localhost:8000";

function resolveApiBase(): string {
  const raw =
    (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) || "";
  const trimmed = raw.trim().replace(/\/+$/, "");
  const origin = trimmed === "" ? DEFAULT_ORIGIN : trimmed.replace(/\/api$/, "");
  return `${origin}/api`;
}

/** Absolute REST base, e.g. `http://localhost:8000/api`. */
export const API_BASE = resolveApiBase();

/** Absolute URL for an API path. Use this for `EventSource` too. */
export const apiUrl = (path: string): string =>
  `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts?.headers ?? {}) },
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`${res.status}: ${err}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Enumerations — mirror nexus_api.schemas.domain exactly.
// ---------------------------------------------------------------------------

/** Honest provenance of a mission plan. Never render `gemini` as the source
 *  unless the backend actually validated a Gemini response. */
export type PlanSource = "gemini" | "deterministic_fallback";

export type TaskStatus =
  | "pending"
  | "ready"
  | "in_progress"
  | "blocked"
  | "completed"
  | "failed"
  | "skipped";

export type RuntimeStatus =
  | "IDLE"
  | "PLANNING"
  | "WORKING"
  | "COMMUNICATING"
  | "WAITING"
  | "APPROVAL_REQUIRED"
  | "BLOCKED"
  | "FAILED"
  | "COMPLETED";

export type MissionStatus =
  | "created"
  | "planning"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "paused"
  | "terminated";

export type ApprovalStatus = "pending" | "granted" | "denied";

export type PolicyOutcome = "ALLOW" | "DENY" | "REQUIRE_APPROVAL";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentCard {
  id: string;
  name: string;
  codename: string;
  role: string;
  departmentId: string;
  tier: number;
  status: string;
  capabilities: string[];
  tools: string[];
  identity: { principal: string; scopes: string[]; riskLevel: string };
  persona: { tagline: string; personality: string[]; inspiration?: string };
  /** Present on the roster contract; may be absent on older payloads. */
  version?: string;
  owner?: string | null;
  dataScopes?: string[];
  policies?: string[];
  unusualOperatorFit?: string | null;
  systemPromptPath?: string | null;
}

/** A node in the mission graph. Execution is entirely data-driven from this. */
export interface MissionTask {
  id: string;
  title: string;
  agentId: string;
  dependsOn: string[];
  tools: string[];
  toolArgs: Record<string, Record<string, unknown>>;
  status: TaskStatus;
  attempts: number;
  maxAttempts: number;
  result: Record<string, unknown>;
  reasoning?: string | null;
  reasoningRuntime?: string | null;
  error?: string | null;
  awaitingApprovalId?: string | null;
  pendingTool?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
}

/** Flat projection of the task graph. Derived — `tasks` is the source of truth. */
export interface MissionPlanStep {
  step: number;
  agentId: string;
  title: string;
  status: string;
  taskId?: string | null;
  dependsOn?: string[];
}

export interface Mission {
  id: string;
  title: string;
  objective: string;
  status: string;
  enterpriseId: string;
  vendorId: string;
  currentStep: number;
  plan: MissionPlanStep[];
  tasks: MissionTask[];
  planSource: PlanSource;
  planModel?: string | null;
  planNotes?: string | null;
  /** Capability -> human-readable reason the system ran in a degraded mode. */
  degraded: Record<string, string>;
  agentStates: Record<string, string>;
  createdAt: string;
  updatedAt?: string;
  completedAt?: string;
  awaitingApprovalId?: string;
  results: Record<string, unknown>;
}

export interface NexusEvent {
  id: string;
  type: string;
  timestamp: string;
  missionId: string;
  agentId?: string;
  targetAgentId?: string;
  summary: string;
  metadata: Record<string, unknown>;
}

export interface Approval {
  id: string;
  missionId: string;
  agentId: string;
  tool: string;
  request: Record<string, unknown>;
  risk: string;
  reason: string;
  policyId: string;
  status: string;
  createdAt: string;
  taskId?: string | null;
  decidedAt?: string;
  decidedBy?: string;
  decision?: string | null;
}

export interface PolicyDecision {
  outcome: PolicyOutcome;
  agentId: string;
  tool: string;
  capability: string;
  reason: string;
  policyId: string;
  metadata: Record<string, unknown>;
}

export interface DepartmentCard {
  id: string;
  name: string;
  description: string;
  managerAgentId?: string | null;
  theme: { primary: string; accent: string };
  location: {
    floor: number;
    x: number;
    y: number;
    width: number;
    height: number;
  };
  agentCount: number;
}

export interface EnterpriseCounts {
  agentsTotal: number;
  /** Deployable agents (roster status `approved`), not agents mid-task. */
  agentsOnline: number;
  agentsBusy: number;
  missionsTotal: number;
  missionsActive: number;
  approvalsPending: number;
  securityAlerts: number;
  departments: number;
}

/** `true` only when the backend proved that code path reachable in-process. */
export interface CapabilityReport {
  gemini: boolean;
  adk: boolean;
  firestore: boolean;
  details: Record<string, string>;
}

export interface EnterpriseSummary {
  id: string;
  name: string;
  environment: string;
  demoMode: boolean;
  defaultVendorId: string;
  defaultVendorName: string;
  departments: DepartmentCard[];
  counts: EnterpriseCounts;
  capabilities: CapabilityReport;
  storeBackend: string;
}

export interface HealthResponse {
  status: string;
  service?: string;
  environment?: string;
  enterpriseId?: string;
  enterpriseName?: string;
  storeBackend?: string;
  capabilities: CapabilityReport;
}

export interface MissionAudit {
  mission: Mission;
  events: NexusEvent[];
}

export interface StartMissionRequest {
  enterpriseId?: string;
  title?: string;
  objective?: string;
  vendorId?: string;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const api = {
  health: () => req<HealthResponse>("/health"),
  seed: () => req<{ status: string; agents: number }>("/demo/seed", { method: "POST" }),
  reset: () => req<Record<string, unknown>>("/demo/reset", { method: "POST" }),

  // Enterprise
  enterprise: () => req<EnterpriseSummary>("/enterprise"),
  departments: () => req<DepartmentCard[]>("/enterprise/departments"),
  counts: () => req<EnterpriseCounts>("/enterprise/counts"),

  // Missions
  listMissions: () => req<Mission[]>("/missions"),
  getMission: (id: string) => req<Mission>(`/missions/${id}`),
  startMission: (body: StartMissionRequest) =>
    req<Mission>("/missions", { method: "POST", body: JSON.stringify(body) }),
  missionEvents: (id: string) => req<NexusEvent[]>(`/missions/${id}/events`),
  missionAudit: (id: string) => req<MissionAudit>(`/missions/${id}/audit`),

  // Events
  listEvents: (missionId?: string) =>
    req<NexusEvent[]>(`/events${missionId ? `?mission_id=${encodeURIComponent(missionId)}` : ""}`),

  // Approvals
  listApprovals: (status?: string) =>
    req<Approval[]>(`/approvals${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  getApproval: (id: string) => req<Approval>(`/approvals/${id}`),
  decideApproval: (id: string, decision: "granted" | "denied", decidedBy = "operator") =>
    req<Mission>(`/approvals/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, decidedBy }),
    }),

  // Agents
  listAgents: () => req<AgentCard[]>("/agents"),
  getAgent: (id: string) => req<AgentCard>(`/agents/${id}`),
  getCapabilities: (id: string) => req<string[]>(`/agents/${id}/capabilities`),
  invokeAgent: (
    id: string,
    body: { tool: string; payload?: Record<string, unknown>; missionId?: string },
  ) =>
    req<Record<string, unknown>>(`/agents/${id}/invoke`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Security
  securityAlerts: () => req<NexusEvent[]>("/security/alerts"),
};
