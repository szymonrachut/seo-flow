import { useTranslation } from 'react-i18next'

import type { JobStatus } from '../types/api'

const statusClasses: Record<JobStatus, string> = {
  pending: 'border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-700/70 dark:bg-amber-950/45 dark:text-amber-200',
  running: 'border-sky-200 bg-sky-100 text-sky-900 dark:border-sky-700/70 dark:bg-sky-950/45 dark:text-sky-200',
  finished: 'border-emerald-200 bg-emerald-100 text-emerald-900 dark:border-emerald-700/70 dark:bg-emerald-950/45 dark:text-emerald-200',
  failed: 'border-rose-200 bg-rose-100 text-rose-900 dark:border-rose-700/70 dark:bg-rose-950/45 dark:text-rose-200',
  stopped: 'border-stone-300 bg-stone-200 text-stone-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200',
}

interface StatusBadgeProps {
  status: JobStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const { t } = useTranslation()

  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${statusClasses[status]}`}
    >
      {t(`jobs.status.${status}`)}
    </span>
  )
}
