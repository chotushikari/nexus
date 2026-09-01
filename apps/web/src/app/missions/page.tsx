"use client";

/**
 * Mission Audit — the end-to-end timeline (§17). Every row is a real
 * backend event; nothing here is synthesised for display.
 */

import { useCallback, useEffect, useState } from "react";
import { api, Mission, NexusEvent } from "@/lib/api";
import { useEventStream } from "@/lib/useEventStream";
import { eventColor, fmtTime, fmtDateTime, MISSION_BADGE_CLASS } from "@/lib/events";

function MissionCard({
  mission,
  selected,
  onClick,
}: {
  mission: Mission;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-lg p-3 transition-colors"
      style={{
        background: selected ? "var(--paper-2)" : "transparent",
        border: `1px solid ${selected ? "var(--ink-3)" : "var(--paper-3)"}`,
      }}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="t-body font-semibold truncate" style={{ color: "var(--ink-0)" }}>
          {mission.title}
        </span>
        <span className={`badge ${MISSION_BADGE_CLASS[mission.status] ?? "s-neutral"} flex-none`}>
          <span className="badge-dot" />
          {mission.status.replace("_", " ")}
        </span>
      </div>
      <div className="t-mono" style={{ color: "var(--ink-3)", fontSize: 10.5 }}>
        {mission.vendorId} · {fmtDateTime(mission.createdAt)}
      </div>
    </button>
  );
}

function TimelineEvent({ ev }: { ev: NexusEvent }) {
  const [expanded, setExpanded] = useState(false);
  const color = eventColor(ev.type);
  const hasMetadata = Object.keys(ev.metadata).length > 0;

  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <span
          className="mt-1.5 h-2.5 w-2.5 flex-none rounded-full"
          style={{ background: color, outline: "2px solid var(--paper-0)" }}
        />
        <div className="mt-1 w-px flex-1" style={{ background: "var(--paper-3)", minHeight: 14 }} />
      </div>

      <div className="min-w-0 flex-1 pb-4">
        <div className="mb-0.5 flex flex-wrap items-center gap-2">
          <span className="t-mono font-semibold" style={{ fontSize: 10.5, color }}>
            {ev.type}
          </span>
          {ev.agentId && (
            <span className="t-mono" style={{ fontSize: 10.5, color: "var(--ink-2)" }}>
              {ev.agentId}
            </span>
          )}
          {ev.targetAgentId && (
            <>
              <span className="t-small" style={{ color: "var(--ink-3)" }}>→</span>
              <span className="t-mono" style={{ fontSize: 10.5, color: "var(--state-comm)" }}>
                {ev.targetAgentId}
              </span>
            </>
          )}
          <span className="t-mono ml-auto" style={{ fontSize: 10, color: "var(--ink-3)" }}>
            {fmtTime(ev.timestamp)}
          </span>
        </div>
        <div className="t-body" style={{ color: "var(--ink-0)" }}>
          {ev.summary}
        </div>
        {hasMetadata && (
          <>
            <button onClick={() => setExpanded(!expanded)} className="t-small mt-1" style={{ color: "var(--ink-3)" }}>
              {expanded ? "Hide details" : "Details"}
            </button>
            {expanded && (
              <pre className="code-block mt-1.5">
                {JSON.stringify(ev.metadata, null, 2)}
              </pre>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const STEP_CLASS: Record<string, string> = {
  completed: "s-success",
  in_progress: "s-active",
  blocked: "s-warning",
  failed: "s-danger",
};

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
  const missionEvents = events.filter((e) => !selectedId || e.missionId === selectedId);

  return (
    <div className="mx-auto h-full max-w-7xl fade-in">
      <div className="mb-4">
        <h1 className="t-display">Mission Audit</h1>
        <p className="t-small mt-0.5" style={{ color: "var(--ink-2)" }}>
          End-to-end record of every autonomous mission — every row is a runtime event
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        {/* Mission list */}
        <div className="panel overflow-hidden">
          <div className="t-label border-b px-4 py-3" style={{ borderColor: "var(--paper-3)" }}>
            Missions ({missions.length})
          </div>
          <div className="space-y-1 overflow-y-auto p-2" style={{ maxHeight: "65vh" }}>
            {loading ? (
              <div className="t-small py-8 text-center" style={{ color: "var(--ink-3)" }}>
                Loading…
              </div>
            ) : missions.length === 0 ? (
              <div className="t-small py-8 text-center" style={{ color: "var(--ink-3)" }}>
                No missions yet. Start one from the Command Center.
              </div>
            ) : (
              missions.map((m) => (
                <MissionCard key={m.id} mission={m} selected={selectedId === m.id} onClick={() => setSelectedId(m.id)} />
              ))
            )}
          </div>
        </div>

        {/* Timeline */}
        <div className="panel overflow-hidden xl:col-span-3">
          {selectedMission ? (
            <>
              <div className="border-b px-6 py-4" style={{ borderColor: "var(--paper-3)" }}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="t-title">{selectedMission.title}</h2>
                    <div className="t-small mt-0.5 italic" style={{ color: "var(--ink-2)" }}>
                      {selectedMission.objective}
                    </div>
                  </div>
                  <div className="t-mono flex-none text-right" style={{ fontSize: 10.5, color: "var(--ink-2)" }}>
                    <div>{selectedMission.enterpriseId}</div>
                    <div>{fmtDateTime(selectedMission.createdAt)}</div>
                    <div style={{ color: "var(--ink-3)" }}>{selectedMission.id}</div>
                  </div>
                </div>

                {/* Execution graph, flat projection of the real task graph */}
                <div className="mt-4 flex items-center gap-2 overflow-x-auto pb-1">
                  {selectedMission.plan.map((step, i) => (
                    <div key={i} className="flex flex-none items-center gap-2">
                      <div
                        className={`badge ${STEP_CLASS[step.status] ?? "s-neutral"}`}
                        style={{ padding: "4px 9px" }}
                      >
                        <span className="badge-dot" />
                        {step.agentId}
                      </div>
                      {i < selectedMission.plan.length - 1 && (
                        <div
                          className="h-px w-5"
                          style={{
                            background:
                              step.status === "completed" ? "var(--state-success)" : "var(--paper-4)",
                          }}
                        />
                      )}
                    </div>
                  ))}
                </div>
                {selectedMission.planSource && (
                  <div className="mt-2">
                    <span className="badge s-neutral t-mono" style={{ fontSize: 9.5 }}>
                      planner:{" "}
                      {selectedMission.planSource === "gemini"
                        ? selectedMission.planModel ?? "gemini"
                        : "deterministic fallback"}
                    </span>
                  </div>
                )}
              </div>

              <div className="overflow-y-auto p-6" style={{ maxHeight: "55vh" }}>
                <div className="t-label mb-4">Event Timeline ({missionEvents.length} events)</div>
                {missionEvents.length === 0 ? (
                  <div className="t-small py-8 text-center" style={{ color: "var(--ink-3)" }}>
                    No events yet for this mission.
                  </div>
                ) : (
                  missionEvents.map((ev) => <TimelineEvent key={ev.id} ev={ev} />)
                )}
              </div>
            </>
          ) : (
            <div className="t-small flex h-64 items-center justify-center" style={{ color: "var(--ink-3)" }}>
              Select a mission to view its audit trail.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
