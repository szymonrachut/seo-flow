import type { JobStatus } from '../types/api'

const statusClasses: Record<JobStatus, string> = {
  pending: 'bg-amber-100 text-amber-900 border-amber-200',
  running: 'bg-sky-100 text-sky-900 border-sky-200',
  finished: 'bg-emerald-100 text-emerald-900 border-emerald-200',
  failed: 'bg-rose-100 text-rose-900 border-rose-200',
  stopped: 'bg-stone-200 text-stone-900 border-stone-300',
}

interface StatusBadgeProps {
  status: JobStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${statusClasses[status]}`}
    >
      {status}
    </span>
  )
}
