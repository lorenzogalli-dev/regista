import { useEffect, useState } from 'react'

import { runAudit } from '../broadcast/audit.ts'
import { BroadcastFrame } from '../broadcast/BroadcastFrame.tsx'
import { loadSample, type Sample } from '../lib/sample.ts'

// Broadcast view (DESIGN.md §5.1). D5a renders a recorded clip exported from a generated match:
// /broadcast?sample=hero_m_1000           plays the clip in a loop
// /broadcast?sample=hero_m_1000&t=4268900 freezes at match time t (ms)
// &debug=anchors                          marks the penalty spots with DOM overlays
// &audit=1                                writes a design audit into <pre id="audit"> after 3 s
export function Broadcast({ graphicsOnly = false }: { graphicsOnly?: boolean }) {
  const params = new URLSearchParams(window.location.search)
  const name = (params.get('sample') ?? 'hero_m_1000').replace(/[^a-z0-9_]/gi, '')
  const t = params.get('t')
  const [sample, setSample] = useState<Sample | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadSample(`/samples/${name}.json`)
      .then(setSample)
      .catch((e: Error) => setError(e.message))
  }, [name])

  useEffect(() => {
    if (!graphicsOnly) return
    document.body.classList.add('graphics')
    return () => document.body.classList.remove('graphics')
  }, [graphicsOnly])

  const audit = params.get('audit') === '1'
  useEffect(() => {
    if (!sample || !audit) return
    const id = window.setTimeout(() => {
      const pre = document.createElement('pre')
      pre.id = 'audit'
      pre.textContent = JSON.stringify(runAudit())
      pre.style.display = 'none'
      document.body.append(pre)
    }, 3000)
    return () => window.clearTimeout(id)
  }, [sample, audit])

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
