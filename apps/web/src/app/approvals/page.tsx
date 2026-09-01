"use client";

import { useCallback, useEffect, useState } from "react";
import { api, Approval } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  pending: "#f59e0b",
  granted: "#10b981",
  denied: "#ef4444",
};

function fmt(ts: string) {
  return new Date(ts).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "medium" });
}

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

  const filtered = approvals.filter(
    (a) => filter === "all" || a.status === filter
  );

  const counts = {
    all: approvals.length,
    pending: approvals.filter((a) => a.status === "pending").length,
    granted: approvals.filter((a) => a.status === "granted").length,
    denied: approvals.filter((a) => a.status === "denied").length,
  };

  return (
    <div className="max-w-4xl mx-auto fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--nexus-text)" }}>
            Approval Queue
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--nexus-muted)" }}>
            Human-in-the-loop governance for high-risk agent actions
          </p>
        </div>
        <button
          onClick={refresh}
          className="px-3 py-1.5 rounded-lg text-sm"
          style={{
            background: "var(--nexus-surface-2)",
            border: "1px solid var(--nexus-border)",
            color: "var(--nexus-muted)",
          }}
        >
          ↻ Refresh
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {(["all", "pending", "granted", "denied"] as const).map((s) => {
          const color = s === "all" ? "#6366f1" : STATUS_COLORS[s];
          const active = filter === s;
          return (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all"
              style={{
                background: active ? color + "22" : "var(--nexus-surface)",
                color: active ? color : "var(--nexus-muted)",
                border: `1px solid ${active ? color + "55" : "var(--nexus-border)"}`,
              }}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
              <span
                className="text-xs px-1.5 py-0.5 rounded-full font-bold"
                style={{ background: color + "33", color }}
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
          <div
            className="rounded-xl py-16 text-center text-sm"
            style={{
              background: "var(--nexus-surface)",
              border: "1px solid var(--nexus-border)",
              color: "var(--nexus-muted)",
            }}
          >
            No {filter === "all" ? "" : filter} approvals.
          </div>
        ) : (
          filtered.map((a) => {
            const sc = STATUS_COLORS[a.status] ?? "#64748b";
            const isPending = a.status === "pending";
            return (
              <div
                key={a.id}
                className="rounded-xl p-5 slide-up"
                style={{
                  background: "var(--nexus-surface)",
                  border: `1px solid ${isPending ? "#f59e0b44" : "var(--nexus-border)"}`,
                }}
              >
                {/* Header row */}
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className="font-bold text-base"
                        style={{ color: "var(--nexus-text)" }}
                      >
                        {a.tool}
                      </span>
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-semibold"
                        style={{
                          background: sc + "22",
                          color: sc,
                          border: `1px solid ${sc}44`,
                        }}
                      >
                        {a.status.toUpperCase()}
                      </span>
                      {isPending && (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full font-bold"
                          style={{
                            background: "rgba(239,68,68,0.15)",
                            color: "#ef4444",
                            border: "1px solid rgba(239,68,68,0.4)",
                          }}
                        >
                          🔴 HIGH RISK
                        </span>
                      )}
                    </div>
                    <div className="text-xs mt-1 space-x-3" style={{ color: "var(--nexus-muted)" }}>
                      <span>Agent: <b>{a.agentId}</b></span>
                      <span>Mission: <b>{a.missionId}</b></span>
                      <span>Policy: {a.policyId}</span>
                    </div>
                  </div>
                  <div className="text-xs text-right" style={{ color: "var(--nexus-muted)" }}>
                    <div>Requested</div>
                    <div>{fmt(a.createdAt)}</div>
                    {a.decidedAt && (
                      <>
                        <div className="mt-1">Decided</div>
                        <div>{fmt(a.decidedAt)}</div>
                      </>
                    )}
                  </div>
                </div>

                {/* Reason */}
                <div
                  className="text-sm mb-3 px-3 py-2 rounded-lg"
                  style={{
                    background: "rgba(245,158,11,0.08)",
                    borderLeft: "3px solid #f59e0b",
                    color: "#fcd34d",
                  }}
                >
                  ⚠ {a.reason}
                </div>

                {/* Request payload */}
                <div
                  className="rounded-lg p-3 text-xs font-mono mb-4 overflow-x-auto"
                  style={{
                    background: "#0a0f1e",
                    border: "1px solid var(--nexus-border)",
                    color: "#94a3b8",
                  }}
                >
                  {JSON.stringify(a.request, null, 2)}
                </div>

                {/* Actions */}
                {isPending && (
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleDecide(a.id, "granted")}
                      disabled={loading}
                      className="flex-1 py-2.5 rounded-xl text-sm font-bold transition-all"
                      style={{
                        background: "rgba(16,185,129,0.15)",
                        color: "#10b981",
                        border: "1px solid rgba(16,185,129,0.5)",
                      }}
                      onMouseEnter={(e) =>
                        ((e.currentTarget as HTMLElement).style.background =
                          "rgba(16,185,129,0.3)")
                      }
                      onMouseLeave={(e) =>
                        ((e.currentTarget as HTMLElement).style.background =
                          "rgba(16,185,129,0.15)")
                      }
                    >
                      ✓ Approve
                    </button>
                    <button
                      onClick={() => handleDecide(a.id, "denied")}
                      disabled={loading}
                      className="flex-1 py-2.5 rounded-xl text-sm font-bold transition-all"
                      style={{
                        background: "rgba(239,68,68,0.15)",
                        color: "#ef4444",
                        border: "1px solid rgba(239,68,68,0.5)",
                      }}
                      onMouseEnter={(e) =>
                        ((e.currentTarget as HTMLElement).style.background =
                          "rgba(239,68,68,0.3)")
                      }
                      onMouseLeave={(e) =>
                        ((e.currentTarget as HTMLElement).style.background =
                          "rgba(239,68,68,0.15)")
                      }
                    >
                      ✕ Deny
                    </button>
                  </div>
                )}

                {!isPending && a.decidedBy && (
                  <div
                    className="text-xs text-right"
                    style={{ color: "var(--nexus-muted)" }}
                  >
                    Decided by <b>{a.decidedBy}</b>
                    {a.decidedAt && ` · ${fmt(a.decidedAt)}`}
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
