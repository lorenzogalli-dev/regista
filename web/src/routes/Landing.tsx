import { MotionConfig, motion, useInView, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState, type ReactNode } from 'react'

import { Mark, Wordmark } from '../brand/Wordmark.tsx'
import { CountUp } from '../broadcast/CountUp.tsx'
import { ProgramFrame } from '../broadcast/ProgramFrame.tsx'
import { usePlayer } from '../lib/player.ts'
import { STAGE } from '../lib/projection.ts'
import './landing.css'
import { SiteNav } from './SiteNav.tsx'

// Landing: what the product does in 30 seconds for anyone, the technical depth further down.
// Plain English at the top, no jargon; numbers as measured (docs/eval).

type Quota = { remaining: number; cap: number }
type Run = { run_id: string; match_id: string; featured_rejection_at_ms: number | null }

const HERO_RUN = 'r_m_1000_1ad2f33e'
const HERO_FROM = 2_031_000

function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -12% 0px' }}
      transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  )
}

/** The real broadcast, playing a recorded agent run, as the hero visual. */
function HeroPlayer() {
  const p = usePlayer({ runId: HERO_RUN, from: HERO_FROM, persona: 'analyst_en', keys: false })
  const ref = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0.4)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => setScale(el.getBoundingClientRect().width / STAGE.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return (
    <div className="hero-player" ref={ref}>
      {p.stream && p.clock ? (
        <ProgramFrame stream={p.stream} clock={p.clock} opts={{ persona: 'analyst_en', scale, fit: false, replay: p.replay }} />
      ) : (
        <div className="hero-player-wait">Loading a recorded match…</div>
      )}
      <a className="hero-player-tag" href={`/broadcast?run=${HERO_RUN}&from=${HERO_FROM}`}>
        <span className="live-dot" /> Playing a real recorded run · open the full player →
      </a>
    </div>
  )
}

function Icon({ kind }: { kind: 'stats' | 'tactics' | 'fans' }) {
  if (kind === 'stats')
    return (
      <svg viewBox="0 0 48 48" className="icon" aria-hidden>
        <path d="M8 34 A16 16 0 0 1 40 34" fill="none" stroke="currentColor" strokeWidth="3" />
        <path d="M24 34 L34 20" stroke="var(--brand)" strokeWidth="4" strokeLinecap="round" />
        <circle cx="24" cy="34" r="3.5" fill="var(--brand)" />
        {[0, 1, 2, 3, 4].map((i) => {
          const a = Math.PI * (1 - i / 4)
          return <line key={i} x1={24 + 13 * Math.cos(a)} y1={34 - 13 * Math.sin(a)} x2={24 + 16 * Math.cos(a)} y2={34 - 16 * Math.sin(a)} stroke="currentColor" strokeWidth="2" />
        })}
      </svg>
    )
  if (kind === 'tactics')
    return (
      <svg viewBox="0 0 48 48" className="icon" aria-hidden>
        <rect x="6" y="10" width="36" height="26" fill="none" stroke="currentColor" strokeWidth="2.5" />
        <line x1="24" y1="10" x2="24" y2="36" stroke="currentColor" strokeWidth="1.5" />
        <path d="M12 30 Q20 14 32 18" fill="none" stroke="var(--ai)" strokeWidth="3" strokeLinecap="round" />
        <path d="M29 14 L33 18 L28 21" fill="none" stroke="var(--ai)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M30 40 l4 4 l8 -9" fill="none" stroke="var(--ai)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  return (
    <svg viewBox="0 0 48 48" className="icon" aria-hidden>
      <circle cx="16" cy="17" r="6" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <path d="M5 38 a11 11 0 0 1 22 0" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <rect x="27" y="10" width="17" height="12" rx="2" fill="none" stroke="var(--brand)" strokeWidth="2.5" />
      <text x="35.5" y="19.5" textAnchor="middle" fontSize="8" fontWeight="800" fill="var(--brand)">
        EN
      </text>
      <rect x="27" y="26" width="17" height="12" rx="2" fill="none" stroke="var(--ai)" strokeWidth="2.5" />
      <text x="35.5" y="35.5" textAnchor="middle" fontSize="8" fontWeight="800" fill="var(--ai)">
        IT
      </text>
    </svg>
  )
}

