import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime } from '../../utils/format'
import { CreateJobForm } from '../jobs/CreateJobForm'
import { useCreateCrawlJobMutation } from '../jobs/api'
import { useSitesQuery } from './api'
import { buildSiteOverviewPath, buildSitesNewPath } from './routes'

export function SitesPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  useDocumentTitle(t('documentTitle.sites'))

  const sitesQuery = useSitesQuery()
  const createMutation = useCreateCrawlJobMutation()

  async function handleCreateCrawl(payload: Parameters<typeof createMutation.mutateAsync>[0]) {
    const createdCrawl = await createMutation.mutateAsync(payload)
    navigate(
      buildSiteOverviewPath(createdCrawl.site_id, {
        activeCrawlId: createdCrawl.id,
      }),
    )
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/75 p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('sites.page.eyebrow')}</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-stone-950">{t('sites.page.title')}</h1>
            <p className="mt-3 max-w-3xl text-sm text-stone-600">{t('sites.page.description')}</p>
          </div>

          <Link
            to={buildSitesNewPath()}
            className="inline-flex rounded-full bg-stone-950 px-4 py-2.5 text-sm font-semibold !text-white transition hover:bg-stone-800"
          >
            {t('sites.page.addSite')}
          </Link>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[380px,1fr]">
        <CreateJobForm
          onSubmit={handleCreateCrawl}
          isPending={createMutation.isPending}
          errorMessage={createMutation.error ? getUiErrorMessage(createMutation.error, t) : null}
        />

        <div className="space-y-4">
          {sitesQuery.isLoading ? <LoadingState label={t('sites.page.loading')} /> : null}
          {sitesQuery.isError ? (
            <ErrorState title={t('sites.page.errorTitle')} message={getUiErrorMessage(sitesQuery.error, t)} />
          ) : null}
          {sitesQuery.isSuccess && sitesQuery.data.length === 0 ? (
            <EmptyState title={t('sites.page.emptyTitle')} description={t('sites.page.emptyDescription')} />
          ) : null}
          {sitesQuery.isSuccess && sitesQuery.data.length > 0 ? (
            <DataTable
              columns={[
                {
                  key: 'site',
                  header: t('sites.table.site'),
                  minWidth: 260,
                  cell: (site) => (
                    <div className="space-y-1">
                      <p className="font-semibold text-stone-900">{site.domain}</p>
                      <p className="text-xs text-stone-500">{site.root_url}</p>
                    </div>
                  ),
                },
                {
                  key: 'latest',
                  header: t('sites.table.latestCrawl'),
                  minWidth: 180,
                  cell: (site) =>
                    site.latest_crawl ? <StatusBadge status={site.latest_crawl.status} /> : t('sites.table.noCrawls'),
                },
                {
                  key: 'counts',
                  header: t('sites.table.crawls'),
                  minWidth: 120,
                  cell: (site) => site.summary.total_crawls,
                },
                {
                  key: 'last-crawl',
                  header: t('sites.table.lastCrawlAt'),
                  minWidth: 170,
                  cell: (site) => formatDateTime(site.summary.last_crawl_at),
                },
                {
                  key: 'gsc',
                  header: t('sites.table.gscProperty'),
                  minWidth: 220,
                  cell: (site) => site.selected_gsc_property_uri ?? '-',
                },
                {
                  key: 'actions',
                  header: t('sites.table.open'),
                  minWidth: 160,
                  cell: (site) => (
                    <button
                      type="button"
                      onClick={() =>
                        navigate(
                          buildSiteOverviewPath(site.id, {
                            activeCrawlId: site.latest_crawl?.id ?? undefined,
                          }),
                        )
                      }
                      className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                    >
                      {t('sites.table.open')}
                    </button>
                  ),
                },
              ]}
              rows={sitesQuery.data}
              rowKey={(site) => site.id}
            />
          ) : null}
        </div>
      </div>
    </div>
  )
}
