// Hooks shared by the broadcast routes.

import { useEffect, useState } from 'react'

import { runAudit } from '../broadcast/audit.ts'
import type { Source } from './stream.ts'

export type RunListItem = { run_id: string; match_id: string; published: number; moments: number }

/** The source from the URL, or the first recorded run when none is given. */
export function useSource(params: URLSearchParams): Source | null {
  const run = params.get('run')
  const liveMatch = params.get('live')
  const [first, setFirst] = useState<string | null>(null)
  useEffect(() => {
    if (run || liveMatch) return
    fetch('/api/runs')
      .then((r) => r.json() as Promise<RunListItem[]>)
      .then((rs) => setFirst(rs[0]?.run_id ?? null))
      .catch(() => setFirst(null))
  }, [run, liveMatch])
  if (liveMatch) return { kind: 'live', matchId: liveMatch }
  const id = run ?? first
  return id ? { kind: 'recorded', runId: id } : null
}

/** `?audit=1` writes the design audit into <pre id="audit">, after `auditAt` ms (default 4 s). */
export function useAudit(ready: boolean, enabled: boolean) {
  useEffect(() => {
    if (!ready || !enabled) return
    const delay = Number(new URLSearchParams(window.location.search).get('auditAt') ?? 4000)
    const id = window.setTimeout(() => {
      const pre = document.createElement('pre')
      pre.id = 'audit'
      pre.textContent = JSON.stringify(runAudit())
      pre.style.display = 'none'
      document.body.append(pre)
    }, delay)
    return () => window.clearTimeout(id)
  }, [ready, enabled])
}

export function useGraphicsBody(on: boolean) {
  useEffect(() => {
    if (!on) return
    document.body.classList.add('graphics')
    // ?bg=00b140 shows the layer over a flat key colour, as a vision mixer would see it.
    const bg = new URLSearchParams(window.location.search).get('bg')
    if (bg && /^[0-9a-f]{6}$/i.test(bg)) document.body.style.background = `#${bg}`
    return () => {
      document.body.classList.remove('graphics')
      document.body.style.background = ''
    }
  }, [on])
}

