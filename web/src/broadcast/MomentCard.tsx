import { AnimatePresence, motion } from 'motion/react'

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
  return unit === 'pct' ? `${Math.round(v * 100)}%` : v.toFixed(v >= 10 || Number.isInteger(v) ? 0 : 1)
}

/** Text that morphs in place when it changes (template → model text): old and new share one
 * grid cell and cross-fade, so nothing around the card jumps. */
function Morph({ text, className, as = 'p' }: { text: string; className: string; as?: 'p' | 'h2' }) {
  const Tag = as === 'h2' ? motion.h2 : motion.p
  return (
    <div className="morph">
      <AnimatePresence initial={false}>
        <Tag
          key={text}
          className={className}
          initial={{ opacity: 0, y: 8, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -6, filter: 'blur(4px)' }}
          transition={{ duration: 0.45, ease: EASE_OUT }}
        >
          {text}
        </Tag>
      </AnimatePresence>
    </div>
  )
}

/**
 * Tier-1 AI insight. `pending`: the Director's deterministic template (numbers from code), amber,
 * while the agents work. `verified`: the model text, cyan, with the verified seal. The card
 * stays mounted across the change so the text morphs in place.
 */
export function MomentCard({
  kicker,
  headline,
  body,
  evidence,
  sample,
  state = 'verified',
}: {
  kicker: string
  headline: string
  body: string
  evidence: Evidence[]
  sample?: string
  state?: 'pending' | 'verified'
}) {
  const pending = state === 'pending'
  return (
    <div className="moment-anchor" data-testid="moment-card" data-state={state}>
      <motion.div className={`moment glass-strong ${pending ? 'pending' : ''}`} {...wipe()}>
        <span className="moment-edge" />
        <div className="moment-inner unskew">
          <div className="moment-top">
            <span className="ai-label">{pending ? 'AI insight · verifying' : 'AI insight'}</span>
            <span className="moment-kicker">{kicker}</span>
            {pending ? (
              <span className="pending-dots" aria-label="waiting for verified model text">
                <i />
                <i />
                <i />
              </span>
            ) : (
              <VerifiedSeal passed={evidence.length} total={evidence.length} delay={0.5} />
            )}
          </div>
          <Morph as="h2" className="moment-headline" text={headline} />
          <Morph className="moment-body" text={body} />
          {evidence.length > 0 && (
            <div className="evidence">
              {evidence.slice(0, 3).map((e, i) => (
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
          )}
          {sample && <div className="sample-tag">{sample}</div>}
        </div>
      </motion.div>
    </div>
  )
}
