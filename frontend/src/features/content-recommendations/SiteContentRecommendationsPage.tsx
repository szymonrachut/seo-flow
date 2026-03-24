import { startTransition, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { buildApiUrl } from '../../api/client'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { PaginationControls } from '../../components/PaginationControls'
import { QuickFilterBar } from '../../components/QuickFilterBar'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type {
  ContentRecommendation,
  ContentRecommendationOutcomeKind,
  ContentRecommendationOutcomeStatus,
  ContentRecommendationOutcomeWindow,
  ContentRecommendationSegment,
  ContentRecommendationType,
  ContentRecommendationsSortBy,
  ImplementedContentRecommendation,
  ImplementedContentRecommendationSummary,
  ImplementedContentRecommendationModeFilter,
  ImplementedContentRecommendationSort,
  ImplementedContentRecommendationStatusFilter,
  PageBucket,
  PageType,
  SortOrder,
} from '../../types/api'
import { IMPLEMENTED_CONTENT_RECOMMENDATION_STATUS_ORDER } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime, formatPercent } from '../../utils/format'
import { buildQueryString, mergeSearchParams, parseFloatParam, parseIntegerParam } from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import {
  buildSiteCompetitiveGapPath,
  buildSiteContentRecommendationsActivePath,
  buildSiteContentRecommendationsImplementedPath,
  buildSitePagesRecordsPath,
} from '../sites/routes'
import {
  type SiteContentRecommendationsQueryParams,
  useMarkSiteContentRecommendationDoneMutation,
  useSiteContentRecommendationsQuery,
} from './api'

const recommendationTypes: ContentRecommendationType[] = [
  'MISSING_SUPPORTING_CONTENT',
  'THIN_CLUSTER',
  'EXPAND_EXISTING_PAGE',
  'MISSING_STRUCTURAL_PAGE_TYPE',
  'INTERNAL_LINKING_SUPPORT',
]

const recommendationSegments: ContentRecommendationSegment[] = [
  'create_new_page',
  'expand_existing_page',
  'strengthen_cluster',
  'improve_internal_support',
]

const pageTypes: PageType[] = [
  'home',
  'category',
  'product',
  'service',
  'blog_article',
  'blog_index',
  'contact',
  'about',
  'faq',
  'location',
  'legal',
  'utility',
  'other',
]

const implementedOutcomeWindows: ContentRecommendationOutcomeWindow[] = ['7d', '30d', '90d', 'all']
const implementedStatusFilters: ReadonlyArray<ImplementedContentRecommendationStatusFilter> = [
  'all',
  ...IMPLEMENTED_CONTENT_RECOMMENDATION_STATUS_ORDER,
]
const implementedModeFilters: ImplementedContentRecommendationModeFilter[] = [
  'all',
  'gsc',
  'internal_linking',
  'cannibalization',
  'issue_flags',
  'mixed',
  'unknown',
]
const implementedSortOptions: ImplementedContentRecommendationSort[] = [
  'implemented_at_desc',
  'implemented_at_asc',
  'outcome',
  'recommendation_type',
  'title',
]
const recommendationSurfaceClass =
  'rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const recommendationSectionClass =
  'rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const recommendationArticleClass =
  'rounded-[28px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/85'
const recommendationPanelClass =
  'rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/85'
const recommendationActionClass =
  'inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:border-slate-500 dark:hover:bg-slate-800'
const recommendationFieldLabelClass = 'grid gap-1 text-sm text-stone-700 dark:text-slate-300'
const recommendationFieldControlClass =
  'rounded-2xl border border-stone-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100'

function readRecommendationType(value: string | null): ContentRecommendationType | undefined {
  if (!value) {
    return undefined
  }

  return recommendationTypes.includes(value as ContentRecommendationType)
    ? (value as ContentRecommendationType)
    : undefined
}

function readRecommendationSegment(value: string | null): ContentRecommendationSegment | undefined {
  if (!value) {
    return undefined
  }

  return recommendationSegments.includes(value as ContentRecommendationSegment)
    ? (value as ContentRecommendationSegment)
    : undefined
}

function readPageType(value: string | null): PageType | undefined {
  if (!value) {
    return undefined
  }

  return pageTypes.includes(value as PageType) ? (value as PageType) : undefined
}

function readSortBy(value: string | null): ContentRecommendationsSortBy {
  return value === 'confidence' ||
    value === 'impact' ||
    value === 'effort' ||
    value === 'cluster_label' ||
    value === 'recommendation_type' ||
    value === 'page_type'
    ? value
    : 'priority_score'
}

function readImplementedOutcomeWindow(value: string | null): ContentRecommendationOutcomeWindow {
  return value === '7d' || value === '90d' || value === 'all' ? value : '30d'
}

function readImplementedStatusFilter(value: string | null): ImplementedContentRecommendationStatusFilter {
  return implementedStatusFilters.includes(value as ImplementedContentRecommendationStatusFilter)
    ? (value as ImplementedContentRecommendationStatusFilter)
    : 'all'
}

function readImplementedModeFilter(value: string | null): ImplementedContentRecommendationModeFilter {
  return implementedModeFilters.includes(value as ImplementedContentRecommendationModeFilter)
    ? (value as ImplementedContentRecommendationModeFilter)
    : 'all'
}

function readImplementedSort(value: string | null): ImplementedContentRecommendationSort {
  return implementedSortOptions.includes(value as ImplementedContentRecommendationSort)
    ? (value as ImplementedContentRecommendationSort)
    : 'implemented_at_desc'
}

function readParams(
  searchParams: URLSearchParams,
  activeCrawlId?: number | null,
  baselineCrawlId?: number | null,
): SiteContentRecommendationsQueryParams {
  return {
    active_crawl_id: activeCrawlId ?? undefined,
    baseline_crawl_id: baselineCrawlId ?? undefined,
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), 25),
    sort_by: readSortBy(searchParams.get('sort_by')),
    sort_order: searchParams.get('sort_order') === 'asc' ? 'asc' : 'desc',
    recommendation_type: readRecommendationType(searchParams.get('recommendation_type')),
    segment: readRecommendationSegment(searchParams.get('segment')),
    page_type: readPageType(searchParams.get('page_type')),
    cluster: searchParams.get('cluster') || undefined,
    confidence_min: parseFloatParam(searchParams.get('confidence_min'), undefined),
    priority_score_min: parseIntegerParam(searchParams.get('priority_score_min'), undefined),
    implemented_outcome_window: readImplementedOutcomeWindow(searchParams.get('implemented_outcome_window')),
    implemented_status_filter: readImplementedStatusFilter(searchParams.get('implemented_status_filter')),
    implemented_mode_filter: readImplementedModeFilter(searchParams.get('implemented_mode_filter')),
    implemented_search: searchParams.get('implemented_search') || undefined,
    implemented_sort: readImplementedSort(searchParams.get('implemented_sort')),
  }
}

function buildExportHref(siteId: number, params: SiteContentRecommendationsQueryParams) {
  const query = buildQueryString({
    active_crawl_id: params.active_crawl_id,
    baseline_crawl_id: params.baseline_crawl_id,
    gsc_date_range: params.gsc_date_range,
    sort_by: params.sort_by,
    sort_order: params.sort_order,
    recommendation_type: params.recommendation_type,
    segment: params.segment,
    page_type: params.page_type,
    cluster: params.cluster,
    confidence_min: params.confidence_min,
    priority_score_min: params.priority_score_min,
  })

  return buildApiUrl(`/sites/${siteId}/export/content-recommendations.csv${query ? `?${query}` : ''}`)
}

