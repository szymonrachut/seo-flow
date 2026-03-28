import { useTranslation } from 'react-i18next'

import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import type { EditorDocumentVersion, EditorDocumentVersionDiff } from '../../types/api'
import { formatDateTime } from '../../utils/format'
import { humanizeAiReviewValue } from './utils'

const sectionClass =
  'rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const panelClass =
  'rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/85'
const primaryActionClass =
  'inline-flex rounded-full bg-stone-950 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-teal-400 dark:text-slate-950 dark:hover:bg-teal-300'

function badgeClass(tone: 'stone' | 'teal' | 'amber' | 'rose') {
  if (tone === 'teal') {
    return 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/60 dark:text-teal-200'
  }
  if (tone === 'amber') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200'
  }
  if (tone === 'rose') {
    return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/60 dark:text-rose-200'
  }
  return 'border-stone-300 bg-stone-100 text-stone-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
}

function renderBadge(label: string, tone: 'stone' | 'teal' | 'amber' | 'rose' = 'stone') {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${badgeClass(tone)}`}
    >
      {label}
    </span>
  )
}

function changeTone(changeType: string) {
  if (changeType === 'added') {
    return 'teal' as const
  }
  if (changeType === 'removed') {
    return 'rose' as const
  }
  return 'amber' as const
}

interface AIReviewEditorDiffPreviewSectionProps {
  selectedVersion: EditorDocumentVersion | null
  diff: EditorDocumentVersionDiff | undefined
  isLoading: boolean
  errorMessage: string | null
  onRestore: (() => void) | null
  restoreDisabled: boolean
}

export function AIReviewEditorDiffPreviewSection({
  selectedVersion,
  diff,
  isLoading,
  errorMessage,
  onRestore,
  restoreDisabled,
}: AIReviewEditorDiffPreviewSectionProps) {
  const { t } = useTranslation()

  if (!selectedVersion) {
    return null
  }

  return (
    <section className={sectionClass} data-testid="ai-review-version-diff">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
            {t('aiReviewEditor.diffPreview.eyebrow')}
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-stone-950 dark:text-slate-50">
            {t('aiReviewEditor.diffPreview.title', { versionNo: selectedVersion.version_no })}
          </h2>
          <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
            {selectedVersion.source_description ?? t('aiReviewEditor.versions.fallbackDescription')}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {renderBadge(
            t(`aiReviewEditor.versionSource.${selectedVersion.source_of_change}`, {
              defaultValue: humanizeAiReviewValue(selectedVersion.source_of_change),
            }),
          )}
          {renderBadge(formatDateTime(selectedVersion.created_at))}
          {selectedVersion.is_current ? renderBadge(t('aiReviewEditor.versions.current'), 'teal') : null}
        </div>
      </div>

      {onRestore ? (
        <div className={`${panelClass} mt-4 flex flex-wrap items-center justify-between gap-3`}>
          <div>
            <p className="text-sm font-medium text-stone-950 dark:text-slate-100">
              {t('aiReviewEditor.diffPreview.restoreTitle')}
            </p>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
              {t('aiReviewEditor.diffPreview.restoreDescription')}
            </p>
          </div>
          <button type="button" onClick={onRestore} disabled={restoreDisabled} className={primaryActionClass}>
            {t('aiReviewEditor.actions.restoreVersion')}
          </button>
        </div>
      ) : null}

      {isLoading ? (
        <div className="mt-6">
          <LoadingState label={t('aiReviewEditor.diffPreview.loading')} />
        </div>
      ) : null}

      {!isLoading && errorMessage ? (
        <div className="mt-6">
          <ErrorState title={t('aiReviewEditor.diffPreview.errorTitle')} message={errorMessage} />
        </div>
      ) : null}

      {!isLoading && !errorMessage && !diff ? (
        <div className="mt-6">
          <EmptyState
            title={t('aiReviewEditor.diffPreview.emptyTitle')}
            description={t('aiReviewEditor.diffPreview.emptyDescription')}
          />
        </div>
      ) : null}

      {!isLoading && !errorMessage && diff ? (
        <div className="mt-6 space-y-4">
          <div className="flex flex-wrap gap-2">
            {renderBadge(`${t('aiReviewEditor.diffPreview.summary.changed')}: ${diff.summary.changed_blocks}`, 'amber')}
            {renderBadge(`${t('aiReviewEditor.diffPreview.summary.added')}: ${diff.summary.added_blocks}`, 'teal')}
            {renderBadge(`${t('aiReviewEditor.diffPreview.summary.removed')}: ${diff.summary.removed_blocks}`, 'rose')}
            {renderBadge(`${t('aiReviewEditor.diffPreview.summary.fields')}: ${diff.summary.changed_fields}`)}
          </div>

          {diff.document_changes.length > 0 ? (
            <div className={panelClass}>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                {t('aiReviewEditor.diffPreview.documentChanges')}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {diff.document_changes.map((change) =>
                  renderBadge(
                    t(`aiReviewEditor.diffField.${change.field}`, {
                      defaultValue: humanizeAiReviewValue(change.field),
                    }),
                  ),
                )}
              </div>
            </div>
          ) : null}

          {diff.block_changes.length === 0 ? (
            <EmptyState
              title={t('aiReviewEditor.diffPreview.noBlockChangesTitle')}
              description={t('aiReviewEditor.diffPreview.noBlockChangesDescription')}
            />
          ) : (
            <div className="space-y-4">
              {diff.block_changes.map((change) => (
                <article key={`${change.block_key}-${change.change_type}`} className={panelClass}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-2">
                      {renderBadge(change.block_key)}
                      {renderBadge(
                        t(`aiReviewEditor.diffChangeType.${change.change_type}`, {
                          defaultValue: humanizeAiReviewValue(change.change_type),
                        }),
                        changeTone(change.change_type),
                      )}
                    </div>
                    {change.after_context_path || change.before_context_path ? (
                      <span className="text-xs text-stone-500 dark:text-slate-400">
                        {change.after_context_path ?? change.before_context_path}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded-2xl border border-stone-200 bg-white/80 p-4 dark:border-slate-800 dark:bg-slate-950/80">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                        {t('aiReviewEditor.diffPreview.before')}
                      </p>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-stone-700 dark:text-slate-200">
                        {change.before_text ?? t('aiReviewEditor.common.none')}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-stone-200 bg-white/80 p-4 dark:border-slate-800 dark:bg-slate-950/80">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                        {t('aiReviewEditor.diffPreview.after')}
                      </p>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-stone-700 dark:text-slate-200">
                        {change.after_text ?? t('aiReviewEditor.common.none')}
                      </p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </section>
  )
}
