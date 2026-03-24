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
import type {
  CrawlCompareChangeType,
  OpportunityCompareHighlight,
  OpportunityType,
  SortOrder,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatCrawlDateTime } from '../../utils/format'
import {
  mergeSearchParams,
  parseCsvParam,
  parseIntegerParam,
  serializeCsvParam,
  toggleCsvParamValue,
} from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import { buildSiteChangesPagesPath, buildSiteOpportunitiesPath } from '../sites/routes'
import { type SiteOpportunitiesCompareQueryParams, useSiteOpportunitiesCompareQuery } from './api'

const OPPORTUNITY_TYPES: OpportunityType[] = [
  'QUICK_WINS',
  'HIGH_IMPRESSIONS_LOW_CTR',
  'TRAFFIC_WITH_TECHNICAL_ISSUES',
  'IMPORTANT_BUT_WEAK',
  'LOW_HANGING_FRUIT',
  'HIGH_RISK_PAGES',
  'UNDERLINKED_OPPORTUNITIES',
]
const CHANGE_KINDS: OpportunityCompareHighlight[] = [
  'NEW_OPPORTUNITY',
  'RESOLVED_OPPORTUNITY',
  'PRIORITY_UP',
  'PRIORITY_DOWN',
  'ENTERED_ACTIONABLE',
  'LEFT_ACTIONABLE',
  'NEW_URL',
  'MISSING_URL',
]

function readSingleChangeKind(value: string | null) {
  const values = Array.from(parseCsvParam(value, CHANGE_KINDS))
  return values.length === 1 ? values[0] : ''
}

function readParams(
  searchParams: URLSearchParams,
  activeCrawlId?: number | null,
  baselineCrawlId?: number | null,
): SiteOpportunitiesCompareQueryParams {
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
      sortBy === 'change_type' ||
      sortBy === 'active_priority_score' ||
      sortBy === 'active_opportunity_count'
        ? sortBy
        : 'delta_priority_score',
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    change_kind: searchParams.get('change_kind') || undefined,
    opportunity_type: searchParams.get('opportunity_type') || undefined,
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

function highlightTone(highlight: OpportunityCompareHighlight): 'stone' | 'rose' | 'amber' | 'teal' {
  if (highlight === 'PRIORITY_DOWN' || highlight === 'LEFT_ACTIONABLE' || highlight === 'MISSING_URL') {
    return 'rose'
  }
  if (highlight === 'PRIORITY_UP' || highlight === 'ENTERED_ACTIONABLE' || highlight === 'RESOLVED_OPPORTUNITY') {
    return 'teal'
  }
  return 'amber'
}

function formatSignedInteger(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }

  return value > 0 ? `+${value}` : String(value)
}

function buildPagesComparePath(
  siteId: number,
  context: { activeCrawlId?: number | null; baselineCrawlId?: number | null },
  url: string,
) {
  const params = new URLSearchParams()
  if (context.activeCrawlId) {
    params.set('active_crawl_id', String(context.activeCrawlId))
  }
  if (context.baselineCrawlId) {
    params.set('baseline_crawl_id', String(context.baselineCrawlId))
  }
  params.set('url_contains', url)

  return `${buildSiteChangesPagesPath(siteId)}?${params.toString()}`
}

