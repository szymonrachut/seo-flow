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
  InternalLinkingCompareHighlight,
  InternalLinkingIssueType,
  SortOrder,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatCrawlDateTime, formatPercent } from '../../utils/format'
import {
  mergeSearchParams,
  parseCsvParam,
  parseIntegerParam,
  serializeCsvParam,
  toggleCsvParamValue,
} from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import { buildSiteChangesPagesPath, buildSiteInternalLinkingPath } from '../sites/routes'
import { type SiteInternalLinkingCompareQueryParams, useSiteInternalLinkingCompareQuery } from './api'

const ISSUE_TYPES: InternalLinkingIssueType[] = [
  'ORPHAN_LIKE',
  'WEAKLY_LINKED_IMPORTANT',
  'LOW_ANCHOR_DIVERSITY',
  'EXACT_MATCH_ANCHOR_CONCENTRATION',
  'BOILERPLATE_DOMINATED',
  'LOW_LINK_EQUITY',
]
const COMPARE_KINDS: InternalLinkingCompareHighlight[] = [
  'NEW_ORPHAN_LIKE',
  'RESOLVED_ORPHAN_LIKE',
  'WEAKLY_LINKED_IMPROVED',
  'WEAKLY_LINKED_WORSENED',
  'LINK_EQUITY_IMPROVED',
  'LINK_EQUITY_WORSENED',
  'LINKING_PAGES_UP',
  'LINKING_PAGES_DOWN',
  'ANCHOR_DIVERSITY_IMPROVED',
  'ANCHOR_DIVERSITY_WORSENED',
  'BOILERPLATE_IMPROVED',
  'BOILERPLATE_WORSENED',
]

function readSingleCompareKind(value: string | null) {
  const values = Array.from(parseCsvParam(value, COMPARE_KINDS))
  return values.length === 1 ? values[0] : ''
}

