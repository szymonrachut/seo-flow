interface EmptyStateProps {
  title: string
  description: string
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="rounded-3xl border border-dashed border-stone-300 bg-white/70 px-6 py-10 text-center shadow-sm dark:border-slate-700 dark:bg-slate-950/75">
      <p className="text-lg font-semibold text-stone-800 dark:text-slate-100">{title}</p>
      <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">{description}</p>
    </div>
  )
}
