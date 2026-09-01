"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, AgentCard, Approval, Mission, NexusEvent } from "@/lib/api";
import { useEventStream } from "@/lib/useEventStream";
import { Office3D } from "@/components/Office3D";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Department {
  id: string;
  name: string;
  icon: string;
  description: string;
  color: string;
  agents: string[];
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  IDLE: "Idle",
  WORKING: "Working",
  COMMUNICATING: "Messaging",
  WAITING: "Waiting",
  APPROVAL_REQUIRED: "Needs Approval",
  BLOCKED: "Blocked",
  COMPLETED: "Done",
};

const STATUS_COLOR: Record<string, string> = {
  IDLE: "#475569",
  WORKING: "#06b6d4",
  COMMUNICATING: "#8b5cf6",
  WAITING: "#f59e0b",
  APPROVAL_REQUIRED: "#f59e0b",
  BLOCKED: "#ef4444",
  COMPLETED: "#10b981",
};

const EVENT_COLORS: Record<string, string> = {
  MISSION_CREATED: "#6366f1",
  PLAN_CREATED: "#8b5cf6",
  AGENT_STARTED: "#06b6d4",
  AGENT_COMPLETED: "#10b981",
  AGENT_PAUSED: "#f59e0b",
  AGENT_RESUMED: "#06b6d4",
  TOOL_STARTED: "#64748b",
  TOOL_COMPLETED: "#475569",
  POLICY_CHECK: "#7c3aed",
  POLICY_ALLOWED: "#059669",
  POLICY_BLOCKED: "#dc2626",
  APPROVAL_REQUESTED: "#f59e0b",
  APPROVAL_GRANTED: "#10b981",
  APPROVAL_DENIED: "#ef4444",
  SECURITY_ALERT: "#ef4444",
  CIRCUIT_BREAKER_TRIPPED: "#7c3aed",
  MISSION_COMPLETED: "#10b981",
  MISSION_FAILED: "#ef4444",
  AGENT_MESSAGE: "#94a3b8",
};

function fmt(ts: string) {
  return new Date(ts).toLocaleTimeString("en-IN", { hour12: false });
}

// ─── Agent Status Ring ────────────────────────────────────────────────────────

function StatusRing({ status }: { status: string }) {
  const color = STATUS_COLOR[status] ?? "#475569";
  const active = ["WORKING", "COMMUNICATING"].includes(status);
  const alert = ["APPROVAL_REQUIRED", "BLOCKED"].includes(status);

  return (
    <div
      className="relative w-3 h-3 rounded-full flex-shrink-0"
      style={{ background: color }}
    >
      {(active || alert) && (
        <div
          className="absolute inset-0 rounded-full animate-ping"
          style={{
            background: color,
            opacity: 0.4,
            animationDuration: alert ? "0.8s" : "1.5s",
          }}
        />
      )}
    </div>
  );
}

// ─── Agent Avatar Card ────────────────────────────────────────────────────────

function AgentAvatar({
  agent,
  status,
  selected,
  onClick,
}: {
  agent: AgentCard;
  status: string;
  selected: boolean;
  onClick: () => void;
}) {
  const color = STATUS_COLOR[status] ?? "#475569";
  const initials = agent.name
    .split(" ")
    .map((n) => n[0])
    .join("");

  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1 group"
      title={`${agent.name} — ${STATUS_LABEL[status] ?? status}`}
    >
      {/* Avatar circle */}
      <div
        className="relative w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold transition-transform group-hover:scale-110"
        style={{
          background: `linear-gradient(135deg, ${color}33, ${color}11)`,
          border: `2px solid ${selected ? color : color + "66"}`,
          color,
          boxShadow: selected ? `0 0 12px ${color}66` : "none",
        }}
      >
        {initials}
        {/* Status ring */}
        <div className="absolute -bottom-1 -right-1">
          <StatusRing status={status} />
        </div>
      </div>
      {/* Name */}
      <span
        className="text-xs font-medium truncate max-w-[60px] text-center"
        style={{ color: selected ? color : "var(--nexus-muted)" }}
      >
        {agent.name.split(" ")[0]}
      </span>
    </button>
  );
}

