import { useEffect, useState } from 'react'

import { VerifiedSeal } from '../broadcast/MomentCard.tsx'
import type { RunListItem } from '../lib/hooks.ts'
import { matchClock } from '../lib/sample.ts'
import './pages.css'
import './second.css'
import { SiteNav } from './SiteNav.tsx'

// Recap (DESIGN.md §5.6), simple: the three highest-salience verified moments of a recorded run.
// /recap?run=<id>&persona=analyst_en

type Moment = {
  moment_id: string
  status: string
  candidate: { t_ms: number }
  detector: { salience: number } | null
  explanation: { claim: string; evidence: unknown[] } | null
  personas: { persona_id: string; headline: string; text: string }[] | null
}

export function Recap() {
  const params = new URLSearchParams(window.location.search)
  const persona = params.get('persona') ?? 'analyst_en'
  const [data, setData] = useState<{ moments: Moment[]; ends: number[]; title: string } | null>(null)
  useEffect(() => {
    const id = params.get('run')
    const load = (rid: string) =>
      fetch(`/api/runs/${rid}`)
        .then((r) => r.json() as Promise<{ match_id: string; moments: Moment[] }>)
        .then(async (r) => {
          const m = (await (await fetch(`/api/matches/${r.match_id}`)).json()) as {
            home: { name: string }
            away: { name: string }
            period_end_ms: number[]
          }
          setData({ moments: r.moments, ends: m.period_end_ms, title: `${m.home.name} v ${m.away.name}` })
        })
    if (id) load(id).catch(() => undefined)
    else
      fetch('/api/runs')
        .then((r) => r.json() as Promise<RunListItem[]>)
        .then((rs) => rs[0] && load(rs[0].run_id))
        .catch(() => undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  if (!data) return null
  const top = data.moments
    .filter((m) => m.status === 'published' && m.explanation)
    .sort((a, b) => (b.detector?.salience ?? 0) - (a.detector?.salience ?? 0))
    .slice(0, 3)
    .sort((a, b) => a.candidate.t_ms - b.candidate.t_ms)
  return (
    <div className="site">
      <SiteNav />
      <header className="page-head">
        <p className="eyebrow">Full-time recap · Recorded agent run</p>
        <h1>{data.title}</h1>
        <p className="lede">The three moments that mattered most, as verified on air.</p>
      </header>
      <main className="page">
        <section className="feed2">
          {top.map((m) => {
            const line = m.personas?.find((p) => p.persona_id === persona)
            return (
              <article className="card2 tactic" key={m.moment_id}>
                <div className="card2-top">
                  <span className="num">{matchClock(m.candidate.t_ms, data.ends)}</span>
                  <VerifiedSeal passed={m.explanation!.evidence.length} total={m.explanation!.evidence.length} />
                </div>
                <h2>{line?.headline ?? ''}</h2>
                <p>{line?.text ?? m.explanation!.claim}</p>
              </article>
            )
          })}
        </section>
      </main>
    </div>
  )
}
