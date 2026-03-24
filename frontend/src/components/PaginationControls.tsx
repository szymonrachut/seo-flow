import { useTranslation } from 'react-i18next'

const pageSizeOptions = [25, 50, 100, 200]

interface PaginationControlsProps {
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}

export function PaginationControls({
  page,
  pageSize,
  totalItems,
  totalPages,
  onPageChange,
  onPageSizeChange,
}: PaginationControlsProps) {
  const { t } = useTranslation()
  const canGoPrev = page > 1
  const canGoNext = totalPages > 0 && page < totalPages

  return (
    <div className="flex flex-col gap-3 rounded-3xl border border-stone-300 bg-white/85 px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between dark:border-slate-800 dark:bg-slate-950/80">
      <div className="text-sm text-stone-600 dark:text-slate-300">
        {t('pagination.summary', {
          page,
          totalPages: Math.max(totalPages, 1),
          totalItems,
        })}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-stone-600 dark:text-slate-300">
          <span>{t('common.pageSize')}</span>
          <select
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {pageSizeOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={!canGoPrev}
          className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800"
        >
          {t('common.prev')}
        </button>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={!canGoNext}
          className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800"
        >
          {t('common.next')}
        </button>
      </div>
    </div>
  )
}
