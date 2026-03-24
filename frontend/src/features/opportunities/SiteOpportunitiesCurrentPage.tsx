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
  OpportunityGroup,
  OpportunityPagePreview,
  OpportunityType,
  PriorityLevel,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatCrawlDateTime, formatNullable, formatPercent, formatPosition } from '../../utils/format'
import {
  mergeSearchParams,
  parseCsvParam,
  parseIntegerParam,
  serializeCsvParam,
  toggleCsvParamValue,
} from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import {
  buildSiteChangesOpportunitiesPath,
  buildSiteOpportunitiesPath,
  buildSiteOpportunitiesRecordsPath,
} from '../sites/routes'
import { localizeOpportunityRationale } from './rationaleLocalization'
import { type OpportunitiesQueryParams, useOpportunitiesQuery } from './api'

const OPPORTUNITY_TYPES: OpportunityType[] = [
  'QUICK_WINS',
  'HIGH_IMPRESSIONS_LOW_CTR',
  'TRAFFIC_WITH_TECHNICAL_ISSUES',
  'IMPORTANT_BUT_WEAK',
  'LOW_HANGING_FRUIT',
  'HIGH_RISK_PAGES',
  'UNDERLINKED_OPPORTUNITIES',
]

type SiteOpportunitiesMode = 'overview' | 'records'
type OpportunityQuickFilter = 'HIGH_PRIORITY' | OpportunityType

interface SiteOpportunitiesCurrentPageProps {
  mode?: SiteOpportunitiesMode
}

interface OpportunityRecord extends OpportunityPagePreview {
  surfaced_by_types: OpportunityType[]
}

function readPriorityLevel(searchParams: URLSearchParams): PriorityLevel | undefined {
  const value = searchParams.get('priority_level')
  return value === 'low' || value === 'medium' || value === 'high' || value === 'critical'
    ? value
    : undefined
}

function readOpportunityType(searchParams: URLSearchParams): OpportunityType | undefined {
  const value = searchParams.get('opportunity_type')
  return OPPORTUNITY_TYPES.includes(value as OpportunityType) ? (value as OpportunityType) : undefined
}

function readParams(searchParams: URLSearchParams, mode: SiteOpportunitiesMode): OpportunitiesQueryParams {
  const sortBy = searchParams.get('sort_by')
  const sortOrder = searchParams.get('sort_order')

  return {
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    priority_level: readPriorityLevel(searchParams),
    opportunity_type: readOpportunityType(searchParams),
    priority_score_min: parseIntegerParam(searchParams.get('priority_score_min'), undefined),
    priority_score_max: parseIntegerParam(searchParams.get('priority_score_max'), undefined),
    sort_by:
      sortBy === 'top_priority_score' || sortBy === 'top_opportunity_score' || sortBy === 'type'
        ? sortBy
        : 'count',
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    top_pages_limit: parseIntegerParam(searchParams.get('top_pages_limit'), mode === 'records' ? 18 : 8),
  }
}

function readQuickFilters(searchParams: URLSearchParams) {
  return parseCsvParam<OpportunityQuickFilter>(searchParams.get('quick_filters'))
}

function serializeQuickFilters(filters: Set<OpportunityQuickFilter>) {
  return serializeCsvParam(filters)
}

function buildExportHref(jobId: number, params: OpportunitiesQueryParams, kind: 'pages' | 'opportunities') {
  const query = new URLSearchParams()
  query.set('gsc_date_range', params.gsc_date_range)
  if (params.priority_level) query.set('priority_level', params.priority_level)
  if (params.opportunity_type) query.set('opportunity_type', params.opportunity_type)
  if (params.priority_score_min !== undefined) query.set('priority_score_min', String(params.priority_score_min))
  if (params.priority_score_max !== undefined) query.set('priority_score_max', String(params.priority_score_max))
  if (kind === 'pages') {
    query.set('sort_by', 'priority_score')
    query.set('sort_order', 'desc')
  }
  const serialized = query.toString()
  return buildApiUrl(`/crawl-jobs/${jobId}/export/${kind}.csv${serialized ? `?${serialized}` : ''}`)
}

