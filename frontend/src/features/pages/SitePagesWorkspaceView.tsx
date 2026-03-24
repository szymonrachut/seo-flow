import { startTransition, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { buildApiUrl } from '../../api/client'
import { DataTable } from '../../components/DataTable'
import { DataViewHeader } from '../../components/DataViewHeader'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { PaginationControls } from '../../components/PaginationControls'
import { QuickFilterBar } from '../../components/QuickFilterBar'
import { SummaryCards } from '../../components/SummaryCards'
import { UrlActions } from '../../components/UrlActions'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type {
  OpportunityType,
  PageBucket,
  PageRecord,
  PageTaxonomySummary,
  PagesQueryParams,
  PageType,
  PriorityLevel,
  SiteDetail,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatNullable, formatPercent, formatResponseTime } from '../../utils/format'
import { buildQueryString, mergeSearchParams, parseFloatParam, parseIntegerParam } from '../../utils/searchParams'
import {
  buildSiteChangesPagesPath,
  buildSitePagesPath,
  buildSitePagesRecordsPath,
} from '../sites/routes'
import { usePageTaxonomySummaryQuery, usePagesQuery } from './api'

interface SitePagesWorkspaceViewProps {
  site: SiteDetail
  mode: 'overview' | 'records'
}

const PAGE_TYPES: PageType[] = [
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
const PAGE_BUCKETS: PageBucket[] = ['commercial', 'informational', 'utility', 'trust', 'other']
const PRIORITY_LEVELS: PriorityLevel[] = ['critical', 'high', 'medium', 'low']
const OPPORTUNITY_TYPES: OpportunityType[] = [
  'QUICK_WINS',
  'HIGH_IMPRESSIONS_LOW_CTR',
  'TRAFFIC_WITH_TECHNICAL_ISSUES',
  'IMPORTANT_BUT_WEAK',
  'LOW_HANGING_FRUIT',
  'HIGH_RISK_PAGES',
  'UNDERLINKED_OPPORTUNITIES',
]

const DEFAULT_SORT_BY: PagesQueryParams['sort_by'] = 'priority_score'
const DEFAULT_SORT_ORDER = 'desc'
const DEFAULT_PAGE_SIZE = 25

function readBooleanParam(searchParams: URLSearchParams, key: string) {
  const value = searchParams.get(key)
  return value === null ? undefined : value === 'true'
}

function hasAdvancedFilterParams(params: PagesQueryParams) {
  return Boolean(
    params.url_contains ||
      params.title_contains ||
      params.page_type ||
      params.page_bucket ||
      params.page_type_confidence_min !== undefined ||
      params.page_type_confidence_max !== undefined ||
      params.has_title !== undefined ||
      params.has_meta_description !== undefined ||
      params.has_h1 !== undefined ||
      params.status_code !== undefined ||
      params.title_too_short !== undefined ||
      params.meta_too_short !== undefined ||
      params.missing_h2 !== undefined ||
      params.was_rendered !== undefined ||
      params.js_heavy_like !== undefined ||
      params.schema_present !== undefined ||
      params.noindex_like !== undefined ||
      params.non_indexable_like !== undefined ||
      params.has_technical_issue !== undefined ||
      params.has_gsc_data !== undefined ||
      params.has_cannibalization !== undefined ||
      params.priority_level ||
      params.opportunity_type ||
      params.priority_score_min !== undefined ||
      params.priority_score_max !== undefined ||
      params.gsc_impressions_min !== undefined ||
      params.gsc_ctr_max !== undefined ||
      params.gsc_position_min !== undefined ||
      params.gsc_top_queries_min !== undefined,
  )
}

function readPagesParams(searchParams: URLSearchParams, pageSize: number): PagesQueryParams {
  return {
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), pageSize),
    sort_by: (searchParams.get('sort_by') ?? DEFAULT_SORT_BY) as PagesQueryParams['sort_by'],
    sort_order: searchParams.get('sort_order') === 'asc' ? 'asc' : DEFAULT_SORT_ORDER,
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    url_contains: searchParams.get('url_contains') || undefined,
    title_contains: searchParams.get('title_contains') || undefined,
    page_type: (searchParams.get('page_type') as PageType) || undefined,
    page_bucket: (searchParams.get('page_bucket') as PageBucket) || undefined,
    page_type_confidence_min: parseFloatParam(searchParams.get('page_type_confidence_min'), undefined),
    page_type_confidence_max: parseFloatParam(searchParams.get('page_type_confidence_max'), undefined),
    has_title: readBooleanParam(searchParams, 'has_title'),
    has_meta_description: readBooleanParam(searchParams, 'has_meta_description'),
    has_h1: readBooleanParam(searchParams, 'has_h1'),
    status_code: parseIntegerParam(searchParams.get('status_code'), undefined),
    title_too_short: readBooleanParam(searchParams, 'title_too_short'),
    meta_too_short: readBooleanParam(searchParams, 'meta_too_short'),
    missing_h2: readBooleanParam(searchParams, 'missing_h2'),
    was_rendered: readBooleanParam(searchParams, 'was_rendered'),
    js_heavy_like: readBooleanParam(searchParams, 'js_heavy_like'),
    schema_present: readBooleanParam(searchParams, 'schema_present'),
    noindex_like: readBooleanParam(searchParams, 'noindex_like'),
    non_indexable_like: readBooleanParam(searchParams, 'non_indexable_like'),
    has_technical_issue: readBooleanParam(searchParams, 'has_technical_issue'),
    has_gsc_data: readBooleanParam(searchParams, 'has_gsc_data'),
    has_cannibalization: readBooleanParam(searchParams, 'has_cannibalization'),
    priority_level: (searchParams.get('priority_level') as PriorityLevel) || undefined,
    opportunity_type: (searchParams.get('opportunity_type') as OpportunityType) || undefined,
    priority_score_min: parseIntegerParam(searchParams.get('priority_score_min'), undefined),
    priority_score_max: parseIntegerParam(searchParams.get('priority_score_max'), undefined),
    gsc_impressions_min: parseIntegerParam(searchParams.get('gsc_impressions_min'), undefined),
    gsc_ctr_max: parseFloatParam(searchParams.get('gsc_ctr_max'), undefined),
    gsc_position_min: parseFloatParam(searchParams.get('gsc_position_min'), undefined),
    gsc_top_queries_min: parseIntegerParam(searchParams.get('gsc_top_queries_min'), undefined),
  }
}

