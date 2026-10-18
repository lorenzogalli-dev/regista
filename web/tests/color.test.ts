import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  AI_ACCENT,
  BG,
  MARK_CONTRAST,
  MIN_AI_DELTA_E,
  MIN_TEAM_DELTA_E,
  TEXT_CONTRAST,
  contrast,
  deltaE,
  teamPalette,
} from '../src/lib/color.ts'

// Kit pairs chosen to clash: near-identical primaries, colours invisible on the dark
// background, a team in the AI accent's cyan, and the sample match.
const CLASHES: [string, string[], string[]][] = [
  ['red vs dark red', ['#C8102E', '#FFFFFF'], ['#A50021', '#F4D03F']],
  ['black vs navy (both invisible on dark)', ['#1B1B1B', '#F2F5F3'], ['#0B1F4B', '#0B1F4B']],
  ['white vs light grey', ['#FFFFFF', '#000000'], ['#E6E6E6', '#C8102E']],
  ['gold vs yellow', ['#F2C230', '#1B1B1B'], ['#FFD500', '#FFD500']],
  ['cyan kit vs teal', ['#40E0D0', '#003B46'], ['#2BB3A3', '#2BB3A3']],
  ['sample m_1000', ['#F2C230', '#1B1B1B'], ['#E6E6E6', '#C8102E']],
]

for (const [name, home, away] of CLASHES) {
  test(`team palette stays readable and distinct: ${name}`, () => {
    const p = teamPalette(home, away)
    for (const t of [p.home, p.away]) {
      assert.ok(contrast(t.fill, t.ink) >= TEXT_CONTRAST, `ink on ${t.fill}`)
      assert.ok(contrast(t.line, BG) >= MARK_CONTRAST, `line ${t.line} on background`)
      assert.ok(deltaE(t.fill, AI_ACCENT) >= MIN_AI_DELTA_E, `${t.fill} too close to AI cyan`)
    }
    assert.ok(
      deltaE(p.home.fill, p.away.fill) >= MIN_TEAM_DELTA_E,
      `${p.home.fill} vs ${p.away.fill}: ${deltaE(p.home.fill, p.away.fill).toFixed(1)}`,
    )
  })
}

test('contrast matches WCAG reference values', () => {
  assert.equal(Math.round(contrast('#000000', '#ffffff') * 10) / 10, 21)
  assert.equal(Math.round(contrast('#777777', '#ffffff') * 100) / 100, 4.48)
})
