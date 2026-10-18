import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'

import { CountUp } from './CountUp.tsx'
import { fmt } from './labels.ts'
import { EASE_OUT, wipe } from './wipe.ts'

export type Evidence = {
  label: string
  before: number
  after: number
  unit: 'pct' | 'num'
  /** Who the number is about and over which windows, e.g. "Linbridge · 19'–34' vs 4'–19'". */
  scope?: string
}

/** "✓ 3/3": how many evidence items the Verifier passed. Stamps in after the text; pressing it
 * opens the evidence. */
export function VerifiedSeal({
  passed,
  total,
  delay = 0,
  onClick,
  open = false,
}: {
  passed: number
  total: number
  delay?: number
  onClick?: () => void
  open?: boolean
}) {
  return (
    <motion.button
      type="button"
      className={`seal ${open ? 'open' : ''}`}
      initial={{ scale: 1.8, opacity: 0, skewX: -5 }}
      animate={{ scale: 1, opacity: 1, skewX: -5 }}
      transition={{ delay, type: 'spring', stiffness: 520, damping: 22 }}
      aria-label={`verified: ${passed} of ${total} evidence items. Show the evidence`}
      aria-expanded={open}
      onClick={onClick}
    >
      <span className="seal-tick">✓</span>
      <span className="num">
        {passed}/{total}
      </span>
      <span className="seal-word">verified</span>
    </motion.button>
  )
}


/** Before → after as two bars per metric, scaled to the larger value. */
export function EvidenceBars({ items, animate = true }: { items: Evidence[]; animate?: boolean }) {
  return (
    <div className="ev-bars">
      {items.map((e, i) => {
        const max = Math.max(Math.abs(e.before), Math.abs(e.after), 1e-9)
        const up = e.after >= e.before
        return (
          <div className="ev-row" key={e.label + i}>
            <div className="ev-head">
              <span className="ev-label">{e.label}</span>
              {e.scope && <span className="ev-scope">{e.scope}</span>}
            </div>
            {(['before', 'after'] as const).map((k, j) => (
              <div className={`ev-bar ${k}`} key={k}>
                <span className="ev-key">{k === 'before' ? 'Before' : 'After'}</span>
                <span className="ev-track">
                  <motion.i
                    initial={animate ? { scaleX: 0 } : false}
                    animate={{ scaleX: Math.abs(e[k]) / max }}
                    transition={{ delay: 0.1 + i * 0.12 + j * 0.08, duration: 0.55, ease: EASE_OUT }}
                  />
                </span>
                <span className="ev-num num">
                  {fmt(e[k], e.unit)}
                  {k === 'after' && <b className={up ? 'up' : 'down'}>{up ? '▲' : '▼'}</b>}
                </span>
              </div>
            ))}
          </div>
        )
      })}
      <p className="ev-foot">
        <span className="seal-tick">✓</span> Recomputed independently by code from the match data before it went on air.
      </p>
    </div>
  )
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
  evidenceAll,
  sample,
  state = 'verified',
  openEvidence,
}: {
  kicker: string
  headline: string
  body: string
  evidence: Evidence[]
  evidenceAll?: Evidence[]
  sample?: string
  state?: 'pending' | 'verified'
  /** Force the evidence panel open (guided tour); otherwise the seal toggles it. */
  openEvidence?: boolean
}) {
  const pending = state === 'pending'
  const [open, setOpen] = useState(false)
  const showEvidence = !pending && (openEvidence ?? open)
  const all = evidenceAll ?? evidence
  return (
    <div className="moment-anchor" data-testid="moment-card" data-state={state}>
      <AnimatePresence>
        {showEvidence && (
          <motion.div
            className="evidence-panel glass-strong"
            data-testid="evidence-panel"
            initial={{ opacity: 0, y: 16, skewX: -5 }}
            animate={{ opacity: 1, y: 0, skewX: -5 }}
            exit={{ opacity: 0, y: 10, skewX: -5 }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
          >
            <div className="unskew-block">
              <p className="ev-title">
                <span className="seal-tick">✓</span> {all.length}/{all.length} evidence items checked
              </p>
              <EvidenceBars items={all} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
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
              <VerifiedSeal
                passed={all.length}
                total={all.length}
                delay={0.5}
                open={showEvidence}
                onClick={() => setOpen((o) => !o)}
              />
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
