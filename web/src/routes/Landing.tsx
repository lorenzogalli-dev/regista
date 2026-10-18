import { motion } from 'motion/react'
import { useEffect, useState } from 'react'

import { wipe } from '../broadcast/wipe.ts'
import './pages.css'

// Landing (DESIGN.md §5.7): one screen.

type Quota = { remaining: number; cap: number }
type Run = { run_id: string; match_id: string; published: number; rejections: number }

export function Landing() {
  const [quota, setQuota] = useState<Quota | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  useEffect(() => {
    fetch('/api/live/quota')
      .then((r) => r.json() as Promise<Quota>)
      .then(setQuota)
      .catch(() => setQuota(null))
    fetch('/api/runs')
      .then((r) => r.json() as Promise<Run[]>)
      .then(setRuns)
      .catch(() => setRuns([]))
  }, [])
  const first = runs[0]
  // The control room is most telling on a run where the Verifier sent a claim back.
  const ctrl = runs.find((r) => r.rejections > 0) ?? first
  const liveOff = quota != null && quota.remaining <= 0
  return (
    <main className="landing">
      <motion.div className="landing-inner" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <p className="eyebrow">Ground Truth Football</p>
        <h1>
          Verified
          <br />
          on air
        </h1>
        <p className="lede">
          A team of AI agents watches a match and explains what changed and why. Every number they cite comes from the
          metrics code and is recomputed before it goes on air.
        </p>
        <div className="actions">
          <motion.a className="cta primary" href={first ? `/broadcast?run=${first.run_id}` : '/broadcast'} {...wipe()}>
            <span className="unskew">Watch a recorded match</span>
          </motion.a>
          <motion.a
            className={`cta ${liveOff ? 'disabled' : ''}`}
            href={liveOff ? undefined : `/broadcast?live=${first?.match_id ?? 'm_1000'}`}
            aria-disabled={liveOff}
            {...wipe(0.08)}
          >
            <span className="unskew">
              Go live{' '}
              <small className="num">{quota ? (liveOff ? 'paused for today' : `${quota.remaining} model calls left today`) : ''}</small>
            </span>
          </motion.a>
        </div>
        <nav className="links">
          <a href={first ? `/split?run=${first.run_id}&from=2045000` : '/split'}>Split view: two viewers, one moment</a>
          <a href={ctrl ? `/control?run=${ctrl.run_id}` : '/control'}>Control room: the agents at work</a>
          <a href="/eval">Evaluation report</a>
          <a href={first ? `/graphics?run=${first.run_id}` : '/graphics'}>Graphics-only output (OBS)</a>
          <a href="/second">Second screen</a>
        </nav>
        <p className="fine">
          Recorded agent runs are real outputs of the pipeline, replayed with zero model calls. All clubs, players and data
          are synthetic.
        </p>
      </motion.div>
    </main>
  )
}
