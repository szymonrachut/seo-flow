import { useTranslation } from 'react-i18next'

import { EmptyState } from '../../components/EmptyState'
import type { EditorDocumentVersion } from '../../types/api'
import { formatDateTime } from '../../utils/format'
import { humanizeAiReviewValue } from './utils'

const sectionClass =
  'rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const panelClass =
  'rounded-3xl border border-stone-200 bg-stone-50/90 p-4 transition dark:border-slate-800 dark:bg-slate-900/85'

function badgeClass(tone: 'stone' | 'teal' | 'amber') {
  if (tone === 'teal') {
    return 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/60 dark:text-teal-200'
  }
  if (tone === 'amber') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200'
  }
  return 'border-stone-300 bg-stone-100 text-stone-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
}

function renderBadge(label: string, tone: 'stone' | 'teal' | 'amber' = 'stone') {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${badgeClass(tone)}`}
    >
      {label}
    </span>
  )
}

interface AIReviewEditorVersionHistorySectionProps {
  versions: EditorDocumentVersion[]
  selectedVersionId?: number
  onSelectVersion: (versionId: number) => void
}

export function AIReviewEditorVersionHistorySection({
  versions,
  selectedVersionId,
  onSelectVersion,
}: AIReviewEditorVersionHistorySectionProps) {
  const { t } = useTranslation()

  return (
    <section className={sectionClass}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
            {t('aiReviewEditor.versions.title')}
          </h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
            {t('aiReviewEditor.versions.description')}
          </p>
        </div>
      </div>

      {versions.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title={t('aiReviewEditor.versions.emptyTitle')}
            description={t('aiReviewEditor.versions.emptyDescription')}
          />
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {versions.map((version) => {
            const isSelected = version.id === selectedVersionId
            return (
              <button
                key={version.id}
                type="button"
                onClick={() => onSelectVersion(version.id)}
                className={`${panelClass} w-full text-left ${
                  isSelected
                    ? 'border-teal-400 bg-teal-50/70 dark:border-teal-700 dark:bg-teal-950/30'
                    : 'hover:border-stone-300 hover:bg-white dark:hover:border-slate-700 dark:hover:bg-slate-950/80'
                }`}
                data-testid={`ai-review-version-${version.id}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap gap-2">
                    {renderBadge(
                      t(`aiReviewEditor.versionSource.${version.source_of_change}`, {
                        defaultValue: humanizeAiReviewValue(version.source_of_change),
                      }),
                      version.source_of_change === 'rollback' ? 'amber' : 'stone',
                    )}
                    {version.is_current ? (
                      <span data-testid="ai-review-current-version-badge">
                        {renderBadge(t('aiReviewEditor.versions.current'), 'teal')}
                      </span>
                    ) : null}
                  </div>
                  <span className="text-xs text-stone-500 dark:text-slate-400">v{version.version_no}</span>
                </div>
                <p className="mt-3 text-sm font-medium text-stone-950 dark:text-slate-100">
                  {version.source_description ?? t('aiReviewEditor.versions.fallbackDescription')}
                </p>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-stone-500 dark:text-slate-400">
                  <span>{formatDateTime(version.created_at)}</span>
                  <span>
                    {t('aiReviewEditor.versions.blockCount')}: {version.block_count}
                  </span>
                  <span>{version.version_hash.slice(0, 8)}</span>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
