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
  CannibalizationCluster,
  CannibalizationClustersQueryParams,
  CannibalizationPageDetails,
  CannibalizationRecommendationType,
  CannibalizationSeverity,
  ImpactLevel,
  SortOrder,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatNullable, formatPercent, formatPosition } from '../../utils/format'
import { mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
import { useCannibalizationClustersQuery, useCannibalizationPageDetailsQuery } from './api'

const SEVERITIES: CannibalizationSeverity[] = ['critical', 'high', 'medium', 'low']
const IMPACT_LEVELS: ImpactLevel[] = ['high', 'medium', 'low']
const RECOMMENDATION_TYPES: CannibalizationRecommendationType[] = [
  'HIGH_IMPACT_CANNIBALIZATION',
  'MERGE_CANDIDATE',
  'SPLIT_INTENT_CANDIDATE',
  'REINFORCE_PRIMARY_URL',
  'QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY',
  'LOW_VALUE_OVERLAP',
]

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }
  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

function readSeverity(searchParams: URLSearchParams): CannibalizationSeverity | undefined {
  const value = searchParams.get('severity')
  return SEVERITIES.includes(value as CannibalizationSeverity) ? (value as CannibalizationSeverity) : undefined
}

function readImpactLevel(searchParams: URLSearchParams): ImpactLevel | undefined {
  const value = searchParams.get('impact_level')
  return IMPACT_LEVELS.includes(value as ImpactLevel) ? (value as ImpactLevel) : undefined
}

function readRecommendationType(searchParams: URLSearchParams): CannibalizationRecommendationType | undefined {
  const value = searchParams.get('recommendation_type')
  return RECOMMENDATION_TYPES.includes(value as CannibalizationRecommendationType)
    ? (value as CannibalizationRecommendationType)
    : undefined
}

function readHasClearPrimary(searchParams: URLSearchParams): boolean | undefined {
  const value = searchParams.get('has_clear_primary')
  if (value === 'true') {
    return true
  }
  if (value === 'false') {
    return false
  }
  return undefined
}

function readPageId(searchParams: URLSearchParams): number | null {
  const parsed = parseIntegerParam(searchParams.get('page_id'), undefined)
  return typeof parsed === 'number' ? parsed : null
}

function readParams(searchParams: URLSearchParams): CannibalizationClustersQueryParams {
  const sortBy = searchParams.get('sort_by')
  const sortOrder = searchParams.get('sort_order')

  return {
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), 25),
    sort_by:
      sortBy === 'impact_level' ||
      sortBy === 'weighted_overlap' ||
      sortBy === 'shared_queries_count' ||
      sortBy === 'shared_query_impressions' ||
      sortBy === 'shared_query_clicks' ||
      sortBy === 'urls_count' ||
      sortBy === 'dominant_url_confidence' ||
      sortBy === 'recommendation_type' ||
      sortBy === 'cluster_id'
        ? sortBy
        : 'severity',
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    severity: readSeverity(searchParams),
    impact_level: readImpactLevel(searchParams),
    recommendation_type: readRecommendationType(searchParams),
    has_clear_primary: readHasClearPrimary(searchParams),
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

function getSeverityTone(value: CannibalizationSeverity): 'stone' | 'rose' | 'amber' | 'teal' {
  if (value === 'critical') {
    return 'rose'
  }
  if (value === 'high') {
    return 'amber'
  }
  if (value === 'medium') {
    return 'teal'
  }
  return 'stone'
}

function getRecommendationTone(value: CannibalizationRecommendationType): 'stone' | 'rose' | 'amber' | 'teal' {
  if (value === 'HIGH_IMPACT_CANNIBALIZATION') {
    return 'rose'
  }
  if (value === 'MERGE_CANDIDATE' || value === 'REINFORCE_PRIMARY_URL') {
    return 'amber'
  }
  if (value === 'SPLIT_INTENT_CANDIDATE' || value === 'QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY') {
    return 'teal'
  }
  return 'stone'
}

