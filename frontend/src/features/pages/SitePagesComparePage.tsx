import { startTransition, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

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
import type { CompareDeltaTrend, CrawlCompareChangeType, SortOrder } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatCrawlDateTime, formatNullable, formatResponseTime } from '../../utils/format'
import {
  mergeSearchParams,
  parseCsvParam,
  parseIntegerParam,
  serializeCsvParam,
  toggleCsvParamValue,
} from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import { buildSiteChangesOpportunitiesPath, buildSitePagesPath } from '../sites/routes'
import { type SitePagesCompareQueryParams, useSitePagesCompareQuery } from './api'

const PAGE_CHANGE_TYPES: CrawlCompareChangeType[] = ['improved', 'worsened', 'unchanged', 'new', 'missing']
const TREND_VALUES: CompareDeltaTrend[] = ['improved', 'worsened', 'flat']

function getBooleanFilterValue(searchParams: URLSearchParams, key: string) {
  const value = searchParams.get(key)
  return value === 'true' || value === 'false' ? value : ''
}

function readSingleCsvValue<T extends string>(value: string | null, allowedValues: readonly T[]): T | '' {
  const values = Array.from(parseCsvParam(value, allowedValues))
  return values.length === 1 ? values[0] : ''
}

function readParams(searchParams: URLSearchParams, activeCrawlId?: number | null, baselineCrawlId?: number | null): SitePagesCompareQueryParams {
  const sortBy = searchParams.get('sort_by')
  const sortOrder = searchParams.get('sort_order')

  return {
    active_crawl_id: activeCrawlId ?? undefined,
    baseline_crawl_id: baselineCrawlId ?? undefined,
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), 25),
    sort_by:
      sortBy === 'url' ||
      sortBy === 'active_status_code' ||
      sortBy === 'delta_priority_score' ||
      sortBy === 'active_priority_score' ||
      sortBy === 'delta_word_count' ||
      sortBy === 'delta_response_time_ms' ||
      sortBy === 'delta_incoming_internal_links' ||
      sortBy === 'delta_incoming_internal_linking_pages' ||
      sortBy === 'priority_trend' ||
      sortBy === 'word_count_trend' ||
      sortBy === 'response_time_trend' ||
      sortBy === 'internal_linking_trend'
        ? sortBy
        : 'change_type',
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    change_type: searchParams.get('change_type') || undefined,
    changed: searchParams.get('changed') === null ? undefined : searchParams.get('changed') === 'true',
    status_changed: searchParams.get('status_changed') === null ? undefined : searchParams.get('status_changed') === 'true',
    title_changed: searchParams.get('title_changed') === null ? undefined : searchParams.get('title_changed') === 'true',
    meta_description_changed:
      searchParams.get('meta_description_changed') === null
        ? undefined
        : searchParams.get('meta_description_changed') === 'true',
    h1_changed: searchParams.get('h1_changed') === null ? undefined : searchParams.get('h1_changed') === 'true',
    canonical_changed:
      searchParams.get('canonical_changed') === null ? undefined : searchParams.get('canonical_changed') === 'true',
    noindex_changed: searchParams.get('noindex_changed') === null ? undefined : searchParams.get('noindex_changed') === 'true',
    priority_trend: searchParams.get('priority_trend') || undefined,
    internal_linking_trend: searchParams.get('internal_linking_trend') || undefined,
    content_trend: searchParams.get('content_trend') || undefined,
    response_time_trend: searchParams.get('response_time_trend') || undefined,
    url_contains: searchParams.get('url_contains') || undefined,
  }
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

function trendTone(trend: CompareDeltaTrend | null | undefined): 'stone' | 'rose' | 'amber' | 'teal' {
  if (trend === 'improved') {
    return 'teal'
  }
  if (trend === 'worsened') {
    return 'rose'
  }
  return 'stone'
}

function formatSignedInteger(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  return value > 0 ? `+${value}` : String(value)
}

