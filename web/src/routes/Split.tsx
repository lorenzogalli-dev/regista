import { useEffect, useState } from 'react'

import { ProgramFrame } from '../broadcast/ProgramFrame.tsx'
import { useSource } from '../lib/hooks.ts'
import { useMatchStream, type Source } from '../lib/stream.ts'
import './split.css'

// Split view (DESIGN.md §5.2): the same moment for two viewers, side by side, from one stream.
// /split?run=<run_id>&left=analyst_en&right=casual_it&fav=<player_id>&from=<ms>

const MODE: Record<string, string> = { analyst: 'Analyst', casual: 'Casual', player_focus: 'Player focus' }

function label(persona: string): string {
  const [lang] = persona.split('_').slice(-1)
  const mode = persona.slice(0, -(lang.length + 1))
  return `${MODE[mode] ?? mode} · ${lang.toUpperCase()}`
}

type RunMoment = { explanation: { player_ids: string[] } | null; status: string }

export function Split() {
  const params = new URLSearchParams(window.location.search)
  const source = useSource(params)
  return (
    <SplitView
      source={source}
      speed={Number(params.get('speed') ?? 1)}
      from={Number(params.get('from') ?? 0)}
      left={params.get('left') ?? 'analyst_en'}
      right={params.get('right') ?? 'casual_it'}
      initialFav={params.get('fav')}
    />
  )
}

export function SplitView({
  source,
  speed,
  from,
  left,
  right,
  initialFav,
  box,
  onReady,
}: {
  source: Source | null
  speed: number
  from: number
  left: string
  right: string
  initialFav: string | null
  /** Fit into this box (px) instead of the window. */
  box?: { width: number; height: number }
  /** Called once the stream has its first frame (or failed). */
  onReady?: () => void
}) {
  const { stream, clock } = useMatchStream(source, speed, from)
  useEffect(() => {
    if (stream) onReady?.()
  }, [stream]) // eslint-disable-line react-hooks/exhaustive-deps
  const [fav, setFav] = useState<string | null>(initialFav)
  const [scale, setScale] = useState(0.5)

  useEffect(() => {
    // Default favourite: the first player a published moment names.
    if (fav || source?.kind !== 'recorded') return
    fetch(`/api/runs/${source.runId}`)
      .then((r) => r.json() as Promise<{ moments: RunMoment[] }>)
      .then((run) => {
        const m = run.moments.find((x) => x.status === 'published' && x.explanation?.player_ids.length)
        setFav(m?.explanation?.player_ids[0] ?? null)
      })
      .catch(() => undefined)
  }, [fav, source])

  const boxW = box?.width
  const boxH = box?.height
  useEffect(() => {
    const update = () =>
      setScale(Math.min(((boxW ?? window.innerWidth) - 48) / 2 / 1920, ((boxH ?? window.innerHeight) - 120) / 1080))
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [boxW, boxH])

  if (stream?.error) return <p style={{ padding: 40 }}>{stream.error}</p>
  if (!stream || !clock) return null
  const favName = stream.meta?.players.find((p) => p.player_id === fav)?.name
  return (
    <main className="split">
      <header className="split-head">
        <span className="split-brand">Regista</span>
        <span className="split-note">Same match, same moment, two viewers. Facts are identical; only the telling changes.</span>
      </header>
      <div className="split-panes">
        {[
          { persona: left, fav: null as string | null, title: label(left) },
          { persona: right, fav, title: `${label(right)}${favName ? ` · ★ ${favName}` : ''}` },
        ].map((p) => (
          <section className="split-pane" key={p.persona}>
            <h2 className="split-title">{p.title}</h2>
            <ProgramFrame stream={stream} clock={clock} opts={{ persona: p.persona, favoritePlayer: p.fav, scale, fit: false }} />
          </section>
        ))}
      </div>
    </main>
  )
}
