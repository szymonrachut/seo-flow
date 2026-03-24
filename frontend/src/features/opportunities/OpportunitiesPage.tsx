import { startTransition, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { buildApiUrl } from '../../api/client'
import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { QuickFilterBar } from '../../components/QuickFilterBar'
import { SummaryCards } from '../../components/SummaryCards'
import { UrlActions } from '../../components/UrlActions'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type {
  GscDateRangeLabel,
  OpportunityType,
  PriorityLevel,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatNullable, formatPercent, formatPosition } from '../../utils/format'
import { mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
import { type OpportunitiesQueryParams, useOpportunitiesQuery } from './api'
import { localizeOpportunityRationale } from './rationaleLocalization'

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

function readOpportunitiesParams(searchParams: URLSearchParams): OpportunitiesQueryParams {
  const sortBy = searchParams.get('sort_by')
  const sortOrder = searchParams.get('sort_order')
  const rawPriorityLevel = searchParams.get('priority_level')
  const rawOpportunityType = searchParams.get('opportunity_type')

  return {
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    priority_level:
      rawPriorityLevel === 'low' || rawPriorityLevel === 'medium' || rawPriorityLevel === 'high' || rawPriorityLevel === 'critical'
        ? (rawPriorityLevel as PriorityLevel)
        : undefined,
    opportunity_type:
      rawOpportunityType &&
      [
        'QUICK_WINS',
        'HIGH_IMPRESSIONS_LOW_CTR',
        'TRAFFIC_WITH_TECHNICAL_ISSUES',
        'IMPORTANT_BUT_WEAK',
        'LOW_HANGING_FRUIT',
        'HIGH_RISK_PAGES',
        'UNDERLINKED_OPPORTUNITIES',
      ].includes(rawOpportunityType)
        ? (rawOpportunityType as OpportunityType)
        : undefined,
    priority_score_min: parseIntegerParam(searchParams.get('priority_score_min'), undefined),
    priority_score_max: parseIntegerParam(searchParams.get('priority_score_max'), undefined),
    sort_by:
      sortBy === 'top_priority_score' || sortBy === 'top_opportunity_score' || sortBy === 'type'
        ? sortBy
        : 'count',
    sort_order: sortOrder === 'asc' ? 'asc' : 'desc',
    top_pages_limit: parseIntegerParam(searchParams.get('top_pages_limit'), 5),
  }
}

function getBooleanQuickFilterState(params: OpportunitiesQueryParams, type: OpportunityType) {
  return params.opportunity_type === type
}

function buildPagesLink(
  jobId: number,
  range: GscDateRangeLabel,
  overrides: Record<string, string | number | undefined>,
) {
  const params = new URLSearchParams()
  params.set('gsc_date_range', range)
  params.set('sort_by', 'priority_score')
  params.set('sort_order', 'desc')

  Object.entries(overrides).forEach(([key, value]) => {
    if (value === undefined || value === '') {
      return
    }
    params.set(key, String(value))
  })

  return `/jobs/${jobId}/pages?${params.toString()}`
}

function buildExportHref(jobId: number, searchParams: URLSearchParams, kind: 'pages' | 'opportunities') {
  const params = new URLSearchParams()
  const gscDateRange = searchParams.get('gsc_date_range')
  const priorityLevel = searchParams.get('priority_level')
  const opportunityType = searchParams.get('opportunity_type')
  const priorityScoreMin = searchParams.get('priority_score_min')
  const priorityScoreMax = searchParams.get('priority_score_max')

  if (gscDateRange) {
    params.set('gsc_date_range', gscDateRange)
  }
  if (priorityLevel) {
    params.set('priority_level', priorityLevel)
  }
  if (opportunityType) {
    params.set('opportunity_type', opportunityType)
  }
  if (priorityScoreMin) {
    params.set('priority_score_min', priorityScoreMin)
  }
  if (priorityScoreMax) {
    params.set('priority_score_max', priorityScoreMax)
  }
  if (kind === 'pages') {
    params.set('sort_by', 'priority_score')
    params.set('sort_order', 'desc')
  }

  const query = params.toString()
  return buildApiUrl(`/crawl-jobs/${jobId}/export/${kind}.csv${query ? `?${query}` : ''}`)
}

export function OpportunitiesPage() {
  const { t, i18n } = useTranslation()
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? t('documentTitle.opportunities', { jobId }) : t('nav.opportunities'))

  if (jobId === null) {
    return <ErrorState title={t('opportunities.invalidIdTitle')} message={t('opportunities.invalidIdMessage')} />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const opportunitiesParams = useMemo(() => readOpportunitiesParams(searchParams), [searchParams])
  const opportunitiesQuery = useOpportunitiesQuery(jobId, opportunitiesParams)
  const currentLanguage = i18n.resolvedLanguage ?? i18n.language

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function applyPreset(updates: Record<string, string | number | undefined>) {
    updateParams({
      ...updates,
      sort_by: 'count',
      sort_order: 'desc',
    })
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: opportunitiesParams.gsc_date_range,
      priority_level: undefined,
      opportunity_type: undefined,
      priority_score_min: undefined,
      priority_score_max: undefined,
      sort_by: 'count',
      sort_order: 'desc',
      top_pages_limit: 5,
    })
  }

  const quickFilters = [
    {
      label: t('opportunities.quickFilters.highPriority'),
      isActive: (opportunitiesParams.priority_score_min ?? 0) >= 45,
      onClick: () => applyPreset({ priority_level: undefined, priority_score_min: 45 }),
    },
    {
      label: t('opportunities.quickFilters.quickWins'),
      isActive: getBooleanQuickFilterState(opportunitiesParams, 'QUICK_WINS'),
      onClick: () => applyPreset({ opportunity_type: 'QUICK_WINS' }),
    },
    {
      label: t('opportunities.quickFilters.trafficTechnical'),
      isActive: getBooleanQuickFilterState(opportunitiesParams, 'TRAFFIC_WITH_TECHNICAL_ISSUES'),
      onClick: () => applyPreset({ opportunity_type: 'TRAFFIC_WITH_TECHNICAL_ISSUES' }),
    },
    {
      label: t('opportunities.quickFilters.highImpressionsLowCtr'),
      isActive: getBooleanQuickFilterState(opportunitiesParams, 'HIGH_IMPRESSIONS_LOW_CTR'),
      onClick: () => applyPreset({ opportunity_type: 'HIGH_IMPRESSIONS_LOW_CTR' }),
    },
    {
      label: t('opportunities.quickFilters.lowHangingFruit'),
      isActive: getBooleanQuickFilterState(opportunitiesParams, 'LOW_HANGING_FRUIT'),
      onClick: () => applyPreset({ opportunity_type: 'LOW_HANGING_FRUIT' }),
    },
    {
      label: t('opportunities.quickFilters.underlinked'),
      isActive: getBooleanQuickFilterState(opportunitiesParams, 'UNDERLINKED_OPPORTUNITIES'),
      onClick: () => applyPreset({ opportunity_type: 'UNDERLINKED_OPPORTUNITIES' }),
    },
  ]

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('opportunities.page.eyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">
              {t('opportunities.page.title', { jobId })}
            </h1>
            <p className="mt-2 text-sm text-stone-600">{t('opportunities.page.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <JobNavigation jobId={jobId} />
            <a
              href={buildExportHref(jobId, searchParams, 'pages')}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('opportunities.page.exportPages')}
            </a>
            <a
              href={buildExportHref(jobId, searchParams, 'opportunities')}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('opportunities.page.exportOpportunities')}
            </a>
          </div>
        </div>
      </section>

      <QuickFilterBar title={t('opportunities.quickFilters.title')} items={quickFilters} />

      <FilterPanel title={t('opportunities.filters.title')} description={t('opportunities.filters.description')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.dateRange')}</span>
          <select
            value={opportunitiesParams.gsc_date_range}
            onChange={(event) => updateParams({ gsc_date_range: event.target.value })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="last_28_days">{t('opportunities.filters.last28Days')}</option>
            <option value="last_90_days">{t('opportunities.filters.last90Days')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.priorityLevel')}</span>
          <select
            value={opportunitiesParams.priority_level ?? ''}
            onChange={(event) => updateParams({ priority_level: event.target.value || undefined })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="critical">{t('opportunities.priorityLevel.critical')}</option>
            <option value="high">{t('opportunities.priorityLevel.high')}</option>
            <option value="medium">{t('opportunities.priorityLevel.medium')}</option>
            <option value="low">{t('opportunities.priorityLevel.low')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.opportunityType')}</span>
          <select
            value={opportunitiesParams.opportunity_type ?? ''}
            onChange={(event) => updateParams({ opportunity_type: event.target.value || undefined })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="QUICK_WINS">{t('opportunities.types.QUICK_WINS.title')}</option>
            <option value="HIGH_IMPRESSIONS_LOW_CTR">{t('opportunities.types.HIGH_IMPRESSIONS_LOW_CTR.title')}</option>
            <option value="TRAFFIC_WITH_TECHNICAL_ISSUES">{t('opportunities.types.TRAFFIC_WITH_TECHNICAL_ISSUES.title')}</option>
            <option value="IMPORTANT_BUT_WEAK">{t('opportunities.types.IMPORTANT_BUT_WEAK.title')}</option>
            <option value="LOW_HANGING_FRUIT">{t('opportunities.types.LOW_HANGING_FRUIT.title')}</option>
            <option value="HIGH_RISK_PAGES">{t('opportunities.types.HIGH_RISK_PAGES.title')}</option>
            <option value="UNDERLINKED_OPPORTUNITIES">{t('opportunities.types.UNDERLINKED_OPPORTUNITIES.title')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.priorityMin')}</span>
          <input
            type="number"
            value={searchParams.get('priority_score_min') ?? ''}
            onChange={(event) => updateParams({ priority_score_min: event.target.value || undefined })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="50"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.priorityMax')}</span>
          <input
            type="number"
            value={searchParams.get('priority_score_max') ?? ''}
            onChange={(event) => updateParams({ priority_score_max: event.target.value || undefined })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="100"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.sortBy')}</span>
          <select
            value={opportunitiesParams.sort_by}
            onChange={(event) => updateParams({ sort_by: event.target.value })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="count">{t('opportunities.filters.sort.count')}</option>
            <option value="top_priority_score">{t('opportunities.filters.sort.topPriority')}</option>
            <option value="top_opportunity_score">{t('opportunities.filters.sort.topOpportunity')}</option>
            <option value="type">{t('opportunities.filters.sort.type')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.sortOrder')}</span>
          <select
            value={opportunitiesParams.sort_order}
            onChange={(event) => updateParams({ sort_order: event.target.value })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="desc">{t('sort.descending')}</option>
            <option value="asc">{t('sort.ascending')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('opportunities.filters.topPagesLimit')}</span>
          <input
            type="number"
            min={1}
            max={20}
            value={String(opportunitiesParams.top_pages_limit)}
            onChange={(event) => updateParams({ top_pages_limit: event.target.value || 5 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          />
        </label>
      </FilterPanel>

      {opportunitiesQuery.isLoading ? <LoadingState label={t('opportunities.page.loading')} /> : null}
      {opportunitiesQuery.isError ? (
        <ErrorState title={t('opportunities.errors.requestTitle')} message={getUiErrorMessage(opportunitiesQuery.error, t)} />
      ) : null}

      {opportunitiesQuery.data ? (
        <>
          <SummaryCards
            items={[
              { label: t('opportunities.summary.totalPages'), value: opportunitiesQuery.data.total_pages },
              { label: t('opportunities.summary.pagesWithOpportunities'), value: opportunitiesQuery.data.pages_with_opportunities },
              { label: t('opportunities.summary.highPriorityPages'), value: opportunitiesQuery.data.high_priority_pages },
              { label: t('opportunities.summary.criticalPriorityPages'), value: opportunitiesQuery.data.critical_priority_pages },
              { label: t('opportunities.summary.groups'), value: opportunitiesQuery.data.groups.length },
              { label: t('opportunities.summary.range'), value: opportunitiesQuery.data.gsc_date_range === 'last_90_days' ? '90d' : '28d' },
            ]}
          />

          <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-stone-950">{t('opportunities.topPriority.title')}</h2>
                <p className="mt-1 text-sm text-stone-600">{t('opportunities.topPriority.description')}</p>
              </div>
              <Link
                to={buildPagesLink(jobId, opportunitiesParams.gsc_date_range, { sort_by: 'priority_score', sort_order: 'desc' })}
                className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
              >
                {t('common.showInPages')}
              </Link>
            </div>

            {opportunitiesQuery.data.top_priority_pages.length === 0 ? (
              <div className="mt-4">
                <EmptyState title={t('opportunities.empty.topPriorityTitle')} description={t('opportunities.empty.topPriorityDescription')} />
              </div>
            ) : (
              <div className="mt-4">
                <DataTable
                  columns={[
                    {
                      key: 'url',
                      header: t('opportunities.table.url'),
                      cell: (row) => (
                        <div className="max-w-[22rem] space-y-1">
                          <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.url}>{row.url}</p>
                          <p className="text-xs text-stone-500">
                            {t('opportunities.table.primaryOpportunity')}: {row.primary_opportunity_type ? t(`opportunities.types.${row.primary_opportunity_type}.title`) : '-'}
                          </p>
                          <UrlActions url={row.url} />
                        </div>
                      ),
                    },
                    {
                      key: 'priority',
                      header: t('opportunities.table.priority'),
                      cell: (row) => `${row.priority_score} / ${t(`opportunities.priorityLevel.${row.priority_level}`)}`,
                    },
                    {
                      key: 'traffic',
                      header: t('opportunities.table.traffic'),
                      cell: (row) => (
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
                      cell: (row) => {
                        const localizedRationale = localizeOpportunityRationale(row.priority_rationale, currentLanguage, t)
                        return <span className="[overflow-wrap:anywhere]" title={localizedRationale}>{localizedRationale}</span>
                      },
                    },
                  ]}
                  rows={opportunitiesQuery.data.top_priority_pages}
                  rowKey={(row) => row.page_id}
                />
              </div>
            )}
          </section>

          {opportunitiesQuery.data.groups.length === 0 ? (
            <EmptyState title={t('opportunities.empty.groupsTitle')} description={t('opportunities.empty.groupsDescription')} />
          ) : (
            opportunitiesQuery.data.groups.map((group) => (
              <section key={group.type} className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-stone-950">{t(`opportunities.types.${group.type}.title`)}</h2>
                    <p className="mt-1 text-sm text-stone-600">{t(`opportunities.types.${group.type}.description`)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <span className="inline-flex rounded-full bg-stone-100 px-3 py-1.5 text-sm font-semibold text-stone-700">
                      {t('opportunities.groupCount', { count: group.count })}
                    </span>
                    <Link
                      to={buildPagesLink(jobId, opportunitiesParams.gsc_date_range, { opportunity_type: group.type })}
                      className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                    >
                      {t('common.showInPages')}
                    </Link>
                  </div>
                </div>

                <div className="mt-4">
                  <DataTable
                    columns={[
                      {
                        key: 'url',
                        header: t('opportunities.table.url'),
                        cell: (row) => (
                          <div className="max-w-[21rem] space-y-1">
                            <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={row.url}>{row.url}</p>
                            <p className="text-xs text-stone-500">
                              {t('opportunities.metrics.internalLinks')}: {row.incoming_internal_links} / {row.incoming_internal_linking_pages}
                            </p>
                            <UrlActions url={row.url} />
                          </div>
                        ),
                      },
                      {
                        key: 'priority',
                        header: t('opportunities.table.priority'),
                        cell: (row) => `${row.priority_score} / ${t(`opportunities.priorityLevel.${row.priority_level}`)}`,
                      },
                      {
                        key: 'impact',
                        header: t('opportunities.table.impact'),
                        cell: (row) => (
                          <div className="space-y-1 text-xs text-stone-600">
                            <p>{t('opportunities.table.opportunityScore')}: {formatNullable(row.opportunity_score)}</p>
                            <p>{t('opportunities.table.impactLevel')}: {row.impact_level ? t(`opportunities.impactLevel.${row.impact_level}`) : '-'}</p>
                            <p>{t('opportunities.table.effortLevel')}: {row.effort_level ? t(`opportunities.effortLevel.${row.effort_level}`) : '-'}</p>
                          </div>
                        ),
                      },
                      {
                        key: 'traffic',
                        header: t('opportunities.table.traffic'),
                        cell: (row) => (
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
                        cell: (row) => {
                          const localizedRationale = localizeOpportunityRationale(row.rationale, currentLanguage, t)
                          return <span className="[overflow-wrap:anywhere]" title={localizedRationale}>{localizedRationale}</span>
                        },
                      },
                    ]}
                    rows={group.top_pages}
                    rowKey={(row) => `${group.type}-${row.page_id}`}
                  />
                </div>
              </section>
            ))
          )}
        </>
      ) : null}
    </div>
  )
}
