import { animate, useReducedMotion } from 'motion/react'
import { useEffect, useRef } from 'react'

/** A number that counts up to `value` when it mounts (tabular figures, so nothing jitters). */
export function CountUp({
  value,
  decimals = 0,
  from = 0,
  duration = 0.7,
  delay = 0,
  format = (v: number) => v.toFixed(decimals),
}: {
  value: number
  decimals?: number
  from?: number
  duration?: number
  delay?: number
  format?: (v: number) => string
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const reduced = useReducedMotion()
  const fmt = useRef(format)
  useEffect(() => {
    fmt.current = format
  })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (reduced) {
      el.textContent = fmt.current(value)
      return
    }
    el.textContent = fmt.current(from)
    const c = animate(from, value, {
      duration,
      delay,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => {
        el.textContent = fmt.current(v)
      },
    })
    return () => c.stop()
  }, [value, from, duration, delay, reduced])
  return <span ref={ref} className="num" />
}
