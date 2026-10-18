// Layout and timing rules for the broadcast frame (pure functions, unit-tested).

import { SAFE, type Camera } from '../lib/projection.ts'
import type { PassCardData, Sample } from '../lib/sample.ts'

// Card box, and its footprint including the slant overhang (height × tan 5° ≈ 12 px).
export const PASS_CARD_SIZE = { width: 432, height: 132 }
const PASS_CARD_FOOTPRINT = PASS_CARD_SIZE.width + 12

// Scorebug footprint (stage px) that no other graphic may overlap; checked in the design review.
export const SCOREBUG_ZONE = { right: 96 + 560, bottom: 54 + 58 }

type Timeline = {
  passerTag: [number, number]
  receiverTag: [number, number]
  trail: [number, number]
  passCard: [number, number]
  moment: [number, number]
  flightS: number
}

/** When each graphic is on air, derived from the clip's events. */
export function timeline(s: Sample): Timeline {
  const p = s.pass_card
  const recovery = s.events.find(
    (e) => e.player_id === p.player_id && e.t_ms <= p.t_ms && e.type !== 'carry' && e.type !== 'pass',
  )
  const shot = s.events.find((e) => e.type === 'shot' && e.t_ms > p.t_ms)
  const flightS = p.pass_length_m / ((p.ball_speed_ms ?? 18) * 0.85)
  const arrival = p.t_ms + flightS * 1000
  return {
    passerTag: [recovery?.t_ms ?? p.t_ms - 2500, p.t_ms + 800],
    receiverTag: [arrival - 200, (shot?.t_ms ?? s.clip.end_ms) + 1500],
    trail: [p.t_ms, p.t_ms + 6500],
    passCard: [p.t_ms + 300, p.t_ms + 6500],
    moment: [p.t_ms + 2600, s.clip.end_ms + 1],
    flightS,
  }
}

export const on = (t: number, [a, b]: [number, number]) => t >= a && t < b

/** Where the pass card sits: above the trail's midpoint, kept inside title-safe and clear of
 * the scorebug. */
export function passCardPosition(pass: PassCardData, camera: Camera, avoid: { right: number; bottom: number }) {
  const mid = camera.project({ x: (pass.x + pass.end_x) / 2, y: (pass.y + pass.end_y) / 2 })
  let left = mid.x - PASS_CARD_SIZE.width / 2
  let top = mid.y - PASS_CARD_SIZE.height - 70
  left = Math.min(Math.max(left, SAFE.left), SAFE.right - PASS_CARD_FOOTPRINT)
  top = Math.min(Math.max(top, SAFE.top), SAFE.bottom - PASS_CARD_SIZE.height)
  if (left < avoid.right && top < avoid.bottom) top = avoid.bottom + 16
  return { left, top }
}

export function surname(name: string): string {
  const parts = name.split(' ')
  return parts[parts.length - 1]
}
