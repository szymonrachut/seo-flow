import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type {
  ContentRecommendationOutcomeStatus,
  CrawlJobDetail,
  GscDateRangeLabel,
  GscRangeCoverage,
  ImplementedContentRecommendation,
  ImplementedContentRecommendationSummary,
  SiteAuditCompare,
  SiteDetail,
  SiteGscSummary,
  SiteInternalLinkingCompareSummary,
  SiteOpportunitiesCompareSummary,
  SitePagesCompareSummary,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatCrawlDateTime, formatDateTime } from '../../utils/format'
import { useSiteAuditCompareQuery } from '../audit/api'
import { useSiteContentRecommendationsQuery } from '../content-recommendations/api'
import { useSiteGscSummaryQuery } from '../gsc/api'
import { useInternalLinkingOverviewQuery, useSiteInternalLinkingCompareQuery } from '../internal-linking/api'
import { useOpportunitiesQuery, useSiteOpportunitiesCompareQuery } from '../opportunities/api'
import { useSitePagesCompareQuery } from '../pages/api'
import { useSiteWorkspaceContext } from './context'
import {
  buildSiteChangesPath,
  buildSiteChangesAuditPath,
  buildSiteChangesInternalLinkingPath,
  buildSiteChangesOpportunitiesPath,
  buildSiteChangesPagesPath,
  buildSiteContentRecommendationsPath,
  buildSiteCrawlsPath,
  buildSiteGscPath,
} from './routes'

const DEFAULT_GSC_RANGE: GscDateRangeLabel = 'last_28_days'
const IMPLEMENTED_OUTCOME_WINDOW = '30d'

interface ProgressDeltaItem {
  key: string
  title: string
  description: string
  to: string
  tone: 'teal' | 'amber' | 'rose' | 'stone'
}

interface ProgressTimelineItem {
  key: string
  title: string
  description: string
  timestamp: string
  badge: string
  tone: 'teal' | 'amber' | 'rose' | 'stone'
  to?: string
}

function formatSignedDelta(value: number) {
  if (value > 0) {
    return `+${value}`
  }
  return String(value)
}

function countMetadataIssues(crawl: CrawlJobDetail | null) {
  if (!crawl) {
    return 0
  }

  return (
    crawl.summary_counts.pages_missing_title +
    crawl.summary_counts.pages_missing_meta_description +
    crawl.summary_counts.pages_missing_h1
  )
}

function countAssessedImplementedOutcomes(summary: ImplementedContentRecommendationSummary | null | undefined) {
  if (!summary) {
    return 0
  }

  return (
    summary.status_counts.improved +
    summary.status_counts.unchanged +
    summary.status_counts.limited +
    summary.status_counts.unavailable +
    summary.status_counts.worsened
  )
}

function selectPreferredGscRange(summary: SiteGscSummary | undefined) {
  if (!summary) {
    return null
  }

  return (
    summary.ranges.find((range) => range.date_range_label === DEFAULT_GSC_RANGE) ??
    summary.ranges[0] ??
    null
  )
}

function gscRangeLabel(t: (key: string, options?: Record<string, unknown>) => string, range: GscRangeCoverage | null) {
  if (!range) {
    return t('sites.progress.gsc.noRange')
  }

  return t(`sites.progress.gsc.ranges.${range.date_range_label}`)
}

function outcomeStatusLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  status: ContentRecommendationOutcomeStatus,
) {
  return t(`contentRecommendations.implemented.status.${status}`)
}

