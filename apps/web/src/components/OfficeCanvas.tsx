"use client";

/**
 * OfficeCanvas — the living office.
 *
 * A Canvas2D pixel-art renderer wired ONLY to real runtime state: agent
 * status derived from the SSE event stream, tool badges from TOOL_STARTED,
 * message lines from AGENT_MESSAGE, approval routing from approval events,
 * security flashes from SECURITY_ALERT. There are no ambient "AI is
 * thinking" animations (§10) — every moving pixel traces to an event.
 *
 * The static floor (carpet, walls, furniture) is prerendered once to an
 * offscreen canvas; agents and effects are drawn every frame. Nameplates
 * are DOM elements positioned imperatively so text stays crisp at any zoom
 * and agents remain clickable (§34).
 */

import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  buildScene,
  type LayoutAgent,
  type LayoutDept,
  type Rect,
  type Scene,
  type Seat,
} from "@/lib/office/layout";
import { PAPER, STATE, STATE_LABEL, agentTraits } from "@/lib/pixel/palette";
import {
  drawBookshelf,
  drawCabinet,
  drawCarpet,
  drawChair,
  drawCorridor,
  drawDesk,
  drawMat,
  drawMeetingTable,
  drawPerson,
  drawPlant,
  drawRack,
  drawStairs,
  drawWalls,
  drawWaterCooler,
  drawWhiteboard,
  px as rect,
  type Ctx,
} from "@/lib/pixel/render";
import type { AgentCard, NexusEvent } from "@/lib/api";

const RACK_DEPTS = ["security", "data", "engineering", "infrastructure"];
const MEETING_DEPTS = ["executive"];

interface MsgAnim {
  id: string;
  from: { x: number; y: number };
  to: { x: number; y: number };
  start: number;
}
interface Flash {
  key: string;
  rect: Rect;
  start: number;
}

interface Camera {
  cx: number;
  cy: number;
  zoom: number;
  tcx: number;
  tcy: number;
  tzoom: number;
}

export interface OfficeCanvasProps {
  departments: LayoutDept[];
  agents: AgentCard[];
  agentStatus: Record<string, string>;
  events: NexusEvent[];
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
}

