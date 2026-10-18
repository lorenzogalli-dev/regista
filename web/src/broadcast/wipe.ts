// Broadcast entrances: graphics wipe in along their slant, hold, then wipe out (never a bare
// fade). The animated element carries the slant itself (motion composes skewX with x), so the
// clip edge follows the skew. Panels skew around their bottom-left corner (see broadcast.css),
// and the slide never moves the left edge outward, so title-safe holds during the wipe too.

import type { MotionProps } from 'motion/react'

export const SKEW_DEG = -5

export const EASE_OUT = [0.16, 1, 0.3, 1] as const

export function wipe(delay = 0): Pick<MotionProps, 'initial' | 'animate' | 'exit' | 'transition'> {
  return {
    initial: { clipPath: 'inset(0 100% 0 0)', x: 20, skewX: SKEW_DEG },
    animate: {
      clipPath: 'inset(0 0% 0 0)',
      x: 0,
      skewX: SKEW_DEG,
      transition: { duration: 0.36, delay, ease: EASE_OUT },
    },
    exit: {
      clipPath: 'inset(0 0 0 100%)',
      x: 20,
      skewX: SKEW_DEG,
      transition: { duration: 0.26, ease: [0.7, 0, 0.84, 0] },
    },
  }
}
