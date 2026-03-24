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
  InternalLinkingIssueRow,
  InternalLinkingIssueType,
  InternalLinkingIssuesQueryParams,
  OpportunityType,
  PriorityLevel,
  SortOrder,
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
  buildSiteChangesInternalLinkingPath,
  buildSiteInternalLinkingIssuesPath,
  buildSiteInternalLinkingPath,
} from '../sites/routes'
import { useInternalLinkingIssuesQuery, useInternalLinkingOverviewQuery } from './api'

const ISSUE_TYPES: InternalLinkingIssueType[] = [
  'ORPHAN_LIKE',
  'WEAKLY_LINKED_IMPORTANT',
  'LOW_ANCHOR_DIVERSITY',
  'EXACT_MATCH_ANCHOR_CONCENTRATION',
  'BOILERPLATE_DOMINATED',
  'LOW_LINK_EQUITY',
]

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

type SiteInternalLinkingMode = 'overview' | 'issues'

interface SiteInternalLinkingCurrentPageProps {
  mode?: SiteInternalLinkingMode
}

function readIssueType(searchParams: URLSearchParams): InternalLinkingIssueType | undefined {
  const value = searchParams.get('issue_type')
  return ISSUE_TYPES.includes(value as InternalLinkingIssueType) ? (value as InternalLinkingIssueType) : undefined
}

function readPriorityLevel(searchParams: URLSearchParams): PriorityLevel | undefined {
  const value = searchParams.get('priority_level')
  return PRIORITY_LEVELS.includes(value as PriorityLevel) ? (value as PriorityLevel) : undefined
}

function readOpportunityType(searchParams: URLSearchParams): OpportunityType | undefined {
  const value = searchParams.get('opportunity_type')
  return OPPORTUNITY_TYPES.includes(value as OpportunityType) ? (value as OpportunityType) : undefined
}

function readParams(searchParams: URLSearchParams, mode: SiteInternalLinkingMode): InternalLinkingIssuesQueryParams {
  const sortBy = searchParams.get('sort_by')
  const sortOrder = searchParams.get('sort_order')

  return {
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), mode === 'issues' ? 25 : 8),
    sort_by:
      sortBy === 'url' ||
      sortBy === 'priority_score' ||
      sortBy === 'link_equity_score' ||
      sortBy === 'link_equity_rank' ||
      sortBy === 'incoming_follow_links' ||
      sortBy === 'incoming_follow_linking_pages' ||
      sortBy === 'body_like_share' ||
      sortBy === 'boilerplate_like_share' ||
      sortBy === 'anchor_diversity_score' ||
      sortBy === 'exact_match_anchor_ratio' ||
      sortBy === 'issue_count'
        ? sortBy
        : 'internal_linking_score',
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    issue_type: readIssueType(searchParams),
    priority_level: readPriorityLevel(searchParams),
    opportunity_type: readOpportunityType(searchParams),
    url_contains: searchParams.get('url_contains') || undefined,
  }
}

function readQuickFilters(searchParams: URLSearchParams) {
  return parseCsvParam(searchParams.get('quick_issue_filters'), ISSUE_TYPES)
}

function serializeQuickFilters(filters: Set<InternalLinkingIssueType>) {
  return serializeCsvParam(filters)
}

function buildExportHref(jobId: number, searchParams: URLSearchParams) {
  const query = new URLSearchParams(searchParams)
  query.delete('page')
  query.delete('page_size')
  query.delete('quick_issue_filters')
  const serialized = query.toString()
  return buildApiUrl(`/crawl-jobs/${jobId}/export/internal-linking.csv${serialized ? `?${serialized}` : ''}`)
}

function applyQuickFilters(rows: InternalLinkingIssueRow[], quickFilters: Set<InternalLinkingIssueType>) {
  if (quickFilters.size === 0) {
    return rows
  }

  return rows.filter((row) => row.issue_types.some((issueType) => quickFilters.has(issueType)))
}

function issueTone(issueType: InternalLinkingIssueType): string {
  if (issueType === 'ORPHAN_LIKE' || issueType === 'LOW_LINK_EQUITY') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (issueType === 'WEAKLY_LINKED_IMPORTANT' || issueType === 'BOILERPLATE_DOMINATED') return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-teal-200 bg-teal-50 text-teal-700'
}

