"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Brain,
  Database,
  Fingerprint,
  Gavel,
  KeyRound,
  Route,
  Users,
  Wrench,
} from "lucide-react";
import {
  api,
  type AgentCard,
  type Mission,
  type MissionTask,
  type NexusEvent,
} from "@/lib/api";
import {
  eventTone,
  fmtDateTime,
  fmtRelative,
  fmtTime,
  humanize,
  initials,
  MEMORY_EVENT_TYPES,
  metaString,
  POLICY_EVENT_TYPES,
  policyOutcomeTone,
  riskTone,
  rosterStatusTone,
  runtimeTone,
  taskTone,
  TIER_DESCRIPTIONS,
  TIER_LABELS,
  tierLabel,
  toneVar,
} from "@/lib/format";
import {
  Badge,
  CodeBlock,
  Disclosure,
  EmptyState,
  ErrorState,
  KeyValue,
  LoadingState,
  PageHeader,
  Panel,
  PanelBody,
  PanelHeader,
  SearchInput,
  SectionLabel,
  SegmentedControl,
  TagList,
} from "@/components/ui";

/**
 * WORKFORCE — the agent registry and inspector.
 *
 * The inspector answers four questions in reading order: who is this agent,
 * what is it doing right now, what can it do, and what may it touch. Every
 * value on screen comes from the backend; nothing is inferred for effect.
 */

const ACTIVE_TASK_STATUSES = new Set(["in_progress", "ready", "blocked"]);
const TIER_ORDER = [1, 2, 3];

type TierFilter = "all" | 1 | 2 | 3;

interface CurrentWork {
  mission: Mission;
  task: MissionTask;
}

/** The task this agent is closest to owning right now: an in-flight task wins,
 *  otherwise the most recently started one. */
function findCurrentWork(missions: Mission[], agentId: string): CurrentWork | null {
  let best: CurrentWork | null = null;
  const rank = (work: CurrentWork) => {
    const active = ACTIVE_TASK_STATUSES.has(work.task.status) ? 1 : 0;
    const startedAt = work.task.startedAt ?? work.mission.createdAt;
    return { active, time: new Date(startedAt).getTime() || 0 };
  };

  for (const mission of missions) {
    for (const task of mission.tasks ?? []) {
      if (task.agentId !== agentId) continue;
      const candidate: CurrentWork = { mission, task };
      if (!best) {
        best = candidate;
        continue;
      }
      const a = rank(candidate);
      const b = rank(best);
      if (a.active > b.active || (a.active === b.active && a.time > b.time)) {
        best = candidate;
      }
    }
  }
  return best;
}

/** Most recent runtime status the backend recorded for this agent. */
function findRuntimeStatus(missions: Mission[], agentId: string): string {
  let latest: { status: string; time: number } | null = null;
  for (const mission of missions) {
    const status = mission.agentStates?.[agentId];
    if (!status) continue;
    const time = new Date(mission.updatedAt ?? mission.createdAt).getTime() || 0;
    if (!latest || time > latest.time) latest = { status, time };
  }
  return latest?.status ?? "IDLE";
}

// ── Roster list ────────────────────────────────────────────────────────────

