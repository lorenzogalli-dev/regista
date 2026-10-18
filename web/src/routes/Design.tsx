import { MotionConfig } from 'motion/react'
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'

import { MomentCard } from '../broadcast/MomentCard.tsx'
import { PassCard } from '../broadcast/PassGraphics.tsx'
import { Scorebug } from '../broadcast/Scorebug.tsx'
import '../broadcast/broadcast.css'
import { AI_ACCENT, BG, contrast, deltaE, teamPalette } from '../lib/color.ts'
import { loadSample, type Sample, type TeamInfo } from '../lib/sample.ts'
import './design.css'

// Design reference (D5a): tokens, type and the first components over clashing team colours.

const COLOURS = [
  ['--bg', '#06110C', 'Background'],
  ['--panel', '#0C1B14', 'Panel'],
  ['--text', '#F2F5F3', 'Text'],
  ['--text-2', '#9FB0A7', 'Secondary text'],
  ['--ai', '#46E5D8', 'AI insight only'],
  ['--brand', '#7CF25C', 'Regista accent: product chrome, computed-by-code marks'],
  ['--pending', '#F5B544', 'Pending model text'],
  ['--error', '#FF5A5F', 'Errors (control room)'],
  ['--grass-2', '#123222', 'Pitch'],
] as const

const PAIRS: { name: string; home: [string, string[]]; away: [string, string[]] }[] = [
  { name: 'Red vs dark red', home: ['RDV', ['#C8102E', '#FFFFFF']], away: ['CRM', ['#A50021', '#F4D03F']] },
  { name: 'Black vs navy', home: ['BLK', ['#1B1B1B', '#F2F5F3']], away: ['NVY', ['#0B1F4B', '#0B1F4B']] },
  { name: 'White vs light grey', home: ['WHT', ['#FFFFFF', '#000000']], away: ['GRY', ['#E6E6E6', '#C8102E']] },
  { name: 'Cyan kit vs teal', home: ['CYN', ['#40E0D0', '#003B46']], away: ['TEA', ['#2BB3A3', '#2BB3A3']] },
]

function team(short: string): TeamInfo {
  return { team_id: `t_${short.toLowerCase()}`, name: short, short, formation: '' }
}

/** Scales a fixed-width broadcast component down to the available width (never up). */
function Fit({ width, children }: { width: number; children: ReactNode }) {
  const outer = useRef<HTMLDivElement>(null)
  const inner = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [height, setHeight] = useState<number | undefined>()
  useLayoutEffect(() => {
    const o = outer.current
    const i = inner.current
    if (!o || !i) return
    const ro = new ResizeObserver(() => {
      const s = Math.min(1, o.clientWidth / width)
      setScale(s)
      setHeight(i.offsetHeight * s)
    })
    ro.observe(o)
    ro.observe(i)
    return () => ro.disconnect()
  }, [width])
  return (
    <div ref={outer} className="fit" style={{ height }}>
      <div ref={inner} style={{ width, transform: `scale(${scale})`, transformOrigin: 'top left' }}>
        {children}
      </div>
    </div>
  )
}