function buildPagesLink(jobId: number, gscDateRange: CannibalizationClustersQueryParams['gsc_date_range'], url: string) {
  const query = new URLSearchParams()
  query.set('gsc_date_range', gscDateRange)
  query.set('url_contains', url)
  return `/jobs/${jobId}/pages?${query.toString()}`
}

function buildDetailLink(jobId: number, gscDateRange: CannibalizationClustersQueryParams['gsc_date_range'], pageId: number) {
  const query = new URLSearchParams()
  query.set('gsc_date_range', gscDateRange)
  query.set('page_id', String(pageId))
  return `/jobs/${jobId}/cannibalization?${query.toString()}`
}

function buildExportHref(jobId: number, searchParams: URLSearchParams) {
  const query = new URLSearchParams(searchParams)
  query.delete('page')
  query.delete('page_size')
  query.delete('page_id')
  const serialized = query.toString()
  return buildApiUrl(`/crawl-jobs/${jobId}/export/cannibalization.csv${serialized ? `?${serialized}` : ''}`)
}

function formatQueryList(values: string[]) {
  if (values.length === 0) {
    return ' - '
  }
  return values.join(' | ')
}

function ClusterUrlsCell({
  cluster,
  jobId,
  params,
  onInspect,
}: {
  cluster: CannibalizationCluster
  jobId: number
  params: CannibalizationClustersQueryParams
  onInspect: (pageId: number) => void
}) {
  const { t } = useTranslation()

  return (
    <div className="min-w-[18rem] space-y-2">
      {cluster.candidate_urls.map((candidate) => (
        <div key={candidate.page_id} className="rounded-2xl border border-stone-200 bg-stone-50/80 p-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {candidate.is_dominant ? renderBadge(t('cannibalization.badges.primary'), 'teal') : null}
            {renderBadge(t('cannibalization.badges.clickShare', { value: formatPercent(candidate.click_share) }), 'stone')}
            {renderBadge(t('cannibalization.badges.impressionShare', { value: formatPercent(candidate.impression_share) }), 'stone')}
          </div>
          <p className="mt-2 text-sm font-medium text-stone-900 [overflow-wrap:anywhere]" title={candidate.url}>{candidate.url}</p>
          <div className="mt-2 space-y-1 text-xs text-stone-600">
            <p>
              {t('cannibalization.metrics.candidateQueries', {
                queryCount: candidate.query_count,
                sharedCount: candidate.shared_query_count,
                exclusiveCount: candidate.exclusive_query_count,
              })}
            </p>
            <p>
              {t('cannibalization.metrics.candidateTraffic', {
                impressions: formatNullable(candidate.impressions),
                clicks: formatNullable(candidate.clicks),
                position: formatPosition(candidate.position),
              })}
            </p>
            <p>{candidate.strongest_competing_url ?? '-'}</p>
          </div>
          <div className="mt-2 flex flex-wrap gap-3 text-xs font-medium text-teal-700">
            <Link to={buildPagesLink(jobId, params.gsc_date_range, candidate.url)}>{t('cannibalization.actions.openPage')}</Link>
            <button type="button" className="transition hover:text-teal-600" onClick={() => onInspect(candidate.page_id)}>
              {t('cannibalization.actions.inspectOverlap')}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function DetailsPanel({
  details,
  jobId,
  gscDateRange,
}: {
  details: CannibalizationPageDetails
  jobId: number
  gscDateRange: CannibalizationClustersQueryParams['gsc_date_range']
}) {
  const { t } = useTranslation()

  return (
    <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-rose-700">{t('cannibalization.details.focusedOverlap')}</p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-stone-950">{details.url}</h2>
          <p className="mt-2 text-sm text-stone-600">
            {details.has_cannibalization ? details.rationale : t('cannibalization.details.notInCluster')}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to={buildPagesLink(jobId, gscDateRange, details.url)}
            className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('cannibalization.actions.openInPages')}
          </Link>
          <UrlActions url={details.url} />
        </div>
      </div>

      {details.has_cannibalization ? (
        <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <div className="space-y-3 rounded-3xl border border-stone-200 bg-stone-50/90 p-4 text-sm text-stone-700">
            <div className="flex flex-wrap gap-2">
              {details.severity ? renderBadge(t(`cannibalization.severity.${details.severity}`), getSeverityTone(details.severity)) : null}
              {details.recommendation_type
                ? renderBadge(t(`cannibalization.recommendations.${details.recommendation_type}`), getRecommendationTone(details.recommendation_type))
                : null}
            </div>
            <p>{t('cannibalization.metrics.competingUrls', { count: details.competing_urls_count })}</p>
            <p>{t('cannibalization.metrics.strongestOverlap', { value: formatPercent(details.overlap_strength) })}</p>
            <p>{t('cannibalization.metrics.strongestSharedQueries', { count: details.common_queries_count })}</p>
            <p>{details.strongest_competing_url ?? '-'}</p>
            <p>{formatQueryList(details.shared_top_queries)}</p>
          </div>
          <div className="space-y-3">
            {details.overlaps.length === 0 ? (
              <EmptyState
                title={t('cannibalization.details.noOverlapsTitle')}
                description={t('cannibalization.details.noOverlapsDescription')}
              />
            ) : (
              details.overlaps.map((row) => (
                <div key={row.competing_page_id} className="rounded-3xl border border-stone-200 bg-white p-4">
                  <div className="flex flex-wrap gap-2">
                    {row.dominant_url
                      ? renderBadge(
                        row.dominant_url === details.url
                          ? t('cannibalization.badges.currentUrlLeads')
                          : t('cannibalization.badges.competitorLeads'),
                        row.dominant_url === details.url ? 'teal' : 'amber',
                      )
                      : renderBadge(t('cannibalization.badges.noClearLeader'), 'stone')}
                    {renderBadge(t('cannibalization.badges.overlap', { value: formatPercent(row.pair_overlap_score) }), 'stone')}
                  </div>
                  <p className="mt-2 text-sm font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.competing_url}>{row.competing_url}</p>
                  <div className="mt-2 space-y-1 text-xs text-stone-600">
                    <p>
                      {t('cannibalization.metrics.overlapTraffic', {
                        sharedCount: row.common_queries_count,
                        impressions: formatNullable(row.shared_query_impressions),
                        clicks: formatNullable(row.shared_query_clicks),
                      })}
                    </p>
                    <p>{formatQueryList(row.shared_top_queries)}</p>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs font-medium text-teal-700">
                    <Link to={buildPagesLink(jobId, gscDateRange, row.competing_url)}>{t('cannibalization.actions.openCompetitor')}</Link>
                    <Link to={buildDetailLink(jobId, gscDateRange, row.competing_page_id)}>{t('cannibalization.actions.focusCompetitor')}</Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </section>
  )
}

export function CannibalizationPage() {
  const { t } = useTranslation()
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? t('documentTitle.cannibalization', { jobId }) : t('nav.cannibalization'))

  if (jobId === null) {
    return <ErrorState title={t('cannibalization.invalidIdTitle')} message={t('cannibalization.invalidIdMessage')} />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const cannibalizationParams = useMemo(() => readParams(searchParams), [searchParams])
  const focusedPageId = readPageId(searchParams)
  const clustersQuery = useCannibalizationClustersQuery(jobId, cannibalizationParams)
  const pageDetailsQuery = useCannibalizationPageDetailsQuery(jobId, focusedPageId, cannibalizationParams.gsc_date_range)

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: cannibalizationParams.gsc_date_range,
      page: 1,
      page_size: 25,
      sort_by: 'severity',
      sort_order: 'desc',
      severity: undefined,
      impact_level: undefined,
      recommendation_type: undefined,
      has_clear_primary: undefined,
      url_contains: undefined,
    })
  }

  const quickFilters = [
    { label: t('cannibalization.quickFilters.highImpact'), isActive: cannibalizationParams.recommendation_type === 'HIGH_IMPACT_CANNIBALIZATION', onClick: () => updateParams({ recommendation_type: 'HIGH_IMPACT_CANNIBALIZATION', page: 1 }) },
    { label: t('cannibalization.quickFilters.mergeCandidate'), isActive: cannibalizationParams.recommendation_type === 'MERGE_CANDIDATE', onClick: () => updateParams({ recommendation_type: 'MERGE_CANDIDATE', page: 1 }) },
    { label: t('cannibalization.quickFilters.splitIntent'), isActive: cannibalizationParams.recommendation_type === 'SPLIT_INTENT_CANDIDATE', onClick: () => updateParams({ recommendation_type: 'SPLIT_INTENT_CANDIDATE', page: 1 }) },
    { label: t('cannibalization.quickFilters.noPrimary'), isActive: cannibalizationParams.has_clear_primary === false, onClick: () => updateParams({ has_clear_primary: 'false', page: 1 }) },
  ]

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-rose-700">{t('cannibalization.page.eyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">
              {t('cannibalization.page.title', { jobId })}
            </h1>
            <p className="mt-2 text-sm text-stone-600">{t('cannibalization.page.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <JobNavigation jobId={jobId} />
            <a
              href={buildExportHref(jobId, searchParams)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('cannibalization.page.export')}
            </a>
          </div>
        </div>
      </section>

      <QuickFilterBar title={t('cannibalization.quickFilters.title')} items={quickFilters} />

      <FilterPanel title={t('cannibalization.filters.title')} description={t('cannibalization.filters.description')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('cannibalization.filters.dateRange')}</span>
          <select value={cannibalizationParams.gsc_date_range} onChange={(event) => updateParams({ gsc_date_range: event.target.value, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="last_28_days">{t('cannibalization.filters.last28Days')}</option>
            <option value="last_90_days">{t('cannibalization.filters.last90Days')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('cannibalization.filters.severity')}</span>
          <select value={cannibalizationParams.severity ?? ''} onChange={(event) => updateParams({ severity: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {SEVERITIES.map((severity) => (
              <option key={severity} value={severity}>{t(`cannibalization.severity.${severity}`)}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('cannibalization.filters.impactLevel')}</span>
          <select value={cannibalizationParams.impact_level ?? ''} onChange={(event) => updateParams({ impact_level: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {IMPACT_LEVELS.map((impactLevel) => (
              <option key={impactLevel} value={impactLevel}>{t(`impact.${impactLevel}`)}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('cannibalization.filters.recommendationType')}</span>
          <select value={cannibalizationParams.recommendation_type ?? ''} onChange={(event) => updateParams({ recommendation_type: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            {RECOMMENDATION_TYPES.map((recommendationType) => (
              <option key={recommendationType} value={recommendationType}>{t(`cannibalization.recommendations.${recommendationType}`)}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('cannibalization.filters.clearPrimary')}</span>
          <select value={cannibalizationParams.has_clear_primary === undefined ? '' : String(cannibalizationParams.has_clear_primary)} onChange={(event) => updateParams({ has_clear_primary: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="">{t('common.any')}</option>
            <option value="true">{t('cannibalization.filters.hasPrimary')}</option>
            <option value="false">{t('cannibalization.filters.noPrimary')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('cannibalization.filters.urlContains')}</span>
          <input value={cannibalizationParams.url_contains ?? ''} onChange={(event) => updateParams({ url_contains: event.target.value || undefined, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2" placeholder={t('cannibalization.filters.urlContainsPlaceholder')} />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('cannibalization.filters.sortBy')}</span>
          <select value={cannibalizationParams.sort_by} onChange={(event) => updateParams({ sort_by: event.target.value, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="severity">{t('cannibalization.sort.severity')}</option>
            <option value="impact_level">{t('cannibalization.sort.impact')}</option>
            <option value="weighted_overlap">{t('cannibalization.sort.overlap')}</option>
            <option value="shared_queries_count">{t('cannibalization.sort.sharedQueries')}</option>
            <option value="shared_query_impressions">{t('cannibalization.sort.sharedImpressions')}</option>
            <option value="shared_query_clicks">{t('cannibalization.sort.sharedClicks')}</option>
            <option value="urls_count">{t('cannibalization.sort.urlsCount')}</option>
            <option value="dominant_url_confidence">{t('cannibalization.sort.primaryConfidence')}</option>
            <option value="recommendation_type">{t('cannibalization.sort.recommendation')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('cannibalization.filters.sortOrder')}</span>
          <select value={cannibalizationParams.sort_order} onChange={(event) => updateParams({ sort_order: event.target.value, page: 1 })} className="rounded-2xl border border-stone-300 bg-white px-3 py-2">
            <option value="desc">{t('sort.descending')}</option>
            <option value="asc">{t('sort.ascending')}</option>
          </select>
        </label>
      </FilterPanel>

      {clustersQuery.isLoading ? <LoadingState label={t('cannibalization.page.loading')} /> : null}
      {clustersQuery.isError ? <ErrorState title={t('cannibalization.errors.requestTitle')} message={getUiErrorMessage(clustersQuery.error, t)} /> : null}
      {clustersQuery.data ? (
        <SummaryCards
          items={[
            { label: t('cannibalization.summary.clusters'), value: clustersQuery.data.summary.clusters_count },
            { label: t('cannibalization.summary.pagesInConflicts'), value: clustersQuery.data.summary.pages_in_conflicts },
            { label: t('cannibalization.summary.highSeverity'), value: clustersQuery.data.summary.high_severity_clusters },
            { label: t('cannibalization.summary.highImpact'), value: clustersQuery.data.summary.high_impact_clusters },
            { label: t('cannibalization.summary.noPrimary'), value: clustersQuery.data.summary.no_clear_primary_clusters },
            { label: t('cannibalization.summary.mergeCandidates'), value: clustersQuery.data.summary.merge_candidates },
            { label: t('cannibalization.summary.splitIntent'), value: clustersQuery.data.summary.split_intent_candidates },
            { label: t('cannibalization.summary.averageOverlap'), value: formatPercent(clustersQuery.data.summary.average_weighted_overlap) },
          ]}
        />
      ) : null}

      {pageDetailsQuery.isLoading ? <LoadingState label={t('cannibalization.page.loadingDetails')} /> : null}
      {pageDetailsQuery.isError ? <ErrorState title={t('cannibalization.errors.detailsTitle')} message={getUiErrorMessage(pageDetailsQuery.error, t)} /> : null}
      {pageDetailsQuery.data ? <DetailsPanel details={pageDetailsQuery.data} jobId={jobId} gscDateRange={cannibalizationParams.gsc_date_range} /> : null}

      {clustersQuery.isSuccess && clustersQuery.data.items.length === 0 ? (
        <EmptyState title={t('cannibalization.empty.title')} description={t('cannibalization.empty.description')} />
      ) : null}
      {clustersQuery.isSuccess && clustersQuery.data.items.length > 0 ? (
        <>
          <DataTable
            columns={[
              {
                key: 'cluster',
                header: t('cannibalization.table.cluster'),
                sortKey: 'severity',
                cell: (cluster) => (
                  <div className="max-w-[16rem] space-y-2">
                    <div className="flex flex-wrap gap-1.5">
                      {renderBadge(t(`cannibalization.severity.${cluster.severity}`), getSeverityTone(cluster.severity))}
                      {renderBadge(t(`opportunities.impactLevel.${cluster.impact_level}`), getSeverityTone(cluster.severity))}
                      {renderBadge(t(`cannibalization.recommendations.${cluster.recommendation_type}`), getRecommendationTone(cluster.recommendation_type))}
                    </div>
                    <p className="text-xs text-stone-500">{cluster.cluster_id}</p>
                    <p className="text-sm text-stone-700">
                      {t('cannibalization.metrics.clusterSummary', {
                        urlsCount: cluster.urls_count,
                        sharedQueriesCount: cluster.shared_queries_count,
                      })}
                    </p>
                  </div>
                ),
              },
              {
                key: 'dominant',
                header: t('cannibalization.table.dominantUrl'),
                sortKey: 'dominant_url_confidence',
                cell: (cluster) => (
                  <div className="min-w-[14rem] space-y-1 text-sm text-stone-700">
                    <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={cluster.dominant_url ?? ''}>
                      {cluster.dominant_url ?? t('cannibalization.table.noPrimary')}
                    </p>
                    <p>{t('cannibalization.table.primaryConfidenceLabel')}: {formatPercent(cluster.dominant_url_confidence)}</p>
                    <p>
                      {t('cannibalization.metrics.clusterTraffic', {
                        impressions: formatNullable(cluster.shared_query_impressions),
                        clicks: formatNullable(cluster.shared_query_clicks),
                      })}
                    </p>
                    <p>{t('cannibalization.metrics.clusterOverlap', { value: formatPercent(cluster.weighted_overlap) })}</p>
                  </div>
                ),
              },
              {
                key: 'queries',
                header: t('cannibalization.table.sampleQueries'),
                sortKey: 'shared_queries_count',
                cell: (cluster) => (
                  <div className="min-w-[15rem] space-y-1 text-xs text-stone-600">
                    {cluster.sample_queries.map((query) => (
                      <p key={query} className="[overflow-wrap:anywhere]" title={query}>{query}</p>
                    ))}
                  </div>
                ),
              },
              {
                key: 'urls',
                header: t('cannibalization.table.competingUrls'),
                cell: (cluster) => (
                  <ClusterUrlsCell
                    cluster={cluster}
                    jobId={jobId}
                    params={cannibalizationParams}
                    onInspect={(pageId) => updateParams({ page_id: pageId })}
                  />
                ),
              },
              {
                key: 'rationale',
                header: t('cannibalization.table.rationale'),
                cell: (cluster) => (
                  <div className="max-w-[18rem] space-y-2">
                    <p className="text-sm leading-5 text-stone-700 [overflow-wrap:anywhere]" title={cluster.rationale}>{cluster.rationale}</p>
                    <div className="flex flex-wrap gap-3 text-xs font-medium text-teal-700">
                      {cluster.candidate_urls.map((candidate) => (
                        <Link key={candidate.page_id} to={buildDetailLink(jobId, cannibalizationParams.gsc_date_range, candidate.page_id)}>
                          {candidate.page_id}
                        </Link>
                      ))}
                    </div>
                  </div>
                ),
              },
            ]}
            rows={clustersQuery.data.items}
            rowKey={(cluster) => cluster.cluster_id}
            sortBy={cannibalizationParams.sort_by}
            sortOrder={cannibalizationParams.sort_order as SortOrder}
            onSortChange={(sortBy, sortOrder) => updateParams({ sort_by: sortBy, sort_order: sortOrder, page: 1 })}
          />
          <PaginationControls
            page={clustersQuery.data.page}
            pageSize={clustersQuery.data.page_size}
            totalItems={clustersQuery.data.total_items}
            totalPages={clustersQuery.data.total_pages}
            onPageChange={(page) => updateParams({ page })}
            onPageSizeChange={(pageSize) => updateParams({ page_size: pageSize, page: 1 })}
          />
        </>
      ) : null}
    </div>
  )
}
