import { startTransition, useMemo } from 'react'
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
  InternalLinkingIssueRow,
  InternalLinkingIssueType,
  InternalLinkingIssuesQueryParams,
  OpportunityType,
  PriorityLevel,
  SortOrder,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatNullable, formatPercent, formatPosition } from '../../utils/format'
import { mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
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

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }
  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
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

function readParams(searchParams: URLSearchParams): InternalLinkingIssuesQueryParams {
  const sortBy = searchParams.get('sort_by')
  const sortOrder = searchParams.get('sort_order')

  return {
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), 25),
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

function buildPagesLink(jobId: number, params: InternalLinkingIssuesQueryParams, url: string) {
  const query = new URLSearchParams()
  query.set('gsc_date_range', params.gsc_date_range)
  query.set('sort_by', 'priority_score')
  query.set('sort_order', 'desc')
  query.set('url_contains', url)
  return `/jobs/${jobId}/pages?${query.toString()}`
}

function buildOpportunitiesLink(jobId: number, params: InternalLinkingIssuesQueryParams, row: InternalLinkingIssueRow) {
  const query = new URLSearchParams()
  query.set('gsc_date_range', params.gsc_date_range)
  if (row.primary_opportunity_type) {
    query.set('opportunity_type', row.primary_opportunity_type)
  } else if (row.priority_level) {
    query.set('priority_level', row.priority_level)
  }
  return `/jobs/${jobId}/opportunities?${query.toString()}`
}

function buildExportHref(jobId: number, searchParams: URLSearchParams) {
  const query = new URLSearchParams(searchParams)
  query.delete('page')
  query.delete('page_size')
  const serialized = query.toString()
  return buildApiUrl(`/crawl-jobs/${jobId}/export/internal-linking.csv${serialized ? `?${serialized}` : ''}`)
}