// ─── Department Card ─────────────────────────────────────────────────────────

function DepartmentCard({
  dept,
  agents,
  agentStatus,
  selectedAgentId,
  onSelectAgent,
  hasAlert,
  pendingApprovals,
}: {
  dept: Department;
  agents: AgentCard[];
  agentStatus: Record<string, string>;
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
  hasAlert: boolean;
  pendingApprovals: number;
}) {
  const deptAgents = agents.filter((a) => dept.agents.includes(a.id));
  const anyActive = deptAgents.some((a) =>
    ["WORKING", "COMMUNICATING"].includes(agentStatus[a.id] ?? "IDLE")
  );
  const anyBlocked = deptAgents.some((a) =>
    ["APPROVAL_REQUIRED", "BLOCKED"].includes(agentStatus[a.id] ?? "IDLE")
  );

  const borderColor = hasAlert
    ? "#ef444466"
    : anyBlocked
    ? "#f59e0b66"
    : anyActive
    ? dept.color + "66"
    : "var(--nexus-border)";

  const glowColor = hasAlert
    ? "rgba(239,68,68,0.08)"
    : anyBlocked
    ? "rgba(245,158,11,0.06)"
    : anyActive
    ? dept.color + "0a"
    : "transparent";

  return (
    <div
      className="rounded-xl p-4 flex flex-col gap-3 transition-all duration-300"
      style={{
        background: `linear-gradient(135deg, var(--nexus-surface), ${glowColor})`,
        border: `1px solid ${borderColor}`,
        minHeight: "120px",
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">{dept.icon}</span>
          <div>
            <div className="text-sm font-semibold" style={{ color: dept.color }}>
              {dept.name}
            </div>
            <div className="text-xs" style={{ color: "var(--nexus-muted)" }}>
              {dept.description}
            </div>
          </div>
        </div>

        {/* Alert badges */}
        <div className="flex gap-1">
          {hasAlert && (
            <span
              className="text-xs px-1.5 py-0.5 rounded font-bold animate-pulse"
              style={{
                background: "rgba(239,68,68,0.2)",
                color: "#ef4444",
                border: "1px solid rgba(239,68,68,0.4)",
              }}
            >
              🚨
            </span>
          )}
          {pendingApprovals > 0 && (
            <span
              className="text-xs px-1.5 py-0.5 rounded font-bold"
              style={{
                background: "rgba(245,158,11,0.2)",
                color: "#f59e0b",
                border: "1px solid rgba(245,158,11,0.4)",
              }}
            >
              ⏸ {pendingApprovals}
            </span>
          )}
        </div>
      </div>

      {/* Agents */}
      {deptAgents.length > 0 ? (
        <div className="flex items-center gap-3 flex-wrap">
          {deptAgents.map((agent) => (
            <AgentAvatar
              key={agent.id}
              agent={agent}
              status={agentStatus[agent.id] ?? "IDLE"}
              selected={selectedAgentId === agent.id}
              onClick={() => onSelectAgent(agent.id)}
            />
          ))}
        </div>
      ) : (
        <div className="text-xs" style={{ color: "var(--nexus-muted)" }}>
          Infrastructure — no agents
        </div>
      )}
    </div>
  );
}

// ─── Mission Launcher ─────────────────────────────────────────────────────────

function MissionLauncher({
  onLaunch,
  loading,
  currentMission,
}: {
  onLaunch: () => void;
  loading: boolean;
  currentMission: Mission | null;
}) {
  const mStatus = currentMission?.status;
  const mColor =
    mStatus === "completed"
      ? "#10b981"
      : mStatus === "awaiting_approval"
      ? "#f59e0b"
      : mStatus === "running"
      ? "#06b6d4"
      : mStatus === "failed"
      ? "#ef4444"
      : "#6366f1";

  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: "var(--nexus-surface-2)",
        border: "1px solid rgba(99,102,241,0.3)",
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-sm font-bold" style={{ color: "#6366f1" }}>
            Operations Center
          </div>
          <div className="text-xs mt-0.5" style={{ color: "var(--nexus-muted)" }}>
            AidOps Global — Emergency Supply Command
          </div>
        </div>
        {currentMission && (
          <span
            className="text-xs px-2 py-0.5 rounded-full font-semibold"
            style={{
              background: mColor + "22",
              color: mColor,
              border: `1px solid ${mColor}44`,
            }}
          >
            {mStatus?.replace("_", " ").toUpperCase()}
          </span>
        )}
      </div>

      {currentMission ? (
        <div className="space-y-2">
          <div className="text-xs font-medium" style={{ color: "var(--nexus-text)" }}>
            {currentMission.title}
          </div>
          <div className="text-xs italic" style={{ color: "var(--nexus-muted)" }}>
            {currentMission.objective}
          </div>
          {/* Stepper */}
          <div className="flex items-center gap-1 mt-2 overflow-x-auto">
            {currentMission.plan.map((step, i) => {
              const sc =
                step.status === "completed"
                  ? "#10b981"
                  : step.status === "in_progress"
                  ? "#06b6d4"
                  : step.status === "blocked"
                  ? "#f59e0b"
                  : "#475569";
              return (
                <div key={i} className="flex items-center gap-1 flex-shrink-0">
                  <div
                    className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold"
                    style={{
                      background: sc + "22",
                      color: sc,
                      border: `1px solid ${sc}55`,
                    }}
                  >
                    {step.status === "completed"
                      ? "✓"
                      : step.status === "in_progress"
                      ? "▶"
                      : step.status === "blocked"
                      ? "⏸"
                      : step.step}
                  </div>
                  {i < currentMission.plan.length - 1 && (
                    <div
                      className="h-px w-4"
                      style={{
                        background: step.status === "completed" ? "#10b981" : "#2a3a52",
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <button
          onClick={onLaunch}
          disabled={loading}
          className="w-full py-2.5 rounded-lg text-sm font-bold transition-all mt-2"
          style={{
            background: "linear-gradient(135deg, #6366f1, #4f46e5)",
            color: "#fff",
            boxShadow: "0 0 16px rgba(99,102,241,0.35)",
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? "Launching…" : "▶  Launch Emergency Vendor Mission"}
        </button>
      )}
    </div>
  );
}

// ─── Agent Inspector ──────────────────────────────────────────────────────────

function AgentInspector({
  agent,
  status,
  events,
  onClose,
}: {
  agent: AgentCard;
  status: string;
  events: NexusEvent[];
  onClose: () => void;
}) {
  const color = STATUS_COLOR[status] ?? "#475569";
  const agentEvents = events
    .filter((e) => e.agentId === agent.id || e.targetAgentId === agent.id)
    .slice(-20)
    .reverse();

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 border-b flex-shrink-0"
        style={{ borderColor: "var(--nexus-border)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center font-bold"
            style={{
              background: color + "22",
              color,
              border: `2px solid ${color}66`,
            }}
          >
            {agent.name
              .split(" ")
              .map((n) => n[0])
              .join("")}
          </div>
          <div>
            <div className="font-semibold text-sm" style={{ color: "var(--nexus-text)" }}>
              {agent.name}
            </div>
            <div className="text-xs" style={{ color: "var(--nexus-muted)" }}>
              {agent.role}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-sm px-2 py-1 rounded"
          style={{ color: "var(--nexus-muted)" }}
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Status */}
        <div>
          <div className="text-xs font-semibold uppercase mb-1.5" style={{ color: "var(--nexus-muted)" }}>
            Status
          </div>
          <div className="flex items-center gap-2">
            <StatusRing status={status} />
            <span className="text-sm font-medium" style={{ color }}>
              {STATUS_LABEL[status] ?? status}
            </span>
          </div>
        </div>

        {/* Identity */}
        <div>
          <div className="text-xs font-semibold uppercase mb-1.5" style={{ color: "var(--nexus-muted)" }}>
            Identity
          </div>
          <div
            className="rounded-lg p-2.5 text-xs font-mono"
            style={{
              background: "var(--nexus-surface-2)",
              border: "1px solid var(--nexus-border)",
              color: "#94a3b8",
            }}
          >
            <div>
              id: <span style={{ color }}>{agent.id}</span>
            </div>
            <div>principal: {agent.identity.principal}</div>
            <div>risk: {agent.identity.riskLevel}</div>
            <div>tier: T{agent.tier}</div>
          </div>
        </div>

        {/* Scopes / Permissions */}
        {agent.identity.scopes.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase mb-1.5" style={{ color: "var(--nexus-muted)" }}>
              Permissions
            </div>
            <div className="flex flex-wrap gap-1">
              {agent.identity.scopes.map((s) => (
                <span
                  key={s}
                  className="text-xs px-1.5 py-0.5 rounded"
                  style={{
                    background: "#10b98122",
                    color: "#10b981",
                    border: "1px solid #10b98133",
                    fontFamily: "monospace",
                  }}
                >
                  ✓ {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Tools */}
        {agent.tools.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase mb-1.5" style={{ color: "var(--nexus-muted)" }}>
              Tools ({agent.tools.length})
            </div>
            <div className="flex flex-wrap gap-1">
              {agent.tools.map((t) => (
                <span
                  key={t}
                  className="text-xs px-1.5 py-0.5 rounded font-mono"
                  style={{
                    background: "rgba(100,116,139,0.15)",
                    color: "#64748b",
                    border: "1px solid rgba(100,116,139,0.2)",
                  }}
                >
                  {t}()
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Tagline */}
        {agent.persona?.tagline && (
          <div>
            <div className="text-xs font-semibold uppercase mb-1.5" style={{ color: "var(--nexus-muted)" }}>
              Persona
            </div>
            <div
              className="text-xs italic p-2 rounded-lg"
              style={{
                borderLeft: `3px solid ${color}`,
                background: color + "11",
                color: "var(--nexus-text)",
              }}
            >
              "{agent.persona.tagline}"
            </div>
          </div>
        )}

        {/* Recent Events */}
        <div>
          <div className="text-xs font-semibold uppercase mb-1.5" style={{ color: "var(--nexus-muted)" }}>
            Recent Activity ({agentEvents.length})
          </div>
          {agentEvents.length === 0 ? (
            <div className="text-xs" style={{ color: "var(--nexus-muted)" }}>
              No events yet.
            </div>
          ) : (
            <div className="space-y-1.5">
              {agentEvents.map((ev) => {
                const ec = EVENT_COLORS[ev.type] ?? "#64748b";
                return (
                  <div key={ev.id} className="flex items-start gap-2">
                    <div
                      className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
                      style={{ background: ec }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1">
                        <span className="text-xs font-semibold" style={{ color: ec }}>
                          {ev.type}
                        </span>
                        <span className="text-xs ml-auto" style={{ color: "var(--nexus-muted)" }}>
                          {fmt(ev.timestamp)}
                        </span>
                      </div>
                      <div className="text-xs truncate" style={{ color: "var(--nexus-muted)" }}>
                        {ev.summary}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Approval Overlay ─────────────────────────────────────────────────────────

function ApprovalBanner({
  approval,
  onDecide,
}: {
  approval: Approval;
  onDecide: (id: string, decision: "granted" | "denied") => void;
}) {
  return (
    <div
      className="rounded-xl p-4 slide-up"
      style={{
        background: "rgba(245,158,11,0.08)",
        border: "2px solid rgba(245,158,11,0.5)",
      }}
    >
      <div className="flex items-start gap-3 mb-3">
        <span className="text-2xl">⏸</span>
        <div>
          <div className="font-bold text-sm" style={{ color: "#f59e0b" }}>
            Approval Required
          </div>
          <div className="text-xs mt-0.5" style={{ color: "var(--nexus-muted)" }}>
            {approval.agentId} wants to execute{" "}
            <span className="font-mono" style={{ color: "#f59e0b" }}>
              {approval.tool}
            </span>
          </div>
        </div>
      </div>
      <div
        className="text-xs rounded-lg p-2 mb-3 font-mono"
        style={{
          background: "var(--nexus-surface-2)",
          border: "1px solid var(--nexus-border)",
          color: "#94a3b8",
        }}
      >
        {JSON.stringify(approval.request, null, 2).split("\n").slice(0, 5).join("\n")}
      </div>
      <div
        className="text-xs mb-3 px-2 py-1.5 rounded"
        style={{
          background: "rgba(245,158,11,0.1)",
          borderLeft: "3px solid #f59e0b",
          color: "#fcd34d",
        }}
      >
        ⚠ {approval.reason}
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => onDecide(approval.id, "granted")}
          className="flex-1 py-2 rounded-lg text-sm font-bold"
          style={{
            background: "rgba(16,185,129,0.15)",
            color: "#10b981",
            border: "1px solid rgba(16,185,129,0.4)",
          }}
        >
          ✓ Approve
        </button>
        <button
          onClick={() => onDecide(approval.id, "denied")}
          className="flex-1 py-2 rounded-lg text-sm font-bold"
          style={{
            background: "rgba(239,68,68,0.15)",
            color: "#ef4444",
            border: "1px solid rgba(239,68,68,0.4)",
          }}
        >
          ✕ Deny
        </button>
      </div>
    </div>
  );
}

// ─── Event Ticker ─────────────────────────────────────────────────────────────

function EventTicker({ events }: { events: NexusEvent[] }) {
  const recent = events.slice(-5).reverse();
  return (
    <div
      className="flex items-center gap-4 px-4 py-2 overflow-x-auto"
      style={{
        background: "var(--nexus-surface-2)",
        borderTop: "1px solid var(--nexus-border)",
        minHeight: "36px",
      }}
    >
      <span className="text-xs font-semibold flex-shrink-0" style={{ color: "var(--nexus-muted)" }}>
        LIVE ▶
      </span>
      {recent.length === 0 ? (
        <span className="text-xs" style={{ color: "var(--nexus-muted)" }}>
          No events yet — launch a mission to begin
        </span>
      ) : (
        recent.map((ev) => {
          const color = EVENT_COLORS[ev.type] ?? "#64748b";
          return (
            <div key={ev.id} className="flex items-center gap-1.5 flex-shrink-0">
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
              <span className="text-xs font-mono" style={{ color }}>
                {ev.type}
              </span>
              <span className="text-xs" style={{ color: "var(--nexus-muted)" }}>
                {ev.agentId && `— ${ev.agentId}`}
              </span>
              <span className="text-xs" style={{ color: "#334155" }}>
                {fmt(ev.timestamp)}
              </span>
              <span className="text-xs mx-2" style={{ color: "#334155" }}>
                ·
              </span>
            </div>
          );
        })
      )}
    </div>
  );
}

// ─── Main Visual Office ───────────────────────────────────────────────────────

export default function OfficePage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [agents, setAgents] = useState<AgentCard[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const { events, connected, agentStatus } = useEventStream();

  // Load static config + initial data
  useEffect(() => {
    fetch("/departments.json")
      .then((r) => r.json())
      .then(setDepartments)
      .catch(console.error);

    api.listAgents().then(setAgents).catch(console.error);
  }, []);

  // Periodically refresh approvals + missions (lightweight)
  const refreshREST = useCallback(async () => {
    const [m, a] = await Promise.all([api.listMissions(), api.listApprovals()]);
    setMissions(m);
    setApprovals(a);
  }, []);

  useEffect(() => {
    refreshREST();
    const id = setInterval(refreshREST, 4000);
    return () => clearInterval(id);
  }, [refreshREST]);

  const handleSeed = async () => {
    setLoading(true);
    try {
      await api.seed();
      const freshAgents = await api.listAgents();
      setAgents(freshAgents);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleLaunch = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.startMission({
        enterpriseId: "aidops-global",
        title: "Emergency Vendor Evaluation — MediSupply Corp",
        objective:
          "Evaluate and onboard MediSupply Corp as an emergency medical equipment vendor after natural disaster declaration.",
        vendorId: "medisupply-corp",
      });
      await refreshREST();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleDecide = async (id: string, decision: "granted" | "denied") => {
    setLoading(true);
    try {
      await api.decideApproval(id, decision);
      await refreshREST();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const latestMission = missions[missions.length - 1] ?? null;
  const pendingApprovals = approvals.filter((a) => a.status === "pending");
  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null;
  const securityEvents = events.filter((e) =>
    ["SECURITY_ALERT", "POLICY_BLOCKED", "CIRCUIT_BREAKER_TRIPPED"].includes(e.type)
  );

  // Map agentId → pending approval count
  const agentApprovalCount: Record<string, number> = {};
  for (const a of pendingApprovals) {
    agentApprovalCount[a.agentId] = (agentApprovalCount[a.agentId] ?? 0) + 1;
  }

  const handleAgentClick = (id: string) => {
    setSelectedAgentId(id);
    setInspectorOpen(true);
  };

  return (
    <div
      className="flex flex-col fade-in"
      style={{ height: "calc(100vh - 56px - 32px)" }} // full height minus nav and footer
    >
      {/* ── Three-panel body ── */}
      <div className="flex flex-1 overflow-hidden gap-4 pb-2">
        {/* ── LEFT SIDEBAR ── */}
        <div
          className="w-56 flex-shrink-0 flex flex-col gap-3 overflow-y-auto"
          style={{ minWidth: "200px" }}
        >
          {/* API status */}
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs"
            style={{
              background: connected ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
              border: `1px solid ${connected ? "rgba(16,185,129,0.25)" : "rgba(239,68,68,0.25)"}`,
              color: connected ? "#10b981" : "#ef4444",
            }}
          >
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{
                background: connected ? "#10b981" : "#ef4444",
                boxShadow: connected ? "0 0 6px #10b981" : "none",
              }}
            />
            {connected ? "Live Stream Active" : "Connecting…"}
          </div>

          {/* Seed button */}
          {agents.length === 0 && (
            <button
              onClick={handleSeed}
              disabled={loading}
              className="w-full py-2 rounded-xl text-sm font-medium"
              style={{
                background: "var(--nexus-surface-2)",
                border: "1px solid var(--nexus-border)",
                color: "var(--nexus-muted)",
              }}
            >
              Initialize Enterprise
            </button>
          )}

          {/* Stats */}
          <div
            className="rounded-xl p-3"
            style={{
              background: "var(--nexus-surface)",
              border: "1px solid var(--nexus-border)",
            }}
          >
            <div className="text-xs font-semibold uppercase mb-2" style={{ color: "var(--nexus-muted)" }}>
              Fleet Stats
            </div>
            {[
              { label: "Agents", value: agents.length, color: "#6366f1" },
              { label: "Missions", value: missions.length, color: "#06b6d4" },
              { label: "Events", value: events.length, color: "#8b5cf6" },
              { label: "Approvals", value: pendingApprovals.length, color: "#f59e0b" },
              { label: "Alerts", value: securityEvents.length, color: "#ef4444" },
            ].map(({ label, value, color }) => (
              <div key={label} className="flex items-center justify-between py-0.5">
                <span className="text-xs" style={{ color: "var(--nexus-muted)" }}>
                  {label}
                </span>
                <span className="text-xs font-bold" style={{ color }}>
                  {value}
                </span>
              </div>
            ))}
          </div>

          {/* Nav links */}
          <div
            className="rounded-xl p-2"
            style={{
              background: "var(--nexus-surface)",
              border: "1px solid var(--nexus-border)",
            }}
          >
            {[
              { href: "/", label: "🏢  Office", active: true },
              { href: "/missions", label: "🎯  Missions" },
              { href: "/agents", label: "🤖  Agents" },
              { href: "/approvals", label: "⏸  Approvals" },
              { href: "/security", label: "🔐  Security" },
            ].map(({ href, label, active }) => (
              <a
                key={href}
                href={href}
                className="block px-3 py-2 rounded-lg text-sm transition-all"
                style={{
                  color: active ? "#6366f1" : "var(--nexus-muted)",
                  background: active ? "rgba(99,102,241,0.12)" : "transparent",
                  textDecoration: "none",
                  fontWeight: active ? 600 : 400,
                }}
              >
                {label}
              </a>
            ))}
          </div>
        </div>

        {/* ── MAIN OFFICE CANVAS ── */}
        <div className="flex-1 relative rounded-xl overflow-hidden min-w-0" style={{ border: "1px solid var(--nexus-border)" }}>
          <Office3D
            departments={departments}
            agents={agents}
            agentStatus={agentStatus}
            selectedAgentId={selectedAgentId}
            onSelectAgent={handleAgentClick}
          />
          
          {/* HUD Overlay */}
          <div className="absolute top-0 left-0 right-0 p-4 pointer-events-none flex flex-col gap-3 z-10">
            {error && (
              <div
                className="px-4 py-2 rounded-xl text-sm pointer-events-auto shadow-lg"
                style={{
                  background: "rgba(239,68,68,0.9)",
                  border: "1px solid #ef4444",
                  color: "#fff",
                }}
              >
                ⚠ {error}
              </div>
            )}

            {/* Mission launcher */}
            <div className="pointer-events-auto shadow-xl max-w-xl">
              <MissionLauncher
                onLaunch={handleLaunch}
                loading={loading}
                currentMission={latestMission}
              />
            </div>

            {/* Pending approval banners */}
            {pendingApprovals.map((ap) => (
              <div key={ap.id} className="pointer-events-auto shadow-xl max-w-xl">
                <ApprovalBanner approval={ap} onDecide={handleDecide} />
              </div>
            ))}
          </div>
        </div>

        {/* ── RIGHT INSPECTOR PANEL ── */}
        <div
          className="w-72 flex-shrink-0 rounded-xl overflow-hidden transition-all"
          style={{
            background: "var(--nexus-surface)",
            border: "1px solid var(--nexus-border)",
            opacity: inspectorOpen && selectedAgent ? 1 : 0.4,
            display: inspectorOpen && selectedAgent ? "block" : "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {inspectorOpen && selectedAgent ? (
            <AgentInspector
              agent={selectedAgent}
              status={agentStatus[selectedAgent.id] ?? "IDLE"}
              events={events}
              onClose={() => {
                setInspectorOpen(false);
                setSelectedAgentId(null);
              }}
            />
          ) : (
            <div
              className="text-center p-6 text-sm"
              style={{ color: "var(--nexus-muted)" }}
            >
              <div className="text-2xl mb-2">🤖</div>
              Click an agent avatar to inspect identity, permissions and activity
            </div>
          )}
        </div>
      </div>

      {/* ── LIVE EVENT TICKER (bottom bar) ── */}
      <EventTicker events={events} />
    </div>
  );
}
