import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime } from '../../utils/format'
import { useSiteCrawlsQuery } from './api'
import { useSiteWorkspaceContext } from './context'
import { buildSiteCrawlsNewPath } from './routes'

export function SiteCrawlsPage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId, updateCrawlContext } = useSiteWorkspaceContext()
  useDocumentTitle(t('documentTitle.siteCrawls', { domain: site.domain }))

  const crawlsQuery = useSiteCrawlsQuery(site.id)

  if (crawlsQuery.isLoading) {
    return <LoadingState label={t('sites.crawls.loading')} />
  }

  if (crawlsQuery.isError) {
    return <ErrorState title={t('sites.crawls.errorTitle')} message={getUiErrorMessage(crawlsQuery.error, t)} />
  }

  const crawls = crawlsQuery.data ?? []
  const routeContext = { activeCrawlId, baselineCrawlId }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">
              {t('sites.crawls.eyebrow')}
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-stone-950 dark:text-slate-50">
              {t('sites.crawls.title')}
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-slate-300">
              {t('sites.crawls.description')}
            </p>
          </div>
          <Link
            to={buildSiteCrawlsNewPath(site.id, routeContext)}
            className="inline-flex rounded-full bg-stone-950 px-4 py-2.5 text-sm font-semibold !text-white transition hover:bg-stone-800 dark:bg-teal-400 dark:!text-slate-950 dark:hover:bg-teal-300"
          >
            {t('nav.newCrawl')}
          </Link>
        </div>
      </section>

      <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <SummaryCards
          items={[
            { label: t('sites.crawls.summary.totalCrawls'), value: site.summary.total_crawls },
            { label: t('sites.crawls.summary.runningCrawls'), value: site.summary.running_crawls },
            { label: t('sites.crawls.summary.finishedCrawls'), value: site.summary.finished_crawls },
            { label: t('sites.crawls.summary.lastCrawl'), value: formatDateTime(site.summary.last_crawl_at) },
          ]}
        />
      </section>

      {crawls.length === 0 ? (
        <EmptyState title={t('sites.crawls.emptyTitle')} description={t('sites.crawls.emptyDescription')} />
      ) : (
        <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
          <DataTable
            columns={[
              {
                key: 'crawl',
                header: t('sites.crawls.table.crawl'),
                minWidth: 220,
                cell: (crawl) => (
                  <div className="space-y-1">
                    <p className="font-semibold text-stone-900 dark:text-slate-100">#{crawl.id}</p>
                    <p className="text-xs text-stone-500 dark:text-slate-400">{crawl.root_url ?? site.root_url}</p>
                  </div>
                ),
              },
              {
                key: 'status',
                header: t('sites.crawls.table.status'),
                minWidth: 120,
                cell: (crawl) => <StatusBadge status={crawl.status} />,
              },
              {
                key: 'created',
                header: t('sites.crawls.table.created'),
                minWidth: 170,
                cell: (crawl) => formatDateTime(crawl.created_at),
              },
              {
                key: 'started',
                header: t('sites.crawls.table.started'),
                minWidth: 170,
                cell: (crawl) => formatDateTime(crawl.started_at),
              },
              {
                key: 'finished',
                header: t('sites.crawls.table.finished'),
                minWidth: 170,
                cell: (crawl) => formatDateTime(crawl.finished_at),
              },
              {
                key: 'pages',
                header: t('sites.crawls.table.pages'),
                minWidth: 90,
                cell: (crawl) => crawl.total_pages,
              },
              {
                key: 'internal',
                header: t('sites.crawls.table.internalLinks'),
                minWidth: 110,
                cell: (crawl) => crawl.total_internal_links,
              },
              {
                key: 'external',
                header: t('sites.crawls.table.externalLinks'),
                minWidth: 110,
                cell: (crawl) => crawl.total_external_links,
              },
              {
                key: 'errors',
                header: t('sites.crawls.table.errors'),
                minWidth: 90,
                cell: (crawl) => crawl.total_errors,
              },
              {
                key: 'actions',
                header: t('sites.crawls.table.actions'),
                minWidth: 360,
                cell: (crawl) => (
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => updateCrawlContext({ active_crawl_id: crawl.id })}
                      disabled={crawl.id === activeCrawlId}
                      className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                    >
                      {crawl.id === activeCrawlId ? t('sites.crawls.actions.active') : t('sites.crawls.actions.useAsActive')}
                    </button>
                    {crawl.id !== activeCrawlId ? (
                      <button
                        type="button"
                        onClick={() => updateCrawlContext({ baseline_crawl_id: crawl.id })}
                        className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                      >
                        {t('sites.crawls.actions.useAsBaseline')}
                      </button>
                    ) : null}
                    <Link
                      to={`/jobs/${crawl.id}`}
                      className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                    >
                      {t('sites.crawls.actions.open')}
                    </Link>
                    <Link
                      to={`/jobs/${crawl.id}/pages`}
                      className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                    >
                      {t('sites.crawls.actions.openPages')}
                    </Link>
                  </div>
                ),
              },
            ]}
            rows={crawls}
            rowKey={(crawl) => crawl.id}
          />
        </section>
      )}
    </div>
  )
}