function readParams(
  searchParams: URLSearchParams,
  activeCrawlId?: number | null,
  baselineCrawlId?: number | null,
): SiteInternalLinkingCompareQueryParams {
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
      sortBy === 'delta_link_equity_score' ||
      sortBy === 'delta_incoming_follow_linking_pages' ||
      sortBy === 'delta_anchor_diversity_score' ||
      sortBy === 'delta_boilerplate_like_share'
        ? sortBy
        : 'delta_internal_linking_score',
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    change_type: searchParams.get('change_type') || undefined,
    compare_kind: searchParams.get('compare_kind') || undefined,
    issue_type: searchParams.get('issue_type') || undefined,
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

function highlightTone(highlight: InternalLinkingCompareHighlight): 'stone' | 'rose' | 'amber' | 'teal' {
  if (
    highlight === 'NEW_ORPHAN_LIKE' ||
    highlight === 'WEAKLY_LINKED_WORSENED' ||
    highlight === 'LINK_EQUITY_WORSENED' ||
    highlight === 'LINKING_PAGES_DOWN' ||
    highlight === 'ANCHOR_DIVERSITY_WORSENED' ||
    highlight === 'BOILERPLATE_WORSENED'
  ) {
    return 'rose'
  }
  return 'teal'
}

function formatSignedInteger(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  return value > 0 ? `+${value}` : String(value)
}

function formatSignedNumber(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined) {
    return '-'
  }
  const formatted = value.toFixed(digits)
  return value > 0 ? `+${formatted}` : formatted
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

export function SiteInternalLinkingComparePage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  useDocumentTitle(t('documentTitle.internalLinkingCompare', { domain: site.domain }))

  const [searchParams, setSearchParams] = useSearchParams()
  const compareParams = useMemo(
    () => readParams(searchParams, activeCrawlId, baselineCrawlId),
    [activeCrawlId, baselineCrawlId, searchParams],
  )
  const compareQuery = useSiteInternalLinkingCompareQuery(site.id, compareParams)
  const selectedCompareKinds = useMemo(() => parseCsvParam(searchParams.get('compare_kind'), COMPARE_KINDS), [searchParams])

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function toggleCompareKind(compareKind: InternalLinkingCompareHighlight) {
    const next = toggleCsvParamValue(selectedCompareKinds, compareKind)
    updateParams({ compare_kind: serializeCsvParam(next), page: 1 })
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: compareParams.gsc_date_range,
      page: 1,
      page_size: 25,
      sort_by: 'delta_internal_linking_score',
      sort_order: 'desc',
      change_type: undefined,
      compare_kind: undefined,
      issue_type: undefined,
      url_contains: undefined,
    })
  }

  const quickFilters = [
    { label: t('internalLinkingCompare.quickFilters.newOrphanLike'), isActive: selectedCompareKinds.has('NEW_ORPHAN_LIKE'), onClick: () => toggleCompareKind('NEW_ORPHAN_LIKE') },
    { label: t('internalLinkingCompare.quickFilters.resolvedOrphanLike'), isActive: selectedCompareKinds.has('RESOLVED_ORPHAN_LIKE'), onClick: () => toggleCompareKind('RESOLVED_ORPHAN_LIKE') },
    { label: t('internalLinkingCompare.quickFilters.weaklyLinkedImproved'), isActive: selectedCompareKinds.has('WEAKLY_LINKED_IMPROVED'), onClick: () => toggleCompareKind('WEAKLY_LINKED_IMPROVED') },
    { label: t('internalLinkingCompare.quickFilters.weaklyLinkedWorsened'), isActive: selectedCompareKinds.has('WEAKLY_LINKED_WORSENED'), onClick: () => toggleCompareKind('WEAKLY_LINKED_WORSENED') },
    { label: t('internalLinkingCompare.quickFilters.linkingPagesUp'), isActive: selectedCompareKinds.has('LINKING_PAGES_UP'), onClick: () => toggleCompareKind('LINKING_PAGES_UP') },
    { label: t('internalLinkingCompare.quickFilters.linkingPagesDown'), isActive: selectedCompareKinds.has('LINKING_PAGES_DOWN'), onClick: () => toggleCompareKind('LINKING_PAGES_DOWN') },
  ]

  if (compareQuery.isLoading) {
    return <LoadingState label={t('internalLinkingCompare.loading')} />
  }

  if (compareQuery.isError) {
    return <ErrorState title={t('internalLinkingCompare.errorTitle')} message={getUiErrorMessage(compareQuery.error, t)} />
  }

  const payload = compareQuery.data
  if (!payload) {
    return <EmptyState title={t('internalLinkingCompare.emptyTitle')} description={t('internalLinkingCompare.emptyDescription')} />
  }

  if (!payload.context.compare_available) {
    return (
      <EmptyState
        title={t('internalLinkingCompare.compareUnavailableTitle')}
        description={payload.context.compare_unavailable_reason ?? t('internalLinkingCompare.compareUnavailableDescription')}
      />
    )
  }

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('internalLinkingCompare.eyebrow')}
        title={t('internalLinkingCompare.title')}
        description={t('internalLinkingCompare.description', {
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
          key: 'open-current-state-internal-linking',
          label: t('internalLinkingCompare.actions.openCurrentState'),
          to: buildSiteInternalLinkingPath(site.id, { activeCrawlId, baselineCrawlId }),
        }}
        operations={
          activeCrawlId
            ? [
                {
                  key: 'open-active-crawl',
                  label: t('internalLinkingCompare.actions.openActiveCrawl'),
                  to: `/jobs/${activeCrawlId}`,
                },
              ]
            : []
        }
      />

      <SummaryCards
        items={[
          { label: t('internalLinkingCompare.summary.issueUrls'), value: payload.summary.issue_urls_in_active },
          { label: t('internalLinkingCompare.summary.newOrphanLike'), value: payload.summary.new_orphan_like_urls },
          { label: t('internalLinkingCompare.summary.resolvedOrphanLike'), value: payload.summary.resolved_orphan_like_urls },
          { label: t('internalLinkingCompare.summary.weaklyLinkedImproved'), value: payload.summary.weakly_linked_improved_urls },
          { label: t('internalLinkingCompare.summary.weaklyLinkedWorsened'), value: payload.summary.weakly_linked_worsened_urls },
          { label: t('internalLinkingCompare.summary.linkingPagesUp'), value: payload.summary.linking_pages_up_urls },
          { label: t('internalLinkingCompare.summary.anchorImproved'), value: payload.summary.anchor_diversity_improved_urls },
          { label: t('internalLinkingCompare.summary.boilerplateWorsened'), value: payload.summary.boilerplate_worsened_urls },
        ]}
      />

      <QuickFilterBar title={t('internalLinkingCompare.quickFilters.title')} items={quickFilters} onReset={resetFilters} />

      <FilterPanel title={t('internalLinkingCompare.filters.title')} description={t('internalLinkingCompare.filters.description')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinkingCompare.filters.dateRange')}</span>
          <select
            value={compareParams.gsc_date_range}
            onChange={(event) => updateParams({ gsc_date_range: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="last_28_days">{t('internalLinkingCompare.filters.last28Days')}</option>
            <option value="last_90_days">{t('internalLinkingCompare.filters.last90Days')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinkingCompare.filters.changeType')}</span>
          <select
            value={compareParams.change_type ?? ''}
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
          <span>{t('internalLinkingCompare.filters.compareKind')}</span>
          <select
            value={readSingleCompareKind(compareParams.compare_kind ?? null)}
            onChange={(event) => updateParams({ compare_kind: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            {COMPARE_KINDS.map((compareKind) => (
              <option key={compareKind} value={compareKind}>
                {t(`internalLinkingCompare.highlights.${compareKind}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinkingCompare.filters.issueType')}</span>
          <select
            value={compareParams.issue_type ?? ''}
            onChange={(event) => updateParams({ issue_type: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            {ISSUE_TYPES.map((issueType) => (
              <option key={issueType} value={issueType}>
                {t(`internalLinking.issueTypes.${issueType}.title`)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinkingCompare.filters.urlContains')}</span>
          <input
            value={compareParams.url_contains ?? ''}
            onChange={(event) => updateParams({ url_contains: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder={t('internalLinkingCompare.filters.urlContainsPlaceholder')}
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinkingCompare.filters.sortBy')}</span>
          <select
            value={compareParams.sort_by}
            onChange={(event) => updateParams({ sort_by: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="delta_internal_linking_score">{t('internalLinkingCompare.filters.sort.internalLinkingDelta')}</option>
            <option value="delta_link_equity_score">{t('internalLinkingCompare.filters.sort.linkEquityDelta')}</option>
            <option value="delta_incoming_follow_linking_pages">{t('internalLinkingCompare.filters.sort.linkingPagesDelta')}</option>
            <option value="delta_anchor_diversity_score">{t('internalLinkingCompare.filters.sort.anchorDiversityDelta')}</option>
            <option value="delta_boilerplate_like_share">{t('internalLinkingCompare.filters.sort.boilerplateDelta')}</option>
            <option value="change_type">{t('internalLinkingCompare.filters.sort.changeType')}</option>
            <option value="url">{t('internalLinkingCompare.filters.sort.url')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinkingCompare.filters.sortOrder')}</span>
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
        <EmptyState title={t('internalLinkingCompare.emptyTitle')} description={t('internalLinkingCompare.emptyDescription')} />
      ) : (
        <>
          <DataTable
            columns={[
              {
                key: 'url',
                header: t('internalLinkingCompare.table.url'),
                sortKey: 'url',
                minWidth: 320,
                cell: (row) => (
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap gap-1.5">
                      {renderBadge(t(`pagesCompare.changeType.${row.change_type}`), changeTone(row.change_type))}
                      {row.highlights.map((highlight) => (
                        <span key={highlight}>{renderBadge(t(`internalLinkingCompare.highlights.${highlight}`), highlightTone(highlight))}</span>
                      ))}
                    </div>
                    <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.url}>{row.url}</p>
                    <UrlActions url={row.url} />
                    <div className="flex flex-wrap gap-2 text-xs font-medium text-teal-700">
                      <Link to={buildPagesComparePath(site.id, { activeCrawlId, baselineCrawlId }, row.url)}>
                        {t('internalLinkingCompare.table.openPagesCompare')}
                      </Link>
                      {activeCrawlId ? (
                        <Link to={`/jobs/${activeCrawlId}/internal-linking?url_contains=${encodeURIComponent(row.url)}`}>
                          {t('internalLinkingCompare.table.openActiveInternalLinking')}
                        </Link>
                      ) : null}
                    </div>
                  </div>
                ),
              },
              {
                key: 'issues',
                header: t('internalLinkingCompare.table.issues'),
                minWidth: 280,
                cell: (row) => (
                  <div className="space-y-1 text-xs text-stone-600">
                    <p className="[overflow-wrap:anywhere]">{t('internalLinkingCompare.table.activeIssues')}: <span className="font-medium text-stone-900">{row.active_issue_types.length ? row.active_issue_types.map((issueType) => t(`internalLinking.issueTypes.${issueType}.title`)).join(', ') : '-'}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('internalLinkingCompare.table.baselineIssues')}: <span className="font-medium text-stone-900">{row.baseline_issue_types.length ? row.baseline_issue_types.map((issueType) => t(`internalLinking.issueTypes.${issueType}.title`)).join(', ') : '-'}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('internalLinkingCompare.table.newIssues')}: <span className="font-medium text-stone-900">{row.new_issue_types.length ? row.new_issue_types.map((issueType) => t(`internalLinking.issueTypes.${issueType}.title`)).join(', ') : '-'}</span></p>
                    <p className="[overflow-wrap:anywhere]">{t('internalLinkingCompare.table.resolvedIssues')}: <span className="font-medium text-stone-900">{row.resolved_issue_types.length ? row.resolved_issue_types.map((issueType) => t(`internalLinking.issueTypes.${issueType}.title`)).join(', ') : '-'}</span></p>
                  </div>
                ),
              },
              {
                key: 'delta',
                header: t('internalLinkingCompare.table.delta'),
                sortKey: 'delta_internal_linking_score',
                minWidth: 260,
                cell: (row) => (
                  <div className="space-y-1 text-xs text-stone-600">
                    <p>{t('internalLinkingCompare.table.internalLinkingDelta')}: <span className="font-medium text-stone-900">{formatSignedInteger(row.delta_internal_linking_score)}</span></p>
                    <p>{t('internalLinkingCompare.table.linkEquityDelta')}: <span className="font-medium text-stone-900">{formatSignedNumber(row.delta_link_equity_score)}</span></p>
                    <p>{t('internalLinkingCompare.table.linkingPagesDelta')}: <span className="font-medium text-stone-900">{formatSignedInteger(row.delta_incoming_follow_linking_pages)}</span></p>
                    <p>{t('internalLinkingCompare.table.anchorDelta')}: <span className="font-medium text-stone-900">{formatSignedNumber(row.delta_anchor_diversity_score)}</span></p>
                    <p>{t('internalLinkingCompare.table.boilerplateDelta')}: <span className="font-medium text-stone-900">{row.delta_boilerplate_like_share === null || row.delta_boilerplate_like_share === undefined ? '-' : formatPercent(row.delta_boilerplate_like_share)}</span></p>
                  </div>
                ),
              },
              {
                key: 'rationale',
                header: t('internalLinkingCompare.table.rationale'),
                minWidth: 280,
                cell: (row) => (
                  <div className="space-y-1">
                    <p className="text-sm leading-5 text-stone-700 [overflow-wrap:anywhere]" title={row.change_rationale}>{row.change_rationale}</p>
                    <p className="text-xs text-stone-500">
                      {t('internalLinkingCompare.table.currentBoilerplate')}: {row.active_boilerplate_like_share === null || row.active_boilerplate_like_share === undefined ? '-' : formatPercent(row.active_boilerplate_like_share)}
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
