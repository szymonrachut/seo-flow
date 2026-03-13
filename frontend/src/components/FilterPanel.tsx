import type { PropsWithChildren } from 'react'

interface FilterPanelProps extends PropsWithChildren {
  title: string
  description?: string
  onReset?: () => void
}

export function FilterPanel({ title, description, onReset, children }: FilterPanelProps) {
  return (
    <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-stone-900">{title}</h2>
          {description ? <p className="mt-1 text-sm text-stone-600">{description}</p> : null}
        </div>
        {onReset ? (
          <button
            type="button"
            onClick={onReset}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            Reset
          </button>
        ) : null}
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">{children}</div>
    </section>
  )
}
