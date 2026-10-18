import { motion } from 'motion/react'
import { useEffect, useState } from 'react'

import { VerifiedSeal } from '../broadcast/MomentCard.tsx'
import type { RunListItem } from '../lib/hooks.ts'
import { matchClock } from '../lib/sample.ts'
import './second.css'

// Second screen (DESIGN.md §5.3), simple version: a vertical feed of verified moments for one
// viewer, a language switch and a favourite-player filter. /second?run=<id>&lang=it&fav=<id>

type Moment = {
  moment_id: string
  status: string
  candidate: { t_ms: number }
  explanation: { mechanism_tag: string; player_ids: string[]; evidence: unknown[] } | null
  personas: { persona_id: string; headline: string; text: string }[] | null
}
type Run = { run_id: string; match_id: string; moments: Moment[] }
type Meta = { home: { name: string; short: string }; away: { name: string; short: string }; players: { player_id: string; name: string; shirt: number; team_id: string }[]; period_end_ms: number[] }

const LANGS = [
  ['en', 'English'],
  ['it', 'Italiano'],
  ['es', 'Español'],
] as const

export function Second() {
  const params = new URLSearchParams(window.location.search)
  const [lang, setLang] = useState(params.get('lang') ?? 'en')
  const [fav, setFav] = useState<string | null>(params.get('fav'))
  const [run, setRun] = useState<Run | null>(null)
  const [meta, setMeta] = useState<Meta | null>(null)

  useEffect(() => {
    const id = params.get('run')
    const load = (rid: string) =>
      fetch(`/api/runs/${rid}`)
        .then((r) => r.json() as Promise<Run>)
        .then((r) => {
          setRun(r)
          return fetch(`/api/matches/${r.match_id}`).then((m) => m.json() as Promise<Meta>)
        })
        .then(setMeta)
    if (id) load(id).catch(() => undefined)
    else
      fetch('/api/runs')
        .then((r) => r.json() as Promise<RunListItem[]>)
        .then((rs) => rs[0] && load(rs[0].run_id))
        .catch(() => undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!run || !meta) return null
  const named = new Set(run.moments.flatMap((m) => m.explanation?.player_ids ?? []))
  const players = meta.players.filter((p) => named.has(p.player_id))
  const feed = run.moments
    .filter((m) => m.status === 'published' && m.personas)
    .filter((m) => !fav || m.explanation?.player_ids.includes(fav))
    .sort((a, b) => b.candidate.t_ms - a.candidate.t_ms)
  const mode = fav ? 'player_focus' : 'casual'

  return (
    <main className="second">
      <header className="second-head">
        <p className="eyebrow">Second screen · Recorded agent run</p>
        <h1>
          {meta.home.short} v {meta.away.short}
        </h1>
        <div className="seg" role="tablist" aria-label="language">
          {LANGS.map(([k, label]) => (
            <button key={k} role="tab" aria-selected={lang === k} className={lang === k ? 'on' : ''} onClick={() => setLang(k)}>
              {label}
            </button>
          ))}
        </div>
        {players.length > 0 && (
          <div className="favs" aria-label="favourite player">
            <button className={!fav ? 'on' : ''} onClick={() => setFav(null)}>
              All moments
            </button>
            {players.map((p) => (
              <button key={p.player_id} className={fav === p.player_id ? 'on' : ''} onClick={() => setFav(p.player_id)}>
                ★ {p.name} <span className="num">#{p.shirt}</span>
              </button>
            ))}
          </div>
        )}
      </header>
      <section className="feed2">
        {feed.map((m, i) => {
          const line = m.personas!.find((p) => p.persona_id === `${mode}_${lang}`) ?? m.personas![0]
          return (
            <motion.article
              key={m.moment_id + lang + mode}
              className="card2"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.35 }}
            >
              <div className="card2-top">
                <span className="num">{matchClock(m.candidate.t_ms, meta.period_end_ms)}</span>
                <VerifiedSeal passed={m.explanation!.evidence.length} total={m.explanation!.evidence.length} />
              </div>
              <h2>{line.headline}</h2>
              <p>{line.text}</p>
            </motion.article>
          )
        })}
        {feed.length === 0 && <p className="empty">No verified moments for this player yet.</p>}
      </section>
    </main>
  )
}
