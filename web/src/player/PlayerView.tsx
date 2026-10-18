import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'

import { PERSONAS } from '../broadcast/labels.ts'
import { ProgramFrame } from '../broadcast/ProgramFrame.tsx'
import { usePlayer } from '../lib/player.ts'
import { STAGE } from '../lib/projection.ts'
import { matchClock } from '../lib/sample.ts'
import { Wordmark } from '../brand/Wordmark.tsx'
import { InsightsFeed } from './InsightsFeed.tsx'
import { Timeline } from './Timeline.tsx'
import './player.css'

// Broadcast player for a recorded agent run: the 16:9 programme, a clickable timeline of key
// moments, transport (pause, next key moment, auto-skip, moment replay), persona and the
// insights feed.


/** Largest stage scale that fits the element. */
function useFitScale(ref: React.RefObject<HTMLElement | null>): number {
  const [scale, setScale] = useState(0.5)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect()
      setScale(Math.max(0.1, Math.min(r.width / STAGE.width, r.height / STAGE.height)))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [ref])
  return scale
}

export function PlayerView({ runId, from, initialPersona, fav }: { runId: string | null; from: number; initialPersona: string; fav: string | null }) {
  const [persona, setPersona] = useState(initialPersona)
  const p = usePlayer({ runId, from, persona })
  const stageRef = useRef<HTMLDivElement>(null)
  const scale = useFitScale(stageRef)
  const meta = p.stream?.meta ?? null

  // Favourite player: from the URL, else the first player a published moment names.
  const favorite =
    fav ?? p.run?.moments.find((m) => m.status === 'published' && m.explanation?.player_ids.length)?.explanation?.player_ids[0] ?? null
  const favName = meta?.players.find((x) => x.player_id === favorite)?.name

  if (p.stream?.error) return <p style={{ padding: 40 }}>{p.stream.error}</p>
  const duration = p.timeline?.duration_ms ?? meta?.period_end_ms[1] ?? 1
  return (
    <MotionConfig reducedMotion="user">
    <main className="player">
      <header className="player-top">
        <a href="/" className="player-home" aria-label="Regista home">
          <Wordmark size={22} />
        </a>
        <span className="player-match">
          {meta ? (
            <>
              {meta.home.name} <span className="dim">v</span> {meta.away.name}
              <span className="player-tag">Recorded agent run · synthetic match</span>
            </>
          ) : (
            ' '
          )}
        </span>
        <label className="player-persona">
          <span>Told for</span>
          <select value={persona} onChange={(e) => setPersona(e.target.value)}>
            {PERSONAS.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
                {id.startsWith('player_focus') && favName ? ` (${favName})` : ''}
              </option>
            ))}
          </select>
        </label>
      </header>

      <div className="player-main">
        <div className="player-stage" ref={stageRef}>
          {p.stream && p.clock && (
            <div className="player-frame" style={{ width: STAGE.width * scale, height: STAGE.height * scale }}>
              <ProgramFrame
                stream={p.stream}
                clock={p.clock}
                opts={{
                  persona,
                  favoritePlayer: persona.startsWith('player_focus') ? favorite : null,
                  scale,
                  fit: false,
                  replay: p.replay,
                }}
              />
              <AnimatePresence>
                {p.skipping && (
                  <motion.div
                    className="ff"
                    data-testid="fast-forward"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                  >
                    <span className="ff-arrows" aria-hidden>
                      <i />
                      <i />
                    </span>
                    <span>
                      Skipping quiet play <b className="num">×8</b>
                    </span>
                  </motion.div>
                )}
                {p.paused && !p.replay && (
                  <motion.button
                    type="button"
                    className="ff paused"
                    onClick={() => p.setPaused(false)}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    ❚❚ Paused · press Space to play
                  </motion.button>
                )}
              </AnimatePresence>
            </div>
          )}
          {!p.stream && <div className="player-loading">Loading the recorded run…</div>}
        </div>
        <InsightsFeed run={p.run} t={p.t} persona={persona} meta={meta} markers={p.markers} onSeek={p.seek} />
      </div>

      <section className="player-bar" aria-label="Playback">
        <div className="controls">
          {p.replay ? (
            <button type="button" className="ctl play continue" onClick={p.endReplay}>
              Continue ▶ <kbd>Space</kbd>
            </button>
          ) : (
            <button type="button" className="ctl play" onClick={() => p.setPaused(!p.paused)} aria-label={p.paused ? 'Play' : 'Pause'}>
              {p.paused ? '▶' : '❚❚'}
            </button>
          )}
          <span className="ctl-clock num">{meta ? matchClock(p.t, meta.period_end_ms) : '--:--'}</span>
          <button type="button" className="ctl next" onClick={p.next}>
            Next key moment <kbd>N</kbd>
          </button>
          <label className="toggle">
            <input type="checkbox" checked={p.autoSkip} onChange={(e) => p.setAutoSkip(e.target.checked)} />
            <span className="toggle-ui" aria-hidden />
            Skip quiet play
          </label>
          <label className="toggle">
            <input type="checkbox" checked={p.momentReplay} onChange={(e) => p.setMomentReplay(e.target.checked)} />
            <span className="toggle-ui" aria-hidden />
            Moment replay
          </label>
        </div>
        {meta && (
          <Timeline t={p.t} duration={duration} periodEnd={p.timeline?.period_end_ms ?? meta.period_end_ms} markers={p.markers} onSeek={p.seek} />
        )}
      </section>
    </main>
    </MotionConfig>
  )
}
