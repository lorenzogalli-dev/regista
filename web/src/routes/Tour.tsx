import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { Wordmark } from '../brand/Wordmark.tsx'
import { ProgramFrame } from '../broadcast/ProgramFrame.tsx'
import { useAudit } from '../lib/hooks.ts'
import { usePlayer } from '../lib/player.ts'
import { STAGE } from '../lib/projection.ts'
import { ControlView } from './Control.tsx'
import { SplitView } from './Split.tsx'
import './tour.css'

// Guided tour (~2 min): the best moments of the recorded runs in sequence, each with a short
// caption saying what is on screen and who made it (code or an AI agent). Every scene is a
// real recorded agent run replayed with zero model calls.
// /tour?step=<n> starts at a step (captures).

const DEMO = 'r_m_1000_1ad2f33e'
const REJECTION = 'r_m_5016_d5b7b361'
const READY_WAIT_MS = 8000

type Tier = 'code' | 'ai' | 'both' | null
type Cue = { at: number; tier: Tier; title: string; sub: string }

type Step =
  | { kind: 'slide'; id: string; label: string; seconds: number; render: () => React.ReactNode }
  | {
      kind: 'broadcast'
      id: string
      label: string
      seconds: number
      run: string
      from: number
      persona?: string
      /** Cues by match time; `replay` overrides them while a moment replay holds the frame. */
      cues: Cue[]
      replay?: { title: string; sub: string; evidenceTitle?: string; evidenceSub?: string }
    }
  | { kind: 'split'; id: string; label: string; seconds: number; run: string; from: number; cues: Cue[] }
  | { kind: 'control'; id: string; label: string; seconds: number; run: string; from: number; speed: number; cues: Cue[] }

const STEPS: Step[] = [
  {
    kind: 'slide',
    id: 'intro',
    label: 'Intro',
    seconds: 6,
    render: () => (
      <div className="tour-slide">
        <Wordmark size={40} />
        <h1>Reads the game. Directs the broadcast.</h1>
        <p>
          A two-minute tour of AI match graphics and tactical explanations, generated live and checked before they go on
          air.
        </p>
        <p className="tour-fine">Everything you will see is a real recorded run of the system on a synthetic match.</p>
      </div>
    ),
  },
  {
    kind: 'broadcast',
    id: 'stats',
    label: 'Live stats',
    seconds: 8.5,
    run: DEMO,
    from: 2_031_000,
    cues: [
      {
        at: 0,
        tier: 'code',
        title: 'Computed by code, instantly',
        sub: 'A pass card: length, how far it moved the ball forward, and how hard it was to complete, measured from tracking data.',
      },
    ],
  },
  {
    kind: 'broadcast',
    id: 'speed',
    label: 'Top speed',
    seconds: 6.5,
    run: DEMO,
    from: 2_131_500,
    cues: [
      {
        at: 0,
        tier: 'code',
        title: 'Computed by code, instantly',
        sub: 'Top speed, picked up the moment a player crosses the threshold, and following the player.',
      },
    ],
  },
  {
    kind: 'broadcast',
    id: 'shot',
    label: 'Shot speed',
    seconds: 7,
    run: DEMO,
    from: 4_898_500,
    cues: [
      {
        at: 0,
        tier: 'code',
        title: 'Computed by code, instantly',
        sub: 'Shot speed and expected goals (xG): the chance of a goal from that position, from a model fitted on the data.',
      },
    ],
  },
  {
    kind: 'broadcast',
    id: 'insight',
    label: 'AI insight',
    seconds: 39,
    run: DEMO,
    from: 2_037_500,
    cues: [
      {
        at: 0,
        tier: 'code',
        title: 'Code notices that something has changed',
        sub: 'Possession and territory have shifted over the last 15 minutes. Nothing is on air yet.',
      },
      {
        at: 2_041_300,
        tier: 'code',
        title: 'A template goes on air at once',
        sub: 'In amber, with numbers computed by code, while six AI agents work out what changed and why.',
      },
      {
        at: 2_055_200,
        tier: 'ai',
        title: 'Written by an AI agent, verified against the data',
        sub: 'The Verifier recomputed every number before this card replaced the template. The seal shows how many checks passed.',
      },
    ],
    replay: {
      title: 'Moment replay: the pitch shows the why',
      sub: 'The frame holds so the card can be read. The shading comes from the match data: this is where the team is now playing.',
      evidenceTitle: 'Every number, checked',
      evidenceSub: 'Tap the seal: each figure the agent cited, before and after, recomputed independently by code.',
    },
  },
  {
    kind: 'split',
    id: 'split',
    label: 'Every fan',
    seconds: 17,
    run: DEMO,
    from: 2_051_000,
    cues: [
      {
        at: 0,
        tier: 'ai',
        title: 'The same moment, told for two viewers',
        sub: 'An analyst in English; a casual fan in Italian, following a favourite player. Same numbers, same seal: only the telling changes.',
      },
    ],
  },
  {
    kind: 'control',
    id: 'control',
    label: 'Control room',
    seconds: 24,
    run: REJECTION,
    from: 5_148_000,
    speed: 2,
    cues: [
      {
        at: 0,
        tier: 'both',
        title: 'The control room: watch the agents work and check each other',
        sub: 'Each candidate moment flows from code to the Detector, the Analyst and the Verifier, then to the agents that write for viewers.',
      },
      {
        at: 5_170_000,
        tier: 'ai',
        title: 'The Verifier says no',
        sub: 'The Analyst credited two players who had already been substituted off. The claim was rejected with its reason; only the corrected version went on air.',
      },
    ],
  },
  {
    kind: 'slide',
    id: 'end',
    label: 'Results',
    seconds: 14,
    render: () => (
      <div className="tour-slide tour-end">
        <h2>Measured, not just demoed</h2>
        <div className="tour-nums">
          <div>
            <b className="num">52%</b>
            <span>of hidden storylines found, on 20 matches the system had never seen</span>
          </div>
          <div>
            <b className="num">0 / 81</b>
            <span>approved explanations with a number the data does not support</span>
          </div>
          <div>
            <b className="num">≈ €1.76</b>
            <span>total AI cost, development and evaluation included</span>
          </div>
        </div>
        <div className="tour-actions">
          <a className="cta primary" href={`/broadcast?run=${DEMO}`}>
            <span className="unskew">Watch a full match</span>
          </a>
          <a className="cta" href="/eval">
            <span className="unskew">Read the evaluation</span>
          </a>
          <a className="cta" href="/">
            <span className="unskew">Back to the start</span>
          </a>
        </div>
      </div>
    ),
  },
]

