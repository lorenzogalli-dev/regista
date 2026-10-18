import { useRef, useState } from 'react'

import type { Marker } from '../lib/player.ts'
import { matchClock } from '../lib/sample.ts'

// Match timeline under the broadcast: AI insights (tier 1, cyan) and data graphics (tier 0,
// green) on separate lanes, plus goals, red cards, shots and Verifier rejections. Clicking a
// marker goes to just before that moment; clicking the track goes to that time.

const LANE: Record<Marker['kind'], number> = { insight: 0, rejection: 0, data: 1, goal: 2, red_card: 2, shot: 2 }

function ticks(periodEnd: number[]): { ms: number; label: string }[] {
  const out = []
  for (let m = 0; m <= 45; m += 15) out.push({ ms: m * 60_000, label: `${m}'` })
  for (let m = 60; m <= 90; m += 15) out.push({ ms: periodEnd[0] + (m - 45) * 60_000, label: `${m}'` })
  return out.filter((x) => x.ms <= periodEnd[periodEnd.length - 1])
}

export function Timeline({
  t,
  duration,
  periodEnd,
  markers,
  onSeek,
}: {
  t: number
  duration: number
  periodEnd: number[]
  markers: Marker[]
  onSeek: (ms: number) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<{ x: number; label: string } | null>(null)
  const pct = (ms: number) => `${Math.min(100, Math.max(0, (ms / duration) * 100))}%`
  const fromEvent = (clientX: number) => {
    const r = ref.current!.getBoundingClientRect()
    return Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * duration
  }
  return (
    <div className="tl" data-testid="timeline">
      <div
        className="tl-body"
        ref={ref}
        onClick={(e) => onSeek(fromEvent(e.clientX))}
        onMouseMove={(e) => {
          if ((e.target as HTMLElement).closest('.tl-marker')) return
          const ms = fromEvent(e.clientX)
          setHover({ x: (ms / duration) * 100, label: `Go to ${matchClock(ms, periodEnd)}` })
        }}
        onMouseLeave={() => setHover(null)}
        role="slider"
        aria-label="Match timeline"
        aria-valuemin={0}
        aria-valuemax={duration}
        aria-valuenow={Math.round(t)}
        aria-valuetext={matchClock(t, periodEnd)}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight') onSeek(t + 30_000)
          if (e.key === 'ArrowLeft') onSeek(t - 30_000)
        }}
      >
        <div className="tl-track">
          <i className="tl-played" style={{ width: pct(t) }} />
          <i className="tl-half" style={{ left: pct(periodEnd[0]) }} />
        </div>
        {markers.map((m, i) => (
          <button
            key={i}
            type="button"
            className={`tl-marker ${m.kind} lane-${LANE[m.kind]} ${m.t <= t ? 'past' : ''}`}
            style={{ left: pct(m.t) }}
            aria-label={`${m.label} at ${matchClock(m.t, periodEnd)}`}
            onClick={(e) => {
              e.stopPropagation()
              onSeek(m.seekTo)
            }}
            onMouseEnter={() => setHover({ x: (m.t / duration) * 100, label: `${matchClock(m.t, periodEnd)} · ${m.label}` })}
            onMouseLeave={() => setHover(null)}
          />
        ))}
        <i className="tl-head" style={{ left: pct(t) }} />
        {hover && (
          <span className="tl-tip" style={{ left: `${Math.min(88, Math.max(12, hover.x))}%` }}>
            {hover.label}
          </span>
        )}
      </div>
      <div className="tl-ticks" aria-hidden>
        {ticks(periodEnd).map((x) => (
          <span key={x.label} style={{ left: pct(x.ms) }}>
            {x.label}
          </span>
        ))}
      </div>
      <div className="tl-legend">
        <span>
          <i className="tl-key insight" /> AI insight, verified
        </span>
        <span>
          <i className="tl-key data" /> Data graphic, computed by code
        </span>
        <span>
          <i className="tl-key goal" /> Goal
        </span>
        <span>
          <i className="tl-key shot" /> Shot
        </span>
        <span>
          <i className="tl-key red_card" /> Red card
        </span>
        <span>
          <i className="tl-key rejection" /> Verifier rejection
        </span>
      </div>
    </div>
  )
}
