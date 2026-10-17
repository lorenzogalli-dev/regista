import { useEffect, useState } from 'react'

type Health = { status: string; db: string }

export function Landing() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetch('/health')
      .then((r) => r.json() as Promise<Health>)
      .then(setHealth)
      .catch(() => setError(true))
  }, [])

  return (
    <main style={{ padding: '5vh 5vw' }}>
      <h1>Ground Truth Football</h1>
      <p style={{ color: 'var(--text-2)' }}>Skeleton build. Screens arrive in D5.</p>
      <p data-testid="health">
        API: {error ? 'unreachable' : health ? `${health.status} (db ${health.db})` : 'checking…'}
      </p>
    </main>
  )
}
