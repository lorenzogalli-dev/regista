import { useEffect, useState } from 'react'

import { BroadcastFrame } from '../broadcast/BroadcastFrame.tsx'
import { ProgramFrame } from '../broadcast/ProgramFrame.tsx'
import { loadSample, type Sample } from '../lib/sample.ts'
import { useAudit, useGraphicsBody, useSource } from '../lib/hooks.ts'
import { useMatchStream } from '../lib/stream.ts'
import { PlayerView } from '../player/PlayerView.tsx'

// Broadcast view (DESIGN.md §5.1).
// /broadcast                               player on the first recorded agent run (zero model calls)
// /broadcast?run=<run_id>&persona=casual_it&from=<ms>&fav=<player_id>
// /broadcast?run=<run_id>&clean=1&speed=1  the bare 16:9 programme, no player chrome (captures)
// /broadcast?live=m_1000&speed=1           live session (agents run, daily cap)
// /broadcast?sample=hero_m_1000&t=4268900  D5a design clip, frozen at t
// &audit=1                                 writes a design audit into <pre id="audit"> after 4 s

function SampleBroadcast({ name, graphicsOnly }: { name: string; graphicsOnly: boolean }) {
  const params = new URLSearchParams(window.location.search)
  const t = params.get('t')
  const [sample, setSample] = useState<Sample | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    loadSample(`/samples/${name}.json`)
      .then(setSample)
      .catch((e: Error) => setError(e.message))
  }, [name])
  useAudit(!!sample, params.get('audit') === '1')
  if (error) return <p style={{ padding: 40 }}>Could not load sample: {error}</p>
  if (!sample) return null
  return (
    <BroadcastFrame
      sample={sample}
      freezeAt={t ? Number(t) : null}
      graphicsOnly={graphicsOnly}
      debugAnchors={params.get('debug') === 'anchors'}
    />
  )
}

function ProgramBroadcast({ graphicsOnly }: { graphicsOnly: boolean }) {
  const params = new URLSearchParams(window.location.search)
  const source = useSource(params)
  const speed = Number(params.get('speed') ?? 1)
  const from = Number(params.get('from') ?? 0)
  const { stream, clock } = useMatchStream(source, speed, from)
  useAudit(!!stream?.meta, params.get('audit') === '1')
  if (stream?.error) return <p style={{ padding: 40 }}>{stream.error}</p>
  if (!stream || !clock) return null
  return (
    <ProgramFrame
      stream={stream}
      clock={clock}
      opts={{
        persona: params.get('persona') ?? 'analyst_en',
        favoritePlayer: params.get('fav'),
        graphicsOnly,
      }}
    />
  )
}

function PlayerBroadcast() {
  const params = new URLSearchParams(window.location.search)
  const source = useSource(params)
  useAudit(!!source, params.get('audit') === '1')
  return (
    <PlayerView
      runId={source?.kind === 'recorded' ? source.runId : null}
      from={Number(params.get('from') ?? 0)}
      initialPersona={params.get('persona') ?? 'analyst_en'}
      fav={params.get('fav')}
    />
  )
}

export function Broadcast({ graphicsOnly = false }: { graphicsOnly?: boolean }) {
  const params = new URLSearchParams(window.location.search)
  useGraphicsBody(graphicsOnly)
  const sample = params.get('sample')
  if (sample) return <SampleBroadcast name={sample.replace(/[^a-z0-9_]/gi, '')} graphicsOnly={graphicsOnly} />
  if (graphicsOnly || params.get('live') || params.get('clean') === '1') return <ProgramBroadcast graphicsOnly={graphicsOnly} />
  return <PlayerBroadcast />
}
