"use client";

import { useCallback, useEffect, useState } from "react";
import { api, Mission, NexusEvent } from "@/lib/api";
import { useEventStream } from "@/lib/useEventStream";

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
  AGENT_MESSAGE: "#94a3b8",
  CIRCUIT_BREAKER_TRIPPED: "#7c3aed",
  MISSION_COMPLETED: "#10b981",
  MISSION_FAILED: "#ef4444",
};

function fmt(ts: string) {
  return new Date(ts).toLocaleTimeString("en-IN", { hour12: false });
}

function fmtDate(ts: string) {
  return new Date(ts).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "medium" });
}

function MissionCard({
  mission,
  selected,
  onClick,
}: {
  mission: Mission;
  selected: boolean;
  onClick: () => void;
}) {
  const color =
    mission.status === "completed"
      ? "#10b981"
      : mission.status === "running"
      ? "#06b6d4"
      : mission.status === "awaiting_approval"
      ? "#f59e0b"
      : mission.status === "failed"
      ? "#ef4444"
      : "#6366f1";

  return (
    <div
      onClick={onClick}
      className="p-3 rounded-xl cursor-pointer transition-all"
      style={{
        background: selected ? "var(--nexus-surface-2)" : "transparent",
        border: `1px solid ${selected ? color + "66" : "var(--nexus-border)"}`,
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-semibold truncate" style={{ color: "var(--nexus-text)" }}>
          {mission.title}
        </span>
        <span
          className="text-xs px-1.5 py-0.5 rounded-full ml-2 flex-shrink-0"
          style={{ background: color + "22", color, border: `1px solid ${color}44` }}
        >
          {mission.status.replace("_", " ")}
        </span>
      </div>
      <div className="text-xs" style={{ color: "var(--nexus-muted)" }}>
        {mission.vendorId} · {fmtDate(mission.createdAt)}
      </div>
    </div>
  );
}

function TimelineEvent({ ev }: { ev: NexusEvent }) {
  const [expanded, setExpanded] = useState(false);
  const color = EVENT_COLORS[ev.type] ?? "#64748b";
  const hasMetadata = Object.keys(ev.metadata).length > 0;

  return (
    <div className="flex gap-3 group">
      {/* Timeline spine */}
      <div className="flex flex-col items-center">
        <div
          className="w-3 h-3 rounded-full flex-shrink-0 mt-0.5"
          style={{ background: color, boxShadow: `0 0 6px ${color}66` }}
        />
        <div
          className="w-px flex-1 mt-1"
          style={{ background: "var(--nexus-border)", minHeight: "16px" }}
        />
      </div>

      {/* Content */}
      <div className="flex-1 pb-3 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span
            className="text-xs font-bold"
            style={{ color, fontFamily: "monospace" }}
          >
            {ev.type}
          </span>
          {ev.agentId && (
            <span className="text-xs" style={{ color: "var(--nexus-muted)" }}>
              {ev.agentId}
            </span>
          )}
          {ev.targetAgentId && (
            <>
              <span className="text-xs" style={{ color: "#334155" }}>
                →
              </span>
              <span className="text-xs" style={{ color: "#6366f1" }}>
                {ev.targetAgentId}
              </span>
            </>
          )}
          <span className="ml-auto text-xs" style={{ color: "var(--nexus-muted)" }}>
            {fmt(ev.timestamp)}
          </span>
        </div>
        <div className="text-sm" style={{ color: "var(--nexus-text)" }}>
          {ev.summary}
        </div>
        {hasMetadata && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs mt-1"
            style={{ color: "var(--nexus-muted)" }}
          >
            {expanded ? "▲ hide" : "▼ details"}
          </button>
        )}
        {expanded && hasMetadata && (
          <pre
            className="mt-1 text-xs rounded p-2 overflow-x-auto"
            style={{
              background: "#0a0f1e",
              border: "1px solid var(--nexus-border)",
              color: "#94a3b8",
            }}
          >
            {JSON.stringify(ev.metadata, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

export default function MissionsPage() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const { events } = useEventStream(selectedId ?? undefined);

  const refresh = useCallback(async () => {
    const m = await api.listMissions();
    setMissions(m.slice().reverse()); // newest first
    if (!selectedId && m.length > 0) setSelectedId(m[m.length - 1].id);
    setLoading(false);
  }, [selectedId]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);

  const selectedMission = missions.find((m) => m.id === selectedId) ?? null;
  const missionEvents = events.filter(
    (e) => !selectedId || e.missionId === selectedId
  );

  return (
    <div className="max-w-7xl mx-auto fade-in h-full">
      <div className="mb-4">
        <h1 className="text-2xl font-bold" style={{ color: "var(--nexus-text)" }}>
          Mission Timeline
        </h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--nexus-muted)" }}>
          End-to-end audit trail for every autonomous mission
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* Mission list */}
        <div
          className="rounded-xl overflow-hidden"
          style={{
            background: "var(--nexus-surface)",
            border: "1px solid var(--nexus-border)",
          }}
        >
          <div
            className="px-4 py-3 border-b text-sm font-semibold"
            style={{
              borderColor: "var(--nexus-border)",
              color: "var(--nexus-muted)",
            }}
          >
            Missions ({missions.length})
          </div>
          <div className="p-2 space-y-1 overflow-y-auto" style={{ maxHeight: "65vh" }}>
            {loading ? (
              <div className="text-center py-8 text-sm" style={{ color: "var(--nexus-muted)" }}>
                Loading…
              </div>
            ) : missions.length === 0 ? (
              <div className="text-center py-8 text-sm" style={{ color: "var(--nexus-muted)" }}>
                No missions yet. Launch one from the Office.
              </div>
            ) : (
              missions.map((m) => (
                <MissionCard
                  key={m.id}
                  mission={m}
                  selected={selectedId === m.id}
                  onClick={() => setSelectedId(m.id)}
                />
              ))
            )}
          </div>
        </div>

        {/* Timeline */}
        <div
          className="xl:col-span-3 rounded-xl overflow-hidden"
          style={{
            background: "var(--nexus-surface)",
            border: "1px solid var(--nexus-border)",
          }}
        >
          {selectedMission ? (
            <>
              {/* Mission header */}
              <div
                className="px-6 py-4 border-b"
                style={{ borderColor: "var(--nexus-border)" }}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="font-bold text-lg" style={{ color: "var(--nexus-text)" }}>
                      {selectedMission.title}
                    </h2>
                    <div className="text-sm mt-0.5 italic" style={{ color: "var(--nexus-muted)" }}>
                      {selectedMission.objective}
                    </div>
                  </div>
                  <div className="text-right text-xs" style={{ color: "var(--nexus-muted)" }}>
                    <div>{selectedMission.enterpriseId}</div>
                    <div>{fmtDate(selectedMission.createdAt)}</div>
                    <div className="mt-1 font-mono">{selectedMission.id}</div>
                  </div>
                </div>

                {/* Step progress */}
                <div className="flex items-center gap-2 mt-4 overflow-x-auto">
                  {selectedMission.plan.map((step, i) => {
                    const sc =
                      step.status === "completed"
                        ? "#10b981"
                        : step.status === "in_progress"
                        ? "#06b6d4"
                        : step.status === "blocked"
                        ? "#f59e0b"
                        : "#475569";
                    return (
                      <div key={i} className="flex items-center gap-2 flex-shrink-0">
                        <div
                          className="flex items-center gap-2 px-3 py-1.5 rounded-xl"
                          style={{
                            background: sc + "22",
                            border: `1px solid ${sc}44`,
                          }}
                        >
                          <div
                            className="w-4 h-4 rounded-full flex items-center justify-center text-xs font-bold"
                            style={{ background: sc + "33", color: sc }}
                          >
                            {step.status === "completed"
                              ? "✓"
                              : step.status === "in_progress"
                              ? "▶"
                              : step.status === "blocked"
                              ? "⏸"
                              : step.step}
                          </div>
                          <span className="text-xs font-medium" style={{ color: sc }}>
                            {step.agentId}
                          </span>
                        </div>
                        {i < selectedMission.plan.length - 1 && (
                          <div
                            className="h-px w-6"
                            style={{
                              background:
                                step.status === "completed" ? "#10b981" : "#2a3a52",
                            }}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Timeline events */}
              <div className="p-6 overflow-y-auto" style={{ maxHeight: "55vh" }}>
                <div className="text-xs font-semibold uppercase mb-4" style={{ color: "var(--nexus-muted)" }}>
                  Event Timeline ({missionEvents.length} events)
                </div>
                {missionEvents.length === 0 ? (
                  <div className="text-sm text-center py-8" style={{ color: "var(--nexus-muted)" }}>
                    No events yet for this mission.
                  </div>
                ) : (
                  missionEvents.map((ev) => <TimelineEvent key={ev.id} ev={ev} />)
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-64 text-sm" style={{ color: "var(--nexus-muted)" }}>
              Select a mission to view its timeline.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
