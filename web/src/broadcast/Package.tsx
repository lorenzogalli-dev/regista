// Tier-0 broadcast graphics added in D5b: speed badge, shot speed, stat compare, momentum
// ribbon, caption ticker and the recorded/live label. Positions are stage pixels; badges anchor
// to players through the shared projection.

import { motion } from 'motion/react'
import { useRef } from 'react'

import type { TeamColors } from '../lib/color.ts'
import { useClockFrame, type Clock } from '../lib/clock.ts'
import { anchorAt, type Camera } from '../lib/projection.ts'
import { positionsAt, type Frame, type PlayerInfo, type TeamInfo } from '../lib/sample.ts'
import { CountUp } from './CountUp.tsx'
import { surname } from './layout.ts'
import { wipe } from './wipe.ts'

/** A badge that follows a player (speed, shot speed). */
function Following({
  playerId,
  frames,
  clock,
  camera,
  children,
}: {
  playerId: string
  frames: () => Frame[]
  clock: Clock
  camera: Camera
  children: React.ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)
  useClockFrame(clock, (t) => {
    const fs = frames()
    const p = fs.length ? positionsAt(fs, t).players.get(playerId) : undefined
    if (!p || !ref.current) return
    const { left, top } = anchorAt(camera, p)
    ref.current.style.transform = `translate(${left + 1.6 * camera.scaleAt(p) + 12}px, ${top - 3.2 * camera.scaleAt(p) - 20}px)`
  })
  return (
    <div ref={ref} className="badge-anchor">
      {children}
    </div>
  )
}

export function SpeedBadge(props: {
  player: PlayerInfo
  colors: TeamColors
  kmh: number
  frames: () => Frame[]
  clock: Clock
  camera: Camera
}) {
  return (
    <Following playerId={props.player.player_id} frames={props.frames} clock={props.clock} camera={props.camera}>
      <motion.div className="badge glass" {...wipe()}>
        <span className="badge-shirt" style={{ background: props.colors.fill, color: props.colors.ink }}>
          <span className="unskew num">{props.player.shirt}</span>
        </span>
        <span className="badge-body unskew">
          <span className="badge-label">Top speed</span>
          <span className="badge-value num">
            <CountUp value={props.kmh} from={props.kmh - 6} decimals={1} duration={0.5} />
            <small>km/h</small>
          </span>
        </span>
        <Ticks />
      </motion.div>
    </Following>
  )
}

/** Speedometer tick marks that sweep once when the badge lands. */
function Ticks() {
  return (
    <span className="ticks" aria-hidden>
      {Array.from({ length: 7 }, (_, i) => (
        <motion.i
          key={i}
          initial={{ opacity: 0.15 }}
          animate={{ opacity: [0.15, 1, 0.55] }}
          transition={{ delay: 0.15 + i * 0.06, duration: 0.35 }}
        />
      ))}
    </span>
  )
}

export function ShotSpeed(props: {
  player: PlayerInfo
  colors: TeamColors
  kmh: number
  xg: number | null
  outcome: string | null
  frames: () => Frame[]
  clock: Clock
  camera: Camera
}) {
  return (
    <Following playerId={props.player.player_id} frames={props.frames} clock={props.clock} camera={props.camera}>
      <motion.div className="badge glass" {...wipe()}>
        <span className="badge-shirt" style={{ background: props.colors.fill, color: props.colors.ink }}>
          <span className="unskew num">{props.player.shirt}</span>
        </span>
        <span className="badge-body unskew">
          <span className="badge-label">Shot · {surname(props.player.name)}</span>
          <span className="badge-value num">
            <CountUp value={props.kmh} from={props.kmh - 20} decimals={1} duration={0.6} />
            <small>km/h</small>
            {props.xg != null && (
              <span className="badge-xg">
                xG <CountUp value={props.xg} decimals={2} delay={0.3} />
              </span>
            )}
          </span>
        </span>
        <Ticks />
      </motion.div>
    </Following>
  )
}

type Row = { possession_time_based: number | null; field_tilt: number | null; ppda: number | null }

