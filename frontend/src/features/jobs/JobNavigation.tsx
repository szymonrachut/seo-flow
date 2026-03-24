import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

interface JobNavigationProps {
  jobId: number
}

const activePillClass =
  'border border-stone-950 bg-stone-950 !text-white shadow-sm hover:bg-stone-900 dark:border-teal-400 dark:bg-teal-400 dark:!text-slate-950 dark:hover:bg-teal-300'

const inactivePillClass =
  'border border-stone-300 bg-white/80 text-stone-700 hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800'

export function JobNavigation({ jobId }: JobNavigationProps) {
  const { t } = useTranslation()
  const links = [
    { to: '', label: t('nav.overview'), end: true },
    { to: 'pages', label: t('nav.pages') },
    { to: 'links', label: t('nav.links') },
    { to: 'internal-linking', label: t('nav.internalLinking') },
    { to: 'cannibalization', label: t('nav.cannibalization') },
    { to: 'audit', label: t('nav.audit') },
    { to: 'opportunities', label: t('nav.opportunities') },
    { to: 'gsc', label: t('nav.gsc') },
    { to: 'trends', label: t('nav.trends') },
  ]

  return (
    <nav className="flex flex-wrap gap-2">
      {links.map((link) => (
        <NavLink
          key={link.label}
          to={`/jobs/${jobId}/${link.to}`}
          end={link.end}
          className={({ isActive }) =>
            `rounded-full px-3 py-1.5 text-sm font-medium transition ${isActive ? activePillClass : inactivePillClass}`
          }
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  )
}
