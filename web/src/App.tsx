import { Graphics } from './routes/Graphics.tsx'
import { Landing } from './routes/Landing.tsx'

// Minimal path switch; a router is introduced only when there are enough screens to need one.
export default function App() {
  if (window.location.pathname.startsWith('/graphics')) return <Graphics />
  return <Landing />
}
