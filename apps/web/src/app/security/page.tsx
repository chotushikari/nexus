"use client";

/**
 * Security Center (§18) — detections are visible, not buried: every row is
 * a real POLICY_BLOCKED / SECURITY_ALERT / circuit-breaker event.
 */

import { useCallback, useEffect, useState } from "react";
import { api, NexusEvent } from "@/lib/api";
import { eventColor, fmtTime } from "@/lib/events";

const THREAT_TYPES = ["SECURITY_ALERT", "POLICY_BLOCKED", "CIRCUIT_BREAKER_TRIPPED"];

const THREAT_LABEL: Record<string, string> = {
  SECURITY_ALERT: "Security Alert",
  POLICY_BLOCKED: "Policy Blocked",
  CIRCUIT_BREAKER_TRIPPED: "Circuit Breaker Tripped",
};

const THREAT_CLASS: Record<string, string> = {
  SECURITY_ALERT: "s-danger",
  POLICY_BLOCKED: "s-danger",
  CIRCUIT_BREAKER_TRIPPED: "s-approval",
};

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

  return (
    <div className="mx-auto max-w-4xl space-y-6 fade-in">
      <div>
        <h1 className="t-display">Security Center</h1>
        <p className="t-small mt-0.5" style={{ color: "var(--ink-2)" }}>
          Prompt-injection detections, policy violations, circuit-breaker events
        </p>
      </div>

      {/* Threat counters */}
      <div className="flex flex-wrap gap-3">
        {THREAT_TYPES.map((t) => {
          const count = events.filter((e) => e.type === t).length;
          return (
            <div key={t} className={`panel flex items-center gap-3 px-4 py-2.5 ${count > 0 ? "attention" : ""}`}>
              <span className="t-display" style={{ fontSize: 20, color: eventColor(t) }}>
                {count}
              </span>
              <span className="t-label">{THREAT_LABEL[t]}</span>
            </div>
          );
        })}
      </div>

      {/* Event list */}
      <div className="space-y-3">
        {loading ? (
          <div className="t-small py-12 text-center" style={{ color: "var(--ink-3)" }}>
            Loading…
          </div>
        ) : events.length === 0 ? (
          <div className="panel t-small py-16 text-center" style={{ color: "var(--ink-2)" }}>
            No security events detected.
            <div className="t-mono mt-1" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
              Run a mission with the malicious vendor document to trigger a SECURITY_ALERT.
            </div>
          </div>
        ) : (
          events.map((e) => (
            <div
              key={e.id}
              className="panel slide-up p-4"
              style={{ borderLeft: `3px solid ${eventColor(e.type)}` }}
            >
              <div className="mb-2 flex items-center gap-2.5">
                <span className={`badge ${THREAT_CLASS[e.type] ?? "s-danger"}`}>
                  <span className="badge-dot" />
                  {e.type}
                </span>
                {e.agentId && (
                  <span className="t-mono" style={{ fontSize: 10.5, color: "var(--ink-2)" }}>
                    {e.agentId}
                  </span>
                )}
                <span className="t-mono ml-auto" style={{ fontSize: 10, color: "var(--ink-3)" }}>
                  {fmtTime(e.timestamp)}
                </span>
              </div>

              <p className="t-body font-medium" style={{ color: "var(--ink-0)" }}>
                {e.summary}
              </p>

              {Object.keys(e.metadata).length > 0 && (
                <details className="mt-2">
                  <summary className="t-small cursor-pointer" style={{ color: "var(--ink-3)" }}>
                    Evidence
                  </summary>
                  <pre className="code-block mt-2">{JSON.stringify(e.metadata, null, 2)}</pre>
                </details>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
