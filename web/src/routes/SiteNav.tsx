import { Wordmark } from '../brand/Wordmark.tsx'
import './site.css'

// The floating pill nav of the site pages (landing, eval report, architecture, recap).

const PAGE_LINKS: [string, string][] = [
  ['/broadcast', 'Broadcast'],
  ['/control', 'Control room'],
  ['/eval', 'Results'],
  ['/architecture', 'Architecture'],
]

export function SiteNav({ links = PAGE_LINKS }: { links?: [string, string][] }) {
  const here = window.location.pathname
  return (
    <nav className="site-nav" aria-label="Site">
      <a className="site-nav-home" href="/" aria-label="Regista home">
        <Wordmark size={20} />
      </a>
      <div className="site-nav-links">
        {links.map(([href, label]) => (
          <a key={href} href={href} aria-current={href === here ? 'page' : undefined}>
            {label}
          </a>
        ))}
      </div>
      <a className="site-nav-cta" href="/tour">
        ▶ Tour
      </a>
    </nav>
  )
}
