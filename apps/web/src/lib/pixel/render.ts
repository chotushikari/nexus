/**
 * Procedural pixel-art drawing primitives for the NEXUS office.
 *
 * Everything is authored here in code — no external tileset, no image
 * assets. The style target is a muted top-down 3/4 office view: paper
 * walls, sage carpet, oak furniture, warm charcoal outlines. Furniture
 * functions draw at world-pixel scale directly onto the static layer.
 */

import { PAPER, INK, SAGE, OAK } from "./palette";

export type Ctx = CanvasRenderingContext2D;

export function px(ctx: Ctx, x: number, y: number, w: number, h: number, c: string) {
  ctx.fillStyle = c;
  ctx.fillRect(x, y, w, h);
}

/** Deterministic 0..1 from integer seed — keeps texture stable per position. */
function rnd(seed: number): number {
  let t = (seed + 0x6d2b79f5) | 0;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

// ─── Floors ──────────────────────────────────────────────────────────────────

/** Office carpet: sage field with a soft 32px checker and sparse flecks. */
export function drawCarpet(ctx: Ctx, x: number, y: number, w: number, h: number) {
  px(ctx, x, y, w, h, SAGE[0]);
  const cs = 32;
  for (let ty = 0; ty < h; ty += cs) {
    for (let tx = 0; tx < w; tx += cs) {
      if (((tx / cs) & 1) !== ((ty / cs) & 1)) {
        px(ctx, x + tx, y + ty, Math.min(cs, w - tx), Math.min(cs, h - ty), SAGE[1]);
      }
    }
  }
  // sparse carpet flecks for texture
  const seedBase = ((x & 0xffff) << 16) | (y & 0xffff);
  for (let i = 0; i < (w * h) / 220; i++) {
    const fx = x + Math.floor(rnd(seedBase + i * 7) * w);
    const fy = y + Math.floor(rnd(seedBase + i * 13 + 1) * h);
    px(ctx, fx, fy, 2, 1, SAGE[2]);
  }
}

/** Corridor: lighter tile with grout lines every 16px. */
export function drawCorridor(ctx: Ctx, x: number, y: number, w: number, h: number) {
  px(ctx, x, y, w, h, PAPER[2]);
  for (let ty = 0; ty < h; ty += 16)
    for (let tx = 0; tx < w; tx += 16) {
      px(ctx, x + tx, y + ty, 16, 1, PAPER[3]);
      px(ctx, x + tx, y + ty, 1, 16, PAPER[3]);
      const alt = (((tx / 16) & 1) !== ((ty / 16) & 1)) && ty + 16 <= h && tx + 16 <= w;
      if (alt) px(ctx, x + tx + 1, y + ty + 1, 14, 14, PAPER[1]);
    }
}

/** Entrance mat with the wordmark, drawn in floor pixels. */
export function drawMat(ctx: Ctx, x: number, y: number, w: number, h: number) {
  px(ctx, x, y, w, h, SAGE[3]);
  px(ctx, x + 2, y + 2, w - 4, h - 4, SAGE[2]);
  px(ctx, x + 3, y + 3, w - 6, h - 6, SAGE[1]);
  // N E X U S — 3x5 pixel letters, centred
  const glyphs: Record<string, number[]> = {
    N: [0b101, 0b111, 0b111, 0b111, 0b101],
    E: [0b111, 0b100, 0b111, 0b100, 0b111],
    X: [0b101, 0b101, 0b010, 0b101, 0b101],
    U: [0b101, 0b101, 0b101, 0b101, 0b111],
    S: [0b111, 0b100, 0b111, 0b001, 0b111],
  };
  const word = "NEXUS";
  const gw = 3 * 2 + 1;
  const total = word.length * gw - 1;
  const ox = x + Math.floor((w - total) / 2);
  const oy = y + Math.floor((h - 5) / 2);
  ctx.fillStyle = PAPER[1];
  for (let i = 0; i < word.length; i++) {
    const rows = glyphs[word[i]];
    for (let r = 0; r < 5; r++)
      for (let c = 0; c < 3; c++)
        if (rows[r] & (1 << (2 - c)))
          ctx.fillRect(ox + i * gw + c * 2, oy + r, 2, 1);
  }
}

// ─── Walls ───────────────────────────────────────────────────────────────────

export interface WallSpec {
  x: number;
  y: number;
  w: number;
  h: number;
  /** Edge that carries the door opening. */
  door: "N" | "S" | "E" | "W" | null;
  /** Approximate door centre as fraction along that edge. */
  doorAt?: number;
}

/**
 * Room walls: pale paper shell, shaded outer face, drop shadow into the
 * room. The top wall reads taller (pseudo-3/4 height).
 */
export function drawWalls(ctx: Ctx, s: WallSpec) {
  const { x, y, w, h } = s;
  const t = 5; // side/bottom thickness
  const top = 10; // top wall height
  const doorW = 30;

  // shadow cast by top wall into the room
  ctx.fillStyle = "rgba(43,38,32,0.10)";
  ctx.fillRect(x + t, y + top, w - t * 2, 5);

  const wall = PAPER[0];
  const edge = PAPER[3];
  const outer = PAPER[4];

  // top wall (with optional door)
  px(ctx, x, y, w, top, wall);
  px(ctx, x, y, w, 2, outer); // outer face
  px(ctx, x, y + top - 2, w, 2, edge); // inner skirting

  // side walls
  px(ctx, x, y + top, t, h - top - t, wall);
  px(ctx, x, y, t, h, outer); // outer face left
  px(ctx, x + w - t, y + top, t, h - top, wall);
  px(ctx, x + w - 2, y, 2, h, outer);

  // bottom wall (with optional door)
  const by = y + h - t;
  if (s.door === "S") {
    const dx = x + Math.max(t + 4, Math.min(w - t - 4 - doorW, w * (s.doorAt ?? 0.5) - doorW / 2));
    px(ctx, x + t, by, dx - (x + t), t, wall);
    px(ctx, x + t, by, dx - (x + t), 1, edge);
    px(ctx, dx + doorW, by, x + w - t - (dx + doorW), t, wall);
    // threshold
    px(ctx, dx, by + 1, doorW, t - 1, PAPER[2]);
    // side jamb shading
    px(ctx, dx, y + top, 2, h - top - t, PAPER[4]);
    px(ctx, dx + doorW - 2, y + top, 2, h - top - t, PAPER[4]);
  } else {
    px(ctx, x + t, by, w - t * 2, t, wall);
    px(ctx, x + t, by + t - 1, w - t * 2, 1, outer);
  }

  if (s.door === "N") {
    const dx = x + Math.max(t + 4, Math.min(w - t - 4 - doorW, w * (s.doorAt ?? 0.5) - doorW / 2));
    px(ctx, dx, y, doorW, top, SAGE[1]); // opening shows corridor beyond
    px(ctx, dx, y + top - 2, doorW, 2, edge);
  }
}

// ─── Furniture ───────────────────────────────────────────────────────────────

/** Desk with monitor. Agent seat is centred just below (y + h + 6). */
export function drawDesk(
  ctx: Ctx,
  x: number,
  y: number,
  w: number,
  opts: { screenOn?: boolean; seed?: number } = {},
) {
  const h = 16;
  // shadow
  ctx.fillStyle = "rgba(43,38,32,0.12)";
  ctx.fillRect(x + 2, y + h, w, 3);
  // top
  px(ctx, x, y, w, h, OAK[0]);
  px(ctx, x, y, w, 2, OAK[1]);
  px(ctx, x, y + h - 3, w, 3, OAK[1]); // front edge
  px(ctx, x, y + h, w, 2, OAK[2]); // front face shadow
  // grain lines
  const seed = opts.seed ?? x * 31 + y;
  for (let i = 0; i < Math.floor(w / 9); i++) {
    const gy = y + 3 + Math.floor(rnd(seed + i * 5) * (h - 7));
    px(ctx, x + 2 + Math.floor(rnd(seed + i) * (w - 8)), gy, 6, 1, OAK[1]);
  }
  // monitor (facing the chair below)
  const mw = 14,
    mh = 10;
  const mx = x + Math.floor(w / 2 - mw / 2);
  const my = y + 2;
  px(ctx, mx - 1, my - 1, mw + 2, mh + 2, INK[1]); // bezel
  px(ctx, mx, my, mw, mh, opts.screenOn ? "#dfe8d8" : "#3a3f3a");
  if (opts.screenOn) {
    // abstract spreadsheet glow
    px(ctx, mx + 2, my + 2, mw - 4, 1, "#8fa68e");
    px(ctx, mx + 2, my + 4, mw - 6, 1, "#a8bca5");
    px(ctx, mx + 2, my + 6, mw - 5, 1, "#8fa68e");
  }
  px(ctx, mx + mw / 2 - 1, my + mh + 1, 2, 2, INK[1]); // stand
  // keyboard + mug + papers
  px(ctx, x + 3, y + h - 6, 8, 3, INK[2]);
  px(ctx, x + w - 8, y + h - 7, 3, 3, PAPER[0]);
  px(ctx, x + w - 8, y + h - 7, 3, 1, "#a63d2f");
  if (rnd(seed + 99) > 0.5) px(ctx, x + w - 16, y + 3, 7, 5, PAPER[0]);
}

export function drawChair(ctx: Ctx, x: number, y: number) {
  px(ctx, x, y, 10, 9, INK[1]);
  px(ctx, x + 1, y + 1, 8, 5, INK[2]);
  px(ctx, x + 3, y + 9, 4, 2, INK[1]);
}

export function drawPlant(ctx: Ctx, x: number, y: number) {
  px(ctx, x + 3, y + 10, 8, 6, OAK[1]); // pot
  px(ctx, x + 3, y + 10, 8, 1, OAK[2]);
  px(ctx, x + 4, y + 4, 6, 7, SAGE[2]);
  px(ctx, x + 2, y + 6, 10, 4, SAGE[2]);
  px(ctx, x + 5, y + 2, 4, 3, SAGE[3]);
  px(ctx, x + 6, y + 5, 2, 5, SAGE[3]);
}

export function drawBookshelf(ctx: Ctx, x: number, y: number, w: number) {
  const h = 14;
  px(ctx, x, y, w, h, OAK[2]);
  px(ctx, x + 1, y + 1, w - 2, h - 2, OAK[1]);
  // book spines
  const colors = [SAGE[3], INK[1], OAK[3], PAPER[4], SAGE[2], INK[2]];
  let bx = x + 2;
  let i = 0;
  while (bx < x + w - 3) {
    const bw = 2 + Math.floor(rnd(x * 7 + bx + i) * 2);
    px(ctx, bx, y + 3, bw, h - 6, colors[i % colors.length]);
    bx += bw + 1;
    i++;
  }
  px(ctx, x, y + h / 2, w, 1, OAK[2]);
}

export function drawCabinet(ctx: Ctx, x: number, y: number) {
  px(ctx, x, y, 14, 16, PAPER[3]);
  px(ctx, x + 1, y + 1, 12, 14, PAPER[0]);
  for (let r = 0; r < 3; r++) {
    px(ctx, x + 2, y + 2 + r * 4, 10, 3, PAPER[2]);
    px(ctx, x + 6, y + 3 + r * 4, 2, 1, INK[2]);
  }
}

/** Server rack: dark cabinet, slot lines, status LEDs (soft green, never neon). */
export function drawRack(ctx: Ctx, x: number, y: number, opts: { alert?: boolean } = {}) {
  const w = 18,
    h = 20;
  ctx.fillStyle = "rgba(43,38,32,0.15)";
  ctx.fillRect(x + 1, y + h, w, 2);
  px(ctx, x, y, w, h, INK[0]);
  px(ctx, x + 1, y + 1, w - 2, h - 2, "#3d3a34");
  for (let sy = y + 3; sy < y + h - 3; sy += 4) {
    px(ctx, x + 2, sy, w - 4, 2, "#55524a");
    px(ctx, x + 3, sy + 1, 1, 1, opts.alert ? "#c8860d" : "#4a7c4e"); // LED
    px(ctx, x + 5, sy + 1, 1, 1, "#758c74");
  }
}

export function drawMeetingTable(ctx: Ctx, x: number, y: number) {
  const w = 96,
    h = 36;
  ctx.fillStyle = "rgba(43,38,32,0.14)";
  ctx.fillRect(x + 2, y + h, w, 4);
  px(ctx, x, y, w, h, OAK[0]);
  px(ctx, x + 2, y + 2, w - 4, h - 4, OAK[0]);
  px(ctx, x, y, w, 2, OAK[1]);
  px(ctx, x, y + h - 3, w, 3, OAK[1]);
  px(ctx, x + w / 2 - 6, y + h / 2 - 2, 12, 4, PAPER[0]); // papers
  px(ctx, x + w / 2 + 8, y + h / 2 - 1, 3, 3, INK[2]); // phone
}

export function drawWhiteboard(ctx: Ctx, x: number, y: number, w: number) {
  px(ctx, x, y, w, 12, OAK[2]);
  px(ctx, x + 1, y + 1, w - 2, 10, PAPER[0]);
  // marker strokes
  px(ctx, x + 3, y + 3, 10, 1, "#4a6f8a");
  px(ctx, x + 3, y + 5, 14, 1, "#4a7c4e");
  px(ctx, x + 3, y + 7, 8, 1, "#b07d2b");
  px(ctx, x + 20, y + 3, 6, 1, INK[3]);
  px(ctx, x + 20, y + 5, 9, 1, INK[3]);
}

export function drawWaterCooler(ctx: Ctx, x: number, y: number) {
  px(ctx, x, y, 10, 14, PAPER[3]);
  px(ctx, x + 1, y + 1, 8, 5, "#a8bca5"); // bottle
  px(ctx, x + 1, y + 7, 8, 6, PAPER[0]);
}

export function drawStairs(ctx: Ctx, x: number, y: number) {
  for (let i = 0; i < 6; i++)
    px(ctx, x + i * 3, y + i * 4, 26 - i * 3, 3, i % 2 ? PAPER[3] : PAPER[2]);
  px(ctx, x, y - 2, 26, 2, PAPER[4]);
}

// ─── People ──────────────────────────────────────────────────────────────────

export interface SpriteOpts {
  skin: string;
  hair: string;
  shirt: string;
  hairStyle: number;
  /** 0 = down (facing camera), 2 = up (facing monitor) */
  facing?: 0 | 2;
  sitting?: boolean;
  /** 2-frame walk/typo bob. */
  frame?: 0 | 1;
  dim?: boolean;
}

/**
 * A person, 12×18 standing / 12×13 seated. Drawn so the head sits at the
 * given (x, y) — callers position by head, which is what occlusion wants.
 */
export function drawPerson(ctx: Ctx, x: number, y: number, o: SpriteOpts) {
  ctx.save();
  if (o.dim) ctx.globalAlpha = 0.35;
  const facingUp = o.facing === 2;
  // torso
  const torsoH = o.sitting ? 8 : 9;
  px(ctx, x + 1, y + 7, 10, torsoH, o.shirt);
  px(ctx, x + 1, y + 7, 10, 1, "rgba(43,38,32,0.25)");
  if (!o.sitting) {
    // legs + shoes
    px(ctx, x + 2, y + 16, 3, 3, INK[0]);
    px(ctx, x + 7, y + 16, 3, 3, INK[0]);
    if (o.frame === 1) {
      px(ctx, x + 1, y + 16, 3, 3, INK[0]);
      px(ctx, x + 8, y + 16, 3, 3, INK[0]);
    }
  }
  // arms — tiny, at sides (typing frame raises them)
  if (o.frame === 1 && !facingUp) {
    px(ctx, x, y + 8, 1, 4, o.shirt);
    px(ctx, x + 11, y + 8, 1, 4, o.shirt);
  } else {
    px(ctx, x, y + 8, 1, 5, o.shirt);
    px(ctx, x + 11, y + 8, 1, 5, o.shirt);
  }
  // head
  px(ctx, x + 2, y, 8, 8, o.skin);
  // hair
  px(ctx, x + 2, y, 8, 2, o.hair);
  if (o.hairStyle === 0) px(ctx, x + 2, y, 2, 5, o.hair); // side part
  if (o.hairStyle === 1) px(ctx, x + 2, y, 8, 3, o.hair); // full
  if (o.hairStyle === 2) {
    px(ctx, x + 2, y, 8, 4, o.hair); // long
    px(ctx, x + 1, y + 2, 1, 5, o.hair);
    px(ctx, x + 10, y + 2, 1, 5, o.hair);
  }
  if (o.hairStyle === 3) px(ctx, x + 3, y - 1, 6, 2, o.hair); // short tuft
  // face
  if (!facingUp) {
    px(ctx, x + 4, y + 4, 1, 2, INK[0]); // eyes
    px(ctx, x + 7, y + 4, 1, 2, INK[0]);
  }
  ctx.restore();
}