function buildImprovedItems(
  t: (key: string, options?: Record<string, unknown>) => string,
  site: SiteDetail,
  context: { activeCrawlId: number | null; baselineCrawlId: number | null },
  compare: {
    audit: SiteAuditCompare | undefined
    pages: SitePagesCompareSummary | undefined
    opportunities: SiteOpportunitiesCompareSummary | undefined
    internalLinking: SiteInternalLinkingCompareSummary | undefined
  },
  implementedSummary: ImplementedContentRecommendationSummary | undefined,
) {
  const items: ProgressDeltaItem[] = []

  if ((compare.audit?.summary.resolved_issues_total ?? 0) > 0) {
    items.push({
      key: 'audit-resolved',
      title: t('sites.progress.improved.items.auditResolvedTitle', {
        count: compare.audit?.summary.resolved_issues_total ?? 0,
      }),
      description: t('sites.progress.improved.items.auditResolvedDescription', {
        count: compare.audit?.summary.resolved_sections ?? 0,
      }),
      to: buildSiteChangesAuditPath(site.id, context),
      tone: 'teal',
    })
  }

  if ((compare.pages?.improved_urls ?? 0) > 0) {
    items.push({
      key: 'pages-improved',
      title: t('sites.progress.improved.items.pagesImprovedTitle', {
        count: compare.pages?.improved_urls ?? 0,
      }),
      description: t('sites.progress.improved.items.pagesImprovedDescription', {
        priorityCount: compare.pages?.priority_improved_urls ?? 0,
        internalCount: compare.pages?.internal_linking_improved_urls ?? 0,
      }),
      to: buildSiteChangesPagesPath(site.id, context),
      tone: 'teal',
    })
  }

  if ((compare.opportunities?.resolved_opportunity_urls ?? 0) > 0) {
    items.push({
      key: 'opportunities-resolved',
      title: t('sites.progress.improved.items.opportunitiesResolvedTitle', {
        count: compare.opportunities?.resolved_opportunity_urls ?? 0,
      }),
      description: t('sites.progress.improved.items.opportunitiesResolvedDescription', {
        count: compare.opportunities?.left_actionable_urls ?? 0,
      }),
      to: buildSiteChangesOpportunitiesPath(site.id, context),
      tone: 'teal',
    })
  }

  const internalLinkingImprovementCount =
    (compare.internalLinking?.resolved_orphan_like_urls ?? 0) +
    (compare.internalLinking?.weakly_linked_improved_urls ?? 0) +
    (compare.internalLinking?.link_equity_improved_urls ?? 0) +
    (compare.internalLinking?.anchor_diversity_improved_urls ?? 0) +
    (compare.internalLinking?.boilerplate_improved_urls ?? 0)
  if (internalLinkingImprovementCount > 0) {
    items.push({
      key: 'internal-linking-improved',
      title: t('sites.progress.improved.items.internalLinkingTitle', {
        count: internalLinkingImprovementCount,
      }),
      description: t('sites.progress.improved.items.internalLinkingDescription', {
        orphanCount: compare.internalLinking?.resolved_orphan_like_urls ?? 0,
        equityCount: compare.internalLinking?.link_equity_improved_urls ?? 0,
      }),
      to: buildSiteChangesInternalLinkingPath(site.id, context),
      tone: 'teal',
    })
  }

  if ((implementedSummary?.status_counts.improved ?? 0) > 0) {
    items.push({
      key: 'implemented-improved',
      title: t('sites.progress.improved.items.implementedTitle', {
        count: implementedSummary?.status_counts.improved ?? 0,
      }),
      description: t('sites.progress.improved.items.implementedDescription', {
        count: countAssessedImplementedOutcomes(implementedSummary),
      }),
      to: buildSiteContentRecommendationsPath(site.id, context),
      tone: 'teal',
    })
  }

  return items
}

function buildWorsenedItems(
  t: (key: string, options?: Record<string, unknown>) => string,
  site: SiteDetail,
  context: { activeCrawlId: number | null; baselineCrawlId: number | null },
  compare: {
    audit: SiteAuditCompare | undefined
    pages: SitePagesCompareSummary | undefined
    opportunities: SiteOpportunitiesCompareSummary | undefined
    internalLinking: SiteInternalLinkingCompareSummary | undefined
  },
  implementedSummary: ImplementedContentRecommendationSummary | undefined,
) {
  const items: ProgressDeltaItem[] = []

  if ((compare.audit?.summary.new_issues_total ?? 0) > 0) {
    items.push({
      key: 'audit-new',
      title: t('sites.progress.worsened.items.auditNewTitle', {
        count: compare.audit?.summary.new_issues_total ?? 0,
      }),
      description: t('sites.progress.worsened.items.auditNewDescription', {
        count: (compare.audit?.summary.new_sections ?? 0) + (compare.audit?.summary.worsened_sections ?? 0),
      }),
      to: buildSiteChangesAuditPath(site.id, context),
      tone: 'rose',
    })
  }

  if ((compare.pages?.worsened_urls ?? 0) > 0) {
    items.push({
      key: 'pages-worsened',
      title: t('sites.progress.worsened.items.pagesTitle', {
        count: compare.pages?.worsened_urls ?? 0,
      }),
      description: t('sites.progress.worsened.items.pagesDescription', {
        priorityCount: compare.pages?.priority_worsened_urls ?? 0,
        contentCount: compare.pages?.content_drop_urls ?? 0,
      }),
      to: buildSiteChangesPagesPath(site.id, context),
      tone: 'rose',
    })
  }

  if ((compare.opportunities?.new_opportunity_urls ?? 0) > 0 || (compare.opportunities?.entered_actionable_urls ?? 0) > 0) {
    items.push({
      key: 'opportunities-new',
      title: t('sites.progress.worsened.items.opportunitiesTitle', {
        count: compare.opportunities?.new_opportunity_urls ?? 0,
      }),
      description: t('sites.progress.worsened.items.opportunitiesDescription', {
        count: compare.opportunities?.entered_actionable_urls ?? 0,
      }),
      to: buildSiteChangesOpportunitiesPath(site.id, context),
      tone: 'amber',
    })
  }

  const internalLinkingRegressionCount =
    (compare.internalLinking?.new_orphan_like_urls ?? 0) +
    (compare.internalLinking?.weakly_linked_worsened_urls ?? 0) +
    (compare.internalLinking?.link_equity_worsened_urls ?? 0) +
    (compare.internalLinking?.anchor_diversity_worsened_urls ?? 0) +
    (compare.internalLinking?.boilerplate_worsened_urls ?? 0)
  if (internalLinkingRegressionCount > 0) {
    items.push({
      key: 'internal-linking-worsened',
      title: t('sites.progress.worsened.items.internalLinkingTitle', {
        count: internalLinkingRegressionCount,
      }),
      description: t('sites.progress.worsened.items.internalLinkingDescription', {
        orphanCount: compare.internalLinking?.new_orphan_like_urls ?? 0,
        weakCount: compare.internalLinking?.weakly_linked_worsened_urls ?? 0,
      }),
      to: buildSiteChangesInternalLinkingPath(site.id, context),
      tone: 'amber',
    })
  }

  if ((implementedSummary?.status_counts.worsened ?? 0) > 0) {
    items.push({
      key: 'implemented-worsened',
      title: t('sites.progress.worsened.items.implementedTitle', {
        count: implementedSummary?.status_counts.worsened ?? 0,
      }),
      description: t('sites.progress.worsened.items.implementedDescription'),
      to: buildSiteContentRecommendationsPath(site.id, context),
      tone: 'rose',
    })
  }

  return items
}

