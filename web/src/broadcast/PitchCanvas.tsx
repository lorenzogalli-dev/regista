import { useEffect, useMemo, useRef } from 'react'

import type { TeamColors } from '../lib/color.ts'
import { useClockFrame, type Clock } from '../lib/clock.ts'
import { STAGE, type Camera, type Vec2 } from '../lib/projection.ts'
import { positionsAt, type Frame, type PlayerInfo } from '../lib/sample.ts'
import { pitchGeometry, type PitchGeometry } from './pitchGeometry.ts'

const PLAYER_RADIUS_M = 1.15

function path(ctx: CanvasRenderingContext2D, pts: Vec2[], close = false) {
  ctx.beginPath()
  pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)))
  if (close) ctx.closePath()
}

function drawPitch(ctx: CanvasRenderingContext2D, g: PitchGeometry) {
  // Night-stadium surround: dark with a soft floodlight pool over the pitch.
  ctx.fillStyle = '#06110c'
  ctx.fillRect(0, 0, STAGE.width, STAGE.height)
  const pool = ctx.createRadialGradient(960, 640, 120, 960, 640, 1150)
  pool.addColorStop(0, 'rgba(46, 92, 64, 0.30)')
  pool.addColorStop(1, 'rgba(6, 17, 12, 0)')
  ctx.fillStyle = pool
  ctx.fillRect(0, 0, STAGE.width, STAGE.height)

  g.stripes.forEach((quad, i) => {
    ctx.fillStyle = i % 2 ? '#123222' : '#0f2a1c'
    path(ctx, quad, true)
    ctx.fill()
  })
  // Depth haze: the far side recedes into the dark.
  const top = Math.min(...g.outline.map((p) => p.y))
  const bottom = Math.max(...g.outline.map((p) => p.y))
  const haze = ctx.createLinearGradient(0, top, 0, bottom)
  haze.addColorStop(0, 'rgba(6, 17, 12, 0.42)')
  haze.addColorStop(0.55, 'rgba(6, 17, 12, 0.06)')
  haze.addColorStop(1, 'rgba(6, 17, 12, 0)')
  ctx.fillStyle = haze
  path(ctx, g.outline, true)
  ctx.fill()

  ctx.strokeStyle = 'rgba(222, 236, 228, 0.55)'
  ctx.lineWidth = 2
  ctx.lineJoin = 'round'
  path(ctx, g.outline)
  ctx.stroke()
  for (const l of g.lines) {
    path(ctx, l)
    ctx.stroke()
  }
  ctx.strokeStyle = 'rgba(222, 236, 228, 0.35)'
  for (const goal of g.goals) {
    path(ctx, goal)
    ctx.stroke()
  }
  ctx.fillStyle = 'rgba(222, 236, 228, 0.7)'
  for (const s of Object.values(g.spots)) {
    ctx.beginPath()
    ctx.arc(s.x, s.y, 3, 0, 2 * Math.PI)
    ctx.fill()
  }
}

type Props = {
  players: PlayerInfo[]
  frames: () => Frame[]
  clock: Clock
  camera: Camera
  palette: Record<string, TeamColors>
}

export function PitchCanvas({ players: roster, frames, clock, camera, palette }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const geometry = useMemo(() => pitchGeometry(camera), [camera])
  const background = useRef<HTMLCanvasElement | null>(null)
  const players = useMemo(() => new Map<string, PlayerInfo>(roster.map((p) => [p.player_id, p])), [roster])
  const dpr = Math.min(2, window.devicePixelRatio || 1)

  useEffect(() => {
    // The static pitch is drawn once into an offscreen canvas and blitted every frame.
    const bg = document.createElement('canvas')
    bg.width = STAGE.width * dpr
    bg.height = STAGE.height * dpr
    const ctx = bg.getContext('2d')!
    ctx.scale(dpr, dpr)
    drawPitch(ctx, geometry)
    background.current = bg
  }, [geometry, dpr])

  useClockFrame(clock, (t) => {
    const canvas = ref.current
    const bg = background.current
    if (!canvas || !bg) return
    const ctx = canvas.getContext('2d')!
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.drawImage(bg, 0, 0)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    const fs = frames()
    if (!fs.length) {
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      return
    }
    const pos = positionsAt(fs, t)

    // Painter's order: far players first.
    const order = [...pos.players.entries()].sort((a, b) => b[1].y - a[1].y)
    for (const [pid, p] of order) {
      const info = players.get(pid)
      const team = info ? palette[info.team_id] : undefined
      if (!info || !team) continue
      const s = camera.project(p)
      const r = PLAYER_RADIUS_M * camera.scaleAt(p)
      ctx.fillStyle = 'rgba(0, 0, 0, 0.35)'
      ctx.beginPath()
      ctx.ellipse(s.x, s.y + r * 0.35, r * 1.05, r * 0.45, 0, 0, 2 * Math.PI)
      ctx.fill()
      ctx.fillStyle = team.fill
      ctx.beginPath()
      ctx.arc(s.x, s.y - r * 0.2, r, 0, 2 * Math.PI)
      ctx.fill()
      ctx.lineWidth = Math.max(1.5, r * 0.14)
      ctx.strokeStyle = 'rgba(6, 17, 12, 0.85)'
      ctx.stroke()
      ctx.fillStyle = team.ink
      ctx.font = `700 ${Math.round(r * 1.05)}px Archivo`
      ctx.fontStretch = 'condensed'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(String(info.shirt), s.x, s.y - r * 0.16)
    }

    const b = camera.project(pos.ball)
    const br = 0.42 * camera.scaleAt(pos.ball)
    const lift = pos.ball.z * camera.scaleAt(pos.ball)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.45)'
    ctx.beginPath()
    ctx.ellipse(b.x, b.y + br * 0.4, br, br * 0.45, 0, 0, 2 * Math.PI)
    ctx.fill()
    ctx.fillStyle = '#ffffff'
    ctx.shadowColor = 'rgba(255, 255, 255, 0.6)'
    ctx.shadowBlur = 8
    ctx.beginPath()
    ctx.arc(b.x, b.y - lift - br * 0.3, br, 0, 2 * Math.PI)
    ctx.fill()
    ctx.shadowBlur = 0
  })

  return (
    <canvas
      ref={ref}
      width={STAGE.width * dpr}
      height={STAGE.height * dpr}
      style={{ position: 'absolute', inset: 0, width: STAGE.width, height: STAGE.height }}
    />
  )
}
