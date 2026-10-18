import { motion, AnimatePresence } from 'motion/react'

import { ProgramFrame } from '../broadcast/ProgramFrame.tsx'
import { useClockTick } from '../lib/clock.ts'
import { useSource } from '../lib/hooks.ts'
import { matchClock } from '../lib/sample.ts'
import { useMatchStream, type PipelineEvent } from '../lib/stream.ts'
import './control.css'

// Control room (DESIGN.md §5.4): the multi-agent pipeline as it runs. Each candidate flows
// Candidate (code) → Detector → Analyst ⇄ Verifier (code + agent) → Narrator · Persona · Director.
// /control?run=<run_id>&speed=4&from=<ms>   or   /control?live=m_1000

type Node = { id: string; label: string; kind: 'code' | 'agent' | 'hybrid'; model?: string; x: number; y: number }

const NODES: Node[] = [
  { id: 'candidate', label: 'Candidates', kind: 'code', x: 70, y: 150 },
  { id: 'detector', label: 'Detector', kind: 'agent', model: 'fast', x: 270, y: 150 },
  { id: 'analyst', label: 'Analyst', kind: 'agent', model: 'reasoning', x: 470, y: 150 },
  { id: 'verifier', label: 'Verifier', kind: 'hybrid', model: 'code + fast', x: 670, y: 150 },
  { id: 'narrator', label: 'Narrator', kind: 'agent', model: 'fast', x: 880, y: 50 },
  { id: 'persona', label: 'Persona ×9', kind: 'agent', model: 'fast', x: 880, y: 150 },
  { id: 'director', label: 'Director', kind: 'agent', model: 'fast', x: 880, y: 250 },
  { id: 'result', label: 'On air', kind: 'code', x: 1070, y: 150 },
]
const EDGES: [string, string][] = [
  ['candidate', 'detector'],
  ['detector', 'analyst'],
  ['analyst', 'verifier'],
  ['verifier', 'narrator'],
  ['verifier', 'persona'],
  ['verifier', 'director'],
  ['narrator', 'result'],
  ['persona', 'result'],
  ['director', 'result'],
]

