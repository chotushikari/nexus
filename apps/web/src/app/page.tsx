"use client";

/**
 * Command Center — the operator's home screen.
 *
 * Layout follows §58: the living office is the hero; a slim left rail
 * carries enterprise identity and honest capability reporting; the right
 * inspector opens on selection; a live event ticker runs along the bottom.
 * Every number on this page comes from the backend.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  AgentCard,
  Approval,
  EnterpriseSummary,
  Mission,
  ClarifyQuestion,
  NexusEvent,
} from "@/lib/api";
import { useEventStream } from "@/lib/useEventStream";
import { OfficeCanvas } from "@/components/OfficeCanvas";
import { StatusTicker, PixelLoader, type Phase } from "@/components/StatusPhrases";
import { STATE_LABEL } from "@/lib/pixel/palette";
import { EVENT_COLOR, MISSION_BADGE_CLASS, fmtTime } from "@/lib/events";

const SUGGESTIONS = [
  { label: "Validate an idea", text: "Validate my business idea: research the market, size the opportunity, and give me a go / no-go decision memo." },
  { label: "Know my competitors", text: "Research my top competitors: scrape their public pricing and positioning, and build a comparison landscape." },
  { label: "Pricing that works", text: "Research market pricing for my product category and recommend a pricing strategy with rationale." },
  { label: "Launch the GTM", text: "Build my go-to-market plan: audience, channels, first-campaign draft, and the metrics to watch." },
  { label: "Vendor onboarding", text: "Evaluate Kestrel Components as a strategic supplier and prepare the onboarding package if they satisfy our policies." },
];

// ─── Inspector ───────────────────────────────────────────────────────────────

function Inspector({
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
  const recent = events
    .filter((e) => e.agentId === agent.id || e.targetAgentId === agent.id)
    .slice(-14)
    .reverse();
  return (
    <div className="panel flex h-full flex-col overflow-hidden">
      <div className="flex items-start justify-between border-b p-3.5" style={{ borderColor: "var(--paper-3)" }}>
        <div>
          <div className="t-title" style={{ fontSize: 15 }}>{agent.name}</div>
          <div className="t-small" style={{ color: "var(--ink-2)" }}>{agent.role}</div>
        </div>
        <button onClick={onClose} className="btn h-7 w-7 !p-0" aria-label="Close inspector">✕</button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-3.5">
        <div className="flex items-center gap-2">
          <span className={`badge ${statusBadgeClass(status)}`}>
            <span className="badge-dot" />
            {STATE_LABEL[status] ?? status}
          </span>
          <span className="t-mono" style={{ color: "var(--ink-3)" }}>T{agent.tier}</span>
          <span className="t-mono" style={{ color: "var(--ink-3)" }}>{agent.version ?? "v1.0"}</span>
        </div>

        <section>
          <div className="t-label mb-1.5">Identity</div>
          <div className="inset t-mono p-2.5" style={{ color: "var(--ink-1)" }}>
            <div>principal: <span style={{ color: "var(--state-active)" }}>{agent.identity.principal}</span></div>
            <div>risk: {agent.identity.riskLevel}</div>
          </div>
        </section>

        {agent.identity.scopes.length > 0 && (
          <section>
            <div className="t-label mb-1.5">Access Scopes</div>
            <div className="flex flex-wrap gap-1">
              {agent.identity.scopes.map((s) => (
                <span key={s} className="badge s-success t-mono">{s}</span>
              ))}
            </div>
          </section>
        )}

        {agent.tools.length > 0 && (
          <section>
            <div className="t-label mb-1.5">Tools ({agent.tools.length})</div>
            <div className="flex flex-wrap gap-1">
              {agent.tools.map((t) => (
                <span key={t} className="inset t-mono px-1.5 py-0.5" style={{ fontSize: 11 }}>{t}</span>
              ))}
            </div>
          </section>
        )}

        {agent.persona?.tagline && (
          <section>
            <div className="t-label mb-1.5">Charter</div>
            <p className="t-small italic" style={{ borderLeft: "3px solid var(--paper-4)", paddingLeft: 8, color: "var(--ink-1)" }}>
              {agent.persona.tagline}
            </p>
          </section>
        )}

        <section>
          <div className="t-label mb-1.5">Recent Activity</div>
          {recent.length === 0 ? (
            <p className="t-small" style={{ color: "var(--ink-3)" }}>No events for this agent yet.</p>
          ) : (
            <div className="space-y-1.5">
              {recent.map((ev) => (
                <div key={ev.id} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 flex-none rounded-full" style={{ background: EVENT_COLOR[ev.type] ?? "var(--ink-3)" }} />
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-1.5">
                      <span className="t-mono" style={{ fontSize: 10.5, color: EVENT_COLOR[ev.type] ?? "var(--ink-2)" }}>{ev.type}</span>
                      <span className="t-mono ml-auto" style={{ fontSize: 10, color: "var(--ink-3)" }}>{fmtTime(ev.timestamp)}</span>
                    </div>
                    <div className="t-small truncate" style={{ color: "var(--ink-1)" }}>{ev.summary}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "WORKING":
    case "TOOL_CALL":
    case "PLANNING":
      return "s-active";
    case "COMMUNICATING":
      return "s-comm";
    case "COMPLETED":
      return "s-success";
    case "WAITING":
    case "PAUSED":
      return "s-warning";
    case "APPROVAL_REQUIRED":
      return "s-approval";
    case "BLOCKED":
    case "FAILED":
      return "s-danger";
    default:
      return "s-neutral";
  }
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function CommandCenterPage() {
  const [enterprise, setEnterprise] = useState<EnterpriseSummary | null>(null);
  const [agents, setAgents] = useState<AgentCard[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [objective, setObjective] = useState("");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [booting, setBooting] = useState(true);
  // Chief-of-staff clarify loop: understanding → questions → refined launch.
  const [phase, setPhase] = useState<"idle" | "understanding" | "clarify">("idle");
  const [questions, setQuestions] = useState<ClarifyQuestion[]>([]);
  const [clarifySource, setClarifySource] = useState<string>("");
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const { events, connected, agentStatus } = useEventStream();

  const refresh = useCallback(async () => {
    const [m, a] = await Promise.all([api.listMissions(), api.listApprovals()]);
    setMissions(m);
    setApprovals(a);
  }, []);

  useEffect(() => {
    Promise.all([api.enterprise().then(setEnterprise), api.listAgents().then(setAgents)])
      .catch(() => {})
      .finally(() => setBooting(false));
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);

  const seed = async () => {
    setLaunching(true);
    try {
      await api.seed();
      setAgents(await api.listAgents());
      setEnterprise(await api.enterprise());
    } catch (e) {
      setError(String(e));
    } finally {
      setLaunching(false);
    }
  };

  const startMission = async (finalObjective: string) => {
    setLaunching(true);
    setError(null);
    try {
      await api.startMission({
        objective: finalObjective,
        title: finalObjective.length > 60 ? finalObjective.slice(0, 57) + "…" : finalObjective,
        vendorId: enterprise?.defaultVendorId,
      });
      setObjective("");
      setPhase("idle");
      setQuestions([]);
      setAnswers({});
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setLaunching(false);
    }
  };

  const launch = async () => {
    const text = objective.trim();
    if (!text || launching || phase !== "idle") return;
    // Chief-of-staff pass: understand before planning. Any failure here
    // degrades straight to a raw launch — never a dead end for the founder.
    setPhase("understanding");
    setError(null);
    try {
      const result = await api.clarify(text);
      if (result.questions.length === 0) {
        await startMission(text);
        return;
      }
      setQuestions(result.questions);
      setClarifySource(result.source);
      setPhase("clarify");
    } catch {
      await startMission(text);
    }
  };

  const launchWithAnswers = async () => {
    const text = objective.trim();
    if (!text) return;
    const context = questions
      .map((q) => {
        const a = (answers[q.id] ?? "").trim();
        return a ? `Q: ${q.question} A: ${a}` : null;
      })
      .filter(Boolean)
      .join(" | ");
    const refined = context
      ? `${text}\n\nFounder context from clarifying questions: ${context}`
      : text;
    await startMission(refined);
  };

  const decide = async (id: string, decision: "granted" | "denied") => {
    try {
      await api.decideApproval(id, decision);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  };

  // Latest mission by creation time — the list order is not guaranteed.
  const mission = useMemo(
    () =>
      missions
        .slice()
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0] ?? null,
    [missions],
  );
  const pending = approvals.filter((a) => a.status === "pending");
  const selected = agents.find((a) => a.id === selectedAgentId) ?? null;
  const alerts = events.filter((e) => ["SECURITY_ALERT", "POLICY_BLOCKED"].includes(e.type));

  const taskStats = useMemo(() => {
    if (!mission?.tasks) return null;
    const done = mission.tasks.filter((t) => t.status === "completed").length;
    return { done, total: mission.tasks.length };
  }, [mission]);

  const counts = enterprise?.counts;

  return (
    <div className="flex min-h-0 flex-col" style={{ height: "calc(100vh - 56px)" }}>
      <div className="flex min-h-0 flex-1 gap-3 p-3">
        {/* ── Left rail ── */}
        <aside className="hidden w-56 flex-none flex-col gap-3 overflow-y-auto lg:flex">
          <div className="panel p-3.5">
            <div className="t-label">Enterprise</div>
            <div className="t-title mt-0.5">{enterprise?.name ?? "—"}</div>
            <div className="t-small mt-0.5" style={{ color: "var(--ink-2)" }}>
              {enterprise?.environment ?? "local"} · {enterprise?.storeBackend ?? "memory"}
            </div>
            <div className="mt-2 flex items-center gap-1.5">
              <span className={`badge ${connected ? "s-success" : "s-danger"}`}>
                <span className="badge-dot" />
                {connected ? "Stream live" : "Reconnecting"}
              </span>
            </div>
          </div>

          <div className="panel space-y-1.5 p-3.5">
            <div className="t-label mb-1">Fleet</div>
            {[
              { k: "Agents online", v: counts ? `${counts.agentsOnline}/${counts.agentsTotal}` : "—" },
              { k: "Departments", v: counts?.departments ?? agents.length ? String(counts?.departments ?? 0) : "—" },
              { k: "Missions", v: counts ? String(counts.missionsTotal) : "—" },
              { k: "Approvals", v: counts ? String(counts.approvalsPending) : "—" },
              { k: "Security alerts", v: counts ? String(counts.securityAlerts) : "—" },
            ].map(({ k, v }) => (
              <div key={k} className="flex items-center justify-between">
                <span className="t-small" style={{ color: "var(--ink-2)" }}>{k}</span>
                <span className="t-mono font-semibold" style={{ color: "var(--ink-0)" }}>{v}</span>
              </div>
            ))}
          </div>

          <div className="panel p-3.5">
            <div className="t-label mb-1.5">Runtime Capabilities</div>
            <div className="space-y-1.5">
              {enterprise
                ? ([
                    ["gemini", enterprise.capabilities.gemini],
                    ["google-adk", enterprise.capabilities.adk],
                    ["firestore", enterprise.capabilities.firestore],
                  ] as const).map(([k, ok]) => (
                    <div key={k} className="flex items-center justify-between">
                      <span className="t-mono" style={{ fontSize: 11, color: "var(--ink-1)" }}>{k}</span>
                      <span className={`badge ${ok ? "s-success" : "s-neutral"}`}>
                        {ok ? "live" : "not configured"}
                      </span>
                    </div>
                  ))
                : null}
            </div>
            <p className="t-small mt-2" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
              Reported from proven code paths, not configuration.
            </p>
          </div>

          {agents.length === 0 && (
            <button className="btn btn-primary" onClick={seed} disabled={launching}>
              Initialize Enterprise
            </button>
          )}
        </aside>

        {/* ── Office hero ── */}
        <main className="panel relative flex min-w-0 flex-1 flex-col overflow-hidden">
          {/* Command bar */}
          <div className="border-b p-3" style={{ borderColor: "var(--paper-3)", background: "var(--paper-0)" }}>
            <div className="flex items-center gap-2">
              <input
                className="input"
                style={{ boxShadow: "none" }}
                placeholder="What should your enterprise accomplish?"
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && launch()}
                aria-label="Mission objective"
              />
              <button className="btn btn-primary flex-none" onClick={launch} disabled={launching || !objective.trim() || phase !== "idle"}>
                {phase === "understanding" ? "Understanding…" : launching ? "Planning…" : "Start Mission"}
              </button>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.label}
                  className="inset t-small px-2 py-0.5 transition-colors hover:border-[var(--ink-3)]"
                  style={{ color: "var(--ink-1)" }}
                  onClick={() => setObjective(s.text)}
                >
                  {s.label}
                </button>
              ))}
              {mission && (
                <span className={`badge ${MISSION_BADGE_CLASS[mission.status] ?? "s-neutral"} ml-auto`}>
                  <span className="badge-dot" />
                  {mission.status.replace("_", " ")}
                  {taskStats ? ` · ${taskStats.done}/${taskStats.total} tasks` : ""}
                </span>
              )}
              {mission?.planSource && (
                <span className="badge s-neutral t-mono" style={{ fontSize: 9.5 }}>
                  planner: {mission.planSource === "gemini" ? mission.planModel ?? "gemini" : "deterministic"}
                </span>
              )}
            </div>
            {mission && (
              <div className="mt-2 flex items-center gap-2">
                <div className="h-1 flex-1 overflow-hidden rounded-full" style={{ background: "var(--paper-2)" }}>
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: taskStats ? `${(taskStats.done / Math.max(1, taskStats.total)) * 100}%` : "0%",
                      background: "var(--state-active)",
                    }}
                  />
                </div>
                <span className="t-mono" style={{ fontSize: 10.5, color: "var(--ink-2)" }}>
                  {mission.title}
                </span>
              </div>
            )}
            {mission &&
              ["planning", "running", "awaiting_approval"].includes(mission.status) && (
                <StatusTicker
                  compact
                  phase={
                    mission.status === "planning"
                      ? "planning"
                      : mission.status === "awaiting_approval"
                        ? "approval"
                        : "executing"
                  }
                />
              )}
          </div>

          {/* Approval banners */}
          {pending.length > 0 && (
            <div className="slide-up space-y-2 border-b p-3" style={{ borderColor: "var(--paper-3)", background: "var(--wash-approval)" }}>
              {pending.map((ap) => (
                <div key={ap.id} className="panel flex items-center gap-3 p-2.5" style={{ borderColor: "var(--state-approval)" }}>
                  <div className="min-w-0 flex-1">
                    <div className="t-small font-semibold" style={{ color: "var(--state-approval)" }}>
                      Approval required — {ap.tool}
                    </div>
                    <div className="t-small truncate" style={{ color: "var(--ink-1)" }}>
                      {agents.find((a) => a.id === ap.agentId)?.name ?? ap.agentId} · {ap.reason}
                    </div>
                  </div>
                  <button className="btn btn-approve flex-none" onClick={() => decide(ap.id, "granted")}>Approve</button>
                  <button className="btn btn-deny flex-none" onClick={() => decide(ap.id, "denied")}>Deny</button>
                </div>
              ))}
            </div>
          )}

          {error && (
            <div className="px-3 pt-2">
              <div className="badge s-danger w-full justify-start !py-1.5">{error}</div>
            </div>
          )}

          {/* The office */}
          <div className="relative min-h-0 flex-1">
            {agents.length > 0 ? (
              <OfficeCanvas
                departments={enterprise?.departments ?? []}
                agents={agents}
                agentStatus={agentStatus}
                events={events}
                selectedAgentId={selectedAgentId}
                onSelectAgent={(id) => setSelectedAgentId(id || null)}
              />
            ) : booting ? (
              <div className="flex h-full flex-col items-center justify-center gap-2">
                <PixelLoader size={7} />
                <StatusTicker phase="booting" />
              </div>
            ) : (
              <div className="flex h-full items-center justify-center">
                <div className="text-center">
                  <div className="t-title" style={{ color: "var(--ink-2)" }}>The office is empty</div>
                  <p className="t-small mt-1" style={{ color: "var(--ink-3)" }}>
                    Initialize the enterprise to staff {enterprise?.name ?? "HQ"}.
                  </p>
                  <button className="btn btn-primary mt-3" onClick={seed} disabled={launching}>
                    {launching ? "Hiring…" : "Initialize Enterprise"}
                  </button>
                </div>
              </div>
            )}

            {/* ── Chief-of-staff clarify overlay ── */}
            {phase !== "idle" && (
              <div
                className="slide-up absolute inset-3 z-40 flex items-center justify-center rounded-lg"
                style={{ background: "rgba(235,228,212,0.72)", backdropFilter: "blur(3px)" }}
              >
                <div className="panel max-h-full w-full max-w-xl overflow-y-auto p-5" style={{ boxShadow: "var(--shadow-3)" }}>
                  {phase === "understanding" || launching ? (
                    <div className="flex flex-col items-center gap-2 py-6">
                      <PixelLoader size={8} />
                      <div className="t-title" style={{ fontSize: 15 }}>
                        {launching ? "Deploying to the floor…" : "NEXUS is understanding your objective"}
                      </div>
                      <StatusTicker phase={launching ? "planning" : "understanding"} />
                    </div>
                  ) : (
                    <>
                      <div className="flex items-baseline justify-between gap-3">
                        <div>
                          <div className="t-title" style={{ fontSize: 15 }}>
                            Before the floor starts moving — a few questions
                          </div>
                          <div className="t-small" style={{ color: "var(--ink-2)" }}>
                            Every answer sharpens the plan. Skip freely; answer with a chip or your own words.
                          </div>
                        </div>
                        <span className="badge s-neutral t-mono flex-none" style={{ fontSize: 9.5 }}>
                          asked by {clarifySource === "gemini" ? "gemini" : "nexus"}
                        </span>
                      </div>

                      <div className="mt-4 space-y-4">
                        {questions.map((q, qi) => (
                          <div key={q.id} className="inset p-3">
                            <div className="flex items-baseline gap-2">
                              <span className="t-mono" style={{ fontSize: 10, color: "var(--ink-3)" }}>
                                {String(qi + 1).padStart(2, "0")}
                              </span>
                              <div className="t-body font-semibold" style={{ color: "var(--ink-0)" }}>
                                {q.question}
                              </div>
                            </div>
                            {q.why && (
                              <div className="t-small mt-0.5 italic" style={{ color: "var(--ink-3)" }}>
                                {q.why}
                              </div>
                            )}
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {(q.suggestions ?? []).map((s) => {
                                const active = answers[q.id] === s;
                                return (
                                  <button
                                    key={s}
                                    className="t-small rounded px-2 py-1 transition-colors"
                                    style={{
                                      background: active ? "var(--ink-0)" : "var(--paper-0)",
                                      color: active ? "var(--paper-0)" : "var(--ink-1)",
                                      border: `1px solid ${active ? "var(--ink-0)" : "var(--paper-4)"}`,
                                    }}
                                    onClick={() =>
                                      setAnswers((prev) => ({ ...prev, [q.id]: active ? "" : s }))
                                    }
                                  >
                                    {s}
                                  </button>
                                );
                              })}
                            </div>
                            <input
                              className="input mt-2"
                              style={{ padding: "6px 10px", fontSize: 12.5 }}
                              placeholder="…or answer in your own words"
                              value={answers[q.id] ?? ""}
                              onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                            />
                          </div>
                        ))}
                      </div>

                      <div className="mt-4 flex items-center gap-2">
                        <button
                          className="btn btn-primary flex-1"
                          onClick={launchWithAnswers}
                          disabled={launching}
                        >
                          {launching ? "Deploying…" : "Launch with answers"}
                        </button>
                        <button
                          className="btn flex-none"
                          onClick={() => startMission(objective.trim())}
                          disabled={launching}
                        >
                          Skip — just launch
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </main>

        {/* ── Inspector ── */}
        <aside className="hidden w-80 flex-none xl:block">
          {selected ? (
            <Inspector
              agent={selected}
              status={agentStatus[selected.id] ?? selected.status ?? "IDLE"}
              events={events}
              onClose={() => setSelectedAgentId(null)}
            />
          ) : (
            <div className="panel flex h-full flex-col items-center justify-center p-6 text-center">
              <div className="t-label mb-2">Inspector</div>
              <p className="t-small" style={{ color: "var(--ink-3)" }}>
                Select an employee on the floor to inspect identity, scopes, tools and live activity.
              </p>
              {alerts.length > 0 && (
                <div className="inset mt-4 w-full p-2.5 text-left">
                  <div className="t-label mb-1" style={{ color: "var(--state-danger)" }}>Latest Security Signal</div>
                  <div className="t-small" style={{ color: "var(--ink-1)" }}>
                    {alerts[alerts.length - 1].summary}
                  </div>
                </div>
              )}
            </div>
          )}
        </aside>
      </div>

      {/* ── Event ticker ── */}
      <footer
        className="flex flex-none items-center gap-4 overflow-x-auto border-t px-4 py-2"
        style={{ borderColor: "var(--paper-3)", background: "var(--paper-0)" }}
      >
        <span className="t-label flex-none" style={{ color: connected ? "var(--state-success)" : "var(--ink-3)" }}>
          {connected ? "● Live" : "○ Offline"}
        </span>
        {events.length === 0 ? (
          <span className="t-small" style={{ color: "var(--ink-3)" }}>
            No runtime events yet — start a mission and the floor comes alive.
          </span>
        ) : (
          events.slice(-6).reverse().map((ev) => (
            <span key={ev.id} className="flex flex-none items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: EVENT_COLOR[ev.type] ?? "var(--ink-3)" }} />
              <span className="t-mono" style={{ fontSize: 10.5, color: EVENT_COLOR[ev.type] ?? "var(--ink-2)" }}>{ev.type}</span>
              <span className="t-small" style={{ color: "var(--ink-1)" }}>{ev.summary}</span>
              <span className="t-mono" style={{ fontSize: 10, color: "var(--ink-3)" }}>{fmtTime(ev.timestamp)}</span>
            </span>
          ))
        )}
      </footer>
    </div>
  );
}