function buildExportHref(activeCrawlId: number, params: PagesQueryParams, filtered: boolean) {
  const query = filtered ? buildQueryString(params) : ''
  return buildApiUrl(`/crawl-jobs/${activeCrawlId}/export/pages.csv${query ? `?${query}` : ''}`)
}

function pageTypeTone(pageType: PageType): 'stone' | 'rose' | 'amber' | 'teal' {
  if (pageType === 'product' || pageType === 'category') return 'amber'
  if (pageType === 'service' || pageType === 'location' || pageType === 'home') return 'teal'
  if (pageType === 'utility' || pageType === 'legal') return 'stone'
  return 'rose'
}

function pageBucketTone(pageBucket: PageBucket): 'stone' | 'rose' | 'amber' | 'teal' {
  if (pageBucket === 'commercial') return 'amber'
  if (pageBucket === 'informational') return 'teal'
  if (pageBucket === 'trust') return 'rose'
  return 'stone'
}

function priorityTone(level: PriorityLevel): 'stone' | 'rose' | 'amber' | 'teal' {
  if (level === 'critical') return 'rose'
  if (level === 'high') return 'amber'
  if (level === 'medium') return 'teal'
  return 'stone'
}

function opportunityTone(type: OpportunityType): 'stone' | 'rose' | 'amber' | 'teal' {
  if (type === 'HIGH_RISK_PAGES') return 'rose'
  if (type === 'QUICK_WINS' || type === 'LOW_HANGING_FRUIT') return 'amber'
  return 'teal'
}

