import assert from 'node:assert/strict'
import { test } from 'node:test'

import { pitchGeometry } from '../src/broadcast/pitchGeometry.ts'
import { PITCH, anchorAt, broadcastCamera, homography } from '../src/lib/projection.ts'

const cam = broadcastCamera()

test('canvas markings and DOM anchors put the penalty spots on the same pixel', () => {
  const g = pitchGeometry(cam)
  for (const [spot, metres] of [
    [g.spots.penaltyLeft, { x: 11, y: 34 }],
    [g.spots.penaltyRight, { x: 94, y: 34 }],
    [g.spots.centre, { x: 52.5, y: 34 }],
  ] as const) {
    const dom = anchorAt(cam, metres)
    assert.ok(Math.abs(dom.left - spot.x) < 1e-9 && Math.abs(dom.top - spot.y) < 1e-9)
  }
})

test('the camera maps the pitch corners where configured and round-trips', () => {
  const nl = cam.project({ x: 0, y: 0 })
  assert.ok(Math.abs(nl.x - 40) < 1e-6 && Math.abs(nl.y - 1012) < 1e-6)
  for (const p of [
    { x: 11, y: 34 },
    { x: 80.3, y: 5.2 },
    { x: 0, y: PITCH.width },
  ]) {
    const back = cam.unproject(cam.project(p))
    assert.ok(Math.hypot(back.x - p.x, back.y - p.y) < 1e-6)
  }
})

test('perspective: the far side is smaller and higher than the near side', () => {
  assert.ok(cam.scaleAt({ x: 52.5, y: 60 }) < cam.scaleAt({ x: 52.5, y: 8 }))
  assert.ok(cam.project({ x: 52.5, y: 60 }).y < cam.project({ x: 52.5, y: 8 }).y)
  // Equal pitch distances shrink with depth: 0→34 m covers more screen than 34→68 m.
  const y = (m: number) => cam.project({ x: 52.5, y: m }).y
  assert.ok(y(0) - y(34) > y(34) - y(68))
})

test('homography solves an affine case exactly', () => {
  const h = homography(
    [
      { x: 0, y: 0 },
      { x: 1, y: 0 },
      { x: 1, y: 1 },
      { x: 0, y: 1 },
    ],
    [
      { x: 10, y: 20 },
      { x: 12, y: 20 },
      { x: 12, y: 23 },
      { x: 10, y: 23 },
    ],
  )
  assert.deepEqual(
    h.map((v) => Math.round(v * 1e9) / 1e9),
    [2, 0, 10, 0, 3, 20, 0, 0, 1],
  )
})
