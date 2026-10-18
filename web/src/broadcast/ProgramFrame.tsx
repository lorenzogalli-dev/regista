import { AnimatePresence, MotionConfig } from 'motion/react'
import { useMemo } from 'react'

import { teamPalette, type TeamColors } from '../lib/color.ts'
import { useClockTick, type Clock } from '../lib/clock.ts'
import { broadcastCamera } from '../lib/projection.ts'
import { matchClock, possessionAt, type PlayerInfo } from '../lib/sample.ts'
import { activeOverlays, type MatchStream, type Overlay } from '../lib/stream.ts'
import './broadcast.css'
import { SCOREBUG_ZONE, passCardPosition } from './layout.ts'
import { MomentCard, type Evidence } from './MomentCard.tsx'
import { Caption, MomentumRibbon, ShotSpeed, SourceLabel, SpeedBadge, StatCompare } from './Package.tsx'
import { PassCard, PassTrail } from './PassGraphics.tsx'
import { PitchCanvas } from './PitchCanvas.tsx'
import { PlayerTag } from './PlayerTag.tsx'
import { Scorebug } from './Scorebug.tsx'
import { Stage } from './Stage.tsx'

const SHARE = new Set(['possession_time_based', 'field_tilt', 'pass_completion'])
const LABELS: Record<string, string> = {
  possession_time_based: 'Possession (time-based)',
  field_tilt: 'Field tilt',
  ppda: 'PPDA',
  pass_completion: 'Pass completion',
  avg_pass_length_m: 'Avg pass length (m)',
  width_m: 'Width (m)',
  xt_added: 'xT added',
  control_index: 'Control index',
  touches: 'Touches',
  progressive_passes: 'Progressive passes',
  passes: 'Passes',
  sprints: 'Sprints',
  distance_m: 'Distance (m)',
  minutes_on_pitch: 'Minutes on pitch',
}
const KICKER: Record<string, string> = {
  pressing_spell: 'Pressing',
  momentum_shift: 'Momentum',
  tactical_switch: 'Tactics',
  player_arc: 'Player',
}

function evidenceChips(items: any[] = []): Evidence[] {
  return items.slice(0, 3).map((e) => ({
    label: LABELS[e.metric] ?? e.metric,
    before: e.before,
    after: e.after,
    unit: SHARE.has(e.metric) ? 'pct' : 'num',
  }))
}

export type ProgramOptions = {
  persona: string
  favoritePlayer?: string | null
  graphicsOnly?: boolean
  fit?: boolean
  scale?: number
}

