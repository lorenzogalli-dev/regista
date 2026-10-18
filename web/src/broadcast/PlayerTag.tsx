import { motion } from 'motion/react'
import { useRef } from 'react'

import type { TeamColors } from '../lib/color.ts'
import { useClockFrame, type Clock } from '../lib/clock.ts'
import { STAGE, anchorAt, type Camera } from '../lib/projection.ts'
import { positionsAt, type Frame, type PlayerInfo } from '../lib/sample.ts'
import { surname } from './layout.ts'
import { wipe } from './wipe.ts'

/** Name + number that follows a player at 60 fps (positions interpolated between 10 Hz frames).
 * Sits above the player, or below when that would collide with a panel graphic on screen. */
const TAG_H = 34
const PANELS = '.scorebug, .pass-card, .moment'

export function PlayerTag({
  player,
  colors,
  frames,
  clock,
  camera,
}: {
  player: PlayerInfo
  colors: TeamColors
  frames: Frame[]
  clock: Clock
  camera: Camera
}) {
  const ref = useRef<HTMLDivElement>(null)
  useClockFrame(clock, (t) => {
    const p = positionsAt(frames, t).players.get(player.player_id)
    if (!p || !ref.current) return
    const { left, top } = anchorAt(camera, p)
    const r = 1.3 * camera.scaleAt(p)
    const stage = ref.current.parentElement!.getBoundingClientRect()
    const k = stage.width / STAGE.width
    const w = (ref.current.firstElementChild?.getBoundingClientRect().width ?? 160) / k
    const above = top - 2 * r - 14
    const box = { left: left - w / 2, right: left + w / 2, top: above - TAG_H, bottom: above }
    const clash = [...document.querySelectorAll(PANELS)].some((el) => {
      const b = el.getBoundingClientRect()
      const a = {
        left: (b.left - stage.left) / k,
        right: (b.right - stage.left) / k,
        top: (b.top - stage.top) / k,
        bottom: (b.bottom - stage.top) / k,
      }
      return box.left < a.right && a.left < box.right && box.top < a.bottom && a.top < box.bottom
    })
    const y = clash ? top + r + TAG_H + 10 : above
    ref.current.style.transform = `translate(${left}px, ${y}px)`
  })
  return (
    <div ref={ref} className="tag-anchor" data-testid={`tag-${player.player_id}`}>
      <div className="tag-center">
        <motion.div className="tag" {...wipe()}>
          <span className="tag-shirt num" style={{ background: colors.fill, color: colors.ink }}>
            <span className="unskew">{player.shirt}</span>
          </span>
          <span className="tag-name unskew">{surname(player.name)}</span>
        </motion.div>
      </div>
    </div>
  )
}