function RosterRow({
  agent,
  runtime,
  selected,
  onSelect,
}: {
  agent: AgentCard;
  runtime: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected ? "true" : undefined}
        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-left transition-colors ${
          selected ? "bg-paper-2" : "hover:bg-paper-2/60"
        }`}
      >
        <span
          className="w-8 h-8 rounded flex items-center justify-center t-small font-semibold flex-none bg-paper-2 border border-paper-3 text-ink-1"
          aria-hidden="true"
          style={selected ? { borderColor: "var(--paper-4)" } : undefined}
        >
          {initials(agent.name)}
        </span>
        <span className="flex-1 min-w-0">
          <span className="block t-body font-semibold text-ink-0 truncate">
            {agent.name}
          </span>
          <span className="block t-small text-ink-2 truncate">{agent.role}</span>
        </span>
        <span
          className="w-1.5 h-1.5 rounded-full flex-none"
          style={{ background: toneVar(runtimeTone(runtime)) }}
          aria-hidden="true"
        />
        <span className="sr-only">{humanize(runtime)}</span>
      </button>
    </li>
  );
}

// ── Inspector sections ─────────────────────────────────────────────────────

function InspectorSection({
  icon: Icon,
  label,
  count,
  aside,
  children,
}: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  label: string;
  count?: number;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="pt-5 mt-5 border-t border-paper-3 first:pt-0 first:mt-0 first:border-t-0">
      <SectionLabel count={count} aside={aside} className="mb-3">
        <span className="inline-flex items-center gap-1.5">
          <Icon size={12} strokeWidth={2} aria-hidden="true" />
          {label}
        </span>
      </SectionLabel>
      {children}
    </section>
  );
}

function CurrentWorkPanel({ work }: { work: CurrentWork | null }) {
  if (!work) {
    return (
      <p className="t-small text-ink-2">
        No task assigned. This agent is not participating in any recorded mission.
      </p>
    );
  }
  const { mission, task } = work;
  const elapsed = task.startedAt ? fmtRelative(task.startedAt) : null;

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="t-body font-semibold text-ink-0">{task.title}</div>
          <div className="t-small text-ink-2 mt-0.5">
            Mission <span className="t-mono">{mission.title}</span>
          </div>
        </div>
        <Badge tone={taskTone(task.status)}>{humanize(task.status)}</Badge>
      </div>

      <KeyValue
        labelWidth="8rem"
        rows={[
          { label: "Task id", value: task.id, mono: true },
          { label: "Mission id", value: mission.id, mono: true },
          {
            label: "Attempts",
            value: `${task.attempts} of ${task.maxAttempts}`,
            mono: true,
          },
          {
            label: "Depends on",
            value:
              task.dependsOn.length > 0 ? (
                <TagList items={task.dependsOn} mono />
              ) : (
                <span className="t-small text-ink-3">Nothing — this task can start immediately</span>
              ),
          },
          {
            label: "Tools in task",
            value:
              task.tools.length > 0 ? (
                <TagList items={task.tools} mono suffix="()" />
              ) : (
                <span className="t-small text-ink-3">No tool calls declared</span>
              ),
          },
          { label: "Started", value: elapsed, mono: true },
          {
            label: "Pending tool",
            value: task.pendingTool ? `${task.pendingTool}()` : null,
            mono: true,
          },
          {
            label: "Awaiting approval",
            value: task.awaitingApprovalId,
            mono: true,
          },
        ]}
      />

      {task.reasoning && (
        <div>
          <SectionLabel className="mb-1.5">
            Reasoning
            {task.reasoningRuntime ? ` · ${task.reasoningRuntime}` : ""}
          </SectionLabel>
          <p className="t-small text-ink-1 inset p-3">{task.reasoning}</p>
        </div>
      )}

      {task.error && (
        <div
          className="inset p-3 t-small"
          style={{ borderLeftWidth: 2, borderLeftColor: toneVar("danger") }}
        >
          <span className="t-label">Error</span>
          <div className="text-ink-1 mt-1">{task.error}</div>
        </div>
      )}
    </div>
  );
}

function ActivityList({ events, emptyHint }: { events: NexusEvent[]; emptyHint: string }) {
  if (events.length === 0) {
    return <p className="t-small text-ink-2">{emptyHint}</p>;
  }
  return (
    <ol className="space-y-2.5 list-none">
      {events.map((event) => (
        <li key={event.id} className="flex gap-3">
          <span
            className="w-1.5 h-1.5 rounded-full mt-1.5 flex-none"
            style={{ background: toneVar(eventTone(event.type)) }}
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="t-small font-semibold text-ink-0">
                {humanize(event.type)}
              </span>
              <span className="t-mono text-ink-3 ml-auto">{fmtTime(event.timestamp)}</span>
            </div>
            <div className="t-small text-ink-2">{event.summary}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}

function PolicyDecisionList({ events }: { events: NexusEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="t-small text-ink-2">
        No policy evaluation recorded yet. Every tool call this agent attempts is
        checked before it runs.
      </p>
    );
  }
  return (
    <ul className="space-y-2 list-none">
      {events.map((event) => {
        const outcome =
          metaString(event.metadata, "outcome") ??
          (event.type === "POLICY_BLOCKED" ? "DENY" : "ALLOW");
        const tool = metaString(event.metadata, "tool");
        const capability = metaString(event.metadata, "capability");
        const policyId = metaString(event.metadata, "policyId");
        const reason = metaString(event.metadata, "reason");
        return (
          <li key={event.id} className="inset p-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge tone={policyOutcomeTone(outcome)}>{humanize(outcome)}</Badge>
              {tool && <span className="t-mono text-ink-0">{tool}()</span>}
              <span className="t-mono text-ink-3 ml-auto">{fmtTime(event.timestamp)}</span>
            </div>
            <KeyValue
              className="mt-2"
              labelWidth="6.5rem"
              rows={[
                { label: "Capability", value: capability, mono: true },
                { label: "Policy", value: policyId, mono: true },
                { label: "Reason", value: humanize(reason) },
              ]}
            />
          </li>
        );
      })}
    </ul>
  );
}

function AgentInspector({
  agent,
  missions,
  events,
}: {
  agent: AgentCard;
  missions: Mission[];
  events: NexusEvent[];
}) {
  const work = useMemo(() => findCurrentWork(missions, agent.id), [missions, agent.id]);
  const runtime = useMemo(() => findRuntimeStatus(missions, agent.id), [missions, agent.id]);

  const agentEvents = useMemo(
    () =>
      events
        .filter((e) => e.agentId === agent.id || e.targetAgentId === agent.id)
        .slice()
        .reverse(),
    [events, agent.id],
  );
  const memoryEvents = useMemo(
    () => agentEvents.filter((e) => (MEMORY_EVENT_TYPES as readonly string[]).includes(e.type)),
    [agentEvents],
  );
  const policyEvents = useMemo(
    () =>
      agentEvents
        .filter((e) => (POLICY_EVENT_TYPES as readonly string[]).includes(e.type))
        .slice(0, 8),
    [agentEvents],
  );
  /** Policy ids this agent has actually been evaluated against. */
  const observedPolicies = useMemo(() => {
    const ids = new Set<string>(agent.policies ?? []);
    for (const event of policyEvents) {
      const id = metaString(event.metadata, "policyId");
      if (id) ids.add(id);
    }
    return [...ids];
  }, [agent.policies, policyEvents]);

  const recentActivity = agentEvents.slice(0, 10);

  return (
    <div className="fade-in">
      {/* Identity header */}
      <div className="flex items-start gap-4 px-5 py-5 border-b border-paper-3">
        <span
          className="w-12 h-12 rounded flex items-center justify-center t-title flex-none bg-paper-2 border border-paper-3 text-ink-0"
          aria-hidden="true"
        >
          {initials(agent.name)}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="t-display text-ink-0 text-[20px]">{agent.name}</h2>
          <div className="t-body text-ink-1 mt-0.5">{agent.role}</div>
          {agent.persona?.tagline && (
            <p className="t-small text-ink-2 mt-2 max-w-xl">{agent.persona.tagline}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1.5 flex-none">
          <Badge tone={runtimeTone(runtime)}>{humanize(runtime)}</Badge>
          <Badge tone={rosterStatusTone(agent.status)}>{humanize(agent.status)}</Badge>
        </div>
      </div>

      <div className="px-5 py-5">
        <InspectorSection icon={Fingerprint} label="Identity">
          <KeyValue
            rows={[
              { label: "Agent id", value: agent.id, mono: true },
              { label: "Codename", value: agent.codename },
              { label: "Principal", value: agent.identity.principal, mono: true },
              {
                label: "Risk level",
                value: (
                  <Badge tone={riskTone(agent.identity.riskLevel)}>
                    {humanize(agent.identity.riskLevel)}
                  </Badge>
                ),
              },
              { label: "Department", value: humanize(agent.departmentId) },
              {
                label: "Tier",
                value: `${agent.tier} · ${tierLabel(agent.tier)} — ${
                  TIER_DESCRIPTIONS[agent.tier] ?? ""
                }`,
              },
              { label: "Version", value: agent.version, mono: true },
              { label: "Owner", value: agent.owner },
            ]}
          />
        </InspectorSection>

        <InspectorSection icon={Route} label="Current work">
          <CurrentWorkPanel work={work} />
        </InspectorSection>

        <InspectorSection
          icon={Brain}
          label="Capabilities"
          count={agent.capabilities.length}
        >
          <TagList
            items={agent.capabilities}
            mono
            emptyLabel="No capabilities declared on the agent card."
          />
        </InspectorSection>

        <InspectorSection icon={Wrench} label="Tools" count={agent.tools.length}>
          <TagList
            items={agent.tools}
            mono
            suffix="()"
            emptyLabel="Registered without live tool bindings — this agent cannot call tools."
          />
        </InspectorSection>

        <InspectorSection
          icon={KeyRound}
          label="Access policy"
          count={agent.identity.scopes.length}
        >
          <div className="space-y-3">
            <div>
              <div className="t-small text-ink-2 mb-1.5">
                Granted scopes. A tool call outside this set is denied before it runs.
              </div>
              <TagList items={agent.identity.scopes} mono emptyLabel="No scopes granted." />
            </div>
            {(agent.dataScopes?.length ?? 0) > 0 && (
              <div>
                <div className="t-small text-ink-2 mb-1.5">Data scopes</div>
                <TagList items={agent.dataScopes ?? []} mono />
              </div>
            )}
            <div>
              <div className="t-small text-ink-2 mb-1.5">Policies bound to this principal</div>
              <TagList
                items={observedPolicies}
                mono
                emptyLabel="Default deny — no named policy has been applied yet."
              />
            </div>
          </div>
        </InspectorSection>

        <InspectorSection icon={Gavel} label="Policy decisions" count={policyEvents.length}>
          <PolicyDecisionList events={policyEvents} />
        </InspectorSection>

        <InspectorSection icon={Database} label="Memory access" count={memoryEvents.length}>
          <ActivityList
            events={memoryEvents.slice(0, 8)}
            emptyHint="No memory read or write recorded for this agent."
          />
        </InspectorSection>

        <InspectorSection icon={Activity} label="Recent activity" count={agentEvents.length}>
          <ActivityList
            events={recentActivity}
            emptyHint="No recorded activity. This agent has not been invoked."
          />
          {agentEvents.length > 0 && (
            <Disclosure summary={`Raw event payloads (${recentActivity.length})`}>
              <CodeBlock value={recentActivity} maxHeight="22rem" />
            </Disclosure>
          )}
        </InspectorSection>

        {agent.unusualOperatorFit && (
          <InspectorSection icon={Users} label="Unusual operator fit">
            <p className="t-small text-ink-1">{agent.unusualOperatorFit}</p>
          </InspectorSection>
        )}
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function WorkforcePage() {
  const [agents, setAgents] = useState<AgentCard[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [events, setEvents] = useState<NexusEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tier, setTier] = useState<TierFilter>("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastLoadedAt, setLastLoadedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [roster, missionList, eventList] = await Promise.all([
        api.listAgents(),
        api.listMissions(),
        api.listEvents(),
      ]);
      setAgents(roster);
      setMissions(missionList);
      setEvents(eventList);
      setError(null);
      setLastLoadedAt(new Date().toISOString());
      setSelectedId((current) => current ?? roster[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return agents.filter((agent) => {
      if (tier !== "all" && agent.tier !== tier) return false;
      if (needle === "") return true;
      return [
        agent.name,
        agent.role,
        agent.codename,
        agent.departmentId,
        ...agent.capabilities,
        ...agent.tools,
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [agents, tier, search]);

  const grouped = useMemo(
    () =>
      TIER_ORDER.map((t) => ({
        tier: t,
        agents: filtered.filter((agent) => agent.tier === t),
      })).filter((group) => group.agents.length > 0),
    [filtered],
  );

  const selected = agents.find((agent) => agent.id === selectedId) ?? null;
  const tierCounts = useMemo(
    () => ({
      all: agents.length,
      1: agents.filter((a) => a.tier === 1).length,
      2: agents.filter((a) => a.tier === 2).length,
      3: agents.filter((a) => a.tier === 3).length,
    }),
    [agents],
  );

  return (
    <div className="max-w-7xl mx-auto fade-in">
      <PageHeader
        title="Workforce"
        subtitle="Every agent registered to this enterprise, the authority it holds, and what it is doing right now."
        actions={
          <div className="t-label">
            {agents.length} agents · {grouped.length || TIER_ORDER.length} tiers
          </div>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] gap-5 items-start">
        {/* Roster */}
        <Panel className="overflow-hidden xl:sticky xl:top-20">
          <div className="p-3 border-b border-paper-3 space-y-2">
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search name, role, capability, tool"
              label="Search the workforce"
            />
            <SegmentedControl
              label="Filter by tier"
              grow
              value={tier}
              onChange={setTier}
              options={[
                { value: "all" as TierFilter, label: "All", count: tierCounts.all },
                { value: 1 as TierFilter, label: TIER_LABELS[1], count: tierCounts[1] },
                { value: 2 as TierFilter, label: TIER_LABELS[2], count: tierCounts[2] },
                { value: 3 as TierFilter, label: TIER_LABELS[3], count: tierCounts[3] },
              ]}
            />
          </div>

          <div className="overflow-y-auto" style={{ maxHeight: "calc(100vh - 16rem)" }}>
            {loading && agents.length === 0 ? (
              <LoadingState label="Loading roster" />
            ) : error && agents.length === 0 ? (
              <ErrorState message={error} onRetry={load} />
            ) : grouped.length === 0 ? (
              <EmptyState
                compact
                icon={Users}
                title="No agents match"
                hint="Clear the search or widen the tier filter."
              />
            ) : (
              grouped.map((group) => (
                <div key={group.tier} className="px-2 py-2">
                  <SectionLabel count={group.agents.length} className="px-2 pb-1.5">
                    Tier {group.tier} · {tierLabel(group.tier)}
                  </SectionLabel>
                  <ul className="list-none space-y-0.5">
                    {group.agents.map((agent) => (
                      <RosterRow
                        key={agent.id}
                        agent={agent}
                        runtime={findRuntimeStatus(missions, agent.id)}
                        selected={selected?.id === agent.id}
                        onSelect={() => setSelectedId(agent.id)}
                      />
                    ))}
                  </ul>
                </div>
              ))
            )}
          </div>
        </Panel>

        {/* Inspector */}
        <Panel className="overflow-hidden">
          {selected ? (
            <AgentInspector agent={selected} missions={missions} events={events} />
          ) : loading ? (
            <LoadingState label="Loading agent" />
          ) : error ? (
            <ErrorState message={error} onRetry={load} />
          ) : (
            <>
              <PanelHeader title="Agent inspector" subtitle="Select an agent from the roster." />
              <PanelBody>
                <EmptyState
                  icon={Users}
                  title="No agent selected"
                  hint="Pick an agent to see its identity, authority, current task and audit trail."
                />
              </PanelBody>
            </>
          )}
        </Panel>
      </div>

      <p className="t-small text-ink-3 mt-4">
        {lastLoadedAt
          ? `Last refreshed ${fmtDateTime(lastLoadedAt)} · roster, missions and events are re-read every 5 seconds`
          : "Reading roster, missions and events…"}
      </p>
    </div>
  );
}
