// Design audit for the broadcast frame (`?audit=1`): checks the rendered DOM against DESIGN.md
// (title-safe, no overlap with the scorebug, text contrast, tabular figures, consistent skew)
// and writes the result as JSON into <pre id="audit">, readable with `chrome --dump-dom`.

import { PANEL, contrast } from '../lib/color.ts'
import { SAFE, STAGE } from '../lib/projection.ts'

const GRAPHICS = [
  '.scorebug',
  '.pass-card',
  '.moment',
  '.tag',
  '.seal',
  '.badge',
  '.stat-compare',
  '.ribbon',
  '.caption',
  '.source',
]
const SKEW_TAN = Math.tan((-5 * Math.PI) / 180)

type Rect = { left: number; top: number; right: number; bottom: number }

function stageRect(el: Element, stage: DOMRect, scale: number): Rect {
  const r = el.getBoundingClientRect()
  return {
    left: (r.left - stage.left) / scale,
    top: (r.top - stage.top) / scale,
    right: (r.right - stage.left) / scale,
    bottom: (r.bottom - stage.top) / scale,
  }
}

function overlaps(a: Rect, b: Rect): boolean {
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom
}

function rgbToHex(css: string): string | null {
  const m = css.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/)
  if (!m || (m[4] !== undefined && Number(m[4]) < 0.5)) return null
  return '#' + [m[1], m[2], m[3]].map((v) => Math.round(Number(v)).toString(16).padStart(2, '0')).join('')
}

function skewOf(el: Element): number | null {
  const t = getComputedStyle(el).transform
  if (!t || t === 'none') return null
  const m = new DOMMatrixReadOnly(t)
  return m.c
}

export function runAudit(): Record<string, unknown> {
  const stageEl = document.querySelector('[data-testid="stage"]')!
  const stage = stageEl.getBoundingClientRect()
  const scale = stage.width / STAGE.width
  const problems: string[] = []
  const bug = document.querySelector('.scorebug')
  const bugRect = bug ? stageRect(bug, stage, scale) : null
  const seen: Record<string, Rect> = {}

  for (const sel of GRAPHICS) {
    document.querySelectorAll(sel).forEach((el, i) => {
      if (getComputedStyle(el).visibility === 'hidden') return
      const r = stageRect(el, stage, scale)
      seen[`${sel}#${i}`] = r
      if (
        r.left < SAFE.left - 0.5 ||
        r.top < SAFE.top - 0.5 ||
        r.right > SAFE.right + 0.5 ||
        r.bottom > SAFE.bottom + 0.5
      ) {
        problems.push(`${sel}#${i} leaves title-safe: ${JSON.stringify(r)}`)
      }
      if (sel !== '.scorebug' && bugRect && overlaps(r, bugRect)) problems.push(`${sel}#${i} overlaps the scorebug`)
      const k = skewOf(el)
      if (k === null || Math.abs(k - SKEW_TAN) > 1e-3)
        problems.push(`${sel}#${i} skew ${k} (want ${SKEW_TAN.toFixed(4)})`)
    })
  }

  // Graphics must not overlap each other (the seal sits inside the moment card).
  const keys = Object.keys(seen).filter((k) => !k.startsWith('.seal'))
  keys.forEach((a, i) =>
    keys.slice(i + 1).forEach((b) => {
      if (overlaps(seen[a], seen[b])) problems.push(`${a} overlaps ${b}`)
    }),
  )

  // Text contrast: every text element over its nearest opaque background (panels are dark glass,
  // approximated by the panel colour when transparent).
  let checked = 0
  document.querySelectorAll('.stage *').forEach((el) => {
    if (!(el instanceof HTMLElement) || !el.childNodes.length) return
    const hasText = [...el.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && n.textContent?.trim())
    if (!hasText) return
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || Number(cs.opacity) === 0) return
    const fg = rgbToHex(cs.color)
    let bg: string | null = null
    for (let p: HTMLElement | null = el; p && !bg; p = p.parentElement)
      bg = rgbToHex(getComputedStyle(p).backgroundColor)
    if (!fg) return
    const c = contrast(fg, bg ?? PANEL)
    checked++
    if (c < 4.5)
      problems.push(`contrast ${c.toFixed(2)} for "${el.textContent?.trim().slice(0, 30)}" (${fg} on ${bg ?? PANEL})`)
    if (/\d/.test(el.textContent ?? '') && !cs.fontVariantNumeric.includes('tabular-nums')) {
      problems.push(`proportional figures in "${el.textContent?.trim().slice(0, 30)}"`)
    }
  })

  return {
    viewport: [window.innerWidth, window.innerHeight],
    scale,
    graphics: seen,
    textChecked: checked,
    problems,
  }
}
