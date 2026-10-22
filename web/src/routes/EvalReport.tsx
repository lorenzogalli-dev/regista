import { motion } from 'motion/react'
import { useEffect, useState } from 'react'

import { CountUp } from '../broadcast/CountUp.tsx'
import './pages.css'
import { SiteNav } from './SiteNav.tsx'

// Evaluation report (DESIGN.md §5.5), from the official run in docs/eval/report.json.

type Report = {
  set: string
  seeds: number[]
  models: Record<string, string>
  storyline_matches: number
  control_matches: number
  storylines: number
  recall: number
  recall_strict: number
  recall_by_type: Record<string, { hit: number; of: number; difficult: boolean }>
  approved: number
  categories: { storyline_hit: number; unplanted_evidence_backed: number; unsupported: number }
  precision: number
  precision_at_3: number
  control_approved_per_match: number
  control_approved_by_tag: Record<string, number>
  evidence: { ok: number; bad: number; unchecked: number }
  evidence_validity: number
  verifier_rejection_rate: number
  latency_ms: Record<string, { p50: number; p95: number }>
  cost_eur: number
  calls: number
}

const NICE: Record<string, string> = {
  momentum_shift: 'Momentum shift',
  player_arc: 'Player arc',
  pressing_spell: 'Pressing spell',
  tactical_switch: 'Tactical switch',
}

function Big({ value, tag, label, pct = true, note }: { value: number; tag: string; label: string; pct?: boolean; note?: string }) {
  return (
    <div className="big board">
      <span className="board-strip">{tag}</span>
      <span className="big-value num">
        <CountUp value={pct ? value * 100 : value} decimals={0} duration={1} />
        {pct && <small>%</small>}
      </span>
      <span className="big-label">{label}</span>
      {note && <span className="big-note">{note}</span>}
    </div>
  )
}

export function EvalReport() {
  const [r, setR] = useState<Report | null>(null)
  const [err, setErr] = useState(false)
  useEffect(() => {
    fetch('/api/eval/report')
      .then((x) => (x.ok ? (x.json() as Promise<Report>) : Promise.reject()))
      .then(setR)
      .catch(() => setErr(true))
  }, [])
  if (err)
    return (
      <div className="site">
        <SiteNav />
        <main className="page">No evaluation report yet.</main>
      </div>
    )
  if (!r) return null
  const c = r.categories
  const total = r.approved || 1
  const stages = Object.entries(r.latency_ms).filter(([k]) => k !== 'candidate_to_approval')
  const maxP95 = Math.max(...stages.map(([, v]) => v.p95), 1)
  return (
    <div className="site">
      <SiteNav />
      <header className="page-head">
        <p className="eyebrow">Evaluation · run once on unseen seeds</p>
        <h1>Does it find what happened, and only say what is true?</h1>
        <p className="lede">
          {r.storyline_matches} matches with {r.storylines} hidden storylines and {r.control_matches} control matches with
          none. Agents never see the storylines; the report scores their approved explanations against them.
        </p>
      </header>
      <main className="page eval">

        <section className="bigs">
          <Big value={r.evidence_validity} tag="Evidence" label="Evidence confirmed by independent recomputation" note={`${r.evidence.ok} items; ${r.evidence.unchecked} not independently checkable`} />
          <Big value={c.unsupported} tag="Unsupported" pct={false} label={`Unsupported explanations of ${r.approved} approved`} />
          <Big value={r.recall} tag="Recall" label="Hidden storylines found" note={`${Math.round(r.recall * r.storylines)} of ${r.storylines}`} />
          <Big value={r.precision_at_3} tag="Precision@3" label="Precision@3: the moments the Director airs" note={`classic precision ${Math.round(r.precision * 100)}%`} />
        </section>

        <section>
          <h2>What the approved explanations are</h2>
          <div className="stack" role="img" aria-label="approved explanations by category">
            {[
              ['hit', c.storyline_hit, 'Planted storyline found'],
              ['unplanted', c.unplanted_evidence_backed, 'Unplanted pattern, evidence-backed'],
              ['unsupported', c.unsupported, 'Unsupported'],
            ].map(([k, v, label]) => (
              <motion.div
                key={k as string}
                className={`stack-part ${k}`}
                initial={{ width: 0 }}
                animate={{ width: `${((v as number) / total) * 100}%` }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              >
                {(v as number) > 0 && (
                  <span>
                    <b className="num">{v as number}</b> {label as string}
                  </span>
                )}
              </motion.div>
            ))}
          </div>
          <p className="explain">
            An explanation that matches no planted storyline is not a hallucination: every number it cites that a second,
            independent recomputation can check was confirmed (numbers on xT and the control index are checked only by the
            Verifier's own recomputation). These are real swings in the simulated match that nobody scripted. Classic
            precision counts them as misses only because the evaluation can score against planted storylines alone.
          </p>
        </section>

        <section className="two">
          <div>
            <h2>Recall by storyline type</h2>
            {Object.entries(r.recall_by_type).map(([k, v]) => (
              <div className="bar-row" key={k}>
                <span className="bar-label">
                  {NICE[k] ?? k} {v.difficult && <em>difficult</em>}
                </span>
                <span className="bar">
                  <motion.i initial={{ width: 0 }} animate={{ width: `${(v.hit / v.of) * 100}%` }} transition={{ duration: 0.8 }} />
                </span>
                <span className="bar-num num">
                  {v.hit}/{v.of}
                </span>
              </div>
            ))}
          </div>
          <div>
            <h2>Control matches (no storylines)</h2>
            <p className="explain">
              {r.control_approved_per_match} approved explanations per match, all with confirmed evidence: real fluctuations,
              reported for transparency.
            </p>
            {Object.entries(r.control_approved_by_tag).map(([k, v]) => (
              <div className="bar-row" key={k}>
                <span className="bar-label">{NICE[k] ?? k}</span>
                <span className="bar muted">
                  <motion.i initial={{ width: 0 }} animate={{ width: `${(v / r.control_matches) * 50}%` }} transition={{ duration: 0.8 }} />
                </span>
                <span className="bar-num num">{v}</span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2>Latency per stage</h2>
          {stages.map(([k, v]) => (
            <div className="bar-row" key={k}>
              <span className="bar-label">{k}</span>
              <span className="bar lat">
                <i style={{ width: `${(v.p50 / maxP95) * 100}%` }} />
                <i className="p95" style={{ width: `${((v.p95 - v.p50) / maxP95) * 100}%` }} />
              </span>
              <span className="bar-num num">
                {(v.p50 / 1000).toFixed(1)} / {(v.p95 / 1000).toFixed(1)} s
              </span>
            </div>
          ))}
          <p className="explain">
            p50 / p95. From candidate to verified card: {(r.latency_ms.candidate_to_approval.p50 / 1000).toFixed(1)} s median.
            Data graphics never wait for agents.
          </p>
        </section>

        <footer className="foot">
          Models: {r.models.fast} (Detector, Verifier) and {r.models.reasoning} (Analyst, {r.models.reasoning_effort} reasoning)
          on Microsoft Foundry · {r.calls} model calls · {r.cost_eur.toFixed(2)} EUR · Verifier sent{' '}
          {Math.round(r.verifier_rejection_rate * 100)}% of explanations back once. All data is synthetic.
        </footer>
      </main>
    </div>
  )
}
