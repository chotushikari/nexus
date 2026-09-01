"use client";

import { useEffect, useState } from "react";
import { api, AgentCard } from "@/lib/api";

const TIER_LABELS: Record<number, string> = { 1: "Core", 2: "Extended", 3: "Registry" };
const TIER_COLORS: Record<number, string> = {
  1: "#6366f1",
  2: "#06b6d4",
  3: "#64748b",
};
const STATUS_COLORS: Record<string, string> = {
  approved: "#10b981",
  experimental: "#f59e0b",
  retired: "#64748b",
  registered_only: "#7c3aed",
};

function AgentRow({
  agent,
  selected,
  onClick,
}: {
  agent: AgentCard;
  selected: boolean;
  onClick: () => void;
}) {
  const tc = TIER_COLORS[agent.tier] ?? "#64748b";
  const sc = STATUS_COLORS[agent.status] ?? "#64748b";
  return (
    <div
      onClick={onClick}
      className="flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all"
      style={{
        background: selected ? "var(--nexus-surface-2)" : "transparent",
        border: `1px solid ${selected ? tc + "66" : "transparent"}`,
      }}
      onMouseEnter={(e) => {
        if (!selected)
          (e.currentTarget as HTMLElement).style.background = "var(--nexus-surface-2)";
      }}
      onMouseLeave={(e) => {
        if (!selected) (e.currentTarget as HTMLElement).style.background = "transparent";
      }}
    >
      {/* Avatar */}
      <div
        className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm flex-shrink-0"
        style={{
          background: tc + "22",
          color: tc,
          border: `1px solid ${tc}44`,
        }}
      >
        {agent.name.split(" ").map((n) => n[0]).join("")}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-sm truncate" style={{ color: "var(--nexus-text)" }}>
          {agent.name}
        </div>
        <div className="text-xs truncate" style={{ color: "var(--nexus-muted)" }}>
          {agent.role}
        </div>
      </div>

      {/* Badges */}
      <div className="flex flex-col items-end gap-1">
        <span
          className="text-xs px-1.5 py-0.5 rounded-full font-medium"
          style={{
            background: tc + "22",
            color: tc,
            border: `1px solid ${tc}44`,
          }}
        >
          T{agent.tier}
        </span>
        <span
          className="text-xs px-1.5 py-0.5 rounded-full"
          style={{
            background: sc + "22",
            color: sc,
          }}
        >
          {agent.status.replace("_", " ")}
        </span>
      </div>
    </div>
  );
}

