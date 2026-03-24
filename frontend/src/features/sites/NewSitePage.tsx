import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getUiErrorMessage } from '../../utils/errors'
import { CreateJobForm } from '../jobs/CreateJobForm'
import { useCreateCrawlJobMutation } from '../jobs/api'
import { buildSiteOverviewPath } from './routes'

export function NewSitePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const createMutation = useCreateCrawlJobMutation()

  useDocumentTitle(t('documentTitle.newSite'))

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
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/75">
        <p className="text-xs uppercase tracking-[0.22em] text-teal-700 dark:text-teal-300">
          {t('sites.newPage.eyebrow')}
        </p>
        <div className="mt-3 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <h1 className="text-4xl font-semibold tracking-tight text-stone-950 dark:text-slate-50">
              {t('sites.newPage.title')}
            </h1>
            <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">{t('sites.newPage.description')}</p>
          </div>
          <Link
            to="/sites"
            className="inline-flex rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
          >
            {t('sites.newPage.backToSites')}
          </Link>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,420px),minmax(0,1fr)]">
        <CreateJobForm
          onSubmit={handleCreateCrawl}
          isPending={createMutation.isPending}
          errorMessage={createMutation.error ? getUiErrorMessage(createMutation.error, t) : null}
        />

        <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/75">
          <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">{t('sites.newPage.workspaceTitle')}</h2>
          <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">{t('sites.newPage.workspaceDescription')}</p>

          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
              <p className="text-sm font-semibold text-stone-900 dark:text-slate-100">
                {t('sites.newPage.cards.workspace.label')}
              </p>
              <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                {t('sites.newPage.cards.workspace.description')}
              </p>
            </div>
            <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
              <p className="text-sm font-semibold text-stone-900 dark:text-slate-100">
                {t('sites.newPage.cards.snapshot.label')}
              </p>
              <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                {t('sites.newPage.cards.snapshot.description')}
              </p>
            </div>
            <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
              <p className="text-sm font-semibold text-stone-900 dark:text-slate-100">
                {t('sites.newPage.cards.navigation.label')}
              </p>
              <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                {t('sites.newPage.cards.navigation.description')}
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
