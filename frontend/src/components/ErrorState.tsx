interface ErrorStateProps {
  title: string
  message: string
}

export function ErrorState({ title, message }: ErrorStateProps) {
  return (
    <div className="rounded-3xl border border-rose-200 bg-rose-50 px-6 py-5 text-rose-950 shadow-sm dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-100">
      <p className="text-base font-semibold">{title}</p>
      <p className="mt-2 text-sm">{message}</p>
    </div>
  )
}