export function Design() {
  const [sample, setSample] = useState<Sample | null>(null)
  useEffect(() => {
    loadSample('/samples/hero_m_1000.json')
      .then(setSample)
      .catch(() => setSample(null))
  }, [])
  const players = new Map(sample?.match.players.map((p) => [p.player_id, p]) ?? [])
  const pass = sample?.pass_card

  return (
    <MotionConfig reducedMotion="user">
      <main className="design">
        <header className="design-head">
          <p className="eyebrow">Regista · design system</p>
          <h1>Verified on air</h1>
          <p className="lede">
            Data graphics are neutral and instant. AI insight is cyan and carries a verified seal. A viewer can tell
            measurement from interpretation at a glance.
          </p>
          <nav>
            <a href="/broadcast?sample=hero_m_1000">Broadcast frame</a>
            <a href="/graphics?sample=hero_m_1000">Graphics-only output</a>
          </nav>
        </header>

        <section>
          <h2>Colour</h2>
          <div className="swatches">
            {COLOURS.map(([token, hex, role]) => (
              <div className="swatch" key={token}>
                <span className="chip" style={{ background: hex }} />
                <code>{token}</code>
                <span className="num">{hex}</span>
                <span className="role">{role}</span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2>Type</h2>
          <div className="type-specimens">
            <div>
              <span className="spec-label">Barlow Condensed 700 · scorebug, lower thirds</span>
              <p className="spec condensed">LIN 1 – 0 DUN · 70:04</p>
            </div>
            <div>
              <span className="spec-label">Barlow Condensed 800 · titles, big numbers</span>
              <p className="spec expanded">Turned the pitch</p>
            </div>
            <div>
              <span className="spec-label">Barlow · body and UI</span>
              <p className="spec body">Field tilt up from 21% to 73% in the last 12 minutes.</p>
            </div>
            <div>
              <span className="spec-label">Tabular figures: values never jitter</span>
              <p className="spec condensed num">11.1 · 38.0 · 64 · 100</p>
            </div>
          </div>
        </section>

        <section>
          <h2>Team colours</h2>
          <p className="note">
            Any kit pair is made readable automatically: text on team colour ≥ 4.5:1, team marks on the dark background
            ≥ 3:1, home and away clearly apart, and no team may look like the AI cyan.
          </p>
          <div className="pairs">
            {PAIRS.map((p) => {
              const pal = teamPalette(p.home[1], p.away[1])
              return (
                <div className="pair" key={p.name}>
                  <span className="spec-label">{p.name}</span>
                  <Fit width={620}>
                    <div className="inline-bug">
                      <Scorebug
                        home={{ team: team(p.home[0]), colors: pal.home, score: 2 }}
                        away={{ team: team(p.away[0]), colors: pal.away, score: 1 }}
                        clock="63:12"
                        possession={team(p.home[0]).team_id}
                      />
                    </div>
                  </Fit>
                  <table className="num">
                    <tbody>
                      {(['home', 'away'] as const).map((side) => (
                        <tr key={side}>
                          <td>{side}</td>
                          <td>
                            <span className="dot" style={{ background: p[side][1][0] }} /> kit {p[side][1][0]}
                          </td>
                          <td>
                            <span className="dot" style={{ background: pal[side].fill }} /> used {pal[side].fill}
                          </td>
                          <td>text {contrast(pal[side].fill, pal[side].ink).toFixed(1)}:1</td>
                          <td>mark {contrast(pal[side].line, BG).toFixed(1)}:1</td>
                          <td>ΔE AI {deltaE(pal[side].fill, AI_ACCENT).toFixed(0)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <span className="role">home vs away ΔE {deltaE(pal.home.fill, pal.away.fill).toFixed(0)}</span>
                </div>
              )
            })}
          </div>
        </section>

        {sample && pass && (
          <section>
            <h2>Graphics</h2>
            <div className="components">
              <div>
                <span className="spec-label">Pass card · tier 0 · data</span>
                <Fit width={430}>
                  <div className="inline-card">
                    <PassCard
                      pass={pass}
                      passer={players.get(pass.player_id)!}
                      receiver={players.get(pass.recipient_id)!}
                      colors={
                        teamPalette(sample.colors[sample.match.home.team_id], sample.colors[sample.match.away.team_id])
                          .away
                      }
                      position={{ left: 0, top: 0 }}
                    />
                  </div>
                </Fit>
              </div>
              <div>
                <span className="spec-label">Moment card · tier 1 · AI insight</span>
                <Fit width={880}>
                  <div className="inline-card">
                    <MomentCard
                      kicker="Momentum · last 12 min"
                      headline="Dunhurst have turned the pitch"
                      body="Trailing 0–1, they are pinning Linbridge back: field tilt up from 21% to 73% in the last 12 minutes."
                      evidence={[
                        { label: 'Field tilt', before: 0.214, after: 0.732, unit: 'pct' },
                        {
                          label: 'Control index',
                          before: sample.window.deltas.control_index.before ?? 0,
                          after: sample.window.deltas.control_index.after ?? 0,
                          unit: 'num',
                        },
                        {
                          label: 'Possession (time-based)',
                          before: sample.window.deltas.possession_time_based.before ?? 0,
                          after: sample.window.deltas.possession_time_based.after ?? 0,
                          unit: 'pct',
                        },
                      ]}
                      sample="Design sample · text hand-written"
                    />
                  </div>
                </Fit>
              </div>
            </div>
          </section>
        )}

        <footer className="design-foot">
          All clubs, players and data are synthetic. Fonts: Barlow, Barlow Condensed and Newsreader, SIL Open Font License (
          <a href="/fonts/LICENSES/Barlow-OFL.txt">Barlow</a>, <a href="/fonts/LICENSES/BarlowCondensed-OFL.txt">Barlow Condensed</a>,{' '}
          <a href="/fonts/LICENSES/Newsreader-OFL.txt">Newsreader</a>).
        </footer>
      </main>
    </MotionConfig>
  )
}