export function SiteInternalLinkingCurrentPage({ mode = 'overview' }: SiteInternalLinkingCurrentPageProps) {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedIssueId, setSelectedIssueId] = useState<number | null>(null)

  useDocumentTitle(
    mode === 'overview'
      ? t('documentTitle.siteInternalLinking', { domain: site.domain })
      : t('documentTitle.siteInternalLinkingIssues', { domain: site.domain }),
  )

  const params = useMemo(() => readParams(searchParams, mode), [mode, searchParams])
  const quickFilters = useMemo(() => readQuickFilters(searchParams), [searchParams])
  const overviewQuery = useInternalLinkingOverviewQuery(activeCrawlId ?? -1, params.gsc_date_range, Boolean(activeCrawlId))
  const issuesQuery = useInternalLinkingIssuesQuery(activeCrawlId ?? -1, params, Boolean(activeCrawlId))
  const routeContext = { activeCrawlId, baselineCrawlId }

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: 'last_28_days',
      page: 1,
      page_size: mode === 'issues' ? 25 : 8,
      sort_by: 'internal_linking_score',
      sort_order: 'desc',
      issue_type: undefined,
      priority_level: undefined,
      opportunity_type: undefined,
      url_contains: undefined,
      quick_issue_filters: undefined,
    })
  }

  function toggleQuickFilter(filter: InternalLinkingIssueType) {
    const nextFilters = toggleCsvParamValue(quickFilters, filter)
    updateParams({ quick_issue_filters: serializeQuickFilters(nextFilters), page: 1 })
  }

  const visibleRows = applyQuickFilters(issuesQuery.data?.items ?? [], quickFilters)

  useEffect(() => {
    if (selectedIssueId && visibleRows.some((row) => row.page_id === selectedIssueId)) return
    setSelectedIssueId(visibleRows[0]?.page_id ?? null)
  }, [selectedIssueId, visibleRows])

  if (!activeCrawlId || !site.active_crawl) {
    return <EmptyState title={t('siteInternalLinking.noActiveCrawlTitle')} description={t('siteInternalLinking.noActiveCrawlDescription')} />
  }

  if (overviewQuery.isLoading || issuesQuery.isLoading) {
    return <LoadingState label={t('siteInternalLinking.loading')} />
  }

  if (overviewQuery.isError) {
    return <ErrorState title={t('siteInternalLinking.errorTitle')} message={getUiErrorMessage(overviewQuery.error, t)} />
  }

  if (issuesQuery.isError) {
    return <ErrorState title={t('siteInternalLinking.errorTitle')} message={getUiErrorMessage(issuesQuery.error, t)} />
  }

  const overview = overviewQuery.data
  const issues = issuesQuery.data
  if (!overview || !issues) {
    return <EmptyState title={t('siteInternalLinking.emptyTitle')} description={t('siteInternalLinking.emptyDescription')} />
  }

  const selectedIssue = visibleRows.find((row) => row.page_id === selectedIssueId) ?? visibleRows[0] ?? null
  const overviewPath = buildSiteInternalLinkingPath(site.id, routeContext)
  const issuesPath = buildSiteInternalLinkingIssuesPath(site.id, routeContext)
  const changesPath = buildSiteChangesInternalLinkingPath(site.id, routeContext)
  const exportHref = buildExportHref(activeCrawlId, searchParams)

  const quickFilterItems = ISSUE_TYPES.map((issueType) => ({
    label: t(`internalLinking.issueTypes.${issueType}.title`),
    isActive: quickFilters.has(issueType),
    onClick: () => toggleQuickFilter(issueType),
  }))

  const columns = [
    {
      key: 'url',
      header: t('internalLinking.table.url'),
      minWidth: 320,
      cell: (row: InternalLinkingIssueRow) => (
        <div className="space-y-1.5">
          <div className="flex flex-wrap gap-1.5">
            {row.issue_types.map((issueType) => (
              <span key={`${row.page_id}-${issueType}`} className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${issueTone(issueType)}`}>
                {t(`internalLinking.issueTypes.${issueType}.title`)}
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
      header: t('internalLinking.table.importance'),
      minWidth: 180,
      cell: (row: InternalLinkingIssueRow) => (
        <div className="space-y-1 text-xs text-stone-600">
          <p className="font-medium text-stone-900">{row.priority_score} / {t(`pages.priority.level.${row.priority_level}`)}</p>
          <p>{t('opportunities.metrics.clicks')}: {formatNullable(row.clicks)}</p>
          <p>{t('opportunities.metrics.impressions')}: {formatNullable(row.impressions)}</p>
          <p>{t('opportunities.metrics.position')}: {formatPosition(row.position)}</p>
        </div>
      ),
    },
    {
      key: 'support',
      header: t('internalLinking.table.internalSupport'),
      minWidth: 220,
      cell: (row: InternalLinkingIssueRow) => (
        <div className="space-y-1 text-xs text-stone-600">
          <p>{t('internalLinking.metrics.followLinks')}: {row.incoming_follow_links} / {row.incoming_follow_linking_pages}</p>
          <p>{t('internalLinking.metrics.linkEquity')}: {row.link_equity_score.toFixed(1)} / #{row.link_equity_rank}</p>
          <p>{t('internalLinking.metrics.bodyLike')}: {formatPercent(row.body_like_share)}</p>
          <p>{t('internalLinking.metrics.boilerplateLike')}: {formatPercent(row.boilerplate_like_share)}</p>
        </div>
      ),
    },
    {
      key: 'inspect',
      header: t('common.open'),
      minWidth: 120,
      cell: (row: InternalLinkingIssueRow) => (
        <button type="button" onClick={() => setSelectedIssueId(row.page_id)} className="rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100">
          {t('siteInternalLinking.inspectIssue')}
        </button>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('nav.internalLinking')}
        title={mode === 'overview' ? t('siteInternalLinking.title') : t('siteInternalLinking.issuesTitle')}
        description={mode === 'overview' ? t('siteInternalLinking.description') : t('siteInternalLinking.issuesDescription')}
        contextChips={[
          { label: 'Active', value: site.active_crawl ? formatCrawlDateTime(site.active_crawl) : '-' },
        ]}
        primaryAction={{
          key: mode === 'overview' ? 'open-issues' : 'open-overview',
          label: mode === 'overview' ? t('siteInternalLinking.openIssues') : t('siteInternalLinking.openOverview'),
          to: mode === 'overview' ? issuesPath : overviewPath,
        }}
        operations={[
          {
            key: 'open-changes',
            label: t('siteInternalLinking.openChanges'),
            to: changesPath,
          },
          {
            key: 'open-active-crawl',
            label: t('siteInternalLinking.openActiveCrawl'),
            to: `/jobs/${activeCrawlId}`,
          },
        ]}
        exports={[
          {
            key: 'export-internal-linking',
            label: t('siteInternalLinking.export'),
            href: exportHref,
          },
        ]}
      />

      <SummaryCards
        items={[
          { label: t('internalLinking.summary.issuePages'), value: overview.issue_pages },
          { label: t('internalLinking.summary.orphanLike'), value: overview.orphan_like_pages },
          { label: t('internalLinking.summary.weaklyLinkedImportant'), value: overview.weakly_linked_important_pages },
          { label: t('internalLinking.summary.lowLinkEquity'), value: overview.low_link_equity_pages },
          { label: t('siteInternalLinking.visibleIssues'), value: visibleRows.length },
          { label: t('internalLinking.summary.medianLinkEquity'), value: overview.median_link_equity_score.toFixed(1) },
        ]}
      />

      <QuickFilterBar title={t('siteInternalLinking.quickFiltersTitle')} items={quickFilterItems} onReset={() => updateParams({ quick_issue_filters: undefined, page: 1 })} />

      <FilterPanel title={t('internalLinking.filters.title')} description={t('siteInternalLinking.filtersDescription')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.dateRange')}</span>
          <select value={params.gsc_date_range} onChange={(event) => updateParams({ gsc_date_range: event.target.value, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="last_28_days">{t('internalLinking.filters.last28Days')}</option>
            <option value="last_90_days">{t('internalLinking.filters.last90Days')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.issueType')}</span>
          <select value={params.issue_type ?? ''} onChange={(event) => updateParams({ issue_type: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {ISSUE_TYPES.map((issueType) => <option key={issueType} value={issueType}>{t(`internalLinking.issueTypes.${issueType}.title`)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.priorityLevel')}</span>
          <select value={params.priority_level ?? ''} onChange={(event) => updateParams({ priority_level: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {PRIORITY_LEVELS.map((priorityLevel) => <option key={priorityLevel} value={priorityLevel}>{t(`pages.priority.level.${priorityLevel}`)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.opportunityType')}</span>
          <select value={params.opportunity_type ?? ''} onChange={(event) => updateParams({ opportunity_type: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {OPPORTUNITY_TYPES.map((type) => <option key={type} value={type}>{t(`opportunities.types.${type}.title`)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.urlContains')}</span>
          <input value={params.url_contains ?? ''} onChange={(event) => updateParams({ url_contains: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" placeholder={t('internalLinking.filters.urlContainsPlaceholder')} />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.sortBy')}</span>
          <select value={params.sort_by} onChange={(event) => updateParams({ sort_by: event.target.value, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="internal_linking_score">{t('internalLinking.filters.sort.internalLinkingScore')}</option>
            <option value="priority_score">{t('internalLinking.filters.sort.priorityScore')}</option>
            <option value="link_equity_score">{t('internalLinking.filters.sort.linkEquity')}</option>
            <option value="incoming_follow_links">{t('internalLinking.filters.sort.followLinks')}</option>
            <option value="anchor_diversity_score">{t('internalLinking.filters.sort.anchorDiversity')}</option>
            <option value="exact_match_anchor_ratio">{t('internalLinking.filters.sort.exactMatchRatio')}</option>
            <option value="issue_count">{t('internalLinking.filters.sort.issueCount')}</option>
            <option value="url">{t('internalLinking.filters.sort.url')}</option>
          </select>
        </label>
      </FilterPanel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-stone-950">{mode === 'overview' ? t('siteInternalLinking.previewTitle') : t('siteInternalLinking.issuesTableTitle')}</h2>
                <p className="mt-1 text-sm text-stone-600">{mode === 'overview' ? t('siteInternalLinking.previewDescription') : t('siteInternalLinking.issuesTableDescription')}</p>
              </div>
              <Link to={mode === 'overview' ? issuesPath : overviewPath} className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100">
                {mode === 'overview' ? t('siteInternalLinking.openIssues') : t('siteInternalLinking.openOverview')}
              </Link>
            </div>
            <div className="mt-4">
              {visibleRows.length === 0 ? (
                <EmptyState title={t('siteInternalLinking.emptyTitle')} description={t('siteInternalLinking.emptyDescription')} />
              ) : (
                <>
                  <DataTable columns={columns} rows={mode === 'overview' ? visibleRows.slice(0, 8) : visibleRows} rowKey={(row) => row.page_id} sortBy={params.sort_by} sortOrder={params.sort_order as SortOrder} onSortChange={(sortBy, sortOrder) => updateParams({ sort_by: sortBy, sort_order: sortOrder, page: 1 })} />
                  {mode === 'issues' ? (
                    <div className="mt-4">
                      <PaginationControls page={issues.page} pageSize={issues.page_size} totalItems={issues.total_items} totalPages={issues.total_pages} onPageChange={(nextPage) => updateParams({ page: nextPage })} onPageSizeChange={(nextPageSize) => updateParams({ page_size: nextPageSize, page: 1 })} />
                    </div>
                  ) : null}
                </>
              )}
            </div>
          </section>
        </div>

        <aside className="rounded-[28px] border border-stone-300 bg-white/90 p-5 shadow-sm">
          <p className="text-xs uppercase tracking-[0.18em] text-teal-700">{t('siteInternalLinking.detailsTitle')}</p>
          {selectedIssue ? (
            <div className="mt-3 space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-stone-950 [overflow-wrap:anywhere]" title={selectedIssue.url}>{selectedIssue.url}</h2>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {selectedIssue.issue_types.map((issueType) => (
                    <span key={`${selectedIssue.page_id}-${issueType}-badge`} className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${issueTone(issueType)}`}>
                      {t(`internalLinking.issueTypes.${issueType}.title`)}
                    </span>
                  ))}
                </div>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-3 text-sm text-stone-700">
                <p>{t('opportunities.metrics.clicks')}: {formatNullable(selectedIssue.clicks)}</p>
                <p>{t('opportunities.metrics.impressions')}: {formatNullable(selectedIssue.impressions)}</p>
                <p>{t('opportunities.metrics.position')}: {formatPosition(selectedIssue.position)}</p>
                <p>{t('internalLinking.metrics.followLinks')}: {selectedIssue.incoming_follow_links} / {selectedIssue.incoming_follow_linking_pages}</p>
                <p>{t('internalLinking.metrics.linkEquity')}: {selectedIssue.link_equity_score.toFixed(1)} / #{selectedIssue.link_equity_rank}</p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-3 text-sm leading-6 text-stone-700 [overflow-wrap:anywhere]">
                {selectedIssue.rationale}
              </div>
              <div className="flex flex-wrap gap-2">
                <Link to={`/jobs/${activeCrawlId}/internal-linking?url_contains=${encodeURIComponent(selectedIssue.url)}`} className="rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100">
                  {t('siteInternalLinking.openInActiveSnapshot')}
                </Link>
                <UrlActions url={selectedIssue.url} />
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-stone-600">{t('siteInternalLinking.detailsEmpty')}</p>
          )}
        </aside>
      </div>
    </div>
  )
}