export function SiteOpportunitiesComparePage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  useDocumentTitle(t('documentTitle.opportunitiesCompare', { domain: site.domain }))

  const [searchParams, setSearchParams] = useSearchParams()
  const compareParams = useMemo(
    () => readParams(searchParams, activeCrawlId, baselineCrawlId),
    [activeCrawlId, baselineCrawlId, searchParams],
  )
  const compareQuery = useSiteOpportunitiesCompareQuery(site.id, compareParams)
  const selectedChangeKinds = useMemo(() => parseCsvParam(searchParams.get('change_kind'), CHANGE_KINDS), [searchParams])

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function toggleChangeKind(changeKind: OpportunityCompareHighlight) {
    const next = toggleCsvParamValue(selectedChangeKinds, changeKind)
    updateParams({ change_kind: serializeCsvParam(next), page: 1 })
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: compareParams.gsc_date_range,
      page: 1,
      page_size: 25,
      sort_by: 'delta_priority_score',
      sort_order: 'desc',
      change_kind: undefined,
      opportunity_type: undefined,
      url_contains: undefined,
    })
  }

  const quickFilters = [
    { label: t('opportunitiesCompare.quickFilters.newOpportunities'), isActive: selectedChangeKinds.has('NEW_OPPORTUNITY'), onClick: () => toggleChangeKind('NEW_OPPORTUNITY') },
    { label: t('opportunitiesCompare.quickFilters.resolvedOpportunities'), isActive: selectedChangeKinds.has('RESOLVED_OPPORTUNITY'), onClick: () => toggleChangeKind('RESOLVED_OPPORTUNITY') },
    { label: t('opportunitiesCompare.quickFilters.priorityUp'), isActive: selectedChangeKinds.has('PRIORITY_UP'), onClick: () => toggleChangeKind('PRIORITY_UP') },
    { label: t('opportunitiesCompare.quickFilters.priorityDown'), isActive: selectedChangeKinds.has('PRIORITY_DOWN'), onClick: () => toggleChangeKind('PRIORITY_DOWN') },
    { label: t('opportunitiesCompare.quickFilters.enteredActionable'), isActive: selectedChangeKinds.has('ENTERED_ACTIONABLE'), onClick: () => toggleChangeKind('ENTERED_ACTIONABLE') },
    { label: t('opportunitiesCompare.quickFilters.leftActionable'), isActive: selectedChangeKinds.has('LEFT_ACTIONABLE'), onClick: () => toggleChangeKind('LEFT_ACTIONABLE') },
  ]

  if (compareQuery.isLoading) {
    return <LoadingState label={t('opportunitiesCompare.loading')} />
  }

  if (compareQuery.isError) {
    return <ErrorState title={t('opportunitiesCompare.errorTitle')} message={getUiErrorMessage(compareQuery.error, t)} />
  }

  const payload = compareQuery.data
  if (!payload) {
    return <EmptyState title={t('opportunitiesCompare.emptyTitle')} description={t('opportunitiesCompare.emptyDescription')} />
  }

  if (!payload.context.compare_available) {
    return (
      <EmptyState
        title={t('opportunitiesCompare.compareUnavailableTitle')}
        description={payload.context.compare_unavailable_reason ?? t('opportunitiesCompare.compareUnavailableDescription')}
      />
    )
  }

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('opportunitiesCompare.eyebrow')}
        title={t('opportunitiesCompare.title')}
        description={t('opportunitiesCompare.description', {
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
          key: 'open-current-state-opportunities',
          label: t('opportunitiesCompare.actions.openCurrentState'),
          to: buildSiteOpportunitiesPath(site.id, { activeCrawlId, baselineCrawlId }),
        }}
        operations={
          activeCrawlId
            ? [
                {
                  key: 'open-active-crawl',
                  label: t('opportunitiesCompare.actions.openActiveCrawl'),
                  to: `/jobs/${activeCrawlId}`,
                },
              ]
            : []
        }
      />

      <SummaryCards
        items={[
          { label: t('opportunitiesCompare.summary.activeUrls'), value: payload.summary.active_urls_with_opportunities },
          { label: t('opportunitiesCompare.summary.actionableUrls'), value: payload.summary.active_actionable_urls },
          { label: t('opportunitiesCompare.summary.newOpportunities'), value: payload.summary.new_opportunity_urls },
          { label: t('opportunitiesCompare.summary.resolvedOpportunities'), value: payload.summary.resolved_opportunity_urls },
          { label: t('opportunitiesCompare.summary.priorityUp'), value: payload.summary.priority_up_urls },
          { label: t('opportunitiesCompare.summary.priorityDown'), value: payload.summary.priority_down_urls },
          { label: t('opportunitiesCompare.summary.enteredActionable'), value: payload.summary.entered_actionable_urls },
          { label: t('opportunitiesCompare.summary.leftActionable'), value: payload.summary.left_actionable_urls },
        ]}
      />

      <QuickFilterBar title={t('opportunitiesCompare.quickFilters.title')} items={quickFilters} onReset={resetFilters} />

      <FilterPanel title={t('opportunitiesCompare.filters.title')} description={t('opportunitiesCompare.filters.description')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunitiesCompare.filters.dateRange')}</span>
          <select
            value={compareParams.gsc_date_range}
            onChange={(event) => updateParams({ gsc_date_range: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="last_28_days">{t('opportunitiesCompare.filters.last28Days')}</option>
            <option value="last_90_days">{t('opportunitiesCompare.filters.last90Days')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunitiesCompare.filters.changeKind')}</span>
          <select
            value={readSingleChangeKind(compareParams.change_kind ?? null)}
            onChange={(event) => updateParams({ change_kind: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            {CHANGE_KINDS.map((changeKind) => (
              <option key={changeKind} value={changeKind}>
                {t(`opportunitiesCompare.highlights.${changeKind}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunitiesCompare.filters.opportunityType')}</span>
          <select
            value={compareParams.opportunity_type ?? ''}
            onChange={(event) => updateParams({ opportunity_type: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            {OPPORTUNITY_TYPES.map((opportunityType) => (
              <option key={opportunityType} value={opportunityType}>
                {t(`opportunities.types.${opportunityType}.title`)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunitiesCompare.filters.urlContains')}</span>
          <input
            value={compareParams.url_contains ?? ''}
            onChange={(event) => updateParams({ url_contains: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder={t('opportunitiesCompare.filters.urlContainsPlaceholder')}
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunitiesCompare.filters.sortBy')}</span>
          <select
            value={compareParams.sort_by}
            onChange={(event) => updateParams({ sort_by: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="delta_priority_score">{t('opportunitiesCompare.filters.sort.priorityDelta')}</option>
            <option value="active_priority_score">{t('opportunitiesCompare.filters.sort.activePriority')}</option>
            <option value="active_opportunity_count">{t('opportunitiesCompare.filters.sort.activeOpportunityCount')}</option>
            <option value="change_type">{t('opportunitiesCompare.filters.sort.changeType')}</option>
            <option value="url">{t('opportunitiesCompare.filters.sort.url')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunitiesCompare.filters.sortOrder')}</span>
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
        <EmptyState title={t('opportunitiesCompare.emptyTitle')} description={t('opportunitiesCompare.emptyDescription')} />
      ) : (
        <>
          <DataTable
            columns={[
              {
                key: 'url',
                header: t('opportunitiesCompare.table.url'),
                sortKey: 'url',
                minWidth: 320,
                cell: (row) => (
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap gap-1.5">
                      {renderBadge(t(`pagesCompare.changeType.${row.change_type}`), changeTone(row.change_type))}
                      {row.highlights.map((highlight) => (
                        <span key={highlight}>{renderBadge(t(`opportunitiesCompare.highlights.${highlight}`), highlightTone(highlight))}</span>
                      ))}
                    </div>
                    <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.url}>{row.url}</p>
                    <UrlActions url={row.url} />
                    <div className="flex flex-wrap gap-2 text-xs font-medium text-teal-700">
                      <Link to={buildPagesComparePath(site.id, { activeCrawlId, baselineCrawlId }, row.url)}>
                        {t('opportunitiesCompare.table.openPagesCompare')}
                      </Link>
                      {activeCrawlId ? (
                        <Link to={`/jobs/${activeCrawlId}/pages?url_contains=${encodeURIComponent(row.url)}`}>
                          {t('opportunitiesCompare.table.openActivePages')}
                        </Link>
                      ) : null}
                    </div>
                  </div>
                ),
              },
              {
                key: 'priority',
                header: t('opportunitiesCompare.table.priority'),
                sortKey: 'delta_priority_score',
                minWidth: 220,
                cell: (row) => (
                  <div className="space-y-1 text-xs text-stone-600">
                    <p>{t('opportunitiesCompare.table.active')}: <span className="font-medium text-stone-900">{row.active_priority_score ?? '-'}</span></p>
                    <p>{t('opportunitiesCompare.table.baseline')}: <span className="font-medium text-stone-900">{row.baseline_priority_score ?? '-'}</span></p>
                    <p>{t('opportunitiesCompare.table.delta')}: <span className="font-medium text-stone-900">{formatSignedInteger(row.delta_priority_score)}</span></p>
                    <p>{t('opportunitiesCompare.table.activeLevel')}: <span className="font-medium text-stone-900">{row.active_priority_level ? t(`pages.priority.level.${row.active_priority_level}`) : '-'}</span></p>
                    <p>{t('opportunitiesCompare.table.baselineLevel')}: <span className="font-medium text-stone-900">{row.baseline_priority_level ? t(`pages.priority.level.${row.baseline_priority_level}`) : '-'}</span></p>
                  </div>
                ),
              },
              {
                key: 'types',
                header: t('opportunitiesCompare.table.opportunities'),
                minWidth: 280,
                cell: (row) => (
                  <div className="space-y-1 text-xs text-stone-600">
                    <p>{t('opportunitiesCompare.table.activeCount')}: <span className="font-medium text-stone-900">{row.active_opportunity_count}</span></p>
                    <p>{t('opportunitiesCompare.table.baselineCount')}: <span className="font-medium text-stone-900">{row.baseline_opportunity_count}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('opportunitiesCompare.table.newTypes')}: <span className="font-medium text-stone-900">{row.new_opportunity_types.length ? row.new_opportunity_types.map((type) => t(`opportunities.types.${type}.title`)).join(', ') : '-'}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('opportunitiesCompare.table.resolvedTypes')}: <span className="font-medium text-stone-900">{row.resolved_opportunity_types.length ? row.resolved_opportunity_types.map((type) => t(`opportunities.types.${type}.title`)).join(', ') : '-'}</span></p>
                  </div>
                ),
              },
              {
                key: 'rationale',
                header: t('opportunitiesCompare.table.rationale'),
                minWidth: 280,
                cell: (row) => (
                  <div className="space-y-1">
                    <p className="text-sm leading-5 text-stone-700 [overflow-wrap:anywhere]" title={row.change_rationale}>{row.change_rationale}</p>
                    <p className="text-xs text-stone-500">
                      {t('opportunitiesCompare.table.actionable')}: {row.entered_actionable ? t('opportunitiesCompare.actionable.entered') : row.left_actionable ? t('opportunitiesCompare.actionable.left') : t('opportunitiesCompare.actionable.steady')}
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
