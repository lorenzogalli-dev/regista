import { motion } from 'motion/react'

import { CountUp } from './CountUp.tsx'
import { EASE_OUT, wipe } from './wipe.ts'

export type Evidence = { label: string; before: number; after: number; unit: 'pct' | 'num' }

/** "✓ 3/3": how many evidence items the Verifier passed. Stamps in after the text. */
export function VerifiedSeal({ passed, total, delay = 0 }: { passed: number; total: number; delay?: number }) {
  return (
    <motion.span
      className="seal"
      initial={{ scale: 1.8, opacity: 0, skewX: -5 }}
      animate={{ scale: 1, opacity: 1, skewX: -5 }}
      transition={{ delay, type: 'spring', stiffness: 520, damping: 22 }}
      aria-label={`verified: ${passed} of ${total} evidence items`}
    >
      <span className="seal-tick">✓</span>
      <span className="num">
        {passed}/{total}
      </span>
      <span className="seal-word">verified</span>
    </motion.span>
  )
}

function fmt(v: number, unit: Evidence['unit']) {
  return unit === 'pct' ? `${Math.round(v * 100)}%` : v.toFixed(0)
}

/**
 * Tier-1 AI insight: headline + why it matters, the cyan accent and the verified seal. In D5a
 * the text is a hand-written design sample (labelled as such); numbers come from the tools.
 */
export function MomentCard({
  kicker,
  headline,
  body,
  evidence,
  sample,
}: {
  kicker: string
  headline: string
  body: string
  evidence: Evidence[]
  sample?: string
}) {
  return (
    <div className="moment-anchor" data-testid="moment-card">
      <motion.div className="moment glass-strong" {...wipe()}>
        <span className="moment-edge" />
        <div className="moment-inner unskew">
          <div className="moment-top">
            <span className="ai-label">AI insight</span>
            <span className="moment-kicker">{kicker}</span>
            <VerifiedSeal passed={evidence.length} total={evidence.length} delay={0.9} />
          </div>
          <motion.h2
            className="moment-headline"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.4, ease: EASE_OUT }}
          >
            {headline}
          </motion.h2>
          <motion.p
            className="moment-body"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35, duration: 0.4 }}
          >
            {body}
          </motion.p>
          <div className="evidence">
            {evidence.map((e, i) => (
              <div className="evidence-item" key={e.label}>
                <span className="evidence-label">{e.label}</span>
                <span className="evidence-value num">
                  <span className="before">{fmt(e.before, e.unit)}</span>
                  <span className="arrow">→</span>
                  <CountUp value={e.after} from={e.before} delay={0.45 + 0.1 * i} format={(v) => fmt(v, e.unit)} />
                </span>
              </div>
            ))}
          </div>
          {sample && <div className="sample-tag">{sample}</div>}
        </div>
      </motion.div>
    </div>
  )
}
