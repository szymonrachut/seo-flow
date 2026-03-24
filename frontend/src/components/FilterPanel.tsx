import { useState, type PropsWithChildren } from 'react'
import { useTranslation } from 'react-i18next'

interface FilterPanelProps extends PropsWithChildren {
  title: string
  description?: string
  onReset?: () => void
  bodyClassName?: string
  defaultOpen?: boolean
}

export function FilterPanel({
  title,
  description,
  onReset,
  children,
  bodyClassName,
  defaultOpen = true,
}: FilterPanelProps) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const resolvedBodyClassName =
    bodyClassName ??
    'grid gap-3 md:grid-cols-2 xl:grid-cols-4'

  return (
    <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/80">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{title}</h2>
          {description ? <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{description}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {onReset ? (
            <button
              type="button"
              onClick={onReset}
              className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800"
            >
              {t('common.reset')}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setIsOpen((current) => !current)}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800"
          >
            {isOpen ? t('common.hideFilters') : t('common.showFilters')}
          </button>
        </div>
      </div>
      {isOpen ? (
        <div
          className={`mt-4 ${resolvedBodyClassName} [&>*]:min-w-0 [&_input]:min-w-0 [&_input]:w-full [&_select]:min-w-0 [&_select]:w-full [&_textarea]:min-w-0 [&_textarea]:w-full`}
        >
          {children}
        </div>
      ) : null}
    </section>
  )
}
