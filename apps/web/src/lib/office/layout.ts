/**
 * Floor-plan generator.
 *
 * Consumes the live backend model — department locations (x/y/w/h per
 * floor) and the agent roster — and produces a scene graph the renderer
 * draws: rooms with walls and doors, desks with seats, department-specific
 * furniture, corridors, stairs, lobby. Nothing department-specific is
 * hard-coded in the renderer; everything comes from this data (§8, §35).
 */

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DeskSpec {
  x: number;
  y: number;
  w: number;
  seed: number;
}

export interface Seat {
  agentId: string | null;
  /** Chair top-left in world px (sprite is drawn from head at chair y+1). */
  x: number;
  y: number;
  desk: DeskSpec;
}

export interface Room {
  deptId: string;
  name: string;
  description: string;
  rect: Rect;
  floor: number;
  isManagerDept: boolean;
  seats: Seat[];
  /** World point used for approval routing lines. */
  focus: { x: number; y: number };
}

export interface SceneLabel {
  x: number;
  y: number;
  title: string;
  sub?: string;
  kind: "floor" | "building";
}

export interface Scene {
  world: Rect;
  rooms: Room[];
  labels: SceneLabel[];
  lobby: { mat: Rect; reception: { x: number; y: number }; stairs: { x: number; y: number }; elevator: { x: number; y: number } };
}

export interface LayoutDept {
  id: string;
  name: string;
  description: string;
  managerAgentId?: string | null;
  location: { floor: number; x: number; y: number; width: number; height: number };
}

export interface LayoutAgent {
  id: string;
  name: string;
  departmentId: string;
}

const FLOOR_GAP = 150; // corridor + stairs between the two floors
const MARGIN = 56; // building shell padding around rooms

/**
 * Departments that read as "machine rooms" get racks along the top wall
 * instead of a bookshelf. Data-driven on id substring so new departments
 * with matching purpose are styled without renderer changes.
 */
const RACK_DEPTS = ["security", "data", "engineering", "infrastructure"];
const MEETING_DEPTS = ["executive"];

export function buildScene(depts: LayoutDept[], agents: LayoutAgent[]): Scene {
  const byFloor = new Map<number, LayoutDept[]>();
  for (const d of depts) {
    const f = d.location.floor || 1;
    if (!byFloor.has(f)) byFloor.set(f, []);
    byFloor.get(f)!.push(d);
  }
  const floors = [...byFloor.keys()].sort((a, b) => a - b);

  // Stack floors vertically: floor 1 at the bottom, higher floors above.
  const offsets = new Map<number, number>();
  let cursor = 0; // top of the topmost floor, in shifted coordinates
  for (const f of [...floors].reverse()) {
    const rooms = byFloor.get(f)!;
    const minY = Math.min(...rooms.map((r) => r.location.y));
    const maxY = Math.max(...rooms.map((r) => r.location.y + r.location.height));
    const shift = cursor - minY;
    offsets.set(f, shift);
    cursor = maxY + shift + FLOOR_GAP;
  }

  const agentsByDept = new Map<string, LayoutAgent[]>();
  for (const a of agents) {
    if (!agentsByDept.has(a.departmentId)) agentsByDept.set(a.departmentId, []);
    agentsByDept.get(a.departmentId)!.push(a);
  }

  const rooms: Room[] = [];
  const labels: SceneLabel[] = [];
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;

  for (const f of floors) {
    const off = offsets.get(f)!;
    for (const d of byFloor.get(f)!) {
      const L = d.location;
      const rect: Rect = { x: L.x, y: L.y + off, w: L.width, h: L.height };
      const deptAgents = agentsByDept.get(d.id) ?? [];
      const isManagerDept = MEETING_DEPTS.some((m) => d.id.includes(m));

      const seats = isManagerDept
        ? buildMeetingSeats(rect, deptAgents)
        : buildDeskSeats(rect, deptAgents, d.id);

      rooms.push({
        deptId: d.id,
        name: d.name,
        description: d.description,
        rect,
        floor: f,
        isManagerDept,
        seats,
        focus: { x: rect.x + rect.w / 2, y: rect.y + rect.h / 2 },
      });

      minX = Math.min(minX, rect.x);
      minY = Math.min(minY, rect.y);
      maxX = Math.max(maxX, rect.x + rect.w);
      maxY = Math.max(maxY, rect.y + rect.h);
    }
  }

  // Building shell
  const bx = minX - MARGIN;
  const by = minY - MARGIN;
  const bw = maxX - minX + MARGIN * 2;
  const bh = maxY - minY + MARGIN * 2;

  // Floor banners sit just ABOVE each floor's top row, anchored left in the
  // corridor so they never collide with rooms or nameplates. The building
  // wordmark sits centred in the top margin.
  for (const f of floors) {
    const fr = byFloor.get(f)!;
    const off = offsets.get(f)!;
    const topY = Math.min(...fr.map((r) => r.location.y)) + off;
    labels.push({
      x: bx + 170,
      y: topY - 32,
      title: `FLOOR ${f}`,
      sub: f === floors[0] ? "Command & Delivery" : "Business Operations",
      kind: "floor",
    });
  }
  labels.push({ x: bx + bw / 2, y: by + 24, title: "NEXUS HQ", kind: "building" });

  const lobby = {
    mat: { x: bx + bw / 2 - 70, y: by + bh - 44, w: 140, h: 30 },
    reception: { x: bx + bw / 2 + 90, y: by + bh - 46 },
    stairs: { x: bx + 30, y: by + bh / 2 - 12 },
    elevator: { x: bx + bw - 52, y: by + bh / 2 - 14 },
  };

  return { world: { x: bx, y: by, w: bw, h: bh }, rooms, labels, lobby };
}

