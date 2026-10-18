import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'

import { KICKER, evidenceItems } from '../broadcast/labels.ts'
import { EvidenceBars } from '../broadcast/MomentCard.tsx'
import type { Marker, RunData } from '../lib/player.ts'
import { matchClock } from '../lib/sample.ts'
import type { MatchMeta, Overlay } from '../lib/stream.ts'

// Insights feed: every AI card that has gone on air stays here, readable, with its evidence
// and a way back to the moment. Newest first.

function Item({
  card,
  template,
  persona,
  meta,
  onSeek,
}: {
  card: Overlay
  template: Overlay | undefined
  persona: string
  meta: MatchMeta
  onSeek: (ms: number) => void
}) {
  const [open, setOpen] = useState(false)
  const p = card.payload
  const text = p.texts?.[persona] ?? p.texts?.analyst_en ?? { headline: p.mechanism_tag, text: p.claim }
  const ev = evidenceItems(p.evidence, meta)
  return (
    <motion.article
      className="ins-item"
      layout
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35 }}
    >
      <header className="ins-head">
        <span className="ins-time num">{matchClock(card.show_at_ms, meta.period_end_ms)}</span>
        <span className="ins-kicker">{KICKER[p.mechanism_tag] ?? 'Insight'}</span>
        <button type="button" className={`ins-seal ${open ? 'open' : ''}`} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          ✓ <span className="num">{ev.length}/{ev.length}</span> verified
        </button>
      </header>
      <h3>{text.headline}</h3>
      <p>{text.text}</p>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            className="ins-evidence"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <EvidenceBars items={ev} />
          </motion.div>
        )}
      </AnimatePresence>
      <button type="button" className="ins-again" onClick={() => onSeek((template?.show_at_ms ?? card.show_at_ms) - 4_000)}>
        ↺ Watch this moment again
      </button>
    </motion.article>
  )
}

export function InsightsFeed({
  run,
  t,
  persona,
  meta,
  markers,
  onSeek,
}: {
  run: RunData | null
  t: number
  persona: string
  meta: MatchMeta | null
  markers: Marker[]
  onSeek: (ms: number) => void
}) {
  if (!run || !meta) return <aside className="insights" />
  const byId = new Map(run.overlays.map((o) => [o.overlay_id, o]))
  const cards = run.overlays
    .filter((o) => o.kind === 'moment_card' && o.payload.state === 'verified' && o.show_at_ms <= t)
    .sort((a, b) => b.show_at_ms - a.show_at_ms)
  const verifying = run.overlays.find(
    (o) =>
      o.kind === 'moment_card' &&
      o.payload.state === 'pending' &&
      o.show_at_ms <= t &&
      !run.overlays.some((v) => v.payload.replaces === o.overlay_id && v.show_at_ms <= t) &&
      t < o.show_at_ms + o.duration_ms,
  )
  const nextInsight = markers.find((m) => m.kind === 'insight' && m.t > t)
  return (
    <aside className="insights" data-testid="insights" aria-label="AI insights so far">
      <h2>
        Insights <span className="num">{cards.length}</span>
      </h2>
      <p className="ins-sub">Every AI explanation that went on air, checked against the data first.</p>
      {verifying && (
        <div className="ins-pending">
          <span className="pending-dots">
            <i />
            <i />
            <i />
          </span>
          Agents are checking: “{verifying.payload.headline}”
        </div>
      )}
      <div className="ins-list">
        <AnimatePresence initial={false}>
          {cards.map((c) => (
            <Item
              key={c.overlay_id}
              card={c}
              template={byId.get(c.payload.replaces)}
              persona={persona}
              meta={meta}
              onSeek={onSeek}
            />
          ))}
        </AnimatePresence>
        {!cards.length && (
          <p className="ins-empty">
            No AI insight yet. They collect here as they go on air.
            {nextInsight && (
              <button type="button" onClick={() => onSeek(nextInsight.seekTo)}>
                Jump to the first one ({matchClock(nextInsight.t, meta.period_end_ms)}) →
              </button>
            )}
          </p>
        )}
      </div>
    </aside>
  )
}
