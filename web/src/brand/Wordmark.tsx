// Regista wordmark: a slanted green tab with a "go on air" notch (the director's cue and the
// playmaker's forward pass), then the name in Barlow Condensed.

export function Mark({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="mark">
      <path d="M8 3 H30 L24 29 H2 Z" fill="var(--brand)" />
      <path d="M12 10 L22 16 L12 22 Z" fill="var(--brand-ink)" />
    </svg>
  )
}

export function Wordmark({ size = 24 }: { size?: number }) {
  return (
    <span className="wordmark" style={{ fontSize: size }}>
      <Mark size={size * 1.05} />
      <span className="wordmark-text">Regista</span>
    </span>
  )
}