/**
 * Rows of desks: two columns per room, one desk per agent plus one empty
 * desk so the floor never looks like a chart. The manager (first listed)
 * gets the wider corner desk.
 */
function buildDeskSeats(rect: Rect, agents: LayoutAgent[], deptId: string): Seat[] {
  const inX = rect.x + 14;
  const inY = rect.y + 20;
  const inW = rect.w - 28;
  const inH = rect.h - 34;

  const colX = [inX + inW * 0.08, inX + inW * 0.54];
  const rowY = [inY + 8, inY + inH * 0.46, inY + inH * 0.78];

  const deskCount = Math.min(6, Math.max(2, agents.length + 1));
  const seats: Seat[] = [];

  let n = 0;
  for (const row of rowY) {
    for (const cx of colX) {
      if (n >= deskCount) break;
      const wide = n === 0 && agents.length > 0; // manager desk
      const w = wide ? 46 : 38;
      const desk = { x: Math.round(cx), y: Math.round(row), w, seed: hash(deptId + n) };
      const agent = agents[n] ?? null;
      seats.push({
        agentId: agent?.id ?? null,
        x: desk.x + Math.floor(w / 2) - 5,
        y: desk.y + 24,
        desk,
      });
      n++;
    }
  }
  return seats;
}

/** Executive: the manager takes a corner desk; the team sits at the table. */
function buildMeetingSeats(rect: Rect, agents: LayoutAgent[]): Seat[] {
  const cx = rect.x + rect.w / 2;
  const tableX = Math.round(cx - 48);
  const tableY = rect.y + 24;
  const seats: Seat[] = [];

  if (agents.length > 0) {
    const desk = { x: rect.x + rect.w - 66, y: rect.y + 26, w: 42, seed: hash("exec-mgr") };
    seats.push({ agentId: agents[0].id, x: desk.x + 14, y: desk.y + 24, desk });
  }

  // Remaining agents sit below the table, two per row, well separated.
  agents.slice(1, 5).forEach((a, i) => {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const x = tableX + 4 + col * 52;
    const y = tableY + 46 + row * 30;
    seats.push({
      agentId: a.id,
      x,
      y,
      desk: { x: x - 12, y: y + 6, w: 38, seed: hash("exec" + i) },
    });
  });

  // Any overflow agents get a side desk below the manager.
  for (let i = 5; i < agents.length; i++) {
    const desk = { x: rect.x + rect.w - 66, y: rect.y + 26 + (i - 4) * 34, w: 38, seed: hash("execside" + i) };
    seats.push({ agentId: agents[i].id, x: desk.x + 12, y: desk.y + 24, desk });
  }
  return seats;
}

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