/** Storyline planted → AI never sees it → found or not. Plays when it scrolls into view. */
function TrustSchema() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '0px 0px -20% 0px' })
  const reduced = useReducedMotion()
  const on = inView || reduced
  const d = (s: number) => (reduced ? 0 : s)
  return (
    <div className="schema" ref={ref} role="img" aria-label="A storyline is planted in a synthetic match and hidden from the AI; the AI watches the match; we count the storylines it finds on its own.">
      <div className="schema-step">
        <span className="schema-num">1</span>
        <h4>We hide a storyline</h4>
        <p>“From minute 60, the home side presses hard.” Written into the simulated match, then sealed away.</p>
      </div>
      <div className="schema-step">
        <span className="schema-num">2</span>
        <h4>The AI watches, blind</h4>
        <p>The agents only see the match data, never the storyline, and flag what they think changed.</p>
      </div>
      <div className="schema-step">
        <span className="schema-num">3</span>
        <h4>We count what it found</h4>
        <p>A flag inside the hidden window counts as found. A flag where nothing was planted counts against it.</p>
      </div>
      <div className="schema-track" aria-hidden>
        <div className="schema-lane">
          <span className="schema-lane-label">Hidden storyline</span>
          <div className="schema-bar">
            <motion.i
              className="schema-window"
              initial={{ scaleX: 0 }}
              animate={on ? { scaleX: 1 } : {}}
              transition={{ duration: 0.7, delay: d(0.2) }}
            >
              <motion.span initial={{ opacity: 0 }} animate={on ? { opacity: 1 } : {}} transition={{ delay: d(0.8) }}>
                Planted: pressing, 60′–75′
              </motion.span>
            </motion.i>
          </div>
        </div>
        <div className="schema-lane">
          <span className="schema-lane-label">What the AI flags</span>
          <div className="schema-bar">
            <motion.i
              className="schema-scan"
              initial={{ left: '0%', opacity: 0 }}
              animate={on ? { left: ['0%', '100%'], opacity: [0, 1, 1, 0] } : {}}
              transition={{ duration: 2.6, delay: d(1.1), ease: 'linear' }}
            />
            <motion.span
              className="schema-flag miss"
              style={{ left: '28%' }}
              initial={{ opacity: 0, y: -8 }}
              animate={on ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: d(1.9) }}
            >
              false alarm
            </motion.span>
            <motion.span
              className="schema-flag hit"
              style={{ left: '71%' }}
              initial={{ opacity: 0, y: -8 }}
              animate={on ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: d(3.0) }}
            >
              ✓ found at 66′
            </motion.span>
          </div>
        </div>
        <div className="schema-ticks">
          {['0′', '15′', '30′', '45′', '60′', '75′', '90′'].map((t) => (
            <span key={t}>{t}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

function Num({ children, tag, label, note }: { children: ReactNode; tag: string; label: string; note: string }) {
  return (
    <Reveal className="result board">
      <span className="board-strip">{tag}</span>
      <b className="result-value">{children}</b>
      <span className="result-label">{label}</span>
      <span className="result-note">{note}</span>
    </Reveal>
  )
}

function InView({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })
  return <span ref={ref}>{inView ? children : ' '}</span>
}

const FLOW = [
  { t: 'Match simulator', s: 'Synthetic matches: every player 10 times a second, every event. Hidden storylines kept apart.', k: 'data' },
  { t: 'Metrics engine', s: 'Speed, pass difficulty, xG, xT, pressing, territory. Plain code, no AI.', k: 'code' },
  { t: 'Statistical candidates', s: 'Code flags a moment only when two signals move beyond normal noise.', k: 'code' },
  { t: 'Six agents', s: 'Detector, Analyst, Verifier, Narrator, Persona, Director on Microsoft Agent Framework; numbers only via MCP tools.', k: 'agent' },
  { t: 'Verifier gate', s: 'Code recomputes every cited number, a model checks the wording. One retry, then drop.', k: 'gate' },
  { t: 'On air', s: 'Data graphics at once; AI cards as a template first, then the verified text.', k: 'air' },
]

const TECH = [
  ['Microsoft Foundry', 'Hosts the language models (gpt-5.4-mini, and gpt-5-mini for the Analyst); the app signs in with its own identity, no keys.'],
  ['Microsoft Agent Framework', 'Runs the six agents as one workflow graph, with timeouts, the Verifier retry loop and template fallbacks.'],
  ['Model Context Protocol (MCP)', 'The only way an agent gets a number: six typed metrics tools served by the app.'],
  ['Azure Container Apps', 'One container serves the API, the live streams and this site.'],
  ['Azure Database for PostgreSQL', 'Keeps every agent run and moment, with its verdicts.'],
  ['Azure Blob Storage + managed identity', 'Demo matches and recorded runs, read at startup with the app’s own identity. The hidden storylines are never uploaded.'],
  ['Application Insights', 'OpenTelemetry traces for every moment and every agent call.'],
]

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
  const first = runs.find((r) => r.featured_rejection_at_ms == null) ?? runs[0]
  const ctrl = runs.find((r) => r.featured_rejection_at_ms != null)
  const ctrlHref = ctrl ? `/control?run=${ctrl.run_id}&from=${(ctrl.featured_rejection_at_ms ?? 0) - 20000}&speed=2` : '/control'
  const runId = first?.run_id ?? HERO_RUN
  const liveOff = quota != null && quota.remaining <= 0

  const EXPLORE = [
    { href: `/broadcast?run=${runId}`, t: 'Broadcast', s: 'Watch a whole match with the graphics on. Skip to the key moments; the AI cards pause so you can read them.' },
    { href: `/split?run=${runId}&from=2045000`, t: 'Split view', s: 'Analyst vs fan: one moment, told for an expert in English and a casual fan in Italian, side by side.' },
    { href: ctrlHref, t: 'Control room', s: 'Watch the AI agents work and check each other, including a claim the Verifier threw out.' },
    { href: `/graphics?run=${runId}`, t: 'Graphics layer for OBS', s: 'Only the graphics, on a transparent background: drop it over any video feed, as a TV gallery would.' },
    { href: '/second', t: 'Second screen', s: 'The phone companion: moments as they happen, in your language, following your player.' },
    { href: '/eval', t: 'Evaluation report', s: 'How we measured it, match by match, including what it gets wrong.' },
  ]

  return (
    <MotionConfig reducedMotion="user">
      <main className="landing site">
        <SiteNav
          links={[
            ['#how', 'How it works'],
            ['#trust', 'Trust'],
            ['#results', 'Results'],
            ['#explore', 'Explore'],
            ['#hood', 'Under the hood'],
          ]}
        />

        <header className="hero">
          <motion.div
            className="hero-copy"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="kicker">
              <Mark size={18} /> AI for live football broadcasts
            </p>
            <h1>
              Reads the game.
              <br />
              <span className="accent">Directs the broadcast.</span>
            </h1>
            <p className="hero-line">
              AI match graphics and tactical explanations, generated live, and checked before they go on air.
            </p>
            <div className="actions">
              <a className="cta primary" href="/tour">
                <span className="unskew">▶ Take the 2-minute tour</span>
              </a>
              <a className="cta" href={`/broadcast?run=${runId}`}>
                <span className="unskew">Watch a full match</span>
              </a>
            </div>
            <p className="name-note">
              In Italian, <em>regista</em> is both the playmaker who reads the game and the TV director who decides what goes on
              air.
            </p>
          </motion.div>
          <motion.div
            className="hero-visual"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          >
            <HeroPlayer />
          </motion.div>
        </header>

        <section className="band light problem" id="problem">
          <Reveal className="narrow">
            <h2 className="eyebrow-h">The problem</h2>
            <p className="big-text">
              On TV, graphics like <q>shot at 112 km/h</q> and lines like <q>they’ve been pressing high for ten minutes</q> are
              prepared by a team of analysts and designers.
            </p>
            <p className="big-text dim">It’s expensive, so it only happens for big matches, and in few languages.</p>
          </Reveal>
        </section>

        <section className="band" id="how">
          <Reveal>
            <h2 className="eyebrow-h">What it does</h2>
          </Reveal>
          <div className="cards3">
            <Reveal className="card" delay={0}>
              <Icon kind="stats" />
              <h3>Live stats graphics</h3>
              <p>Player speed, shot speed, pass difficulty: computed by code, instantly, and drawn like a TV graphic.</p>
              <span className="who code">Computed by code</span>
            </Reveal>
            <Reveal className="card" delay={0.08}>
              <Icon kind="tactics" />
              <h3>Tactical explanations</h3>
              <p>It notices when something changes, for example a team raising its press, and explains why it matters, citing the numbers.</p>
              <span className="who ai">Written by AI, verified</span>
            </Reveal>
            <Reveal className="card" delay={0.16}>
              <Icon kind="fans" />
              <h3>Made for every fan</h3>
              <p>The same moment told differently to an expert analyst and a casual fan, in English, Italian or Spanish, following their favourite player.</p>
              <span className="who ai">Written by AI, verified</span>
            </Reveal>
          </div>
        </section>

        <section className="band light trust" id="trust">
          <Reveal className="narrow">
            <h2 className="eyebrow-h">Why you can trust it</h2>
            <p className="big-text">
              The real problem with AI on live TV is trust: one invented stat on air is a disaster. So every number an agent says
              is <span className="accent">recomputed by code</span> before it is shown.
            </p>
            <p className="body-text">
              And we measured how reliable it is. Our synthetic matches contain hidden storylines that the AI never sees; then we
              count how many it discovers on its own.
            </p>
          </Reveal>
          <Reveal className="dark-scope">
            <TrustSchema />
          </Reveal>
        </section>

        <section className="band" id="results">
          <Reveal>
            <h2 className="eyebrow-h">Results</h2>
            <p className="body-text">One official run on matches kept aside during development. All data is synthetic.</p>
          </Reveal>
          <div className="results">
            <Num tag="Storylines found" label="of the hidden storylines found" note="23 of 44, on 20 matches the system had never seen">
              <InView>
                <CountUp value={52} duration={1.2} />
              </InView>
              <small>%</small>
            </Num>
            <Num tag="Unsupported on air" label="explanations on air with a number the data doesn’t support" note="out of 81 approved explanations">
              <InView>
                <CountUp value={0} from={9} duration={1.2} />
              </InView>
              <small> / 81</small>
            </Num>
            <Num tag="Evidence recount" label="evidence items confirmed by an independent recount" note="267 of 267 recomputed from the raw match data">
              <InView>
                <CountUp value={100} duration={1.2} />
              </InView>
              <small>%</small>
            </Num>
            <Num tag="AI cost" label="total AI cost" note="Microsoft Foundry, development, evaluation and demo runs together">
              <small>≈ €</small>
              <InView>
                <CountUp value={1.76} decimals={2} duration={1.2} />
              </InView>
            </Num>
          </div>
          <Reveal>
            <p className="caveats">
              Read with care: 45 more evidence items (xT, control index) are checked only by the Verifier’s own recomputation.
              Precision is 43%: about half of the approved explanations describe ordinary swings that look like a storyline, and on
              control matches with nothing planted it still approved 1.8 explanations per match. About a quarter of storylines,
              mostly single-player ones, never become a candidate. One run, 20 evaluation and 10 control matches.{' '}
              <a href="/eval">Full report →</a>
            </p>
          </Reveal>
        </section>

        <section className="band light" id="explore">
          <Reveal>
            <h2 className="eyebrow-h">Explore</h2>
          </Reveal>
          <div className="explore">
            {EXPLORE.map((e, i) => (
              <Reveal key={e.t} delay={0.05 * i} className="explore-cell">
                <a className="explore-card tactic dark-scope" href={e.href}>
                  <h3>
                    <span className="kit-num num">{i + 1}</span> {e.t} <span aria-hidden>→</span>
                  </h3>
                  <p>{e.s}</p>
                </a>
              </Reveal>
            ))}
            <Reveal delay={0.3} className="explore-cell">
              <a
                className={`explore-card tactic dark-scope live ${liveOff ? 'disabled' : ''}`}
                href={liveOff ? undefined : `/broadcast?live=${first?.match_id ?? 'm_1000'}`}
                aria-disabled={liveOff}
              >
                <h3>
                  <span className="live-dot" /> Go live <span aria-hidden>→</span>
                </h3>
                <p>
                  Run the agents now on a match, with real model calls.{' '}
                  <span className="num">{quota ? (liveOff ? 'Paused for today.' : `${quota.remaining} model calls left today.`) : ''}</span>
                </p>
              </a>
            </Reveal>
          </div>
        </section>

        <section className="band hood" id="hood">
          <Reveal>
            <h2 className="eyebrow-h">Under the hood</h2>
            <p className="big-text">Numbers from tools, words from models.</p>
          </Reveal>
          <div className="flow">
            {FLOW.map((f, i) => (
              <Reveal key={f.t} delay={0.08 * i} className={`flow-node ${f.k}`}>
                <span className={`kit-num num ${f.k === 'agent' || f.k === 'gate' ? 'ai' : f.k === 'code' ? '' : 'away'}`}>{i + 1}</span>
                <h4>{f.t}</h4>
                <p>{f.s}</p>
                {i < FLOW.length - 1 && <i className="flow-link" aria-hidden />}
              </Reveal>
            ))}
          </div>
          <div className="tech">
            {TECH.map(([t, s], i) => (
              <Reveal key={t} delay={0.04 * i} className="tech-item">
                <b>{t}</b>
                <span>{s}</span>
              </Reveal>
            ))}
          </div>
          <p className="body-text">
            <a href="/architecture">Architecture on Azure →</a>
          </p>
        </section>

        <footer className="land-foot">
          <Wordmark size={18} />
          <span>Reads the game. Directs the broadcast.</span>
          <span className="credit">
            Built by Lorenzo Galli · MSc student, KTH Royal Institute of Technology ·{' '}
            <a href="https://github.com/lorenzogalli-dev">github.com/lorenzogalli-dev</a>
          </span>
          <span className="fine">
            Recorded agent runs are real outputs of the pipeline, replayed with zero model calls. All clubs, players and data are
            synthetic. MIT licence.
          </span>
        </footer>
      </main>
    </MotionConfig>
  )
}
