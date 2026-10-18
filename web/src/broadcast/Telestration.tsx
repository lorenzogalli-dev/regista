// Telestration during a moment replay: shapes drawn on the pitch from the match data
// (`/api/runs/{id}/timeline`), so the viewer sees where the numbers on the AI card come from.
// Everything here is computed by code; it uses the brand green ("from the data"), not the AI
// cyan reserved for agent-written text.

import { motion } from 'motion/react'
import { useRef } from 'react'

import { useClockFrame, type Clock } from '../lib/clock.ts'
import { SAFE, type Camera, type Vec2 } from '../lib/projection.ts'
import { positionsAt, type Frame } from '../lib/sample.ts'
import { EASE_OUT, wipe } from './wipe.ts'

export type Telestration = {
  moment_id: string
  show_at_ms: number
  team_id: string
  kind: 'press' | 'width' | 'long' | 'progressive' | 'territory'
  players: string[]
  zones: { x0: number; y0: number; x1: number; y1: number }[]
  arrows: { x: number; y: number; end_x: number; end_y: number }[]
  dots: { x: number; y: number }[]
  label: string
}

const KIND: Record<Telestration['kind'], string> = {
  press: 'Where they win it back',
  width: 'Play out wide',
  long: 'Longest passes',
  progressive: 'Progressive passes',
  territory: 'Final third',
}

// Region the moment card occupies (stage px): labels stay clear of it.
const CARD_ZONE = { left: SAFE.left, right: SAFE.left + 900, top: 560 }

function pts(cam: Camera, ps: Vec2[]): string {
  return ps
    .map((p) => cam.project(p))
    .map((s) => `${s.x.toFixed(1)},${s.y.toFixed(1)}`)
    .join(' ')
}

function arrowPath(cam: Camera, a: { x: number; y: number; end_x: number; end_y: number }) {
  const s = cam.project({ x: a.x, y: a.y })
  const e = cam.project({ x: a.end_x, y: a.end_y })
  // A gentle arc, bowed away from the camera, reads like a hand-drawn telestrator line.
  const mx = (s.x + e.x) / 2
  const my = (s.y + e.y) / 2 - Math.min(80, Math.hypot(e.x - s.x, e.y - s.y) * 0.18)
  return { d: `M${s.x.toFixed(1)},${s.y.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${e.x.toFixed(1)},${e.y.toFixed(1)}`, end: e }
}

/** Where the label goes: above the drawing, inside title-safe, off the moment card. */
function labelPosition(cam: Camera, t: Telestration): { left: number; top: number } {
  const all: Vec2[] = [
    ...t.zones.flatMap((z) => [
      { x: z.x0, y: z.y1 },
      { x: z.x1, y: z.y1 },
    ]),
    ...t.arrows.flatMap((a) => [
      { x: a.x, y: a.y },
      { x: a.end_x, y: a.end_y },
    ]),
  ]
  const s = all.length ? all.map((p) => cam.project(p)) : [{ x: 960, y: 300 }]
  const cx = s.reduce((n, p) => n + p.x, 0) / s.length
  const top = Math.min(...s.map((p) => p.y))
  const width = Math.max(420, 30 + 13.5 * t.label.length)
  let left = Math.min(Math.max(cx - width / 2, SAFE.left + 600), SAFE.right - width - 12)
  let y = Math.max(SAFE.top + 96, top - 96)
  if (left < CARD_ZONE.right && y + 80 > CARD_ZONE.top) y = CARD_ZONE.top - 96
  if (y < SAFE.top + 96) {
    y = SAFE.top + 96
    left = Math.max(left, SAFE.left + 600)
  }
  return { left, top: y }
}

