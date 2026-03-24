import { useTranslation } from 'react-i18next'

import type { SortOrder } from '../types/api'

interface SortOption {
  label: string
  value: string
}

interface SortControlsProps {
  label?: string
  sortBy: string
  sortOrder: SortOrder
  options: SortOption[]
  onSortByChange: (sortBy: string) => void
  onSortOrderChange: (sortOrder: SortOrder) => void
}

export function SortControls({
  label,
  sortBy,
  sortOrder,
  options,
  onSortByChange,
  onSortOrderChange,
}: SortControlsProps) {
  const { t } = useTranslation()
  const resolvedLabel = label ?? t('sort.title')

  return (
    <div className="flex flex-col gap-3 rounded-3xl border border-stone-300 bg-white/85 p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between dark:border-slate-800 dark:bg-slate-950/80">
      <div>
        <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{resolvedLabel}</h2>
        <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('sort.description')}</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-2 text-sm text-stone-700 dark:text-slate-200">
          <span>{t('sort.by')}</span>
          <select
            value={sortBy}
            onChange={(event) => onSortByChange(event.target.value)}
            className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-stone-700 dark:text-slate-200">
          <span>{t('sort.order')}</span>
          <select
            value={sortOrder}
            onChange={(event) => onSortOrderChange(event.target.value as SortOrder)}
            className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="asc">{t('sort.ascending')}</option>
            <option value="desc">{t('sort.descending')}</option>
          </select>
        </label>
      </div>
    </div>
  )
}