export function ProgramFrame({ stream, clock, opts }: { stream: MatchStream; clock: Clock; opts: ProgramOptions }) {
  const t = useClockTick(clock, 100)
  const camera = useMemo(() => broadcastCamera(), [])
  const meta = stream.meta
  const pal = useMemo(() => {
    if (!meta) return null
    const p = teamPalette(meta.home.colors, meta.away.colors)
    return { [meta.home.team_id]: p.home, [meta.away.team_id]: p.away } as Record<string, TeamColors>
  }, [meta])
  const players = useMemo(
    () => new Map<string, PlayerInfo>((meta?.players ?? []).map((p) => [p.player_id, p])),
    [meta],
  )
  if (!meta || !pal) return <Stage fit={opts.fit ?? !opts.graphicsOnly} scale={opts.scale} transparent={opts.graphicsOnly}>{null}</Stage>

  const frames = () => stream.frames
  const on = activeOverlays(stream.overlays, t)
  const latest = (kinds: string[]) =>
    on.filter((o) => kinds.includes(o.kind)).sort((a, b) => b.show_at_ms - a.show_at_ms)[0] as Overlay | undefined
  const badge = latest(['speed_badge', 'shot_speed'])
  const passCard = latest(['pass_card'])
  const stat = latest(['stat_compare'])
  const card = latest(['moment_card'])
  // The Narrator writes captions in English; other languages get the persona card only.
  const caption = opts.persona.endsWith('_en') ? latest(['caption']) : undefined
  const ribbon = stream.overlays
    .filter((o) => o.kind === 'momentum_bar' && o.show_at_ms <= t)
    .map((o) => ({
      t: o.show_at_ms,
      home: o.payload.control_index[meta.home.team_id],
      away: o.payload.control_index[meta.away.team_id],
    }))

  const score: Record<string, number> = { [meta.home.team_id]: 0, [meta.away.team_id]: 0 }
  for (const e of stream.events) if (e.type === 'goal' && e.t_ms <= t && e.team_id) score[e.team_id] += 1

  const persona = opts.persona
  const cardProps = (() => {
    if (!card || card.payload.state === 'withdrawn') return null
    const p = card.payload
    if (p.state === 'pending') {
      return { state: 'pending' as const, headline: p.headline, body: p.text, evidence: [], kicker: 'Template · numbers from code' }
    }
    const text = p.texts?.[persona] ?? { headline: p.mechanism_tag, text: p.claim }
    return {
      state: 'verified' as const,
      headline: text.headline,
      body: text.text,
      evidence: evidenceChips(p.evidence),
      kicker: `${KICKER[p.mechanism_tag] ?? 'Insight'} · ${persona.replace('_', ' ')}`,
    }
  })()

  const pc = passCard?.payload
  const passer = pc ? players.get(pc.player_id) : undefined
  const receiver = pc?.recipient_id ? players.get(pc.recipient_id) : undefined
  const fav = opts.favoritePlayer ? players.get(opts.favoritePlayer) : undefined
  const badgePlayer = badge ? players.get(badge.payload.player_id) : undefined

  return (
    <MotionConfig reducedMotion="user">
      <Stage fit={opts.fit ?? !opts.graphicsOnly} scale={opts.scale} transparent={opts.graphicsOnly}>
        {!opts.graphicsOnly && (
          <PitchCanvas players={meta.players} frames={frames} clock={clock} camera={camera} palette={pal} />
        )}
        <AnimatePresence>
          {pc && passer && (
            <PassTrail
              key={passCard!.overlay_id + '_trail'}
              pass={{ ...pc, t_ms: passCard!.show_at_ms } as never}
              camera={camera}
              color={pal[pc.team_id].line}
              flightS={pc.pass_length_m / ((pc.ball_speed_ms ?? 18) * 0.85)}
            />
          )}
        </AnimatePresence>
        <AnimatePresence>
          {fav && <PlayerTag key={'fav_' + fav.player_id} player={fav} colors={pal[fav.team_id]} frames={frames} clock={clock} camera={camera} />}
          {passer && passer.player_id !== fav?.player_id && (
            <PlayerTag key={'p_' + passCard!.overlay_id} player={passer} colors={pal[passer.team_id]} frames={frames} clock={clock} camera={camera} />
          )}
          {receiver && receiver.player_id !== fav?.player_id && (
            <PlayerTag key={'r_' + passCard!.overlay_id} player={receiver} colors={pal[receiver.team_id]} frames={frames} clock={clock} camera={camera} />
          )}
        </AnimatePresence>
        <AnimatePresence>
          {badge && badgePlayer && badge.kind === 'speed_badge' && (
            <SpeedBadge key={badge.overlay_id} player={badgePlayer} colors={pal[badgePlayer.team_id]} kmh={badge.payload.value} frames={frames} clock={clock} camera={camera} />
          )}
          {badge && badgePlayer && badge.kind === 'shot_speed' && (
            <ShotSpeed
              key={badge.overlay_id}
              player={badgePlayer}
              colors={pal[badgePlayer.team_id]}
              kmh={badge.payload.value}
              xg={badge.payload.xg}
              outcome={badge.payload.outcome}
              frames={frames}
              clock={clock}
              camera={camera}
            />
          )}
        </AnimatePresence>
        <Scorebug
          home={{ team: meta.home, colors: pal[meta.home.team_id], score: score[meta.home.team_id] }}
          away={{ team: meta.away, colors: pal[meta.away.team_id], score: score[meta.away.team_id] }}
          clock={matchClock(t, meta.period_end_ms)}
          possession={possessionAt(stream.events, t)}
        />
        {stream.header && <SourceLabel kind={stream.header.kind} />}
        <AnimatePresence>
          {stat && (
            <StatCompare
              key={stat.overlay_id}
              minutes={stat.payload.window_minutes}
              home={meta.home}
              away={meta.away}
              colors={pal}
              rows={stat.payload.teams}
            />
          )}
        </AnimatePresence>
        <AnimatePresence>
          {pc && passer && receiver && (
            <PassCard
              key={passCard!.overlay_id}
              pass={pc as never}
              passer={passer}
              receiver={receiver}
              colors={pal[pc.team_id]}
              position={passCardPosition(pc as never, camera, SCOREBUG_ZONE)}
            />
          )}
        </AnimatePresence>
        <MomentumRibbon points={ribbon} home={meta.home} away={meta.away} colors={pal} endMs={meta.period_end_ms[1]} />
        <AnimatePresence>
          {cardProps && <MomentCard key={card!.source_moment_id ?? card!.overlay_id} {...cardProps} />}
        </AnimatePresence>
        <AnimatePresence>{caption && <Caption key={caption.overlay_id} text={caption.payload.text} />}</AnimatePresence>
      </Stage>
    </MotionConfig>
  )
}