function AgentDetail({ agent }: { agent: AgentCard }) {
  const tc = TIER_COLORS[agent.tier] ?? "#64748b";
  return (
    <div className="space-y-4 fade-in">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-black"
          style={{
            background: `linear-gradient(135deg, ${tc}44, ${tc}22)`,
            color: tc,
            border: `2px solid ${tc}66`,
            boxShadow: `0 0 24px ${tc}44`,
          }}
        >
          {agent.name.split(" ").map((n) => n[0]).join("")}
        </div>
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--nexus-text)" }}>
            {agent.name}
          </h2>
          <div className="text-sm" style={{ color: "var(--nexus-muted)" }}>
            {agent.codename} · {agent.role}
          </div>
          <div className="text-xs mt-1" style={{ color: "var(--nexus-muted)" }}>
            Dept: {agent.departmentId} · Tier {agent.tier} ({TIER_LABELS[agent.tier]})
          </div>
        </div>
      </div>

      {/* Tagline */}
      {agent.persona?.tagline && (
        <div
          className="px-4 py-3 rounded-xl text-sm italic"
          style={{
            background: tc + "11",
            borderLeft: `3px solid ${tc}`,
            color: "var(--nexus-text)",
          }}
        >
          "{agent.persona.tagline}"
        </div>
      )}

      {/* Identity */}
      <div>
        <div className="text-xs font-semibold uppercase mb-2" style={{ color: "var(--nexus-muted)" }}>
          Identity
        </div>
        <div
          className="rounded-xl p-3 text-xs font-mono"
          style={{
            background: "#0a0f1e",
            border: "1px solid var(--nexus-border)",
            color: "#94a3b8",
          }}
        >
          <div>principal: <span style={{ color: tc }}>{agent.identity.principal}</span></div>
          <div>riskLevel: {agent.identity.riskLevel}</div>
          <div>scopes: [{agent.identity.scopes.join(", ")}]</div>
        </div>
      </div>

      {/* Capabilities */}
      {agent.capabilities.length > 0 && (
        <div>
          <div className="text-xs font-semibold uppercase mb-2" style={{ color: "var(--nexus-muted)" }}>
            Capabilities ({agent.capabilities.length})
          </div>
          <div className="flex flex-wrap gap-1">
            {agent.capabilities.map((cap) => (
              <span
                key={cap}
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: tc + "22",
                  color: tc,
                  border: `1px solid ${tc}33`,
                }}
              >
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tools */}
      {agent.tools.length > 0 && (
        <div>
          <div className="text-xs font-semibold uppercase mb-2" style={{ color: "var(--nexus-muted)" }}>
            Tools ({agent.tools.length})
          </div>
          <div className="flex flex-wrap gap-1">
            {agent.tools.map((t) => (
              <span
                key={t}
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: "rgba(100,116,139,0.2)",
                  color: "#94a3b8",
                  border: "1px solid rgba(100,116,139,0.3)",
                  fontFamily: "monospace",
                }}
              >
                {t}()
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Personality traits */}
      {agent.persona?.personality?.length > 0 && (
        <div>
          <div className="text-xs font-semibold uppercase mb-2" style={{ color: "var(--nexus-muted)" }}>
            Personality
          </div>
          <div className="flex flex-wrap gap-1">
            {agent.persona.personality.map((p) => (
              <span
                key={p}
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: "rgba(139,92,246,0.15)",
                  color: "#8b5cf6",
                  border: "1px solid rgba(139,92,246,0.3)",
                }}
              >
                {p}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentCard[]>([]);
  const [selected, setSelected] = useState<AgentCard | null>(null);
  const [filter, setFilter] = useState<"all" | 1 | 2 | 3>("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listAgents().then((data) => {
      setAgents(data);
      setSelected(data[0] ?? null);
      setLoading(false);
    });
  }, []);

  const filtered = agents.filter((a) => {
    const matchesTier = filter === "all" || a.tier === filter;
    const matchesSearch =
      search === "" ||
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.role.toLowerCase().includes(search.toLowerCase()) ||
      a.codename.toLowerCase().includes(search.toLowerCase());
    return matchesTier && matchesSearch;
  });

  return (
    <div className="max-w-7xl mx-auto fade-in">
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: "var(--nexus-text)" }}>
          Agent Roster
        </h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--nexus-muted)" }}>
          {agents.length} enterprise agents across 3 tiers
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* List */}
        <div
          className="xl:col-span-1 rounded-xl"
          style={{
            background: "var(--nexus-surface)",
            border: "1px solid var(--nexus-border)",
          }}
        >
          {/* Filters */}
          <div className="p-3 border-b space-y-2" style={{ borderColor: "var(--nexus-border)" }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search agents…"
              className="w-full px-3 py-1.5 rounded-lg text-sm outline-none"
              style={{
                background: "var(--nexus-surface-2)",
                border: "1px solid var(--nexus-border)",
                color: "var(--nexus-text)",
              }}
            />
            <div className="flex gap-1">
              {(["all", 1, 2, 3] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setFilter(t)}
                  className="flex-1 py-1 rounded-lg text-xs font-medium transition-all"
                  style={{
                    background:
                      filter === t
                        ? t === "all"
                          ? "rgba(99,102,241,0.2)"
                          : TIER_COLORS[t as number] + "22"
                        : "transparent",
                    color:
                      filter === t
                        ? t === "all"
                          ? "#6366f1"
                          : TIER_COLORS[t as number]
                        : "var(--nexus-muted)",
                    border: `1px solid ${
                      filter === t
                        ? t === "all"
                          ? "rgba(99,102,241,0.4)"
                          : TIER_COLORS[t as number] + "44"
                        : "transparent"
                    }`,
                  }}
                >
                  {t === "all" ? "All" : `T${t}`}
                </button>
              ))}
            </div>
          </div>

          {/* Agent list */}
          <div className="p-2 overflow-y-auto" style={{ maxHeight: "65vh" }}>
            {loading ? (
              <div className="text-center py-8 text-sm" style={{ color: "var(--nexus-muted)" }}>
                Loading agents…
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-8 text-sm" style={{ color: "var(--nexus-muted)" }}>
                No agents match.
              </div>
            ) : (
              filtered.map((a) => (
                <AgentRow
                  key={a.id}
                  agent={a}
                  selected={selected?.id === a.id}
                  onClick={() => setSelected(a)}
                />
              ))
            )}
          </div>
        </div>

        {/* Detail */}
        <div
          className="xl:col-span-2 rounded-xl p-6 overflow-y-auto"
          style={{
            background: "var(--nexus-surface)",
            border: "1px solid var(--nexus-border)",
            maxHeight: "80vh",
          }}
        >
          {selected ? (
            <AgentDetail agent={selected} />
          ) : (
            <div className="text-center py-16 text-sm" style={{ color: "var(--nexus-muted)" }}>
              Select an agent to view details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
