// One client for recorded agent runs and live sessions: both speak the same messages
// (`run`, `meta`, `frame`, `event`, `overlay`, `pipeline`, `notice`, `end`). The match clock
// follows the stream, rendered a little behind the newest frame so positions interpolate.

import { useEffect, useState } from 'react'

import type { Clock } from './clock.ts'
import type { Frame, MatchEvent, PlayerInfo, TeamInfo } from './sample.ts'

export type Overlay = {
  overlay_id: string
  source_moment_id: string | null
  tier: 0 | 1
  show_at_ms: number
  duration_ms: number
  priority: number
  kind: string
  anchor: { type: string; player_id?: string; x?: number; y?: number }
  payload: Record<string, any>
}

export type PipelineEvent = {
  type: 'pipeline'
  moment_id: string
  stage: string
  phase: 'start' | 'end' | 'verdict'
  outcome?: string
  ms?: number
  detail?: string
  at_ms?: number
}

export type RunHeader = {
  kind: 'Recorded agent run' | 'Live'
  run_id?: string | null
  match_id: string
  models?: Record<string, string>
  provider?: string
  usage?: { calls?: number; cost_eur?: number }
  provenance?: string | null
  featured_rejection?: { moment_id: string; note: string } | null
}

export type MatchMeta = {
  match_id: string
  home: TeamInfo & { colors: string[] }
  away: TeamInfo & { colors: string[] }
  players: PlayerInfo[]
  period_end_ms: number[]
}

const KEEP_FRAMES = 300 // 30 s of 10 Hz frames
const RENDER_DELAY_MS = 250

export class MatchStream {
  header: RunHeader | null = null
  meta: MatchMeta | null = null
  frames: Frame[] = []
  events: MatchEvent[] = []
  overlays: Overlay[] = []
  pipeline: PipelineEvent[] = []
  notices: string[] = []
  ended = false
  error: string | null = null
  speed: number
  private lastT = 0
  private lastWall = 0
  private ws: WebSocket | null = null
  private subs = new Set<() => void>()

  constructor(url: string, speed: number) {
    this.speed = speed
    this.ws = new WebSocket(url)
    this.ws.onmessage = (ev) => this.onMessage(JSON.parse(ev.data as string))
    this.ws.onerror = () => {
      this.error = 'connection failed'
      this.notify()
    }
  }

  close() {
    this.ws?.close()
  }

  subscribe(fn: () => void): () => void {
    this.subs.add(fn)
    return () => this.subs.delete(fn)
  }

  private notify() {
    this.subs.forEach((fn) => fn())
  }

  private onMessage(m: any) {
    switch (m.type) {
      case 'run':
        this.header = m.data
        break
      case 'meta':
        this.meta = m.data
        break
      case 'frame':
        this.frames.push(m.data)
        if (this.frames.length > KEEP_FRAMES) this.frames.splice(0, this.frames.length - KEEP_FRAMES)
        this.lastT = m.data.t_ms
        this.lastWall = performance.now()
        return // frames are read by the clock; no React update per frame
      case 'event':
        this.events.push(m.data)
        break
      case 'overlay':
        this.overlays.push(m.data)
        break
      case 'pipeline':
        this.pipeline.push({ ...m, at_ms: m.at_ms ?? this.lastT })
        break
      case 'notice':
        this.notices.push(m.detail)
        break
      case 'error':
        this.error = m.detail
        break
      case 'end':
        this.ended = true
        break
    }
    this.notify()
  }

  /** Render time: just behind the newest frame, advancing smoothly between frames. */
  now(): number {
    if (!this.lastWall) return 0
    const el = (performance.now() - this.lastWall) * this.speed
    const ahead = Math.min(el, 1000 * this.speed)
    return Math.max(0, this.lastT + ahead - RENDER_DELAY_MS * this.speed)
  }
}

/** A Clock driven by the stream (requestAnimationFrame). */
export function streamClock(s: MatchStream): Clock & { stop(): void } {
  const subs = new Set<(t: number) => void>()
  let raf = 0
  const step = () => {
    const t = s.now()
    subs.forEach((fn) => fn(t))
    raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)
  return {
    now: () => s.now(),
    subscribe(fn) {
      subs.add(fn)
      fn(s.now())
      return () => subs.delete(fn)
    },
    stop: () => cancelAnimationFrame(raf),
  }
}

export type Source = { kind: 'recorded'; runId: string } | { kind: 'live'; matchId: string }

export function streamUrl(src: Source, speed: number, fromMs = 0): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const base = `${proto}://${window.location.host}`
  return src.kind === 'recorded'
    ? `${base}/ws/recorded/${src.runId}?speed=${speed}&from_ms=${fromMs}`
    : `${base}/ws/live/${src.matchId}?speed=${speed}`
}

/** Open a stream for the component's lifetime; re-renders on non-frame messages. The stream is
 * created inside the effect, so a remount (StrictMode) opens a fresh connection. */
export function useMatchStream(src: Source | null, speed: number, fromMs = 0) {
  const url = src ? streamUrl(src, speed, fromMs) : null
  const [state, setState] = useState<{ stream: MatchStream; clock: Clock & { stop(): void } } | null>(null)
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!url) return
    const stream = new MatchStream(url, speed)
    const clock = streamClock(stream)
    const unsub = stream.subscribe(() => setTick((n) => n + 1))
    // The stream is an external system opened here; storing it is the subscription itself.
    // eslint-disable-next-line react/set-state-in-effect
    setState({ stream, clock })
    return () => {
      unsub()
      stream.close()
      clock.stop()
      setState(null)
    }
  }, [url, speed])
  return { stream: state?.stream ?? null, clock: state?.clock ?? null }
}

/** Overlays on air at `t`: a verified card hides the template it replaces; a withdrawal hides
 * its template from then on. */
export function activeOverlays(all: Overlay[], t: number): Overlay[] {
  const replacedAt = new Map<string, number>()
  for (const o of all) {
    const r = o.payload.replaces as string | undefined
    if (r && o.show_at_ms <= t) replacedAt.set(r, Math.min(replacedAt.get(r) ?? Infinity, o.show_at_ms))
  }
  return all.filter(
    (o) =>
      o.show_at_ms <= t &&
      t < o.show_at_ms + o.duration_ms &&
      !(replacedAt.has(o.overlay_id) && (replacedAt.get(o.overlay_id) ?? Infinity) <= t),
  )
}