function outcomeTone(status: ContentRecommendationOutcomeStatus): ProgressTimelineItem['tone'] {
  if (status === 'improved') {
    return 'teal'
  }
  if (status === 'worsened') {
    return 'rose'
  }
  if (status === 'too_early' || status === 'pending' || status === 'limited') {
    return 'amber'
  }
  return 'stone'
}

function buildTimelineItems(
  t: (key: string, options?: Record<string, unknown>) => string,
  site: SiteDetail,
  context: { activeCrawlId: number | null; baselineCrawlId: number | null },
  activeCrawl: CrawlJobDetail | null,
  baselineCrawl: CrawlJobDetail | null,
  gscSummary: SiteGscSummary | undefined,
  implementedItems: ImplementedContentRecommendation[] | undefined,
) {
  const items: ProgressTimelineItem[] = []

  if (activeCrawl) {
    const activeTimestamp = activeCrawl.finished_at ?? activeCrawl.started_at ?? activeCrawl.created_at
    const activeTitle =
      activeCrawl.status === 'finished'
        ? t('sites.progress.timeline.events.activeFinishedTitle')
        : activeCrawl.status === 'running'
          ? t('sites.progress.timeline.events.activeRunningTitle')
          : activeCrawl.status === 'pending'
            ? t('sites.progress.timeline.events.activePendingTitle')
            : t('sites.progress.timeline.events.activeSnapshotTitle')

    items.push({
      key: `active-crawl-${activeCrawl.id}`,
      title: activeTitle,
      description: t('sites.progress.timeline.events.activeDescription', { id: activeCrawl.id }),
      timestamp: activeTimestamp,
      badge: t(`jobs.status.${activeCrawl.status}`),
      tone: activeCrawl.status === 'finished' ? 'teal' : activeCrawl.status === 'failed' ? 'rose' : 'stone',
      to: `/jobs/${activeCrawl.id}`,
    })
  }

  if (baselineCrawl) {
    items.push({
      key: `baseline-crawl-${baselineCrawl.id}`,
      title: t('sites.progress.timeline.events.baselineTitle'),
      description: t('sites.progress.timeline.events.baselineDescription', { id: baselineCrawl.id }),
      timestamp: baselineCrawl.finished_at ?? baselineCrawl.started_at ?? baselineCrawl.created_at,
      badge: t('sites.progress.timeline.compareBadge'),
      tone: 'stone',
      to: buildSiteChangesPath(site.id, context),
    })
  }

  for (const range of gscSummary?.ranges ?? []) {
    if (!range.last_imported_at) {
      continue
    }

    items.push({
      key: `gsc-${range.date_range_label}-${range.last_imported_at}`,
      title: t('sites.progress.timeline.events.gscImportTitle', {
        range: gscRangeLabel(t, range),
      }),
      description: t('sites.progress.timeline.events.gscImportDescription', {
        clicksPages: range.pages_with_clicks,
        impressionsPages: range.pages_with_impressions,
      }),
      timestamp: range.last_imported_at,
      badge: t('nav.gsc'),
      tone: 'teal',
      to: buildSiteGscPath(site.id, context),
    })
  }

  for (const item of implementedItems ?? []) {
    items.push({
      key: `implemented-${item.recommendation_key}-${item.implemented_at}`,
      title: t('sites.progress.timeline.events.implementedTitle'),
      description: t('sites.progress.timeline.events.implementedDescription', {
        target: item.target_url ?? item.cluster_label ?? item.recommendation_text,
      }),
      timestamp: item.implemented_at,
      badge: outcomeStatusLabel(t, item.outcome_status),
      tone: outcomeTone(item.outcome_status),
      to: buildSiteContentRecommendationsPath(site.id, context),
    })
  }

  return items
    .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime())
    .slice(0, 6)
}