function Rings({ players, frames, clock, camera }: { players: string[]; frames: () => Frame[]; clock: Clock; camera: Camera }) {
  const refs = useRef<(SVGGElement | null)[]>([])
  useClockFrame(clock, (t) => {
    const fs = frames()
    if (!fs.length) return
    const pos = positionsAt(fs, t).players
    players.forEach((id, i) => {
      const p = pos.get(id)
      const g = refs.current[i]
      if (!g) return
      if (!p) {
        g.style.display = 'none'
        return
      }
      const s = camera.project(p)
      const k = camera.scaleAt(p)
      g.style.display = ''
      g.setAttribute('transform', `translate(${s.x.toFixed(1)} ${s.y.toFixed(1)}) scale(${(k / 14).toFixed(3)})`)
    })
  })
  return (
    <>
      {players.map((id, i) => (
        <g key={id} ref={(el) => void (refs.current[i] = el)} className="tele-ring">
          <motion.ellipse
            rx="34"
            ry="13"
            initial={{ opacity: 0, scale: 2.2 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.2 + i * 0.12, ease: EASE_OUT }}
          />
          <motion.ellipse
            className="tele-ring-pulse"
            rx="34"
            ry="13"
            initial={{ opacity: 0.8, scale: 1 }}
            animate={{ opacity: 0, scale: 1.9 }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut', delay: 0.7 }}
          />
        </g>
      ))}
    </>
  )
}

export function TelestrationLayer({
  tele,
  camera,
  frames,
  clock,
}: {
  tele: Telestration
  camera: Camera
  frames: () => Frame[]
  clock: Clock
}) {
  const label = labelPosition(camera, tele)
  return (
    <div className="tele" data-testid="telestration">
      <svg className="tele-svg" width="1920" height="1080" viewBox="0 0 1920 1080" aria-hidden>
        <defs>
          <marker id="tele-head" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--brand)" />
          </marker>
          <pattern id="tele-hatch" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(-35)">
            <line x1="0" y1="0" x2="0" y2="14" stroke="var(--brand)" strokeOpacity="0.32" strokeWidth="3" />
          </pattern>
        </defs>
        {tele.zones.map((z, i) => {
          const p = pts(camera, [
            { x: z.x0, y: z.y0 },
            { x: z.x1, y: z.y0 },
            { x: z.x1, y: z.y1 },
            { x: z.x0, y: z.y1 },
          ])
          return (
            <motion.g
              key={i}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.1 + i * 0.15 }}
            >
              <polygon points={p} className="tele-zone" />
              <polygon points={p} fill="url(#tele-hatch)" />
              <motion.polygon
                points={p}
                className="tele-zone-edge"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.9, delay: 0.15 + i * 0.15, ease: EASE_OUT }}
              />
            </motion.g>
          )
        })}
        {tele.dots.map((d, i) => {
          const s = camera.project(d)
          return (
            <motion.circle
              key={i}
              cx={s.x}
              cy={s.y}
              r={5}
              className="tele-dot"
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 0.95, scale: 1 }}
              transition={{ delay: 0.35 + i * 0.025, duration: 0.25 }}
            />
          )
        })}
        {tele.arrows.map((a, i) => {
          const { d } = arrowPath(camera, a)
          return (
            <motion.path
              key={i}
              d={d}
              className="tele-arrow"
              markerEnd="url(#tele-head)"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ delay: 0.25 + i * 0.18, duration: 0.6, ease: EASE_OUT }}
            />
          )
        })}
        <Rings players={tele.players} frames={frames} clock={clock} camera={camera} />
      </svg>
      <div className="tele-label-anchor" style={{ left: label.left, top: label.top }}>
        <motion.div className="tele-label glass-strong" {...wipe(0.35)}>
          <span className="tele-kicker unskew">From the data · {KIND[tele.kind]}</span>
          <span className="tele-text unskew num">{tele.label}</span>
        </motion.div>
      </div>
    </div>
  )
}

/** "Moment replay" bug: the frame is held so the verified card can be read. */
export function ReplayBug({ remaining, total }: { remaining: number; total: number }) {
  return (
    <div className="replay-anchor" data-testid="replay-bug">
      <motion.div className="replay-bug glass-strong" {...wipe()}>
        <span className="replay-word unskew">
          <i className="replay-dot" />
          Moment replay
        </span>
        <span className="replay-hint unskew">Held so you can read it</span>
        <span className="replay-bar">
          <i style={{ transform: `scaleX(${total ? Math.max(0, remaining / total) : 0})` }} />
        </span>
      </motion.div>
    </div>
  )
}
