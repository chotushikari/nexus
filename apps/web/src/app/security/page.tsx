"use client";

import { useCallback, useEffect, useState } from "react";
import { api, NexusEvent } from "@/lib/api";

const THREAT_TYPES = ["SECURITY_ALERT", "POLICY_BLOCKED", "CIRCUIT_BREAKER_TRIPPED"];

function fmt(ts: string) {
  return new Date(ts).toLocaleTimeString("en-IN", { hour12: false });
}

export default function SecurityPage() {
  const [events, setEvents] = useState<NexusEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const all = await api.listEvents();
    setEvents(all.filter((e) => THREAT_TYPES.includes(e.type)).reverse());
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);

  const COLOR: Record<string, string> = {
    SECURITY_ALERT: "#ef4444",
    POLICY_BLOCKED: "#f59e0b",
    CIRCUIT_BREAKER_TRIPPED: "#7c3aed",
  };

  return (
    <div className="max-w-4xl mx-auto fade-in space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--nexus-text)" }}>
          Security Console
        </h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--nexus-muted)" }}>
          Prompt-injection detections, policy violations, circuit-breaker events
        </p>
      </div>

      {/* Threat count chips */}
      <div className="flex gap-3">
        {THREAT_TYPES.map((t) => {
          const count = events.filter((e) => e.type === t).length;
          const color = COLOR[t];
          return (
            <div
              key={t}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm"
              style={{
                background: color + "11",
                border: `1px solid ${color}44`,
              }}
            >
              <span style={{ color }} className="font-bold text-lg">
                {count}
              </span>
              <span style={{ color: "var(--nexus-muted)" }}>{t.replace(/_/g, " ")}</span>
            </div>
          );
        })}
      </div>

      {/* Event list */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-12 text-center text-sm" style={{ color: "var(--nexus-muted)" }}>
            Loading…
          </div>
        ) : events.length === 0 ? (
          <div
            className="py-16 text-center text-sm rounded-xl"
            style={{
              background: "var(--nexus-surface)",
              border: "1px solid var(--nexus-border)",
              color: "var(--nexus-muted)",
            }}
          >
            ✅ No security events detected.
            <div className="mt-1 text-xs">
              Run a mission with a malicious vendor document to trigger a SECURITY_ALERT.
            </div>
          </div>
        ) : (
          events.map((e) => {
            const color = COLOR[e.type] ?? "#ef4444";
            return (
              <div
                key={e.id}
                className="rounded-xl p-4 slide-up"
                style={{
                  background: "var(--nexus-surface)",
                  border: `1px solid ${color}44`,
                }}
              >
                <div className="flex items-center gap-3 mb-2">
                  <span
                    className="text-lg"
                    role="img"
                    aria-label={e.type}
                  >
                    {e.type === "SECURITY_ALERT"
                      ? "🚨"
                      : e.type === "POLICY_BLOCKED"
                      ? "🛡"
                      : "⚡"}
                  </span>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-bold"
                    style={{
                      background: color + "22",
                      color,
                      border: `1px solid ${color}55`,
                    }}
                  >
                    {e.type}
                  </span>
                  {e.agentId && (
                    <span className="text-xs" style={{ color: "var(--nexus-muted)" }}>
                      {e.agentId}
                    </span>
                  )}
                  <span className="ml-auto text-xs" style={{ color: "var(--nexus-muted)" }}>
                    {fmt(e.timestamp)}
                  </span>
                </div>

                <p className="text-sm font-medium mb-2" style={{ color: "var(--nexus-text)" }}>
                  {e.summary}
                </p>

                {Object.keys(e.metadata).length > 0 && (
                  <details>
                    <summary
                      className="text-xs cursor-pointer"
                      style={{ color: "var(--nexus-muted)" }}
                    >
                      View metadata
                    </summary>
                    <pre
                      className="mt-2 rounded-lg p-2 text-xs overflow-x-auto"
                      style={{
                        background: "#0a0f1e",
                        border: "1px solid var(--nexus-border)",
                        color: "#94a3b8",
                      }}
                    >
                      {JSON.stringify(e.metadata, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
