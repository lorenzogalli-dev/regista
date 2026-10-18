// Display names for metrics and mechanisms, and evidence items as the graphics show them.

import { matchClock } from '../lib/sample.ts'
import type { MatchMeta } from '../lib/stream.ts'
import type { Evidence } from './MomentCard.tsx'

export const SHARE = new Set(['possession_time_based', 'field_tilt', 'pass_completion'])
export const LABELS: Record<string, string> = {
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
export const KICKER: Record<string, string> = {
  pressing_spell: 'Pressing',
  momentum_shift: 'Momentum',
  tactical_switch: 'Tactics',
  player_arc: 'Player',
}

export function evidenceItems(items: any[] = [], meta?: MatchMeta | null): Evidence[] {
  const minute = (ms: number) => (meta ? `${matchClock(ms, meta.period_end_ms).split(':')[0].replace(/^0/, '')}'` : '')
  const who = (id: string) =>
    meta
      ? id === meta.home.team_id
        ? meta.home.name
        : id === meta.away.team_id
          ? meta.away.name
          : (meta.players.find((p) => p.player_id === id)?.name ?? id)
      : id
  return items.map((e) => ({
    label: LABELS[e.metric] ?? e.metric,
    before: e.before,
    after: e.after,
    unit: SHARE.has(e.metric) ? 'pct' : 'num',
    scope:
      e.after_start_ms != null
        ? `${who(e.subject)} · ${minute(e.after_start_ms)}–${minute(e.after_end_ms)} vs ${minute(e.before_start_ms)}–${minute(e.before_end_ms)}`
        : undefined,
  }))
}


export function fmt(v: number, unit: Evidence['unit']) {
  return unit === 'pct' ? `${Math.round(v * 100)}%` : v.toFixed(v >= 10 || Number.isInteger(v) ? 0 : 1)
}

export const PERSONAS = [
  ['analyst_en', 'Analyst · English'],
  ['casual_en', 'Casual fan · English'],
  ['player_focus_en', 'Favourite player · English'],
  ['analyst_it', 'Analyst · Italiano'],
  ['casual_it', 'Casual fan · Italiano'],
  ['player_focus_it', 'Favourite player · Italiano'],
  ['analyst_es', 'Analyst · Español'],
  ['casual_es', 'Casual fan · Español'],
  ['player_focus_es', 'Favourite player · Español'],
] as const
