// Player for recorded agent runs: seek, pause, "next key moment", auto-skip of quiet play and
// the moment replay (slow down, hold while the verified card is read, then play on). The
// stream does the pacing (`MatchStream.setRate` also tells the server); this hook decides
// the rate from the run's full overlay timeline, which is known up front.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { Telestration } from '../broadcast/Telestration.tsx'
import { useClockTick } from './clock.ts'
import { useMatchStream, type Overlay } from './stream.ts'

export type MarkerKind = 'insight' | 'data' | 'goal' | 'red_card' | 'shot' | 'rejection'

export type Marker = {
  t: number
  kind: MarkerKind
  tier: 0 | 1 | null
  label: string
  /** Where "go to this moment" lands. */
  seekTo: number
}

type RunMoment = {
  moment_id: string
  status: string
  candidate: { t_ms: number; kind: string }
  explanation: { player_ids: string[]; mechanism_tag: string } | null
}

export type RunData = { run_id: string; match_id: string; overlays: Overlay[]; moments: RunMoment[] }

export type TimelineData = {
  duration_ms: number
  period_end_ms: number[]
  highlights: { t_ms: number; kind: 'goal' | 'red_card' | 'shot'; team_id: string | null; player_id: string | null }[]
  rejections: { t_ms: number; moment_id: string; stage: string; detail: string }[]
  telestration: Telestration[]
}

const LEAD_MS = 20_000 // "next key moment" lands this long before it
const SKIP_RATE = 8
const QUIET_MS = 25_000 // fast-forward when nothing is on air and the next moment is further away
const SKIP_STOP_BEFORE_MS = 6_000
const SLOW_RATE = 0.3
const SLOW_WALL_MS = 700
const MIN_HOLD_MS = 6_000
const MAX_HOLD_MS = 16_000

/** How long to hold a card: reading time for its words (~4 words/s) plus a beat, at least 6 s. */
export function holdMs(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length
  return Math.min(MAX_HOLD_MS, Math.max(MIN_HOLD_MS, (words / 4) * 1000 + 2000))
}

const DATA_LABEL: Record<string, string> = {
  pass_card: 'Pass card',
  speed_badge: 'Top speed',
  shot_speed: 'Shot speed',
}

export function buildMarkers(run: RunData | null, tl: TimelineData | null): Marker[] {
  const out: Marker[] = []
  for (const o of run?.overlays ?? []) {
    if (o.kind === 'moment_card' && o.payload.state === 'verified') {
      const head = o.payload.texts?.analyst_en?.headline ?? o.payload.mechanism_tag
      out.push({ t: o.show_at_ms, kind: 'insight', tier: 1, label: `AI insight · ${head}`, seekTo: o.show_at_ms - LEAD_MS })
    } else if (o.kind in DATA_LABEL) {
      const v = o.payload.value
      const label = o.kind === 'pass_card' ? 'Pass card' : `${DATA_LABEL[o.kind]} · ${v?.toFixed?.(1) ?? ''} km/h`
      out.push({ t: o.show_at_ms, kind: 'data', tier: 0, label, seekTo: o.show_at_ms - 8_000 })
    }
  }
  for (const h of tl?.highlights ?? []) {
    out.push({
      t: h.t_ms,
      kind: h.kind,
      tier: null,
      label: h.kind === 'goal' ? 'Goal' : h.kind === 'red_card' ? 'Red card' : 'Shot',
      seekTo: h.t_ms - (h.kind === 'shot' ? 8_000 : 15_000),
    })
  }
  for (const r of tl?.rejections ?? []) {
    out.push({ t: r.t_ms, kind: 'rejection', tier: 1, label: 'Verifier rejected a claim', seekTo: r.t_ms - LEAD_MS })
  }
  return out.sort((a, b) => a.t - b.t)
}

/** Kinds that make a moment worth stopping fast-forward for. */
const SKIP_STOPS: MarkerKind[] = ['insight', 'data', 'goal', 'red_card', 'shot', 'rejection']
/** Kinds "next key moment" jumps between. */
const KEY: MarkerKind[] = ['insight', 'goal', 'red_card', 'rejection']

export type ReplayState = { overlayId: string; tele: Telestration | null; phase: 'slow' | 'hold'; until: number; total: number }

