import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { StatusBadge } from '../../components/StatusBadge'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { CrawlJobDetail, SiteCrawlListItem, SiteDetail } from '../../types/api'
import { formatDateTime } from '../../utils/format'
import { SiteContentGeneratorSection } from './SiteContentGeneratorSection'
import { useSiteWorkspaceContext } from './context'
import {
  buildSiteChangesPath,
  buildSiteCompetitiveGapPath,
  buildSiteContentRecommendationsPath,
  buildSiteCrawlsPath,
  buildSiteCrawlsNewPath,
  buildSiteGscPath,
} from './routes'

interface OverviewSignal {
  key: string
  title: string
  description: string
  actionLabel: string
  to: string
  tone: 'warning' | 'info' | 'success'
}

function buildSignals(
  t: (key: string, options?: Record<string, unknown>) => string,
  site: SiteDetail,
  activeCrawl: CrawlJobDetail | null,
  context: { activeCrawlId?: number | null; baselineCrawlId?: number | null },
): OverviewSignal[] {
  if (!activeCrawl) {
    return [
      {
        key: 'no-active-crawl',
        title: t('sites.overview.signals.noActiveTitle'),
        description: t('sites.overview.signals.noActiveDescription'),
        actionLabel: t('nav.newCrawl'),
        to: buildSiteCrawlsNewPath(site.id, context),
        tone: 'info',
      },
    ]
  }

  const signals: OverviewSignal[] = []
  const metadataIssues =
    activeCrawl.summary_counts.pages_missing_title + activeCrawl.summary_counts.pages_missing_meta_description
  const internalLinkingIssues =
    activeCrawl.summary_counts.broken_internal_links + activeCrawl.summary_counts.redirecting_internal_links

  if (activeCrawl.status === 'running' || activeCrawl.status === 'pending') {
    signals.push({
      key: 'crawl-running',
      title: t('sites.overview.signals.crawlRunningTitle'),
      description: t('sites.overview.signals.crawlRunningDescription'),
      actionLabel: t('sites.overview.actions.openCrawl'),
      to: `/jobs/${activeCrawl.id}`,
      tone: 'info',
    })
  }

  if (activeCrawl.progress.errors_count > 0) {
    signals.push({
      key: 'crawl-errors',
      title: t('sites.overview.signals.crawlErrorsTitle'),
      description: t('sites.overview.signals.crawlErrorsDescription', { count: activeCrawl.progress.errors_count }),
      actionLabel: t('sites.overview.actions.openCrawl'),
      to: `/jobs/${activeCrawl.id}`,
      tone: 'warning',
    })
  }

  if (metadataIssues > 0) {
    signals.push({
      key: 'metadata-gaps',
      title: t('sites.overview.signals.metadataTitle'),
      description: t('sites.overview.signals.metadataDescription', {
        titleCount: activeCrawl.summary_counts.pages_missing_title,
        metaCount: activeCrawl.summary_counts.pages_missing_meta_description,
      }),
      actionLabel: t('sites.overview.actions.openCrawl'),
      to: `/jobs/${activeCrawl.id}`,
      tone: 'warning',
    })
  }

  if (internalLinkingIssues > 0) {
    signals.push({
      key: 'internal-linking',
      title: t('sites.overview.signals.internalLinkingTitle'),
      description: t('sites.overview.signals.internalLinkingDescription', {
        brokenCount: activeCrawl.summary_counts.broken_internal_links,
        redirectCount: activeCrawl.summary_counts.redirecting_internal_links,
      }),
      actionLabel: t('sites.overview.actions.openCrawls'),
      to: buildSiteCrawlsPath(site.id, context),
      tone: 'warning',
    })
  }

  if (!site.selected_gsc_property_uri) {
    signals.push({
      key: 'gsc-missing',
      title: t('sites.overview.signals.gscMissingTitle'),
      description: t('sites.overview.signals.gscMissingDescription'),
      actionLabel: t('sites.overview.actions.openGsc'),
      to: buildSiteGscPath(site.id, context),
      tone: 'info',
    })
  } else if (activeCrawl.summary_counts.gsc_opportunities_28d > 0) {
    signals.push({
      key: 'gsc-opportunities',
      title: t('sites.overview.signals.gscOpportunitiesTitle'),
      description: t('sites.overview.signals.gscOpportunitiesDescription', {
        count: activeCrawl.summary_counts.gsc_opportunities_28d,
      }),
      actionLabel: t('sites.overview.actions.openContentRecommendations'),
      to: buildSiteContentRecommendationsPath(site.id, context),
      tone: 'info',
    })
  }

  if (signals.length === 0) {
    signals.push({
      key: 'snapshot-ready',
      title: t('sites.overview.signals.readyTitle'),
      description: t('sites.overview.signals.readyDescription'),
      actionLabel: t('sites.overview.actions.openCompetitiveGap'),
      to: buildSiteCompetitiveGapPath(site.id, context),
      tone: 'success',
    })
  }

  return signals.slice(0, 4)
}

