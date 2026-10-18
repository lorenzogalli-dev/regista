import { motion } from 'motion/react'

import type { TeamColors } from '../lib/color.ts'
import type { Camera } from '../lib/projection.ts'
import type { PassCardData, PlayerInfo } from '../lib/sample.ts'
import { CountUp } from './CountUp.tsx'
import { PASS_CARD_SIZE, surname } from './layout.ts'
import { wipe } from './wipe.ts'

const SEGMENTS = 10

/** Animated trail from passer to receiver; glow intensity follows pass difficulty (tier 0). */
export function PassTrail({
  pass,
  camera,
  color,
  flightS,
}: {
  pass: PassCardData
  camera: Camera
  color: string
  flightS: number
}) {
  const a = camera.project({ x: pass.x, y: pass.y })
  const b = camera.project({ x: pass.end_x, y: pass.end_y })
  const glow = 4 + 18 * pass.pass_difficulty
  return (
    <svg className="overlay-svg" width="1920" height="1080" viewBox="0 0 1920 1080" aria-hidden>
      <defs>
        <filter id="trail-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation={glow / 2} />
        </filter>
      </defs>
      <motion.line
        x1={a.x}
        y1={a.y}
        x2={b.x}
        y2={b.y}
        stroke={color}
        strokeWidth={10}
        strokeLinecap="round"
        filter="url(#trail-glow)"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 0.35 + 0.6 * pass.pass_difficulty }}
        exit={{ opacity: 0 }}
        transition={{ duration: flightS, ease: 'linear' }}
      />
      <motion.line
        x1={a.x}
        y1={a.y}
        x2={b.x}
        y2={b.y}
        stroke="#f2f5f3"
        strokeWidth={3}
        strokeLinecap="round"
        strokeDasharray="0 1"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: flightS, ease: 'linear' }}
      />
      <circle cx={a.x} cy={a.y} r={5} fill="#f2f5f3" />
      <motion.circle
        cx={b.x}
        cy={b.y}
        r={7}
        fill="none"
        stroke={color}
        strokeWidth={3}
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: flightS, duration: 0.3 }}
      />
    </svg>
  )
}

export function PassCard({
  pass,
  passer,
  receiver,
  colors,
  position,
}: {
  pass: PassCardData
  passer: PlayerInfo
  receiver: PlayerInfo
  colors: TeamColors
  position: { left: number; top: number }
}) {
  const difficulty = Math.round(pass.pass_difficulty * 100)
  const filled = Math.round((difficulty / 100) * SEGMENTS)
  return (
    <div className="pass-card-anchor" style={{ ...position, width: PASS_CARD_SIZE.width }} data-testid="pass-card">
      <motion.div className="pass-card glass" {...wipe()}>
        <div className="pass-card-head">
          <span className="tier0-label unskew">Pass</span>
          <span className="pass-card-players unskew">
            <span className="shirt" style={{ background: colors.fill, color: colors.ink }}>
              {passer.shirt}
            </span>
            {surname(passer.name)}
            <span className="arrow">→</span>
            <span className="shirt" style={{ background: colors.fill, color: colors.ink }}>
              {receiver.shirt}
            </span>
            {surname(receiver.name)}
          </span>
        </div>
        <div className="pass-card-stats unskew">
          <Stat label="Length">
            <CountUp value={pass.pass_length_m} decimals={1} delay={0.15} />
            <small>m</small>
          </Stat>
          <Stat label="Progression">
            +<CountUp value={pass.pass_progression_m} decimals={1} delay={0.2} />
            <small>m</small>
          </Stat>
          <Stat label="Difficulty">
            <CountUp value={difficulty} delay={0.25} />
            <span className="meter" aria-hidden>
              {Array.from({ length: SEGMENTS }, (_, i) => (
                <motion.i
                  key={i}
                  initial={{ opacity: 0.12 }}
                  animate={{ opacity: i < filled ? 1 : 0.16 }}
                  transition={{ delay: 0.25 + i * 0.05, duration: 0.15 }}
                  style={{ background: i < filled ? colors.line : 'var(--text-2)' }}
                />
              ))}
            </span>
          </Stat>
        </div>
      </motion.div>
    </div>
  )
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value num">{children}</span>
    </div>
  )
}
