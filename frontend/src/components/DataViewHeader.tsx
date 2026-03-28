import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ActionMenu, type ActionMenuItem } from './ActionMenu'

type DataViewHeaderTone = 'default' | 'success' | 'warning'

interface DataViewHeaderChip {
  label: string
  value: string
  tone?: DataViewHeaderTone
}

interface DataViewHeaderProps {
  eyebrow?: string
  title: string
  description?: string
  contextChips?: DataViewHeaderChip[]
  primaryAction?: ActionMenuItem
  operations?: ActionMenuItem[]
  exports?: ActionMenuItem[]
}

function toneClassName(tone: DataViewHeaderTone) {
  if (tone === 'success') {
    return 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-400/40 dark:bg-teal-400/10 dark:text-teal-200'
  }
  if (tone === 'warning') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/40 dark:bg-amber-400/10 dark:text-amber-200'
  }
  return 'border-stone-300 bg-stone-100 text-stone-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
}

function renderPrimaryAction(action: ActionMenuItem) {
  const className =
    'inline-flex items-center rounded-full bg-stone-950 px-4 py-2 text-sm font-semibold !text-white transition hover:bg-stone-800 dark:bg-teal-400 dark:!text-slate-950 dark:hover:bg-teal-300'

  if (action.to) {
    return (
      <Link to={action.to} className={className}>
        {action.label}
      </Link>
    )
  }

  if (action.href) {
    return (
      <a href={action.href} className={className}>
        {action.label}
      </a>
    )
  }

  return (
    <button type="button" onClick={action.onClick} disabled={action.disabled} className={className}>
      {action.label}
    </button>
  )
}

export function DataViewHeader({
  eyebrow,
  title,
  description,
  contextChips = [],
  primaryAction,
  operations = [],
  exports = [],
}: DataViewHeaderProps) {
  const { t } = useTranslation()
  const hasActions = Boolean(primaryAction) || operations.length > 0 || exports.length > 0

  return (
    <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/80">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="space-y-3">
          {eyebrow ? (
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700 dark:text-teal-300">{eyebrow}</p>
          ) : null}
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-stone-950 dark:text-slate-50">
              {title}
            </h1>
            {description ? (
              <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-slate-300">{description}</p>
            ) : null}
          </div>
          {contextChips.length > 0 ? (
            <div className="flex flex-wrap gap-2 text-xs font-medium">
              {contextChips.map((chip) => (
                <span
                  key={`${chip.label}-${chip.value}`}
                  className={`rounded-full border px-3 py-1 ${toneClassName(chip.tone ?? 'default')}`}
                >
                  {chip.label}: {chip.value}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        {hasActions ? (
          <div className="flex flex-wrap justify-start gap-2 xl:justify-end">
            {primaryAction ? renderPrimaryAction(primaryAction) : null}
            <ActionMenu label={t('common.operations')} items={operations} />
            <ActionMenu label={t('common.export')} items={exports} />
          </div>
        ) : null}
      </div>
    </section>
  )
}
