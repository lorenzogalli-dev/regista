// Pitch markings in screen space, computed through the shared camera. The canvas draws exactly
// these points; nothing on the canvas is positioned any other way.

import { PITCH, type Camera, type Vec2 } from '../lib/projection.ts'

export const STRIPES = 18
const L = PITCH.length
const W = PITCH.width
const MID = W / 2

export type PitchGeometry = {
  outline: Vec2[]
  stripes: Vec2[][]
  lines: Vec2[][]
  spots: { centre: Vec2; penaltyLeft: Vec2; penaltyRight: Vec2 }
  goals: Vec2[][]
}

function arc(c: Vec2, r: number, from: number, to: number, n = 48): Vec2[] {
  return Array.from({ length: n + 1 }, (_, i) => {
    const a = from + ((to - from) * i) / n
    return { x: c.x + r * Math.cos(a), y: c.y + r * Math.sin(a) }
  })
}

function rect(x0: number, y0: number, x1: number, y1: number): Vec2[] {
  return [
    { x: x0, y: y0 },
    { x: x1, y: y0 },
    { x: x1, y: y1 },
    { x: x0, y: y1 },
    { x: x0, y: y0 },
  ]
}

/** Markings in pitch metres (IFAB dimensions). */
export function pitchMarkingsMetres(): Omit<PitchGeometry, 'stripes'> {
  const penL = { x: 11, y: MID }
  const penR = { x: L - 11, y: MID }
  // Penalty arc: the part of the 9.15 m circle around the spot outside the 16.5 m box.
  const a = Math.acos(5.5 / 9.15)
  return {
    outline: rect(0, 0, L, W),
    lines: [
      [
        { x: L / 2, y: 0 },
        { x: L / 2, y: W },
      ],
      arc({ x: L / 2, y: MID }, 9.15, 0, 2 * Math.PI, 96),
      rect(0, MID - 20.16, 16.5, MID + 20.16),
      rect(L - 16.5, MID - 20.16, L, MID + 20.16),
      rect(0, MID - 9.16, 5.5, MID + 9.16),
      rect(L - 5.5, MID - 9.16, L, MID + 9.16),
      arc(penL, 9.15, -a, a),
      arc(penR, 9.15, Math.PI - a, Math.PI + a),
    ],
    spots: { centre: { x: L / 2, y: MID }, penaltyLeft: penL, penaltyRight: penR },
    goals: [rect(-2, MID - 3.66, 0, MID + 3.66), rect(L, MID - 3.66, L + 2, MID + 3.66)],
  }
}

export function pitchGeometry(cam: Camera): PitchGeometry {
  const m = pitchMarkingsMetres()
  const p = (pts: Vec2[]) => pts.map((q) => cam.project(q))
  const stripes = Array.from({ length: STRIPES }, (_, i) =>
    p(rect((L * i) / STRIPES, 0, (L * (i + 1)) / STRIPES, W).slice(0, 4)),
  )
  return {
    outline: p(m.outline),
    stripes,
    lines: m.lines.map(p),
    spots: {
      centre: cam.project(m.spots.centre),
      penaltyLeft: cam.project(m.spots.penaltyLeft),
      penaltyRight: cam.project(m.spots.penaltyRight),
    },
    goals: m.goals.map(p),
  }
}
