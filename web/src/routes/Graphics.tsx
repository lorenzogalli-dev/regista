import { Broadcast } from './Broadcast.tsx'

// Graphics-only output (DESIGN.md §4): the overlay layer alone, transparent, at exactly
// 1920×1080, for OBS / vision mixers. Same components and timing as /broadcast.
export function Graphics() {
  return <Broadcast graphicsOnly />
}
