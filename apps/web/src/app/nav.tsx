"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  type CapabilityReport,
  type EnterpriseCounts,
  type EnterpriseSummary,
} from "@/lib/api";
import { toneVar, type Tone } from "@/lib/format";

/**
 * Operator top bar.
 *
 * Everything here is read from the backend: the enterprise name comes from
 * `/api/enterprise` (never hard-coded), the counters from the same payload,
 * and the health dot from `/api/health`. The base URL comes from `lib/api`
 * so this file has no idea what host it is talking to.
 */

const LINKS = [
  { href: "/", label: "Command Center" },
  { href: "/missions", label: "Mission Control" },
  { href: "/agents", label: "Workforce" },
  { href: "/approvals", label: "Approvals" },
  { href: "/security", label: "Security" },
];

type Health = "unknown" | "online" | "offline";

const HEALTH_TONE: Record<Health, Tone> = {
  unknown: "neutral",
  online: "success",
  offline: "danger",
};

const HEALTH_LABEL: Record<Health, string> = {
  unknown: "Checking",
  online: "Backend online",
  offline: "Backend unreachable",
};

/** Plain-language summary of the honest capability report, for the tooltip. */
function capabilitySummary(report?: CapabilityReport | null): string {
  if (!report) return "Capability report unavailable";
  const flags: [string, boolean][] = [
    ["Gemini", report.gemini],
    ["ADK", report.adk],
    ["Firestore", report.firestore],
  ];
  return flags
    .map(([name, live]) => {
      const detail = report.details?.[name.toLowerCase()];
      return `${name}: ${live ? "live" : "not active"}${detail ? ` — ${detail}` : ""}`;
    })
    .join("\n");
}

function Counter({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | null;
  tone: Tone;
}) {
  return (
    <div className="flex items-baseline gap-1.5" title={`${label}: ${value ?? "unknown"}`}>
      <span
        className="t-mono font-semibold"
        style={{ color: value === null ? "var(--ink-3)" : toneVar(tone) }}
      >
        {value ?? "—"}
      </span>
      <span className="t-label">{label}</span>
    </div>
  );
}

export default function Nav() {
  const pathname = usePathname();
  const [health, setHealth] = useState<Health>("unknown");
  const [capabilities, setCapabilities] = useState<CapabilityReport | null>(null);
  const [enterprise, setEnterprise] = useState<EnterpriseSummary | null>(null);

  const poll = useCallback(async () => {
    try {
      const report = await api.health();
      setHealth(report.status === "ok" ? "online" : "offline");
      setCapabilities(report.capabilities ?? null);
    } catch {
      setHealth("offline");
    }
    try {
      setEnterprise(await api.enterprise());
    } catch {
      // Leave the last known identity in place rather than flashing a
      // placeholder company name on a transient failure.
    }
  }, []);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 6000);
    return () => clearInterval(id);
  }, [poll]);

  const counts: EnterpriseCounts | null = enterprise?.counts ?? null;

  return (
    <header className="sticky top-0 z-50 border-b border-paper-3 bg-paper-0/90 backdrop-blur-md">
      <div className="flex items-center gap-6 px-6 h-14">
        {/* Identity — name and environment come from the backend */}
        <Link href="/" className="flex items-center gap-2.5 no-underline group flex-none">
          <span
            className="w-7 h-7 rounded flex items-center justify-center t-mono font-semibold bg-paper-2 border border-paper-4 text-ink-0"
            aria-hidden="true"
          >
            N
          </span>
          <span className="flex flex-col leading-tight">
            <span className="t-title text-ink-0">{enterprise?.name ?? "NEXUS"}</span>
            <span className="t-label">
              {enterprise
                ? `${enterprise.environment}${enterprise.demoMode ? " · demo data" : ""}`
                : "Enterprise operating environment"}
            </span>
          </span>
        </Link>

        {/* Sections */}
        <nav aria-label="Primary" className="flex items-center gap-0.5 min-w-0">
          {LINKS.map(({ href, label }) => {
            const active =
              pathname === href || (href !== "/" && (pathname ?? "").startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`px-3 py-1.5 rounded t-small font-semibold no-underline whitespace-nowrap transition-colors ${
                  active
                    ? "bg-paper-2 text-ink-0"
                    : "text-ink-2 hover:text-ink-0 hover:bg-paper-2/60"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Live counts + health */}
        <div className="ml-auto flex items-center gap-5 flex-none">
          <div className="hidden xl:flex items-center gap-5">
            <Counter label="Agents online" value={counts?.agentsOnline ?? null} tone="success" />
            <Counter
              label="Missions active"
              value={counts?.missionsActive ?? null}
              tone={counts && counts.missionsActive > 0 ? "active" : "neutral"}
            />
            <Counter
              label="Approvals pending"
              value={counts?.approvalsPending ?? null}
              tone={counts && counts.approvalsPending > 0 ? "approval" : "neutral"}
            />
            <Counter
              label="Security alerts"
              value={counts?.securityAlerts ?? null}
              tone={counts && counts.securityAlerts > 0 ? "danger" : "neutral"}
            />
          </div>

          <div
            className="flex items-center gap-2 pl-5 border-l border-paper-3"
            title={capabilitySummary(capabilities)}
          >
            <span
              className="w-2 h-2 rounded-full flex-none"
              style={{ background: toneVar(HEALTH_TONE[health]) }}
              aria-hidden="true"
            />
            <span className="t-label">{HEALTH_LABEL[health]}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
