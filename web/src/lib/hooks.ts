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

export function useAudit(ready: boolean, enabled: boolean) {
  useEffect(() => {
    if (!ready || !enabled) return
    const id = window.setTimeout(() => {
      const pre = document.createElement('pre')
      pre.id = 'audit'
      pre.textContent = JSON.stringify(runAudit())
      pre.style.display = 'none'
      document.body.append(pre)
    }, 4000)
    return () => window.clearTimeout(id)
  }, [ready, enabled])
}

export function useGraphicsBody(on: boolean) {
  useEffect(() => {
    if (!on) return
    document.body.classList.add('graphics')
    return () => document.body.classList.remove('graphics')
  }, [on])
}