function renderBadge(label: string, tone: 'stone' | 'rose' | 'amber' | 'teal' = 'stone') {
  const styles = {
    stone: 'border-stone-300 bg-stone-100 text-stone-700',
    rose: 'border-rose-200 bg-rose-50 text-rose-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    teal: 'border-teal-200 bg-teal-50 text-teal-700',
  }

  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${styles[tone]}`}>{label}</span>
}

function buildSignals(page: PageRecord, t: (key: string) => string) {
  const signals: Array<{ label: string; tone: 'stone' | 'rose' | 'amber' | 'teal' }> = []
  if (page.title_missing) signals.push({ label: t('pages.signals.missingTitle'), tone: 'rose' })
  if (page.title_too_short) signals.push({ label: t('pages.signals.titleTooShort'), tone: 'amber' })
  if (page.meta_description_missing) signals.push({ label: t('pages.signals.missingMeta'), tone: 'rose' })
  if (page.meta_description_too_short) signals.push({ label: t('pages.signals.metaTooShort'), tone: 'amber' })
  if (page.h1_missing) signals.push({ label: t('pages.signals.missingH1'), tone: 'rose' })
  if (page.missing_h2) signals.push({ label: t('pages.signals.missingH2'), tone: 'amber' })
  if (page.was_rendered) signals.push({ label: t('pages.signals.rendered'), tone: 'teal' })
  if (page.js_heavy_like) signals.push({ label: t('pages.signals.jsHeavyLike'), tone: 'amber' })
  if (page.schema_present) signals.push({ label: t('pages.signals.schemaPresent'), tone: 'teal' })
  if (page.noindex_like || page.non_indexable_like) signals.push({ label: t('pages.signals.nonIndexable'), tone: 'teal' })
  if (page.has_cannibalization) signals.push({ label: t('pages.cannibalization.label'), tone: 'amber' })
  return signals
}

function summaryNumbers(site: SiteDetail, taxonomy: PageTaxonomySummary | undefined, matchingRows: number) {
  const summary = site.active_crawl?.summary_counts
  const totalPages = summary?.total_pages ?? 0
  return {
    totalPages,
    matchingRows,
    metadataGaps:
      (summary?.pages_missing_title ?? 0) +
      (summary?.pages_missing_meta_description ?? 0) +
      (summary?.pages_missing_h1 ?? 0),
    renderIssues:
      (summary?.rendered_pages ?? 0) + (summary?.js_heavy_like_pages ?? 0) + (summary?.pages_with_render_errors ?? 0),
    gscCoverage: summary?.pages_with_gsc_28d ?? 0,
    opportunities: summary?.gsc_opportunities_28d ?? 0,
    taxonomyCoverage: taxonomy ? `${taxonomy.classified_pages}/${taxonomy.total_pages}` : '-',
  }
}

export function SitePagesWorkspaceView({ site, mode }: SitePagesWorkspaceViewProps) {
  const { t } = useTranslation()
  const activeCrawlId = site.active_crawl_id
  const activeCrawl = site.active_crawl
  const baselineCrawl = site.baseline_crawl
  const pageHeading = mode === 'overview' ? t('shell.routeTitles.pages') : t('shell.routeTitles.pagesRecords')
  const pageSize = mode === 'overview' ? 8 : DEFAULT_PAGE_SIZE
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedPageId, setSelectedPageId] = useState<number | null>(null)
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)

  useDocumentTitle(
    activeCrawlId
      ? t(mode === 'overview' ? 'documentTitle.sitePages' : 'documentTitle.sitePagesRecords', { domain: site.domain })
      : t('nav.pages'),
  )

  const params = useMemo(() => readPagesParams(searchParams, pageSize), [pageSize, searchParams])
  const pagesQuery = usePagesQuery(activeCrawlId ?? -1, params, { enabled: Boolean(activeCrawlId) })
  const taxonomyQuery = usePageTaxonomySummaryQuery(activeCrawlId ?? -1, { enabled: Boolean(activeCrawlId) })

  useEffect(() => {
    if (hasAdvancedFilterParams(params)) {
      setShowAdvancedFilters(true)
    }
  }, [params])

  useEffect(() => {
    if (!pagesQuery.data?.items.length) {
      setSelectedPageId(null)
      return
    }
    if (selectedPageId && pagesQuery.data.items.some((page) => page.id === selectedPageId)) {
      return
    }
    setSelectedPageId(pagesQuery.data.items[0].id)
  }, [pagesQuery.data?.items, selectedPageId])

  function updateParams(updates: Record<string, string | number | boolean | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function resetFilters() {
    updateParams({
      page: 1,
      page_size: pageSize,
      sort_by: DEFAULT_SORT_BY,
      sort_order: DEFAULT_SORT_ORDER,
      gsc_date_range: 'last_28_days',
      url_contains: undefined,
      title_contains: undefined,
      page_type: undefined,
      page_bucket: undefined,
      page_type_confidence_min: undefined,
      page_type_confidence_max: undefined,
      has_title: undefined,
      has_meta_description: undefined,
      has_h1: undefined,
      status_code: undefined,
      title_too_short: undefined,
      meta_too_short: undefined,
      missing_h2: undefined,
      was_rendered: undefined,
      js_heavy_like: undefined,
      schema_present: undefined,
      noindex_like: undefined,
      non_indexable_like: undefined,
      has_technical_issue: undefined,
      has_gsc_data: undefined,
      has_cannibalization: undefined,
      priority_level: undefined,
      opportunity_type: undefined,
      priority_score_min: undefined,
      priority_score_max: undefined,
      gsc_impressions_min: undefined,
      gsc_ctr_max: undefined,
      gsc_position_min: undefined,
      gsc_top_queries_min: undefined,
    })
  }

  function toggleFilter(
    isActive: boolean,
    updatesOn: Record<string, string | number | boolean | undefined>,
    updatesOff: Record<string, string | number | boolean | undefined>,
  ) {
    updateParams(isActive ? { ...updatesOff, page: 1 } : { ...updatesOn, page: 1 })
  }

  function resetQuickFilters() {
    updateParams({
      priority_score_min: undefined,
      opportunity_type: undefined,
      has_technical_issue: undefined,
      title_too_short: undefined,
      meta_too_short: undefined,
      missing_h2: undefined,
      was_rendered: undefined,
      js_heavy_like: undefined,
      schema_present: undefined,
      noindex_like: undefined,
      non_indexable_like: undefined,
      has_cannibalization: undefined,
      gsc_impressions_min: undefined,
      gsc_ctr_max: undefined,
      page: 1,
    })
  }

  const quickFilters = [
    { label: t('pages.quickFilters.highPriority'), isActive: (params.priority_score_min ?? 0) >= 45, onClick: () => toggleFilter((params.priority_score_min ?? 0) >= 45, { priority_score_min: 45, sort_by: 'priority_score' }, { priority_score_min: undefined }) },
    { label: t('pages.quickFilters.quickWins'), isActive: params.opportunity_type === 'QUICK_WINS', onClick: () => toggleFilter(params.opportunity_type === 'QUICK_WINS', { opportunity_type: 'QUICK_WINS', sort_by: 'priority_score' }, { opportunity_type: undefined }) },
    { label: t('pages.quickFilters.trafficTechnical'), isActive: params.has_technical_issue === true, onClick: () => toggleFilter(params.has_technical_issue === true, { has_technical_issue: true }, { has_technical_issue: undefined }) },
    { label: t('pages.quickFilters.titleTooShort'), isActive: params.title_too_short === true, onClick: () => toggleFilter(params.title_too_short === true, { title_too_short: true }, { title_too_short: undefined }) },
    { label: t('pages.quickFilters.metaTooShort'), isActive: params.meta_too_short === true, onClick: () => toggleFilter(params.meta_too_short === true, { meta_too_short: true }, { meta_too_short: undefined }) },
    { label: t('pages.quickFilters.missingH2'), isActive: params.missing_h2 === true, onClick: () => toggleFilter(params.missing_h2 === true, { missing_h2: true }, { missing_h2: undefined }) },
    { label: t('pages.quickFilters.rendered'), isActive: params.was_rendered === true, onClick: () => toggleFilter(params.was_rendered === true, { was_rendered: true }, { was_rendered: undefined }) },
    { label: t('pages.quickFilters.jsHeavyLike'), isActive: params.js_heavy_like === true, onClick: () => toggleFilter(params.js_heavy_like === true, { js_heavy_like: true }, { js_heavy_like: undefined }) },
    { label: t('pages.quickFilters.schemaPresent'), isActive: params.schema_present === true, onClick: () => toggleFilter(params.schema_present === true, { schema_present: true }, { schema_present: undefined }) },
    { label: t('pages.quickFilters.noindexLike'), isActive: params.noindex_like === true || params.non_indexable_like === true, onClick: () => toggleFilter(params.noindex_like === true || params.non_indexable_like === true, { noindex_like: true, non_indexable_like: true }, { noindex_like: undefined, non_indexable_like: undefined }) },
    { label: t('pages.quickFilters.highRiskPages'), isActive: params.has_cannibalization === true, onClick: () => toggleFilter(params.has_cannibalization === true, { has_cannibalization: true }, { has_cannibalization: undefined }) },
    { label: t('pages.quickFilters.highImpressionsLowCtrOpportunity'), isActive: (params.gsc_impressions_min ?? 0) >= 100 && (params.gsc_ctr_max ?? 1) <= 0.02, onClick: () => toggleFilter((params.gsc_impressions_min ?? 0) >= 100 && (params.gsc_ctr_max ?? 1) <= 0.02, { gsc_impressions_min: 100, gsc_ctr_max: 0.02 }, { gsc_impressions_min: undefined, gsc_ctr_max: undefined }) },
  ]

  if (!activeCrawlId || !activeCrawl) {
    return (
      <EmptyState
        title={t('sitePages.empty.noActiveTitle')}
        description={t('sitePages.empty.noActiveDescription')}
      />
    )
  }

  if (pagesQuery.isLoading) {
    return <LoadingState label={t('sitePages.loading')} />
  }

  if (pagesQuery.isError) {
    return <ErrorState title={t('sitePages.errors.requestTitle')} message={getUiErrorMessage(pagesQuery.error, t)} />
  }

  const payload = pagesQuery.data
  if (!payload) {
    return (
      <EmptyState
        title={t('sitePages.empty.unavailableTitle')}
        description={t('sitePages.empty.unavailableDescription')}
      />
    )
  }

  const selectedPage = pagesQuery.data.items.find((page) => page.id === selectedPageId) ?? pagesQuery.data.items[0] ?? null
  const totals = summaryNumbers(site, taxonomyQuery.data, payload.total_items)
  const exportHref = (filtered: boolean) => buildExportHref(activeCrawlId, params, filtered)
  const routeContext = { activeCrawlId, baselineCrawlId: baselineCrawl?.id ?? site.baseline_crawl_id }
  const currentStatePath =
    mode === 'overview' ? buildSitePagesRecordsPath(site.id, routeContext) : buildSitePagesPath(site.id, routeContext)
  const changesPath = buildSiteChangesPagesPath(site.id, routeContext)

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('nav.pages')}
        title={pageHeading}
        description={t('sitePages.description', { domain: site.domain })}
        contextChips={[
          { label: t('sitePages.context.active'), value: `#${activeCrawl.id}` },
          { label: t('sitePages.context.status'), value: activeCrawl.status },
        ]}
        primaryAction={{
          key: mode === 'overview' ? 'open-records' : 'open-overview',
          label: mode === 'overview' ? t('sites.pages.records.navLabel') : t('nav.overview'),
          to: currentStatePath,
        }}
        operations={[
          {
            key: 'open-changes',
            label: t('sitePages.actions.openChanges'),
            to: changesPath,
          },
          {
            key: 'open-active-crawl',
            label: t('sitePages.actions.openActiveCrawl'),
            to: `/jobs/${activeCrawlId}`,
          },
        ]}
        exports={[
          {
            key: 'export-full',
            label: t('pages.page.exportFull'),
            href: exportHref(false),
          },
          {
            key: 'export-current',
            label: t('pages.page.exportCurrentView'),
            href: exportHref(true),
          },
        ]}
      />

      <SummaryCards
        items={[
          {
            label: t('sitePages.summary.activePages'),
            value: totals.totalPages,
            hint: t('sitePages.summaryHints.activePages', { crawlId: activeCrawlId }),
          },
          {
            label: t('sitePages.summary.matchingRows'),
            value: totals.matchingRows,
            hint: t('sitePages.summaryHints.matchingRows'),
          },
          {
            label: t('sitePages.summary.metadataGaps'),
            value: totals.metadataGaps,
            hint: t('sitePages.summaryHints.metadataGaps', {
              missingTitle: activeCrawl.summary_counts.pages_missing_title,
              missingMeta: activeCrawl.summary_counts.pages_missing_meta_description,
              missingH1: activeCrawl.summary_counts.pages_missing_h1,
            }),
          },
          {
            label: t('sitePages.summary.renderIssues'),
            value: totals.renderIssues,
            hint: t('sitePages.summaryHints.renderIssues', {
              rendered: activeCrawl.summary_counts.rendered_pages,
              jsHeavy: activeCrawl.summary_counts.js_heavy_like_pages,
            }),
          },
          {
            label: t('sitePages.summary.gscCoverage'),
            value: totals.gscCoverage,
            hint: t('sitePages.summaryHints.gscCoverage', {
              count: activeCrawl.summary_counts.gsc_opportunities_28d,
            }),
          },
          {
            label: t('sitePages.summary.taxonomyCoverage'),
            value: totals.taxonomyCoverage,
            hint: taxonomyQuery.data
              ? t('sitePages.summaryHints.taxonomyCoverageReady', {
                  version: taxonomyQuery.data.page_type_version,
                })
              : t('sitePages.summaryHints.taxonomyCoverageWaiting'),
          },
        ]}
      />

      <QuickFilterBar title={t('sitePages.quickFiltersTitle')} items={quickFilters} onReset={resetQuickFilters} />

      <FilterPanel
        title={t('sitePages.filters.title')}
        description={t('sitePages.filters.description')}
        onReset={resetFilters}
        bodyClassName="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
      >
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.urlContains')}</span>
          <input value={params.url_contains ?? ''} onChange={(event) => updateParams({ url_contains: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.titleContains')}</span>
          <input value={params.title_contains ?? ''} onChange={(event) => updateParams({ title_contains: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.gscDateRange')}</span>
          <select value={params.gsc_date_range} onChange={(event) => updateParams({ gsc_date_range: event.target.value, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="last_28_days">{t('pagesCompare.filters.last28Days')}</option>
            <option value="last_90_days">{t('pagesCompare.filters.last90Days')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.pageType')}</span>
          <select value={params.page_type ?? ''} onChange={(event) => updateParams({ page_type: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {PAGE_TYPES.map((pageType) => <option key={pageType} value={pageType}>{t(`pages.taxonomy.pageTypes.${pageType}`)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.pageBucket')}</span>
          <select value={params.page_bucket ?? ''} onChange={(event) => updateParams({ page_bucket: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {PAGE_BUCKETS.map((pageBucket) => <option key={pageBucket} value={pageBucket}>{t(`pages.taxonomy.pageBuckets.${pageBucket}`)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.priorityLevel')}</span>
          <select value={params.priority_level ?? ''} onChange={(event) => updateParams({ priority_level: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {PRIORITY_LEVELS.map((priorityLevel) => <option key={priorityLevel} value={priorityLevel}>{t(`pages.priority.level.${priorityLevel}`)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.opportunityType')}</span>
          <select value={params.opportunity_type ?? ''} onChange={(event) => updateParams({ opportunity_type: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {OPPORTUNITY_TYPES.map((opportunityType) => <option key={opportunityType} value={opportunityType}>{t(`opportunities.types.${opportunityType}.title`)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.statusCode')}</span>
          <input type="number" value={params.status_code ?? ''} onChange={(event) => updateParams({ status_code: event.target.value ? Number(event.target.value) : undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.priorityScoreMin')}</span>
          <input type="number" value={params.priority_score_min ?? ''} onChange={(event) => updateParams({ priority_score_min: event.target.value ? Number(event.target.value) : undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.priorityScoreMax')}</span>
          <input type="number" value={params.priority_score_max ?? ''} onChange={(event) => updateParams({ priority_score_max: event.target.value ? Number(event.target.value) : undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.gscMinImpressions')}</span>
          <input type="number" value={params.gsc_impressions_min ?? ''} onChange={(event) => updateParams({ gsc_impressions_min: event.target.value ? Number(event.target.value) : undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.gscMaxCtr')}</span>
          <input type="number" step="0.01" value={params.gsc_ctr_max ? String(Number(params.gsc_ctr_max) * 100) : ''} onChange={(event) => updateParams({ gsc_ctr_max: event.target.value ? String(Number(event.target.value) / 100) : undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.gscMinPosition')}</span>
          <input type="number" step="0.1" value={params.gsc_position_min ?? ''} onChange={(event) => updateParams({ gsc_position_min: event.target.value ? Number(event.target.value) : undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.gscMinTopQueries')}</span>
          <input type="number" value={params.gsc_top_queries_min ?? ''} onChange={(event) => updateParams({ gsc_top_queries_min: event.target.value ? Number(event.target.value) : undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <div className="flex items-center justify-between gap-3 md:col-span-2 xl:col-span-3">
          <p className="text-sm font-medium text-stone-700">
            {showAdvancedFilters ? t('sitePages.filters.expandedState') : t('sitePages.filters.compactState')}
          </p>
          <button
            type="button"
            onClick={() => setShowAdvancedFilters((current) => !current)}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {showAdvancedFilters ? t('common.hideExtraFilters') : t('common.showAllFilters')}
          </button>
        </div>
        {showAdvancedFilters ? (
          <>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.pageTypeConfidenceMin')}</span>
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                value={params.page_type_confidence_min ? String(Number(params.page_type_confidence_min) * 100) : ''}
                onChange={(event) =>
                  updateParams({
                    page_type_confidence_min: event.target.value ? String(Number(event.target.value) / 100) : undefined,
                    page: 1,
                  })
                }
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
              />
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.pageTypeConfidenceMax')}</span>
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                value={params.page_type_confidence_max ? String(Number(params.page_type_confidence_max) * 100) : ''}
                onChange={(event) =>
                  updateParams({
                    page_type_confidence_max: event.target.value ? String(Number(event.target.value) / 100) : undefined,
                    page: 1,
                  })
                }
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
              />
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.hasTitle')}</span>
              <select value={params.has_title === undefined ? '' : String(params.has_title)} onChange={(event) => updateParams({ has_title: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.hasMetaDescription')}</span>
              <select value={params.has_meta_description === undefined ? '' : String(params.has_meta_description)} onChange={(event) => updateParams({ has_meta_description: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.hasH1')}</span>
              <select value={params.has_h1 === undefined ? '' : String(params.has_h1)} onChange={(event) => updateParams({ has_h1: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.wasRendered')}</span>
              <select value={params.was_rendered === undefined ? '' : String(params.was_rendered)} onChange={(event) => updateParams({ was_rendered: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.jsHeavyLike')}</span>
              <select value={params.js_heavy_like === undefined ? '' : String(params.js_heavy_like)} onChange={(event) => updateParams({ js_heavy_like: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.schemaPresent')}</span>
              <select value={params.schema_present === undefined ? '' : String(params.schema_present)} onChange={(event) => updateParams({ schema_present: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.noindexLike')}</span>
              <select value={params.noindex_like === undefined ? '' : String(params.noindex_like)} onChange={(event) => updateParams({ noindex_like: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.hasTechnicalIssue')}</span>
              <select value={params.has_technical_issue === undefined ? '' : String(params.has_technical_issue)} onChange={(event) => updateParams({ has_technical_issue: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.hasGscData')}</span>
              <select value={params.has_gsc_data === undefined ? '' : String(params.has_gsc_data)} onChange={(event) => updateParams({ has_gsc_data: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.hasCannibalization')}</span>
              <select value={params.has_cannibalization === undefined ? '' : String(params.has_cannibalization)} onChange={(event) => updateParams({ has_cannibalization: event.target.value === '' ? undefined : event.target.value === 'true', page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
                <option value="">{t('common.any')}</option>
                <option value="true">{t('common.yes')}</option>
                <option value="false">{t('common.no')}</option>
              </select>
            </label>
          </>
        ) : null}
      </FilterPanel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="space-y-4">
          {payload.items.length === 0 ? (
            <EmptyState
              title={t('sitePages.empty.filteredTitle')}
              description={t('sitePages.empty.filteredDescription')}
            />
          ) : (
            <>
              <DataTable
                columns={[
                  {
                    key: 'url',
                    header: t('pages.table.url'),
                    sortKey: 'url',
                    minWidth: 320,
                    cell: (page: PageRecord) => (
                      <div className="space-y-1.5">
                        <p className="font-medium text-stone-900" title={page.url}>
                          {page.url}
                        </p>
                        <p className="text-xs text-stone-500" title={page.normalized_url}>
                          {page.normalized_url}
                        </p>
                        <UrlActions url={page.url} />
                      </div>
                    ),
                  },
                  {
                    key: 'status',
                    header: t('pages.table.status'),
                    sortKey: 'status_code',
                    minWidth: 90,
                    cell: (page: PageRecord) => formatNullable(page.status_code),
                  },
                  {
                    key: 'taxonomy',
                    header: t('pages.table.taxonomy'),
                    sortKey: 'page_type_confidence',
                    minWidth: 220,
                    cell: (page: PageRecord) => (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-1.5">
                          {renderBadge(t(`pages.taxonomy.pageTypes.${page.page_type}`), pageTypeTone(page.page_type))}
                          {renderBadge(t(`pages.taxonomy.pageBuckets.${page.page_bucket}`), pageBucketTone(page.page_bucket))}
                        </div>
                        <p className="text-xs text-stone-600">
                          {t('pages.taxonomy.confidence')}: {formatPercent(page.page_type_confidence)}
                        </p>
                      </div>
                    ),
                  },
                  {
                    key: 'priority',
                    header: t('pages.table.priority'),
                    sortKey: 'priority_score',
                    minWidth: 240,
                    cell: (page: PageRecord) => (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-1.5">
                          {renderBadge(t('pages.priority.scoreBadge', { score: page.priority_score }), priorityTone(page.priority_level))}
                          {renderBadge(t(`pages.priority.level.${page.priority_level}`), priorityTone(page.priority_level))}
                          {page.primary_opportunity_type
                            ? renderBadge(
                                t(`opportunities.types.${page.primary_opportunity_type}.title`),
                                opportunityTone(page.primary_opportunity_type),
                              )
                            : null}
                        </div>
                        <p className="text-xs text-stone-600">{page.priority_rationale}</p>
                      </div>
                    ),
                  },
                  {
                    key: 'signals',
                    header: t('pages.table.signals'),
                    minWidth: 200,
                    cell: (page: PageRecord) => (
                      <div className="flex flex-wrap gap-1.5">
                        {buildSignals(page, t).map((signal, index) => (
                          <span key={`${signal.label}-${index}`}>{renderBadge(signal.label, signal.tone)}</span>
                        ))}
                      </div>
                    ),
                  },
                  {
                    key: 'details',
                    header: t('common.open'),
                    minWidth: 120,
                    cell: (page: PageRecord) => (
                      <button
                        type="button"
                        onClick={() => setSelectedPageId(page.id)}
                        className="rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                      >
                        {t('sitePages.inspectRecord')}
                      </button>
                    ),
                  },
                ]}
                rows={payload.items}
                rowKey={(page) => page.id}
                sortBy={params.sort_by}
                sortOrder={params.sort_order}
                onSortChange={(sortBy, sortOrder) => updateParams({ sort_by: sortBy, sort_order: sortOrder, page: 1 })}
              />
              <PaginationControls
                page={payload.page}
                pageSize={payload.page_size}
                totalItems={payload.total_items}
                totalPages={payload.total_pages}
                onPageChange={(page) => updateParams({ page })}
                onPageSizeChange={(pageSize) => updateParams({ page_size: pageSize, page: 1 })}
              />
            </>
          )}
        </section>

        <aside className="rounded-[28px] border border-stone-300 bg-white/90 p-5 shadow-sm">
          {selectedPage ? (
            <div className="space-y-4">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-teal-700">{t('sitePages.details.title')}</p>
                <h2 className="mt-2 text-lg font-semibold text-stone-950" title={selectedPage.url}>
                  {selectedPage.url}
                </h2>
                <p className="mt-1 text-sm text-stone-600" title={selectedPage.normalized_url}>
                  {selectedPage.normalized_url}
                </p>
              </div>
              <div className="grid gap-3">
                <div className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-stone-500">{t('pages.table.status')}</p>
                  <p className="mt-1 font-medium text-stone-900">{formatNullable(selectedPage.status_code)}</p>
                </div>
                <div className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-stone-500">{t('pages.table.title')}</p>
                  <p className="mt-1 text-sm text-stone-900">{selectedPage.title ?? '-'}</p>
                  <p className="mt-1 text-xs text-stone-500">
                    {selectedPage.title_length == null
                      ? '-'
                      : t('common.length', { count: Number(selectedPage.title_length) })}
                  </p>
                </div>
                <div className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-stone-500">{t('pages.table.metaDescription')}</p>
                  <p className="mt-1 text-sm text-stone-900">{selectedPage.meta_description ?? '-'}</p>
                  <p className="mt-1 text-xs text-stone-500">
                    {selectedPage.meta_description_length == null
                      ? '-'
                      : t('common.length', { count: Number(selectedPage.meta_description_length) })}
                  </p>
                </div>
                <div className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-stone-500">{t('pages.table.canonical')}</p>
                  <p className="mt-1 break-words text-sm text-stone-900">{selectedPage.canonical_url ?? '-'}</p>
                  <p className="mt-1 text-xs text-stone-500">
                    {selectedPage.robots_meta ?? '-'} | {selectedPage.x_robots_tag ?? '-'}
                  </p>
                </div>
                <div className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-stone-500">{t('pages.table.priority')}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {renderBadge(t('pages.priority.scoreBadge', { score: selectedPage.priority_score }), priorityTone(selectedPage.priority_level))}
                    {renderBadge(t(`pages.priority.level.${selectedPage.priority_level}`), priorityTone(selectedPage.priority_level))}
                    {selectedPage.primary_opportunity_type
                      ? renderBadge(
                          t(`opportunities.types.${selectedPage.primary_opportunity_type}.title`),
                          opportunityTone(selectedPage.primary_opportunity_type),
                        )
                      : null}
                  </div>
                  <p className="mt-2 text-xs text-stone-600">{selectedPage.priority_rationale}</p>
                  <p className="mt-2 text-xs text-stone-600">
                    {t('sitePages.details.responseTime')}: {formatResponseTime(selectedPage.response_time_ms)}
                  </p>
                  <p className="text-xs text-stone-600">
                    {t('nav.gsc')}: {formatNullable(selectedPage.clicks_28d)} {t('sitePages.details.clicks')} /{' '}
                    {formatNullable(selectedPage.impressions_28d)} {t('sitePages.details.impressions')}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  to={`/jobs/${activeCrawlId}/pages?url_contains=${encodeURIComponent(selectedPage.url)}`}
                  className="rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                >
                  {t('sitePages.actions.openInJobPages')}
                </Link>
                <UrlActions url={selectedPage.url} />
              </div>
            </div>
          ) : (
            <EmptyState
              title={t('sitePages.empty.detailsTitle')}
              description={t('sitePages.empty.detailsDescription')}
            />
          )}
        </aside>
      </div>
    </div>
  )
}
