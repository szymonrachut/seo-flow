import { useTranslation } from 'react-i18next'

interface QuickFilterItem {
  label: string
  isActive?: boolean
  onClick: () => void
}

interface QuickFilterBarProps {
  title: string
  items: QuickFilterItem[]
  onReset?: () => void
}

const activePillClass =
  'border border-stone-950 bg-stone-950 !text-white shadow-sm hover:bg-stone-900 dark:border-teal-400 dark:bg-teal-400 dark:!text-slate-950 dark:hover:bg-teal-300'

const inactivePillClass =
  'border border-stone-300 bg-white text-stone-700 hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:bg-slate-900/85 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800'

export function QuickFilterBar({ title, items, onReset }: QuickFilterBarProps) {
  const { t } = useTranslation()

  return (
    <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/80">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{title}</h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('quickFilters.description')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={item.onClick}
              aria-pressed={item.isActive === true}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${item.isActive ? activePillClass : inactivePillClass}`}
            >
              {item.label}
            </button>
          ))}
          {onReset ? (
            <button
              type="button"
              onClick={onReset}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${inactivePillClass}`}
            >
              {t('common.reset')}
            </button>
          ) : null}
        </div>
      </div>
    </section>
  )
}
