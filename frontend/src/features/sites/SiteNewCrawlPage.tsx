import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime } from '../../utils/format'
import { CreateJobForm } from '../jobs/CreateJobForm'
import { useCreateSiteCrawlMutation } from './api'
import { useSiteWorkspaceContext } from './context'
import { buildSiteCrawlsPath, buildSiteOverviewPath } from './routes'

export function SiteNewCrawlPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const createMutation = useCreateSiteCrawlMutation(site.id)

  useDocumentTitle(t('documentTitle.siteNewCrawl', { domain: site.domain }))

  async function handleCreateCrawl(payload: Parameters<typeof createMutation.mutateAsync>[0]) {
    const createdCrawl = await createMutation.mutateAsync(payload)
    navigate(
      buildSiteOverviewPath(site.id, {
        activeCrawlId: createdCrawl.id,
        baselineCrawlId: activeCrawlId ?? baselineCrawlId,
      }),
    )
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">
              {t('sites.crawls.newPage.eyebrow')}
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-stone-950 dark:text-slate-50">
              {t('sites.crawls.newPage.title')}
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-slate-300">
              {t('sites.crawls.newPage.description')}
            </p>
          </div>
          <Link
            to={buildSiteCrawlsPath(site.id, { activeCrawlId, baselineCrawlId })}
            className="inline-flex rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
          >
            {t('sites.crawls.newPage.backToHistory')}
          </Link>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,420px),minmax(0,1fr)]">
        <CreateJobForm
          onSubmit={handleCreateCrawl}
          isPending={createMutation.isPending}
          errorMessage={createMutation.error ? getUiErrorMessage(createMutation.error, t) : null}
          initialValues={{ root_url: site.root_url }}
        />

        <div className="space-y-4">
          <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
            <h3 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
              {t('sites.crawls.newPage.siteContextTitle')}
            </h3>
            <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
              {t('sites.crawls.newPage.siteContextDescription')}
            </p>
            <div className="mt-4">
              <SummaryCards
                items={[
                  { label: t('sites.crawls.newPage.siteContext.domain'), value: site.domain },
                  { label: t('sites.crawls.newPage.siteContext.rootUrl'), value: site.root_url },
                  { label: t('sites.crawls.newPage.siteContext.totalCrawls'), value: site.summary.total_crawls },
                  { label: t('sites.crawls.newPage.siteContext.lastCrawl'), value: formatDateTime(site.summary.last_crawl_at) },
                ]}
              />
            </div>
          </section>

          <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
            <h3 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
              {t('sites.crawls.newPage.snapshotTitle')}
            </h3>
            <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
              {t('sites.crawls.newPage.snapshotDescription')}
            </p>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
                <p className="text-sm font-semibold text-stone-900 dark:text-slate-100">
                  {t('sites.crawls.newPage.cards.workspace.label')}
                </p>
                <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                  {t('sites.crawls.newPage.cards.workspace.description')}
                </p>
              </div>
              <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
                <p className="text-sm font-semibold text-stone-900 dark:text-slate-100">
                  {t('sites.crawls.newPage.cards.snapshot.label')}
                </p>
                <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                  {t('sites.crawls.newPage.cards.snapshot.description')}
                </p>
              </div>
            </div>

            {site.selected_gsc_property_uri ? (
              <div className="mt-4 rounded-3xl border border-teal-200 bg-teal-50/80 p-4 text-sm text-teal-950 dark:border-teal-900/60 dark:bg-teal-950/30 dark:text-teal-100">
                <p className="font-semibold">{t('sites.crawls.newPage.gscTitle')}</p>
                <p className="mt-1">{t('sites.crawls.newPage.gscDescription')}</p>
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  )
}
