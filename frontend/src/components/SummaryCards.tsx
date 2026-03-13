import type { ReactNode } from 'react'

interface SummaryCardItem {
  label: string
  value: ReactNode
  hint?: string
}

interface SummaryCardsProps {
  items: SummaryCardItem[]
}

export function SummaryCards({ items }: SummaryCardsProps) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <article key={item.label} className="rounded-3xl border border-stone-300 bg-white/90 p-4 shadow-sm">
          <p className="text-xs uppercase tracking-[0.18em] text-stone-500">{item.label}</p>
          <p className="mt-3 text-2xl font-semibold text-stone-950">{item.value}</p>
          {item.hint ? <p className="mt-2 text-sm text-stone-600">{item.hint}</p> : null}
        </article>
      ))}
    </div>
  )
}
