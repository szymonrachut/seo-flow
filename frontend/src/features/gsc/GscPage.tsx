import { startTransition, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

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
import type { GscDateRangeLabel, PageRecord, PagesQueryParams, SortOrder } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime, formatNullable, formatPercent, formatPosition } from '../../utils/format'
import { mergeSearchParams, parseFloatParam, parseIntegerParam } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
import { usePagesQuery } from '../pages/api'
import { buildSiteGscPath } from '../sites/routes'
import {
  useGscPropertiesQuery,
  useGscSummaryQuery,
  useImportGscDataMutation,
  useSelectGscPropertyMutation,
  useGscTopQueriesQuery,
} from './api'

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

function readOpportunitiesParams(searchParams: URLSearchParams): PagesQueryParams {
  const sortBy = searchParams.get('sort_by')
  const sortOrder = searchParams.get('sort_order')
  const gscDateRange = searchParams.get('gsc_date_range')

  return {
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), 25),
    sort_by: (sortBy ?? 'gsc_impressions') as PagesQueryParams['sort_by'],
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    gsc_date_range: gscDateRange === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    has_technical_issue:
      searchParams.get('has_technical_issue') === null
        ? undefined
        : searchParams.get('has_technical_issue') === 'true',
    has_gsc_data:
      searchParams.get('has_gsc_data') === null
        ? undefined
        : searchParams.get('has_gsc_data') === 'true',
    gsc_clicks_min: parseIntegerParam(searchParams.get('gsc_clicks_min'), undefined),
    gsc_clicks_max: parseIntegerParam(searchParams.get('gsc_clicks_max'), undefined),
    gsc_impressions_min: parseIntegerParam(searchParams.get('gsc_impressions_min'), undefined),
    gsc_impressions_max: parseIntegerParam(searchParams.get('gsc_impressions_max'), undefined),
    gsc_ctr_min: parseFloatParam(searchParams.get('gsc_ctr_min'), undefined),
    gsc_ctr_max: parseFloatParam(searchParams.get('gsc_ctr_max'), undefined),
    gsc_position_min: parseFloatParam(searchParams.get('gsc_position_min'), undefined),
    gsc_position_max: parseFloatParam(searchParams.get('gsc_position_max'), undefined),
    gsc_top_queries_min: parseIntegerParam(searchParams.get('gsc_top_queries_min'), undefined),
  }
}

function readTopQueriesParams(searchParams: URLSearchParams) {
  return {
    page_id: parseIntegerParam(searchParams.get('page_id'), undefined),
    date_range_label: (searchParams.get('gsc_date_range') === 'last_90_days'
      ? 'last_90_days'
      : 'last_28_days') as GscDateRangeLabel,
    page: parseIntegerParam(searchParams.get('queries_page'), 1),
    page_size: parseIntegerParam(searchParams.get('queries_page_size'), 10),
    sort_by: (searchParams.get('queries_sort_by') ?? 'clicks') as 'query' | 'clicks' | 'impressions' | 'ctr' | 'position' | 'url',
    sort_order: (searchParams.get('queries_sort_order') === 'asc' ? 'asc' : 'desc') as 'asc' | 'desc',
    query_contains: searchParams.get('query_contains') || undefined,
    query_excludes: searchParams.get('query_excludes') || undefined,
    clicks_min: parseIntegerParam(searchParams.get('query_clicks_min'), undefined),
    impressions_min: parseIntegerParam(searchParams.get('query_impressions_min'), undefined),
    ctr_max: parseFloatParam(searchParams.get('query_ctr_max'), undefined),
    position_min: parseFloatParam(searchParams.get('query_position_min'), undefined),
  }
}

