import { motion } from 'motion/react'

import type { TeamColors } from '../lib/color.ts'
import type { TeamInfo } from '../lib/sample.ts'
import { wipe } from './wipe.ts'

type Side = { team: TeamInfo; colors: TeamColors; score: number }

/** Top-left, always on: team shorts, score, clock and a possession dot (tier 0). */
export function Scorebug({
  home,
  away,
  clock,
  possession,
}: {
  home: Side
  away: Side
  clock: string
  possession: string | null
}) {
  return (
    <div className="scorebug-anchor">
      <motion.div className="scorebug glass" {...wipe()} data-testid="scorebug">
        {[home, away].map((s, i) => (
          <div className={`scorebug-team ${i ? 'away' : 'home'}`} key={s.team.team_id}>
            <span className="scorebug-kit" style={{ background: s.colors.fill }} />
            <span className="scorebug-short unskew">{s.team.short}</span>
            <span
              className="scorebug-dot"
              style={{
                background: s.colors.line,
                opacity: possession === s.team.team_id ? 1 : 0,
                transform: `scale(${possession === s.team.team_id ? 1 : 0.4})`,
              }}
              aria-label={possession === s.team.team_id ? 'in possession' : undefined}
            />
            <span className="scorebug-score num unskew">{s.score}</span>
          </div>
        ))}
        <div className="scorebug-clock num unskew">{clock}</div>
      </motion.div>
    </div>
  )
}
