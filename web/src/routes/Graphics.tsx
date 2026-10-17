import { useEffect } from 'react'

// Graphics-only output (DESIGN.md §4): transparent 1920×1080 overlay layer for OBS / vision mixers.
// Placeholder until the broadcast package is built in D5b.
export function Graphics() {
  useEffect(() => {
    document.body.classList.add('graphics')
    return () => document.body.classList.remove('graphics')
  }, [])

  const params = new URLSearchParams(window.location.search)

  return (
    <div
      data-testid="graphics-frame"
      data-match={params.get('match') ?? ''}
      data-persona={params.get('persona') ?? ''}
      style={{ position: 'relative', width: 1920, height: 1080, background: 'transparent' }}
    />
  )
}
