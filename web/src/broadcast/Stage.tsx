import { useEffect, useState, type ReactNode } from 'react'

import { STAGE } from '../lib/projection.ts'

/**
 * The 1920×1080 broadcast frame. Everything inside is laid out in stage pixels; `fit` scales the
 * whole frame to the viewport (letterboxed), so canvas and overlays scale together.
 */
export function Stage({
  children,
  fit = true,
  transparent = false,
}: {
  children: ReactNode
  fit?: boolean
  transparent?: boolean
}) {
  const [scale, setScale] = useState(1)
  useEffect(() => {
    if (!fit) return
    const update = () => setScale(Math.min(window.innerWidth / STAGE.width, window.innerHeight / STAGE.height))
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [fit])

  const frame = (
    <div
      className="stage"
      data-testid="stage"
      style={{
        position: 'relative',
        width: STAGE.width,
        height: STAGE.height,
        overflow: 'hidden',
        background: transparent ? 'transparent' : 'var(--bg)',
        transform: fit ? `scale(${scale})` : undefined,
        transformOrigin: 'top left',
      }}
    >
      {children}
    </div>
  )
  if (!fit) return frame
  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        display: 'grid',
        placeItems: 'center',
        background: '#000',
      }}
    >
      <div style={{ width: STAGE.width * scale, height: STAGE.height * scale }}>{frame}</div>
    </div>
  )
}
