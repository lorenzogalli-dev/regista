// Match-time clock driven by requestAnimationFrame. Per-frame consumers (canvas, player tags)
// subscribe and update imperatively; React state only follows coarse ticks.

import { useEffect, useRef, useState } from 'react'

export type Clock = {
  now(): number
  subscribe(fn: (t: number) => void): () => void
}

export type ClockOptions = { start: number; end: number; speed?: number; freezeAt?: number | null; loop?: boolean }

export function createClock({ start, end, speed = 1, freezeAt = null, loop = true }: ClockOptions): Clock & {
  start(): void
  stop(): void
} {
  const subs = new Set<(t: number) => void>()
  let t0 = 0
  let t = freezeAt ?? start
  let raf = 0
  const step = (now: number) => {
    if (freezeAt == null) {
      const span = end - start
      const el = (now - t0) * speed
      t = loop ? start + (el % span) : Math.min(end, start + el)
    }
    subs.forEach((fn) => fn(t))
    raf = requestAnimationFrame(step)
  }
  return {
    now: () => t,
    subscribe(fn) {
      subs.add(fn)
      fn(t)
      return () => subs.delete(fn)
    },
    start() {
      cancelAnimationFrame(raf)
      t0 = performance.now()
      raf = requestAnimationFrame(step)
    },
    stop: () => cancelAnimationFrame(raf),
  }
}

/** Run `fn` on every animation frame with the current match time. */
export function useClockFrame(clock: Clock | null, fn: (t: number) => void): void {
  const ref = useRef(fn)
  useEffect(() => {
    ref.current = fn
  })
  useEffect(() => clock?.subscribe((t) => ref.current(t)), [clock])
}

/** Match time quantised to `stepMs`, as React state (for showing/hiding graphics). */
export function useClockTick(clock: Clock | null, stepMs = 100): number {
  const quantise = (t: number) => Math.floor(t / stepMs) * stepMs
  const [q, setQ] = useState(() => (clock ? quantise(clock.now()) : 0))
  useClockFrame(clock, (t) => setQ(quantise(t)))
  return q
}
