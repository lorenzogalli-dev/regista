import { motion } from 'motion/react'

import './architecture.css'

// Architecture on Azure (for the README and the demo video).

type Box = { id: string; x: number; y: number; w: number; h: number; title: string; sub: string; kind: 'code' | 'agent' | 'azure' | 'data' }

const BOXES: Box[] = [
  { id: 'sim', x: 40, y: 140, w: 220, h: 90, title: 'Match simulator', sub: 'synthetic events + 10 Hz tracking; hidden storylines kept apart', kind: 'data' },
  { id: 'metrics', x: 320, y: 140, w: 240, h: 90, title: 'Metrics engine', sub: 'live store, xG / xT / pass difficulty; code, not agents', kind: 'code' },
  { id: 'mcp', x: 320, y: 270, w: 240, h: 70, title: 'MCP server', sub: '6 typed tools; the only way to numbers', kind: 'code' },
  { id: 'cand', x: 620, y: 40, w: 200, h: 70, title: 'Candidates', sub: '2-signal rule vs noise', kind: 'code' },
  { id: 'workflow', x: 620, y: 140, w: 560, h: 200, title: 'Agent Framework workflow', sub: '', kind: 'agent' },
  { id: 'overlay', x: 1240, y: 140, w: 220, h: 90, title: 'Overlay timeline', sub: 'tier 0 from code at once; tier 1 template → verified text', kind: 'code' },
  { id: 'web', x: 1240, y: 270, w: 220, h: 70, title: 'Broadcast front-end', sub: 'React · WebSocket · /graphics for OBS', kind: 'code' },
]
const AGENTS = ['Detector', 'Analyst', 'Verifier', 'Narrator', 'Persona ×9', 'Director']
const AZURE = [
  ['Azure Container Apps', 'API + front-end, one container'],
  ['Microsoft Foundry', 'gpt-5.4-mini · gpt-5-mini'],
  ['Azure Database for PostgreSQL', 'runs and moments'],
  ['Azure Blob Storage', 'demo matches, recorded runs (read-only)'],
  ['Application Insights', 'OpenTelemetry traces per moment'],
  ['GitHub Actions + GHCR', 'CI, image after green CI'],
]

export function Architecture() {
  return (
    <main className="arch">
      <p className="eyebrow">Ground Truth Football · architecture</p>
      <h1>Numbers from tools, words from models</h1>
      <svg viewBox="0 0 1500 380" className="arch-svg" role="img" aria-label="architecture">
        <defs>
          <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0 0 L10 5 L0 10z" fill="#9fb0a7" />
          </marker>
        </defs>
        {[
          [260, 185, 320, 185],
          [440, 230, 440, 270],
          [560, 185, 620, 75],
          [720, 110, 720, 140],
          [560, 305, 620, 300],
          [1180, 185, 1240, 185],
          [1350, 230, 1350, 270],
        ].map(([x1, y1, x2, y2], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#9fb0a7" strokeWidth="2" markerEnd="url(#a)" />
        ))}
        {BOXES.map((b, i) => (
          <motion.g key={b.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 * i }}>
            <rect x={b.x} y={b.y} width={b.w} height={b.h} className={`box ${b.kind}`} />
            <text x={b.x + 14} y={b.y + 28} className="box-title">
              {b.title}
            </text>
            <foreignObject x={b.x + 14} y={b.y + 36} width={b.w - 28} height={b.h - 40}>
              <p className="box-sub">{b.sub}</p>
            </foreignObject>
          </motion.g>
        ))}
        {AGENTS.map((a, i) => {
          const x = 640 + (i % 3) * 180
          const y = 185 + Math.floor(i / 3) * 70
          return (
            <motion.g key={a} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 + 0.1 * i }}>
              <rect x={x} y={y} width={160} height={52} className={`agent ${a === 'Verifier' ? 'hybrid' : ''}`} />
              <text x={x + 80} y={y + 32} className="agent-label">
                {a}
              </text>
            </motion.g>
          )
        })}
        <text x="900" y="176" className="hint">
          Verifier: code recomputes every number, a model checks the wording; one retry
        </text>
      </svg>
      <section className="azure">
        {AZURE.map(([t, s], i) => (
          <motion.div key={t} className="az" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.4 + 0.08 * i }}>
            <b>{t}</b>
            <span>{s}</span>
          </motion.div>
        ))}
      </section>
    </main>
  )
}
