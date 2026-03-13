import { NavLink } from 'react-router-dom'

interface JobNavigationProps {
  jobId: number
}

const links = [
  { to: '', label: 'Overview', end: true },
  { to: 'pages', label: 'Pages' },
  { to: 'links', label: 'Links' },
  { to: 'audit', label: 'Audit' },
]

export function JobNavigation({ jobId }: JobNavigationProps) {
  return (
    <nav className="flex flex-wrap gap-2">
      {links.map((link) => (
        <NavLink
          key={link.label}
          to={`/jobs/${jobId}/${link.to}`}
          end={link.end}
          className={({ isActive }) =>
            `rounded-full px-3 py-1.5 text-sm font-medium transition ${
              isActive
                ? 'bg-stone-950 text-white'
                : 'border border-stone-300 bg-white/80 text-stone-700 hover:bg-stone-100'
            }`
          }
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  )
}