export function SitePagesComparePage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  useDocumentTitle(t('documentTitle.pagesCompare', { domain: site.domain }))

  const [searchParams, setSearchParams] = useSearchParams()
  const compareParams = useMemo(() => readParams(searchParams, activeCrawlId, baselineCrawlId), [activeCrawlId, baselineCrawlId, searchParams])
  const compareQuery = useSitePagesCompareQuery(site.id, compareParams)
  const selectedChangeTypes = useMemo(() => parseCsvParam(searchParams.get('change_type'), PAGE_CHANGE_TYPES), [searchParams])
  const selectedPriorityTrends = useMemo(() => parseCsvParam(searchParams.get('priority_trend'), TREND_VALUES), [searchParams])
  const selectedInternalLinkingTrends = useMemo(
    () => parseCsvParam(searchParams.get('internal_linking_trend'), TREND_VALUES),
    [searchParams],
  )
  const selectedContentTrends = useMemo(() => parseCsvParam(searchParams.get('content_trend'), TREND_VALUES), [searchParams])

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function toggleCsvFilter(key: string, value: string) {
    const next = toggleCsvParamValue(parseCsvParam(searchParams.get(key)), value)
    updateParams({ [key]: serializeCsvParam(next), page: 1 })
  }

  function toggleBooleanFilter(key: string, isActive: boolean) {
    updateParams({ [key]: isActive ? undefined : 'true', page: 1 })
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: compareParams.gsc_date_range,
      page: 1,
      page_size: 25,
      sort_by: 'change_type',
      sort_order: 'desc',
      change_type: undefined,
      changed: undefined,
      status_changed: undefined,
      title_changed: undefined,
      meta_description_changed: undefined,
      h1_changed: undefined,
      canonical_changed: undefined,
      noindex_changed: undefined,
      priority_trend: undefined,
      internal_linking_trend: undefined,
      content_trend: undefined,
      response_time_trend: undefined,
      url_contains: undefined,
    })
  }

  const quickFilters = [
    { label: t('pagesCompare.quickFilters.newUrls'), isActive: selectedChangeTypes.has('new'), onClick: () => toggleCsvFilter('change_type', 'new') },
    { label: t('pagesCompare.quickFilters.missingUrls'), isActive: selectedChangeTypes.has('missing'), onClick: () => toggleCsvFilter('change_type', 'missing') },
    { label: t('pagesCompare.quickFilters.changed'), isActive: compareParams.changed === true, onClick: () => toggleBooleanFilter('changed', compareParams.changed === true) },
    { label: t('pagesCompare.quickFilters.statusChanged'), isActive: compareParams.status_changed === true, onClick: () => toggleBooleanFilter('status_changed', compareParams.status_changed === true) },
    { label: t('pagesCompare.quickFilters.titleChanged'), isActive: compareParams.title_changed === true, onClick: () => toggleBooleanFilter('title_changed', compareParams.title_changed === true) },
    { label: t('pagesCompare.quickFilters.h1Changed'), isActive: compareParams.h1_changed === true, onClick: () => toggleBooleanFilter('h1_changed', compareParams.h1_changed === true) },
    { label: t('pagesCompare.quickFilters.canonicalChanged'), isActive: compareParams.canonical_changed === true, onClick: () => toggleBooleanFilter('canonical_changed', compareParams.canonical_changed === true) },
    { label: t('pagesCompare.quickFilters.noindexChanged'), isActive: compareParams.noindex_changed === true, onClick: () => toggleBooleanFilter('noindex_changed', compareParams.noindex_changed === true) },
    { label: t('pagesCompare.quickFilters.priorityUp'), isActive: selectedPriorityTrends.has('improved'), onClick: () => toggleCsvFilter('priority_trend', 'improved') },
    { label: t('pagesCompare.quickFilters.priorityDown'), isActive: selectedPriorityTrends.has('worsened'), onClick: () => toggleCsvFilter('priority_trend', 'worsened') },
    { label: t('pagesCompare.quickFilters.linksUp'), isActive: selectedInternalLinkingTrends.has('improved'), onClick: () => toggleCsvFilter('internal_linking_trend', 'improved') },
    { label: t('pagesCompare.quickFilters.linksDown'), isActive: selectedInternalLinkingTrends.has('worsened'), onClick: () => toggleCsvFilter('internal_linking_trend', 'worsened') },
    { label: t('pagesCompare.quickFilters.contentUp'), isActive: selectedContentTrends.has('improved'), onClick: () => toggleCsvFilter('content_trend', 'improved') },
    { label: t('pagesCompare.quickFilters.contentDown'), isActive: selectedContentTrends.has('worsened'), onClick: () => toggleCsvFilter('content_trend', 'worsened') },
  ]

  if (compareQuery.isLoading) {
    return <LoadingState label={t('pagesCompare.loading')} />
  }

  if (compareQuery.isError) {
    return <ErrorState title={t('pagesCompare.errorTitle')} message={getUiErrorMessage(compareQuery.error, t)} />
  }

  const payload = compareQuery.data
  if (!payload) {
    return <EmptyState title={t('pagesCompare.emptyTitle')} description={t('pagesCompare.emptyDescription')} />
  }

  if (!payload.context.compare_available) {
    return (
      <EmptyState
        title={t('pagesCompare.compareUnavailableTitle')}
        description={payload.context.compare_unavailable_reason ?? t('pagesCompare.compareUnavailableDescription')}
      />
    )
  }

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('pagesCompare.eyebrow')}
        title={t('pagesCompare.title')}
        description={t('pagesCompare.description', {
          active: formatCrawlDateTime(payload.context.active_crawl),
          baseline: formatCrawlDateTime(payload.context.baseline_crawl),
        })}
        contextChips={[
          {
            label: 'Active',
            value: payload.context.active_crawl_id ? `#${payload.context.active_crawl_id}` : '-',
          },
          {
            label: 'Baseline',
            value: payload.context.baseline_crawl_id ? `#${payload.context.baseline_crawl_id}` : '-',
          },
          {
            label: 'Compare',
            value: payload.context.compare_available ? 'Ready' : 'Waiting',
            tone: payload.context.compare_available ? 'success' : 'warning',
          },
        ]}
        primaryAction={{
          key: 'open-current-state-pages',
          label: t('pagesCompare.actions.openCurrentState'),
          to: buildSitePagesPath(site.id, { activeCrawlId, baselineCrawlId }),
        }}
        operations={
          activeCrawlId
            ? [
                {
                  key: 'open-active-crawl',
                  label: t('pagesCompare.actions.openActiveCrawl'),
                  to: `/jobs/${activeCrawlId}`,
                },
              ]
            : []
        }
      />

      <SummaryCards
        items={[
          { label: t('pagesCompare.summary.activeUrls'), value: payload.summary.active_urls },
          { label: t('pagesCompare.summary.newUrls'), value: payload.summary.new_urls },
          { label: t('pagesCompare.summary.missingUrls'), value: payload.summary.missing_urls },
          { label: t('pagesCompare.summary.changedUrls'), value: payload.summary.changed_urls },
          { label: t('pagesCompare.summary.improvedUrls'), value: payload.summary.improved_urls },
          { label: t('pagesCompare.summary.worsenedUrls'), value: payload.summary.worsened_urls },
          { label: t('pagesCompare.summary.statusChanged'), value: payload.summary.status_changed_urls },
          { label: t('pagesCompare.summary.priorityDown'), value: payload.summary.priority_worsened_urls },
        ]}
      />

      <QuickFilterBar title={t('pagesCompare.quickFilters.title')} items={quickFilters} onReset={resetFilters} />

      <FilterPanel title={t('pagesCompare.filters.title')} description={t('pagesCompare.filters.description')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pagesCompare.filters.dateRange')}</span>
          <select
            value={compareParams.gsc_date_range}
            onChange={(event) => updateParams({ gsc_date_range: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="last_28_days">{t('pagesCompare.filters.last28Days')}</option>
            <option value="last_90_days">{t('pagesCompare.filters.last90Days')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pagesCompare.filters.changeType')}</span>
          <select
            value={readSingleCsvValue(compareParams.change_type ?? null, PAGE_CHANGE_TYPES)}
            onChange={(event) => updateParams({ change_type: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="new">{t('pagesCompare.changeType.new')}</option>
            <option value="missing">{t('pagesCompare.changeType.missing')}</option>
            <option value="improved">{t('pagesCompare.changeType.improved')}</option>
            <option value="worsened">{t('pagesCompare.changeType.worsened')}</option>
            <option value="unchanged">{t('pagesCompare.changeType.unchanged')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pagesCompare.filters.urlContains')}</span>
          <input
            value={compareParams.url_contains ?? ''}
            onChange={(event) => updateParams({ url_contains: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          />
        </label>
        {[
          ['status_changed', t('pagesCompare.filters.statusChanged')],
          ['title_changed', t('pagesCompare.filters.titleChanged')],
          ['meta_description_changed', t('pagesCompare.filters.metaDescriptionChanged')],
          ['h1_changed', t('pagesCompare.filters.h1Changed')],
          ['canonical_changed', t('pagesCompare.filters.canonicalChanged')],
          ['noindex_changed', t('pagesCompare.filters.noindexChanged')],
        ].map(([key, label]) => (
          <label key={key} className="grid gap-1 text-sm text-stone-700">
            <span>{label}</span>
            <select
              value={getBooleanFilterValue(searchParams, key)}
              onChange={(event) => updateParams({ [key]: event.target.value || undefined, page: 1 })}
              className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            >
              <option value="">{t('common.any')}</option>
              <option value="true">{t('common.yes')}</option>
              <option value="false">{t('common.no')}</option>
            </select>
          </label>
        ))}
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pagesCompare.filters.priorityTrend')}</span>
          <select
            value={readSingleCsvValue(compareParams.priority_trend ?? null, TREND_VALUES)}
            onChange={(event) => updateParams({ priority_trend: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="improved">{t('pagesCompare.trend.improved')}</option>
            <option value="worsened">{t('pagesCompare.trend.worsened')}</option>
            <option value="flat">{t('pagesCompare.trend.flat')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pagesCompare.filters.internalLinkingTrend')}</span>
          <select
            value={readSingleCsvValue(compareParams.internal_linking_trend ?? null, TREND_VALUES)}
            onChange={(event) => updateParams({ internal_linking_trend: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="improved">{t('pagesCompare.trend.improved')}</option>
            <option value="worsened">{t('pagesCompare.trend.worsened')}</option>
            <option value="flat">{t('pagesCompare.trend.flat')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pagesCompare.filters.contentTrend')}</span>
          <select
            value={readSingleCsvValue(compareParams.content_trend ?? null, TREND_VALUES)}
            onChange={(event) => updateParams({ content_trend: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="improved">{t('pagesCompare.trend.improved')}</option>
            <option value="worsened">{t('pagesCompare.trend.worsened')}</option>
            <option value="flat">{t('pagesCompare.trend.flat')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pagesCompare.filters.sortBy')}</span>
          <select
            value={compareParams.sort_by}
            onChange={(event) => updateParams({ sort_by: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="change_type">{t('pagesCompare.filters.sort.changeType')}</option>
            <option value="delta_priority_score">{t('pagesCompare.filters.sort.priorityDelta')}</option>
            <option value="delta_word_count">{t('pagesCompare.filters.sort.wordCountDelta')}</option>
            <option value="delta_response_time_ms">{t('pagesCompare.filters.sort.responseTimeDelta')}</option>
            <option value="delta_incoming_internal_links">{t('pagesCompare.filters.sort.internalLinksDelta')}</option>
            <option value="url">{t('pagesCompare.filters.sort.url')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('pagesCompare.filters.sortOrder')}</span>
          <select
            value={compareParams.sort_order}
            onChange={(event) => updateParams({ sort_order: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="desc">{t('sort.descending')}</option>
            <option value="asc">{t('sort.ascending')}</option>
          </select>
        </label>
      </FilterPanel>

      {payload.items.length === 0 ? (
        <EmptyState title={t('pagesCompare.emptyTitle')} description={t('pagesCompare.emptyDescription')} />
      ) : (
        <>
          <DataTable
            columns={[
              {
                key: 'url',
                header: t('pagesCompare.table.url'),
                sortKey: 'url',
                minWidth: 320,
                cell: (row) => (
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap gap-1.5">
                      {renderBadge(t(`pagesCompare.changeType.${row.change_type}`), changeTone(row.change_type))}
                      {row.changed_fields.map((field) => (
                        <span key={field}>{renderBadge(t(`pagesCompare.changedFields.${field}`), 'stone')}</span>
                      ))}
                    </div>
                    <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.url}>{row.url}</p>
                    <UrlActions url={row.url} />
                    <div className="flex flex-wrap gap-2 text-xs font-medium text-teal-700">
                      {activeCrawlId ? <Link to={`/jobs/${activeCrawlId}/pages?url_contains=${encodeURIComponent(row.url)}`}>{t('pagesCompare.table.openActivePages')}</Link> : null}
                      <Link
                        to={buildSiteChangesOpportunitiesPath(site.id, {
                          activeCrawlId,
                          baselineCrawlId,
                        })}
                      >
                        {t('pagesCompare.table.openOpportunitiesCompare')}
                      </Link>
                    </div>
                  </div>
                ),
              },
              {
                key: 'active',
                header: t('pagesCompare.table.active'),
                minWidth: 320,
                cell: (row) => (
                  <div className="space-y-1 text-xs text-stone-600">
                    <p>{t('pagesCompare.table.status')}: <span className="font-medium text-stone-900">{formatNullable(row.active_status_code)}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('pagesCompare.table.titleLabel')}: <span className="font-medium text-stone-900">{row.active_title ?? '-'}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('pagesCompare.table.h1Label')}: <span className="font-medium text-stone-900">{row.active_h1 ?? '-'}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('pagesCompare.table.canonicalLabel')}: <span className="font-medium text-stone-900">{row.active_canonical_url ?? '-'}</span></p>
                    <p>{t('pagesCompare.table.noindexLabel')}: <span className="font-medium text-stone-900">{String(row.active_noindex_like ?? '-')}</span></p>
                  </div>
                ),
              },
              {
                key: 'baseline',
                header: t('pagesCompare.table.baseline'),
                minWidth: 320,
                cell: (row) => (
                  <div className="space-y-1 text-xs text-stone-600">
                    <p>{t('pagesCompare.table.status')}: <span className="font-medium text-stone-900">{formatNullable(row.baseline_status_code)}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('pagesCompare.table.titleLabel')}: <span className="font-medium text-stone-900">{row.baseline_title ?? '-'}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('pagesCompare.table.h1Label')}: <span className="font-medium text-stone-900">{row.baseline_h1 ?? '-'}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('pagesCompare.table.canonicalLabel')}: <span className="font-medium text-stone-900">{row.baseline_canonical_url ?? '-'}</span></p>
                    <p>{t('pagesCompare.table.noindexLabel')}: <span className="font-medium text-stone-900">{String(row.baseline_noindex_like ?? '-')}</span></p>
                  </div>
                ),
              },
              {
                key: 'delta',
                header: t('pagesCompare.table.delta'),
                sortKey: 'delta_priority_score',
                minWidth: 220,
                cell: (row) => (
                  <div className="space-y-1 text-xs text-stone-600">
                    <p>{t('pagesCompare.table.priorityDelta')}: <span className="font-medium text-stone-900">{formatSignedInteger(row.delta_priority_score)}</span></p>
                    <p>{t('pagesCompare.table.wordCountDelta')}: <span className="font-medium text-stone-900">{formatSignedInteger(row.delta_word_count)}</span></p>
                    <p>{t('pagesCompare.table.responseTimeDelta')}: <span className="font-medium text-stone-900">{formatSignedInteger(row.delta_response_time_ms)}</span></p>
                    <p>{t('pagesCompare.table.internalLinksDelta')}: <span className="font-medium text-stone-900">{formatSignedInteger(row.delta_incoming_internal_links)}</span></p>
                    <p>{t('pagesCompare.table.linkingPagesDelta')}: <span className="font-medium text-stone-900">{formatSignedInteger(row.delta_incoming_internal_linking_pages)}</span></p>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {row.priority_trend ? renderBadge(t(`pagesCompare.trend.${row.priority_trend}`), trendTone(row.priority_trend)) : null}
                      {row.word_count_trend ? renderBadge(t(`pagesCompare.trend.${row.word_count_trend}`), trendTone(row.word_count_trend)) : null}
                      {row.internal_linking_trend ? renderBadge(t(`pagesCompare.trend.${row.internal_linking_trend}`), trendTone(row.internal_linking_trend)) : null}
                    </div>
                  </div>
                ),
              },
              {
                key: 'rationale',
                header: t('pagesCompare.table.rationale'),
                minWidth: 260,
                cell: (row) => (
                  <div className="space-y-1">
                    <p className="text-sm leading-5 text-stone-700 [overflow-wrap:anywhere]" title={row.change_rationale}>{row.change_rationale}</p>
                    <p className="text-xs text-stone-500">
                      {t('pagesCompare.table.responseTime')}: {formatResponseTime(row.active_response_time_ms)}
                    </p>
                  </div>
                ),
              },
            ]}
            rows={payload.items}
            rowKey={(row) => row.normalized_url}
            sortBy={compareParams.sort_by}
            sortOrder={compareParams.sort_order as SortOrder}
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
    </div>
  )
}
