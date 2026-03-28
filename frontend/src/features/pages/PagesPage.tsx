import { startTransition, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { buildApiUrl } from '../../api/client'
import { DataTable } from '../../components/DataTable'
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
  PagesQueryParams,
  PageType,
  PriorityLevel,
  SortOrder,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import {
  formatBytes,
  formatDateTime,
  formatNullable,
  formatPercent,
  formatPosition,
  formatResponseTime,
} from '../../utils/format'
import { mergeSearchParams, parseFloatParam, parseIntegerParam } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
import { usePageTaxonomySummaryQuery, usePagesQuery } from './api'

const OPPORTUNITY_TYPES: OpportunityType[] = [
  'QUICK_WINS',
  'HIGH_IMPRESSIONS_LOW_CTR',
  'TRAFFIC_WITH_TECHNICAL_ISSUES',
  'IMPORTANT_BUT_WEAK',
  'LOW_HANGING_FRUIT',
  'HIGH_RISK_PAGES',
  'UNDERLINKED_OPPORTUNITIES',
]

const PRIORITY_LEVELS: PriorityLevel[] = ['critical', 'high', 'medium', 'low']
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
const TAXONOMY_FOCUS_PAGE_TYPES: PageType[] = ['category', 'product', 'service', 'blog_article', 'blog_index', 'utility']
const NON_FILTER_QUERY_KEYS = new Set(['page', 'page_size', 'sort_by', 'sort_order', 'gsc_date_range'])
const PAGES_FILTER_GRID_CLASS = 'grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6'

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

function getBooleanFilterValue(searchParams: URLSearchParams, key: string) {
  const value = searchParams.get(key)
  return value === 'true' || value === 'false' ? value : ''
}

function readPriorityLevel(searchParams: URLSearchParams): PriorityLevel | undefined {
  const value = searchParams.get('priority_level')
  return PRIORITY_LEVELS.includes(value as PriorityLevel) ? (value as PriorityLevel) : undefined
}

function readOpportunityType(searchParams: URLSearchParams): OpportunityType | undefined {
  const value = searchParams.get('opportunity_type')
  return OPPORTUNITY_TYPES.includes(value as OpportunityType) ? (value as OpportunityType) : undefined
}

function readPageType(searchParams: URLSearchParams): PageType | undefined {
  const value = searchParams.get('page_type')
  return PAGE_TYPES.includes(value as PageType) ? (value as PageType) : undefined
}

function readPageBucket(searchParams: URLSearchParams): PageBucket | undefined {
  const value = searchParams.get('page_bucket')
  return PAGE_BUCKETS.includes(value as PageBucket) ? (value as PageBucket) : undefined
}

function readPagesParams(searchParams: URLSearchParams): PagesQueryParams {
  const sortBy = searchParams.get('sort_by')
  const sortOrder = searchParams.get('sort_order')

  return {
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), 25),
    sort_by: (sortBy ?? 'url') as PagesQueryParams['sort_by'],
    sort_order: sortOrder === 'desc' ? 'desc' : 'asc',
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    url_contains: searchParams.get('url_contains') || undefined,
    title_contains: searchParams.get('title_contains') || undefined,
    page_type: readPageType(searchParams),
    page_bucket: readPageBucket(searchParams),
    page_type_confidence_min: parseFloatParam(searchParams.get('page_type_confidence_min'), undefined),
    page_type_confidence_max: parseFloatParam(searchParams.get('page_type_confidence_max'), undefined),
    has_title: searchParams.get('has_title') === null ? undefined : searchParams.get('has_title') === 'true',
    has_meta_description:
      searchParams.get('has_meta_description') === null
        ? undefined
        : searchParams.get('has_meta_description') === 'true',
    has_h1: searchParams.get('has_h1') === null ? undefined : searchParams.get('has_h1') === 'true',
    status_code: parseIntegerParam(searchParams.get('status_code'), undefined),
    canonical_missing:
      searchParams.get('canonical_missing') === null
        ? undefined
        : searchParams.get('canonical_missing') === 'true',
    robots_meta_contains: searchParams.get('robots_meta_contains') || undefined,
    noindex_like:
      searchParams.get('noindex_like') === null ? undefined : searchParams.get('noindex_like') === 'true',
    non_indexable_like:
      searchParams.get('non_indexable_like') === null
        ? undefined
        : searchParams.get('non_indexable_like') === 'true',
    title_too_short:
      searchParams.get('title_too_short') === null
        ? undefined
        : searchParams.get('title_too_short') === 'true',
    title_too_long:
      searchParams.get('title_too_long') === null ? undefined : searchParams.get('title_too_long') === 'true',
    meta_too_short:
      searchParams.get('meta_too_short') === null ? undefined : searchParams.get('meta_too_short') === 'true',
    meta_too_long:
      searchParams.get('meta_too_long') === null ? undefined : searchParams.get('meta_too_long') === 'true',
    multiple_h1:
      searchParams.get('multiple_h1') === null ? undefined : searchParams.get('multiple_h1') === 'true',
    missing_h2:
      searchParams.get('missing_h2') === null ? undefined : searchParams.get('missing_h2') === 'true',
    self_canonical:
      searchParams.get('self_canonical') === null ? undefined : searchParams.get('self_canonical') === 'true',
    canonical_to_other_url:
      searchParams.get('canonical_to_other_url') === null
        ? undefined
        : searchParams.get('canonical_to_other_url') === 'true',
    canonical_to_non_200:
      searchParams.get('canonical_to_non_200') === null
        ? undefined
        : searchParams.get('canonical_to_non_200') === 'true',
    canonical_to_redirect:
      searchParams.get('canonical_to_redirect') === null
        ? undefined
        : searchParams.get('canonical_to_redirect') === 'true',
    thin_content:
      searchParams.get('thin_content') === null ? undefined : searchParams.get('thin_content') === 'true',
    duplicate_content:
      searchParams.get('duplicate_content') === null
        ? undefined
        : searchParams.get('duplicate_content') === 'true',
    missing_alt_images:
      searchParams.get('missing_alt_images') === null
        ? undefined
        : searchParams.get('missing_alt_images') === 'true',
    no_images:
      searchParams.get('no_images') === null ? undefined : searchParams.get('no_images') === 'true',
    oversized:
      searchParams.get('oversized') === null ? undefined : searchParams.get('oversized') === 'true',
    was_rendered:
      searchParams.get('was_rendered') === null ? undefined : searchParams.get('was_rendered') === 'true',
    js_heavy_like:
      searchParams.get('js_heavy_like') === null ? undefined : searchParams.get('js_heavy_like') === 'true',
    schema_present:
      searchParams.get('schema_present') === null ? undefined : searchParams.get('schema_present') === 'true',
    schema_type: searchParams.get('schema_type') || undefined,
    has_render_error:
      searchParams.get('has_render_error') === null
        ? undefined
        : searchParams.get('has_render_error') === 'true',
    has_x_robots_tag:
      searchParams.get('has_x_robots_tag') === null
        ? undefined
        : searchParams.get('has_x_robots_tag') === 'true',
    has_technical_issue:
      searchParams.get('has_technical_issue') === null
        ? undefined
        : searchParams.get('has_technical_issue') === 'true',
    has_gsc_data:
      searchParams.get('has_gsc_data') === null
        ? undefined
        : searchParams.get('has_gsc_data') === 'true',
    has_cannibalization:
      searchParams.get('has_cannibalization') === null
        ? undefined
        : searchParams.get('has_cannibalization') === 'true',
    priority_level: readPriorityLevel(searchParams),
    opportunity_type: readOpportunityType(searchParams),
    priority_score_min: parseIntegerParam(searchParams.get('priority_score_min'), undefined),
    priority_score_max: parseIntegerParam(searchParams.get('priority_score_max'), undefined),
    status_code_min: parseIntegerParam(searchParams.get('status_code_min'), undefined),
    status_code_max: parseIntegerParam(searchParams.get('status_code_max'), undefined),
    gsc_clicks_min: parseIntegerParam(searchParams.get('gsc_clicks_min'), undefined),
    gsc_clicks_max: parseIntegerParam(searchParams.get('gsc_clicks_max'), undefined),
    gsc_impressions_min: parseIntegerParam(searchParams.get('gsc_impressions_min'), undefined),
    gsc_impressions_max: parseIntegerParam(searchParams.get('gsc_impressions_max'), undefined),
    gsc_ctr_min: parseFloatParam(searchParams.get('gsc_ctr_min'), undefined),
    gsc_ctr_max: parseFloatParam(searchParams.get('gsc_ctr_max'), undefined),
    gsc_position_min: parseFloatParam(searchParams.get('gsc_position_min'), undefined),
    gsc_position_max: parseFloatParam(searchParams.get('gsc_position_max'), undefined),
    gsc_top_queries_min: parseIntegerParam(searchParams.get('gsc_top_queries_min'), undefined),
    title_exact: searchParams.get('title_exact') || undefined,
    meta_description_exact: searchParams.get('meta_description_exact') || undefined,
    content_text_hash_exact: searchParams.get('content_text_hash_exact') || undefined,
  }
}

