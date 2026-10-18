// A short clip of a generated match (exported by `python -m metrics.export_sample`): public
// tracking and events plus numbers computed by the metrics tools. Used for design work (D5a).

import type { Vec2 } from './projection.ts'

export type PlayerInfo = {
  player_id: string
  team_id: string
  name: string
  shirt: number
  position: string
  starter: boolean
}

export type TeamInfo = { team_id: string; name: string; short: string; formation: string }

export type Frame = {
  t_ms: number
  period: number
  ball: { x: number; y: number; z: number; speed_ms: number }
  players: { player_id: string; x: number; y: number; speed_ms: number }[]
}

export type MatchEvent = {
  event_id: string
  t_ms: number
  type: string
  team_id: string | null
  player_id: string | null
  x: number
  y: number
  end_x: number | null
  end_y: number | null
  outcome: string | null
  recipient_id: string | null
}

export type PassCardData = {
  event_id: string
  t_ms: number
  player_id: string
  recipient_id: string
  team_id: string
  x: number
  y: number
  end_x: number
  end_y: number
  pass_length_m: number
  pass_progression_m: number
  pass_difficulty: number
  ball_speed_ms: number | null
}

export type MetricDelta = { metric: string; before: number | null; after: number | null; delta: number | null }

export type Sample = {
  note: string
  match: { match_id: string; competition: string; venue: string; home: TeamInfo; away: TeamInfo; players: PlayerInfo[] }
  colors: Record<string, string[]>
  period_end_ms: number[]
  clip: { start_ms: number; end_ms: number; pass_ms: number }
  score: Record<string, number>
  pass_card: PassCardData
  window: { team_id: string; minutes: number; deltas: Record<string, MetricDelta> }
  frames: Frame[]
  events: MatchEvent[]
}

export async function loadSample(url: string): Promise<Sample> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url}: ${r.status}`)
  return (await r.json()) as Sample
}

export type Positions = { players: Map<string, Vec2>; ball: Vec2 & { z: number } }

/** Positions at `t` by linear interpolation between the two surrounding 10 Hz frames. */
export function positionsAt(frames: Frame[], t: number): Positions {
  let i = 0
  let hi = frames.length - 1
  while (i < hi) {
    const mid = (i + hi + 1) >> 1
    if (frames[mid].t_ms <= t) i = mid
    else hi = mid - 1
  }
  const a = frames[i]
  const b = frames[Math.min(i + 1, frames.length - 1)]
  const span = b.t_ms - a.t_ms
  const k = span > 0 ? Math.min(1, Math.max(0, (t - a.t_ms) / span)) : 0
  const lerp = (u: number, v: number) => u + (v - u) * k
  const bp = new Map(b.players.map((p) => [p.player_id, p]))
  const players = new Map<string, Vec2>()
  for (const p of a.players) {
    const q = bp.get(p.player_id) ?? p
    players.set(p.player_id, { x: lerp(p.x, q.x), y: lerp(p.y, q.y) })
  }
  return {
    players,
    ball: { x: lerp(a.ball.x, b.ball.x), y: lerp(a.ball.y, b.ball.y), z: lerp(a.ball.z, b.ball.z) },
  }
}

/** Broadcast clock "mm:ss" (second half continues from 45:00). */
export function matchClock(t: number, periodEndMs: number[]): string {
  const s = t < periodEndMs[0] ? Math.floor(t / 1000) : 45 * 60 + Math.floor((t - periodEndMs[0]) / 1000)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

/** Team in possession at `t`: the team of the last on-ball event. */
export function possessionAt(events: MatchEvent[], t: number): string | null {
  let team: string | null = null
  for (const e of events) {
    if (e.t_ms > t) break
    if (e.team_id && ['pass', 'carry', 'shot', 'ball_recovery', 'interception', 'kickoff'].includes(e.type)) {
      team = e.team_id
    }
  }
  return team
}