export function SiteProgressPage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()

  useDocumentTitle(t('documentTitle.siteProgress', { domain: site.domain }))

  const activeCrawl = site.active_crawl
  const baselineCrawl = site.baseline_crawl
  const routeContext = { activeCrawlId, baselineCrawlId }
  const effectiveBaselineId = baselineCrawl?.id ?? null
  const comparisonReady = Boolean(activeCrawlId && effectiveBaselineId && activeCrawlId !== effectiveBaselineId)

  const pagesCompareQuery = useSitePagesCompareQuery(
    site.id,
    {
      active_crawl_id: activeCrawlId ?? undefined,
      baseline_crawl_id: effectiveBaselineId ?? undefined,
      gsc_date_range: DEFAULT_GSC_RANGE,
      page: 1,
      page_size: 1,
      sort_by: 'delta_priority_score',
      sort_order: 'desc',
    },
    comparisonReady,
  )
  const auditCompareQuery = useSiteAuditCompareQuery(
    site.id,
    {
      active_crawl_id: activeCrawlId ?? undefined,
      baseline_crawl_id: effectiveBaselineId ?? undefined,
    },
    comparisonReady,
  )
  const opportunitiesCompareQuery = useSiteOpportunitiesCompareQuery(
    site.id,
    {
      active_crawl_id: activeCrawlId ?? undefined,
      baseline_crawl_id: effectiveBaselineId ?? undefined,
      gsc_date_range: DEFAULT_GSC_RANGE,
      page: 1,
      page_size: 1,
      sort_by: 'delta_priority_score',
      sort_order: 'desc',
    },
    comparisonReady,
  )
  const internalLinkingCompareQuery = useSiteInternalLinkingCompareQuery(
    site.id,
    {
      active_crawl_id: activeCrawlId ?? undefined,
      baseline_crawl_id: effectiveBaselineId ?? undefined,
      gsc_date_range: DEFAULT_GSC_RANGE,
      page: 1,
      page_size: 1,
      sort_by: 'delta_internal_linking_score',
      sort_order: 'desc',
    },
    comparisonReady,
  )
  const opportunitiesQuery = useOpportunitiesQuery(
    activeCrawlId ?? 0,
    {
      gsc_date_range: DEFAULT_GSC_RANGE,
      sort_by: 'count',
      sort_order: 'desc',
      top_pages_limit: 5,
    },
    Boolean(activeCrawlId),
  )
  const internalLinkingOverviewQuery = useInternalLinkingOverviewQuery(
    activeCrawlId ?? 0,
    DEFAULT_GSC_RANGE,
    Boolean(activeCrawlId),
  )
  const recommendationsQuery = useSiteContentRecommendationsQuery(
    site.id,
    {
      active_crawl_id: activeCrawlId ?? undefined,
      baseline_crawl_id: effectiveBaselineId ?? undefined,
      gsc_date_range: DEFAULT_GSC_RANGE,
      page: 1,
      page_size: 5,
      sort_by: 'priority_score',
      sort_order: 'desc',
      implemented_outcome_window: IMPLEMENTED_OUTCOME_WINDOW,
      implemented_status_filter: 'all',
      implemented_mode_filter: 'all',
      implemented_sort: 'implemented_at_desc',
    },
    Boolean(activeCrawlId),
  )
  const gscSummaryQuery = useSiteGscSummaryQuery(
    site.id,
    { active_crawl_id: activeCrawlId ?? undefined },
    Boolean(activeCrawlId),
  )

  const compareLoading =
    comparisonReady &&
    (pagesCompareQuery.isLoading ||
      auditCompareQuery.isLoading ||
      opportunitiesCompareQuery.isLoading ||
      internalLinkingCompareQuery.isLoading)
  const compareError =
    comparisonReady &&
    (pagesCompareQuery.error ??
      auditCompareQuery.error ??
      opportunitiesCompareQuery.error ??
      internalLinkingCompareQuery.error ??
      null)

  const metadataIssues = countMetadataIssues(activeCrawl)
  const baselineMetadataIssues = countMetadataIssues(baselineCrawl)
  const recommendationsSummary = recommendationsQuery.data?.summary
  const implementedSummary = recommendationsQuery.data?.implemented_summary
  const gscRange = selectPreferredGscRange(gscSummaryQuery.data)
  const improvedItems = buildImprovedItems(
    t,
    site,
    routeContext,
    {
      audit: auditCompareQuery.data,
      pages: pagesCompareQuery.data?.summary,
      opportunities: opportunitiesCompareQuery.data?.summary,
      internalLinking: internalLinkingCompareQuery.data?.summary,
    },
    implementedSummary,
  )
  const worsenedItems = buildWorsenedItems(
    t,
    site,
    routeContext,
    {
      audit: auditCompareQuery.data,
      pages: pagesCompareQuery.data?.summary,
      opportunities: opportunitiesCompareQuery.data?.summary,
      internalLinking: internalLinkingCompareQuery.data?.summary,
    },
    implementedSummary,
  )
  const timelineItems = buildTimelineItems(
    t,
    site,
    routeContext,
    activeCrawl,
    baselineCrawl,
    gscSummaryQuery.data,
    recommendationsQuery.data?.implemented_items,
  )

  if (!activeCrawl) {
    return (
      <section className="rounded-[32px] border border-stone-300 bg-white/90 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">
            {t('sites.progress.eyebrow')}
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-stone-950 dark:text-slate-50">{t('sites.progress.title')}</h2>
          <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-slate-300">{t('sites.progress.description')}</p>
        </div>

        <div className="mt-5">
          <EmptyState
            title={t('sites.progress.emptyActiveTitle')}
            description={t('sites.progress.emptyActiveDescription')}
          />
        </div>
      </section>
    )
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">
              {t('sites.progress.eyebrow')}
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-stone-950 dark:text-slate-50">{t('sites.progress.title')}</h2>
            <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-slate-300">{t('sites.progress.description')}</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={activeCrawl.status} />
            <Link
              to={`/jobs/${activeCrawl.id}`}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
            >
              {t('sites.progress.actions.openCrawl')}
            </Link>
          </div>
        </div>

        <div className="mt-5 grid gap-6 xl:grid-cols-[minmax(0,1.3fr),minmax(300px,0.9fr)]">
          <section className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
                  {t('sites.progress.status.title')}
                </h3>
                <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                  {t('sites.progress.status.description')}
                </p>
              </div>
              <p className="text-sm font-medium text-stone-700 dark:text-slate-200">#{activeCrawl.id}</p>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <ProgressStat label={t('sites.progress.status.pagesVisited')} value={activeCrawl.progress.visited_pages} />
              <ProgressStat label={t('sites.progress.status.queuedUrls')} value={activeCrawl.progress.queued_urls} />
              <ProgressStat
                label={t('sites.progress.status.discoveredLinks')}
                value={activeCrawl.progress.discovered_links}
              />
              <ProgressStat label={t('sites.progress.status.errors')} value={activeCrawl.progress.errors_count} />
            </div>

            <dl className="mt-4 grid gap-3 text-sm text-stone-700 dark:text-slate-200 sm:grid-cols-2">
              <ProgressMetaItem
                label={t('sites.progress.status.crawlStarted')}
                value={formatDateTime(activeCrawl.started_at ?? activeCrawl.created_at)}
              />
              <ProgressMetaItem
                label={t('sites.progress.status.crawlFinished')}
                value={formatDateTime(activeCrawl.finished_at)}
              />
              <ProgressMetaItem
                label={t('sites.progress.status.activeSnapshot')}
                value={formatCrawlDateTime(activeCrawl)}
              />
              <ProgressMetaItem
                label={t('sites.progress.status.workingScope')}
                value={String(activeCrawl.settings_json.start_url ?? site.root_url)}
                breakAll
              />
            </dl>
          </section>

          <div className="space-y-4">
            <section className="rounded-3xl border border-dashed border-stone-300 bg-white/70 p-4 dark:border-slate-700 dark:bg-slate-950/50">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
                    {t('sites.progress.context.title')}
                  </h3>
                  <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                    {comparisonReady
                      ? t('sites.progress.context.readyDescription')
                      : t('sites.progress.context.waitingDescription')}
                  </p>
                </div>
                {baselineCrawl ? <StatusBadge status={baselineCrawl.status} /> : null}
              </div>

              {baselineCrawl ? (
                <div className="mt-4 rounded-2xl border border-stone-200 bg-stone-50/90 p-3 dark:border-slate-800 dark:bg-slate-900/80">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
                    {comparisonReady ? t('sites.progress.context.compareReady') : t('sites.progress.context.baselineOnly')}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-stone-950 dark:text-slate-100">
                    #{baselineCrawl.id}
                  </p>
                  <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                    {comparisonReady
                      ? t('sites.progress.context.compareReadyDescription', { id: baselineCrawl.id })
                      : t('sites.progress.context.baselineOnlyDescription', { id: baselineCrawl.id })}
                  </p>
                  <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                    {formatDateTime(baselineCrawl.finished_at ?? baselineCrawl.started_at ?? baselineCrawl.created_at)}
                  </p>
                </div>
              ) : (
                <InlineEmptyState
                  title={t('sites.progress.context.emptyTitle')}
                  description={t('sites.progress.context.emptyDescription')}
                />
              )}

              <div className="mt-4">
                <Link
                  to={comparisonReady ? buildSiteChangesPath(site.id, routeContext) : buildSiteCrawlsPath(site.id, routeContext)}
                  className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                >
                  {comparisonReady ? t('sites.progress.actions.openChanges') : t('sites.progress.actions.openCrawls')}
                </Link>
              </div>
            </section>

            <section className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-stone-950 dark:text-slate-50">{t('sites.progress.gsc.title')}</h3>
                  <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                    {site.selected_gsc_property_uri
                      ? gscSummaryQuery.data?.active_crawl_has_gsc_data
                        ? t('sites.progress.gsc.connectedDescription')
                        : t('sites.progress.gsc.noDataDescription')
                      : t('sites.progress.gsc.notConnectedDescription')}
                  </p>
                </div>
                <Link
                  to={buildSiteGscPath(site.id, routeContext)}
                  className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                >
                  {t('sites.progress.actions.openGsc')}
                </Link>
              </div>

              <dl className="mt-4 grid gap-3 text-sm text-stone-700 dark:text-slate-200 sm:grid-cols-2">
                <ProgressMetaItem
                  label={t('sites.progress.gsc.property')}
                  value={site.selected_gsc_property_uri ?? t('sites.progress.gsc.noProperty')}
                  breakAll
                />
                <ProgressMetaItem label={t('sites.progress.gsc.rangeLabel')} value={gscRangeLabel(t, gscRange)} />
                <ProgressMetaItem
                  label={t('sites.progress.gsc.pagesWithImpressions')}
                  value={String(gscRange?.pages_with_impressions ?? 0)}
                />
                <ProgressMetaItem
                  label={t('sites.progress.gsc.lastImported')}
                  value={formatDateTime(gscRange?.last_imported_at)}
                />
              </dl>
            </section>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-3">
          <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">{t('sites.progress.kpis.title')}</h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('sites.progress.kpis.description')}</p>
        </div>
        <SummaryCards
          items={[
            {
              label: t('sites.progress.kpis.cards.pagesCrawled'),
              value: activeCrawl.summary_counts.total_pages,
              hint: baselineCrawl
                ? t('sites.progress.kpis.hints.pagesCompared', {
                    delta: formatSignedDelta(activeCrawl.summary_counts.total_pages - baselineCrawl.summary_counts.total_pages),
                  })
                : t('sites.progress.kpis.hints.pagesCurrent'),
            },
            {
              label: t('sites.progress.kpis.cards.metadataIssues'),
              value: metadataIssues,
              hint: baselineCrawl
                ? t('sites.progress.kpis.hints.metadataCompared', {
                    delta: formatSignedDelta(metadataIssues - baselineMetadataIssues),
                  })
                : t('sites.progress.kpis.hints.metadataCurrent'),
            },
            {
              label: t('sites.progress.kpis.cards.opportunityPages'),
              value: opportunitiesQuery.isLoading
                ? '...'
                : opportunitiesQuery.isError
                  ? t('sites.progress.kpis.valueUnavailable')
                  : (opportunitiesQuery.data?.pages_with_opportunities ?? 0),
              hint: opportunitiesCompareQuery.data?.summary
                ? t('sites.progress.kpis.hints.opportunitiesCompared', {
                    resolved: opportunitiesCompareQuery.data.summary.resolved_opportunity_urls,
                    newCount: opportunitiesCompareQuery.data.summary.new_opportunity_urls,
                  })
                : opportunitiesQuery.data
                  ? t('sites.progress.kpis.hints.opportunitiesCurrent', {
                      high: opportunitiesQuery.data.high_priority_pages,
                      critical: opportunitiesQuery.data.critical_priority_pages,
                    })
                  : t('sites.progress.kpis.hints.opportunitiesWaiting'),
            },
            {
              label: t('sites.progress.kpis.cards.internalLinkingIssues'),
              value: internalLinkingOverviewQuery.isLoading
                ? '...'
                : internalLinkingOverviewQuery.isError
                  ? t('sites.progress.kpis.valueUnavailable')
                  : (internalLinkingOverviewQuery.data?.issue_pages ?? 0),
              hint: internalLinkingCompareQuery.data?.summary
                ? t('sites.progress.kpis.hints.internalCompared', {
                    resolved: internalLinkingCompareQuery.data.summary.resolved_orphan_like_urls,
                    worsened: internalLinkingCompareQuery.data.summary.weakly_linked_worsened_urls,
                  })
                : internalLinkingOverviewQuery.data
                  ? t('sites.progress.kpis.hints.internalCurrent', {
                      orphan: internalLinkingOverviewQuery.data.orphan_like_pages,
                      weak: internalLinkingOverviewQuery.data.weakly_linked_important_pages,
                    })
                  : t('sites.progress.kpis.hints.internalWaiting'),
            },
            {
              label: t('sites.progress.kpis.cards.implementedRecommendations'),
              value: recommendationsQuery.isLoading
                ? '...'
                : recommendationsQuery.isError
                  ? t('sites.progress.kpis.valueUnavailable')
                  : (implementedSummary?.total_count ?? 0),
              hint: implementedSummary
                ? t('sites.progress.kpis.hints.implemented', {
                    improved: implementedSummary.status_counts.improved,
                    tooEarly: implementedSummary.status_counts.too_early,
                    active: recommendationsSummary?.total_recommendations ?? 0,
                  })
                : t('sites.progress.kpis.hints.implementedWaiting'),
            },
            {
              label: t('sites.progress.kpis.cards.gscPagesWithClicks'),
              value: gscSummaryQuery.isLoading
                ? '...'
                : gscSummaryQuery.isError
                  ? t('sites.progress.kpis.valueUnavailable')
                  : site.selected_gsc_property_uri && gscRange
                    ? gscRange.pages_with_clicks
                    : t('sites.progress.kpis.valueNoGsc'),
              hint: gscRange
                ? t('sites.progress.kpis.hints.gscCoverage', {
                    impressions: gscRange.pages_with_impressions,
                    importedAt: formatDateTime(gscRange.last_imported_at),
                  })
                : site.selected_gsc_property_uri
                  ? t('sites.progress.kpis.hints.gscWaiting')
                  : t('sites.progress.kpis.hints.gscDisconnected'),
            },
          ]}
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
          <div>
            <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">{t('sites.progress.improved.title')}</h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('sites.progress.improved.description')}</p>
          </div>

          {!comparisonReady ? (
            <div className="mt-4">
              <InlineEmptyState
                title={t('sites.progress.compareEmptyTitle')}
                description={t('sites.progress.compareEmptyDescription')}
              />
            </div>
          ) : compareLoading ? (
            <div className="mt-4">
              <LoadingState label={t('sites.progress.loadingCompare')} />
            </div>
          ) : compareError ? (
            <div className="mt-4">
              <ErrorState
                title={t('sites.progress.compareErrorTitle')}
                message={getUiErrorMessage(compareError, t)}
              />
            </div>
          ) : improvedItems.length === 0 ? (
            <div className="mt-4">
              <InlineEmptyState
                title={t('sites.progress.improved.emptyTitle')}
                description={t('sites.progress.improved.emptyDescription')}
              />
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {improvedItems.map((item) => (
                <DeltaCard key={item.key} item={item} actionLabel={t('common.open')} />
              ))}
            </div>
          )}
        </section>
        <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
          <div>
            <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">{t('sites.progress.worsened.title')}</h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('sites.progress.worsened.description')}</p>
          </div>

          {!comparisonReady ? (
            <div className="mt-4">
              <InlineEmptyState
                title={t('sites.progress.compareEmptyTitle')}
                description={t('sites.progress.compareEmptyDescription')}
              />
            </div>
          ) : compareLoading ? (
            <div className="mt-4">
              <LoadingState label={t('sites.progress.loadingCompare')} />
            </div>
          ) : compareError ? (
            <div className="mt-4">
              <ErrorState
                title={t('sites.progress.compareErrorTitle')}
                message={getUiErrorMessage(compareError, t)}
              />
            </div>
          ) : worsenedItems.length === 0 ? (
            <div className="mt-4">
              <InlineEmptyState
                title={t('sites.progress.worsened.emptyTitle')}
                description={t('sites.progress.worsened.emptyDescription')}
              />
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {worsenedItems.map((item) => (
                <DeltaCard key={item.key} item={item} actionLabel={t('common.open')} />
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr),minmax(300px,0.9fr)]">
        <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
          <div className="flex flex-col gap-2 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">
                {t('sites.progress.implementation.title')}
              </h2>
              <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                {t('sites.progress.implementation.description', { window: IMPLEMENTED_OUTCOME_WINDOW })}
              </p>
            </div>
            <Link
              to={buildSiteContentRecommendationsPath(site.id, routeContext)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
            >
              {t('sites.progress.actions.openContentRecommendations')}
            </Link>
          </div>

          {recommendationsQuery.isLoading ? (
            <div className="mt-4">
              <LoadingState label={t('sites.progress.loadingImplementation')} />
            </div>
          ) : recommendationsQuery.isError ? (
            <div className="mt-4">
              <ErrorState
                title={t('sites.progress.implementation.errorTitle')}
                message={getUiErrorMessage(recommendationsQuery.error, t)}
              />
            </div>
          ) : implementedSummary ? (
            <>
              <div className="mt-4">
                <SummaryCards
                  items={[
                    {
                      label: t('sites.progress.implementation.cards.active'),
                      value: recommendationsSummary?.total_recommendations ?? 0,
                      hint: t('sites.progress.implementation.hints.active'),
                    },
                    {
                      label: t('sites.progress.implementation.cards.implemented'),
                      value: implementedSummary.total_count,
                      hint: t('sites.progress.implementation.hints.implemented'),
                    },
                    {
                      label: t('sites.progress.implementation.cards.tooEarly'),
                      value: implementedSummary.status_counts.too_early,
                      hint: t('sites.progress.implementation.hints.tooEarly', { window: IMPLEMENTED_OUTCOME_WINDOW }),
                    },
                    {
                      label: t('sites.progress.implementation.cards.assessed'),
                      value: countAssessedImplementedOutcomes(implementedSummary),
                      hint: t('sites.progress.implementation.hints.assessed'),
                    },
                  ]}
                />
              </div>

              <div className="mt-5">
                <h3 className="text-base font-semibold text-stone-950 dark:text-slate-50">
                  {t('sites.progress.implementation.recentTitle')}
                </h3>
                {recommendationsQuery.data?.implemented_items.length ? (
                  <div className="mt-3 space-y-3">
                    {recommendationsQuery.data.implemented_items.map((item) => (
                      <ImplementedRecommendationCard
                        key={`${item.recommendation_key}-${item.implemented_at}`}
                        item={item}
                        title={item.target_url ?? item.cluster_label ?? item.recommendation_text}
                        description={item.outcome_summary}
                        implementedAtLabel={t('sites.progress.implementation.implementedAt')}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="mt-3">
                    <InlineEmptyState
                      title={t('sites.progress.implementation.emptyTitle')}
                      description={t('sites.progress.implementation.emptyDescription')}
                    />
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="mt-4">
              <InlineEmptyState
                title={t('sites.progress.implementation.emptyTitle')}
                description={t('sites.progress.implementation.emptyDescription')}
              />
            </div>
          )}
        </section>

        <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
          <div>
            <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">{t('sites.progress.timeline.title')}</h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('sites.progress.timeline.description')}</p>
          </div>

          {timelineItems.length === 0 ? (
            <div className="mt-4">
              <InlineEmptyState
                title={t('sites.progress.timeline.emptyTitle')}
                description={t('sites.progress.timeline.emptyDescription')}
              />
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {timelineItems.map((item) => (
                <TimelineCard key={item.key} item={item} actionLabel={t('common.open')} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

interface ProgressStatProps {
  label: string
  value: number
}

function ProgressStat({ label, value }: ProgressStatProps) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white/80 p-3 dark:border-slate-800 dark:bg-slate-950/70">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-stone-950 dark:text-slate-50">{value}</p>
    </div>
  )
}

interface ProgressMetaItemProps {
  label: string
  value: string
  breakAll?: boolean
}

function ProgressMetaItem({ label, value, breakAll = false }: ProgressMetaItemProps) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">{label}</dt>
      <dd className={`mt-1 text-sm font-medium text-stone-900 dark:text-slate-100 ${breakAll ? 'break-all' : ''}`}>
        {value}
      </dd>
    </div>
  )
}

interface InlineEmptyStateProps {
  title: string
  description: string
}

function InlineEmptyState({ title, description }: InlineEmptyStateProps) {
  return (
    <div className="rounded-3xl border border-dashed border-stone-300 bg-stone-50/70 p-4 text-sm text-stone-700 dark:border-slate-700 dark:bg-slate-950/45 dark:text-slate-200">
      <p className="font-semibold text-stone-950 dark:text-slate-100">{title}</p>
      <p className="mt-2">{description}</p>
    </div>
  )
}

interface DeltaCardProps {
  item: ProgressDeltaItem
  actionLabel: string
}

function DeltaCard({ item, actionLabel }: DeltaCardProps) {
  const toneClass =
    item.tone === 'teal'
      ? 'border-teal-200 bg-teal-50/70 dark:border-teal-900/50 dark:bg-teal-950/25'
      : item.tone === 'rose'
        ? 'border-rose-200 bg-rose-50/70 dark:border-rose-900/50 dark:bg-rose-950/25'
        : item.tone === 'amber'
          ? 'border-amber-200 bg-amber-50/70 dark:border-amber-900/50 dark:bg-amber-950/25'
          : 'border-stone-200 bg-stone-50/90 dark:border-slate-800 dark:bg-slate-900/80'

  return (
    <article className={`rounded-3xl border p-4 ${toneClass}`}>
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h3 className="text-base font-semibold text-stone-950 dark:text-slate-50">{item.title}</h3>
          <p className="mt-2 text-sm text-stone-700 dark:text-slate-200">{item.description}</p>
        </div>
        <Link
          to={item.to}
          className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-white/80 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-950"
        >
          {actionLabel}
        </Link>
      </div>
    </article>
  )
}

interface ImplementedRecommendationCardProps {
  item: ImplementedContentRecommendation
  title: string
  description: string
  implementedAtLabel: string
}

function ImplementedRecommendationCard({
  item,
  title,
  description,
  implementedAtLabel,
}: ImplementedRecommendationCardProps) {
  const { t } = useTranslation()

  return (
    <article className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <OutcomeBadge status={item.outcome_status} label={outcomeStatusLabel(t, item.outcome_status)} />
            <span className="text-xs uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
              {t(`contentRecommendations.implemented.mode.${item.primary_outcome_kind}`)}
            </span>
          </div>
          <h3 className="mt-3 break-all text-base font-semibold text-stone-950 dark:text-slate-50">{title}</h3>
          <p className="mt-2 text-sm text-stone-700 dark:text-slate-200">{description}</p>
          <p className="mt-3 text-xs text-stone-500 dark:text-slate-400">
            {implementedAtLabel}: {formatDateTime(item.implemented_at)}
          </p>
        </div>
      </div>
    </article>
  )
}

interface OutcomeBadgeProps {
  status: ContentRecommendationOutcomeStatus
  label: string
}

function OutcomeBadge({ status, label }: OutcomeBadgeProps) {
  const toneClass =
    status === 'improved'
      ? 'border-teal-200 bg-teal-100 text-teal-900 dark:border-teal-900/60 dark:bg-teal-950/40 dark:text-teal-100'
      : status === 'worsened'
        ? 'border-rose-200 bg-rose-100 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-100'
        : status === 'too_early' || status === 'pending' || status === 'limited'
          ? 'border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-100'
          : 'border-stone-300 bg-stone-100 text-stone-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100'

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${toneClass}`}>
      {label}
    </span>
  )
}

interface TimelineCardProps {
  item: ProgressTimelineItem
  actionLabel: string
}

function TimelineCard({ item, actionLabel }: TimelineCardProps) {
  const badgeClass =
    item.tone === 'teal'
      ? 'border-teal-200 bg-teal-100 text-teal-900 dark:border-teal-900/60 dark:bg-teal-950/40 dark:text-teal-100'
      : item.tone === 'rose'
        ? 'border-rose-200 bg-rose-100 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-100'
        : item.tone === 'amber'
          ? 'border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-100'
          : 'border-stone-300 bg-stone-100 text-stone-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100'

  return (
    <article className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${badgeClass}`}>
              {item.badge}
            </span>
            <span className="text-xs text-stone-500 dark:text-slate-400">{formatDateTime(item.timestamp)}</span>
          </div>
          <h3 className="mt-3 text-base font-semibold text-stone-950 dark:text-slate-50">{item.title}</h3>
          <p className="mt-2 text-sm text-stone-700 dark:text-slate-200">{item.description}</p>
        </div>
        {item.to ? (
          <Link
            to={item.to}
            className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-white/80 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-950"
          >
            {actionLabel}
          </Link>
        ) : null}
      </div>
    </article>
  )
}