function buildPagesExportHref(jobId: number, searchParams: URLSearchParams, filtered: boolean) {
  const query = filtered ? searchParams.toString() : ''
  return buildApiUrl(`/crawl-jobs/${jobId}/export/pages.csv${query ? `?${query}` : ''}`)
}

function isPagesViewFiltered(searchParams: URLSearchParams) {
  return Array.from(searchParams.keys()).some((key) => key !== 'page' && key !== 'page_size' && key !== 'sort_by' && key !== 'sort_order')
}

function renderBadge(
  label: string,
  tone: 'stone' | 'rose' | 'amber' | 'teal' = 'stone',
  selected = false,
) {
  const styles = {
    stone: selected
      ? 'border-stone-950 bg-stone-950 !text-white shadow-sm'
      : 'border-stone-300 bg-stone-100 text-stone-700',
    rose: selected
      ? 'border-rose-700 bg-rose-700 text-white shadow-sm'
      : 'border-rose-200 bg-rose-50 text-rose-700',
    amber: selected
      ? 'border-amber-600 bg-amber-600 text-white shadow-sm'
      : 'border-amber-200 bg-amber-50 text-amber-700',
    teal: selected
      ? 'border-teal-700 bg-teal-700 text-white shadow-sm'
      : 'border-teal-200 bg-teal-50 text-teal-700',
  }

  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${styles[tone]}`}>{label}</span>
  )
}

function buildPageSignals(page: PageRecord, translate: (key: string) => string) {
  const signals: Array<{ label: string; tone: 'stone' | 'rose' | 'amber' | 'teal' }> = []

  if (page.title_missing) {
    signals.push({ label: translate('pages.signals.missingTitle'), tone: 'rose' })
  } else if (page.title_too_short) {
    signals.push({ label: translate('pages.signals.titleTooShort'), tone: 'amber' })
  } else if (page.title_too_long) {
    signals.push({ label: translate('pages.signals.titleTooLong'), tone: 'amber' })
  }
  if (page.meta_description_missing) {
    signals.push({ label: translate('pages.signals.missingMeta'), tone: 'rose' })
  } else if (page.meta_description_too_short) {
    signals.push({ label: translate('pages.signals.metaTooShort'), tone: 'amber' })
  } else if (page.meta_description_too_long) {
    signals.push({ label: translate('pages.signals.metaTooLong'), tone: 'amber' })
  }
  if (page.h1_missing) {
    signals.push({ label: translate('pages.signals.missingH1'), tone: 'rose' })
  }
  if (page.multiple_h1) {
    signals.push({ label: translate('pages.signals.multipleH1'), tone: 'amber' })
  }
  if (page.missing_h2) {
    signals.push({ label: translate('pages.signals.missingH2'), tone: 'amber' })
  }
  if (page.canonical_missing) {
    signals.push({ label: translate('pages.signals.missingCanonical'), tone: 'amber' })
  }
  if (page.canonical_to_other_url) {
    signals.push({ label: translate('pages.signals.canonicalToOther'), tone: 'teal' })
  }
  if (page.canonical_to_non_200) {
    signals.push({ label: translate('pages.signals.canonicalToNon200'), tone: 'rose' })
  }
  if (page.canonical_to_redirect) {
    signals.push({ label: translate('pages.signals.canonicalToRedirect'), tone: 'amber' })
  }
  if (page.noindex_like || page.non_indexable_like) {
    signals.push({ label: translate('pages.signals.nonIndexable'), tone: 'teal' })
  }
  if (page.thin_content) {
    signals.push({ label: translate('pages.signals.thinContent'), tone: 'amber' })
  }
  if (page.duplicate_content) {
    signals.push({ label: translate('pages.signals.duplicateContent'), tone: 'teal' })
  }
  if (page.missing_alt_images) {
    signals.push({ label: translate('pages.signals.missingAlt'), tone: 'amber' })
  }
  if (page.no_images) {
    signals.push({ label: translate('pages.signals.noImages'), tone: 'stone' })
  }
  if (page.oversized) {
    signals.push({ label: translate('pages.signals.oversized'), tone: 'rose' })
  }
  if (page.was_rendered) {
    signals.push({ label: translate('pages.signals.rendered'), tone: 'teal' })
  }
  if (page.js_heavy_like) {
    signals.push({ label: translate('pages.signals.jsHeavyLike'), tone: 'amber' })
  }
  if (page.schema_present) {
    signals.push({ label: translate('pages.signals.schemaPresent'), tone: 'teal' })
  }
  if (page.has_x_robots_tag) {
    signals.push({ label: translate('pages.signals.xRobots'), tone: 'stone' })
  }
  if (page.has_render_error) {
    signals.push({ label: translate('pages.signals.renderError'), tone: 'rose' })
  }

  return signals
}

function PageTextCell({
  value,
  length,
  lengthLabel,
  allowLongWrap = false,
}: {
  value: string | null | undefined
  length: number | null | undefined
  lengthLabel: string
  allowLongWrap?: boolean
}) {
  const shouldWrap = allowLongWrap && typeof value === 'string' && (length ?? value.length) > 100

  return (
    <div className="space-y-1">
      <p
        className={`text-sm leading-5 text-stone-900 ${
          shouldWrap ? 'max-w-[22rem] whitespace-normal break-words' : 'whitespace-nowrap'
        }`}
      >
        {value || '-'}
      </p>
      <p className="text-xs whitespace-nowrap text-stone-500">
        {lengthLabel}: {formatNullable(length)}
      </p>
    </div>
  )
}

function MetricLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 text-xs whitespace-nowrap text-stone-600">
      <span className="shrink-0">{label}</span>
      <span className="min-w-0 text-right font-medium text-stone-900">{value}</span>
    </div>
  )
}

function pageGscValue(
  page: Pick<
    PageRecord,
    | 'clicks_28d'
    | 'impressions_28d'
    | 'ctr_28d'
    | 'position_28d'
    | 'top_queries_count_28d'
    | 'clicks_90d'
    | 'impressions_90d'
    | 'ctr_90d'
    | 'position_90d'
    | 'top_queries_count_90d'
  >,
  metric: 'clicks' | 'impressions' | 'ctr' | 'position' | 'top_queries_count',
  range: PagesQueryParams['gsc_date_range'],
) {
  const suffix = range === 'last_90_days' ? '90d' : '28d'
  return page[`${metric}_${suffix}` as keyof typeof page]
}

function getPriorityTone(level: PriorityLevel): 'stone' | 'rose' | 'amber' | 'teal' {
  if (level === 'critical') {
    return 'rose'
  }
  if (level === 'high') {
    return 'amber'
  }
  if (level === 'medium') {
    return 'teal'
  }
  return 'stone'
}

function getOpportunityTone(type: OpportunityType): 'stone' | 'rose' | 'amber' | 'teal' {
  if (type === 'HIGH_RISK_PAGES') {
    return 'rose'
  }
  if (type === 'QUICK_WINS' || type === 'LOW_HANGING_FRUIT') {
    return 'amber'
  }
  return 'teal'
}

function getPageTypeTone(pageType: PageType): 'stone' | 'rose' | 'amber' | 'teal' {
  if (pageType === 'product' || pageType === 'category') {
    return 'amber'
  }
  if (pageType === 'service' || pageType === 'location' || pageType === 'home') {
    return 'teal'
  }
  if (pageType === 'utility' || pageType === 'legal') {
    return 'stone'
  }
  return 'rose'
}

function getPageBucketTone(pageBucket: PageBucket): 'stone' | 'rose' | 'amber' | 'teal' {
  if (pageBucket === 'commercial') {
    return 'amber'
  }
  if (pageBucket === 'informational') {
    return 'teal'
  }
  if (pageBucket === 'trust') {
    return 'rose'
  }
  return 'stone'
}

function buildCannibalizationLink(jobId: number, pageId: number, gscDateRange: PagesQueryParams['gsc_date_range']) {
  const query = new URLSearchParams()
  query.set('gsc_date_range', gscDateRange)
  query.set('page_id', String(pageId))
  return `/jobs/${jobId}/cannibalization?${query.toString()}`
}

export function PagesPage() {
  const { t } = useTranslation()
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? t('documentTitle.pages', { jobId }) : t('nav.pages'))

  if (jobId === null) {
    return <ErrorState title={t('pages.invalidIdTitle')} message={t('pages.invalidIdMessage')} />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const pagesParams = useMemo(() => readPagesParams(searchParams), [searchParams])
  const pagesQuery = usePagesQuery(jobId, pagesParams)
  const taxonomySummaryQuery = usePageTaxonomySummaryQuery(jobId)
  const filteredView = isPagesViewFiltered(searchParams)
  const availableStatusCodes = useMemo(() => {
    const responseStatuses = pagesQuery.data?.available_status_codes ?? []
    const selectedStatus = pagesParams.status_code !== undefined ? [pagesParams.status_code] : []
    return Array.from(new Set([...responseStatuses, ...selectedStatus])).sort((left, right) => left - right)
  }, [pagesParams.status_code, pagesQuery.data?.available_status_codes])
  const hasGscIntegration = Boolean(
    pagesQuery.data?.has_gsc_integration ??
      pagesQuery.data?.items?.some((item) => item.has_gsc_28d || item.has_gsc_90d || item.top_queries_count_28d > 0 || item.top_queries_count_90d > 0),
  )
  const visibleFilterKeys = useMemo(
    () =>
      new Set([
        'status_code',
        'page_type',
        'page_bucket',
        'url_contains',
        'title_contains',
        ...(hasGscIntegration ? ['gsc_clicks_min'] : []),
      ]),
    [hasGscIntegration],
  )
  const hasAdvancedFiltersActive = useMemo(
    () =>
      Array.from(searchParams.keys()).some((key) => !NON_FILTER_QUERY_KEYS.has(key) && !visibleFilterKeys.has(key)),
    [searchParams, visibleFilterKeys],
  )
  const [showAllFilters, setShowAllFilters] = useState(hasAdvancedFiltersActive)
  const suppressAutoExpandRef = useRef(false)

  useEffect(() => {
    if (hasAdvancedFiltersActive && !suppressAutoExpandRef.current) {
      setShowAllFilters(true)
    }
    suppressAutoExpandRef.current = false
  }, [hasAdvancedFiltersActive])

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function updateFilter(key: string, value: string) {
    updateParams({
      [key]: value || undefined,
      page: 1,
    })
  }

  function applyPreset(updates: Record<string, string | number | undefined>) {
    suppressAutoExpandRef.current = true
    updateParams({
      page: 1,
      ...updates,
    })
  }

  function togglePreset(isActive: boolean, updates: Record<string, string | number | undefined>) {
    if (!isActive) {
      applyPreset(updates)
      return
    }

    const clearedUpdates = Object.keys(updates).reduce<Record<string, string | number | undefined>>((acc, key) => {
      acc[key] = undefined
      return acc
    }, {})

    suppressAutoExpandRef.current = true
    updateParams({
      page: 1,
      ...clearedUpdates,
    })
  }

  function togglePageTypeFilter(pageType: PageType) {
    updateParams({
      page_type: pagesParams.page_type === pageType ? undefined : pageType,
      page: 1,
    })
  }

  function resetFilters() {
    updateParams({
      page: 1,
      gsc_date_range: pagesParams.gsc_date_range,
      status_code: undefined,
      page_type: undefined,
      page_bucket: undefined,
      page_type_confidence_min: undefined,
      page_type_confidence_max: undefined,
      url_contains: undefined,
      title_contains: undefined,
      has_title: undefined,
      has_meta_description: undefined,
      has_h1: undefined,
      canonical_missing: undefined,
      robots_meta_contains: undefined,
      noindex_like: undefined,
      non_indexable_like: undefined,
      status_code_min: undefined,
      status_code_max: undefined,
      title_exact: undefined,
      meta_description_exact: undefined,
      content_text_hash_exact: undefined,
      title_too_short: undefined,
      title_too_long: undefined,
      meta_too_short: undefined,
      meta_too_long: undefined,
      multiple_h1: undefined,
      missing_h2: undefined,
      self_canonical: undefined,
      canonical_to_other_url: undefined,
      canonical_to_non_200: undefined,
      canonical_to_redirect: undefined,
      thin_content: undefined,
      duplicate_content: undefined,
      missing_alt_images: undefined,
      no_images: undefined,
      oversized: undefined,
      was_rendered: undefined,
      js_heavy_like: undefined,
      schema_present: undefined,
      schema_type: undefined,
      has_render_error: undefined,
      has_x_robots_tag: undefined,
      has_technical_issue: undefined,
      has_gsc_data: undefined,
      has_cannibalization: undefined,
      priority_level: undefined,
      opportunity_type: undefined,
      priority_score_min: undefined,
      priority_score_max: undefined,
      gsc_clicks_min: undefined,
      gsc_clicks_max: undefined,
      gsc_impressions_min: undefined,
      gsc_impressions_max: undefined,
      gsc_ctr_min: undefined,
      gsc_ctr_max: undefined,
      gsc_position_min: undefined,
      gsc_position_max: undefined,
      gsc_top_queries_min: undefined,
    })
  }

  function handleTableSort(sortBy: string, nextSortOrder: SortOrder) {
    updateParams({
      sort_by: sortBy,
      sort_order: nextSortOrder,
      page: 1,
    })
  }

  const quickFilters = [
    {
      label: t('pages.quickFilters.highPriority'),
      isActive: (pagesParams.priority_score_min ?? 0) >= 45,
      onClick: () =>
        togglePreset((pagesParams.priority_score_min ?? 0) >= 45, {
          priority_score_min: 45,
          sort_by: 'priority_score',
          sort_order: 'desc',
        }),
    },
    {
      label: t('pages.quickFilters.quickWins'),
      isActive: pagesParams.opportunity_type === 'QUICK_WINS',
      onClick: () =>
        togglePreset(pagesParams.opportunity_type === 'QUICK_WINS', {
          opportunity_type: 'QUICK_WINS',
          sort_by: 'priority_score',
          sort_order: 'desc',
        }),
    },
    {
      label: t('pages.quickFilters.trafficTechnical'),
      isActive: pagesParams.opportunity_type === 'TRAFFIC_WITH_TECHNICAL_ISSUES',
      onClick: () =>
        togglePreset(pagesParams.opportunity_type === 'TRAFFIC_WITH_TECHNICAL_ISSUES', {
          opportunity_type: 'TRAFFIC_WITH_TECHNICAL_ISSUES',
          sort_by: 'priority_score',
          sort_order: 'desc',
        }),
    },
    {
      label: t('pages.quickFilters.highImpressionsLowCtrOpportunity'),
      isActive: pagesParams.opportunity_type === 'HIGH_IMPRESSIONS_LOW_CTR',
      onClick: () =>
        togglePreset(pagesParams.opportunity_type === 'HIGH_IMPRESSIONS_LOW_CTR', {
          opportunity_type: 'HIGH_IMPRESSIONS_LOW_CTR',
          sort_by: 'priority_score',
          sort_order: 'desc',
        }),
    },
    {
      label: t('pages.quickFilters.lowHangingFruit'),
      isActive: pagesParams.opportunity_type === 'LOW_HANGING_FRUIT',
      onClick: () =>
        togglePreset(pagesParams.opportunity_type === 'LOW_HANGING_FRUIT', {
          opportunity_type: 'LOW_HANGING_FRUIT',
          sort_by: 'priority_score',
          sort_order: 'desc',
        }),
    },
    {
      label: t('pages.quickFilters.underlinked'),
      isActive: pagesParams.opportunity_type === 'UNDERLINKED_OPPORTUNITIES',
      onClick: () =>
        togglePreset(pagesParams.opportunity_type === 'UNDERLINKED_OPPORTUNITIES', {
          opportunity_type: 'UNDERLINKED_OPPORTUNITIES',
          sort_by: 'priority_score',
          sort_order: 'desc',
        }),
    },
    {
      label: t('pages.quickFilters.highRiskPages'),
      isActive: pagesParams.opportunity_type === 'HIGH_RISK_PAGES',
      onClick: () =>
        togglePreset(pagesParams.opportunity_type === 'HIGH_RISK_PAGES', {
          opportunity_type: 'HIGH_RISK_PAGES',
          sort_by: 'priority_score',
          sort_order: 'desc',
        }),
    },
    {
      label: t('pages.quickFilters.titleTooShort'),
      isActive: pagesParams.title_too_short === true,
      onClick: () => togglePreset(pagesParams.title_too_short === true, { title_too_short: 'true' }),
    },
    {
      label: t('pages.quickFilters.titleTooLong'),
      isActive: pagesParams.title_too_long === true,
      onClick: () => togglePreset(pagesParams.title_too_long === true, { title_too_long: 'true' }),
    },
    {
      label: t('pages.quickFilters.metaTooShort'),
      isActive: pagesParams.meta_too_short === true,
      onClick: () => togglePreset(pagesParams.meta_too_short === true, { meta_too_short: 'true' }),
    },
    {
      label: t('pages.quickFilters.metaTooLong'),
      isActive: pagesParams.meta_too_long === true,
      onClick: () => togglePreset(pagesParams.meta_too_long === true, { meta_too_long: 'true' }),
    },
    {
      label: t('pages.quickFilters.multipleH1'),
      isActive: pagesParams.multiple_h1 === true,
      onClick: () => togglePreset(pagesParams.multiple_h1 === true, { multiple_h1: 'true' }),
    },
    {
      label: t('pages.quickFilters.missingH2'),
      isActive: pagesParams.missing_h2 === true,
      onClick: () => togglePreset(pagesParams.missing_h2 === true, { missing_h2: 'true' }),
    },
    {
      label: t('pages.quickFilters.canonicalToOther'),
      isActive: pagesParams.canonical_to_other_url === true,
      onClick: () => togglePreset(pagesParams.canonical_to_other_url === true, { canonical_to_other_url: 'true' }),
    },
    {
      label: t('pages.quickFilters.noindexLike'),
      isActive: pagesParams.non_indexable_like === true,
      onClick: () => togglePreset(pagesParams.non_indexable_like === true, { non_indexable_like: 'true' }),
    },
    {
      label: t('pages.quickFilters.thinContent'),
      isActive: pagesParams.thin_content === true,
      onClick: () => togglePreset(pagesParams.thin_content === true, { thin_content: 'true' }),
    },
    {
      label: t('pages.quickFilters.duplicateContent'),
      isActive: pagesParams.duplicate_content === true,
      onClick: () => togglePreset(pagesParams.duplicate_content === true, { duplicate_content: 'true' }),
    },
    {
      label: t('pages.quickFilters.missingAlt'),
      isActive: pagesParams.missing_alt_images === true,
      onClick: () => togglePreset(pagesParams.missing_alt_images === true, { missing_alt_images: 'true' }),
    },
    {
      label: t('pages.quickFilters.oversized'),
      isActive: pagesParams.oversized === true,
      onClick: () => togglePreset(pagesParams.oversized === true, { oversized: 'true' }),
    },
    {
      label: t('pages.quickFilters.rendered'),
      isActive: pagesParams.was_rendered === true,
      onClick: () => togglePreset(pagesParams.was_rendered === true, { was_rendered: 'true' }),
    },
    {
      label: t('pages.quickFilters.jsHeavyLike'),
      isActive: pagesParams.js_heavy_like === true,
      onClick: () => togglePreset(pagesParams.js_heavy_like === true, { js_heavy_like: 'true' }),
    },
    {
      label: t('pages.quickFilters.renderErrors'),
      isActive: pagesParams.has_render_error === true,
      onClick: () => togglePreset(pagesParams.has_render_error === true, { has_render_error: 'true' }),
    },
    {
      label: t('pages.quickFilters.schemaPresent'),
      isActive: pagesParams.schema_present === true,
      onClick: () => togglePreset(pagesParams.schema_present === true, { schema_present: 'true' }),
    },
    {
      label: t('pages.quickFilters.xRobots'),
      isActive: pagesParams.has_x_robots_tag === true,
      onClick: () => togglePreset(pagesParams.has_x_robots_tag === true, { has_x_robots_tag: 'true' }),
    },
    {
      label: t('pages.quickFilters.impressionsWithIssue'),
      isActive: pagesParams.has_technical_issue === true && (pagesParams.gsc_impressions_min ?? 0) >= 1,
      onClick: () =>
        togglePreset(
          pagesParams.has_technical_issue === true && (pagesParams.gsc_impressions_min ?? 0) >= 1,
          { has_technical_issue: 'true', gsc_impressions_min: 1 },
        ),
    },
    {
      label: t('pages.quickFilters.clicksWithIssue'),
      isActive: pagesParams.has_technical_issue === true && (pagesParams.gsc_clicks_min ?? 0) >= 1,
      onClick: () =>
        togglePreset(
          pagesParams.has_technical_issue === true && (pagesParams.gsc_clicks_min ?? 0) >= 1,
          { has_technical_issue: 'true', gsc_clicks_min: 1 },
        ),
    },
    {
      label: t('pages.quickFilters.lowCtrHighImpressions'),
      isActive: (pagesParams.gsc_impressions_min ?? 0) >= 100 && (pagesParams.gsc_ctr_max ?? 1) <= 0.02,
      onClick: () =>
        togglePreset(
          (pagesParams.gsc_impressions_min ?? 0) >= 100 && (pagesParams.gsc_ctr_max ?? 1) <= 0.02,
          { gsc_impressions_min: 100, gsc_ctr_max: 0.02 },
        ),
    },
    {
      label: t('pages.quickFilters.highImpressionsWeakPosition'),
      isActive: (pagesParams.gsc_impressions_min ?? 0) >= 100 && (pagesParams.gsc_position_min ?? 0) >= 8,
      onClick: () =>
        togglePreset(
          (pagesParams.gsc_impressions_min ?? 0) >= 100 && (pagesParams.gsc_position_min ?? 0) >= 8,
          { gsc_impressions_min: 100, gsc_position_min: 8 },
        ),
    },
  ]

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('pages.page.eyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">
              {t('pages.page.title', { jobId })}
            </h1>
            <p className="mt-2 text-sm text-stone-600">{t('pages.page.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <JobNavigation jobId={jobId} />
            <a
              href={buildPagesExportHref(jobId, searchParams, false)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('pages.page.exportFull')}
            </a>
            <a
              href={buildPagesExportHref(jobId, searchParams, true)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {filteredView ? t('pages.page.exportCurrentView') : t('pages.page.exportCurrentView')}
            </a>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-900">{t('pages.gsc.title')}</h2>
            <p className="mt-1 text-sm text-stone-600">{t('pages.gsc.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => updateParams({ gsc_date_range: 'last_28_days', page: 1 })}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                pagesParams.gsc_date_range === 'last_28_days'
                  ? 'border border-stone-950 bg-stone-950 !text-white'
                  : 'border border-stone-300 bg-white text-stone-700 hover:border-stone-400 hover:bg-stone-100'
              }`}
            >
              {t('pages.gsc.last28Days')}
            </button>
            <button
              type="button"
              onClick={() => updateParams({ gsc_date_range: 'last_90_days', page: 1 })}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                pagesParams.gsc_date_range === 'last_90_days'
                  ? 'border border-stone-950 bg-stone-950 !text-white'
                  : 'border border-stone-300 bg-white text-stone-700 hover:border-stone-400 hover:bg-stone-100'
              }`}
            >
              {t('pages.gsc.last90Days')}
            </button>
            <Link
              to={`/jobs/${jobId}/gsc?gsc_date_range=${pagesParams.gsc_date_range}`}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('pages.gsc.openSection')}
            </Link>
            <Link
              to={`/jobs/${jobId}/opportunities?gsc_date_range=${pagesParams.gsc_date_range}`}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('pages.gsc.openOpportunities')}
            </Link>
          </div>
        </div>
      </section>

      {taxonomySummaryQuery.data ? (
        <section className="space-y-3">
          <SummaryCards
            items={[
              {
                label: t('pages.summary.totalPages'),
                value: taxonomySummaryQuery.data.total_pages,
                hint: t('pages.summary.versionHint', { version: taxonomySummaryQuery.data.page_type_version }),
              },
              {
                label: t('pages.summary.commercial'),
                value: taxonomySummaryQuery.data.counts_by_page_bucket.commercial,
              },
              {
                label: t('pages.summary.informational'),
                value: taxonomySummaryQuery.data.counts_by_page_bucket.informational,
              },
              {
                label: t('pages.summary.utility'),
                value: taxonomySummaryQuery.data.counts_by_page_bucket.utility,
              },
              {
                label: t('pages.summary.trust'),
                value: taxonomySummaryQuery.data.counts_by_page_bucket.trust,
              },
              {
                label: t('pages.summary.product'),
                value: taxonomySummaryQuery.data.counts_by_page_type.product,
              },
              {
                label: t('pages.summary.category'),
                value: taxonomySummaryQuery.data.counts_by_page_type.category,
              },
              {
                label: t('pages.summary.blogArticle'),
                value: taxonomySummaryQuery.data.counts_by_page_type.blog_article,
              },
            ]}
          />
          <section className="rounded-3xl border border-stone-300 bg-white/85 p-4 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h2 className="text-base font-semibold text-stone-900">{t('pages.summary.taxonomyTitle')}</h2>
                <p className="mt-1 text-sm text-stone-600">{t('pages.summary.taxonomyDescription')}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {TAXONOMY_FOCUS_PAGE_TYPES.map((pageType) => (
                  <button
                    key={pageType}
                    type="button"
                    aria-pressed={pagesParams.page_type === pageType}
                    onClick={() => togglePageTypeFilter(pageType)}
                    className="transition hover:-translate-y-0.5"
                  >
                    {renderBadge(
                      t(`pages.taxonomy.pageTypes.${pageType}`) +
                        `: ${taxonomySummaryQuery.data.counts_by_page_type[pageType] ?? 0}`,
                      getPageTypeTone(pageType),
                      pagesParams.page_type === pageType,
                    )}
                  </button>
                ))}
              </div>
            </div>
          </section>
        </section>
      ) : null}

      <QuickFilterBar title={t('pages.quickFilters.title')} items={quickFilters} />

      <FilterPanel
        title={t('pages.filters.title')}
        description={t('pages.filters.description')}
        onReset={resetFilters}
        bodyClassName="grid gap-4"
      >
        <div className={PAGES_FILTER_GRID_CLASS}>
          <label className="grid gap-1 text-sm text-stone-700">
            <span>{t('pages.filters.statusCode')}</span>
            <select
              value={pagesParams.status_code ?? ''}
              onChange={(event) =>
                updateParams({
                  status_code: event.target.value || undefined,
                  status_code_min: undefined,
                  status_code_max: undefined,
                  page: 1,
                })}
              className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            >
              <option value="">{t('common.any')}</option>
              {availableStatusCodes.map((statusCode) => (
                <option key={statusCode} value={statusCode}>
                  {statusCode}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm text-stone-700">
            <span>{t('pages.filters.pageType')}</span>
            <select
              value={pagesParams.page_type ?? ''}
              onChange={(event) => updateFilter('page_type', event.target.value)}
              className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            >
              <option value="">{t('common.any')}</option>
              {PAGE_TYPES.map((pageType) => (
                <option key={pageType} value={pageType}>
                  {t(`pages.taxonomy.pageTypes.${pageType}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm text-stone-700">
            <span>{t('pages.filters.pageBucket')}</span>
            <select
              value={pagesParams.page_bucket ?? ''}
              onChange={(event) => updateFilter('page_bucket', event.target.value)}
              className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            >
              <option value="">{t('common.any')}</option>
              {PAGE_BUCKETS.map((pageBucket) => (
                <option key={pageBucket} value={pageBucket}>
                  {t(`pages.taxonomy.pageBuckets.${pageBucket}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm text-stone-700">
            <span>{t('pages.filters.urlContains')}</span>
            <input
              value={searchParams.get('url_contains') ?? ''}
              onChange={(event) => updateFilter('url_contains', event.target.value)}
              className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
              placeholder={t('pages.filters.urlContainsPlaceholder')}
            />
          </label>
          <label className="grid gap-1 text-sm text-stone-700">
            <span>{t('pages.filters.titleContains')}</span>
            <input
              value={searchParams.get('title_contains') ?? ''}
              onChange={(event) => updateFilter('title_contains', event.target.value)}
              className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
              placeholder={t('pages.filters.titleContainsPlaceholder')}
            />
          </label>
          {hasGscIntegration ? (
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('pages.filters.gscMinClicks')}</span>
              <input
                type="number"
                value={searchParams.get('gsc_clicks_min') ?? ''}
                onChange={(event) => updateFilter('gsc_clicks_min', event.target.value)}
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                placeholder="1"
              />
            </label>
          ) : null}
        </div>
        <div className="flex w-full justify-end">
          <button
            type="button"
            onClick={() => setShowAllFilters((current) => !current)}
            className="rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {showAllFilters ? t('common.hideExtraFilters') : t('common.showAllFilters')}
          </button>
        </div>
        {showAllFilters ? (
          <div className={PAGES_FILTER_GRID_CLASS}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.hasTitle')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_title')}
            onChange={(event) => updateFilter('has_title', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.hasMetaDescription')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_meta_description')}
            onChange={(event) => updateFilter('has_meta_description', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.titleTooShort')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'title_too_short')}
            onChange={(event) => updateFilter('title_too_short', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.titleTooLong')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'title_too_long')}
            onChange={(event) => updateFilter('title_too_long', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.metaTooShort')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'meta_too_short')}
            onChange={(event) => updateFilter('meta_too_short', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.metaTooLong')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'meta_too_long')}
            onChange={(event) => updateFilter('meta_too_long', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.hasH1')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_h1')}
            onChange={(event) => updateFilter('has_h1', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.multipleH1')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'multiple_h1')}
            onChange={(event) => updateFilter('multiple_h1', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.missingH2')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'missing_h2')}
            onChange={(event) => updateFilter('missing_h2', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.canonicalMissing')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'canonical_missing')}
            onChange={(event) => updateFilter('canonical_missing', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.canonicalToOther')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'canonical_to_other_url')}
            onChange={(event) => updateFilter('canonical_to_other_url', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.robotsMetaContains')}</span>
          <input
            value={searchParams.get('robots_meta_contains') ?? ''}
            onChange={(event) => updateFilter('robots_meta_contains', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder={t('pages.filters.robotsMetaPlaceholder')}
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.noindexLike')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'noindex_like')}
            onChange={(event) => updateFilter('noindex_like', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.thinContent')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'thin_content')}
            onChange={(event) => updateFilter('thin_content', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.duplicateContent')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'duplicate_content')}
            onChange={(event) => updateFilter('duplicate_content', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.missingAltImages')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'missing_alt_images')}
            onChange={(event) => updateFilter('missing_alt_images', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.oversized')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'oversized')}
            onChange={(event) => updateFilter('oversized', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.nonIndexableLike')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'non_indexable_like')}
            onChange={(event) => updateFilter('non_indexable_like', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.exactTitle')}</span>
          <input
            value={searchParams.get('title_exact') ?? ''}
            onChange={(event) => updateFilter('title_exact', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder={t('pages.filters.exactTitlePlaceholder')}
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.exactMetaDescription')}</span>
          <input
            value={searchParams.get('meta_description_exact') ?? ''}
            onChange={(event) => updateFilter('meta_description_exact', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder={t('pages.filters.exactMetaDescriptionPlaceholder')}
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.wasRendered')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'was_rendered')}
            onChange={(event) => updateFilter('was_rendered', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.jsHeavyLike')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'js_heavy_like')}
            onChange={(event) => updateFilter('js_heavy_like', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.schemaPresent')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'schema_present')}
            onChange={(event) => updateFilter('schema_present', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.schemaType')}</span>
          <input
            value={searchParams.get('schema_type') ?? ''}
            onChange={(event) => updateFilter('schema_type', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder={t('pages.filters.schemaTypePlaceholder')}
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.hasRenderError')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_render_error')}
            onChange={(event) => updateFilter('has_render_error', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.hasXRobotsTag')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_x_robots_tag')}
            onChange={(event) => updateFilter('has_x_robots_tag', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.hasTechnicalIssue')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_technical_issue')}
            onChange={(event) => updateFilter('has_technical_issue', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.hasGscData')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_gsc_data')}
            onChange={(event) => updateFilter('has_gsc_data', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.hasCannibalization')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_cannibalization')}
            onChange={(event) => updateFilter('has_cannibalization', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.priorityLevel')}</span>
          <select
            value={pagesParams.priority_level ?? ''}
            onChange={(event) => updateFilter('priority_level', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="critical">{t('pages.priority.level.critical')}</option>
            <option value="high">{t('pages.priority.level.high')}</option>
            <option value="medium">{t('pages.priority.level.medium')}</option>
            <option value="low">{t('pages.priority.level.low')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.opportunityType')}</span>
          <select
            value={pagesParams.opportunity_type ?? ''}
            onChange={(event) => updateFilter('opportunity_type', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            {OPPORTUNITY_TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`opportunities.types.${type}.title`)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.pageTypeConfidenceMin')}</span>
          <input
            type="number"
            min="0"
            max="100"
            step="1"
            value={
              searchParams.get('page_type_confidence_min')
                ? String(Number(searchParams.get('page_type_confidence_min')) * 100)
                : ''
            }
            onChange={(event) =>
              updateFilter(
                'page_type_confidence_min',
                event.target.value ? String(Number(event.target.value) / 100) : '',
              )
            }
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="70"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.pageTypeConfidenceMax')}</span>
          <input
            type="number"
            min="0"
            max="100"
            step="1"
            value={
              searchParams.get('page_type_confidence_max')
                ? String(Number(searchParams.get('page_type_confidence_max')) * 100)
                : ''
            }
            onChange={(event) =>
              updateFilter(
                'page_type_confidence_max',
                event.target.value ? String(Number(event.target.value) / 100) : '',
              )
            }
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="95"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.priorityScoreMin')}</span>
          <input
            type="number"
            value={searchParams.get('priority_score_min') ?? ''}
            onChange={(event) => updateFilter('priority_score_min', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="45"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.priorityScoreMax')}</span>
          <input
            type="number"
            value={searchParams.get('priority_score_max') ?? ''}
            onChange={(event) => updateFilter('priority_score_max', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="100"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.gscMinImpressions')}</span>
          <input
            type="number"
            value={searchParams.get('gsc_impressions_min') ?? ''}
            onChange={(event) => updateFilter('gsc_impressions_min', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="100"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.gscMaxCtr')}</span>
          <input
            type="number"
            step="0.01"
            value={searchParams.get('gsc_ctr_max') ? String(Number(searchParams.get('gsc_ctr_max')) * 100) : ''}
            onChange={(event) => updateFilter('gsc_ctr_max', event.target.value ? String(Number(event.target.value) / 100) : '')}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="2"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.gscMinPosition')}</span>
          <input
            type="number"
            step="0.1"
            value={searchParams.get('gsc_position_min') ?? ''}
            onChange={(event) => updateFilter('gsc_position_min', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="8"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pages.filters.gscMinTopQueries')}</span>
          <input
            type="number"
            value={searchParams.get('gsc_top_queries_min') ?? ''}
            onChange={(event) => updateFilter('gsc_top_queries_min', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="1"
          />
        </label>
          </div>
        ) : null}
      </FilterPanel>

      {pagesQuery.isLoading ? <LoadingState label={t('pages.page.loading')} /> : null}
      {pagesQuery.isError ? (
        <ErrorState
          title={t('pages.errors.requestTitle')}
          message={getUiErrorMessage(pagesQuery.error, t)}
        />
      ) : null}
      {pagesQuery.isSuccess && pagesQuery.data.items.length === 0 ? (
        <EmptyState title={t('pages.empty.title')} description={t('pages.empty.description')} />
      ) : null}
      {pagesQuery.isSuccess && pagesQuery.data.items.length > 0 ? (
        <>
          <DataTable
            columns={[
              {
                key: 'url',
                header: t('pages.table.url'),
                sortKey: 'url',
                minWidth: 380,
                cell: (page) => (
                  <div className="space-y-1.5">
                    <p className="font-medium text-stone-900" title={page.url}>
                      {page.url}
                    </p>
                    <p className="text-xs text-stone-500" title={page.normalized_url}>
                      {page.normalized_url}
                    </p>
                    <p className="text-xs text-stone-500">{t('pages.table.depthLabel', { count: page.depth })}</p>
                    <Link
                      to={`/jobs/${jobId}/gsc?page_id=${page.id}&gsc_date_range=${pagesParams.gsc_date_range}`}
                      className="inline-flex text-xs font-medium text-teal-700 transition hover:text-teal-600"
                    >
                      {t('pages.table.openTopQueries')}
                    </Link>
                    <UrlActions url={page.url} />
                  </div>
                ),
              },
              {
                key: 'status',
                header: t('pages.table.status'),
                sortKey: 'status_code',
                minWidth: 90,
                cell: (page) => formatNullable(page.status_code),
              },
              {
                key: 'taxonomy',
                header: t('pages.table.taxonomy'),
                sortKey: 'page_type_confidence',
                minWidth: 240,
                cell: (page) => (
                  <div className="min-w-[13rem] space-y-2">
                    <div className="flex flex-wrap gap-1.5">
                      {renderBadge(t(`pages.taxonomy.pageTypes.${page.page_type}`), getPageTypeTone(page.page_type))}
                      {renderBadge(
                        t(`pages.taxonomy.pageBuckets.${page.page_bucket}`),
                        getPageBucketTone(page.page_bucket),
                      )}
                    </div>
                    <div className="space-y-1">
                      <MetricLine
                        label={t('pages.taxonomy.confidence')}
                        value={formatPercent(page.page_type_confidence)}
                      />
                      <MetricLine
                        label={t('pages.taxonomy.version')}
                        value={formatNullable(page.page_type_version)}
                      />
                    </div>
                    {page.page_type_rationale ? (
                      <p className="text-xs leading-5 text-stone-600" title={page.page_type_rationale}>
                        {page.page_type_rationale}
                      </p>
                    ) : null}
                  </div>
                ),
              },
              {
                key: 'title',
                header: t('pages.table.title'),
                sortKey: 'title',
                minWidth: 320,
                cell: (page) => (
                  <PageTextCell
                    value={page.title}
                    length={page.title_length}
                    lengthLabel={t('pages.table.length')}
                    allowLongWrap
                  />
                ),
              },
              {
                key: 'title-length',
                header: t('pages.table.titleLength'),
                sortKey: 'title_length',
                minWidth: 100,
                cell: (page) => formatNullable(page.title_length),
              },
              {
                key: 'meta',
                header: t('pages.table.metaDescription'),
                sortKey: 'meta_description',
                minWidth: 380,
                cell: (page) => (
                  <PageTextCell
                    value={page.meta_description}
                    length={page.meta_description_length}
                    lengthLabel={t('pages.table.length')}
                  />
                ),
              },
              {
                key: 'meta-length',
                header: t('pages.table.metaDescriptionLength'),
                sortKey: 'meta_description_length',
                minWidth: 100,
                cell: (page) => formatNullable(page.meta_description_length),
              },
              {
                key: 'headings',
                header: t('pages.table.headings'),
                sortKey: 'h1',
                minWidth: 320,
                cell: (page) => (
                  <div className="space-y-1">
                    <p
                      className={`text-sm text-stone-900 ${
                        typeof page.h1 === 'string' && (page.h1_length ?? page.h1.length) > 100
                          ? 'max-w-[22rem] whitespace-normal break-words'
                          : 'whitespace-nowrap'
                      }`}
                      title={page.h1 ?? ''}
                    >
                      {page.h1 ?? '-'}
                    </p>
                    <MetricLine label="H1" value={formatNullable(page.h1_count)} />
                    <MetricLine label="H2" value={formatNullable(page.h2_count)} />
                  </div>
                ),
              },
              {
                key: 'h1-length',
                header: t('pages.table.h1Length'),
                sortKey: 'h1_length',
                minWidth: 100,
                cell: (page) => formatNullable(page.h1_length),
              },
              {
                key: 'canonical',
                header: t('pages.table.canonical'),
                sortKey: 'canonical_url',
                minWidth: 240,
                cell: (page) => (
                  <div className="space-y-1">
                    <p className="text-sm text-stone-900" title={page.canonical_url ?? ''}>
                      {page.canonical_url ?? '-'}
                    </p>
                    <p className="text-xs text-stone-500" title={page.robots_meta ?? ''}>
                      {t('pages.table.robotsLabel')}: {page.robots_meta ?? '-'}
                    </p>
                    <p className="text-xs text-stone-500" title={page.x_robots_tag ?? ''}>
                      {t('pages.table.xRobotsLabel')}: {page.x_robots_tag ?? '-'}
                    </p>
                  </div>
                ),
              },
              {
                key: 'metrics',
                header: t('pages.table.metrics'),
                sortKey: 'word_count',
                minWidth: 160,
                cell: (page) => (
                  <div className="min-w-[11rem] space-y-1">
                    <MetricLine label={t('pages.metrics.words')} value={formatNullable(page.word_count)} />
                    <MetricLine label={t('pages.metrics.images')} value={formatNullable(page.images_count)} />
                    <MetricLine label={t('pages.metrics.missingAlt')} value={formatNullable(page.images_missing_alt_count)} />
                    <MetricLine label={t('pages.metrics.htmlSize')} value={formatBytes(page.html_size_bytes)} />
                  </div>
                ),
              },
              {
                key: 'gsc',
                header: t('pages.table.gsc'),
                sortKey: 'gsc_impressions',
                minWidth: 170,
                cell: (page) => (
                  <div className="min-w-[11rem] space-y-1">
                    <MetricLine label={t('pages.gsc.clicks')} value={formatNullable(pageGscValue(page, 'clicks', pagesParams.gsc_date_range) as number | null)} />
                    <MetricLine label={t('pages.gsc.impressions')} value={formatNullable(pageGscValue(page, 'impressions', pagesParams.gsc_date_range) as number | null)} />
                    <MetricLine label={t('pages.gsc.ctr')} value={formatPercent(pageGscValue(page, 'ctr', pagesParams.gsc_date_range) as number | null)} />
                    <MetricLine label={t('pages.gsc.position')} value={formatPosition(pageGscValue(page, 'position', pagesParams.gsc_date_range) as number | null)} />
                    <MetricLine label={t('pages.gsc.topQueries')} value={formatNullable(pageGscValue(page, 'top_queries_count', pagesParams.gsc_date_range) as number | null)} />
                  </div>
                ),
              },
              {
                key: 'priority',
                header: t('pages.table.priority'),
                sortKey: 'priority_score',
                minWidth: 340,
                cell: (page) => (
                  <div className="min-w-[18rem] space-y-2">
                    <div className="flex flex-wrap gap-1.5">
                      {renderBadge(t('pages.priority.scoreBadge', { score: page.priority_score }), getPriorityTone(page.priority_level))}
                      {renderBadge(t(`pages.priority.level.${page.priority_level}`), getPriorityTone(page.priority_level))}
                      {page.primary_opportunity_type
                        ? renderBadge(
                            t(`opportunities.types.${page.primary_opportunity_type}.title`),
                            getOpportunityTone(page.primary_opportunity_type),
                          )
                        : null}
                    </div>
                    <div className="space-y-1">
                      <MetricLine label={t('pages.priority.trafficComponent')} value={formatNullable(page.traffic_component)} />
                      <MetricLine label={t('pages.priority.issueComponent')} value={formatNullable(page.issue_component)} />
                      <MetricLine
                        label={t('pages.priority.opportunityComponent')}
                        value={formatNullable(page.opportunity_component)}
                      />
                      <MetricLine
                        label={t('pages.priority.internalLinkingComponent')}
                        value={formatNullable(page.internal_linking_component)}
                      />
                      <MetricLine label={t('pages.priority.opportunityCount')} value={formatNullable(page.opportunity_count)} />
                      <MetricLine
                        label={t('pages.priority.internalLinks')}
                        value={`${page.incoming_internal_links} / ${page.incoming_internal_linking_pages}`}
                      />
                    </div>
                    <p className="text-xs leading-5 text-stone-600" title={page.priority_rationale}>
                      {page.priority_rationale}
                    </p>
                    {page.primary_opportunity_type ? (
                      <Link
                        to={`/jobs/${jobId}/opportunities?gsc_date_range=${pagesParams.gsc_date_range}&opportunity_type=${page.primary_opportunity_type}`}
                        className="inline-flex text-xs font-medium text-teal-700 transition hover:text-teal-600"
                      >
                        {t('pages.table.openOpportunity')}
                      </Link>
                    ) : null}
                    {page.has_cannibalization ? (
                      <div className="space-y-1 border-t border-stone-200 pt-2 text-xs text-stone-600">
                        <MetricLine label={t('pages.cannibalization.label')} value={t('common.yes')} />
                        <MetricLine label={t('pages.cannibalization.competingUrls')} value={formatNullable(page.cannibalization_competing_urls_count)} />
                        <MetricLine label={t('pages.cannibalization.overlapStrength')} value={formatPercent(page.cannibalization_overlap_strength)} />
                        <MetricLine
                          label={t('pages.cannibalization.strongestCompetitor')}
                          value={formatNullable(page.cannibalization_strongest_competing_url)}
                        />
                        {page.cannibalization_recommendation_type ? (
                          <p>{t(`cannibalization.recommendations.${page.cannibalization_recommendation_type}`)}</p>
                        ) : null}
                        <Link
                          to={buildCannibalizationLink(jobId, page.id, pagesParams.gsc_date_range)}
                          className="inline-flex text-xs font-medium text-teal-700 transition hover:text-teal-600"
                        >
                          {t('pages.cannibalization.openDetails')}
                        </Link>
                      </div>
                    ) : null}
                  </div>
                ),
              },
              {
                key: 'signals',
                header: t('pages.table.signals'),
                minWidth: 220,
                cell: (page) => (
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap gap-1.5">
                      {buildPageSignals(page, t).map((signal, index) => (
                        <span key={`${signal.label}-${index}`}>{renderBadge(signal.label, signal.tone)}</span>
                      ))}
                    </div>
                    {page.schema_types_text ? (
                      <p className="text-xs text-stone-500" title={page.schema_types_text}>
                        {t('pages.table.schemaLabel')}: {page.schema_types_text}
                      </p>
                    ) : null}
                  </div>
                ),
              },
              {
                key: 'response',
                header: t('pages.table.responseTime'),
                sortKey: 'response_time_ms',
                minWidth: 110,
                cell: (page) => formatResponseTime(page.response_time_ms),
              },
              {
                key: 'fetched',
                header: t('pages.table.fetchedAt'),
                sortKey: 'fetched_at',
                minWidth: 170,
                cell: (page) => formatDateTime(page.fetched_at),
              },
            ]}
            rows={pagesQuery.data.items}
            rowKey={(page) => page.id}
            sortBy={pagesParams.sort_by}
            sortOrder={pagesParams.sort_order as SortOrder}
            onSortChange={handleTableSort}
          />
          <PaginationControls
            page={pagesQuery.data.page}
            pageSize={pagesQuery.data.page_size}
            totalItems={pagesQuery.data.total_items}
            totalPages={pagesQuery.data.total_pages}
            onPageChange={(page) => updateParams({ page })}
            onPageSizeChange={(pageSize) => updateParams({ page_size: pageSize, page: 1 })}
          />
        </>
      ) : null}
    </div>
  )
}