export function StatCompare({
  minutes,
  home,
  away,
  colors,
  rows,
}: {
  minutes: number
  home: TeamInfo
  away: TeamInfo
  colors: Record<string, TeamColors>
  rows: Record<string, Row>
}) {
  const h = rows[home.team_id]
  const a = rows[away.team_id]
  const items: { label: string; h: number | null; a: number | null; pct: boolean; lowerWins?: boolean }[] = [
    { label: 'Time-based possession', h: h?.possession_time_based, a: a?.possession_time_based, pct: true },
    { label: 'Field tilt', h: h?.field_tilt, a: a?.field_tilt, pct: true },
    { label: 'PPDA (lower = more pressing)', h: h?.ppda, a: a?.ppda, pct: false, lowerWins: true },
  ]
  return (
    <div className="stat-anchor" data-testid="stat-compare">
      <motion.div className="stat-compare glass" {...wipe()}>
        <div className="stat-head unskew">
          <span style={{ color: colors[home.team_id].text }}>{home.short}</span>
          <span className="tier0-label">Last {minutes} min</span>
          <span style={{ color: colors[away.team_id].text }}>{away.short}</span>
        </div>
        {items.map((it, i) => {
          const hv = it.h ?? 0
          const av = it.a ?? 0
          const share = it.pct ? hv / Math.max(1e-6, hv + av) : av / Math.max(1e-6, hv + av)
          const fmt = (v: number | null) => (v == null ? '–' : it.pct ? `${Math.round(v * 100)}%` : v.toFixed(1))
          return (
            <div className="stat-row" key={it.label}>
              <span className="stat-num num unskew">{fmt(it.h)}</span>
              <span className="stat-bar">
                <motion.i
                  style={{ background: colors[home.team_id].fill }}
                  initial={{ width: '50%' }}
                  animate={{ width: `${Math.round(share * 100)}%` }}
                  transition={{ delay: 0.3 + i * 0.1, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                />
                <i style={{ background: colors[away.team_id].fill, flex: 1 }} />
              </span>
              <span className="stat-num num unskew">{fmt(it.a)}</span>
              <span className="stat-label unskew">{it.label}</span>
            </div>
          )
        })}
      </motion.div>
    </div>
  )
}

/** Bottom strip: control index over time per team, drawn as two flowing areas. */
export function MomentumRibbon({
  points,
  home,
  away,
  colors,
  endMs,
}: {
  points: { t: number; home: number | null; away: number | null }[]
  home: TeamInfo
  away: TeamInfo
  colors: Record<string, TeamColors>
  endMs: number
}) {
  const W = 1540
  const H = 44
  const x = (t: number) => (t / endMs) * W
  const pts = points.filter((p) => p.home != null && p.away != null)
  const path = (side: 'home' | 'away') => {
    if (!pts.length) return ''
    const y = (p: (typeof pts)[number]) => {
      const d = Math.max(-1, Math.min(1, ((p.home as number) - (p.away as number)) / 40)) // ±40 pts = full height
      return side === 'home' ? H / 2 - Math.max(0, d) * H * 0.9 : H / 2 + Math.max(0, -d) * H * 0.9
    }
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p).toFixed(1)}`).join(' ')
    return `${line} L${x(pts[pts.length - 1].t).toFixed(1)},${H / 2} L${x(pts[0].t).toFixed(1)},${H / 2} Z`
  }
  return (
    <div className="ribbon-anchor" data-testid="momentum-ribbon">
      <div className="ribbon glass">
        <span className="ribbon-label unskew">
          <span style={{ color: colors[home.team_id].text }}>{home.short}</span>
          <span className="tier0-label">Control</span>
          <span style={{ color: colors[away.team_id].text }}>{away.short}</span>
        </span>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="ribbon-svg" aria-hidden>
          <line x1="0" x2={W} y1={H / 2} y2={H / 2} stroke="rgba(242,245,243,0.18)" />
          <line x1={x(endMs / 2)} x2={x(endMs / 2)} y1="4" y2={H - 4} stroke="rgba(242,245,243,0.18)" />
          <path d={path('home')} fill={colors[home.team_id].line} opacity="0.75" />
          <path d={path('away')} fill={colors[away.team_id].line} opacity="0.75" />
        </svg>
      </div>
    </div>
  )
}

export function Caption({ text }: { text: string }) {
  return (
    <div className="caption-anchor" data-testid="caption">
      <motion.div className="caption glass-strong" {...wipe()}>
        <span className="ai-dot" />
        <span className="caption-text unskew">{text}</span>
      </motion.div>
    </div>
  )
}

export function SourceLabel({ kind }: { kind: 'Recorded agent run' | 'Live' }) {
  return (
    <div className="source-anchor" data-testid="source-label">
      <div className={`source glass ${kind === 'Live' ? 'live' : ''}`}>
        <span className="unskew">
          {kind === 'Live' && <span className="live-dot" />}
          {kind}
        </span>
      </div>
    </div>
  )
}
