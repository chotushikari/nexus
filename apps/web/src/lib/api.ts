const BASE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) ||
  "http://localhost:8000/api";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts?.headers ?? {}) },
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`${res.status}: ${err}`);
  }
  return res.json() as Promise<T>;
}

// ---------- Types ----------
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
  persona: { tagline: string; personality: string[] };
}

export interface Mission {
  id: string;
  title: string;
  objective: string;
  status: string;
  enterpriseId: string;
  vendorId: string;
  currentStep: number;
  plan: { step: number; agentId: string; title: string; status: string }[];
  agentStates: Record<string, string>;
  createdAt: string;
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
  decidedAt?: string;
  decidedBy?: string;
}

// ---------- API calls ----------
export const api = {
  health: () => req<{ status: string }>("/health"),
  seed: () => req<{ status: string; agents: number }>("/demo/seed", { method: "POST" }),

  // Missions
  listMissions: () => req<Mission[]>("/missions"),
  getMission: (id: string) => req<Mission>(`/missions/${id}`),
  startMission: (body: {
    enterpriseId: string;
    title: string;
    objective: string;
    vendorId: string;
  }) => req<Mission>("/missions", { method: "POST", body: JSON.stringify(body) }),
  missionAudit: (id: string) => req<{ mission: Mission; events: NexusEvent[] }>(`/missions/${id}/audit`),

  // Events
  listEvents: (missionId?: string) =>
    req<NexusEvent[]>(`/events${missionId ? `?mission_id=${missionId}` : ""}`),

  // Approvals
  listApprovals: (status?: string) =>
    req<Approval[]>(`/approvals${status ? `?status=${status}` : ""}`),
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
};
