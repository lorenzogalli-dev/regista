import { Broadcast } from './routes/Broadcast.tsx'
import { Design } from './routes/Design.tsx'
import { Graphics } from './routes/Graphics.tsx'
import { Landing } from './routes/Landing.tsx'

// Minimal path switch; a router is introduced only when there are enough screens to need one.
export default function App() {
  const path = window.location.pathname
  if (path.startsWith('/graphics')) return <Graphics />
  if (path.startsWith('/broadcast')) return <Broadcast />
  if (path.startsWith('/design')) return <Design />
  return <Landing />
}