function metricValue(
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
  range: GscDateRangeLabel,
) {
  const suffix = range === 'last_90_days' ? '90d' : '28d'
  return page[`${metric}_${suffix}` as keyof typeof page]
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

function buildOpportunitySignals(page: PageRecord, t: (key: string) => string) {
  const signals: Array<{ label: string; tone: 'stone' | 'rose' | 'amber' | 'teal' }> = []

  if (page.title_missing) {
    signals.push({ label: t('pages.signals.missingTitle'), tone: 'rose' })
  }
  if (page.meta_description_missing) {
    signals.push({ label: t('pages.signals.missingMeta'), tone: 'rose' })
  }
  if (page.h1_missing) {
    signals.push({ label: t('pages.signals.missingH1'), tone: 'rose' })
  }
  if (page.thin_content) {
    signals.push({ label: t('pages.signals.thinContent'), tone: 'amber' })
  }
  if (page.canonical_missing) {
    signals.push({ label: t('pages.signals.missingCanonical'), tone: 'amber' })
  }
  if (page.noindex_like) {
    signals.push({ label: t('pages.signals.nonIndexable'), tone: 'teal' })
  }
  if (page.missing_alt_images) {
    signals.push({ label: t('pages.signals.missingAlt'), tone: 'amber' })
  }
  if (page.oversized) {
    signals.push({ label: t('pages.signals.oversized'), tone: 'rose' })
  }

  return signals
}

function buildPagesExportHref(jobId: number, searchParams: URLSearchParams) {
  const query = searchParams.toString()
  return buildApiUrl(`/crawl-jobs/${jobId}/export/pages.csv${query ? `?${query}` : ''}`)
}

function buildTopQueriesExportHref(jobId: number, searchParams: URLSearchParams) {
  const params = new URLSearchParams()
  const pageId = searchParams.get('page_id')
  if (pageId) {
    params.set('page_id', pageId)
  }
  params.set('date_range_label', searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days')

  for (const [from, to] of [
    ['query_contains', 'query_contains'],
    ['query_excludes', 'query_excludes'],
    ['query_clicks_min', 'clicks_min'],
    ['query_impressions_min', 'impressions_min'],
    ['query_ctr_max', 'ctr_max'],
    ['query_position_min', 'position_min'],
    ['queries_sort_by', 'sort_by'],
    ['queries_sort_order', 'sort_order'],
  ]) {
    const value = searchParams.get(from)
    if (value) {
      params.set(to, value)
    }
  }

  const query = params.toString()
  return buildApiUrl(`/crawl-jobs/${jobId}/export/gsc-top-queries.csv${query ? `?${query}` : ''}`)
}

function buildGscOauthStartHref(jobId: number) {
  const params = new URLSearchParams()
  const frontendRedirectUrl = `${globalThis.location.origin}/jobs/${jobId}/gsc`
  params.set('frontend_redirect_url', frontendRedirectUrl)
  return buildApiUrl(`/crawl-jobs/${jobId}/gsc/oauth/start?${params.toString()}`)
}

function formatRangeLabel(range: GscDateRangeLabel) {
  return range === 'last_90_days' ? '90d' : '28d'
}

export function GscPage() {
  const { t } = useTranslation()
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? t('documentTitle.gsc', { jobId }) : t('nav.gsc'))

  if (jobId === null) {
    return <ErrorState title={t('gsc.invalidIdTitle')} message={t('gsc.invalidIdMessage')} />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const opportunitiesParams = useMemo(() => readOpportunitiesParams(searchParams), [searchParams])
  const topQueriesParams = useMemo(() => readTopQueriesParams(searchParams), [searchParams])
  const gscSummaryQuery = useGscSummaryQuery(jobId)
  const gscPropertiesQuery = useGscPropertiesQuery(jobId, gscSummaryQuery.data?.auth_connected === true)
  const pagesQuery = usePagesQuery(jobId, opportunitiesParams)
  const topQueriesQuery = useGscTopQueriesQuery(jobId, topQueriesParams, topQueriesParams.page_id !== undefined)
  const selectPropertyMutation = useSelectGscPropertyMutation(jobId)
  const importGscMutation = useImportGscDataMutation(jobId)
  const [selectedPropertyUri, setSelectedPropertyUri] = useState('')
  const [topQueriesLimitInput, setTopQueriesLimitInput] = useState('')
  const topQueriesLimitInputId = 'gsc-top-queries-limit'

  useEffect(() => {
    if (!gscPropertiesQuery.data || gscPropertiesQuery.data.length === 0) {
      return
    }

    const selected = gscPropertiesQuery.data.find((item) => item.is_selected) ?? gscPropertiesQuery.data[0]
    setSelectedPropertyUri(selected.property_uri)
  }, [gscPropertiesQuery.data])

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
    updateParams({
      page: 1,
      ...updates,
    })
  }

  function resetOpportunityFilters() {
    updateParams({
      page: 1,
      has_technical_issue: undefined,
      has_gsc_data: undefined,
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

  function resetTopQueryFilters() {
    updateParams({
      queries_page: 1,
      query_contains: undefined,
      query_excludes: undefined,
      query_clicks_min: undefined,
      query_impressions_min: undefined,
      query_ctr_max: undefined,
      query_position_min: undefined,
    })
  }

  function handlePageSort(sortBy: string, nextSortOrder: SortOrder) {
    updateParams({
      sort_by: sortBy,
      sort_order: nextSortOrder,
      page: 1,
    })
  }

  function handleQuerySort(sortBy: string, nextSortOrder: SortOrder) {
    updateParams({
      queries_sort_by: sortBy,
      queries_sort_order: nextSortOrder,
      queries_page: 1,
    })
  }

  function closeTopQueries() {
    updateParams({
      page_id: undefined,
      queries_page: 1,
    })
  }

  const currentRange = opportunitiesParams.gsc_date_range
  const activeRangeSummary = gscSummaryQuery.data?.ranges.find((item) => item.date_range_label === currentRange)
  const selectedPage = pagesQuery.data?.items.find((item) => item.id === topQueriesParams.page_id) ?? null
  const quickFilters = [
    {
      label: t('gsc.quickFilters.impressionsWithIssue'),
      isActive: opportunitiesParams.has_technical_issue === true && (opportunitiesParams.gsc_impressions_min ?? 0) >= 1,
      onClick: () => applyPreset({ has_technical_issue: 'true', gsc_impressions_min: 1 }),
    },
    {
      label: t('gsc.quickFilters.clicksWithIssue'),
      isActive: opportunitiesParams.has_technical_issue === true && (opportunitiesParams.gsc_clicks_min ?? 0) >= 1,
      onClick: () => applyPreset({ has_technical_issue: 'true', gsc_clicks_min: 1 }),
    },
    {
      label: t('gsc.quickFilters.lowCtrHighImpressions'),
      isActive: (opportunitiesParams.gsc_impressions_min ?? 0) >= 100 && (opportunitiesParams.gsc_ctr_max ?? 1) <= 0.02,
      onClick: () => applyPreset({ gsc_impressions_min: 100, gsc_ctr_max: 0.02 }),
    },
    {
      label: t('gsc.quickFilters.highImpressionsWeakPosition'),
      isActive: (opportunitiesParams.gsc_impressions_min ?? 0) >= 100 && (opportunitiesParams.gsc_position_min ?? 0) >= 8,
      onClick: () => applyPreset({ gsc_impressions_min: 100, gsc_position_min: 8 }),
    },
  ]

  async function handleSelectProperty() {
    if (!selectedPropertyUri) {
      return
    }
    await selectPropertyMutation.mutateAsync(selectedPropertyUri)
  }

  function resolveTopQueriesLimit(): number | undefined {
    const raw = topQueriesLimitInput.trim()
    if (!raw) {
      return undefined
    }

    const parsed = Number(raw)
    if (!Number.isInteger(parsed) || parsed < 1) {
      return undefined
    }

    return parsed
  }

  async function handleImportAll() {
    await importGscMutation.mutateAsync({
      date_ranges: ['last_28_days', 'last_90_days'],
      top_queries_limit: resolveTopQueriesLimit(),
    })
  }

  async function handleImportCurrentRange() {
    await importGscMutation.mutateAsync({
      date_ranges: [currentRange],
      top_queries_limit: resolveTopQueriesLimit(),
    })
  }

  const topQueriesContext = topQueriesQuery.data?.page_context ?? selectedPage
  const topQueriesTitle = topQueriesContext?.title ?? selectedPage?.title ?? '-'

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('gsc.page.eyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">{t('gsc.page.title', { jobId })}</h1>
            <p className="mt-2 text-sm text-stone-600">{t('gsc.page.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <JobNavigation jobId={jobId} />
            <a
              href={buildPagesExportHref(jobId, searchParams)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('gsc.page.exportPages')}
            </a>
            <a
              href={buildTopQueriesExportHref(jobId, searchParams)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('gsc.page.exportQueries')}
            </a>
          </div>
        </div>
      </section>

      {gscSummaryQuery.isLoading ? <LoadingState label={t('gsc.page.loading')} /> : null}
      {gscSummaryQuery.isError ? (
        <ErrorState title={t('gsc.errors.summaryTitle')} message={getUiErrorMessage(gscSummaryQuery.error, t)} />
      ) : null}

      {gscSummaryQuery.data ? (
        <>
          <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div className="space-y-2">
                <h2 className="text-lg font-semibold text-stone-950">{t('gsc.connection.title')}</h2>
                <p className="text-sm text-stone-600">{t('gsc.connection.description')}</p>
                <p className="text-sm text-stone-700">
                  {t('gsc.connection.selectedProperty')}:{' '}
                  <span className="font-medium text-stone-950">{gscSummaryQuery.data.selected_property_uri ?? '-'}</span>
                </p>
                <p className="text-sm text-stone-700">
                  {t('gsc.connection.siteWorkspaceHint')}{' '}
                  <Link
                    to={buildSiteGscPath(gscSummaryQuery.data.site_id, { activeCrawlId: jobId })}
                    className="font-medium text-teal-700 underline-offset-2 hover:underline"
                  >
                    {t('gsc.connection.openSiteWorkspace')}
                  </Link>
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {!gscSummaryQuery.data.auth_connected ? (
                  <a
                    href={buildGscOauthStartHref(jobId)}
                    className="inline-flex rounded-full bg-teal-700 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-teal-600"
                  >
                    {t('gsc.connection.connect')}
                  </a>
                ) : (
                  <>
                    <div className="grid gap-1 text-xs text-stone-600 dark:text-slate-300">
                      <div className="inline-flex items-center gap-2">
                        <label htmlFor={topQueriesLimitInputId}>{t('gsc.connection.topQueriesLimit')}</label>
                        <button
                          type="button"
                          title={t('gsc.connection.topQueriesLimitTooltip')}
                          aria-label={t('gsc.connection.topQueriesLimitTooltip')}
                          className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-stone-300 bg-white text-[11px] font-semibold text-stone-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                        >
                          ?
                        </button>
                      </div>
                      <input
                        id={topQueriesLimitInputId}
                        type="number"
                        min={1}
                        step={1}
                        value={topQueriesLimitInput}
                        onChange={(event) => setTopQueriesLimitInput(event.target.value)}
                        placeholder="20"
                        className="w-36 rounded-full border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                      />
                    </div>
                    <select
                      value={selectedPropertyUri}
                      onChange={(event) => setSelectedPropertyUri(event.target.value)}
                      className="min-w-[18rem] rounded-full border border-stone-300 bg-white px-4 py-1.5 text-sm text-stone-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                    >
                      {(gscPropertiesQuery.data ?? []).map((property) => (
                        <option key={property.property_uri} value={property.property_uri}>
                          {property.matches_site ? `${property.property_uri} *` : property.property_uri}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => void handleSelectProperty()}
                      disabled={!selectedPropertyUri || selectPropertyMutation.isPending}
                      className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {selectPropertyMutation.isPending ? t('gsc.connection.saving') : t('gsc.connection.saveProperty')}
                    </button>
                  </>
                )}
                <button
                  type="button"
                  onClick={() => void handleImportCurrentRange()}
                  disabled={!gscSummaryQuery.data.selected_property_uri || importGscMutation.isPending}
                  className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {importGscMutation.isPending ? t('gsc.connection.importing') : t('gsc.connection.importCurrentRange')}
                </button>
                <button
                  type="button"
                  onClick={() => void handleImportAll()}
                  disabled={!gscSummaryQuery.data.selected_property_uri || importGscMutation.isPending}
                  className="inline-flex rounded-full bg-teal-700 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-teal-600 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-teal-400 dark:text-slate-950 dark:hover:bg-teal-300"
                >
                  {importGscMutation.isPending ? t('gsc.connection.importing') : t('gsc.connection.importAll')}
                </button>
              </div>
            </div>
            <p className="mt-3 text-xs text-stone-600 dark:text-slate-300">{t('gsc.connection.topQueriesLimitHint')}</p>
            {searchParams.get('oauth') === 'success' ? (
              <p className="mt-4 text-sm text-teal-700">{t('gsc.connection.oauthSuccess')}</p>
            ) : null}
            {selectPropertyMutation.isError ? (
              <div className="mt-4">
                <ErrorState title={t('gsc.errors.propertyTitle')} message={getUiErrorMessage(selectPropertyMutation.error, t)} />
              </div>
            ) : null}
            {importGscMutation.isError ? (
              <div className="mt-4">
                <ErrorState title={t('gsc.errors.importTitle')} message={getUiErrorMessage(importGscMutation.error, t)} />
              </div>
            ) : null}
            {importGscMutation.data ? (
              <div className="mt-4 space-y-3 rounded-2xl border border-teal-200 bg-teal-50/80 px-4 py-3 text-sm text-teal-900 dark:border-teal-900/70 dark:bg-teal-950/30 dark:text-teal-100">
                <p className="font-medium">{t('gsc.connection.lastImport', { date: formatDateTime(importGscMutation.data.imported_at) })}</p>
                <p className="mt-1">{importGscMutation.data.property_uri}</p>
                <div className="grid gap-2 md:grid-cols-2">
                  {importGscMutation.data.ranges.map((range) => (
                    <div
                      key={range.date_range_label}
                      className="rounded-2xl border border-teal-200/80 bg-white/70 px-3 py-3 text-xs text-teal-950 dark:border-teal-900/70 dark:bg-slate-950/30 dark:text-teal-100"
                    >
                      <p className="font-semibold uppercase tracking-[0.18em] text-teal-700 dark:text-teal-300">
                        {t('gsc.connection.rangeSummary', { range: formatRangeLabel(range.date_range_label) })}
                      </p>
                      <p className="mt-2">{t('gsc.connection.pagesWithTopQueries', { count: range.pages_with_top_queries })}</p>
                      <p>{t('gsc.connection.storedTopQueries', { count: range.imported_top_queries })}</p>
                      <p>{t('gsc.connection.failedPages', { count: range.failed_pages })}</p>
                      {range.errors.length > 0 ? (
                        <p className="mt-2 text-rose-700 dark:text-rose-300">
                          {t('gsc.connection.importErrors', { count: range.errors.length })}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
                <p className="text-xs text-teal-900/90 dark:text-teal-100/90">{t('gsc.connection.matchingNote')}</p>
              </div>
            ) : null}
          </section>

          <SummaryCards
            items={[
              {
                label: t('gsc.summary.importedPages'),
                value: activeRangeSummary?.imported_pages ?? '-',
                hint: t('gsc.summary.activeRange', { range: currentRange === 'last_90_days' ? '90d' : '28d' }),
              },
              { label: t('gsc.summary.pagesWithImpressions'), value: activeRangeSummary?.pages_with_impressions ?? '-' },
              { label: t('gsc.summary.pagesWithClicks'), value: activeRangeSummary?.pages_with_clicks ?? '-' },
              { label: t('gsc.summary.totalTopQueries'), value: activeRangeSummary?.total_top_queries ?? '-' },
              {
                label: t('gsc.summary.opportunitiesImpressions'),
                value: activeRangeSummary?.opportunities_with_impressions ?? '-',
              },
              { label: t('gsc.summary.opportunitiesClicks'), value: activeRangeSummary?.opportunities_with_clicks ?? '-' },
              { label: t('gsc.summary.pagesWithTopQueries'), value: activeRangeSummary?.pages_with_top_queries ?? '-' },
              { label: t('gsc.summary.lastImportedAt'), value: formatDateTime(activeRangeSummary?.last_imported_at ?? null) },
            ]}
          />

          <QuickFilterBar title={t('gsc.quickFilters.title')} items={quickFilters} />

          <FilterPanel title={t('gsc.filters.title')} description={t('gsc.filters.description')} onReset={resetOpportunityFilters}>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('gsc.filters.dateRange')}</span>
              <select
                value={currentRange}
                onChange={(event) => updateParams({ gsc_date_range: event.target.value, page: 1, queries_page: 1 })}
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
              >
                <option value="last_28_days">{t('gsc.filters.last28Days')}</option>
                <option value="last_90_days">{t('gsc.filters.last90Days')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('gsc.filters.hasTechnicalIssue')}</span>
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
              <span>{t('gsc.filters.hasGscData')}</span>
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
              <span>{t('gsc.filters.minImpressions')}</span>
              <input
                type="number"
                value={searchParams.get('gsc_impressions_min') ?? ''}
                onChange={(event) => updateFilter('gsc_impressions_min', event.target.value)}
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                placeholder="100"
              />
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('gsc.filters.minClicks')}</span>
              <input
                type="number"
                value={searchParams.get('gsc_clicks_min') ?? ''}
                onChange={(event) => updateFilter('gsc_clicks_min', event.target.value)}
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                placeholder="1"
              />
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('gsc.filters.maxCtr')}</span>
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
              <span>{t('gsc.filters.minPosition')}</span>
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
              <span>{t('gsc.filters.minTopQueries')}</span>
              <input
                type="number"
                value={searchParams.get('gsc_top_queries_min') ?? ''}
                onChange={(event) => updateFilter('gsc_top_queries_min', event.target.value)}
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                placeholder="1"
              />
            </label>
          </FilterPanel>

          {pagesQuery.isLoading ? <LoadingState label={t('gsc.page.loadingOpportunities')} /> : null}
          {pagesQuery.isError ? (
            <ErrorState title={t('gsc.errors.opportunitiesTitle')} message={getUiErrorMessage(pagesQuery.error, t)} />
          ) : null}
          {pagesQuery.isSuccess && pagesQuery.data.items.length === 0 ? (
            <EmptyState title={t('gsc.empty.opportunitiesTitle')} description={t('gsc.empty.opportunitiesDescription')} />
          ) : null}
          {pagesQuery.isSuccess && pagesQuery.data.items.length > 0 ? (
            <>
              <DataTable
                columns={[
                  {
                    key: 'url',
                    header: t('gsc.table.url'),
                    sortKey: 'url',
                    minWidth: 380,
                    cell: (page) => (
                      <div className="space-y-1.5">
                        <button
                          type="button"
                          onClick={() => updateParams({ page_id: page.id, queries_page: 1 })}
                          className="text-left font-medium text-stone-900 hover:text-teal-700"
                          title={page.url}
                        >
                          {page.url}
                        </button>
                        <p className="text-xs text-stone-500">
                          {t('gsc.table.topQueriesCount')}: {formatNullable(metricValue(page, 'top_queries_count', currentRange) as number | null)}
                        </p>
                        <UrlActions url={page.url} />
                      </div>
                    ),
                  },
                  {
                    key: 'technical',
                    header: t('gsc.table.technical'),
                    minWidth: 220,
                    cell: (page) => (
                      <div className="space-y-1.5">
                        <div className="flex flex-wrap gap-1.5">
                          {buildOpportunitySignals(page, t).map((signal) => renderBadge(signal.label, signal.tone))}
                        </div>
                        <p className="text-xs text-stone-500">{t('gsc.table.technicalCount', { count: page.technical_issue_count })}</p>
                      </div>
                    ),
                  },
                  {
                    key: 'clicks',
                    header: t('gsc.table.clicks'),
                    sortKey: 'gsc_clicks',
                    minWidth: 100,
                    cell: (page) => formatNullable(metricValue(page, 'clicks', currentRange) as number | null),
                  },
                  {
                    key: 'impressions',
                    header: t('gsc.table.impressions'),
                    sortKey: 'gsc_impressions',
                    minWidth: 110,
                    cell: (page) => formatNullable(metricValue(page, 'impressions', currentRange) as number | null),
                  },
                  {
                    key: 'ctr',
                    header: t('gsc.table.ctr'),
                    sortKey: 'gsc_ctr',
                    minWidth: 90,
                    cell: (page) => formatPercent(metricValue(page, 'ctr', currentRange) as number | null),
                  },
                  {
                    key: 'position',
                    header: t('gsc.table.position'),
                    sortKey: 'gsc_position',
                    minWidth: 90,
                    cell: (page) => formatPosition(metricValue(page, 'position', currentRange) as number | null),
                  },
                ]}
                rows={pagesQuery.data.items}
                rowKey={(page) => page.id}
                sortBy={opportunitiesParams.sort_by}
                sortOrder={opportunitiesParams.sort_order}
                onSortChange={handlePageSort}
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

          <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-stone-950">{t('gsc.topQueries.title')}</h2>
                <p className="mt-1 text-sm text-stone-600">{t('gsc.topQueries.description')}</p>
              </div>
              {topQueriesParams.page_id !== undefined ? (
                <Link
                  to={`/jobs/${jobId}/pages?gsc_date_range=${currentRange}&page=1`}
                  className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                >
                  {t('gsc.topQueries.openPages')}
                </Link>
              ) : null}
            </div>

            {topQueriesParams.page_id === undefined ? (
              <div className="mt-4">
                <EmptyState title={t('gsc.empty.topQueriesTitle')} description={t('gsc.empty.topQueriesDescription')} />
              </div>
            ) : null}
          </section>

          {topQueriesParams.page_id !== undefined ? (
            <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-stone-950/55 px-4 py-6 sm:px-6 sm:py-10">
              <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="gsc-top-queries-modal-title"
                className="w-full max-w-6xl rounded-[32px] border border-stone-300 bg-white p-5 shadow-2xl sm:p-6"
              >
                <div className="flex items-start justify-between gap-4 border-b border-stone-200 pb-4">
                  <div className="min-w-0 space-y-2">
                    <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('gsc.topQueries.title')}</p>
                    <h2
                      id="gsc-top-queries-modal-title"
                      className="text-lg font-semibold text-stone-950 whitespace-normal break-words"
                    >
                      {topQueriesTitle}
                    </h2>
                    <p className="text-sm text-stone-600 whitespace-normal break-words">{topQueriesContext?.url ?? '-'}</p>
                  </div>
                  <button
                    type="button"
                    onClick={closeTopQueries}
                    className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-stone-300 text-xl leading-none text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                    aria-label={t('gsc.topQueries.close')}
                  >
                    ×
                  </button>
                </div>

                <div className="mt-5 flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                  <div>
                    <p className="text-sm text-stone-600">{t('gsc.topQueries.filtersDescription')}</p>
                  </div>
                  <Link
                    to={`/jobs/${jobId}/pages?gsc_date_range=${currentRange}&page=1`}
                    className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                  >
                    {t('gsc.topQueries.openPages')}
                  </Link>
                </div>

                <FilterPanel
                  title={t('gsc.topQueries.filtersTitle')}
                  description={t('gsc.topQueries.filtersDescription')}
                  onReset={resetTopQueryFilters}
                >
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('gsc.topQueries.queryContains')}</span>
                    <input
                      value={searchParams.get('query_contains') ?? ''}
                      onChange={(event) => updateParams({ query_contains: event.target.value, queries_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                      placeholder={t('gsc.topQueries.queryPlaceholder')}
                    />
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('gsc.topQueries.queryExcludes')}</span>
                    <input
                      value={searchParams.get('query_excludes') ?? ''}
                      onChange={(event) => updateParams({ query_excludes: event.target.value, queries_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                      placeholder={t('gsc.topQueries.queryPlaceholder')}
                    />
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('gsc.topQueries.minImpressions')}</span>
                    <input
                      type="number"
                      value={searchParams.get('query_impressions_min') ?? ''}
                      onChange={(event) => updateParams({ query_impressions_min: event.target.value, queries_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                      placeholder="10"
                    />
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('gsc.topQueries.minClicks')}</span>
                    <input
                      type="number"
                      value={searchParams.get('query_clicks_min') ?? ''}
                      onChange={(event) => updateParams({ query_clicks_min: event.target.value, queries_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                      placeholder="1"
                    />
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('gsc.topQueries.maxCtr')}</span>
                    <input
                      type="number"
                      step="0.01"
                      value={searchParams.get('query_ctr_max') ? String(Number(searchParams.get('query_ctr_max')) * 100) : ''}
                      onChange={(event) =>
                        updateParams({
                          query_ctr_max: event.target.value ? String(Number(event.target.value) / 100) : undefined,
                          queries_page: 1,
                        })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                      placeholder="3"
                    />
                  </label>
                  <label className="grid gap-1 text-sm text-stone-700">
                    <span>{t('gsc.topQueries.minPosition')}</span>
                    <input
                      type="number"
                      step="0.1"
                      value={searchParams.get('query_position_min') ?? ''}
                      onChange={(event) => updateParams({ query_position_min: event.target.value, queries_page: 1 })}
                      className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                      placeholder="8"
                    />
                  </label>
                </FilterPanel>

                {topQueriesQuery.isLoading ? <LoadingState label={t('gsc.topQueries.loading')} /> : null}
                {topQueriesQuery.isError ? (
                  <ErrorState title={t('gsc.errors.topQueriesTitle')} message={getUiErrorMessage(topQueriesQuery.error, t)} />
                ) : null}
                {topQueriesQuery.isSuccess ? (
                  <div className="mt-4 space-y-4">
                    <div className="rounded-2xl border border-stone-200 bg-stone-50/90 px-4 py-3">
                      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
                        <p className="text-xs text-stone-600">{t('gsc.topQueries.summaryClicks')}: {formatNullable(topQueriesContext ? metricValue(topQueriesContext, 'clicks', currentRange) as number | null : null)}</p>
                        <p className="text-xs text-stone-600">{t('gsc.topQueries.summaryImpressions')}: {formatNullable(topQueriesContext ? metricValue(topQueriesContext, 'impressions', currentRange) as number | null : null)}</p>
                        <p className="text-xs text-stone-600">{t('gsc.topQueries.summaryCtr')}: {formatPercent(topQueriesContext ? metricValue(topQueriesContext, 'ctr', currentRange) as number | null : null)}</p>
                        <p className="text-xs text-stone-600">{t('gsc.topQueries.summaryPosition')}: {formatPosition(topQueriesContext ? metricValue(topQueriesContext, 'position', currentRange) as number | null : null)}</p>
                        <p className="text-xs text-stone-600">{t('gsc.topQueries.summaryIssues')}: {formatNullable(topQueriesContext?.technical_issue_count)}</p>
                      </div>
                    </div>

                    {topQueriesQuery.data.items.length === 0 ? (
                      <EmptyState title={t('gsc.empty.topQueriesNoRowsTitle')} description={t('gsc.empty.topQueriesNoRowsDescription')} />
                    ) : (
                      <>
                        <DataTable
                          columns={[
                            {
                              key: 'query',
                              header: t('gsc.topQueries.table.query'),
                              sortKey: 'query',
                              minWidth: 320,
                              cell: (row) => <span title={row.query}>{row.query}</span>,
                            },
                            {
                              key: 'clicks',
                              header: t('gsc.topQueries.table.clicks'),
                              sortKey: 'clicks',
                              minWidth: 100,
                              cell: (row) => formatNullable(row.clicks),
                            },
                            {
                              key: 'impressions',
                              header: t('gsc.topQueries.table.impressions'),
                              sortKey: 'impressions',
                              minWidth: 110,
                              cell: (row) => formatNullable(row.impressions),
                            },
                            {
                              key: 'ctr',
                              header: t('gsc.topQueries.table.ctr'),
                              sortKey: 'ctr',
                              minWidth: 90,
                              cell: (row) => formatPercent(row.ctr),
                            },
                            {
                              key: 'position',
                              header: t('gsc.topQueries.table.position'),
                              sortKey: 'position',
                              minWidth: 90,
                              cell: (row) => formatPosition(row.position),
                            },
                          ]}
                          rows={topQueriesQuery.data.items}
                          rowKey={(row) => row.id}
                          sortBy={topQueriesParams.sort_by}
                          sortOrder={topQueriesParams.sort_order as SortOrder}
                          onSortChange={handleQuerySort}
                        />
                        <PaginationControls
                          page={topQueriesQuery.data.page}
                          pageSize={topQueriesQuery.data.page_size}
                          totalItems={topQueriesQuery.data.total_items}
                          totalPages={topQueriesQuery.data.total_pages}
                          onPageChange={(page) => updateParams({ queries_page: page })}
                          onPageSizeChange={(pageSize) => updateParams({ queries_page_size: pageSize, queries_page: 1 })}
                        />
                      </>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