function badgeTone(
  value: InternalLinkingIssueType | PriorityLevel,
): 'stone' | 'rose' | 'amber' | 'teal' {
  if (value === 'ORPHAN_LIKE' || value === 'LOW_LINK_EQUITY' || value === 'critical') {
    return 'rose'
  }
  if (value === 'WEAKLY_LINKED_IMPORTANT' || value === 'BOILERPLATE_DOMINATED' || value === 'high') {
    return 'amber'
  }
  if (value === 'LOW_ANCHOR_DIVERSITY' || value === 'EXACT_MATCH_ANCHOR_CONCENTRATION' || value === 'medium') {
    return 'teal'
  }
  return 'stone'
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

export function InternalLinkingPage() {
  const { t } = useTranslation()
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? t('documentTitle.internalLinking', { jobId }) : t('nav.internalLinking'))

  if (jobId === null) {
    return <ErrorState title={t('internalLinking.invalidIdTitle')} message={t('internalLinking.invalidIdMessage')} />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const internalLinkingParams = useMemo(() => readParams(searchParams), [searchParams])
  const overviewQuery = useInternalLinkingOverviewQuery(jobId, internalLinkingParams.gsc_date_range)
  const issuesQuery = useInternalLinkingIssuesQuery(jobId, internalLinkingParams)

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: internalLinkingParams.gsc_date_range,
      page: 1,
      page_size: 25,
      sort_by: 'internal_linking_score',
      sort_order: 'desc',
      issue_type: undefined,
      priority_level: undefined,
      opportunity_type: undefined,
      url_contains: undefined,
    })
  }

  const quickFilters = [
    { label: t('internalLinking.quickFilters.orphanLike'), isActive: internalLinkingParams.issue_type === 'ORPHAN_LIKE', onClick: () => updateParams({ issue_type: 'ORPHAN_LIKE', page: 1 }) },
    { label: t('internalLinking.quickFilters.weaklyLinkedImportant'), isActive: internalLinkingParams.issue_type === 'WEAKLY_LINKED_IMPORTANT', onClick: () => updateParams({ issue_type: 'WEAKLY_LINKED_IMPORTANT', page: 1 }) },
    { label: t('internalLinking.quickFilters.anchorDiversity'), isActive: internalLinkingParams.issue_type === 'LOW_ANCHOR_DIVERSITY', onClick: () => updateParams({ issue_type: 'LOW_ANCHOR_DIVERSITY', page: 1 }) },
    { label: t('internalLinking.quickFilters.exactMatch'), isActive: internalLinkingParams.issue_type === 'EXACT_MATCH_ANCHOR_CONCENTRATION', onClick: () => updateParams({ issue_type: 'EXACT_MATCH_ANCHOR_CONCENTRATION', page: 1 }) },
    { label: t('internalLinking.quickFilters.boilerplateDominated'), isActive: internalLinkingParams.issue_type === 'BOILERPLATE_DOMINATED', onClick: () => updateParams({ issue_type: 'BOILERPLATE_DOMINATED', page: 1 }) },
    { label: t('internalLinking.quickFilters.lowLinkEquity'), isActive: internalLinkingParams.issue_type === 'LOW_LINK_EQUITY', onClick: () => updateParams({ issue_type: 'LOW_LINK_EQUITY', page: 1 }) },
  ]

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('internalLinking.page.eyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">
              {t('internalLinking.page.title', { jobId })}
            </h1>
            <p className="mt-2 text-sm text-stone-600">{t('internalLinking.page.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <JobNavigation jobId={jobId} />
            <a
              href={buildExportHref(jobId, searchParams)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('internalLinking.page.export')}
            </a>
          </div>
        </div>
      </section>

      <QuickFilterBar title={t('internalLinking.quickFilters.title')} items={quickFilters} />

      <FilterPanel title={t('internalLinking.filters.title')} description={t('internalLinking.filters.description')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.dateRange')}</span>
          <select
            value={internalLinkingParams.gsc_date_range}
            onChange={(event) => updateParams({ gsc_date_range: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="last_28_days">{t('internalLinking.filters.last28Days')}</option>
            <option value="last_90_days">{t('internalLinking.filters.last90Days')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.issueType')}</span>
          <select
            value={internalLinkingParams.issue_type ?? ''}
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
          <span>{t('internalLinking.filters.priorityLevel')}</span>
          <select
            value={internalLinkingParams.priority_level ?? ''}
            onChange={(event) => updateParams({ priority_level: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            {PRIORITY_LEVELS.map((priorityLevel) => (
              <option key={priorityLevel} value={priorityLevel}>
                {t(`pages.priority.level.${priorityLevel}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.opportunityType')}</span>
          <select
            value={internalLinkingParams.opportunity_type ?? ''}
            onChange={(event) => updateParams({ opportunity_type: event.target.value || undefined, page: 1 })}
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
          <span>{t('internalLinking.filters.urlContains')}</span>
          <input
            value={internalLinkingParams.url_contains ?? ''}
            onChange={(event) => updateParams({ url_contains: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder={t('internalLinking.filters.urlContainsPlaceholder')}
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.sortBy')}</span>
          <select
            value={internalLinkingParams.sort_by}
            onChange={(event) => updateParams({ sort_by: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
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
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('internalLinking.filters.sortOrder')}</span>
          <select
            value={internalLinkingParams.sort_order}
            onChange={(event) => updateParams({ sort_order: event.target.value, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="desc">{t('sort.descending')}</option>
            <option value="asc">{t('sort.ascending')}</option>
          </select>
        </label>
      </FilterPanel>

      {overviewQuery.isLoading ? <LoadingState label={t('internalLinking.page.loadingOverview')} /> : null}
      {overviewQuery.isError ? (
        <ErrorState title={t('internalLinking.errors.overviewTitle')} message={getUiErrorMessage(overviewQuery.error, t)} />
      ) : null}
      {overviewQuery.data ? (
        <SummaryCards
          items={[
            { label: t('internalLinking.summary.issuePages'), value: overviewQuery.data.issue_pages },
            { label: t('internalLinking.summary.orphanLike'), value: overviewQuery.data.orphan_like_pages },
            { label: t('internalLinking.summary.weaklyLinkedImportant'), value: overviewQuery.data.weakly_linked_important_pages },
            { label: t('internalLinking.summary.anchorDiversity'), value: overviewQuery.data.low_anchor_diversity_pages },
            { label: t('internalLinking.summary.exactMatch'), value: overviewQuery.data.exact_match_anchor_concentration_pages },
            { label: t('internalLinking.summary.boilerplateDominated'), value: overviewQuery.data.boilerplate_dominated_pages },
            { label: t('internalLinking.summary.lowLinkEquity'), value: overviewQuery.data.low_link_equity_pages },
            { label: t('internalLinking.summary.medianLinkEquity'), value: overviewQuery.data.median_link_equity_score.toFixed(1) },
          ]}
        />
      ) : null}

      {issuesQuery.isLoading ? <LoadingState label={t('internalLinking.page.loadingIssues')} /> : null}
      {issuesQuery.isError ? (
        <ErrorState title={t('internalLinking.errors.issuesTitle')} message={getUiErrorMessage(issuesQuery.error, t)} />
      ) : null}
      {issuesQuery.isSuccess && issuesQuery.data.items.length === 0 ? (
        <EmptyState title={t('internalLinking.empty.title')} description={t('internalLinking.empty.description')} />
      ) : null}
      {issuesQuery.isSuccess && issuesQuery.data.items.length > 0 ? (
        <>
          <DataTable
            columns={[
              {
                key: 'url',
                header: t('internalLinking.table.url'),
                sortKey: 'url',
                cell: (row) => (
                  <div className="max-w-[22rem] space-y-1.5">
                    <div className="flex flex-wrap gap-1.5">
                      {row.issue_types.map((issueType) => (
                        <span key={issueType}>{renderBadge(t(`internalLinking.issueTypes.${issueType}.title`), badgeTone(issueType))}</span>
                      ))}
                    </div>
                    <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.url}>{row.url}</p>
                    <UrlActions url={row.url} />
                    <div className="flex flex-wrap gap-2 text-xs font-medium text-teal-700">
                      <Link to={buildPagesLink(jobId, internalLinkingParams, row.url)}>{t('internalLinking.common.openPages')}</Link>
                      <Link to={buildOpportunitiesLink(jobId, internalLinkingParams, row)}>{t('internalLinking.common.openOpportunities')}</Link>
                    </div>
                  </div>
                ),
              },
              {
                key: 'importance',
                header: t('internalLinking.table.importance'),
                sortKey: 'priority_score',
                cell: (row) => (
                  <div className="min-w-[12rem] space-y-1 text-xs text-stone-600">
                    <p className="font-medium text-stone-900">
                      {row.priority_score} / {t(`pages.priority.level.${row.priority_level}`)}
                    </p>
                    <p>{t('opportunities.metrics.clicks')}: {formatNullable(row.clicks)}</p>
                    <p>{t('opportunities.metrics.impressions')}: {formatNullable(row.impressions)}</p>
                    <p>{t('opportunities.metrics.position')}: {formatPosition(row.position)}</p>
                    {row.primary_opportunity_type ? <p>{t(`opportunities.types.${row.primary_opportunity_type}.title`)}</p> : null}
                  </div>
                ),
              },
              {
                key: 'support',
                header: t('internalLinking.table.internalSupport'),
                sortKey: 'incoming_follow_links',
                cell: (row) => (
                  <div className="min-w-[13rem] space-y-1 text-xs text-stone-600">
                    <p>{t('internalLinking.metrics.followLinks')}: {row.incoming_follow_links} / {row.incoming_follow_linking_pages}</p>
                    <p>{t('internalLinking.metrics.bodyLike')}: {row.body_like_links} / {row.body_like_linking_pages} ({formatPercent(row.body_like_share)})</p>
                    <p>{t('internalLinking.metrics.boilerplateLike')}: {row.boilerplate_like_links} / {row.boilerplate_like_linking_pages} ({formatPercent(row.boilerplate_like_share)})</p>
                    <p>{t('internalLinking.metrics.nofollow')}: {row.incoming_nofollow_links}</p>
                    <p>{t('internalLinking.metrics.linkEquity')}: {row.link_equity_score.toFixed(1)} / #{row.link_equity_rank}</p>
                  </div>
                ),
              },
              {
                key: 'anchors',
                header: t('internalLinking.table.anchors'),
                sortKey: 'anchor_diversity_score',
                cell: (row) => (
                  <div className="min-w-[15rem] space-y-1 text-xs text-stone-600">
                    <p>{t('internalLinking.metrics.anchorDiversity')}: {row.anchor_diversity_score.toFixed(1)}</p>
                    <p>{t('internalLinking.metrics.uniqueAnchors')}: {row.unique_anchor_count}</p>
                    <p>{t('internalLinking.metrics.exactMatchRatio')}: {formatPercent(row.exact_match_anchor_ratio)}</p>
                    {row.top_anchor_samples.map((sample) => (
                      <p key={`${sample.anchor_text}-${sample.links}`} className="[overflow-wrap:anywhere]" title={sample.anchor_text}>
                        {sample.anchor_text || '-'} | {sample.links}
                      </p>
                    ))}
                  </div>
                ),
              },
              {
                key: 'rationale',
                header: t('internalLinking.table.rationale'),
                cell: (row) => (
                  <div className="max-w-[22rem] space-y-1">
                    <p className="text-sm leading-5 text-stone-700 [overflow-wrap:anywhere]" title={row.rationale}>{row.rationale}</p>
                    <p className="text-xs text-stone-500 [overflow-wrap:anywhere]" title={row.priority_rationale}>{row.priority_rationale}</p>
                  </div>
                ),
              },
            ]}
            rows={issuesQuery.data.items}
            rowKey={(row) => row.page_id}
            sortBy={internalLinkingParams.sort_by}
            sortOrder={internalLinkingParams.sort_order as SortOrder}
            onSortChange={(sortBy, sortOrder) => updateParams({ sort_by: sortBy, sort_order: sortOrder, page: 1 })}
          />
          <PaginationControls
            page={issuesQuery.data.page}
            pageSize={issuesQuery.data.page_size}
            totalItems={issuesQuery.data.total_items}
            totalPages={issuesQuery.data.total_pages}
            onPageChange={(page) => updateParams({ page })}
            onPageSizeChange={(pageSize) => updateParams({ page_size: pageSize, page: 1 })}
          />
        </>
      ) : null}
    </div>
  )
}