function recentHistoryRows(crawlHistory: SiteCrawlListItem[]) {
  return crawlHistory.slice(0, 6)
}

export function SiteOverviewPage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId, updateCrawlContext } = useSiteWorkspaceContext()
  useDocumentTitle(t('documentTitle.siteOverview', { domain: site.domain }))

  const activeCrawl = site.active_crawl
  const baselineCrawl = site.baseline_crawl
  const routeContext = { activeCrawlId, baselineCrawlId }
  const signals = buildSignals(t, site, activeCrawl, routeContext)

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">
              {t('sites.overview.activeEyebrow')}
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-stone-950 dark:text-slate-50">
              {t('sites.overview.activeTitle')}
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-slate-300">
              {t('sites.overview.activeDescription')}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {activeCrawl ? <StatusBadge status={activeCrawl.status} /> : null}
            {activeCrawl ? (
              <Link
                to={`/jobs/${activeCrawl.id}`}
                className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
              >
                {t('sites.overview.actions.openCrawl')}
              </Link>
            ) : null}
          </div>
        </div>

        {!activeCrawl ? (
          <div className="mt-5">
            <EmptyState
              title={t('sites.overview.emptyActiveTitle')}
              description={t('sites.overview.emptyActiveDescription')}
            />
          </div>
        ) : (
          <div className="mt-5 grid gap-6 xl:grid-cols-[minmax(0,1.3fr),minmax(300px,0.9fr)]">
            <div className="space-y-5">
              <section className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
                      {t('sites.overview.status.title')}
                    </h3>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      {t('sites.overview.status.description')}
                    </p>
                  </div>
                  <p className="text-sm font-medium text-stone-700 dark:text-slate-200">#{activeCrawl.id}</p>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <MiniStat label={t('sites.overview.status.pagesVisited')} value={activeCrawl.progress.visited_pages} />
                  <MiniStat label={t('sites.overview.status.queuedUrls')} value={activeCrawl.progress.queued_urls} />
                  <MiniStat
                    label={t('sites.overview.status.discoveredLinks')}
                    value={activeCrawl.progress.discovered_links}
                  />
                  <MiniStat label={t('sites.overview.status.errors')} value={activeCrawl.progress.errors_count} />
                </div>

                <dl className="mt-4 grid gap-3 text-sm text-stone-700 dark:text-slate-200 sm:grid-cols-2">
                  <OverviewMetaItem
                    label={t('sites.overview.status.crawlStarted')}
                    value={formatDateTime(activeCrawl.started_at ?? activeCrawl.created_at)}
                  />
                  <OverviewMetaItem
                    label={t('sites.overview.status.crawlFinished')}
                    value={formatDateTime(activeCrawl.finished_at)}
                  />
                  <OverviewMetaItem
                    label={t('sites.overview.status.crawlCreated')}
                    value={formatDateTime(activeCrawl.created_at)}
                  />
                  <OverviewMetaItem
                    label={t('sites.overview.status.workingScope')}
                    value={String(activeCrawl.settings_json.start_url ?? site.root_url)}
                    breakAll
                  />
                </dl>
              </section>

              <section>
                <div className="mb-3">
                  <h3 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
                    {t('sites.overview.kpiTitle')}
                  </h3>
                  <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                    {t('sites.overview.kpiDescription')}
                  </p>
                </div>
                <SummaryCards
                  items={[
                    { label: t('sites.overview.kpi.totalPages'), value: activeCrawl.summary_counts.total_pages },
                    {
                      label: t('sites.overview.kpi.internalLinks'),
                      value: activeCrawl.summary_counts.total_internal_links,
                    },
                    { label: t('sites.overview.kpi.gsc28d'), value: activeCrawl.summary_counts.pages_with_gsc_28d },
                    {
                      label: t('sites.overview.kpi.gscOpportunities'),
                      value: activeCrawl.summary_counts.gsc_opportunities_28d,
                    },
                    { label: t('sites.overview.kpi.missingTitle'), value: activeCrawl.summary_counts.pages_missing_title },
                    {
                      label: t('sites.overview.kpi.missingMeta'),
                      value: activeCrawl.summary_counts.pages_missing_meta_description,
                    },
                    {
                      label: t('sites.overview.kpi.brokenInternalLinks'),
                      value: activeCrawl.summary_counts.broken_internal_links,
                    },
                    {
                      label: t('sites.overview.kpi.redirectingInternalLinks'),
                      value: activeCrawl.summary_counts.redirecting_internal_links,
                    },
                  ]}
                />
              </section>
            </div>

            <div className="space-y-4">
              <section className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
                      {t('sites.overview.gsc.title')}
                    </h3>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      {site.selected_gsc_property_uri
                        ? t('sites.overview.gsc.connectedDescription')
                        : t('sites.overview.gsc.emptyDescription')}
                    </p>
                  </div>
                  <Link
                    to={buildSiteGscPath(site.id, routeContext)}
                    className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                  >
                    {t('sites.overview.actions.openGsc')}
                  </Link>
                </div>

                <dl className="mt-4 space-y-3 text-sm text-stone-700 dark:text-slate-200">
                  <OverviewMetaItem
                    label={t('sites.overview.gsc.property')}
                    value={site.selected_gsc_property_uri ?? t('sites.overview.gsc.noProperty')}
                    breakAll
                  />
                </dl>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <MiniStat
                    label={t('sites.overview.kpi.gsc28d')}
                    value={activeCrawl.summary_counts.pages_with_gsc_28d}
                  />
                  <MiniStat
                    label={t('sites.overview.kpi.gscOpportunities')}
                    value={activeCrawl.summary_counts.gsc_opportunities_28d}
                  />
                </div>
              </section>

              <section className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
                      {t('sites.overview.baselineTitle')}
                    </h3>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      {t('sites.overview.baselineDescription')}
                    </p>
                  </div>
                  {baselineCrawl ? <StatusBadge status={baselineCrawl.status} /> : null}
                </div>
                {baselineCrawl ? (
                  <>
                    <div className="mt-4 rounded-2xl border border-stone-200 bg-white/80 p-3 dark:border-slate-800 dark:bg-slate-950/70">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-stone-950 dark:text-slate-100">
                          #{baselineCrawl.id}
                        </p>
                        <span className="inline-flex rounded-full border border-stone-200 bg-stone-100 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-stone-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
                          {t('sites.overview.baselineReady')}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                        {t('sites.overview.baselineReadyDescription', { id: baselineCrawl.id })}
                      </p>
                      <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                        {formatDateTime(baselineCrawl.started_at ?? baselineCrawl.created_at)}
                      </p>
                    </div>
                    <div className="mt-4">
                      <Link
                        to={buildSiteChangesPath(site.id, routeContext)}
                        className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                      >
                        {t('sites.overview.actions.openChanges')}
                      </Link>
                    </div>
                  </>
                ) : (
                  <div className="mt-4 rounded-2xl border border-dashed border-stone-300 bg-white/70 p-4 text-sm text-stone-700 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-200">
                    <p className="font-semibold text-stone-950 dark:text-slate-100">
                      {t('sites.overview.baselineWaiting')}
                    </p>
                    <p className="mt-2">{t('sites.overview.baselineWaitingDescription')}</p>
                    <Link
                      to={buildSiteCrawlsPath(site.id, routeContext)}
                      className="mt-3 inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                    >
                      {t('sites.overview.actions.openCrawls')}
                    </Link>
                  </div>
                )}
              </section>
            </div>
          </div>
        )}
      </section>

      <SiteContentGeneratorSection
        siteId={site.id}
        activeCrawlId={activeCrawlId}
        activeCrawlStatus={activeCrawl?.status ?? null}
      />

      <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <div>
          <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">
            {t('sites.overview.signals.title')}
          </h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
            {t('sites.overview.signals.description')}
          </p>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {signals.map((signal) => (
            <SignalCard key={signal.key} signal={signal} />
          ))}
        </div>
      </section>

      <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <div>
          <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">
            {t('sites.overview.shortcuts.title')}
          </h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
            {t('sites.overview.shortcuts.description')}
          </p>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <ShortcutCard
            title={t('nav.contentRecommendations')}
            description={t('sites.overview.shortcuts.contentRecommendationsDescription')}
            to={buildSiteContentRecommendationsPath(site.id, routeContext)}
          />
          <ShortcutCard
            title={t('nav.competitiveGap')}
            description={t('sites.overview.shortcuts.competitiveGapDescription')}
            to={buildSiteCompetitiveGapPath(site.id, routeContext)}
          />
          <ShortcutCard
            title={t('nav.gsc')}
            description={t('sites.overview.shortcuts.gscDescription')}
            to={buildSiteGscPath(site.id, routeContext)}
          />
          <ShortcutCard
            title={t('nav.crawls')}
            description={t('sites.overview.shortcuts.crawlsDescription')}
            to={buildSiteCrawlsPath(site.id, routeContext)}
          />
          <ShortcutCard
            title={t('nav.changes')}
            description={t('sites.overview.shortcuts.changesDescription')}
            to={buildSiteChangesPath(site.id, routeContext)}
          />
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr),minmax(300px,0.8fr)]">
        <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
          <div className="flex flex-col gap-2 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">
                {t('sites.overview.historyTitle')}
              </h2>
              <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                {t('sites.overview.historyDescription')}
              </p>
            </div>
            <Link
              to={buildSiteCrawlsPath(site.id, routeContext)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
            >
              {t('sites.overview.actions.openCrawls')}
            </Link>
          </div>

          {site.crawl_history.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                title={t('sites.overview.emptyHistoryTitle')}
                description={t('sites.overview.emptyHistoryDescription')}
              />
            </div>
          ) : (
            <div className="mt-4">
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
                    key: 'pages',
                    header: t('sites.crawls.table.pages'),
                    minWidth: 90,
                    cell: (crawl) => crawl.total_pages,
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
                    minWidth: 260,
                    cell: (crawl) => (
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => updateCrawlContext({ active_crawl_id: crawl.id })}
                          className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                        >
                          {t('sites.crawls.actions.useAsActive')}
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
                      </div>
                    ),
                  },
                ]}
                rows={recentHistoryRows(site.crawl_history)}
                rowKey={(crawl) => crawl.id}
              />
            </div>
          )}
        </section>

        <div className="space-y-4">
          <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
            <div>
              <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">
                {t('sites.overview.siteSummaryTitle')}
              </h2>
              <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                {t('sites.overview.siteSummaryDescription')}
              </p>
            </div>
            <div className="mt-4">
              <SummaryCards
                items={[
                  { label: t('sites.overview.summary.totalCrawls'), value: site.summary.total_crawls },
                  { label: t('sites.overview.summary.runningCrawls'), value: site.summary.running_crawls },
                  { label: t('sites.overview.summary.lastCrawl'), value: formatDateTime(site.summary.last_crawl_at) },
                  { label: t('sites.overview.summary.createdAt'), value: formatDateTime(site.created_at) },
                ]}
              />
            </div>
          </section>

          <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">
                  {t('sites.overview.newCrawlTitle')}
                </h2>
                <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                  {t('sites.overview.newCrawlDescription')}
                </p>
              </div>
              <Link
                to={buildSiteCrawlsNewPath(site.id, routeContext)}
                className="inline-flex rounded-full bg-stone-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-stone-800 dark:bg-teal-400 dark:text-slate-950 dark:hover:bg-teal-300"
              >
                {t('nav.newCrawl')}
              </Link>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
                <p className="text-sm font-semibold text-stone-900 dark:text-slate-100">
                  {t('sites.overview.newCrawlCards.snapshot.label')}
                </p>
                <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                  {t('sites.overview.newCrawlCards.snapshot.description')}
                </p>
              </div>
              <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
                <p className="text-sm font-semibold text-stone-900 dark:text-slate-100">
                  {t('sites.overview.newCrawlCards.workspace.label')}
                </p>
                <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                  {t('sites.overview.newCrawlCards.workspace.description')}
                </p>
              </div>
            </div>
          </section>

          {site.selected_gsc_property_uri ? (
            <div className="rounded-3xl border border-teal-200 bg-teal-50/70 p-4 text-sm text-teal-950 dark:border-teal-900/60 dark:bg-teal-950/30 dark:text-teal-100">
              <p className="font-semibold">{t('sites.overview.reuseGscTitle')}</p>
              <p className="mt-1">{t('sites.overview.reuseGscDescription')}</p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

interface MiniStatProps {
  label: string
  value: number
}

function MiniStat({ label, value }: MiniStatProps) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white/80 p-3 dark:border-slate-800 dark:bg-slate-950/70">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-stone-950 dark:text-slate-50">{value}</p>
    </div>
  )
}

