interface LoadingStateProps {
  label: string
}

export function LoadingState({ label }: LoadingStateProps) {
  return (
    <div className="rounded-3xl border border-stone-300 bg-white/75 px-6 py-8 shadow-sm dark:border-slate-800 dark:bg-slate-950/75">
      <div className="flex items-center gap-3 text-sm text-stone-700 dark:text-slate-200">
        <div className="h-3 w-3 animate-pulse rounded-full bg-teal-600" />
        <span>{label}</span>
      </div>
    </div>
  )
}
