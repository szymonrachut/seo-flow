import { startTransition, useEffect, useMemo } from 'react'
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
  CrawlCompareChangeType,
  MetricTrend,
  OpportunityType,
  SortOrder,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatPercent, formatPosition } from '../../utils/format'
import { mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
import {
  type CrawlCompareQueryParams,
  type GscCompareQueryParams,
  useCrawlCompareQuery,
  useGscCompareQuery,
  useTrendsOverviewQuery,
} from './api'

const CHANGE_TYPES: CrawlCompareChangeType[] = ['improved', 'worsened', 'unchanged', 'new', 'missing']
const METRIC_TRENDS: MetricTrend[] = ['improved', 'worsened', 'flat']

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

function readChangeType(searchParams: URLSearchParams): CrawlCompareChangeType | undefined {
  const value = searchParams.get('change_type')
  return CHANGE_TYPES.includes(value as CrawlCompareChangeType) ? (value as CrawlCompareChangeType) : undefined
}

function readMetricTrend(searchParams: URLSearchParams, key: string): MetricTrend | undefined {
  const value = searchParams.get(key)
  return METRIC_TRENDS.includes(value as MetricTrend) ? (value as MetricTrend) : undefined
}

function readCrawlCompareParams(searchParams: URLSearchParams, baselineJobId: number | undefined): CrawlCompareQueryParams | null {
  if (!baselineJobId) {
    return null
  }

  const sortBy = searchParams.get('crawl_sort_by')
  const sortOrder = searchParams.get('crawl_sort_order')

  return {
    baseline_job_id: baselineJobId,
    gsc_date_range: searchParams.get('crawl_gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    page: parseIntegerParam(searchParams.get('crawl_page'), 1),
    page_size: parseIntegerParam(searchParams.get('crawl_page_size'), 25),
    sort_by:
      sortBy === 'url' ||
      sortBy === 'change_type' ||
      sortBy === 'issues_resolved_count' ||
      sortBy === 'issues_added_count' ||
      sortBy === 'delta_word_count' ||
      sortBy === 'delta_schema_count' ||
      sortBy === 'delta_response_time_ms' ||
      sortBy === 'delta_incoming_internal_links' ||
      sortBy === 'delta_incoming_internal_linking_pages'
        ? sortBy
        : 'delta_priority_score',
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    change_type: readChangeType(searchParams),
    resolved_issues_min: parseIntegerParam(searchParams.get('resolved_issues_min'), undefined),
    added_issues_min: parseIntegerParam(searchParams.get('added_issues_min'), undefined),
    url_contains: searchParams.get('crawl_url_contains') || undefined,
  }
}

function readGscCompareParams(searchParams: URLSearchParams): GscCompareQueryParams {
  const sortBy = searchParams.get('gsc_sort_by')
  const sortOrder = searchParams.get('gsc_sort_order')

  return {
    baseline_gsc_range: searchParams.get('baseline_gsc_range') === 'last_28_days' ? 'last_28_days' : 'last_90_days',
    target_gsc_range: searchParams.get('target_gsc_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    page: parseIntegerParam(searchParams.get('gsc_page'), 1),
    page_size: parseIntegerParam(searchParams.get('gsc_page_size'), 25),
    sort_by:
      sortBy === 'url' ||
      sortBy === 'overall_trend' ||
      sortBy === 'delta_impressions' ||
      sortBy === 'delta_ctr' ||
      sortBy === 'delta_position' ||
      sortBy === 'delta_top_queries_count'
        ? sortBy
        : 'delta_clicks',
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    trend: readMetricTrend(searchParams, 'trend'),
    clicks_trend: readMetricTrend(searchParams, 'clicks_trend'),
    impressions_trend: readMetricTrend(searchParams, 'impressions_trend'),
    ctr_trend: readMetricTrend(searchParams, 'ctr_trend'),
    position_trend: readMetricTrend(searchParams, 'position_trend'),
    top_queries_trend: readMetricTrend(searchParams, 'top_queries_trend'),
    url_contains: searchParams.get('gsc_url_contains') || undefined,
  }
}

function buildPagesLink(jobId: number, opportunityType?: OpportunityType | null) {
  const params = new URLSearchParams()
  params.set('sort_by', 'priority_score')
  params.set('sort_order', 'desc')
  if (opportunityType) {
    params.set('opportunity_type', opportunityType)
  }
  return `/jobs/${jobId}/pages?${params.toString()}`
}

function buildOpportunitiesLink(jobId: number, opportunityType?: OpportunityType | null) {
  const params = new URLSearchParams()
  if (opportunityType) {
    params.set('opportunity_type', opportunityType)
  }
  const query = params.toString()
  return `/jobs/${jobId}/opportunities${query ? `?${query}` : ''}`
}

function buildGscLink(jobId: number, pageId?: number | null) {
  const params = new URLSearchParams()
  if (pageId) {
    params.set('page_id', String(pageId))
  }
  const query = params.toString()
  return `/jobs/${jobId}/gsc${query ? `?${query}` : ''}`
}

function buildCompareExportHref(jobId: number, kind: 'crawl' | 'gsc', searchParams: URLSearchParams) {
  const params = new URLSearchParams()
  if (kind === 'crawl') {
    ;[
      'baseline_job_id',
      'crawl_gsc_date_range',
      'crawl_sort_by',
      'crawl_sort_order',
      'change_type',
      'resolved_issues_min',
      'added_issues_min',
      'crawl_url_contains',
    ].forEach((key) => {
      const value = searchParams.get(key)
      if (!value) {
        return
      }
      const normalizedKey =
        key === 'crawl_gsc_date_range'
          ? 'gsc_date_range'
          : key === 'crawl_sort_by'
            ? 'sort_by'
            : key === 'crawl_sort_order'
              ? 'sort_order'
              : key === 'crawl_url_contains'
                ? 'url_contains'
                : key
      params.set(normalizedKey, value)
    })
    const query = params.toString()
    return buildApiUrl(`/crawl-jobs/${jobId}/export/crawl-compare.csv${query ? `?${query}` : ''}`)
  }

  ;[
    'baseline_gsc_range',
    'target_gsc_range',
    'gsc_sort_by',
    'gsc_sort_order',
    'trend',
    'clicks_trend',
    'impressions_trend',
    'ctr_trend',
    'position_trend',
    'top_queries_trend',
    'gsc_url_contains',
  ].forEach((key) => {
    const value = searchParams.get(key)
    if (!value) {
      return
    }
    const normalizedKey =
      key === 'gsc_sort_by'
        ? 'sort_by'
        : key === 'gsc_sort_order'
          ? 'sort_order'
          : key === 'gsc_url_contains'
            ? 'url_contains'
            : key
    params.set(normalizedKey, value)
  })
  const query = params.toString()
  return buildApiUrl(`/crawl-jobs/${jobId}/export/gsc-compare.csv${query ? `?${query}` : ''}`)
}

function formatSignedInteger(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  return value > 0 ? `+${value}` : String(value)
}

function formatSignedFloat(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) {
    return '-'
  }
  const fixed = value.toFixed(digits)
  return value > 0 ? `+${fixed}` : fixed
}

function formatSignedPercentPoints(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  const points = value * 100
  return points > 0 ? `+${points.toFixed(2)}pp` : `${points.toFixed(2)}pp`
}

function renderToneBadge(label: string, tone: 'stone' | 'rose' | 'amber' | 'teal' = 'stone') {
  const styles = {
    stone: 'border-stone-300 bg-stone-100 text-stone-700',
    rose: 'border-rose-200 bg-rose-50 text-rose-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    teal: 'border-teal-200 bg-teal-50 text-teal-700',
  }

  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${styles[tone]}`}>{label}</span>
}

function changeTone(changeType: CrawlCompareChangeType): 'stone' | 'rose' | 'amber' | 'teal' {
  if (changeType === 'worsened') {
    return 'rose'
  }
  if (changeType === 'improved') {
    return 'teal'
  }
  if (changeType === 'new' || changeType === 'missing') {
    return 'amber'
  }
  return 'stone'
}

function trendTone(trend: MetricTrend): 'stone' | 'rose' | 'amber' | 'teal' {
  if (trend === 'improved') {
    return 'teal'
  }
  if (trend === 'worsened') {
    return 'rose'
  }
  return 'stone'
}

export function TrendsPage() {
  const { t } = useTranslation()
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? t('documentTitle.trends', { jobId }) : t('nav.trends'))

  if (jobId === null) {
    return <ErrorState title={t('trends.invalidIdTitle')} message={t('trends.invalidIdMessage')} />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const overviewQuery = useTrendsOverviewQuery(jobId)
  const baselineJobId =
    parseIntegerParam(searchParams.get('baseline_job_id'), undefined) ??
    overviewQuery.data?.default_baseline_job_id ??
    undefined
  const crawlParams = useMemo(() => readCrawlCompareParams(searchParams, baselineJobId), [searchParams, baselineJobId])
  const gscParams = useMemo(() => readGscCompareParams(searchParams), [searchParams])

  useEffect(() => {
    if (!overviewQuery.data?.default_baseline_job_id || searchParams.get('baseline_job_id')) {
      return
    }
    const next = mergeSearchParams(searchParams, { baseline_job_id: overviewQuery.data.default_baseline_job_id })
    startTransition(() => setSearchParams(next, { replace: true }))
  }, [overviewQuery.data, searchParams, setSearchParams])

  const crawlCompareQuery = useCrawlCompareQuery(jobId, crawlParams, Boolean(crawlParams))
  const gscCompareQuery = useGscCompareQuery(jobId, gscParams, true)

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function resetCrawlFilters() {
    updateParams({
      baseline_job_id: baselineJobId,
      crawl_gsc_date_range: crawlParams?.gsc_date_range ?? 'last_28_days',
      crawl_page: 1,
      crawl_page_size: 25,
      crawl_sort_by: 'delta_priority_score',
      crawl_sort_order: 'desc',
      change_type: undefined,
      resolved_issues_min: undefined,
      added_issues_min: undefined,
      crawl_url_contains: undefined,
    })
  }

  function resetGscFilters() {
    updateParams({
      baseline_gsc_range: gscParams.baseline_gsc_range,
      target_gsc_range: gscParams.target_gsc_range,
      gsc_page: 1,
      gsc_page_size: 25,
      gsc_sort_by: 'delta_clicks',
      gsc_sort_order: 'desc',
      trend: undefined,
      clicks_trend: undefined,
      impressions_trend: undefined,
      ctr_trend: undefined,
      position_trend: undefined,
      top_queries_trend: undefined,
      gsc_url_contains: undefined,
    })
  }

  const crawlQuickFilters = [
    { label: t('trends.crawl.quickFilters.improved'), isActive: crawlParams?.change_type === 'improved', onClick: () => updateParams({ change_type: 'improved', crawl_page: 1 }) },
    { label: t('trends.crawl.quickFilters.worsened'), isActive: crawlParams?.change_type === 'worsened', onClick: () => updateParams({ change_type: 'worsened', crawl_page: 1 }) },
    { label: t('trends.crawl.quickFilters.new'), isActive: crawlParams?.change_type === 'new', onClick: () => updateParams({ change_type: 'new', crawl_page: 1 }) },
    { label: t('trends.crawl.quickFilters.missing'), isActive: crawlParams?.change_type === 'missing', onClick: () => updateParams({ change_type: 'missing', crawl_page: 1 }) },
    { label: t('trends.crawl.quickFilters.resolvedIssues'), isActive: (crawlParams?.resolved_issues_min ?? 0) >= 1, onClick: () => updateParams({ change_type: 'improved', resolved_issues_min: 1, crawl_page: 1 }) },
    { label: t('trends.crawl.quickFilters.newIssues'), isActive: (crawlParams?.added_issues_min ?? 0) >= 1, onClick: () => updateParams({ change_type: 'worsened', added_issues_min: 1, crawl_page: 1 }) },
    { label: t('trends.crawl.quickFilters.priorityGain'), isActive: crawlParams?.sort_by === 'delta_priority_score' && crawlParams?.sort_order === 'desc', onClick: () => updateParams({ crawl_sort_by: 'delta_priority_score', crawl_sort_order: 'desc', crawl_page: 1 }) },
    { label: t('trends.crawl.quickFilters.priorityDrop'), isActive: crawlParams?.sort_by === 'delta_priority_score' && crawlParams?.sort_order === 'asc', onClick: () => updateParams({ crawl_sort_by: 'delta_priority_score', crawl_sort_order: 'asc', crawl_page: 1 }) },
  ]

  const gscQuickFilters = [
    { label: t('trends.gsc.quickFilters.clicksUp'), isActive: gscParams.clicks_trend === 'improved', onClick: () => updateParams({ clicks_trend: 'improved', gsc_sort_by: 'delta_clicks', gsc_sort_order: 'desc', gsc_page: 1 }) },
    { label: t('trends.gsc.quickFilters.clicksDown'), isActive: gscParams.clicks_trend === 'worsened', onClick: () => updateParams({ clicks_trend: 'worsened', gsc_sort_by: 'delta_clicks', gsc_sort_order: 'asc', gsc_page: 1 }) },
    { label: t('trends.gsc.quickFilters.impressionsUp'), isActive: gscParams.impressions_trend === 'improved', onClick: () => updateParams({ impressions_trend: 'improved', gsc_sort_by: 'delta_impressions', gsc_sort_order: 'desc', gsc_page: 1 }) },
    { label: t('trends.gsc.quickFilters.ctrDown'), isActive: gscParams.ctr_trend === 'worsened', onClick: () => updateParams({ ctr_trend: 'worsened', gsc_sort_by: 'delta_ctr', gsc_sort_order: 'asc', gsc_page: 1 }) },
    { label: t('trends.gsc.quickFilters.positionImproved'), isActive: gscParams.position_trend === 'improved', onClick: () => updateParams({ position_trend: 'improved', gsc_sort_by: 'delta_position', gsc_sort_order: 'asc', gsc_page: 1 }) },
    { label: t('trends.gsc.quickFilters.positionWorsened'), isActive: gscParams.position_trend === 'worsened', onClick: () => updateParams({ position_trend: 'worsened', gsc_sort_by: 'delta_position', gsc_sort_order: 'desc', gsc_page: 1 }) },
  ]

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('trends.page.eyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">{t('trends.page.title', { jobId })}</h1>
            <p className="mt-2 text-sm text-stone-600">{t('trends.page.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <JobNavigation jobId={jobId} />
            <a
              href={buildCompareExportHref(jobId, 'crawl', searchParams)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('trends.page.exportCrawlCompare')}
            </a>
            <a
              href={buildCompareExportHref(jobId, 'gsc', searchParams)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('trends.page.exportGscCompare')}
            </a>
          </div>
        </div>
      </section>

      {overviewQuery.isLoading ? <LoadingState label={t('trends.page.loadingOverview')} /> : null}
      {overviewQuery.isError ? (
        <ErrorState title={t('trends.errors.overviewTitle')} message={getUiErrorMessage(overviewQuery.error, t)} />
      ) : null}

      {overviewQuery.data ? (
        <>
          <QuickFilterBar title={t('trends.crawl.quickFilters.title')} items={crawlQuickFilters} />

          <section className="space-y-4 rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-stone-950">{t('trends.crawl.title')}</h2>
                <p className="mt-1 text-sm text-stone-600">{t('trends.crawl.description')}</p>
              </div>
              <div className="text-sm text-stone-600">
                {t('trends.crawl.siteLabel')}: <span className="font-medium text-stone-900">{overviewQuery.data.site_domain}</span>
              </div>
            </div>

            {overviewQuery.data.baseline_candidates.length === 0 ? (
              <EmptyState title={t('trends.crawl.emptyBaselineTitle')} description={t('trends.crawl.emptyBaselineDescription')} />
            ) : (
              <>
                <FilterPanel title={t('trends.crawl.filters.title')} description={t('trends.crawl.filters.description')} onReset={resetCrawlFilters}>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('trends.crawl.filters.baselineJob')}</span>
                    <select
                      value={String(baselineJobId ?? '')}
                      onChange={(event) => updateParams({ baseline_job_id: event.target.value || undefined, crawl_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                    >
                      <option value="">{t('common.any')}</option>
                      {overviewQuery.data.baseline_candidates.map((candidate) => (
                        <option key={candidate.id} value={candidate.id}>
                          #{candidate.id} · {candidate.root_url ?? '-'}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('trends.crawl.filters.gscRange')}</span>
                    <select
                      value={crawlParams?.gsc_date_range ?? 'last_28_days'}
                      onChange={(event) => updateParams({ crawl_gsc_date_range: event.target.value, crawl_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                    >
                      <option value="last_28_days">{t('trends.crawl.filters.last28Days')}</option>
                      <option value="last_90_days">{t('trends.crawl.filters.last90Days')}</option>
                    </select>
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('trends.crawl.filters.changeType')}</span>
                    <select
                      value={crawlParams?.change_type ?? ''}
                      onChange={(event) => updateParams({ change_type: event.target.value || undefined, crawl_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                    >
                      <option value="">{t('common.any')}</option>
                      {CHANGE_TYPES.map((changeType) => (
                        <option key={changeType} value={changeType}>
                          {t(`trends.crawl.changeType.${changeType}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('trends.crawl.filters.resolvedIssuesMin')}</span>
                    <input
                      type="number"
                      value={searchParams.get('resolved_issues_min') ?? ''}
                      onChange={(event) => updateParams({ resolved_issues_min: event.target.value || undefined, crawl_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                    />
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('trends.crawl.filters.addedIssuesMin')}</span>
                    <input
                      type="number"
                      value={searchParams.get('added_issues_min') ?? ''}
                      onChange={(event) => updateParams({ added_issues_min: event.target.value || undefined, crawl_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                    />
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('trends.crawl.filters.urlContains')}</span>
                    <input
                      value={searchParams.get('crawl_url_contains') ?? ''}
                      onChange={(event) => updateParams({ crawl_url_contains: event.target.value || undefined, crawl_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                    />
                  </label>
                </FilterPanel>

                {crawlCompareQuery.isLoading ? <LoadingState label={t('trends.crawl.loading')} /> : null}
                {crawlCompareQuery.isError ? (
                  <ErrorState title={t('trends.errors.crawlTitle')} message={getUiErrorMessage(crawlCompareQuery.error, t)} />
                ) : null}

                {crawlCompareQuery.data ? (
                  <>
                    <SummaryCards
                      items={[
                        { label: t('trends.crawl.summary.shared'), value: crawlCompareQuery.data.summary.shared_urls },
                        { label: t('trends.crawl.summary.new'), value: crawlCompareQuery.data.summary.new_urls },
                        { label: t('trends.crawl.summary.missing'), value: crawlCompareQuery.data.summary.missing_urls },
                        { label: t('trends.crawl.summary.improved'), value: crawlCompareQuery.data.summary.improved_urls },
                        { label: t('trends.crawl.summary.worsened'), value: crawlCompareQuery.data.summary.worsened_urls },
                        { label: t('trends.crawl.summary.unchanged'), value: crawlCompareQuery.data.summary.unchanged_urls },
                        { label: t('trends.crawl.summary.resolvedIssues'), value: crawlCompareQuery.data.summary.resolved_issues_total },
                        { label: t('trends.crawl.summary.addedIssues'), value: crawlCompareQuery.data.summary.added_issues_total },
                      ]}
                    />

                    {crawlCompareQuery.data.items.length === 0 ? (
                      <EmptyState title={t('trends.crawl.emptyTitle')} description={t('trends.crawl.emptyDescription')} />
                    ) : (
                      <>
                        <DataTable
                          columns={[
                            {
                              key: 'url',
                              header: t('trends.crawl.table.url'),
                              sortKey: 'url',
                              cell: (row) => (
                                <div className="max-w-[20rem] space-y-1.5">
                                  <div className="flex flex-wrap gap-1.5">
                                    {renderToneBadge(t(`trends.crawl.changeType.${row.change_type}`), changeTone(row.change_type))}
                                    {row.target_primary_opportunity_type ? renderToneBadge(t(`opportunities.types.${row.target_primary_opportunity_type}.title`), 'teal') : null}
                                  </div>
                                  <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.url}>{row.url}</p>
                                  <UrlActions url={row.url} />
                                  <div className="flex flex-wrap gap-2 text-xs font-medium text-teal-700">
                                    <Link to={buildPagesLink(jobId, row.target_primary_opportunity_type)}>{t('trends.common.openPages')}</Link>
                                    <Link to={buildOpportunitiesLink(jobId, row.target_primary_opportunity_type)}>{t('trends.common.openOpportunities')}</Link>
                                    <Link to={buildGscLink(jobId, row.target_page_id ?? row.baseline_page_id)}>{t('trends.common.openGsc')}</Link>
                                  </div>
                                </div>
                              ),
                            },
                            {
                              key: 'change',
                              header: t('trends.crawl.table.change'),
                              sortKey: 'change_type',
                              cell: (row) => (
                                <div className="max-w-[18rem] space-y-1">
                                  <p className="text-sm font-medium text-stone-900">{t(`trends.crawl.changeType.${row.change_type}`)}</p>
                                  <p className="text-xs leading-5 text-stone-600 [overflow-wrap:anywhere]" title={row.change_rationale}>{row.change_rationale}</p>
                                </div>
                              ),
                            },
                            {
                              key: 'issues',
                              header: t('trends.crawl.table.issues'),
                              sortKey: 'issues_added_count',
                              cell: (row) => (
                                <div className="min-w-[12rem] space-y-1 text-xs text-stone-600">
                                  <p>{t('trends.crawl.table.resolved')}: {row.issues_resolved_count}</p>
                                  <p>{t('trends.crawl.table.added')}: {row.issues_added_count}</p>
                                  {row.resolved_issues.length > 0 ? <p>{row.resolved_issues.join(', ')}</p> : null}
                                  {row.added_issues.length > 0 ? <p>{row.added_issues.join(', ')}</p> : null}
                                </div>
                              ),
                            },
                            {
                              key: 'priority',
                              header: t('trends.crawl.table.priority'),
                              sortKey: 'delta_priority_score',
                              cell: (row) => (
                                <div className="min-w-[10rem] space-y-1 text-xs text-stone-600">
                                  <p>{row.baseline_priority_score ?? '-'}{' -> '}{row.target_priority_score ?? '-'}</p>
                                  <p>{t('trends.crawl.table.delta')}: {formatSignedInteger(row.delta_priority_score)}</p>
                                  <p>{row.baseline_priority_level ?? '-'}{' -> '}{row.target_priority_level ?? '-'}</p>
                                </div>
                              ),
                            },
                            {
                              key: 'content',
                              header: t('trends.crawl.table.content'),
                              sortKey: 'delta_word_count',
                              cell: (row) => (
                                <div className="min-w-[11rem] space-y-1 text-xs text-stone-600">
                                  <p>{t('trends.crawl.table.wordCount')}: {formatSignedInteger(row.delta_word_count)}</p>
                                  <p>{t('trends.crawl.table.schemaCount')}: {formatSignedInteger(row.delta_schema_count)}</p>
                                  <p>{t('trends.crawl.table.responseTime')}: {formatSignedInteger(row.delta_response_time_ms)}</p>
                                </div>
                              ),
                            },
                            {
                              key: 'internal',
                              header: t('trends.crawl.table.internalLinking'),
                              sortKey: 'delta_incoming_internal_links',
                              cell: (row) => (
                                <div className="min-w-[12rem] space-y-1 text-xs text-stone-600">
                                  <p>{t('trends.crawl.table.links')}: {formatSignedInteger(row.delta_incoming_internal_links)}</p>
                                  <p>{t('trends.crawl.table.linkingPages')}: {formatSignedInteger(row.delta_incoming_internal_linking_pages)}</p>
                                </div>
                              ),
                            },
                          ]}
                          rows={crawlCompareQuery.data.items}
                          rowKey={(row) => row.normalized_url}
                          sortBy={crawlParams?.sort_by}
                          sortOrder={crawlParams?.sort_order as SortOrder}
                          onSortChange={(sortBy, sortOrder) => updateParams({ crawl_sort_by: sortBy, crawl_sort_order: sortOrder, crawl_page: 1 })}
                        />
                        <PaginationControls
                          page={crawlCompareQuery.data.page}
                          pageSize={crawlCompareQuery.data.page_size}
                          totalItems={crawlCompareQuery.data.total_items}
                          totalPages={crawlCompareQuery.data.total_pages}
                          onPageChange={(page) => updateParams({ crawl_page: page })}
                          onPageSizeChange={(pageSize) => updateParams({ crawl_page_size: pageSize, crawl_page: 1 })}
                        />
                      </>
                    )}
                  </>
                ) : null}
              </>
            )}
          </section>

          <QuickFilterBar title={t('trends.gsc.quickFilters.title')} items={gscQuickFilters} />

          <section className="space-y-4 rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
            <div>
              <h2 className="text-lg font-semibold text-stone-950">{t('trends.gsc.title')}</h2>
              <p className="mt-1 text-sm text-stone-600">{t('trends.gsc.description')}</p>
            </div>

            <FilterPanel title={t('trends.gsc.filters.title')} description={t('trends.gsc.filters.description')} onReset={resetGscFilters}>
              <label className="grid gap-1 text-sm text-stone-700">
                <span>{t('trends.gsc.filters.baselineRange')}</span>
                <select
                  value={gscParams.baseline_gsc_range}
                  onChange={(event) => updateParams({ baseline_gsc_range: event.target.value, gsc_page: 1 })}
                  className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                >
                  <option value="last_90_days">{t('trends.gsc.filters.last90Days')}</option>
                  <option value="last_28_days">{t('trends.gsc.filters.last28Days')}</option>
                </select>
              </label>
              <label className="grid gap-1 text-sm text-stone-700">
                <span>{t('trends.gsc.filters.targetRange')}</span>
                <select
                  value={gscParams.target_gsc_range}
                  onChange={(event) => updateParams({ target_gsc_range: event.target.value, gsc_page: 1 })}
                  className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                >
                  <option value="last_28_days">{t('trends.gsc.filters.last28Days')}</option>
                  <option value="last_90_days">{t('trends.gsc.filters.last90Days')}</option>
                </select>
              </label>
              <label className="grid gap-1 text-sm text-stone-700">
                <span>{t('trends.gsc.filters.overallTrend')}</span>
                <select
                  value={gscParams.trend ?? ''}
                  onChange={(event) => updateParams({ trend: event.target.value || undefined, gsc_page: 1 })}
                  className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                >
                  <option value="">{t('common.any')}</option>
                  {METRIC_TRENDS.map((trend) => (
                    <option key={trend} value={trend}>
                      {t(`trends.gsc.trend.${trend}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-sm text-stone-700">
                <span>{t('trends.gsc.filters.urlContains')}</span>
                <input
                  value={searchParams.get('gsc_url_contains') ?? ''}
                  onChange={(event) => updateParams({ gsc_url_contains: event.target.value || undefined, gsc_page: 1 })}
                  className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                />
              </label>
              <label className="grid gap-1 text-sm text-stone-700">
                <span>{t('trends.gsc.filters.sortBy')}</span>
                <select
                  value={gscParams.sort_by}
                  onChange={(event) => updateParams({ gsc_sort_by: event.target.value, gsc_page: 1 })}
                  className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                >
                  <option value="delta_clicks">{t('trends.gsc.filters.sort.clicksDelta')}</option>
                  <option value="delta_impressions">{t('trends.gsc.filters.sort.impressionsDelta')}</option>
                  <option value="delta_ctr">{t('trends.gsc.filters.sort.ctrDelta')}</option>
                  <option value="delta_position">{t('trends.gsc.filters.sort.positionDelta')}</option>
                  <option value="delta_top_queries_count">{t('trends.gsc.filters.sort.topQueriesDelta')}</option>
                  <option value="overall_trend">{t('trends.gsc.filters.sort.overallTrend')}</option>
                  <option value="url">{t('trends.gsc.filters.sort.url')}</option>
                </select>
              </label>
              <label className="grid gap-1 text-sm text-stone-700">
                <span>{t('trends.gsc.filters.sortOrder')}</span>
                <select
                  value={gscParams.sort_order}
                  onChange={(event) => updateParams({ gsc_sort_order: event.target.value, gsc_page: 1 })}
                  className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                >
                  <option value="desc">{t('sort.descending')}</option>
                  <option value="asc">{t('sort.ascending')}</option>
                </select>
              </label>
            </FilterPanel>

            {gscCompareQuery.isLoading ? <LoadingState label={t('trends.gsc.loading')} /> : null}
            {gscCompareQuery.isError ? (
              <ErrorState title={t('trends.errors.gscTitle')} message={getUiErrorMessage(gscCompareQuery.error, t)} />
            ) : null}

            {gscCompareQuery.data ? (
              <>
                <SummaryCards
                  items={[
                    { label: t('trends.gsc.summary.clicksDelta'), value: formatSignedInteger(gscCompareQuery.data.summary.delta_clicks) },
                    { label: t('trends.gsc.summary.impressionsDelta'), value: formatSignedInteger(gscCompareQuery.data.summary.delta_impressions) },
                    { label: t('trends.gsc.summary.ctrDelta'), value: formatSignedPercentPoints(gscCompareQuery.data.summary.delta_ctr) },
                    { label: t('trends.gsc.summary.positionDelta'), value: formatSignedFloat(gscCompareQuery.data.summary.delta_position) },
                    { label: t('trends.gsc.summary.topQueriesDelta'), value: formatSignedInteger(gscCompareQuery.data.summary.delta_top_queries_count) },
                    { label: t('trends.gsc.summary.improved'), value: gscCompareQuery.data.summary.improved_urls },
                    { label: t('trends.gsc.summary.worsened'), value: gscCompareQuery.data.summary.worsened_urls },
                    { label: t('trends.gsc.summary.flat'), value: gscCompareQuery.data.summary.flat_urls },
                  ]}
                />

                {gscCompareQuery.data.items.length === 0 ? (
                  <EmptyState title={t('trends.gsc.emptyTitle')} description={t('trends.gsc.emptyDescription')} />
                ) : (
                  <>
                    <DataTable
                      columns={[
                        {
                          key: 'url',
                          header: t('trends.gsc.table.url'),
                          sortKey: 'url',
                          cell: (row) => (
                            <div className="max-w-[20rem] space-y-1.5">
                              <div className="flex flex-wrap gap-1.5">
                                {renderToneBadge(t(`trends.gsc.trend.${row.overall_trend}`), trendTone(row.overall_trend))}
                                {renderToneBadge(String(row.priority_score), 'stone')}
                              </div>
                              <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.url}>{row.url}</p>
                              <UrlActions url={row.url} />
                              <div className="flex flex-wrap gap-2 text-xs font-medium text-teal-700">
                                <Link to={buildPagesLink(jobId, row.primary_opportunity_type)}>{t('trends.common.openPages')}</Link>
                                <Link to={buildOpportunitiesLink(jobId, row.primary_opportunity_type)}>{t('trends.common.openOpportunities')}</Link>
                                <Link to={buildGscLink(jobId, row.page_id)}>{t('trends.common.openTopQueries')}</Link>
                              </div>
                            </div>
                          ),
                        },
                        {
                          key: 'trend',
                          header: t('trends.gsc.table.trend'),
                          sortKey: 'overall_trend',
                          cell: (row) => (
                            <div className="max-w-[18rem] space-y-1">
                              <p className="text-sm font-medium text-stone-900">{t(`trends.gsc.trend.${row.overall_trend}`)}</p>
                              <p className="text-xs leading-5 text-stone-600 [overflow-wrap:anywhere]" title={row.rationale}>{row.rationale}</p>
                            </div>
                          ),
                        },
                        {
                          key: 'clicks',
                          header: t('trends.gsc.table.clicks'),
                          sortKey: 'delta_clicks',
                          cell: (row) => (
                            <div className="min-w-[8rem] space-y-1 text-xs text-stone-600">
                              <p>{row.baseline_clicks}{' -> '}{row.target_clicks}</p>
                              <p>{formatSignedInteger(row.delta_clicks)}</p>
                            </div>
                          ),
                        },
                        {
                          key: 'impressions',
                          header: t('trends.gsc.table.impressions'),
                          sortKey: 'delta_impressions',
                          cell: (row) => (
                            <div className="min-w-[8rem] space-y-1 text-xs text-stone-600">
                              <p>{row.baseline_impressions}{' -> '}{row.target_impressions}</p>
                              <p>{formatSignedInteger(row.delta_impressions)}</p>
                            </div>
                          ),
                        },
                        {
                          key: 'ctr',
                          header: t('trends.gsc.table.ctr'),
                          sortKey: 'delta_ctr',
                          cell: (row) => (
                            <div className="min-w-[8rem] space-y-1 text-xs text-stone-600">
                              <p>{formatPercent(row.baseline_ctr)}{' -> '}{formatPercent(row.target_ctr)}</p>
                              <p>{formatSignedPercentPoints(row.delta_ctr)}</p>
                            </div>
                          ),
                        },
                        {
                          key: 'position',
                          header: t('trends.gsc.table.position'),
                          sortKey: 'delta_position',
                          cell: (row) => (
                            <div className="min-w-[8rem] space-y-1 text-xs text-stone-600">
                              <p>{formatPosition(row.baseline_position)}{' -> '}{formatPosition(row.target_position)}</p>
                              <p>{formatSignedFloat(row.delta_position)}</p>
                            </div>
                          ),
                        },
                      ]}
                      rows={gscCompareQuery.data.items}
                      rowKey={(row) => `${row.page_id}-${row.url}`}
                      sortBy={gscParams.sort_by}
                      sortOrder={gscParams.sort_order as SortOrder}
                      onSortChange={(sortBy, sortOrder) => updateParams({ gsc_sort_by: sortBy, gsc_sort_order: sortOrder, gsc_page: 1 })}
                    />
                    <PaginationControls
                      page={gscCompareQuery.data.page}
                      pageSize={gscCompareQuery.data.page_size}
                      totalItems={gscCompareQuery.data.total_items}
                      totalPages={gscCompareQuery.data.total_pages}
                      onPageChange={(page) => updateParams({ gsc_page: page })}
                      onPageSizeChange={(pageSize) => updateParams({ gsc_page_size: pageSize, gsc_page: 1 })}
                    />
                  </>
                )}
              </>
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  )
}
