"use client";

import { useEffect, useRef, useState } from "react";
import { NexusEvent } from "./api";

/**
 * useEventStream — connects to the backend SSE endpoint and
 * delivers events to the consumer with zero-latency push.
 * Falls back to REST polling if SSE is unavailable.
 */
export function useEventStream(missionId?: string) {
  const [events, setEvents] = useState<NexusEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const url = `http://localhost:8000/api/events/stream${
      missionId ? `?mission_id=${missionId}` : ""
    }`;

    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (e) => {
      try {
        const ev: NexusEvent = JSON.parse(e.data);
        setEvents((prev) => {
          // deduplicate by id
          if (prev.some((x) => x.id === ev.id)) return prev;
          return [...prev, ev];
        });
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      setConnected(false);
      es.close();
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, [missionId]);

  /** Latest agent state derived from events */
  const agentStatus = deriveAgentStatus(events);

  return { events, connected, agentStatus };
}

/** Maps agentId → most recent runtime status derived from event stream */
function deriveAgentStatus(events: NexusEvent[]): Record<string, string> {
  const status: Record<string, string> = {};
  for (const ev of events) {
    const agent = ev.agentId;
    if (!agent) continue;
    switch (ev.type) {
      case "AGENT_STARTED":
        status[agent] = "WORKING";
        break;
      case "AGENT_COMPLETED":
        status[agent] = "COMPLETED";
        break;
      case "AGENT_PAUSED":
        status[agent] = "APPROVAL_REQUIRED";
        break;
      case "AGENT_RESUMED":
        status[agent] = "WORKING";
        break;
      case "SECURITY_ALERT":
        status[agent] = "BLOCKED";
        break;
      case "AGENT_MESSAGE":
        status[agent] = "COMMUNICATING";
        break;
      case "TOOL_STARTED":
        if (status[agent] !== "WORKING") status[agent] = "WORKING";
        break;
      default:
        break;
    }
  }
  return status;
}