const nodeOf = (stage: string) => stage.split(/[#:]/)[0]

type MomentRow = {
  id: string
  at: number
  kind: string
  stages: { stage: string; outcome?: string; ms?: number; detail?: string; running: boolean }[]
  result?: string
  reason?: string
}

function rows(events: PipelineEvent[]): MomentRow[] {
  const by = new Map<string, MomentRow>()
  for (const e of events) {
    let r = by.get(e.moment_id)
    if (!r) {
      r = { id: e.moment_id, at: e.at_ms ?? 0, kind: '', stages: [] }
      by.set(e.moment_id, r)
    }
    if (e.stage === 'candidate') r.kind = e.detail ?? ''
    else if (e.stage === 'result') {
      r.result = e.outcome
      r.reason = e.detail
    } else if (e.phase === 'start') r.stages.push({ stage: e.stage, running: true })
    else if (e.phase === 'end') {
      const s = [...r.stages].reverse().find((x) => x.stage === e.stage && x.running)
      if (s) Object.assign(s, { running: false, outcome: e.outcome, ms: e.ms, detail: e.detail })
      else r.stages.push({ stage: e.stage, running: false, outcome: e.outcome, ms: e.ms, detail: e.detail })
    }
  }
  return [...by.values()].sort((a, b) => b.at - a.at)
}

function median(xs: number[]): number | null {
  if (!xs.length) return null
  const s = [...xs].sort((a, b) => a - b)
  return s[Math.floor(s.length / 2)]
}

function outcomeClass(o?: string) {
  if (!o) return 'running'
  if (o === 'ok' || o === 'approved' || o === 'published') return 'ok'
  if (o === 'rejected' || o === 'dropped') return 'bad'
  return 'warn'
}

export function Control() {
  const params = new URLSearchParams(window.location.search)
  const source = useSource(params)
  const speed = Number(params.get('speed') ?? 4)
  const from = Number(params.get('from') ?? 0)
  const { stream, clock } = useMatchStream(source, speed, from)
  const t = useClockTick(clock, 200)
  if (stream?.error) return <p style={{ padding: 40 }}>{stream.error}</p>
  if (!stream || !clock) return null

  const events = stream.pipeline.filter((e) => (e.at_ms ?? 0) <= t)
  const moments = rows(events)
  const active = new Set(moments.flatMap((m) => m.stages.filter((s) => s.running).map((s) => nodeOf(s.stage))))
  const last = new Map<string, { outcome?: string; ms?: number }>()
  const lat = new Map<string, number[]>()
  for (const m of [...moments].reverse()) {
    for (const s of m.stages) {
      if (s.running) continue
      last.set(nodeOf(s.stage), { outcome: s.outcome, ms: s.ms })
      if (s.ms != null) lat.set(nodeOf(s.stage), [...(lat.get(nodeOf(s.stage)) ?? []), s.ms])
    }
    if (m.result) last.set('result', { outcome: m.result })
  }
  const counts = {
    candidates: moments.length,
    published: moments.filter((m) => m.result === 'published' || m.result === 'approved').length,
    dropped: moments.filter((m) => m.result === 'dropped').length,
    rejections: moments.reduce((n, m) => n + m.stages.filter((s) => s.outcome === 'rejected').length, 0),
    fallbacks: moments.reduce((n, m) => n + m.stages.filter((s) => s.outcome === 'timeout' || s.outcome?.startsWith('error')).length, 0),
  }
  const models = stream.header?.models ?? {}
  const pos = new Map(NODES.map((n) => [n.id, n]))

  return (
    <main className="control">
      <header className="control-head">
        <div>
          <p className="eyebrow">Control room · {stream.header?.kind ?? ''}</p>
          <h1>Agent pipeline</h1>
        </div>
        <div className="control-meta num">
          <span className="clock">{stream.meta ? matchClock(t, stream.meta.period_end_ms) : '--:--'}</span>
          <span>
            {stream.meta?.home.short} v {stream.meta?.away.short} · {speed}×
          </span>
          <span>
            fast: {models.fast ?? '–'} · reasoning: {models.reasoning ?? '–'}
          </span>
        </div>
      </header>

      <section className="graph-wrap glass">
        <svg viewBox="0 0 1140 300" className="graph" role="img" aria-label="agent pipeline graph">
          {EDGES.map(([a, b]) => {
            const p = pos.get(a)!
            const q = pos.get(b)!
            const hot = active.has(b) || (active.has(a) && b === 'result')
            return (
              <line
                key={a + b}
                x1={p.x + 70}
                y1={p.y}
                x2={q.x - 70}
                y2={q.y}
                className={`edge ${hot ? 'hot' : ''}`}
              />
            )
          })}
          <path d="M 600 178 C 580 230, 500 230, 480 178" className="edge retry" markerEnd="url(#arrow)" />
          <text x="540" y="238" className="edge-label">
            retry once with the reason
          </text>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--error)" />
            </marker>
          </defs>
          {NODES.map((n) => {
            const l = last.get(n.id)
            const med = median(lat.get(n.id) ?? [])
            return (
              <g key={n.id} transform={`translate(${n.x - 70}, ${n.y - 34})`} className={`node ${n.kind} ${active.has(n.id) ? 'active' : ''}`}>
                <rect width="140" height="68" rx="2" transform="skewX(-5)" />
                <text x="70" y="26" className="node-label">
                  {n.label}
                </text>
                <text x="70" y="44" className="node-sub">
                  {n.kind === 'code' ? 'code' : n.model}
                </text>
                <text x="70" y="60" className={`node-stat ${outcomeClass(l?.outcome)}`}>
                  {med != null ? `p50 ${(med / 1000).toFixed(1)} s` : l?.outcome ?? ''}
                </text>
              </g>
            )
          })}
        </svg>
        <div className="counters num">
          <span>
            <b>{counts.candidates}</b> candidates
          </span>
          <span className="ok">
            <b>{counts.published}</b> verified
          </span>
          <span className="bad">
            <b>{counts.rejections}</b> Verifier rejections
          </span>
          <span>
            <b>{counts.dropped}</b> dropped
          </span>
          <span className="warn">
            <b>{counts.fallbacks}</b> fallbacks
          </span>
        </div>
      </section>

      <div className="control-body">
        <section className="feed">
          <h2>Moments</h2>
          <AnimatePresence initial={false}>
            {moments.map((m) => (
              <motion.article
                key={m.id}
                className={`moment-row ${outcomeClass(m.result)}`}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3 }}
                layout
              >
                <div className="row-head">
                  <span className="num">{stream.meta ? matchClock(m.at, stream.meta.period_end_ms) : ''}</span>
                  <span className="row-kind">{m.kind.replace('/', ' · ')}</span>
                  <span className={`verdict ${outcomeClass(m.result)}`}>{m.result ?? 'in progress'}</span>
                </div>
                <div className="chips">
                  {m.stages.map((s, i) => (
                    <span key={i} className={`chip ${outcomeClass(s.running ? undefined : s.outcome)}`} title={s.detail}>
                      {s.stage}
                      <i className="num">{s.running ? '…' : s.ms != null ? `${(s.ms / 1000).toFixed(1)}s` : ''}</i>
                    </span>
                  ))}
                </div>
                {m.stages
                  .filter((s) => s.outcome === 'rejected' && s.detail)
                  .map((s, i) => (
                    <p key={i} className="reason bad">
                      <b>{s.stage === 'verifier:code' ? 'Recomputation failed' : 'Verifier rejected the claim'}:</b> {s.detail}
                    </p>
                  ))}
                {m.result === 'dropped' && m.reason && <p className="reason bad">Dropped: {m.reason}</p>}
              </motion.article>
            ))}
          </AnimatePresence>
        </section>
        <aside className="preview">
          <h2>On air</h2>
          <ProgramFrame stream={stream} clock={clock} opts={{ persona: 'analyst_en', scale: 0.32, fit: false }} />
          <p className="note">
            Tier-0 graphics come straight from code; AI cards appear as an amber template, then the verified text. Numbers
            are recomputed by code before anything goes on air.
          </p>
        </aside>
      </div>
    </main>
  )
}
