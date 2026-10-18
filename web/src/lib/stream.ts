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
  /** Playback rate (recorded runs can change it: 0 holds, 1 is the starting speed's pace). */
  rate: number
  private lastT = -1
  private anchorT = 0
  private anchorWall = 0
  private ws: WebSocket | null = null
  private subs = new Set<() => void>()
  private firstFrame: (() => void) | null = null

  constructor(url: string, speed: number, onFirstFrame?: () => void) {
    this.speed = speed
    this.rate = speed
    this.firstFrame = onFirstFrame ?? null
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

  /** Change the playback rate here and on the server (recorded runs; live sessions ignore it). */
  setRate(rate: number) {
    if (rate === this.rate) return
    const t = this.now()
    this.anchorT = t
    this.anchorWall = performance.now()
    this.rate = rate
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: 'pace', speed: rate }))
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
        if (this.lastT < 0) {
          this.anchorT = m.data.t_ms - RENDER_DELAY_MS * Math.max(1, this.rate)
          this.anchorWall = performance.now()
        }
        this.lastT = m.data.t_ms
        if (this.firstFrame) {
          const fn = this.firstFrame
          this.firstFrame = null
          fn()
        }
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

  /** Render time: advances at the playback rate, just behind the newest frame. It never runs
   * past the data and catches up if it falls far behind (a stalled connection). */
  now(): number {
    if (this.lastT < 0) return 0
    const wall = performance.now()
    let t = this.anchorT + (wall - this.anchorWall) * this.rate
    const lead = RENDER_DELAY_MS * Math.max(1, this.rate)
    if (t > this.lastT) {
      t = this.lastT
      this.anchorT = t
      this.anchorWall = wall
    } else if (this.lastT - t > 2000 * Math.max(1, this.rate) + lead) {
      t = this.lastT - lead
      this.anchorT = t
      this.anchorWall = wall
    }
    return Math.max(0, t)
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
 * created inside the effect, so a remount (StrictMode) opens a fresh connection. When the URL
 * changes (a seek), the previous stream stays on screen until the new one has its first frame. */
export function useMatchStream(src: Source | null, speed: number, fromMs = 0) {
  const url = src ? streamUrl(src, speed, fromMs) : null
  const [state, setState] = useState<{ stream: MatchStream; clock: Clock & { stop(): void } } | null>(null)
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!url) return
    let live: { stream: MatchStream; clock: Clock & { stop(): void } } | null = null
    const stream: MatchStream = new MatchStream(url, speed, () => {
      const clock = streamClock(stream)
      live = { stream, clock }
      setState(live)
    })
    const unsub = stream.subscribe(() => {
      if (stream.error && !live) {
        live = { stream, clock: streamClock(stream) }
        setState(live)
      }
      setTick((n) => n + 1)
    })
    return () => {
      unsub()
      stream.close()
      live?.clock.stop()
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