interface OverviewMetaItemProps {
  label: string
  value: string
  breakAll?: boolean
}

function OverviewMetaItem({ label, value, breakAll = false }: OverviewMetaItemProps) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">{label}</dt>
      <dd className={`mt-1 text-sm font-medium text-stone-900 dark:text-slate-100 ${breakAll ? 'break-all' : ''}`}>
        {value}
      </dd>
    </div>
  )
}

interface SignalCardProps {
  signal: OverviewSignal
}

function SignalCard({ signal }: SignalCardProps) {
  const toneClasses =
    signal.tone === 'warning'
      ? 'border-amber-300 bg-amber-50/80 dark:border-amber-900/60 dark:bg-amber-950/25'
      : signal.tone === 'success'
        ? 'border-emerald-300 bg-emerald-50/80 dark:border-emerald-900/60 dark:bg-emerald-950/25'
        : 'border-stone-200 bg-stone-50/90 dark:border-slate-800 dark:bg-slate-900/80'

  return (
    <article className={`rounded-3xl border p-4 ${toneClasses}`}>
      <h3 className="text-base font-semibold text-stone-950 dark:text-slate-50">{signal.title}</h3>
      <p className="mt-2 text-sm text-stone-700 dark:text-slate-200">{signal.description}</p>
      <Link
        to={signal.to}
        className="mt-4 inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-white/80 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-950"
      >
        {signal.actionLabel}
      </Link>
    </article>
  )
}

interface ShortcutCardProps {
  title: string
  description: string
  to: string
}

function ShortcutCard({ title, description, to }: ShortcutCardProps) {
  const { t } = useTranslation()

  return (
    <article className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
      <h3 className="text-base font-semibold text-stone-950 dark:text-slate-50">{title}</h3>
      <p className="mt-2 text-sm text-stone-700 dark:text-slate-200">{description}</p>
      <Link
        to={to}
        className="mt-4 inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-white/80 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-950"
      >
        {t('common.open')}
      </Link>
    </article>
  )
}
