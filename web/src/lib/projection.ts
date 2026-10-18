// Pitch → screen projection. The single source of truth for where a pitch point lands on the
// 1920×1080 stage: the canvas pitch and every DOM overlay (tags, badges, trails) go through it,
// so overlays stay on the players with the pitch tilted.

export type Vec2 = { x: number; y: number }

export const PITCH = { length: 105, width: 68 } as const
export const STAGE = { width: 1920, height: 1080 } as const

// Title-safe area: 5 % of the frame on every side (DESIGN.md §2).
export const SAFE = {
  left: STAGE.width * 0.05,
  top: STAGE.height * 0.05,
  right: STAGE.width * 0.95,
  bottom: STAGE.height * 0.95,
} as const

export type Camera = {
  project(p: Vec2): Vec2
  unproject(s: Vec2): Vec2
  /** Screen pixels per pitch metre around `p` (along the pitch length). */
  scaleAt(p: Vec2): number
}

type H = readonly number[] // 3×3 row-major, h[8] = 1

function solve(a: number[][], b: number[]): number[] {
  const n = b.length
  const m = a.map((row, i) => [...row, b[i]])
  for (let c = 0; c < n; c++) {
    let piv = c
    for (let r = c + 1; r < n; r++) if (Math.abs(m[r][c]) > Math.abs(m[piv][c])) piv = r
    ;[m[c], m[piv]] = [m[piv], m[c]]
    for (let r = 0; r < n; r++) {
      if (r === c) continue
      const f = m[r][c] / m[c][c]
      for (let k = c; k <= n; k++) m[r][k] -= f * m[c][k]
    }
  }
  return m.map((row, i) => row[n] / row[i])
}

/** Homography mapping four source points onto four destination points. */
export function homography(src: Vec2[], dst: Vec2[]): H {
  const a: number[][] = []
  const b: number[] = []
  for (let i = 0; i < 4; i++) {
    const { x, y } = src[i]
    const { x: u, y: v } = dst[i]
    a.push([x, y, 1, 0, 0, 0, -u * x, -u * y])
    b.push(u)
    a.push([0, 0, 0, x, y, 1, -v * x, -v * y])
    b.push(v)
  }
  return [...solve(a, b), 1]
}

function apply(h: H, p: Vec2): Vec2 {
  const w = h[6] * p.x + h[7] * p.y + h[8]
  return { x: (h[0] * p.x + h[1] * p.y + h[2]) / w, y: (h[3] * p.x + h[4] * p.y + h[5]) / w }
}

function invert(h: H): H {
  const [a, b, c, d, e, f, g, i, j] = h
  const A = e * j - f * i
  const B = -(d * j - f * g)
  const C = d * i - e * g
  const det = a * A + b * B + c * C
  const inv = [
    A,
    -(b * j - c * i),
    b * f - c * e,
    B,
    a * j - c * g,
    -(a * f - c * d),
    C,
    -(a * i - b * g),
    a * e - b * d,
  ].map((v) => v / det)
  return inv.map((v) => v / inv[8])
}

export function cameraFromCorners(corners: { nearLeft: Vec2; nearRight: Vec2; farRight: Vec2; farLeft: Vec2 }): Camera {
  const src = [
    { x: 0, y: 0 },
    { x: PITCH.length, y: 0 },
    { x: PITCH.length, y: PITCH.width },
    { x: 0, y: PITCH.width },
  ]
  const dst = [corners.nearLeft, corners.nearRight, corners.farRight, corners.farLeft]
  const h = homography(src, dst)
  const hi = invert(h)
  return {
    project: (p) => apply(h, p),
    unproject: (s) => apply(hi, s),
    scaleAt: (p) => {
      const a = apply(h, { x: p.x - 0.5, y: p.y })
      const b = apply(h, { x: p.x + 0.5, y: p.y })
      return Math.hypot(b.x - a.x, b.y - a.y)
    },
  }
}

/**
 * High main-camera view: the near touchline (pitch y = 0) at the bottom of the frame, the far
 * touchline narrower and higher, like a camera on the gantry. Pitch x runs left to right.
 */
export function broadcastCamera(): Camera {
  return cameraFromCorners({
    nearLeft: { x: 40, y: 1012 },
    nearRight: { x: 1880, y: 1012 },
    farRight: { x: 1588, y: 268 },
    farLeft: { x: 332, y: 268 },
  })
}

/** Absolute-position style for a DOM overlay anchored at a pitch point. */
export function anchorAt(cam: Camera, p: Vec2): { left: number; top: number } {
  const s = cam.project(p)
  return { left: s.x, top: s.y }
}