function flattenRecords(groups: OpportunityGroup[], topPriorityPages: OpportunityPagePreview[]) {
  const map = new Map<number, OpportunityRecord>()
  const append = (record: OpportunityPagePreview, surfacedBy: OpportunityType) => {
    const existing = map.get(record.page_id)
    if (!existing) {
      map.set(record.page_id, { ...record, surfaced_by_types: [surfacedBy] })
      return
    }
    map.set(record.page_id, {
      ...existing,
      opportunity_count: Math.max(existing.opportunity_count, record.opportunity_count),
      priority_score: Math.max(existing.priority_score, record.priority_score),
      opportunity_types: Array.from(new Set([...existing.opportunity_types, ...record.opportunity_types])),
      surfaced_by_types: Array.from(new Set([...existing.surfaced_by_types, surfacedBy])),
    })
  }

  groups.forEach((group) => group.top_pages.forEach((page) => append(page, group.type)))
  topPriorityPages.forEach((page) => append(page, page.primary_opportunity_type ?? page.opportunity_types[0] ?? 'QUICK_WINS'))
  return Array.from(map.values()).sort((left, right) => right.priority_score - left.priority_score)
}

function applyQuickFiltersToGroups(groups: OpportunityGroup[], quickFilters: Set<OpportunityQuickFilter>) {
  const selectedTypes = Array.from(quickFilters).filter((value): value is OpportunityType => value !== 'HIGH_PRIORITY')
  const highPriorityOnly = quickFilters.has('HIGH_PRIORITY')

  return groups.filter((group) => {
    if (selectedTypes.length > 0 && !selectedTypes.includes(group.type)) return false
    if (highPriorityOnly && !group.top_pages.some((page) => page.priority_score >= 45)) return false
    return true
  })
}

function applyQuickFiltersToRecords(records: OpportunityRecord[], quickFilters: Set<OpportunityQuickFilter>) {
  const selectedTypes = Array.from(quickFilters).filter((value): value is OpportunityType => value !== 'HIGH_PRIORITY')
  const highPriorityOnly = quickFilters.has('HIGH_PRIORITY')

  return records.filter((record) => {
    if (selectedTypes.length > 0 && !record.opportunity_types.some((type) => selectedTypes.includes(type))) return false
    if (highPriorityOnly && record.priority_score < 45) return false
    return true
  })
}

function appendPathQuery(path: string, params: Record<string, string | number | undefined>) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  const serialized = query.toString()
  return serialized ? `${path}${path.includes('?') ? '&' : '?'}${serialized}` : path
}