function toneClass(tone: 'stone' | 'teal' | 'amber' | 'rose') {
  if (tone === 'teal') {
    return 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/60 dark:text-teal-200'
  }
  if (tone === 'amber') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200'
  }
  if (tone === 'rose') {
    return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/60 dark:text-rose-200'
  }
  return 'border-stone-300 bg-stone-100 text-stone-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
}

function renderBadge(label: string, tone: 'stone' | 'teal' | 'amber' | 'rose' = 'stone') {
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${toneClass(tone)}`}>
      {label}
    </span>
  )
}

function recommendationTypeTone(type: ContentRecommendationType) {
  if (type === 'INTERNAL_LINKING_SUPPORT') {
    return 'teal'
  }
  if (type === 'EXPAND_EXISTING_PAGE') {
    return 'amber'
  }
  return 'stone'
}

function impactTone(impact: ContentRecommendation['impact']) {
  if (impact === 'high') {
    return 'rose'
  }
  if (impact === 'medium') {
    return 'amber'
  }
  return 'stone'
}

function effortTone(effort: ContentRecommendation['effort']) {
  if (effort === 'high') {
    return 'rose'
  }
  if (effort === 'medium') {
    return 'amber'
  }
  return 'teal'
}

function recommendationTypeLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  type: ContentRecommendationType,
) {
  return t(`contentRecommendations.types.${type}.title`)
}

function recommendationSegmentLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  segment: ContentRecommendationSegment,
) {
  return t(`contentRecommendations.segments.${segment}`)
}

function pageTypeLabel(t: (key: string, options?: Record<string, unknown>) => string, pageType: PageType) {
  return t(`pages.taxonomy.pageTypes.${pageType}`)
}

function pageBucketLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  pageBucket: PageBucket,
) {
  return t(`pages.taxonomy.pageBuckets.${pageBucket}`)
}

function outcomeTone(status: ContentRecommendationOutcomeStatus) {
  if (status === 'improved') {
    return 'teal'
  }
  if (status === 'worsened') {
    return 'rose'
  }
  if (status === 'pending' || status === 'limited' || status === 'too_early') {
    return 'amber'
  }
  return 'stone'
}

function outcomeStatusLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  status: ContentRecommendationOutcomeStatus,
) {
  return t(`contentRecommendations.implemented.status.${status}`)
}

function outcomeKindLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  kind: ContentRecommendationOutcomeKind,
) {
  return t(`contentRecommendations.implemented.mode.${kind}`)
}

function outcomeWindowLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  window: ContentRecommendationOutcomeWindow,
) {
  return t(`contentRecommendations.implemented.windows.${window}`)
}

function implementedSummaryTone(status: 'total' | ContentRecommendationOutcomeStatus) {
  if (status === 'total') {
    return 'stone'
  }
  return outcomeTone(status)
}

function renderSummaryPill(
  label: string,
  count: number,
  tone: 'stone' | 'teal' | 'amber' | 'rose',
  options?: {
    muted?: boolean
    active?: boolean
    disabled?: boolean
    onClick?: () => void
  },
) {
  const muted = options?.muted ?? false
  const active = options?.active ?? false
  const disabled = options?.disabled ?? false
  const className = `inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition ${toneClass(
    tone,
  )} ${muted ? 'opacity-60' : ''} ${
    active ? 'shadow-sm outline outline-2 outline-offset-2 outline-stone-300 dark:outline-slate-500' : ''
  } ${
    disabled
      ? 'cursor-not-allowed'
      : 'cursor-pointer hover:-translate-y-px hover:shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-stone-400 dark:focus-visible:outline-slate-400'
  }`

  if (options?.onClick) {
    return (
      <button
        type="button"
        aria-label={`${label}: ${count}`}
        aria-pressed={active}
        disabled={disabled}
        onClick={options.onClick}
        className={className}
      >
        <span>{label}</span>
        <span aria-hidden="true">:</span>
        <span className="font-semibold">{count}</span>
      </button>
    )
  }

  return (
    <span
      aria-label={`${label}: ${count}`}
      className={className}
    >
      <span>{label}</span>
      <span aria-hidden="true">:</span>
      <span className="font-semibold">{count}</span>
    </span>
  )
}

function internalIssueTypeLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  issueType: string,
) {
  return t(`internalLinking.issueTypes.${issueType}.title`)
}

function buildPagesLink(
  siteId: number,
  targetUrl: string,
  activeCrawlId?: number | null,
  baselineCrawlId?: number | null,
) {
  const base = buildSitePagesRecordsPath(siteId, { activeCrawlId, baselineCrawlId })
  const separator = base.includes('?') ? '&' : '?'
  return `${base}${separator}${buildQueryString({ url_contains: targetUrl })}`
}

function implementedRecommendationHeading(item: ImplementedContentRecommendation) {
  return item.recommendation_text
}

function implementedRecommendationContext(item: ImplementedContentRecommendation) {
  return item.target_title_snapshot ?? item.target_url ?? item.cluster_label ?? item.cluster_key ?? null
}

function buildImplementedSummaryItems(
  t: (key: string, options?: Record<string, unknown>) => string,
  implementedSummary: ImplementedContentRecommendationSummary,
): Array<{
  key: 'total' | ContentRecommendationOutcomeStatus
  label: string
  count: number
  tone: 'stone' | 'teal' | 'amber' | 'rose'
  statusFilter: ImplementedContentRecommendationStatusFilter
}> {
  const statusItems: Array<{
    key: ContentRecommendationOutcomeStatus
    label: string
    count: number
    tone: 'stone' | 'teal' | 'amber' | 'rose'
    statusFilter: ContentRecommendationOutcomeStatus
  }> = IMPLEMENTED_CONTENT_RECOMMENDATION_STATUS_ORDER.map((status) => ({
    key: status,
    label: outcomeStatusLabel(t, status),
    count: implementedSummary.status_counts[status],
    tone: implementedSummaryTone(status),
    statusFilter: status,
  }))

  return [
    {
      key: 'total',
      label: t('contentRecommendations.implemented.summaryTotal'),
      count: implementedSummary.total_count,
      tone: implementedSummaryTone('total'),
      statusFilter: 'all',
    },
    ...statusItems,
  ]
}

type SiteContentRecommendationsPageMode = 'overview' | 'active' | 'implemented'

interface SiteContentRecommendationsPageProps {
  mode?: SiteContentRecommendationsPageMode
}

export function SiteContentRecommendationsPage({
  mode = 'overview',
}: SiteContentRecommendationsPageProps) {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const documentTitleKey = {
    overview: 'documentTitle.siteContentRecommendations',
    active: 'documentTitle.siteContentRecommendationsActive',
    implemented: 'documentTitle.siteContentRecommendationsImplemented',
  }[mode]
  useDocumentTitle(t(documentTitleKey, { domain: site.domain }))

  const [searchParams, setSearchParams] = useSearchParams()
  const recommendationParams = useMemo(
    () => readParams(searchParams, activeCrawlId, baselineCrawlId),
    [activeCrawlId, baselineCrawlId, searchParams],
  )
  const recommendationsQuery = useSiteContentRecommendationsQuery(site.id, recommendationParams)
  const markDoneMutation = useMarkSiteContentRecommendationDoneMutation(site.id)

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function updateFilter(updates: Record<string, string | number | undefined>) {
    updateParams({ ...updates, page: 1 })
  }

  function updateImplementedFilters(updates: Record<string, string | number | undefined>) {
    updateParams(updates)
  }

  function applyImplementedSummaryFilter(statusFilter: ImplementedContentRecommendationStatusFilter) {
    updateParams({
      implemented_status_filter: statusFilter,
      page: 1,
    })
  }

  function applyQuickFilter(updates: Record<string, string | number | undefined>) {
    updateFilter({
      ...updates,
      sort_by: 'priority_score',
      sort_order: 'desc',
    })
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: recommendationParams.gsc_date_range,
      page: 1,
      page_size: 25,
      sort_by: 'priority_score',
      sort_order: 'desc',
      recommendation_type: undefined,
      segment: undefined,
      page_type: undefined,
      cluster: undefined,
      confidence_min: undefined,
      priority_score_min: undefined,
    })
  }

  function resetImplementedFilters() {
    updateImplementedFilters({
      implemented_outcome_window: '30d',
      implemented_status_filter: undefined,
      implemented_mode_filter: undefined,
      implemented_search: undefined,
      implemented_sort: undefined,
    })
  }

  const quickFilters = [
    {
      label: t('contentRecommendations.quickFilters.createNewPage'),
      isActive: recommendationParams.segment === 'create_new_page',
      onClick: () => applyQuickFilter({ segment: 'create_new_page', recommendation_type: undefined }),
    },
    {
      label: t('contentRecommendations.quickFilters.expandExisting'),
      isActive: recommendationParams.segment === 'expand_existing_page',
      onClick: () => applyQuickFilter({ segment: 'expand_existing_page', recommendation_type: undefined }),
    },
    {
      label: t('contentRecommendations.quickFilters.strengthenCluster'),
      isActive: recommendationParams.segment === 'strengthen_cluster',
      onClick: () => applyQuickFilter({ segment: 'strengthen_cluster', recommendation_type: undefined }),
    },
    {
      label: t('contentRecommendations.quickFilters.internalSupport'),
      isActive: recommendationParams.segment === 'improve_internal_support',
      onClick: () => applyQuickFilter({ segment: 'improve_internal_support', recommendation_type: undefined }),
    },
    {
      label: t('contentRecommendations.quickFilters.highPriority'),
      isActive: (recommendationParams.priority_score_min ?? 0) >= 70,
      onClick: () => applyQuickFilter({ priority_score_min: 70 }),
    },
  ]

  if (recommendationsQuery.isLoading) {
    return <LoadingState label={t('contentRecommendations.page.loading')} />
  }

  if (recommendationsQuery.isError) {
    return (
      <ErrorState
        title={t('contentRecommendations.errorTitle')}
        message={getUiErrorMessage(recommendationsQuery.error, t)}
      />
    )
  }

  const payload = recommendationsQuery.data
  if (!payload) {
    return (
      <EmptyState
        title={t('contentRecommendations.emptyTitle')}
        description={t('contentRecommendations.emptyDescription')}
      />
    )
  }

  if (!payload.context.active_crawl_id) {
    return (
      <EmptyState
        title={t('contentRecommendations.noActiveCrawlTitle')}
        description={t('contentRecommendations.noActiveCrawlDescription')}
      />
    )
  }

  const summaryTypeEntries = Object.entries(payload.summary.counts_by_type).filter(([, count]) => count > 0)
  const summaryPageTypeEntries = Object.entries(payload.summary.counts_by_page_type).filter(([, count]) => count > 0)
  const implementedTrackedCount = payload.implemented_summary.total_count
  const implementedSummaryItems = buildImplementedSummaryItems(t, payload.implemented_summary)
  const routeContext = {
    activeCrawlId,
    baselineCrawlId,
  }
  const confidenceInputValue =
    recommendationParams.confidence_min !== undefined
      ? String(Math.round(recommendationParams.confidence_min * 100))
      : ''
  const showImplementedSection =
    mode === 'implemented' ||
    payload.summary.implemented_recommendations > 0 ||
    payload.implemented_items.length > 0
  const showImplementedSummaryBar = implementedTrackedCount > 0
  const implementedStatusDrilldownActive = recommendationParams.implemented_status_filter !== 'all'
  const implementedEmptyTitle =
    implementedStatusDrilldownActive && implementedTrackedCount > 0
      ? t('contentRecommendations.implemented.emptyStatusDrilldownTitle')
      : t('contentRecommendations.implemented.emptyFilteredTitle')
  const implementedEmptyDescription =
    implementedStatusDrilldownActive && implementedTrackedCount > 0
      ? t('contentRecommendations.implemented.emptyStatusDrilldownDescription')
      : t('contentRecommendations.implemented.emptyFilteredDescription')
  const headerTitle =
    mode === 'active'
      ? t('contentRecommendations.views.active.title')
      : mode === 'implemented'
        ? t('contentRecommendations.views.implemented.title')
        : t('contentRecommendations.views.overview.title')
  const headerDescription =
    mode === 'active'
      ? t('contentRecommendations.views.active.description')
      : mode === 'implemented'
        ? t('contentRecommendations.views.implemented.description')
        : t('contentRecommendations.views.overview.description')

  function handleMarkDone(item: ContentRecommendation) {
    markDoneMutation.mutate({
      recommendation_key: item.recommendation_key,
      active_crawl_id: recommendationParams.active_crawl_id,
      baseline_crawl_id: recommendationParams.baseline_crawl_id,
      gsc_date_range: recommendationParams.gsc_date_range,
    })
  }

  return (
    <div className="space-y-6">
      <section className={recommendationSurfaceClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700 dark:text-teal-300">
              {t('contentRecommendations.views.eyebrow')}
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950 dark:text-slate-50">
              {headerTitle}
            </h1>
            <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
              {headerDescription}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {mode !== 'active' ? (
              <Link
                to={buildSiteContentRecommendationsActivePath(site.id, routeContext)}
                className={recommendationActionClass}
              >
                {t('contentRecommendations.actions.openActive')}
              </Link>
            ) : null}
            {mode !== 'implemented' ? (
              <Link
                to={buildSiteContentRecommendationsImplementedPath(site.id, routeContext)}
                className={recommendationActionClass}
              >
                {t('contentRecommendations.actions.openImplemented')}
              </Link>
            ) : null}
            <Link
              to={buildSitePagesRecordsPath(site.id, routeContext)}
              className={recommendationActionClass}
            >
              {t('contentRecommendations.actions.openPages')}
            </Link>
            <Link
              to={buildSiteCompetitiveGapPath(site.id, routeContext)}
              className={recommendationActionClass}
            >
              {t('contentRecommendations.actions.openCompetitiveGap')}
            </Link>
            <a
              href={buildExportHref(site.id, recommendationParams)}
              className={recommendationActionClass}
            >
              {t('contentRecommendations.actions.export')}
            </a>
          </div>
        </div>
      </section>

      <SummaryCards
        items={
          mode === 'implemented'
            ? [
                { label: t('contentRecommendations.summary.implemented'), value: payload.summary.implemented_recommendations },
                { label: t('contentRecommendations.implemented.summaryTotal'), value: implementedTrackedCount },
                { label: t('contentRecommendations.implemented.summaryImproved'), value: payload.implemented_summary.status_counts.improved },
                { label: t('contentRecommendations.implemented.summaryTooEarly'), value: payload.implemented_summary.status_counts.too_early },
                { label: t('contentRecommendations.summary.range'), value: recommendationParams.gsc_date_range === 'last_90_days' ? '90d' : '28d' },
              ]
            : [
                { label: t('contentRecommendations.summary.totalRecommendations'), value: payload.summary.total_recommendations },
                { label: t('contentRecommendations.summary.implemented'), value: payload.summary.implemented_recommendations },
                { label: t('contentRecommendations.summary.highPriority'), value: payload.summary.high_priority_recommendations },
                { label: t('contentRecommendations.summary.clustersCovered'), value: payload.summary.clusters_covered },
                { label: t('contentRecommendations.summary.createNewPage'), value: payload.summary.create_new_page_recommendations },
                { label: t('contentRecommendations.summary.expandExistingPage'), value: payload.summary.expand_existing_page_recommendations },
                { label: t('contentRecommendations.summary.strengthenCluster'), value: payload.summary.strengthen_cluster_recommendations },
                { label: t('contentRecommendations.summary.internalSupport'), value: payload.summary.improve_internal_support_recommendations },
                { label: t('contentRecommendations.summary.range'), value: recommendationParams.gsc_date_range === 'last_90_days' ? '90d' : '28d' },
              ]
        }
      />

      {mode === 'overview' ? (
        <>
          <section className={recommendationSectionClass}>
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                  {t('contentRecommendations.overview.lifecycleTitle')}
                </h2>
                <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                  {t('contentRecommendations.overview.lifecycleDescription')}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {implementedSummaryItems.slice(0, 4).map((item) => (
                  <span key={item.key}>
                    {renderSummaryPill(item.label, item.count, item.tone)}
                  </span>
                ))}
              </div>
            </div>
          </section>

          <section className={recommendationSectionClass}>
            <div className="flex flex-col gap-2">
              <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                {t('contentRecommendations.overview.shortcutsTitle')}
              </h2>
              <p className="text-sm text-stone-600 dark:text-slate-300">
                {t('contentRecommendations.overview.shortcutsDescription')}
              </p>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link to={buildSiteContentRecommendationsActivePath(site.id, routeContext)} className={recommendationActionClass}>
                {t('contentRecommendations.actions.openActive')}
              </Link>
              <Link to={buildSiteContentRecommendationsImplementedPath(site.id, routeContext)} className={recommendationActionClass}>
                {t('contentRecommendations.actions.openImplemented')}
              </Link>
              <Link to={buildSitePagesRecordsPath(site.id, routeContext)} className={recommendationActionClass}>
                {t('contentRecommendations.actions.openPages')}
              </Link>
              <Link to={buildSiteCompetitiveGapPath(site.id, routeContext)} className={recommendationActionClass}>
                {t('contentRecommendations.actions.openCompetitiveGap')}
              </Link>
            </div>
          </section>

          <section className={recommendationSectionClass}>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className={recommendationPanelClass}>
                <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                  {t('contentRecommendations.overview.activeNow')}
                </p>
                <p className="mt-2 text-sm text-stone-700 dark:text-slate-300">
                  {payload.summary.total_recommendations > 0
                    ? t('contentRecommendations.overview.activeNowDescription', {
                        count: payload.summary.total_recommendations,
                      })
                    : t('contentRecommendations.emptyDescription')}
                </p>
              </div>
              <div className={recommendationPanelClass}>
                <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                  {t('contentRecommendations.overview.implementedNow')}
                </p>
                <p className="mt-2 text-sm text-stone-700 dark:text-slate-300">
                  {implementedTrackedCount > 0
                    ? t('contentRecommendations.overview.implementedNowDescription', {
                        count: implementedTrackedCount,
                      })
                    : t('contentRecommendations.implemented.emptyFilteredDescription')}
                </p>
              </div>
            </div>
          </section>
        </>
      ) : (
        <QuickFilterBar title={t('contentRecommendations.quickFilters.title')} items={quickFilters} />
      )}

      {mode === 'active' ? (
      <FilterPanel
        title={t('contentRecommendations.filters.title')}
        description={t('contentRecommendations.filters.description')}
        onReset={resetFilters}
      >
        <label className={recommendationFieldLabelClass}>
          <span>{t('contentRecommendations.filters.dateRange')}</span>
          <select
            value={recommendationParams.gsc_date_range}
            onChange={(event) => updateFilter({ gsc_date_range: event.target.value })}
            className={recommendationFieldControlClass}
          >
            <option value="last_28_days">{t('contentRecommendations.filters.last28Days')}</option>
            <option value="last_90_days">{t('contentRecommendations.filters.last90Days')}</option>
          </select>
        </label>

        <label className={recommendationFieldLabelClass}>
          <span>{t('contentRecommendations.filters.recommendationType')}</span>
          <select
            value={recommendationParams.recommendation_type ?? ''}
            onChange={(event) => updateFilter({ recommendation_type: event.target.value || undefined })}
            className={recommendationFieldControlClass}
          >
            <option value="">{t('common.any')}</option>
            {recommendationTypes.map((type) => (
              <option key={type} value={type}>
                {recommendationTypeLabel(t, type)}
              </option>
            ))}
          </select>
        </label>

        <label className={recommendationFieldLabelClass}>
          <span>{t('contentRecommendations.filters.segment')}</span>
          <select
            value={recommendationParams.segment ?? ''}
            onChange={(event) => updateFilter({ segment: event.target.value || undefined })}
            className={recommendationFieldControlClass}
          >
            <option value="">{t('common.any')}</option>
            {recommendationSegments.map((segment) => (
              <option key={segment} value={segment}>
                {recommendationSegmentLabel(t, segment)}
              </option>
            ))}
          </select>
        </label>

        <label className={recommendationFieldLabelClass}>
          <span>{t('contentRecommendations.filters.pageType')}</span>
          <select
            value={recommendationParams.page_type ?? ''}
            onChange={(event) => updateFilter({ page_type: event.target.value || undefined })}
            className={recommendationFieldControlClass}
          >
            <option value="">{t('common.any')}</option>
            {pageTypes.map((pageType) => (
              <option key={pageType} value={pageType}>
                {pageTypeLabel(t, pageType)}
              </option>
            ))}
          </select>
        </label>

        <label className={recommendationFieldLabelClass}>
          <span>{t('contentRecommendations.filters.cluster')}</span>
          <input
            type="text"
            value={recommendationParams.cluster ?? ''}
            onChange={(event) => updateFilter({ cluster: event.target.value || undefined })}
            className={recommendationFieldControlClass}
            placeholder={t('contentRecommendations.filters.clusterPlaceholder')}
          />
        </label>

        <label className={recommendationFieldLabelClass}>
          <span>{t('contentRecommendations.filters.confidenceMin')}</span>
          <input
            type="number"
            min={0}
            max={100}
            step={1}
            value={confidenceInputValue}
            onChange={(event) =>
              updateFilter({
                confidence_min: event.target.value ? Math.min(1, Number(event.target.value) / 100) : undefined,
              })
            }
            className={recommendationFieldControlClass}
            placeholder="70"
          />
        </label>

        <label className={recommendationFieldLabelClass}>
          <span>{t('contentRecommendations.filters.priorityMin')}</span>
          <input
            type="number"
            min={0}
            max={100}
            step={1}
            value={recommendationParams.priority_score_min ?? ''}
            onChange={(event) => updateFilter({ priority_score_min: event.target.value || undefined })}
            className={recommendationFieldControlClass}
            placeholder="70"
          />
        </label>

        <label className={recommendationFieldLabelClass}>
          <span>{t('contentRecommendations.filters.sortBy')}</span>
          <select
            value={recommendationParams.sort_by}
            onChange={(event) => updateFilter({ sort_by: event.target.value })}
            className={recommendationFieldControlClass}
          >
            <option value="priority_score">{t('contentRecommendations.filters.sort.priorityScore')}</option>
            <option value="confidence">{t('contentRecommendations.filters.sort.confidence')}</option>
            <option value="impact">{t('contentRecommendations.filters.sort.impact')}</option>
            <option value="effort">{t('contentRecommendations.filters.sort.effort')}</option>
            <option value="cluster_label">{t('contentRecommendations.filters.sort.cluster')}</option>
            <option value="recommendation_type">{t('contentRecommendations.filters.sort.type')}</option>
            <option value="page_type">{t('contentRecommendations.filters.sort.pageType')}</option>
          </select>
        </label>

        <label className={recommendationFieldLabelClass}>
          <span>{t('contentRecommendations.filters.sortOrder')}</span>
          <select
            value={recommendationParams.sort_order}
            onChange={(event) => updateFilter({ sort_order: event.target.value as SortOrder })}
            className={recommendationFieldControlClass}
          >
            <option value="desc">{t('sort.descending')}</option>
            <option value="asc">{t('sort.ascending')}</option>
          </select>
        </label>
      </FilterPanel>
      ) : null}

      {mode === 'active' ? (
      <section className={recommendationSectionClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
              {t('contentRecommendations.mix.title')}
            </h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
              {t('contentRecommendations.mix.description')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {summaryTypeEntries.map(([type, count]) => (
              <span key={type}>
                {renderBadge(`${recommendationTypeLabel(t, type as ContentRecommendationType)}: ${count}`)}
              </span>
            ))}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {summaryPageTypeEntries.map(([pageType, count]) => (
            <span key={pageType}>
              {renderBadge(`${pageTypeLabel(t, pageType as PageType)}: ${count}`, 'teal')}
            </span>
          ))}
        </div>
      </section>
      ) : null}

      {mode === 'active' ? (
      <section className="space-y-4">
        <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
              {t('contentRecommendations.active.title')}
            </h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
              {t('contentRecommendations.active.description')}
            </p>
          </div>
          <span>{renderBadge(`${t('contentRecommendations.active.visible')}: ${payload.total_items}`, 'stone')}</span>
        </div>

        {markDoneMutation.isError ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
            {getUiErrorMessage(markDoneMutation.error, t)}
          </div>
        ) : null}

        {payload.items.length === 0 ? (
          <EmptyState
            title={t('contentRecommendations.emptyTitle')}
            description={t('contentRecommendations.emptyDescription')}
          />
        ) : (
          <div className="space-y-4">
            {payload.items.map((item) => {
              const markDonePending =
                markDoneMutation.isPending &&
                markDoneMutation.variables?.recommendation_key === item.recommendation_key

              return (
                <article key={item.recommendation_key} className={recommendationArticleClass}>
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {renderBadge(
                      recommendationTypeLabel(t, item.recommendation_type),
                      recommendationTypeTone(item.recommendation_type),
                    )}
                    {renderBadge(recommendationSegmentLabel(t, item.segment), 'stone')}
                    {renderBadge(pageTypeLabel(t, item.page_type), 'teal')}
                    {renderBadge(`${t('contentRecommendations.card.priority')} ${item.priority_score}`, 'amber')}
                    {renderBadge(`${t('contentRecommendations.card.confidence')} ${formatPercent(item.confidence, 0)}`)}
                    {item.was_implemented_before && item.previously_implemented_at
                      ? renderBadge(
                          t('contentRecommendations.card.previouslyImplemented', {
                            date: formatDateTime(item.previously_implemented_at),
                          }),
                          'stone',
                        )
                      : null}
                  </div>
                  <div>
                    <button
                      type="button"
                      onClick={() => updateFilter({ cluster: item.cluster_label })}
                      className="text-left text-2xl font-semibold tracking-tight text-stone-950 transition hover:text-teal-700 dark:text-slate-50 dark:hover:text-teal-300"
                    >
                      {item.cluster_label}
                    </button>
                    <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">{item.rationale}</p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => handleMarkDone(item)}
                    disabled={markDonePending}
                    className={recommendationActionClass}
                  >
                    {markDonePending
                      ? t('contentRecommendations.card.markingDone')
                      : t('contentRecommendations.card.markDone')}
                  </button>
                  {item.target_url ? (
                    <>
                      <a
                        href={item.target_url}
                        className={recommendationActionClass}
                      >
                        {t('contentRecommendations.card.openTarget')}
                      </a>
                      <Link
                        to={buildPagesLink(site.id, item.target_url, activeCrawlId, baselineCrawlId)}
                        className={recommendationActionClass}
                      >
                        {t('contentRecommendations.card.openInPages')}
                      </Link>
                    </>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className={recommendationPanelClass}>
                  <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                    {t('contentRecommendations.card.targetPage')}
                  </p>
                  <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">{item.target_url ?? '-'}</p>
                  <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">
                    {t('contentRecommendations.card.targetPageType')}: {pageTypeLabel(t, item.target_page_type)}
                  </p>
                  <p className="mt-1 text-xs text-stone-600 dark:text-slate-300">
                    {t('contentRecommendations.card.suggestedPageType')}:{' '}
                    {item.suggested_page_type ? pageTypeLabel(t, item.suggested_page_type) : '-'}
                  </p>
                </div>

                <div className={recommendationPanelClass}>
                  <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                    {t('contentRecommendations.card.impactEffort')}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {renderBadge(
                      `${t('contentRecommendations.card.impact')} ${t(`opportunities.impactLevel.${item.impact}`)}`,
                      impactTone(item.impact),
                    )}
                    {renderBadge(
                      `${t('contentRecommendations.card.effort')} ${t(`opportunities.effortLevel.${item.effort}`)}`,
                      effortTone(item.effort),
                    )}
                  </div>
                </div>

                <div className={recommendationPanelClass}>
                  <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                    {t('contentRecommendations.card.clusterScores')}
                  </p>
                  <dl className="mt-2 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                    <div className="flex items-center justify-between gap-3">
                      <dt>{t('contentRecommendations.card.clusterStrength')}</dt>
                      <dd className="font-medium text-stone-950 dark:text-slate-50">{item.cluster_strength}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt>{t('contentRecommendations.card.coverageGap')}</dt>
                      <dd className="font-medium text-stone-950 dark:text-slate-50">{item.coverage_gap_score}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <dt>{t('contentRecommendations.card.internalSupport')}</dt>
                      <dd className="font-medium text-stone-950 dark:text-slate-50">{item.internal_support_score}</dd>
                    </div>
                  </dl>
                </div>

                <div className={recommendationPanelClass}>
                  <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                    {t('contentRecommendations.card.cluster')}
                  </p>
                  <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">{item.cluster_label}</p>
                  <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">
                    {t('contentRecommendations.card.clusterKey')}: {item.cluster_key}
                  </p>
                </div>
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <section className={recommendationPanelClass}>
                  <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                    {t('contentRecommendations.card.reasons')}
                  </h3>
                  <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                    {item.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </section>

                <section className={recommendationPanelClass}>
                  <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                    {t('contentRecommendations.card.signals')}
                  </h3>
                  <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                    {item.signals.map((signal) => (
                      <li key={signal}>{signal}</li>
                    ))}
                  </ul>
                </section>
              </div>

              {item.prerequisites.length > 0 || item.supporting_urls.length > 0 ? (
                <div className="mt-4 grid gap-4 xl:grid-cols-2">
                  <section className={recommendationPanelClass}>
                    <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                      {t('contentRecommendations.card.prerequisites')}
                    </h3>
                    {item.prerequisites.length === 0 ? (
                      <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                        {t('contentRecommendations.card.none')}
                      </p>
                    ) : (
                      <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                        {item.prerequisites.map((prerequisite) => (
                          <li key={prerequisite}>{prerequisite}</li>
                        ))}
                      </ul>
                    )}
                  </section>

                  <section className={recommendationPanelClass}>
                    <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                      {t('contentRecommendations.card.supportingUrls')}
                    </h3>
                    {item.supporting_urls.length === 0 ? (
                      <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                        {t('contentRecommendations.card.none')}
                      </p>
                    ) : (
                      <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                        {item.supporting_urls.map((url) => (
                          <li key={url}>
                            <a
                              href={url}
                              className="break-all text-teal-700 transition hover:text-teal-600 dark:text-teal-300 dark:hover:text-teal-200"
                            >
                              {url}
                            </a>
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                </div>
              ) : null}

              {item.url_improvement_helper ? (
                <details className="mt-4 rounded-3xl border border-stone-200 bg-stone-50/90 dark:border-slate-800 dark:bg-slate-900/85">
                  <summary className="cursor-pointer list-none px-4 py-4">
                    <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                          {t('contentRecommendations.helper.title')}
                        </p>
                        <p className="mt-1 text-xs text-stone-600 dark:text-slate-300">
                          {item.url_improvement_helper.title ?? item.url_improvement_helper.target_url}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {renderBadge(pageTypeLabel(t, item.url_improvement_helper.page_type), 'teal')}
                        {item.url_improvement_helper.page_bucket
                          ? renderBadge(pageBucketLabel(t, item.url_improvement_helper.page_bucket), 'stone')
                          : null}
                      </div>
                    </div>
                  </summary>

                  <div className="border-t border-stone-200 px-4 pb-4 pt-4 dark:border-slate-800">
                    <div className="grid gap-4 xl:grid-cols-2">
                      <section className={recommendationPanelClass}>
                        <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                          {t('contentRecommendations.helper.openIssues')}
                        </h3>
                        {item.url_improvement_helper.open_issues.length === 0 ? (
                          <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                            {t('contentRecommendations.card.none')}
                          </p>
                        ) : (
                          <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                            {item.url_improvement_helper.open_issues.map((issue) => (
                              <li key={issue}>{issue}</li>
                            ))}
                          </ul>
                        )}
                      </section>

                      <section className={recommendationPanelClass}>
                        <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                          {t('contentRecommendations.helper.improvementActions')}
                        </h3>
                        {item.url_improvement_helper.improvement_actions.length === 0 ? (
                          <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                            {t('contentRecommendations.card.none')}
                          </p>
                        ) : (
                          <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                            {item.url_improvement_helper.improvement_actions.map((action) => (
                              <li key={action}>{action}</li>
                            ))}
                          </ul>
                        )}
                      </section>
                    </div>

                    <div className="mt-4 grid gap-4 xl:grid-cols-2">
                      <section className={recommendationPanelClass}>
                        <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                          {t('contentRecommendations.helper.supportingSignals')}
                        </h3>
                        <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                          {item.url_improvement_helper.supporting_signals.map((signal) => (
                            <li key={signal}>{signal}</li>
                          ))}
                        </ul>
                      </section>

                      <section className={recommendationPanelClass}>
                        <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                          {t('contentRecommendations.helper.gscContext')}
                        </h3>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.gscImpressions')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.gsc_context.impressions}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.gscClicks')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.gsc_context.clicks}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.gscCtr')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {formatPercent(item.url_improvement_helper.gsc_context.ctr)}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.gscPosition')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.gsc_context.position?.toFixed(1) ?? '-'}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.gscTopQueries')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.gsc_context.top_queries_count}
                            </dd>
                          </div>
                        </dl>
                        {item.url_improvement_helper.gsc_context.notes.length > 0 ? (
                          <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                            {item.url_improvement_helper.gsc_context.notes.map((note) => (
                              <li key={note}>{note}</li>
                            ))}
                          </ul>
                        ) : null}
                      </section>
                    </div>

                    <div className="mt-4 grid gap-4 xl:grid-cols-2">
                      <section className={recommendationPanelClass}>
                        <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                          {t('contentRecommendations.helper.internalLinkingContext')}
                        </h3>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.internalScore')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.internal_linking_context.internal_linking_score}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.internalIssues')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.internal_linking_context.issue_count}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.internalLinks')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.internal_linking_context.incoming_internal_links}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.internalLinkingPages')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.internal_linking_context.incoming_internal_linking_pages}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.linkEquity')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.internal_linking_context.link_equity_score.toFixed(2)}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>{t('contentRecommendations.helper.anchorDiversity')}</dt>
                            <dd className="font-medium text-stone-950 dark:text-slate-50">
                              {item.url_improvement_helper.internal_linking_context.anchor_diversity_score.toFixed(2)}
                            </dd>
                          </div>
                        </dl>
                        {item.url_improvement_helper.internal_linking_context.issue_types.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {item.url_improvement_helper.internal_linking_context.issue_types.map((issueType) => (
                              <span key={issueType}>
                                {renderBadge(internalIssueTypeLabel(t, issueType), 'teal')}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </section>

                      <section className={recommendationPanelClass}>
                        <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                          {t('contentRecommendations.helper.cannibalizationContext')}
                        </h3>
                        {item.url_improvement_helper.cannibalization_context.has_active_signals ? (
                          <>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {item.url_improvement_helper.cannibalization_context.severity
                                ? renderBadge(
                                    t(
                                      `cannibalization.severity.${item.url_improvement_helper.cannibalization_context.severity}`,
                                    ),
                                    'amber',
                                  )
                                : null}
                              {renderBadge(
                                `${t('contentRecommendations.helper.competingUrls')} ${item.url_improvement_helper.cannibalization_context.competing_urls_count}`,
                                'stone',
                              )}
                            </div>
                            <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                              <div className="flex items-center justify-between gap-3">
                                <dt>{t('contentRecommendations.helper.sharedQueries')}</dt>
                                <dd className="font-medium text-stone-950 dark:text-slate-50">
                                  {item.url_improvement_helper.cannibalization_context.common_queries_count}
                                </dd>
                              </div>
                            </dl>
                            {item.url_improvement_helper.cannibalization_context.strongest_competing_url ? (
                              <p className="mt-3 break-all text-sm text-stone-700 dark:text-slate-300">
                                {item.url_improvement_helper.cannibalization_context.strongest_competing_url}
                              </p>
                            ) : null}
                            {item.url_improvement_helper.cannibalization_context.shared_top_queries.length > 0 ? (
                              <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                                {item.url_improvement_helper.cannibalization_context.shared_top_queries.map((query) => (
                                  <li key={query}>{query}</li>
                                ))}
                              </ul>
                            ) : null}
                          </>
                        ) : (
                          <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                            {t('contentRecommendations.helper.noCannibalization')}
                          </p>
                        )}
                      </section>
                    </div>
                  </div>
                </details>
              ) : null}
                </article>
              )
            })}
          </div>
        )}
      </section>
      ) : null}

      {mode === 'implemented' && showImplementedSection ? (
        <section className={recommendationSectionClass}>
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                {t('contentRecommendations.implemented.title')}
              </h2>
              <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                {t('contentRecommendations.implemented.description', {
                  count: implementedTrackedCount,
                })}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span>{renderBadge(`${t('contentRecommendations.implemented.visible')}: ${payload.implemented_total}`)}</span>
            </div>
          </div>

          <div className="mt-4">
            <FilterPanel
              title={t('contentRecommendations.implemented.filtersTitle')}
              description={t('contentRecommendations.implemented.filtersDescription')}
              onReset={resetImplementedFilters}
              bodyClassName="grid gap-3 md:grid-cols-2 xl:grid-cols-5"
            >
              <label className={recommendationFieldLabelClass}>
                <span>{t('contentRecommendations.implemented.windowLabel')}</span>
                <select
                  aria-label={t('contentRecommendations.implemented.windowLabel')}
                  value={recommendationParams.implemented_outcome_window}
                  onChange={(event) => updateImplementedFilters({ implemented_outcome_window: event.target.value })}
                  className={recommendationFieldControlClass}
                >
                  {implementedOutcomeWindows.map((window) => (
                    <option key={window} value={window}>
                      {outcomeWindowLabel(t, window)}
                    </option>
                  ))}
                </select>
              </label>

              <label className={recommendationFieldLabelClass}>
                <span>{t('contentRecommendations.implemented.statusFilterLabel')}</span>
                <select
                  aria-label={t('contentRecommendations.implemented.statusFilterLabel')}
                  value={recommendationParams.implemented_status_filter}
                  onChange={(event) =>
                    updateImplementedFilters({ implemented_status_filter: event.target.value || undefined })
                  }
                  className={recommendationFieldControlClass}
                >
                  {implementedStatusFilters.map((status) => (
                    <option key={status} value={status}>
                      {status === 'all'
                        ? t('common.any')
                        : outcomeStatusLabel(t, status as ContentRecommendationOutcomeStatus)}
                    </option>
                  ))}
                </select>
              </label>

              <label className={recommendationFieldLabelClass}>
                <span>{t('contentRecommendations.implemented.modeFilterLabel')}</span>
                <select
                  aria-label={t('contentRecommendations.implemented.modeFilterLabel')}
                  value={recommendationParams.implemented_mode_filter}
                  onChange={(event) =>
                    updateImplementedFilters({ implemented_mode_filter: event.target.value || undefined })
                  }
                  className={recommendationFieldControlClass}
                >
                  {implementedModeFilters.map((mode) => (
                    <option key={mode} value={mode}>
                      {mode === 'all'
                        ? t('common.any')
                        : outcomeKindLabel(t, mode as ContentRecommendationOutcomeKind)}
                    </option>
                  ))}
                </select>
              </label>

              <label className={recommendationFieldLabelClass}>
                <span>{t('contentRecommendations.implemented.searchLabel')}</span>
                <input
                  aria-label={t('contentRecommendations.implemented.searchLabel')}
                  type="text"
                  value={recommendationParams.implemented_search ?? ''}
                  onChange={(event) =>
                    updateImplementedFilters({ implemented_search: event.target.value || undefined })
                  }
                  className={recommendationFieldControlClass}
                  placeholder={t('contentRecommendations.implemented.searchPlaceholder')}
                />
              </label>

              <label className={recommendationFieldLabelClass}>
                <span>{t('contentRecommendations.implemented.sortLabel')}</span>
                <select
                  aria-label={t('contentRecommendations.implemented.sortLabel')}
                  value={recommendationParams.implemented_sort}
                  onChange={(event) => updateImplementedFilters({ implemented_sort: event.target.value })}
                  className={recommendationFieldControlClass}
                >
                  <option value="implemented_at_desc">
                    {t('contentRecommendations.implemented.sort.implementedAtDesc')}
                  </option>
                  <option value="implemented_at_asc">
                    {t('contentRecommendations.implemented.sort.implementedAtAsc')}
                  </option>
                  <option value="outcome">{t('contentRecommendations.implemented.sort.outcome')}</option>
                  <option value="recommendation_type">
                    {t('contentRecommendations.implemented.sort.recommendationType')}
                  </option>
                  <option value="title">{t('contentRecommendations.implemented.sort.title')}</option>
                </select>
              </label>
            </FilterPanel>
          </div>

          {showImplementedSummaryBar ? (
            <div
              className="mt-4 rounded-3xl border border-stone-200 bg-stone-50/80 p-4 dark:border-slate-800 dark:bg-slate-900/70"
              data-testid="implemented-summary-bar"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                {t('contentRecommendations.implemented.summaryTitle')}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {implementedSummaryItems.map((item) => (
                  <span key={item.key}>
                    {renderSummaryPill(item.label, item.count, item.tone, {
                      muted: item.count === 0 && recommendationParams.implemented_status_filter !== item.statusFilter,
                      active: recommendationParams.implemented_status_filter === item.statusFilter,
                      disabled:
                        item.statusFilter !== 'all' &&
                        item.count === 0 &&
                        recommendationParams.implemented_status_filter !== item.statusFilter,
                      onClick: () => applyImplementedSummaryFilter(item.statusFilter),
                    })}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          {payload.implemented_items.length === 0 ? (
            <div className="mt-4 rounded-3xl border border-dashed border-stone-300 bg-stone-50/70 px-5 py-6 text-sm text-stone-600 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-300">
              <p className="font-medium text-stone-900 dark:text-slate-50">
                {implementedEmptyTitle}
              </p>
              <p className="mt-2">{implementedEmptyDescription}</p>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {payload.implemented_items.map((item) => (
              <details
                key={item.recommendation_key}
                className="rounded-[28px] border border-stone-300 bg-white/90 shadow-sm dark:border-slate-800 dark:bg-slate-950/85"
              >
                <summary className="cursor-pointer list-none px-5 py-4">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap gap-2">
                        {renderBadge(
                          recommendationTypeLabel(t, item.recommendation_type),
                          recommendationTypeTone(item.recommendation_type),
                        )}
                        {item.segment ? renderBadge(recommendationSegmentLabel(t, item.segment), 'stone') : null}
                        {renderBadge(outcomeKindLabel(t, item.primary_outcome_kind), 'stone')}
                        {renderBadge(outcomeWindowLabel(t, item.outcome_window), 'stone')}
                        {renderBadge(outcomeStatusLabel(t, item.outcome_status), outcomeTone(item.outcome_status))}
                      </div>
                      <p className="text-base font-semibold text-stone-950 dark:text-slate-50">
                        {implementedRecommendationHeading(item)}
                      </p>
                      {(item.target_title_snapshot || item.target_url || implementedRecommendationContext(item)) ? (
                        <p className="text-sm text-stone-600 dark:text-slate-300">
                          {item.target_title_snapshot ?? implementedRecommendationContext(item)}
                          {item.target_title_snapshot && item.target_url ? ' · ' : ''}
                          {item.target_url ?? (!item.target_title_snapshot ? implementedRecommendationContext(item) : '')}
                        </p>
                      ) : null}
                    </div>

                    <div className="grid gap-1 text-sm text-stone-700 dark:text-slate-300 xl:text-right">
                      <span className="font-medium text-stone-950 dark:text-slate-50">{item.outcome_summary}</span>
                      <span>
                        {t('contentRecommendations.implemented.implementedAt')} {formatDateTime(item.implemented_at)}
                      </span>
                    </div>
                  </div>
                </summary>

                <div className="border-t border-stone-200 px-5 pb-5 pt-4 dark:border-slate-800">
                  {item.is_too_early ? (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                      <p className="font-medium">{item.outcome_summary}</p>
                      <p className="mt-1">
                        {t('contentRecommendations.implemented.tooEarlyMessage', {
                          window: outcomeWindowLabel(t, item.outcome_window),
                          days: item.days_since_implemented ?? 0,
                        })}
                      </p>
                    </div>
                  ) : null}

                  <div className="grid gap-4 xl:grid-cols-2">
                    <section className={recommendationPanelClass}>
                      <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                        {t('contentRecommendations.implemented.outcomeDetails')}
                      </h3>
                      <p className="mt-2 text-xs text-stone-600 dark:text-slate-400">
                        {t('contentRecommendations.implemented.windowApplied', {
                          window: outcomeWindowLabel(t, item.outcome_window),
                          days: item.days_since_implemented ?? 0,
                        })}
                      </p>
                      {item.outcome_details.length === 0 ? (
                        <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">{item.outcome_summary}</p>
                      ) : (
                        <div className="mt-3 space-y-3">
                          {item.outcome_details.map((detail) => (
                            <div
                              key={`${detail.label}:${detail.before ?? '-'}:${detail.after ?? '-'}`}
                              className="rounded-2xl border border-stone-200 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-950/60"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <p className="text-sm font-medium text-stone-900 dark:text-slate-50">{detail.label}</p>
                                {detail.change ? (
                                  <span className="text-xs text-stone-600 dark:text-slate-300">{detail.change}</span>
                                ) : null}
                              </div>
                              <div className="mt-2 grid gap-2 text-sm text-stone-700 dark:text-slate-300 sm:grid-cols-2">
                                <p>
                                  {t('contentRecommendations.implemented.before')}: {detail.before ?? '-'}
                                </p>
                                <p>
                                  {t('contentRecommendations.implemented.after')}: {detail.after ?? '-'}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>

                    <section className={recommendationPanelClass}>
                      <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                        {t('contentRecommendations.implemented.snapshot')}
                      </h3>
                      <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                        <div className="flex items-center justify-between gap-3">
                          <dt>{t('contentRecommendations.implemented.implementedAtLabel')}</dt>
                          <dd className="font-medium text-stone-950 dark:text-slate-50">
                            {formatDateTime(item.implemented_at)}
                          </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt>{t('contentRecommendations.implemented.modeLabel')}</dt>
                          <dd className="font-medium text-stone-950 dark:text-slate-50">
                            {outcomeKindLabel(t, item.primary_outcome_kind)}
                          </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt>{t('contentRecommendations.implemented.windowLabel')}</dt>
                          <dd className="font-medium text-stone-950 dark:text-slate-50">
                            {outcomeWindowLabel(t, item.outcome_window)}
                          </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt>{t('contentRecommendations.implemented.daysSinceImplemented')}</dt>
                          <dd className="font-medium text-stone-950 dark:text-slate-50">
                            {item.days_since_implemented ?? '-'}
                          </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt>{t('contentRecommendations.implemented.eligibleForWindow')}</dt>
                          <dd className="font-medium text-stone-950 dark:text-slate-50">
                            {item.eligible_for_window ? t('common.yes') : t('common.no')}
                          </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt>{t('contentRecommendations.implemented.implementedCrawl')}</dt>
                          <dd className="font-medium text-stone-950 dark:text-slate-50">
                            {item.implemented_crawl_job_id ?? '-'}
                          </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt>{t('contentRecommendations.implemented.baselineCrawl')}</dt>
                          <dd className="font-medium text-stone-950 dark:text-slate-50">
                            {item.implemented_baseline_crawl_job_id ?? '-'}
                          </dd>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <dt>{t('contentRecommendations.implemented.timesMarkedDone')}</dt>
                          <dd className="font-medium text-stone-950 dark:text-slate-50">{item.times_marked_done}</dd>
                        </div>
                      </dl>
                      {item.target_url ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          <a href={item.target_url} className={recommendationActionClass}>
                            {t('contentRecommendations.card.openTarget')}
                          </a>
                          <Link
                            to={buildPagesLink(site.id, item.target_url, activeCrawlId, baselineCrawlId)}
                            className={recommendationActionClass}
                          >
                            {t('contentRecommendations.card.openInPages')}
                          </Link>
                        </div>
                      ) : null}
                    </section>
                  </div>

                  {item.helper_snapshot ? (
                    <div className="mt-4 grid gap-4 xl:grid-cols-2">
                      <section className={recommendationPanelClass}>
                        <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                          {t('contentRecommendations.implemented.snapshotOpenIssues')}
                        </h3>
                        {item.helper_snapshot.open_issues.length === 0 ? (
                          <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                            {t('contentRecommendations.card.none')}
                          </p>
                        ) : (
                          <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                            {item.helper_snapshot.open_issues.map((issue) => (
                              <li key={issue}>{issue}</li>
                            ))}
                          </ul>
                        )}
                      </section>

                      <section className={recommendationPanelClass}>
                        <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                          {t('contentRecommendations.implemented.snapshotActions')}
                        </h3>
                        {item.helper_snapshot.improvement_actions.length === 0 ? (
                          <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                            {t('contentRecommendations.card.none')}
                          </p>
                        ) : (
                          <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                            {item.helper_snapshot.improvement_actions.map((action) => (
                              <li key={action}>{action}</li>
                            ))}
                          </ul>
                        )}
                      </section>
                    </div>
                  ) : null}

                  <div className="mt-4 grid gap-4 xl:grid-cols-2">
                    <section className={recommendationPanelClass}>
                      <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                        {t('contentRecommendations.card.reasons')}
                      </h3>
                      {item.reasons_snapshot.length === 0 ? (
                        <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                          {item.recommendation_text}
                        </p>
                      ) : (
                        <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                          {item.reasons_snapshot.map((reason) => (
                            <li key={reason}>{reason}</li>
                          ))}
                        </ul>
                      )}
                    </section>

                    <section className={recommendationPanelClass}>
                      <h3 className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                        {t('contentRecommendations.card.signals')}
                      </h3>
                      {item.signals_snapshot.length === 0 ? (
                        <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                          {t('contentRecommendations.card.none')}
                        </p>
                      ) : (
                        <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                          {item.signals_snapshot.map((signal) => (
                            <li key={signal}>{signal}</li>
                          ))}
                        </ul>
                      )}
                    </section>
                  </div>
                </div>
              </details>
            ))}
          </div>
          )}
        </section>
      ) : null}

      {mode !== 'overview' ? (
      <PaginationControls
        page={payload.page}
        pageSize={payload.page_size}
        totalItems={payload.total_items}
        totalPages={payload.total_pages}
        onPageChange={(page) => updateParams({ page })}
        onPageSizeChange={(pageSize) => updateParams({ page: 1, page_size: pageSize })}
      />
      ) : null}
    </div>
  )
}