export function OfficeCanvas({
  departments,
  agents,
  agentStatus,
  events,
  selectedAgentId,
  onSelectAgent,
}: OfficeCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const staticRef = useRef<HTMLCanvasElement | null>(null);
  const cameraRef = useRef<Camera>({ cx: 0, cy: 0, zoom: 0.5, tcx: 0, tcy: 0, tzoom: 0.5 });
  const sizeRef = useRef({ w: 1, h: 1 });
  const fittedRef = useRef(false);

  const msgsRef = useRef<MsgAnim[]>([]);
  const flashesRef = useRef<Flash[]>([]);
  const toolRef = useRef<Map<string, { tool: string; until: number }>>(new Map());
  const approvalRef = useRef<Map<string, { to: { x: number; y: number }; start: number }>>(new Map());
  const lastEventRef = useRef(0);

  // ── Scene ────────────────────────────────────────────────────────────────
  const layoutAgents: LayoutAgent[] = useMemo(
    () => agents.map((a) => ({ id: a.id, name: a.name, departmentId: a.departmentId })),
    [agents],
  );
  const scene: Scene = useMemo(
    () => buildScene(departments, layoutAgents),
    [departments, layoutAgents],
  );

  const seatIndex = useMemo(() => {
    const m = new Map<string, { x: number; y: number }>();
    for (const room of scene.rooms)
      for (const s of room.seats)
        if (s.agentId) m.set(s.agentId, { x: s.x + 6, y: s.y + 10 });
    const fallback = new Map(scene.rooms.map((r) => [r.deptId, r.focus]));
    return { seat: m, fallback };
  }, [scene]);

  const locate = useCallback(
    (agentId?: string): { x: number; y: number } | null => {
      if (!agentId) return null;
      if (seatIndex.seat.has(agentId)) return seatIndex.seat.get(agentId)!;
      const dept = agents.find((a) => a.id === agentId)?.departmentId;
      return (dept && seatIndex.fallback.get(dept)) || null;
    },
    [seatIndex, agents],
  );

  // ── Static layer: the whole building, prerendered once ───────────────────
  useEffect(() => {
    const c = document.createElement("canvas");
    c.width = scene.world.w;
    c.height = scene.world.h;
    const ctx = c.getContext("2d")!;
    drawBuilding(ctx, scene, RACK_DEPTS, MEETING_DEPTS);
    staticRef.current = c;
  }, [scene]);

  // ── Event-driven animations ──────────────────────────────────────────────
  useEffect(() => {
    const now = performance.now();
    for (; lastEventRef.current < events.length; lastEventRef.current++) {
      const ev = events[lastEventRef.current];
      const from = locate(ev.agentId);
      const to = locate(ev.targetAgentId);
      switch (ev.type) {
        case "AGENT_MESSAGE":
          if (from && to)
            msgsRef.current.push({ id: ev.id, from, to, start: now });
          break;
        case "TOOL_STARTED": {
          const tool =
            (ev.metadata?.tool as string) || ev.summary.split(" ")[0] || "tool";
          if (ev.agentId)
            toolRef.current.set(ev.agentId, { tool, until: now + 5200 });
          break;
        }
        case "APPROVAL_REQUESTED": {
          const exec = scene.rooms.find((r) => MEETING_DEPTS.some((m) => r.deptId.includes(m)));
          if (from && exec && ev.agentId)
            approvalRef.current.set(ev.agentId, { to: exec.focus, start: now });
          break;
        }
        case "APPROVAL_GRANTED":
        case "APPROVAL_DENIED":
          if (ev.agentId) approvalRef.current.delete(ev.agentId);
          break;
        case "SECURITY_ALERT": {
          const dept = agents.find((a) => a.id === ev.agentId)?.departmentId;
          const room = scene.rooms.find((r) => r.deptId === dept);
          if (room)
            flashesRef.current.push({
              key: ev.id,
              rect: room.rect,
              start: now,
            });
          break;
        }
        case "MISSION_COMPLETED":
        case "MISSION_FAILED":
          toolRef.current.clear();
          approvalRef.current.clear();
          break;
      }
    }
  }, [events, locate, scene, agents]);

  // ── Camera: fit on mount, follow selection ───────────────────────────────
  useEffect(() => {
    if (!selectedAgentId) return;
    const p = locate(selectedAgentId);
    if (!p) return;
    const cam = cameraRef.current;
    cam.tcx = p.x;
    cam.tcy = p.y + 20;
    cam.tzoom = Math.max(cam.tzoom, 1.6);
  }, [selectedAgentId, locate]);

  // ── Render loop ──────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current!;
    const container = containerRef.current!;
    const ctx = canvas.getContext("2d")!;

    const ro = new ResizeObserver(() => {
      const r = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      sizeRef.current = { w: r.width, h: r.height };
      canvas.width = Math.max(1, Math.round(r.width * dpr));
      canvas.height = Math.max(1, Math.round(r.height * dpr));
      canvas.style.width = `${r.width}px`;
      canvas.style.height = `${r.height}px`;
      if (!fittedRef.current && r.width > 10) {
        fittedRef.current = true;
        const cam = cameraRef.current;
        const fit = Math.min(
          r.width / (scene.world.w + 60),
          r.height / (scene.world.h + 60),
        );
        cam.zoom = cam.tzoom = fit;
        cam.cx = cam.tcx = scene.world.x + scene.world.w / 2;
        cam.cy = cam.tcy = scene.world.y + scene.world.h / 2;
      }
    });
    ro.observe(container);

    let raf = 0;
    let last = performance.now();

    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const { w, h } = sizeRef.current;
      const dpr = window.devicePixelRatio || 1;
      const cam = cameraRef.current;

      // smooth camera
      const k = 1 - Math.pow(0.0015, dt);
      cam.cx += (cam.tcx - cam.cx) * k;
      cam.cy += (cam.tcy - cam.cy) * k;
      cam.zoom += (cam.tzoom - cam.zoom) * k;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.imageSmoothingEnabled = cam.zoom < 1;

      const s2x = (wx: number) => (wx - cam.cx) * cam.zoom + w / 2;
      const s2y = (wy: number) => (wy - cam.cy) * cam.zoom + h / 2;

      // static building
      const st = staticRef.current;
      if (st) {
        ctx.drawImage(
          st,
          s2x(scene.world.x),
          s2y(scene.world.y),
          scene.world.w * cam.zoom,
          scene.world.h * cam.zoom,
        );
      }

      // security flashes (3s)
      flashesRef.current = flashesRef.current.filter((f) => now - f.start < 3000);
      for (const f of flashesRef.current) {
        const t = (now - f.start) / 3000;
        ctx.fillStyle = `rgba(166,61,47,${(0.16 * (1 - t)) * (0.6 + 0.4 * Math.sin(now / 90))})`;
        ctx.fillRect(
          s2x(f.rect.x),
          s2y(f.rect.y),
          f.rect.w * cam.zoom,
          f.rect.h * cam.zoom,
        );
      }

      // approval routes: agent → executive
      for (const [aid, r] of approvalRef.current) {
        const p = locate(aid);
        if (!p) continue;
        dashedLine(
          ctx,
          s2x(p.x),
          s2y(p.y),
          s2x(r.to.x),
          s2y(r.to.y),
          "#c8860d",
          cam.zoom,
          now,
        );
      }

      // message lines (2.2s)
      msgsRef.current = msgsRef.current.filter((m) => now - m.start < 2200);
      for (const m of msgsRef.current) {
        const t = (now - m.start) / 2200;
        const alpha = t < 0.8 ? 1 : 1 - (t - 0.8) / 0.2;
        const mx = (m.from.x + m.to.x) / 2;
        const my = (m.from.y + m.to.y) / 2 - 40;
        ctx.strokeStyle = `rgba(74,111,138,${0.75 * alpha})`;
        ctx.lineWidth = Math.max(1, 1.5 * cam.zoom);
        ctx.setLineDash([4 * cam.zoom, 4 * cam.zoom]);
        ctx.lineDashOffset = -now / 24;
        ctx.beginPath();
        ctx.moveTo(s2x(m.from.x), s2y(m.from.y));
        ctx.quadraticCurveTo(s2x(mx), s2y(my), s2x(m.to.x), s2y(m.to.y));
        ctx.stroke();
        ctx.setLineDash([]);
        // travelling dot
        const qt = 0.15 + 0.7 * ((now - m.start) / 1600);
        const qx =
          (1 - qt) * (1 - qt) * m.from.x + 2 * (1 - qt) * qt * mx + qt * qt * m.to.x;
        const qy =
          (1 - qt) * (1 - qt) * m.from.y + 2 * (1 - qt) * qt * my + qt * qt * m.to.y;
        ctx.fillStyle = `rgba(74,111,138,${alpha})`;
        ctx.beginPath();
        ctx.arc(s2x(qx), s2y(qy), Math.max(2, 2.5 * cam.zoom), 0, Math.PI * 2);
        ctx.fill();
      }

      // agents
      const bob = Math.floor(now / 480) % 2 === 0 ? 1 : 0;
      for (const room of scene.rooms) {
        for (const seat of room.seats) {
          if (!seat.agentId) {
            drawSeatStatic(ctx, seat, s2x, s2y, cam.zoom, true);
            continue;
          }
          const agent = agents.find((a) => a.id === seat.agentId);
          if (!agent) continue;
          const status = agentStatus[agent.id] ?? "IDLE";
          const active =
            status === "WORKING" ||
            status === "TOOL_CALL" ||
            status === "PLANNING" ||
            status === "COMMUNICATING";
          const traits = agentTraits(agent.id);

          // lit monitor when working
          if (active) {
            const d = seat.desk;
            const mw = 14,
              mh = 10;
            const mx = d.x + d.w / 2 - mw / 2;
            ctx.fillStyle = "#dfe8d8";
            ctx.fillRect(s2x(mx), s2y(d.y + 3), mw * cam.zoom, (mh - 2) * cam.zoom);
            ctx.fillStyle = "#8fa68e";
            ctx.fillRect(
              s2x(mx + 2),
              s2y(d.y + 5),
              (mw - 4) * cam.zoom,
              1 * cam.zoom,
            );
            ctx.fillRect(
              s2x(mx + 2),
              s2y(d.y + 7),
              (mw - 6) * cam.zoom,
              1 * cam.zoom,
            );
          }

          const gx = s2x(seat.x);
          const gy = s2y(seat.y);
          ctx.save();
          ctx.translate(gx, gy);
          ctx.scale(cam.zoom, cam.zoom);
          drawPerson(ctx, 0, 0, {
            skin: traits.skin,
            hair: traits.hair,
            shirt: traits.shirt,
            hairStyle: traits.hairStyle,
            sitting: true,
            frame: active && bob ? 1 : 0,
            dim: status === "OFFLINE",
          });
          // stool
          rect(ctx, 3, 13, 8, 3, "#4a4238");
          ctx.restore();

          // status dot above head
          const c = STATE[status] ?? STATE.IDLE;
          const pulse =
            status === "APPROVAL_REQUIRED" || status === "BLOCKED"
              ? 0.5 + 0.5 * Math.sin(now / 160)
              : 1;
          ctx.fillStyle = c;
          ctx.beginPath();
          ctx.arc(gx + 6 * cam.zoom, gy - 6 * cam.zoom, 2.4 * cam.zoom * (0.8 + 0.35 * pulse), 0, Math.PI * 2);
          ctx.fill();
          if (pulse !== 1) {
            ctx.strokeStyle = c;
            ctx.globalAlpha = 0.5 * pulse;
            ctx.beginPath();
            ctx.arc(gx + 6 * cam.zoom, gy - 6 * cam.zoom, 5.5 * cam.zoom, 0, Math.PI * 2);
            ctx.stroke();
            ctx.globalAlpha = 1;
          }

          // selection ring
          if (agent.id === selectedAgentId) {
            ctx.strokeStyle = PAPER[4];
            ctx.lineWidth = 1.5;
            ctx.strokeRect(
              s2x(seat.x - 4),
              s2y(seat.y - 6),
              20 * cam.zoom,
              26 * cam.zoom,
            );
          }
        }
      }

      // tool badges expire
      for (const [aid, t] of toolRef.current) if (now > t.until) toolRef.current.delete(aid);

      // ── DOM overlay sync (crisp text, clickable) ──
      syncOverlay(container, scene, cam, w, h, s2x, s2y, toolRef.current, agentStatus, STATE_LABEL);

      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [scene, agents, agentStatus, selectedAgentId, locate]);

  // ── Camera interactions ──────────────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current!;
    const canvas = canvasRef.current!;
    let dragging = false;
    let moved = false;
    let lx = 0,
      ly = 0;

    const onDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      dragging = true;
      moved = false;
      lx = e.clientX;
      ly = e.clientY;
      canvas.setPointerCapture(e.pointerId);
    };
    const onMove = (e: PointerEvent) => {
      if (!dragging) return;
      const dx = e.clientX - lx;
      const dy = e.clientY - ly;
      if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      lx = e.clientX;
      ly = e.clientY;
      const cam = cameraRef.current;
      cam.tcx -= dx / cam.zoom;
      cam.tcy -= dy / cam.zoom;
      cam.cx = cam.tcx;
      cam.cy = cam.tcy;
    };
    const onUp = () => {
      dragging = false;
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const cam = cameraRef.current;
      const { w, h } = sizeRef.current;
      const r = canvas.getBoundingClientRect();
      const mx = e.clientX - r.left;
      const my = e.clientY - r.top;
      const wx = cam.cx + (mx - w / 2) / cam.zoom;
      const wy = cam.cy + (my - h / 2) / cam.zoom;
      const factor = e.deltaY < 0 ? 1.16 : 1 / 1.16;
      const z = Math.min(4, Math.max(0.25, cam.tzoom * factor));
      cam.tzoom = z;
      cam.tcx = wx - (mx - w / 2) / z;
      cam.tcy = wy - (my - h / 2) / z;
    };
    const onClick = (e: MouseEvent) => {
      if (moved) return;
      if ((e.target as HTMLElement).closest("[data-nameplate]")) return;
      onSelectAgent(""); // click empty floor clears selection
    };

    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("click", onClick);
    return () => {
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("click", onClick);
    };
  }, [onSelectAgent]);

  const zoomBy = (f: number) => {
    const cam = cameraRef.current;
    cam.tzoom = Math.min(4, Math.max(0.25, cam.tzoom * f));
  };
  const resetView = () => {
    const cam = cameraRef.current;
    const { w, h } = sizeRef.current;
    cam.tzoom = Math.min(w / (scene.world.w + 60), h / (scene.world.h + 60));
    cam.tcx = scene.world.x + scene.world.w / 2;
    cam.tcy = scene.world.y + scene.world.h / 2;
  };

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden" style={{ background: PAPER[1] }}>
      <canvas ref={canvasRef} className="pixelated absolute inset-0 cursor-grab active:cursor-grabbing" />

      {/* DOM overlay: labels + nameplates, positioned per-frame */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {scene.labels.map((l, i) => (
          <div
            key={`lbl-${i}`}
            data-label={i}
            className="absolute left-0 top-0 -translate-x-1/2 whitespace-nowrap text-center"
            style={{ willChange: "transform" }}
          >
            <span
              className="t-label"
              style={{
                fontSize: l.kind === "building" ? 11 : 9.5,
                color: l.kind === "building" ? "var(--ink-1)" : "var(--ink-3)",
                letterSpacing: "0.18em",
              }}
            >
              {l.title}
              {l.sub ? <span style={{ marginLeft: 8, letterSpacing: "0.08em" }}>{l.sub}</span> : null}
            </span>
          </div>
        ))}

        {scene.rooms.map((r) => (
          <div
            key={`room-${r.deptId}`}
            data-room={r.deptId}
            className="absolute left-0 top-0 whitespace-nowrap"
            style={{ willChange: "transform" }}
          >
            <span
              className="t-label"
              style={{
                fontSize: 9.5,
                color: "var(--ink-2)",
                background: "rgba(251,248,241,0.82)",
                padding: "1px 6px",
                borderRadius: 3,
                border: "1px solid var(--paper-3)",
              }}
            >
              {r.name}
            </span>
          </div>
        ))}

        {agents.map((a) => {
          const status = agentStatus[a.id] ?? "IDLE";
          const selected = a.id === selectedAgentId;
          return (
            <button
              key={a.id}
              data-nameplate={a.id}
              onClick={(e) => {
                e.stopPropagation();
                onSelectAgent(a.id);
              }}
              className="pointer-events-auto absolute left-0 top-0 flex -translate-x-1/2 items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 transition-shadow"
              style={{
                willChange: "transform",
                background: selected ? "var(--paper-0)" : "rgba(251,248,241,0.85)",
                border: `1px solid ${selected ? "var(--ink-2)" : "var(--paper-3)"}`,
                boxShadow: "var(--shadow-1)",
                cursor: "pointer",
                zIndex: selected ? 30 : 20,
              }}
              title={`${a.name} — ${a.role} — ${STATE_LABEL[status] ?? status}`}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: STATE[status] ?? STATE.IDLE }}
              />
              <span className="text-[10px] font-semibold" style={{ color: "var(--ink-0)" }}>
                {a.name.split(" ")[0]}
              </span>
              <span className="text-[9px]" style={{ color: "var(--ink-2)" }}>
                {STATE_LABEL[status] ?? status}
              </span>
            </button>
          );
        })}

        {[...agents.map((a) => a.id)].map((id) => (
          <div
            key={`tool-${id}`}
            data-tool={id}
            className="t-mono absolute left-0 top-0 hidden -translate-x-1/2 rounded px-1.5 py-0.5"
            style={{
              fontSize: 9.5,
              background: "var(--ink-0)",
              color: "var(--paper-0)",
              zIndex: 40,
              willChange: "transform",
            }}
          />
        ))}
      </div>

      {/* Camera controls */}
      <div className="absolute bottom-3 right-3 flex flex-col gap-1.5">
        {[
          { label: "+", fn: () => zoomBy(1.25), title: "Zoom in" },
          { label: "−", fn: () => zoomBy(1 / 1.25), title: "Zoom out" },
          { label: "⤢", fn: resetView, title: "Fit building" },
        ].map((b) => (
          <button
            key={b.label}
            onClick={b.fn}
            title={b.title}
            className="panel flex h-8 w-8 items-center justify-center text-sm font-semibold"
            style={{ color: "var(--ink-1)" }}
          >
            {b.label}
          </button>
        ))}
      </div>

      {/* Legend */}
      <div
        className="panel absolute bottom-3 left-3 flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5"
        style={{ maxWidth: 340 }}
      >
        {["IDLE", "WORKING", "COMMUNICATING", "APPROVAL_REQUIRED", "BLOCKED"].map((s) => (
          <span key={s} className="flex items-center gap-1 text-[9.5px]" style={{ color: "var(--ink-2)" }}>
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: STATE[s] }} />
            {STATE_LABEL[s]}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

type S2 = (v: number) => number;

function dashedLine(
  ctx: Ctx,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  color: string,
  zoom: number,
  now: number,
) {
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(1, 1.4 * zoom);
  ctx.setLineDash([5 * zoom, 5 * zoom]);
  ctx.lineDashOffset = -(now / 30);
  ctx.globalAlpha = 0.55 + 0.3 * Math.sin(now / 300);
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
}

/** Empty seat: chair only. */
function drawSeatStatic(
  ctx: Ctx,
  seat: Seat,
  s2x: S2,
  s2y: S2,
  zoom: number,
  _empty: boolean,
) {
  ctx.save();
  ctx.translate(s2x(seat.x + 1), s2y(seat.y + 2));
  ctx.scale(zoom, zoom);
  drawChair(ctx, 0, 0);
  ctx.restore();
}

/** Prerender the entire building once. */
function drawBuilding(
  ctx: Ctx,
  scene: Scene,
  rackDepts: string[],
  meetingDepts: string[],
) {
  const { world, rooms, lobby } = scene;

  // building floor = corridor tile everywhere
  drawCorridor(ctx, world.x, world.y, world.w, world.h);

  // lobby dressing
  drawMat(ctx, lobby.mat.x, lobby.mat.y, lobby.mat.w, lobby.mat.h);
  drawDesk(ctx, lobby.reception.x, lobby.reception.y, 64, { seed: 7 });
  drawPlant(ctx, lobby.reception.x + 70, lobby.reception.y + 2);
  drawStairs(ctx, lobby.stairs.x, lobby.stairs.y);
  // elevator
  rect(ctx, lobby.elevator.x, lobby.elevator.y, 22, 24, PAPER[3]);
  rect(ctx, lobby.elevator.x + 2, lobby.elevator.y + 2, 18, 20, PAPER[4]);
  rect(ctx, lobby.elevator.x + 4, lobby.elevator.y + 4, 14, 16, PAPER[2]);
  rect(ctx, lobby.elevator.x + 10, lobby.elevator.y + 11, 2, 2, INK_HEX);

  for (const room of rooms) {
    const r = room.rect;
    const ix = r.x + 5,
      iy = r.y + 10,
      iw = r.w - 10,
      ih = r.h - 15;

    // interior carpet
    drawCarpet(ctx, ix, iy, iw, ih);

    const isMeeting = meetingDepts.some((m) => room.deptId.includes(m));
    const isRack = rackDepts.some((m) => room.deptId.includes(m));

    if (isMeeting) {
      drawMeetingTable(ctx, ix + iw / 2 - 48, iy + 16);
      // chairs around the table
      for (let i = 0; i < 3; i++) {
        drawChair(ctx, ix + iw / 2 - 40 + i * 32, iy + 2);
        drawChair(ctx, ix + iw / 2 - 40 + i * 32, iy + 54);
      }
      drawWhiteboard(ctx, ix + 8, iy + 2, 44);
      drawPlant(ctx, ix + iw - 16, iy + ih - 18);
      drawWaterCooler(ctx, ix + iw - 30, iy + 2);
    } else {
      // wall furniture
      drawBookshelf(ctx, ix + 6, iy + 2, Math.min(56, iw / 3));
      if (isRack) {
        for (let i = 0; i < 3; i++)
          drawRack(ctx, ix + iw - 22 - i * 24, iy + 1);
      } else {
        drawWhiteboard(ctx, ix + iw - 52, iy + 2, 44);
      }
      drawCabinet(ctx, ix + 6, iy + ih - 20);
      drawPlant(ctx, ix + iw - 14, iy + ih - 18);

      // desks + stools from seats
      for (const seat of room.seats) {
        drawDesk(ctx, seat.desk.x, seat.desk.y, seat.desk.w, {
          seed: seat.desk.seed,
          screenOn: false,
        });
        if (!seat.agentId) {
          drawChair(ctx, seat.x + 1, seat.y + 2);
        }
      }
      if (isRack && room.seats.length === 0) {
        // machine room with no staff: fill with racks
        for (let i = 0; i < 4; i++)
          drawRack(ctx, ix + 16 + i * 26, iy + ih - 24);
      }
    }
  }

  // inner walls over the floors
  for (const room of rooms) {
    drawWalls(ctx, {
      x: room.rect.x,
      y: room.rect.y,
      w: room.rect.w,
      h: room.rect.h,
      door: "S",
      doorAt: 0.5,
    });
  }

  // building shell with entrance
  drawWalls(ctx, { x: world.x, y: world.y, w: world.w, h: world.h, door: "S", doorAt: 0.5 });
}

const INK_HEX = "#4a4238";

// ─── Overlay sync ────────────────────────────────────────────────────────────

function syncOverlay(
  container: HTMLElement,
  scene: Scene,
  cam: Camera,
  vw: number,
  vh: number,
  s2x: S2,
  s2y: S2,
  tools: Map<string, { tool: string; until: number }>,
  agentStatus: Record<string, string>,
  stateLabel: Record<string, string>,
) {
  const setT = (el: HTMLElement, x: number, y: number, hide: boolean) => {
    el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
    el.style.visibility = hide ? "hidden" : "visible";
  };
  const visible = (x: number, y: number) =>
    x > -80 && x < vw + 80 && y > -40 && y < vh + 40;

  container.querySelectorAll<HTMLElement>("[data-label]").forEach((el) => {
    const i = Number(el.dataset.label);
    const l = scene.labels[i];
    if (!l) return;
    setT(el, s2x(l.x), s2y(l.y), !visible(s2x(l.x), s2y(l.y)));
  });

  container.querySelectorAll<HTMLElement>("[data-room]").forEach((el) => {
    const room = scene.rooms.find((r) => r.deptId === el.dataset.room);
    if (!room) return;
    const x = s2x(room.rect.x + room.rect.w / 2);
    const y = s2y(room.rect.y) - 16;
    setT(el, x, y, !visible(x, y));
  });

  container.querySelectorAll<HTMLElement>("[data-nameplate]").forEach((el) => {
    const id = el.dataset.nameplate;
    const seat = [...scene.rooms.flatMap((r) => r.seats)].find((s) => s.agentId === id);
    if (!seat) {
      el.style.visibility = "hidden";
      return;
    }
    const x = s2x(seat.x + 6);
    const y = s2y(seat.y) - 14;
    setT(el, x, y, !visible(x, y));
  });

  container.querySelectorAll<HTMLElement>("[data-tool]").forEach((el) => {
    const id = el.dataset.tool;
    const t = id ? tools.get(id) : undefined;
    if (!t) {
      el.classList.add("hidden");
      return;
    }
    const seat = [...scene.rooms.flatMap((r) => r.seats)].find((s) => s.agentId === id);
    if (!seat) {
      el.classList.add("hidden");
      return;
    }
    el.classList.remove("hidden");
    if (el.textContent !== t.tool) el.textContent = `${t.tool}()`;
    const x = s2x(seat.x + 6);
    const y = s2y(seat.y) + 30;
    setT(el, x, y, !visible(x, y));
  });
  void agentStatus;
  void stateLabel;
  void cam;
  void vh;
}
