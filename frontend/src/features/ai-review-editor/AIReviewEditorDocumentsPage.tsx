import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { DataViewHeader } from '../../components/DataViewHeader'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime } from '../../utils/format'
import { useSiteWorkspaceContext } from '../sites/context'
import {
  buildSiteAiReviewEditorDocumentPath,
  buildSiteAiReviewEditorNewDocumentPath,
} from '../sites/routes'
import { useSiteAiReviewDocumentsQuery } from './api'

function documentStatusClass(status: string) {
  if (status === 'parsed') {
    return 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/60 dark:text-teal-200'
  }
  if (status === 'draft') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200'
  }
  return 'border-stone-300 bg-stone-100 text-stone-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
}

export function AIReviewEditorDocumentsPage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const documentsQuery = useSiteAiReviewDocumentsQuery(site.id)

  useDocumentTitle(t('documentTitle.aiReviewEditorDocuments', { domain: site.domain }))

  if (documentsQuery.isLoading) {
    return <LoadingState label={t('aiReviewEditor.documents.loading')} />
  }

  if (documentsQuery.isError) {
    return (
      <ErrorState
        title={t('aiReviewEditor.documents.errorTitle')}
        message={getUiErrorMessage(documentsQuery.error, t)}
      />
    )
  }

  const items = documentsQuery.data?.items ?? []
  const parsedCount = items.filter((item) => item.status === 'parsed').length
  const draftCount = items.filter((item) => item.status === 'draft').length
  const activeBlocksCount = items.reduce((sum, item) => sum + item.active_block_count, 0)

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('aiReviewEditor.header.eyebrow')}
        title={t('aiReviewEditor.documents.title')}
        description={t('aiReviewEditor.documents.description')}
        primaryAction={{
          key: 'new-document',
          label: t('aiReviewEditor.actions.newDocument'),
          to: buildSiteAiReviewEditorNewDocumentPath(site.id, {
            activeCrawlId,
            baselineCrawlId,
          }),
        }}
        contextChips={[
          { label: t('aiReviewEditor.documents.context.site'), value: site.domain },
          {
            label: t('aiReviewEditor.documents.context.activeCrawl'),
            value: activeCrawlId ? `#${activeCrawlId}` : t('aiReviewEditor.common.none'),
          },
          {
            label: t('aiReviewEditor.documents.context.baseline'),
            value: baselineCrawlId ? `#${baselineCrawlId}` : t('aiReviewEditor.common.none'),
          },
        ]}
      />

      <SummaryCards
        items={[
          { label: t('aiReviewEditor.documents.summary.total'), value: items.length },
          { label: t('aiReviewEditor.documents.summary.parsed'), value: parsedCount },
          { label: t('aiReviewEditor.documents.summary.drafts'), value: draftCount },
          { label: t('aiReviewEditor.documents.summary.activeBlocks'), value: activeBlocksCount },
        ]}
      />

      {items.length === 0 ? (
        <EmptyState
          title={t('aiReviewEditor.documents.emptyTitle')}
          description={t('aiReviewEditor.documents.emptyDescription')}
        />
      ) : (
        <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/80">
          <div className="overflow-x-auto">
            <table className="min-w-full border-separate border-spacing-y-3">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                  <th className="pb-1 pr-4">{t('aiReviewEditor.documents.table.title')}</th>
                  <th className="pb-1 pr-4">{t('aiReviewEditor.documents.table.type')}</th>
                  <th className="pb-1 pr-4">{t('aiReviewEditor.documents.table.status')}</th>
                  <th className="pb-1 pr-4">{t('aiReviewEditor.documents.table.blocks')}</th>
                  <th className="pb-1 pr-4">{t('aiReviewEditor.documents.table.updated')}</th>
                  <th className="pb-1 text-right">{t('aiReviewEditor.documents.table.open')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="rounded-3xl border border-stone-200 bg-stone-50/85 dark:border-slate-800 dark:bg-slate-900/70">
                    <td className="rounded-l-3xl px-4 py-4 align-top">
                      <div>
                        <p className="text-sm font-semibold text-stone-950 dark:text-slate-100">{item.title}</p>
                        <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{item.source_format}</p>
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top text-sm text-stone-700 dark:text-slate-200">{item.document_type}</td>
                    <td className="px-4 py-4 align-top">
                      <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${documentStatusClass(item.status)}`}>
                        {t(`aiReviewEditor.documentStatus.${item.status}`)}
                      </span>
                    </td>
                    <td className="px-4 py-4 align-top text-sm text-stone-700 dark:text-slate-200">{item.active_block_count}</td>
                    <td className="px-4 py-4 align-top text-sm text-stone-700 dark:text-slate-200">{formatDateTime(item.updated_at)}</td>
                    <td className="rounded-r-3xl px-4 py-4 text-right align-top">
                      <Link
                        to={buildSiteAiReviewEditorDocumentPath(item.site_id, item.id, {
                          activeCrawlId,
                          baselineCrawlId,
                        })}
                        className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-100 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                      >
                        {t('common.open')}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