function useBox(ref: React.RefObject<HTMLElement | null>) {
  const [box, setBox] = useState({ width: 1280, height: 600 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect()
      setBox({ width: r.width, height: r.height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [ref])
  return box
}

function Caption({ cue }: { cue: Cue | null }) {
  return (
    <div className="tour-caption" aria-live="polite">
      <AnimatePresence mode="wait">
        {cue && (
          <motion.div
            key={cue.title}
            className="tour-caption-inner"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35 }}
          >
            {cue.tier && (
              <span className={`tour-tier ${cue.tier}`}>
                {cue.tier === 'code' ? 'Code' : cue.tier === 'ai' ? 'AI agent · verified' : 'Code + AI agents'}
              </span>
            )}
            <div>
              <h2>{cue.title}</h2>
              <p>{cue.sub}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function current(cues: Cue[], t: number): Cue | null {
  let c: Cue | null = null
  for (const x of cues) if (x.at === 0 || x.at <= t) c = x
  return c
}

function BroadcastScene({
  step,
  box,
  onCue,
  onReady,
}: {
  step: Extract<Step, { kind: 'broadcast' }>
  box: { width: number; height: number }
  onCue: (c: Cue | null) => void
  onReady: () => void
}) {
  const p = usePlayer({
    runId: step.run,
    from: step.from,
    persona: step.persona ?? 'analyst_en',
    autoSkip: false,
    keys: false,
    holdScale: 1.5,
  })
  const scale = Math.min(box.width / STAGE.width, box.height / STAGE.height)
  // A replay hold is told in three beats: the verified card, the telestration, the evidence.
  const beat = p.replay ? 1 - p.replay.remaining / p.replay.total : 0
  const evidence = !!p.replay && beat >= 0.62
  const cue: Cue | null =
    p.replay && step.replay && beat >= 0.3
      ? evidence && step.replay.evidenceTitle
        ? { at: 0, tier: 'both', title: step.replay.evidenceTitle, sub: step.replay.evidenceSub ?? '' }
        : { at: 0, tier: 'both', title: step.replay.title, sub: step.replay.sub }
      : current(step.cues, p.replay ? Infinity : p.t)
  useEffect(() => onCue(cue), [cue?.title]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (p.stream) onReady()
  }, [p.stream]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!p.stream || !p.clock) return null
  return (
    <div style={{ width: STAGE.width * scale, height: STAGE.height * scale }} className="tour-frame">
      <ProgramFrame
        stream={p.stream}
        clock={p.clock}
        opts={{ persona: step.persona ?? 'analyst_en', scale, fit: false, replay: p.replay, openEvidence: evidence }}
      />
    </div>
  )
}

function TimedCues({ cues, onCue, t }: { cues: Cue[]; onCue: (c: Cue | null) => void; t: number }) {
  const cue = current(cues, t)
  useEffect(() => onCue(cue), [cue?.title]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

export function Tour() {
  const params = new URLSearchParams(window.location.search)
  const [i, setI] = useState(Math.min(STEPS.length - 1, Math.max(0, Number(params.get('step') ?? 0))))
  const [paused, setPaused] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [cue, setCue] = useState<Cue | null>(null)
  const [ready, setReady] = useState(false)
  const sceneRef = useRef<HTMLDivElement>(null)
  const elapsedRef = useRef(0)
  const box = useBox(sceneRef)
  const step = STEPS[i]
  useAudit(true, params.get('audit') === '1')

  const go = useCallback((n: number) => {
    setI(Math.min(STEPS.length - 1, Math.max(0, n)))
    elapsedRef.current = 0
    setElapsed(0)
    setCue(null)
    setReady(false)
    setPaused(false)
  }, [setI, setElapsed, setCue, setReady, setPaused])
  const onReady = useCallback(() => setReady(true), [setReady])

  // A scene's step starts with its first frame, so a slow seek never eats the step; after
  // READY_WAIT_MS it starts anyway.
  const waiting = step.kind !== 'slide' && !ready
  useEffect(() => {
    if (!waiting) return
    const id = window.setTimeout(onReady, READY_WAIT_MS)
    return () => window.clearTimeout(id)
  }, [waiting, i, onReady])

  // Step clock (wall time). The last step waits for the viewer.
  useEffect(() => {
    if (paused || waiting) return
    let last = performance.now()
    const id = window.setInterval(() => {
      const now = performance.now()
      elapsedRef.current += (now - last) / 1000
      last = now
      if (elapsedRef.current >= step.seconds && i < STEPS.length - 1) go(i + 1)
      else setElapsed(elapsedRef.current)
    }, 100)
    return () => window.clearInterval(id)
  }, [paused, waiting, i, step.seconds, go])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') go(i + 1)
      else if (e.key === 'ArrowLeft') go(i - 1)
      else if (e.key === 'Escape') window.location.href = '/'
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [i, go])

  // Non-broadcast scenes: cues by match time are approximated by wall time since the step began.
  const approxT = step.kind === 'control' ? step.from + elapsed * 1000 * step.speed : step.kind === 'split' ? step.from + elapsed * 1000 : 0

  return (
    <MotionConfig reducedMotion="user">
    <main className="tour">
      <header className="tour-top">
        <a href="/" aria-label="Regista home">
          <Wordmark size={20} />
        </a>
        <span className="tour-title">Guided tour</span>
        <ol className="tour-steps">
          {STEPS.map((s, k) => (
            <li key={s.id}>
              <button type="button" className={k === i ? 'on' : k < i ? 'done' : ''} onClick={() => go(k)}>
                <span className="tour-step-bar">
                  <i style={{ transform: `scaleX(${k < i ? 1 : k === i ? Math.min(1, elapsed / s.seconds) : 0})` }} />
                </span>
                <span className="tour-step-label">{s.label}</span>
              </button>
            </li>
          ))}
        </ol>
        <div className="tour-ctl">
          <button type="button" onClick={() => go(i - 1)} aria-label="Previous step" disabled={i === 0}>
            ‹
          </button>
          <button type="button" onClick={() => setPaused((p) => !p)} aria-label={paused ? 'Resume tour' : 'Pause tour'}>
            {paused ? '▶' : '❚❚'}
          </button>
          <button type="button" onClick={() => go(i + 1)} aria-label="Next step" disabled={i === STEPS.length - 1}>
            ›
          </button>
          <a href="/" className="tour-exit">
            Exit
          </a>
        </div>
      </header>
      <div className={`tour-scene ${step.kind === 'slide' ? 'slide' : ''}`} ref={sceneRef}>
        <AnimatePresence mode="wait">
          <motion.div
            key={step.id}
            className="tour-scene-inner"
            initial={{ opacity: 0, scale: 0.985 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.01 }}
            transition={{ duration: 0.45 }}
          >
            {step.kind === 'slide' && step.render()}
            {step.kind === 'broadcast' && <BroadcastScene step={step} box={box} onCue={setCue} onReady={onReady} />}
            {step.kind === 'split' && (
              <>
                <SplitView
                  source={{ kind: 'recorded', runId: step.run }}
                  speed={1}
                  from={step.from}
                  left="analyst_en"
                  right="casual_it"
                  initialFav={null}
                  box={box}
                  onReady={onReady}
                />
                <TimedCues cues={step.cues} onCue={setCue} t={approxT} />
              </>
            )}
            {step.kind === 'control' && (
              <div className="tour-control" style={{ ['--k' as string]: Math.min(box.width / 1600, box.height / 1000) }}>
                <ControlView source={{ kind: 'recorded', runId: step.run }} speed={step.speed} from={step.from} onReady={onReady} />
                <TimedCues cues={step.cues} onCue={setCue} t={approxT} />
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
      {step.kind !== 'slide' && <Caption cue={cue} />}
    </main>
    </MotionConfig>
  )
}
