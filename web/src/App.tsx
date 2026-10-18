import { Architecture } from './routes/Architecture.tsx'
import { Broadcast } from './routes/Broadcast.tsx'
import { Control } from './routes/Control.tsx'
import { Design } from './routes/Design.tsx'
import { EvalReport } from './routes/EvalReport.tsx'
import { Graphics } from './routes/Graphics.tsx'
import { Landing } from './routes/Landing.tsx'
import { Recap } from './routes/Recap.tsx'
import { Second } from './routes/Second.tsx'
import { Split } from './routes/Split.tsx'
import { Tour } from './routes/Tour.tsx'

// Minimal path switch; a router is introduced only when there are enough screens to need one.
export default function App() {
  const path = window.location.pathname
  if (path.startsWith('/graphics')) return <Graphics />
  if (path.startsWith('/broadcast')) return <Broadcast />
  if (path.startsWith('/design')) return <Design />
  if (path.startsWith('/split')) return <Split />
  if (path.startsWith('/control')) return <Control />
  if (path.startsWith('/eval')) return <EvalReport />
  if (path.startsWith('/second')) return <Second />
  if (path.startsWith('/recap')) return <Recap />
  if (path.startsWith('/architecture')) return <Architecture />
  if (path.startsWith('/tour')) return <Tour />
  return <Landing />
}