export function usePlayer(opts: {
  runId: string | null
  speed?: number
  from?: number
  persona: string
  autoSkip?: boolean
  momentReplay?: boolean
  /** Space / N shortcuts (off when a page has its own). */
  keys?: boolean
  /** Longer replay holds (guided tour), as a factor on the reading time. */
  holdScale?: number
}) {
  const base = opts.speed ?? 1
  const [from, setFrom] = useState(opts.from ?? 0)
  const source = useMemo(() => (opts.runId ? ({ kind: 'recorded', runId: opts.runId } as const) : null), [opts.runId])
  const { stream, clock } = useMatchStream(source, base, from)
  const t = useClockTick(clock, 100)

  const [run, setRun] = useState<RunData | null>(null)
  const [tl, setTl] = useState<TimelineData | null>(null)
  useEffect(() => {
    if (!opts.runId) return
    fetch(`/api/runs/${opts.runId}`)
      .then((r) => r.json() as Promise<RunData>)
      .then(setRun)
      .catch(() => setRun(null))
    fetch(`/api/runs/${opts.runId}/timeline`)
      .then((r) => r.json() as Promise<TimelineData>)
      .then(setTl)
      .catch(() => setTl(null))
  }, [opts.runId])

  const markers = useMemo(() => buildMarkers(run, tl), [run, tl])
  const verified = useMemo(
    () => (run?.overlays ?? []).filter((o) => o.kind === 'moment_card' && o.payload.state === 'verified'),
    [run],
  )
  const onAirKinds = useMemo(
    () => (run?.overlays ?? []).filter((o) => !['momentum_bar', 'stat_compare', 'caption'].includes(o.kind)),
    [run],
  )

  const [paused, setPaused] = useState(false)
  const [autoSkip, setAutoSkip] = useState(opts.autoSkip ?? true)
  const [momentReplay, setMomentReplay] = useState(opts.momentReplay ?? true)
  const [skipping, setSkipping] = useState(false)
  const [replay, setReplay] = useState<ReplayState | null>(null)
  const [wall, setWall] = useState(0)
  const replayed = useRef(new Set<string>())
  const lastT = useRef(0)
  // Between a seek and the new stream's first frame the old (frozen) clock is still around.
  const seekPending = useRef(false)
  useEffect(() => {
    seekPending.current = false
    if (clock) lastT.current = clock.now()
  }, [stream, clock])

  // The rate the stream should play at, from the current state.
  const rate = paused ? 0 : replay ? (replay.phase === 'slow' ? SLOW_RATE * base : 0) : skipping ? SKIP_RATE * base : base
  useEffect(() => {
    stream?.setRate(rate)
  }, [stream, rate])

  const seek = useCallback(
    (ms: number) => {
      const target = Math.max(0, Math.round(ms))
      // Seeking back re-arms the replays still ahead.
      for (const o of verified) if (o.show_at_ms >= target) replayed.current.delete(o.overlay_id)
      lastT.current = target
      seekPending.current = true
      setReplay(null)
      setSkipping(false)
      setPaused(false)
      // The same position twice still has to reconnect (the URL must change).
      setFrom((f) => (f === target ? target + 1 : target))
    },
    [verified],
  )

  const endReplay = useCallback(() => setReplay(null), [])

  const next = useCallback(() => {
    const now = clock?.now() ?? t
    const m = markers.find((x) => KEY.includes(x.kind) && x.seekTo > now + 1_000)
    if (m) seek(m.seekTo)
  }, [clock, t, markers, seek])

  // Drive replay and auto-skip from the match clock (100 ms ticks) and the wall clock.
  useEffect(() => {
    if (!stream || !clock) return
    const id = window.setInterval(() => {
      if (seekPending.current) return
      const now = clock.now()
      const w = performance.now()
      setWall(w)
      const prev = lastT.current
      lastT.current = now
      if (replay) {
        if (replay.phase === 'slow' && w >= replay.until) {
          setReplay({ ...replay, phase: 'hold', until: w + replay.total })
        } else if (replay.phase === 'hold' && w >= replay.until) {
          setReplay(null)
        }
        return
      }
      if (paused) return
      // A verified card just went on air: replay it.
      if (momentReplay) {
        const card = verified.find(
          (o) => !replayed.current.has(o.overlay_id) && o.show_at_ms > prev - 50 && o.show_at_ms <= now + 50,
        )
        if (card) {
          replayed.current.add(card.overlay_id)
          const text = card.payload.texts?.[opts.persona] ?? card.payload.texts?.analyst_en ?? { headline: '', text: card.payload.claim }
          const tele = tl?.telestration.find((x) => x.moment_id === card.source_moment_id) ?? null
          setSkipping(false)
          setReplay({ overlayId: card.overlay_id, tele, phase: 'slow', until: w + SLOW_WALL_MS, total: holdMs(`${text.headline} ${text.text}`) * (opts.holdScale ?? 1) })
          return
        }
      }
      if (!autoSkip) {
        if (skipping) setSkipping(false)
        return
      }
      const onAir = onAirKinds.some((o) => o.show_at_ms <= now && now < o.show_at_ms + o.duration_ms)
      const nextStop = markers.find((m) => SKIP_STOPS.includes(m.kind) && m.t > now)
      const gap = (nextStop?.t ?? (tl?.duration_ms ?? Infinity)) - now
      if (skipping) {
        if (onAir || gap <= SKIP_STOP_BEFORE_MS) setSkipping(false)
      } else if (!onAir && gap > QUIET_MS) {
        setSkipping(true)
      }
    }, 100)
    return () => window.clearInterval(id)
  }, [stream, clock, replay, paused, momentReplay, autoSkip, skipping, verified, onAirKinds, markers, tl, opts.persona, opts.holdScale])

  // Keyboard: Space pauses / ends a replay, N jumps to the next key moment.
  const keys = opts.keys ?? true
  useEffect(() => {
    if (!keys) return
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.metaKey || e.ctrlKey) return
      if (e.key === 'n' || e.key === 'N') {
        e.preventDefault()
        next()
      } else if (e.key === ' ') {
        e.preventDefault()
        if (replay) endReplay()
        else setPaused((p) => !p)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [keys, next, replay, endReplay])

  const replayView = replay
    ? {
        tele: replay.tele,
        remaining: replay.phase === 'slow' ? replay.total : Math.max(0, replay.until - wall),
        total: replay.total,
      }
    : null

  return {
    stream,
    clock,
    t,
    run,
    timeline: tl,
    markers,
    seek,
    next,
    paused,
    setPaused,
    autoSkip,
    setAutoSkip,
    momentReplay,
    setMomentReplay,
    skipping,
    replay: replayView,
    endReplay,
  }
}

export type Player = ReturnType<typeof usePlayer>