export function SiteOpportunitiesCurrentPage({ mode = 'overview' }: SiteOpportunitiesCurrentPageProps) {
  const { t, i18n } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null)
  const currentLanguage = i18n.resolvedLanguage ?? i18n.language

  useDocumentTitle(
    mode === 'overview'
      ? t('documentTitle.siteOpportunities', { domain: site.domain })
      : t('documentTitle.siteOpportunitiesRecords', { domain: site.domain }),
  )

  const opportunitiesParams = useMemo(() => readParams(searchParams, mode), [mode, searchParams])
  const quickFilters = useMemo(() => readQuickFilters(searchParams), [searchParams])
  const page = parseIntegerParam(searchParams.get('page'), 1)
  const pageSize = parseIntegerParam(searchParams.get('page_size'), mode === 'records' ? 10 : 6)
  const query = useOpportunitiesQuery(activeCrawlId ?? -1, opportunitiesParams, Boolean(activeCrawlId))
  const routeContext = { activeCrawlId, baselineCrawlId }

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function toggleQuickFilter(filter: OpportunityQuickFilter) {
    const nextFilters = toggleCsvParamValue(quickFilters, filter)
    updateParams({ quick_filters: serializeQuickFilters(nextFilters), page: 1 })
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: 'last_28_days',
      priority_level: undefined,
      opportunity_type: undefined,
      priority_score_min: undefined,
      priority_score_max: undefined,
      sort_by: 'count',
      sort_order: 'desc',
      top_pages_limit: mode === 'records' ? 18 : 8,
      quick_filters: undefined,
      page: 1,
      page_size: mode === 'records' ? 10 : 6,
    })
  }

  const effectRecords = query.data
    ? applyQuickFiltersToRecords(flattenRecords(query.data.groups, query.data.top_priority_pages), quickFilters)
    : []

  useEffect(() => {
    if (selectedRecordId && effectRecords.some((record) => record.page_id === selectedRecordId)) return
    setSelectedRecordId(effectRecords[0]?.page_id ?? null)
  }, [effectRecords, selectedRecordId])

  if (!activeCrawlId || !site.active_crawl) {
    return <EmptyState title={t('siteOpportunities.noActiveCrawlTitle')} description={t('siteOpportunities.noActiveCrawlDescription')} />
  }

  if (query.isLoading) {
    return <LoadingState label={t('siteOpportunities.loading')} />
  }

  if (query.isError) {
    return <ErrorState title={t('siteOpportunities.errorTitle')} message={getUiErrorMessage(query.error, t)} />
  }

  const payload = query.data
  if (!payload) {
    return <EmptyState title={t('siteOpportunities.emptyTitle')} description={t('siteOpportunities.emptyDescription')} />
  }

  const visibleGroups = applyQuickFiltersToGroups(payload.groups, quickFilters)
  const visibleRecords = applyQuickFiltersToRecords(flattenRecords(payload.groups, payload.top_priority_pages), quickFilters)
  const totalPages = Math.max(1, Math.ceil(visibleRecords.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const paginatedRecords = visibleRecords.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const selectedRecord = visibleRecords.find((record) => record.page_id === selectedRecordId) ?? visibleRecords[0] ?? null

  const quickFilterItems = [
    { label: t('opportunities.quickFilters.highPriority'), isActive: quickFilters.has('HIGH_PRIORITY'), onClick: () => toggleQuickFilter('HIGH_PRIORITY') },
    ...OPPORTUNITY_TYPES.map((type) => ({
      label: t(`opportunities.types.${type}.title`),
      isActive: quickFilters.has(type),
      onClick: () => toggleQuickFilter(type),
    })),
  ]

  const recordsPath = buildSiteOpportunitiesRecordsPath(site.id, routeContext)
  const overviewPath = buildSiteOpportunitiesPath(site.id, routeContext)
  const changesPath = buildSiteChangesOpportunitiesPath(site.id, routeContext)
  const exportPagesHref = buildExportHref(activeCrawlId, opportunitiesParams, 'pages')
  const exportOpportunitiesHref = buildExportHref(activeCrawlId, opportunitiesParams, 'opportunities')

  const recordColumns = [
    {
      key: 'url',
      header: t('opportunities.table.url'),
      minWidth: 320,
      cell: (row: OpportunityRecord) => (
        <div className="space-y-1.5">
          <div className="flex flex-wrap gap-1.5">
            {row.surfaced_by_types.map((type) => (
              <span key={`${row.page_id}-${type}`} className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                {t(`opportunities.types.${type}.title`)}
              </span>
            ))}
          </div>
          <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.url}>{row.url}</p>
          <UrlActions url={row.url} />
        </div>
      ),
    },
    {
      key: 'priority',
      header: t('opportunities.table.priority'),
      minWidth: 180,
      cell: (row: OpportunityRecord) => `${row.priority_score} / ${t(`opportunities.priorityLevel.${row.priority_level}`)}`,
    },
    {
      key: 'traffic',
      header: t('opportunities.table.traffic'),
      minWidth: 180,
      cell: (row: OpportunityRecord) => (
        <div className="space-y-1 text-xs text-stone-600">
          <p>{t('opportunities.metrics.clicks')}: {formatNullable(row.clicks)}</p>
          <p>{t('opportunities.metrics.impressions')}: {formatNullable(row.impressions)}</p>
          <p>{t('opportunities.metrics.ctr')}: {formatPercent(row.ctr)}</p>
          <p>{t('opportunities.metrics.position')}: {formatPosition(row.position)}</p>
        </div>
      ),
    },
    {
      key: 'rationale',
      header: t('opportunities.table.rationale'),
      minWidth: 280,
      cell: (row: OpportunityRecord) => {
        const localized = localizeOpportunityRationale(row.rationale, currentLanguage, t)
        return <span className="[overflow-wrap:anywhere]" title={localized}>{localized}</span>
      },
    },
    {
      key: 'inspect',
      header: t('common.open'),
      minWidth: 120,
      cell: (row: OpportunityRecord) => (
        <button type="button" onClick={() => setSelectedRecordId(row.page_id)} className="rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100">
          {t('siteOpportunities.inspectRecord')}
        </button>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('nav.opportunities')}
        title={mode === 'overview' ? t('siteOpportunities.title') : t('siteOpportunities.recordsTitle')}
        description={mode === 'overview' ? t('siteOpportunities.description') : t('siteOpportunities.recordsDescription')}
        contextChips={[
          { label: 'Active', value: site.active_crawl ? formatCrawlDateTime(site.active_crawl) : '-' },
        ]}
        primaryAction={{
          key: mode === 'overview' ? 'open-records' : 'open-overview',
          label: mode === 'overview' ? t('siteOpportunities.openRecords') : t('siteOpportunities.openOverview'),
          to: mode === 'overview' ? recordsPath : overviewPath,
        }}
        operations={[
          {
            key: 'open-changes',
            label: t('siteOpportunities.openChanges'),
            to: changesPath,
          },
          {
            key: 'open-active-crawl',
            label: t('siteOpportunities.openActiveCrawl'),
            to: `/jobs/${activeCrawlId}`,
          },
        ]}
        exports={[
          {
            key: 'export-pages',
            label: t('siteOpportunities.exportPages'),
            href: exportPagesHref,
          },
          {
            key: 'export-opportunities',
            label: t('siteOpportunities.exportOpportunities'),
            href: exportOpportunitiesHref,
          },
        ]}
      />

      <SummaryCards
        items={[
          { label: t('opportunities.summary.pagesWithOpportunities'), value: payload.pages_with_opportunities },
          { label: t('opportunities.summary.highPriorityPages'), value: payload.high_priority_pages },
          { label: t('opportunities.summary.criticalPriorityPages'), value: payload.critical_priority_pages },
          { label: t('opportunities.summary.groups'), value: payload.groups.length },
          { label: t('siteOpportunities.visibleRecords'), value: visibleRecords.length },
          { label: t('opportunities.summary.range'), value: payload.gsc_date_range === 'last_90_days' ? '90d' : '28d' },
        ]}
      />

      <QuickFilterBar title={t('siteOpportunities.quickFiltersTitle')} items={quickFilterItems} onReset={() => updateParams({ quick_filters: undefined, page: 1 })} />

      <FilterPanel title={t('opportunities.filters.title')} description={t('siteOpportunities.filtersDescription')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.dateRange')}</span>
          <select value={opportunitiesParams.gsc_date_range} onChange={(event) => updateParams({ gsc_date_range: event.target.value, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="last_28_days">{t('opportunities.filters.last28Days')}</option>
            <option value="last_90_days">{t('opportunities.filters.last90Days')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.priorityLevel')}</span>
          <select value={opportunitiesParams.priority_level ?? ''} onChange={(event) => updateParams({ priority_level: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            <option value="critical">{t('opportunities.priorityLevel.critical')}</option>
            <option value="high">{t('opportunities.priorityLevel.high')}</option>
            <option value="medium">{t('opportunities.priorityLevel.medium')}</option>
            <option value="low">{t('opportunities.priorityLevel.low')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.opportunityType')}</span>
          <select value={opportunitiesParams.opportunity_type ?? ''} onChange={(event) => updateParams({ opportunity_type: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {OPPORTUNITY_TYPES.map((type) => <option key={type} value={type}>{t(`opportunities.types.${type}.title`)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.priorityMin')}</span>
          <input type="number" value={opportunitiesParams.priority_score_min ?? ''} onChange={(event) => updateParams({ priority_score_min: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.priorityMax')}</span>
          <input type="number" value={opportunitiesParams.priority_score_max ?? ''} onChange={(event) => updateParams({ priority_score_max: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('siteOpportunities.recordsPerGroup')}</span>
          <input type="number" min={4} max={30} value={opportunitiesParams.top_pages_limit} onChange={(event) => updateParams({ top_pages_limit: event.target.value || (mode === 'records' ? 18 : 8), page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" />
        </label>
      </FilterPanel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          {mode === 'overview' ? (
            <>
              <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-stone-950">{t('siteOpportunities.topRecordsTitle')}</h2>
                    <p className="mt-1 text-sm text-stone-600">{t('siteOpportunities.topRecordsDescription')}</p>
                  </div>
                  <Link to={recordsPath} className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100">
                    {t('siteOpportunities.openRecords')}
                  </Link>
                </div>
                <div className="mt-4">
                  {visibleRecords.length === 0 ? <EmptyState title={t('siteOpportunities.emptyTitle')} description={t('siteOpportunities.emptyDescription')} /> : <DataTable columns={recordColumns} rows={visibleRecords.slice(0, 6)} rowKey={(row) => row.page_id} />}
                </div>
              </section>

              <section className="space-y-4">
                <div>
                  <h2 className="text-lg font-semibold text-stone-950">{t('siteOpportunities.groupsTitle')}</h2>
                  <p className="mt-1 text-sm text-stone-600">{t('siteOpportunities.groupsDescription')}</p>
                </div>
                {visibleGroups.length === 0 ? (
                  <EmptyState title={t('siteOpportunities.groupsEmptyTitle')} description={t('siteOpportunities.groupsEmptyDescription')} />
                ) : (
                  visibleGroups.map((group) => (
                    <section key={group.type} className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
                      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                        <div>
                          <h3 className="text-lg font-semibold text-stone-950">{t(`opportunities.types.${group.type}.title`)}</h3>
                          <p className="mt-1 text-sm text-stone-600">{t(`opportunities.types.${group.type}.description`)}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <span className="inline-flex rounded-full bg-stone-100 px-3 py-1.5 text-sm font-semibold text-stone-700">{t('opportunities.groupCount', { count: group.count })}</span>
                          <Link to={appendPathQuery(recordsPath, { opportunity_type: group.type })} className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100">
                            {t('siteOpportunities.openRecords')}
                          </Link>
                        </div>
                      </div>
                      <div className="mt-4 space-y-2">
                        {group.top_pages.map((page) => (
                          <button key={`${group.type}-${page.page_id}`} type="button" onClick={() => setSelectedRecordId(page.page_id)} className="flex w-full items-center justify-between rounded-2xl border border-stone-200 bg-stone-50/85 px-4 py-3 text-left transition hover:border-stone-300 hover:bg-stone-100">
                            <span className="max-w-[70%] truncate text-sm font-medium text-stone-900" title={page.url}>{page.url}</span>
                            <span className="text-xs font-medium text-stone-600">{page.priority_score}</span>
                          </button>
                        ))}
                      </div>
                    </section>
                  ))
                )}
              </section>
            </>
          ) : (
            <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-stone-950">{t('siteOpportunities.recordsTableTitle')}</h2>
                  <p className="mt-1 text-sm text-stone-600">{t('siteOpportunities.recordsTableDescription')}</p>
                </div>
                <Link to={overviewPath} className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100">
                  {t('siteOpportunities.openOverview')}
                </Link>
              </div>
              <div className="mt-4">
                {paginatedRecords.length === 0 ? (
                  <EmptyState title={t('siteOpportunities.emptyTitle')} description={t('siteOpportunities.emptyDescription')} />
                ) : (
                  <>
                    <DataTable columns={recordColumns} rows={paginatedRecords} rowKey={(row) => row.page_id} />
                    <div className="mt-4">
                      <PaginationControls page={currentPage} pageSize={pageSize} totalItems={visibleRecords.length} totalPages={totalPages} onPageChange={(nextPage) => updateParams({ page: nextPage })} onPageSizeChange={(nextPageSize) => updateParams({ page_size: nextPageSize, page: 1 })} />
                    </div>
                  </>
                )}
              </div>
            </section>
          )}
        </div>

        <aside className="rounded-[28px] border border-stone-300 bg-white/90 p-5 shadow-sm">
          <p className="text-xs uppercase tracking-[0.18em] text-teal-700">{t('siteOpportunities.detailsTitle')}</p>
          {selectedRecord ? (
            <div className="mt-3 space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-stone-950 [overflow-wrap:anywhere]" title={selectedRecord.url}>{selectedRecord.url}</h2>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {selectedRecord.opportunity_types.map((type) => (
                    <span key={`${selectedRecord.page_id}-${type}-badge`} className="inline-flex rounded-full border border-teal-200 bg-teal-50 px-2 py-0.5 text-[11px] font-medium text-teal-700">
                      {t(`opportunities.types.${type}.title`)}
                    </span>
                  ))}
                </div>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-3 text-sm text-stone-700">
                <p>{t('opportunities.metrics.clicks')}: {formatNullable(selectedRecord.clicks)}</p>
                <p>{t('opportunities.metrics.impressions')}: {formatNullable(selectedRecord.impressions)}</p>
                <p>{t('opportunities.metrics.ctr')}: {formatPercent(selectedRecord.ctr)}</p>
                <p>{t('opportunities.metrics.position')}: {formatPosition(selectedRecord.position)}</p>
                <p>{t('opportunities.metrics.internalLinks')}: {selectedRecord.incoming_internal_links}</p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-3 text-sm leading-6 text-stone-700 [overflow-wrap:anywhere]">
                {localizeOpportunityRationale(selectedRecord.rationale, currentLanguage, t)}
              </div>
              <div className="flex flex-wrap gap-2">
                <Link to={`/jobs/${activeCrawlId}/pages?url_contains=${encodeURIComponent(selectedRecord.url)}&sort_by=priority_score&sort_order=desc`} className="rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100">
                  {t('siteOpportunities.openInActivePages')}
                </Link>
                <UrlActions url={selectedRecord.url} />
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-stone-600">{t('siteOpportunities.detailsEmpty')}</p>
          )}
        </aside>
      </div>
    </div>
  )
}
