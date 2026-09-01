"use client";

/**
 * Executive approvals (§38). The amber decision buttons are the one place
 * the palette reserves colour for an action.
 */

import { useCallback, useEffect, useState } from "react";
import { api, Approval } from "@/lib/api";
import { fmtDateTime } from "@/lib/events";

const STATUS_CLASS: Record<string, string> = {
  pending: "s-approval",
  granted: "s-success",
  denied: "s-danger",
};

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<"all" | "pending" | "granted" | "denied">("all");

  const refresh = useCallback(async () => {
    const data = await api.listApprovals();
    setApprovals(data.slice().reverse()); // newest first
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);

  const handleDecide = async (id: string, decision: "granted" | "denied") => {
    setLoading(true);
    try {
      await api.decideApproval(id, decision);
      await refresh();
    } finally {
      setLoading(false);
    }
  };

  const filtered = approvals.filter((a) => filter === "all" || a.status === filter);

  const counts = {
    all: approvals.length,
    pending: approvals.filter((a) => a.status === "pending").length,
    granted: approvals.filter((a) => a.status === "granted").length,
    denied: approvals.filter((a) => a.status === "denied").length,
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="t-display">Approval Queue</h1>
          <p className="t-small mt-0.5" style={{ color: "var(--ink-2)" }}>
            Human-in-the-loop governance for high-risk agent actions
          </p>
        </div>
        <button className="btn" onClick={refresh}>
          Refresh
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex flex-wrap gap-2">
        {(["all", "pending", "granted", "denied"] as const).map((s) => {
          const active = filter === s;
          return (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className="btn"
              style={{
                background: active ? "var(--ink-0)" : "var(--paper-0)",
                color: active ? "var(--paper-0)" : "var(--ink-1)",
                borderColor: active ? "var(--ink-0)" : "var(--paper-4)",
              }}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
              <span
                className="t-mono rounded-full px-1.5"
                style={{ fontSize: 10, background: active ? "rgba(251,248,241,0.18)" : "var(--paper-2)" }}
              >
                {counts[s]}
              </span>
            </button>
          );
        })}
      </div>

      {/* Approval list */}
      <div className="space-y-3">
        {filtered.length === 0 ? (
          <div className="panel t-small py-16 text-center" style={{ color: "var(--ink-3)" }}>
            No {filter === "all" ? "" : filter} approvals.
          </div>
        ) : (
          filtered.map((a) => {
            const isPending = a.status === "pending";
            return (
              <div
                key={a.id}
                className="panel slide-up p-5"
                style={{
                  borderColor: isPending ? "var(--state-approval)" : "var(--paper-3)",
                }}
              >
                {/* Header row */}
                <div className="mb-3 flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="t-title t-mono">{a.tool}</span>
                      <span className={`badge ${STATUS_CLASS[a.status] ?? "s-neutral"}`}>
                        <span className="badge-dot" />
                        {a.status}
                      </span>
                      {isPending && (
                        <span className="badge s-danger">
                          {a.risk ? a.risk.toUpperCase() : "HIGH"} RISK
                        </span>
                      )}
                    </div>
                    <div className="t-small mt-1 flex flex-wrap gap-x-4" style={{ color: "var(--ink-2)" }}>
                      <span>
                        Agent: <b style={{ color: "var(--ink-0)" }}>{a.agentId}</b>
                      </span>
                      <span>
                        Mission: <b style={{ color: "var(--ink-0)" }}>{a.missionId}</b>
                      </span>
                      <span>
                        Policy: <span className="t-mono">{a.policyId}</span>
                      </span>
                    </div>
                  </div>
                  <div className="t-mono flex-none text-right" style={{ fontSize: 10.5, color: "var(--ink-2)" }}>
                    <div style={{ color: "var(--ink-3)" }}>Requested</div>
                    <div>{fmtDateTime(a.createdAt)}</div>
                    {a.decidedAt && (
                      <>
                        <div className="mt-1" style={{ color: "var(--ink-3)" }}>
                          Decided
                        </div>
                        <div>{fmtDateTime(a.decidedAt)}</div>
                      </>
                    )}
                  </div>
                </div>

                {/* Reason */}
                <div
                  className="t-body mb-3 px-3 py-2"
                  style={{
                    background: "var(--wash-approval)",
                    borderLeft: "3px solid var(--state-approval)",
                    color: "var(--ink-0)",
                    borderRadius: "0 var(--radius) var(--radius) 0",
                  }}
                >
                  {a.reason}
                </div>

                {/* Request payload */}
                <pre className="code-block mb-4">{JSON.stringify(a.request, null, 2)}</pre>

                {/* Actions */}
                {isPending && (
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleDecide(a.id, "granted")}
                      disabled={loading}
                      className="btn btn-approve flex-1"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleDecide(a.id, "denied")}
                      disabled={loading}
                      className="btn btn-deny flex-1"
                    >
                      Deny
                    </button>
                  </div>
                )}

                {!isPending && a.decidedBy && (
                  <div className="t-small text-right" style={{ color: "var(--ink-3)" }}>
                    Decided by <b>{a.decidedBy}</b>
                    {a.decidedAt && ` · ${fmtDateTime(a.decidedAt)}`}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
