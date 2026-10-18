// Colour utilities: WCAG contrast and team palettes that stay readable for any pair of team
// colours (DESIGN.md §2: contrast ≥ 4.5:1 for text over team colours, AI cyan reserved).

export const BG = '#06110c'
export const PANEL = '#0c1b14'
export const INK_DARK = '#06110c'
export const INK_LIGHT = '#f2f5f3'
export const AI_ACCENT = '#46e5d8'

export const TEXT_CONTRAST = 4.5
export const MARK_CONTRAST = 3 // non-text graphics on the dark background (WCAG 1.4.11)
export const MIN_TEAM_DELTA_E = 30 // home vs away must be clearly different
export const MIN_AI_DELTA_E = 25 // no team colour may look like the AI accent

type RGB = [number, number, number]

export function hexToRgb(hex: string): RGB {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? [...h].map((c) => c + c).join('') : h
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16)) as RGB
}

export function rgbToHex([r, g, b]: RGB): string {
  return (
    '#' +
    [r, g, b]
      .map((v) =>
        Math.round(Math.min(255, Math.max(0, v)))
          .toString(16)
          .padStart(2, '0'),
      )
      .join('')
  )
}

function lin(c: number): number {
  const s = c / 255
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}

export function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map(lin)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

export function mix(hex: string, target: string, t: number): string {
  const a = hexToRgb(hex)
  const b = hexToRgb(target)
  return rgbToHex(a.map((v, i) => v + (b[i] - v) * t) as RGB)
}

function toLab(hex: string): [number, number, number] {
  const [r, g, b] = hexToRgb(hex).map(lin)
  const x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
  const y = 0.2126 * r + 0.7152 * g + 0.0722 * b
  const z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
  const f = (t: number) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116)
  return [116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))]
}

/** CIE76 colour difference (≈ 2.3 is just noticeable; > 30 clearly different). */
export function deltaE(a: string, b: string): number {
  const la = toLab(a)
  const lb = toLab(b)
  return Math.hypot(la[0] - lb[0], la[1] - lb[1], la[2] - lb[2])
}

/** The ink (dark or light) with the higher contrast on `fill`. */
export function inkOn(fill: string): string {
  return contrast(fill, INK_DARK) >= contrast(fill, INK_LIGHT) ? INK_DARK : INK_LIGHT
}

/** Nudge `fill` toward black or white until its best ink reaches `min` contrast. */
export function withReadableInk(fill: string, min = TEXT_CONTRAST): { fill: string; ink: string } {
  let f = fill
  for (let i = 0; i < 20 && contrast(f, inkOn(f)) < min; i++) {
    f = mix(f, inkOn(f) === INK_DARK ? '#ffffff' : '#000000', 0.08)
  }
  return { fill: f, ink: inkOn(f) }
}

/** Lighten `c` until it is visible on the dark background. */
function visibleOnBg(c: string): string {
  let f = c
  for (let i = 0; i < 20 && contrast(f, BG) < MARK_CONTRAST; i++) f = mix(f, '#ffffff', 0.08)
  return f
}

export type TeamColors = {
  /** Team colour for bars, chips and player discs. */
  fill: string
  /** Text colour on `fill`, contrast ≥ 4.5. */
  ink: string
  /** Team colour for lines and marks on the dark background, contrast ≥ 3. */
  line: string
}

function candidates(colors: string[]): string[] {
  return colors.length ? colors : ['#bbbbbb']
}

function pick(colors: string[], avoid: string[]): string {
  // First colour that is visible on the dark background and far from the colours to avoid;
  // otherwise the best-scoring one after lightening.
  const scored = candidates(colors).map((c) => {
    const v = visibleOnBg(c)
    const sep = Math.min(deltaE(v, AI_ACCENT) / MIN_AI_DELTA_E, ...avoid.map((a) => deltaE(v, a) / MIN_TEAM_DELTA_E))
    return { v, ok: sep >= 1 && v === c, sep }
  })
  const ok = scored.find((s) => s.ok)
  if (ok) return ok.v
  return scored.reduce((a, b) => (b.sep > a.sep ? b : a)).v
}

function separate(c: string, avoid: string): string {
  // Last resort when both of a team's colours clash: move lightness away from the other team.
  if (deltaE(c, avoid) >= MIN_TEAM_DELTA_E && deltaE(c, AI_ACCENT) >= MIN_AI_DELTA_E) return c
  const target = luminance(avoid) > 0.3 ? '#000000' : '#ffffff'
  let f = c
  for (let i = 0; i < 20 && (deltaE(f, avoid) < MIN_TEAM_DELTA_E || deltaE(f, AI_ACCENT) < MIN_AI_DELTA_E); i++) {
    f = mix(f, target, 0.08)
  }
  return f
}

function teamColors(base: string): TeamColors {
  const { fill, ink } = withReadableInk(base)
  return { fill, ink, line: visibleOnBg(base) }
}

/** Palettes for both teams from their kit colours (`match.json` `colors`, primary first). */
export function teamPalette(home: string[], away: string[]): { home: TeamColors; away: TeamColors } {
  const h = separate(pick(home, []), AI_ACCENT)
  const a = separate(pick(away, [h]), h)
  return { home: teamColors(h), away: teamColors(a) }
}
