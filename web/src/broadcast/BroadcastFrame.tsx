import { AnimatePresence, MotionConfig } from 'motion/react'
import { useEffect, useMemo } from 'react'

import { teamPalette, type TeamColors } from '../lib/color.ts'
import { createClock, useClockTick } from '../lib/clock.ts'
import { anchorAt, broadcastCamera } from '../lib/projection.ts'
import { matchClock, possessionAt, type PlayerInfo, type Sample } from '../lib/sample.ts'
import './broadcast.css'
import { MomentCard, type Evidence } from './MomentCard.tsx'
import { SCOREBUG_ZONE, on, passCardPosition, timeline } from './layout.ts'
import { PassCard, PassTrail } from './PassGraphics.tsx'
import { PitchCanvas } from './PitchCanvas.tsx'
import { PlayerTag } from './PlayerTag.tsx'
import { Scorebug } from './Scorebug.tsx'
import { Stage } from './Stage.tsx'

function momentCopy(s: Sample, teamName: string, otherName: string, own: number, other: number) {
  const d = s.window.deltas
  const pct = (v: number | null) => Math.round((v ?? 0) * 100)
  const evidence: Evidence[] = [
    { label: 'Field tilt', before: d.field_tilt.before ?? 0, after: d.field_tilt.after ?? 0, unit: 'pct' },
    { label: 'Control index', before: d.control_index.before ?? 0, after: d.control_index.after ?? 0, unit: 'num' },
    {
      label: 'Possession (time-based)',
      before: d.possession_time_based.before ?? 0,
      after: d.possession_time_based.after ?? 0,
      unit: 'pct',
    },
  ]
  const state =
    own < other ? `Trailing ${own}–${other}` : own > other ? `Leading ${own}–${other}` : `Level at ${own}–${other}`
  return {
    kicker: `Momentum · last ${s.window.minutes} min`,
    headline: `${teamName} have turned the pitch`,
    body: `${state}, they are pinning ${otherName} back: field tilt up from ${pct(d.field_tilt.before)}% to ${pct(d.field_tilt.after)}% in the last ${s.window.minutes} minutes.`,
    evidence,
  }
}

export function BroadcastFrame({
  sample,
  freezeAt,
  graphicsOnly = false,
  debugAnchors = false,
}: {
  sample: Sample
  freezeAt: number | null
  graphicsOnly?: boolean
  debugAnchors?: boolean
}) {
  const camera = useMemo(() => broadcastCamera(), [])
  const clock = useMemo(
    () => createClock({ start: sample.clip.start_ms, end: sample.clip.end_ms, freezeAt }),
    [sample, freezeAt],
  )
  useEffect(() => {
    clock.start()
    return () => clock.stop()
  }, [clock])
  const t = useClockTick(clock, 100)

  const { home, away } = sample.match
  const pal = useMemo(() => {
    const p = teamPalette(sample.colors[home.team_id], sample.colors[away.team_id])
    return { [home.team_id]: p.home, [away.team_id]: p.away } as Record<string, TeamColors>
  }, [sample, home.team_id, away.team_id])
  const players = useMemo(
    () => new Map<string, PlayerInfo>(sample.match.players.map((p) => [p.player_id, p])),
    [sample],
  )
  const tl = useMemo(() => timeline(sample), [sample])

  const pass = sample.pass_card
  const passer = players.get(pass.player_id)!
  const receiver = players.get(pass.recipient_id)!
  const team = sample.window.team_id
  const teamInfo = team === home.team_id ? home : away
  const otherInfo = team === home.team_id ? away : home
  const copy = momentCopy(
    sample,
    teamInfo.name.split(' ')[0],
    otherInfo.name.split(' ')[0],
    sample.score[team] ?? 0,
    sample.score[otherInfo.team_id] ?? 0,
  )
  const cardPos = passCardPosition(pass, camera, SCOREBUG_ZONE)

  return (
    <MotionConfig reducedMotion="user">
      <Stage fit={!graphicsOnly} transparent={graphicsOnly}>
        {!graphicsOnly && clock && <PitchCanvas sample={sample} clock={clock} camera={camera} palette={pal} />}
        {clock && (
          <>
            <AnimatePresence>
              {on(t, tl.trail) && (
                <PassTrail
                  key="trail"
                  pass={pass}
                  camera={camera}
                  color={pal[pass.team_id].line}
                  flightS={tl.flightS}
                />
              )}
            </AnimatePresence>
            <AnimatePresence>
              {on(t, tl.passerTag) && (
                <PlayerTag
                  key="passer"
                  player={passer}
                  colors={pal[passer.team_id]}
                  frames={sample.frames}
                  clock={clock}
                  camera={camera}
                />
              )}
              {on(t, tl.receiverTag) && (
                <PlayerTag
                  key="receiver"
                  player={receiver}
                  colors={pal[receiver.team_id]}
                  frames={sample.frames}
                  clock={clock}
                  camera={camera}
                />
              )}
            </AnimatePresence>
            <Scorebug
              home={{ team: home, colors: pal[home.team_id], score: sample.score[home.team_id] ?? 0 }}
              away={{ team: away, colors: pal[away.team_id], score: sample.score[away.team_id] ?? 0 }}
              clock={matchClock(t, sample.period_end_ms)}
              possession={possessionAt(sample.events, t)}
            />
            <AnimatePresence>
              {on(t, tl.passCard) && (
                <PassCard
                  key="pass"
                  pass={pass}
                  passer={passer}
                  receiver={receiver}
                  colors={pal[pass.team_id]}
                  position={cardPos}
                />
              )}
            </AnimatePresence>
            <AnimatePresence>
              {on(t, tl.moment) && (
                <MomentCard
                  key="moment"
                  {...copy}
                  sample="Design sample · text hand-written for D5a · numbers from the metrics tools"
                />
              )}
            </AnimatePresence>
          </>
        )}
        {debugAnchors &&
          [
            { x: 11, y: 34 },
            { x: 94, y: 34 },
            { x: 52.5, y: 34 },
          ].map((p) => <span key={p.x} className="debug-anchor" style={anchorAt(camera, p)} />)}
      </Stage>
    </MotionConfig>
  )
}
