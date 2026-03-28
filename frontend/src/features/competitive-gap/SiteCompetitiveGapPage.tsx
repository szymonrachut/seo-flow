import { startTransition, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ApiError, buildApiUrl } from '../../api/client'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { PaginationControls } from '../../components/PaginationControls'
import { QuickFilterBar } from '../../components/QuickFilterBar'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type {
  CompetitiveGapDataSourceMode,
  CompetitiveGapDecisionAction,
  CompetitiveGapCoverageType,
  CompetitiveGapDetailType,
  CompetitiveGapRow,
  CompetitiveGapSegment,
  CompetitiveGapSemanticAnalysisMode,
  CompetitiveGapSortBy,
  CompetitiveGapType,
  CompetitiveGapExplanationResponse,
  CompetitiveGapEmptyStateReason,
  CompetitiveGapSemanticMatchStatus,
  CompetitiveGapSemanticStatus,
  CompetitorSyncStatus,
  PaginatedCompetitiveGapResponse,
  PageType,
  SiteContentGapReviewRun,
  SiteCompetitor,
  SiteCompetitiveGapQueryParams,
  StrategyNormalizationStatus,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatCrawlDateTime, formatDateTime, formatPercent, truncateText } from '../../utils/format'
import { buildQueryString, mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import {
  buildSiteCompetitiveGapCompetitorsPath,
  buildSiteCompetitiveGapResultsPath,
  buildSiteCompetitiveGapSemstormDiscoveryPath,
  buildSiteCompetitiveGapSemstormOpportunitiesPath,
  buildSiteCompetitiveGapStrategyPath,
  buildSiteCompetitiveGapSyncPath,
  buildSitePagesRecordsPath,
} from '../sites/routes'
import {
  useCompetitiveGapExplanationMutation,
  useCreateSiteCompetitiveGapCompetitorMutation,
  useDeleteSiteCompetitiveGapCompetitorMutation,
  useSiteCompetitiveGapCompetitorReviewQuery,
  useDeleteSiteCompetitiveGapStrategyMutation,
  useRetrySiteCompetitiveGapCompetitorSyncMutation,
  useRetrySiteCompetitiveGapReviewRunMutation,
  useResetSiteCompetitiveGapCompetitorSyncMutation,
  useRerunSiteCompetitiveGapSemanticMatchingMutation,
  useSiteCompetitiveGapCompetitorSyncRunsQuery,
  useSiteCompetitiveGapCompetitorsQuery,
  useSiteCompetitiveGapQuery,
  useSiteCompetitiveGapReviewRunsQuery,
  useSiteCompetitiveGapStrategyQuery,
  useSyncAllSiteCompetitiveGapCompetitorsMutation,
  useSyncSiteCompetitiveGapCompetitorMutation,
  useUpdateSiteCompetitiveGapCompetitorMutation,
  useUpsertSiteCompetitiveGapStrategyMutation,
} from './api'

const gapTypes: CompetitiveGapType[] = ['NEW_TOPIC', 'EXPAND_EXISTING_TOPIC', 'MISSING_SUPPORTING_PAGE']
const gapSegments: CompetitiveGapSegment[] = ['create_new_page', 'expand_existing_page', 'strengthen_cluster']
const pageTypes: PageType[] = [
  'home',
  'category',
  'product',
  'service',
  'blog_article',
  'blog_index',
  'contact',
  'about',
  'faq',
  'location',
  'legal',
  'utility',
  'other',
]

const surfaceClass =
  'rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const sectionClass =
  'rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const cardClass =
  'rounded-[28px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/85'
const panelClass =
  'rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/85'
const actionClass =
  'inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:border-slate-500 dark:hover:bg-slate-800'
const primaryActionClass =
  'inline-flex rounded-full bg-teal-700 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-teal-600 disabled:cursor-not-allowed disabled:opacity-60'
const fieldLabelClass = 'grid gap-1 text-sm text-stone-700 dark:text-slate-300'
const fieldControlClass =
  'rounded-2xl border border-stone-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100'
const competitorRecentRunsLimit = 5
const contentGapReviewRunsLimit = 5
const competitorReviewPageSize = 20

type CompetitiveGapPageMode = 'full' | 'overview' | 'strategy' | 'competitors' | 'sync' | 'results'

function readGapType(value: string | null): CompetitiveGapType | undefined {
  return value && gapTypes.includes(value as CompetitiveGapType) ? (value as CompetitiveGapType) : undefined
}

function readGapSegment(value: string | null): CompetitiveGapSegment | undefined {
  return value && gapSegments.includes(value as CompetitiveGapSegment) ? (value as CompetitiveGapSegment) : undefined
}

function readPageType(value: string | null): PageType | undefined {
  return value && pageTypes.includes(value as PageType) ? (value as PageType) : undefined
}

function readSortBy(value: string | null): CompetitiveGapSortBy {
  return value === 'consensus_score' ||
    value === 'competitor_count' ||
    value === 'competitor_coverage_score' ||
    value === 'own_coverage_score' ||
    value === 'strategy_alignment_score' ||
    value === 'business_value_score' ||
    value === 'merged_topic_count' ||
    value === 'confidence' ||
    value === 'topic_label' ||
    value === 'gap_type' ||
    value === 'page_type'
    ? value
    : 'priority_score'
}

function readOwnMatchStatus(value: string | null): CompetitiveGapSemanticMatchStatus | undefined {
  return value === 'exact_match' ||
    value === 'semantic_match' ||
    value === 'partial_coverage' ||
    value === 'no_meaningful_match'
    ? value
    : undefined
}

function readParams(searchParams: URLSearchParams, activeCrawlId?: number | null): SiteCompetitiveGapQueryParams {
  return {
    active_crawl_id: activeCrawlId ?? undefined,
    gsc_date_range: searchParams.get('gsc_date_range') === 'last_90_days' ? 'last_90_days' : 'last_28_days',
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), 25),
    sort_by: readSortBy(searchParams.get('sort_by')),
    sort_order: searchParams.get('sort_order') === 'asc' ? 'asc' : 'desc',
    gap_type: readGapType(searchParams.get('gap_type')),
    segment: readGapSegment(searchParams.get('segment')),
    page_type: readPageType(searchParams.get('page_type')),
    own_match_status: readOwnMatchStatus(searchParams.get('own_match_status')),
    topic: searchParams.get('topic') || undefined,
    priority_score_min: parseIntegerParam(searchParams.get('priority_score_min'), undefined),
    consensus_min: parseIntegerParam(searchParams.get('consensus_min'), undefined),
  }
}

function buildExportHref(siteId: number, params: SiteCompetitiveGapQueryParams) {
  const query = buildQueryString({
    active_crawl_id: params.active_crawl_id,
    gsc_date_range: params.gsc_date_range,
    sort_by: params.sort_by,
    sort_order: params.sort_order,
    gap_type: params.gap_type,
    segment: params.segment,
    page_type: params.page_type,
    own_match_status: params.own_match_status,
    topic: params.topic,
    priority_score_min: params.priority_score_min,
    consensus_min: params.consensus_min,
  })
  return buildApiUrl(`/sites/${siteId}/export/competitive-content-gap.csv${query ? `?${query}` : ''}`)
}

function buildPagesLink(siteId: number, targetUrl: string, activeCrawlId?: number | null, baselineCrawlId?: number | null) {
  const base = buildSitePagesRecordsPath(siteId, { activeCrawlId, baselineCrawlId })
  const separator = base.includes('?') ? '&' : '?'
  return `${base}${separator}${buildQueryString({ url_contains: targetUrl })}`
}

function toneClass(tone: 'stone' | 'teal' | 'amber' | 'rose') {
  if (tone === 'teal') {
    return 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/60 dark:text-teal-200'
  }
  if (tone === 'amber') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200'
  }
  if (tone === 'rose') {
    return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/60 dark:text-rose-200'
  }
  return 'border-stone-300 bg-stone-100 text-stone-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
}

function renderBadge(label: string, tone: 'stone' | 'teal' | 'amber' | 'rose' = 'stone') {
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${toneClass(tone)}`}>{label}</span>
}

function strategyStatusTone(status: StrategyNormalizationStatus | null | undefined) {
  if (status === 'ready') {
    return 'teal'
  }
  if (status === 'failed') {
    return 'rose'
  }
  if (status === 'not_processed') {
    return 'amber'
  }
  return 'stone'
}

function competitorSyncStatusTone(status: CompetitorSyncStatus | null | undefined) {
  if (status === 'done') {
    return 'teal'
  }
  if (status === 'failed') {
    return 'rose'
  }
  if (status === 'queued' || status === 'running') {
    return 'amber'
  }
  return 'stone'
}

function competitorSyncStageTone(stage: string | null | undefined) {
  if (stage === 'extracting' || stage === 'crawling' || stage === 'persisting' || stage === 'finalizing') {
    return 'amber'
  }
  if (stage === 'done') {
    return 'teal'
  }
  if (stage === 'failed') {
    return 'rose'
  }
  if (stage === 'stale') {
    return 'amber'
  }
  return 'stone'
}

function syncRunStatusTone(status: string | null | undefined) {
  if (status === 'done') {
    return 'teal'
  }
  if (status === 'failed') {
    return 'rose'
  }
  if (status === 'stale') {
    return 'amber'
  }
  if (status === 'queued' || status === 'running') {
    return 'amber'
  }
  return 'stone'
}

function semanticStatusTone(status: CompetitiveGapSemanticStatus | null | undefined) {
  if (status === 'ready' || status === 'completed') {
    return 'teal'
  }
  if (status === 'failed') {
    return 'rose'
  }
  if (status === 'queued' || status === 'running' || status === 'partial' || status === 'stale') {
    return 'amber'
  }
  return 'stone'
}

function semanticAnalysisModeTone(mode: CompetitiveGapSemanticAnalysisMode | null | undefined) {
  if (mode === 'llm_only') {
    return 'teal'
  }
  if (mode === 'mixed') {
    return 'amber'
  }
  return 'stone'
}

function semanticRuntimeStateTone(state: SemanticRuntimeState) {
  if (state === 'working' || state === 'queued') {
    return 'amber'
  }
  if (state === 'stopped') {
    return 'rose'
  }
  return 'stone'
}

function semanticMatchTone(status: CompetitiveGapSemanticMatchStatus | null | undefined) {
  if (status === 'exact_match') {
    return 'teal'
  }
  if (status === 'semantic_match') {
    return 'amber'
  }
  if (status === 'partial_coverage') {
    return 'stone'
  }
  if (status === 'no_meaningful_match') {
    return 'rose'
  }
  return 'stone'
}

function gapTypeTone(type: CompetitiveGapType) {
  if (type === 'NEW_TOPIC') {
    return 'teal'
  }
  if (type === 'MISSING_SUPPORTING_PAGE') {
    return 'amber'
  }
  return 'stone'
}

function getCompetitorSyncProgressPercent(competitor: SiteCompetitor) {
  return Math.max(0, Math.min(100, competitor.last_sync_progress_percent ?? 0))
}

function scoreTone(value: number) {
  if (value >= 75) {
    return 'rose'
  }
  if (value >= 50) {
    return 'amber'
  }
  return 'stone'
}

function contentGapSourceModeTone(mode: CompetitiveGapDataSourceMode | null | undefined) {
  if (mode === 'reviewed') {
    return 'teal'
  }
  if (mode === 'raw_candidates') {
    return 'amber'
  }
  return 'stone'
}

function reviewDecisionTone(action: CompetitiveGapDecisionAction | null | undefined) {
  if (action === 'keep') {
    return 'teal'
  }
  if (action === 'rewrite') {
    return 'amber'
  }
  if (action === 'remove') {
    return 'rose'
  }
  return 'stone'
}

function reviewRunStatusTone(status: string | null | undefined) {
  if (status === 'completed') {
    return 'teal'
  }
  if (status === 'failed' || status === 'cancelled') {
    return 'rose'
  }
  if (status === 'queued' || status === 'running' || status === 'stale') {
    return 'amber'
  }
  return 'stone'
}

function isRetryableReviewRunStatus(status: string | null | undefined) {
  return status === 'failed' || status === 'stale' || status === 'cancelled'
}

type SurfaceTone = 'stone' | 'teal' | 'amber' | 'rose'

interface EmptyStateCopy {
  title: string
  description: string
  tone: SurfaceTone
}

interface SyncReasonStat {
  key: string
  count: number
}

type SemanticRuntimeState = 'working' | 'queued' | 'stopped' | 'idle'

interface SemanticReadinessSummary {
  status: CompetitiveGapSemanticStatus
  analysisMode: CompetitiveGapSemanticAnalysisMode
  runtimeState: SemanticRuntimeState
  activeRunsCount: number
  currentStage: string | null
  currentBatchCandidatesCount: number
  currentBatchResolvedCount: number
  lastHeartbeatAt: string | null
  leaseExpiresAt: string | null
  candidatesCount: number
  resolvedCount: number
  progressPercent: number
  llmJobsCount: number
  cacheHits: number
  fallbackCount: number
  llmMergedUrlsCount: number
  lastRunStartedAt: string | null
  lastRunFinishedAt: string | null
  lastError: string | null
  model: string | null
  promptVersion: string | null
}

function syncSummaryCount(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function isCompetitorSyncBusy(competitor: SiteCompetitor) {
  return competitor.last_sync_status === 'queued' || competitor.last_sync_status === 'running'
}

function isRetryableRunStatus(status: string | null | undefined) {
  return status === 'failed' || status === 'stale' || status === 'cancelled'
}

interface CompetitorRecentRunsPanelProps {
  siteId: number
  competitor: SiteCompetitor
  expanded: boolean
  onToggle: () => void
}

interface ContentGapReviewRunsPanelProps {
  siteId: number
  activeCrawlId?: number | null
  enabled: boolean
}

function ContentGapReviewRunsPanel({ siteId, activeCrawlId, enabled }: ContentGapReviewRunsPanelProps) {
  const { t } = useTranslation()
  const retryReviewRunMutation = useRetrySiteCompetitiveGapReviewRunMutation(siteId)
  const [retryingRunId, setRetryingRunId] = useState<number | null>(null)
  const reviewRunsQuery = useSiteCompetitiveGapReviewRunsQuery(siteId, contentGapReviewRunsLimit, enabled)
  const recentRuns = reviewRunsQuery.data ?? []
  const latestRun = recentRuns[0] ?? null

  async function handleRetry(run: SiteContentGapReviewRun) {
    setRetryingRunId(run.run_id)
    try {
      await retryReviewRunMutation.mutateAsync(run.run_id)
    } finally {
      setRetryingRunId(null)
    }
  }

  return (
    <section className={sectionClass}>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{t('competitiveGap.reviewRuns.title')}</h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.reviewRuns.description')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {activeCrawlId ? renderBadge(t('competitiveGap.reviewRuns.activeCrawlBadge', { crawlId: activeCrawlId }), 'teal') : null}
          {latestRun ? renderBadge(t('competitiveGap.reviewRuns.latestRunBadge', { runId: latestRun.run_id }), reviewRunStatusTone(latestRun.status)) : null}
        </div>
      </div>

      {reviewRunsQuery.isLoading ? (
        <p className="mt-4 text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.reviewRuns.loading')}</p>
      ) : reviewRunsQuery.isError ? (
        <p className="mt-4 text-sm text-rose-700 dark:text-rose-300">{getUiErrorMessage(reviewRunsQuery.error, t)}</p>
      ) : recentRuns.length === 0 ? (
        <p className="mt-4 text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.reviewRuns.empty')}</p>
      ) : (
        <div className="mt-4 space-y-3">
          {recentRuns.map((run) => {
            const isCurrentSnapshot = activeCrawlId != null && run.basis_crawl_job_id === activeCrawlId
            const canRetry = isCurrentSnapshot && isRetryableReviewRunStatus(run.status)

            return (
              <div
                key={run.run_id}
                className="rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/70"
              >
                <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      {renderBadge(t('competitiveGap.reviewRuns.runBadge', { runId: run.run_id }))}
                      {renderBadge(t('competitiveGap.reviewRuns.statusBadge', { status: run.status }), reviewRunStatusTone(run.status))}
                      {renderBadge(t('competitiveGap.reviewRuns.stageBadge', { stage: run.stage }))}
                      {renderBadge(t('competitiveGap.reviewRuns.snapshotBadge', { crawlId: run.basis_crawl_job_id }), isCurrentSnapshot ? 'teal' : 'amber')}
                      {run.retry_of_run_id ? renderBadge(t('competitiveGap.reviewRuns.retryOfBadge', { runId: run.retry_of_run_id })) : null}
                    </div>
                    <div className="grid gap-2 text-xs text-stone-600 sm:grid-cols-2 xl:grid-cols-4 dark:text-slate-300">
                      <p>{t('competitiveGap.reviewRuns.candidates', { count: run.candidate_count })}</p>
                      <p>{t('competitiveGap.reviewRuns.progress', { completed: run.completed_batch_count, total: run.batch_count })}</p>
                      <p>{t('competitiveGap.reviewRuns.startedAt', { value: run.started_at ? formatDateTime(run.started_at) : t('competitiveGap.strategy.debug.notAvailable') })}</p>
                      <p>{t('competitiveGap.reviewRuns.finishedAt', { value: run.finished_at ? formatDateTime(run.finished_at) : t('competitiveGap.strategy.debug.notAvailable') })}</p>
                    </div>
                    {!isCurrentSnapshot ? (
                      <p className="text-xs text-amber-800 dark:text-amber-200">
                        {t('competitiveGap.reviewRuns.outdatedRunHint', { crawlId: run.basis_crawl_job_id })}
                      </p>
                    ) : null}
                    {run.error_message_safe ? (
                      <p className="text-sm text-stone-700 dark:text-slate-200">{run.error_message_safe}</p>
                    ) : null}
                  </div>
                  {canRetry ? (
                    <button
                      type="button"
                      onClick={() => void handleRetry(run)}
                      disabled={retryReviewRunMutation.isPending && retryingRunId === run.run_id}
                      className={actionClass}
                    >
                      {retryReviewRunMutation.isPending && retryingRunId === run.run_id
                        ? t('competitiveGap.reviewRuns.retrying')
                        : t('competitiveGap.reviewRuns.retry')}
                    </button>
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {retryReviewRunMutation.isError ? (
        <p className="mt-3 text-sm text-rose-700 dark:text-rose-300">
          {getUiErrorMessage(retryReviewRunMutation.error, t)}
        </p>
      ) : null}
    </section>
  )
}

function CompetitorRecentRunsPanel({ siteId, competitor, expanded, onToggle }: CompetitorRecentRunsPanelProps) {
  const { t } = useTranslation()
  const runsQuery = useSiteCompetitiveGapCompetitorSyncRunsQuery(
    siteId,
    competitor.id,
    competitorRecentRunsLimit,
    expanded,
    expanded && isCompetitorSyncBusy(competitor) ? 4_000 : false,
  )

  function syncRunStatusLabel(value: string | null | undefined) {
    return t(`competitiveGap.competitors.runStatus.${value ?? 'cancelled'}`)
  }

  function syncRunStageLabel(value: string | null | undefined) {
    return t(`competitiveGap.competitors.runStage.${value ?? 'cancelled'}`)
  }

  function syncRunTriggerLabel(value: string | null | undefined) {
    return t(`competitiveGap.competitors.runTrigger.${value ?? 'manual_single'}`)
  }

  return (
    <div className={panelClass}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
            {t('competitiveGap.competitors.recentRunsTitle')}
          </p>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
            {t('competitiveGap.competitors.recentRunsDescription')}
          </p>
        </div>
        <button type="button" onClick={onToggle} className={actionClass}>
          {expanded ? t('competitiveGap.competitors.hideRecentRuns') : t('competitiveGap.competitors.showRecentRuns')}
        </button>
      </div>

      {expanded ? (
        <div className="mt-3">
          {runsQuery.isLoading ? (
            <p className="text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.competitors.recentRunsLoading')}</p>
          ) : runsQuery.isError ? (
            <p className="text-sm text-rose-700 dark:text-rose-300">{getUiErrorMessage(runsQuery.error, t)}</p>
          ) : (runsQuery.data?.length ?? 0) === 0 ? (
            <p className="text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.competitors.recentRunsEmpty')}</p>
          ) : (
            <div className="space-y-2">
              {runsQuery.data?.map((run) => (
                <div
                  key={`${competitor.id}:${run.run_id}`}
                  className="rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/70"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    {renderBadge(t('competitiveGap.competitors.lastRunValue', { runId: run.run_id }))}
                    {renderBadge(syncRunStatusLabel(run.status), syncRunStatusTone(run.status))}
                    {renderBadge(syncRunStageLabel(run.stage), competitorSyncStageTone(run.stage))}
                    {renderBadge(syncRunTriggerLabel(run.trigger_source), run.trigger_source === 'retry' ? 'amber' : 'stone')}
                    {run.retry_of_run_id ? renderBadge(t('competitiveGap.competitors.retryOf', { runId: run.retry_of_run_id })) : null}
                    {run.error_code ? renderBadge(run.error_code, run.status === 'stale' ? 'amber' : 'rose') : null}
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-stone-600 sm:grid-cols-2 xl:grid-cols-4 dark:text-slate-300">
                    <p>
                      {t('competitiveGap.competitors.lastStarted')}: {run.started_at ? formatDateTime(run.started_at) : t('competitiveGap.strategy.debug.notAvailable')}
                    </p>
                    <p>
                      {t('competitiveGap.competitors.lastFinished')}: {run.finished_at ? formatDateTime(run.finished_at) : t('competitiveGap.strategy.debug.notAvailable')}
                    </p>
                    <p>
                      {t('competitiveGap.competitors.lastHeartbeat')}: {run.last_heartbeat_at ? formatDateTime(run.last_heartbeat_at) : t('competitiveGap.strategy.debug.notAvailable')}
                    </p>
                    <p>
                      {t('competitiveGap.competitors.progressLabel')}: {run.progress_percent}%
                    </p>
                  </div>
                  {run.error_message_safe ? (
                    <p className="mt-3 text-sm text-stone-700 dark:text-slate-200">{run.error_message_safe}</p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}

interface CompetitorPageReviewPanelProps {
  siteId: number
  competitor: SiteCompetitor
}

function CompetitorPageReviewPanel({ siteId, competitor }: CompetitorPageReviewPanelProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const [reviewStatus, setReviewStatus] = useState<'all' | 'accepted' | 'rejected'>('all')
  const reviewQuery = useSiteCompetitiveGapCompetitorReviewQuery(
    siteId,
    competitor.id,
    {
      review_status: reviewStatus,
      page: 1,
      page_size: competitorReviewPageSize,
    },
    expanded,
  )

  const reviewSummary = reviewQuery.data?.summary
  const topReasons = Object.entries(reviewSummary?.counts_by_reason ?? {})
    .slice(0, 4)
    .map(([reason, count]) => ({ reason, count }))

  function reviewStatusLabel(value: 'all' | 'accepted' | 'rejected') {
    return t(`competitiveGap.competitors.review.filter.${value}`)
  }

  function reviewStatusTone(value: 'all' | 'accepted' | 'rejected') {
    if (value === 'accepted') {
      return 'teal' as const
    }
    if (value === 'rejected') {
      return 'rose' as const
    }
    return 'stone' as const
  }

  return (
    <div className={panelClass}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
            {t('competitiveGap.competitors.review.title')}
          </p>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
            {t('competitiveGap.competitors.review.description')}
          </p>
        </div>
        <button type="button" onClick={() => setExpanded((current) => !current)} className={actionClass}>
          {expanded ? t('competitiveGap.competitors.review.hide') : t('competitiveGap.competitors.review.show')}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {renderBadge(
          t('competitiveGap.competitors.review.acceptedCount', { count: competitor.accepted_pages_count ?? 0 }),
          'teal',
        )}
        {renderBadge(
          t('competitiveGap.competitors.review.rejectedCount', { count: competitor.rejected_pages_count ?? 0 }),
          (competitor.rejected_pages_count ?? 0) > 0 ? 'rose' : 'stone',
        )}
        {renderBadge(
          t('competitiveGap.competitors.review.extractedCount', { count: competitor.extracted_pages_count }),
          competitor.extracted_pages_count > 0 ? 'amber' : 'stone',
        )}
      </div>

      {topReasons.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {topReasons.map((item) => renderBadge(`${item.reason}: ${item.count}`, item.reason.startsWith('accepted') ? 'teal' : 'rose'))}
        </div>
      ) : null}

      {expanded ? (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-2">
            {(['all', 'accepted', 'rejected'] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setReviewStatus(value)}
                className={`${actionClass} ${reviewStatus === value ? 'border-stone-500 bg-stone-100 dark:border-slate-500 dark:bg-slate-800' : ''}`}
              >
                {reviewStatusLabel(value)}
              </button>
            ))}
          </div>

          {reviewQuery.isLoading ? (
            <p className="text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.competitors.review.loading')}</p>
          ) : reviewQuery.isError ? (
            <p className="text-sm text-rose-700 dark:text-rose-300">{getUiErrorMessage(reviewQuery.error, t)}</p>
          ) : (reviewQuery.data?.items.length ?? 0) === 0 ? (
            <p className="text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.competitors.review.empty')}</p>
          ) : (
            <div className="space-y-3">
              <p className="text-xs text-stone-600 dark:text-slate-300">
                {t('competitiveGap.competitors.review.showing', {
                  shown: reviewQuery.data?.items.length ?? 0,
                  total: reviewQuery.data?.total_items ?? 0,
                })}
              </p>
              {reviewQuery.data?.items.map((item) => {
                const diagnostics = item.diagnostics ?? {}
                const diagnosticEntries = Object.entries(diagnostics).filter(([, value]) => value !== null && value !== '' && value !== false)
                return (
                  <div
                    key={`${competitor.id}:${item.id}`}
                    className="rounded-2xl border border-stone-200 bg-white/80 px-4 py-4 dark:border-slate-800 dark:bg-slate-950/70"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      {renderBadge(reviewStatusLabel(item.review_status), reviewStatusTone(item.review_status))}
                      {renderBadge(item.review_reason_code, item.review_status === 'accepted' ? 'teal' : 'rose')}
                      {item.has_current_extraction
                        ? renderBadge(t('competitiveGap.competitors.review.currentExtractionReady'), 'amber')
                        : null}
                    </div>
                    <p className="mt-3 break-all text-sm font-medium text-stone-900 dark:text-slate-50">{item.url}</p>
                    {item.title ? <p className="mt-2 text-sm text-stone-700 dark:text-slate-200">{item.title}</p> : null}
                    <div className="mt-2 flex flex-wrap gap-2">
                      {item.h1 ? renderBadge(`H1: ${truncateText(item.h1, 48)}`) : null}
                      {item.meta_description ? renderBadge(`Meta: ${truncateText(item.meta_description, 48)}`) : null}
                      {renderBadge(`page_type=${item.page_type}`)}
                      {renderBadge(`bucket=${item.page_bucket}`)}
                    </div>
                    <p className="mt-3 text-sm text-stone-700 dark:text-slate-200">{item.review_reason_detail}</p>
                    {item.current_extraction_topic_label ? (
                      <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">
                        {t('competitiveGap.competitors.review.currentExtractionTopic', {
                          topic: item.current_extraction_topic_label,
                        })}
                      </p>
                    ) : null}
                    {diagnosticEntries.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {diagnosticEntries.slice(0, 8).map(([key, value]) => (
                          <span key={`${item.id}:${key}`}>
                            {renderBadge(
                              `${key}=${Array.isArray(value) ? value.join(', ') : String(value)}`,
                              item.review_status === 'accepted' ? 'stone' : 'amber',
                            )}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}

export function SiteCompetitiveGapPage({ mode = 'full' }: { mode?: CompetitiveGapPageMode }) {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const documentTitleKey = {
    full: 'documentTitle.siteCompetitiveGap',
    overview: 'documentTitle.siteCompetitiveGap',
    strategy: 'documentTitle.siteCompetitiveGapStrategy',
    competitors: 'documentTitle.siteCompetitiveGapCompetitors',
    sync: 'documentTitle.siteCompetitiveGapSync',
    results: 'documentTitle.siteCompetitiveGapResults',
  }[mode]
  useDocumentTitle(t(documentTitleKey, { domain: site.domain }))

  const [searchParams, setSearchParams] = useSearchParams()
  const gapParams = useMemo(() => readParams(searchParams, activeCrawlId), [activeCrawlId, searchParams])
  const needsGapQuery = mode === 'full' || mode === 'overview' || mode === 'sync' || mode === 'results'
  const effectiveGapParams = useMemo<SiteCompetitiveGapQueryParams>(() => {
    if (mode === 'overview') {
      return {
        ...gapParams,
        page: 1,
        page_size: 5,
        sort_by: 'priority_score',
        sort_order: 'desc',
        gap_type: undefined,
        segment: undefined,
        page_type: undefined,
        own_match_status: undefined,
        topic: undefined,
        priority_score_min: undefined,
        consensus_min: undefined,
      }
    }
    return gapParams
  }, [gapParams, mode])

  const strategyQuery = useSiteCompetitiveGapStrategyQuery(site.id)
  const competitorsQuery = useSiteCompetitiveGapCompetitorsQuery(site.id)
  const gapQuery = useSiteCompetitiveGapQuery(site.id, effectiveGapParams, needsGapQuery)

  const upsertStrategyMutation = useUpsertSiteCompetitiveGapStrategyMutation(site.id)
  const deleteStrategyMutation = useDeleteSiteCompetitiveGapStrategyMutation(site.id)
  const createCompetitorMutation = useCreateSiteCompetitiveGapCompetitorMutation(site.id)
  const updateCompetitorMutation = useUpdateSiteCompetitiveGapCompetitorMutation(site.id)
  const deleteCompetitorMutation = useDeleteSiteCompetitiveGapCompetitorMutation(site.id)
  const syncCompetitorMutation = useSyncSiteCompetitiveGapCompetitorMutation(site.id)
  const retryCompetitorSyncMutation = useRetrySiteCompetitiveGapCompetitorSyncMutation(site.id)
  const resetCompetitorSyncMutation = useResetSiteCompetitiveGapCompetitorSyncMutation(site.id)
  const syncAllCompetitorsMutation = useSyncAllSiteCompetitiveGapCompetitorsMutation(site.id)
  const rerunSemanticMatchingMutation = useRerunSiteCompetitiveGapSemanticMatchingMutation(site.id)
  const explanationMutation = useCompetitiveGapExplanationMutation(site.id)

  const [strategyInput, setStrategyInput] = useState('')
  const [newCompetitorRootUrl, setNewCompetitorRootUrl] = useState('')
  const [newCompetitorLabel, setNewCompetitorLabel] = useState('')
  const [newCompetitorNotes, setNewCompetitorNotes] = useState('')
  const [editingCompetitorId, setEditingCompetitorId] = useState<number | null>(null)
  const [editingCompetitorRootUrl, setEditingCompetitorRootUrl] = useState('')
  const [editingCompetitorLabel, setEditingCompetitorLabel] = useState('')
  const [editingCompetitorNotes, setEditingCompetitorNotes] = useState('')
  const [editingCompetitorIsActive, setEditingCompetitorIsActive] = useState(true)
  const [syncingCompetitorId, setSyncingCompetitorId] = useState<number | null>(null)
  const [retryingCompetitorId, setRetryingCompetitorId] = useState<number | null>(null)
  const [resettingCompetitorId, setResettingCompetitorId] = useState<number | null>(null)
  const [syncAllPending, setSyncAllPending] = useState(false)
  const [expandedRunHistoryIds, setExpandedRunHistoryIds] = useState<Record<number, boolean>>({})
  const [recentlyRetriedCompetitorIds, setRecentlyRetriedCompetitorIds] = useState<Record<number, boolean>>({})
  const [expandedGapKey, setExpandedGapKey] = useState<string | null>(null)
  const [loadedExplanations, setLoadedExplanations] = useState<Record<string, CompetitiveGapExplanationResponse>>({})
  const [loadingExplanationGapKey, setLoadingExplanationGapKey] = useState<string | null>(null)
  const [explanationErrors, setExplanationErrors] = useState<Record<string, string>>({})
  const [semanticActionMode, setSemanticActionMode] = useState<'resume' | 'rerun' | null>(null)
  const hadActiveRuntimeRef = useRef(false)

  useEffect(() => {
    setStrategyInput(strategyQuery.data?.raw_user_input ?? '')
  }, [strategyQuery.data?.raw_user_input])

  useEffect(() => {
    const competitors = competitorsQuery.data ?? []
    const hasActiveRuntime = competitors.some(
      (competitor) =>
        competitor.last_sync_status === 'queued' ||
        competitor.last_sync_status === 'running' ||
        competitor.semantic_status === 'queued' ||
        competitor.semantic_status === 'running',
    )
    if (!hasActiveRuntime) {
      return undefined
    }

    const intervalId = window.setInterval(() => {
      void competitorsQuery.refetch()
    }, 4_000)
    return () => window.clearInterval(intervalId)
  }, [competitorsQuery.data, competitorsQuery.refetch])

  useEffect(() => {
    const competitors = competitorsQuery.data ?? []
    const hasActiveRuntime = competitors.some(
      (competitor) =>
        competitor.last_sync_status === 'queued' ||
        competitor.last_sync_status === 'running' ||
        competitor.semantic_status === 'queued' ||
        competitor.semantic_status === 'running',
    )

    if (hadActiveRuntimeRef.current && !hasActiveRuntime) {
      void gapQuery.refetch()
    }

    hadActiveRuntimeRef.current = hasActiveRuntime
  }, [competitorsQuery.data, gapQuery.refetch])

  useEffect(() => {
    const competitors = competitorsQuery.data ?? []
    setRecentlyRetriedCompetitorIds((current) => {
      let changed = false
      const next: Record<number, boolean> = {}
      Object.entries(current).forEach(([competitorIdValue, value]) => {
        const competitorId = Number(competitorIdValue)
        const competitor = competitors.find((item) => item.id === competitorId)
        if (value && competitor && isCompetitorSyncBusy(competitor)) {
          next[competitorId] = true
        } else if (value) {
          changed = true
        }
      })
      return changed || Object.keys(current).length !== Object.keys(next).length ? next : current
    })
  }, [competitorsQuery.data])

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function updateFilter(updates: Record<string, string | number | undefined>) {
    updateParams({ ...updates, page: 1 })
  }

  function applyQuickFilter(updates: Record<string, string | number | undefined>) {
    updateFilter({ ...updates, sort_by: 'priority_score', sort_order: 'desc' })
  }

  function resetFilters() {
    updateParams({
      gsc_date_range: gapParams.gsc_date_range,
      page: 1,
      page_size: 25,
      sort_by: 'priority_score',
      sort_order: 'desc',
      gap_type: undefined,
      segment: undefined,
      page_type: undefined,
      topic: undefined,
      priority_score_min: undefined,
      consensus_min: undefined,
    })
  }

  async function handleSaveStrategy() {
    await upsertStrategyMutation.mutateAsync({ raw_user_input: strategyInput.trim() })
  }

  async function handleRerunStrategyNormalization() {
    await upsertStrategyMutation.mutateAsync({ raw_user_input: strategyInput.trim() })
  }

  async function handleRerunSemanticMatching() {
    setSemanticActionMode('rerun')
    try {
      await rerunSemanticMatchingMutation.mutateAsync({
        mode: 'full',
        active_crawl_id: activeCrawlId ?? undefined,
      })
    } catch {
      return
    } finally {
      setSemanticActionMode(null)
    }
  }

  async function handleResumeSemanticMatching() {
    setSemanticActionMode('resume')
    try {
      await rerunSemanticMatchingMutation.mutateAsync({
        mode: 'incremental',
        active_crawl_id: activeCrawlId ?? undefined,
      })
    } catch {
      return
    } finally {
      setSemanticActionMode(null)
    }
  }

  async function handleDeleteStrategy() {
    await deleteStrategyMutation.mutateAsync()
    setStrategyInput('')
  }

  async function handleCreateCompetitor() {
    await createCompetitorMutation.mutateAsync({
      root_url: newCompetitorRootUrl.trim(),
      label: newCompetitorLabel.trim() || undefined,
      notes: newCompetitorNotes.trim() || undefined,
      is_active: true,
    })
    setNewCompetitorRootUrl('')
    setNewCompetitorLabel('')
    setNewCompetitorNotes('')
  }

  async function handleSyncCompetitor(competitorId: number) {
    setSyncingCompetitorId(competitorId)
    try {
      await syncCompetitorMutation.mutateAsync(competitorId)
    } finally {
      setSyncingCompetitorId(null)
    }
  }

  async function handleSyncAllCompetitors() {
    setSyncAllPending(true)
    try {
      await syncAllCompetitorsMutation.mutateAsync()
    } finally {
      setSyncAllPending(false)
    }
  }

  async function handleRetryCompetitorSync(competitorId: number) {
    setRetryingCompetitorId(competitorId)
    try {
      await retryCompetitorSyncMutation.mutateAsync(competitorId)
      setRecentlyRetriedCompetitorIds((current) => ({ ...current, [competitorId]: true }))
      setExpandedRunHistoryIds((current) => ({ ...current, [competitorId]: true }))
    } finally {
      setRetryingCompetitorId(null)
    }
  }

  async function handleResetCompetitorSync(competitorId: number) {
    setResettingCompetitorId(competitorId)
    try {
      await resetCompetitorSyncMutation.mutateAsync(competitorId)
    } finally {
      setResettingCompetitorId(null)
    }
  }

  function toggleCompetitorRunHistory(competitorId: number) {
    setExpandedRunHistoryIds((current) => ({ ...current, [competitorId]: !current[competitorId] }))
  }

  function startEditingCompetitor(competitor: SiteCompetitor) {
    setEditingCompetitorId(competitor.id)
    setEditingCompetitorRootUrl(competitor.root_url)
    setEditingCompetitorLabel(competitor.label)
    setEditingCompetitorNotes(competitor.notes ?? '')
    setEditingCompetitorIsActive(competitor.is_active)
  }

  async function handleSaveCompetitor() {
    if (editingCompetitorId === null) {
      return
    }

    await updateCompetitorMutation.mutateAsync({
      competitorId: editingCompetitorId,
      payload: {
        root_url: editingCompetitorRootUrl.trim(),
        label: editingCompetitorLabel.trim() || undefined,
        notes: editingCompetitorNotes.trim() || undefined,
        is_active: editingCompetitorIsActive,
      },
    })
    setEditingCompetitorId(null)
  }

  async function handleExplain(row: CompetitiveGapRow, resolvedActiveCrawlId: number | null) {
    if (expandedGapKey === row.gap_key) {
      setExpandedGapKey(null)
      return
    }

    setExpandedGapKey(row.gap_key)
    if (!resolvedActiveCrawlId || loadedExplanations[row.gap_key]) {
      return
    }

    setLoadingExplanationGapKey(row.gap_key)
    setExplanationErrors((current) => {
      const next = { ...current }
      delete next[row.gap_key]
      return next
    })
    try {
      const result = await explanationMutation.mutateAsync({
        gap_key: row.gap_key,
        active_crawl_id: resolvedActiveCrawlId,
        gsc_date_range: gapParams.gsc_date_range,
      })
      setLoadedExplanations((current) => ({ ...current, [row.gap_key]: result }))
    } catch (error) {
      setExplanationErrors((current) => ({ ...current, [row.gap_key]: getUiErrorMessage(error, t) }))
    } finally {
      setLoadingExplanationGapKey(null)
    }
  }

  const quickFilters = [
    { label: t('competitiveGap.quickFilters.newTopic'), isActive: gapParams.gap_type === 'NEW_TOPIC', onClick: () => applyQuickFilter({ gap_type: 'NEW_TOPIC', segment: undefined }) },
    { label: t('competitiveGap.quickFilters.expandExisting'), isActive: gapParams.gap_type === 'EXPAND_EXISTING_TOPIC', onClick: () => applyQuickFilter({ gap_type: 'EXPAND_EXISTING_TOPIC', segment: undefined }) },
    { label: t('competitiveGap.quickFilters.supportCluster'), isActive: gapParams.gap_type === 'MISSING_SUPPORTING_PAGE', onClick: () => applyQuickFilter({ gap_type: 'MISSING_SUPPORTING_PAGE', segment: undefined }) },
    { label: t('competitiveGap.quickFilters.highPriority'), isActive: (gapParams.priority_score_min ?? 0) >= 70, onClick: () => applyQuickFilter({ priority_score_min: 70 }) },
    { label: t('competitiveGap.quickFilters.highConsensus'), isActive: (gapParams.consensus_min ?? 0) >= 60, onClick: () => applyQuickFilter({ consensus_min: 60 }) },
  ]

  if (strategyQuery.isLoading || competitorsQuery.isLoading || (needsGapQuery && gapQuery.isLoading)) {
    return <LoadingState label={t('competitiveGap.page.loading')} />
  }

  const blockingError = strategyQuery.error ?? competitorsQuery.error ?? (needsGapQuery ? gapQuery.error : null)
  if (blockingError) {
    return <ErrorState title={t('competitiveGap.errorTitle')} message={getUiErrorMessage(blockingError, t)} />
  }

  const strategy = strategyQuery.data
  const competitors = competitorsQuery.data ?? []
  const rawGapPayload = gapQuery.data ?? null

  if (needsGapQuery && !rawGapPayload) {
    return <EmptyState title={t('competitiveGap.emptyTitle')} description={t('competitiveGap.emptyDescription')} />
  }

  const resolvedModuleActiveCrawlId = rawGapPayload?.context.active_crawl_id ?? activeCrawlId ?? site.active_crawl_id ?? null
  if (!resolvedModuleActiveCrawlId) {
    return <EmptyState title={t('competitiveGap.noActiveCrawlTitle')} description={t('competitiveGap.noActiveCrawlDescription')} />
  }

  const payload: PaginatedCompetitiveGapResponse =
    rawGapPayload ?? {
      context: {
        site_id: site.id,
        site_domain: site.domain,
        active_crawl_id: resolvedModuleActiveCrawlId,
        gsc_date_range: effectiveGapParams.gsc_date_range,
        active_crawl: site.active_crawl
          ? {
              id: site.active_crawl.id,
              status: site.active_crawl.status,
              created_at: site.active_crawl.created_at,
              started_at: site.active_crawl.started_at,
              finished_at: site.active_crawl.finished_at,
              root_url: site.root_url,
            }
          : null,
        strategy_present: Boolean(strategy),
        active_competitor_count: competitors.filter((competitor) => competitor.is_active).length,
        data_readiness: {
          has_active_crawl: Boolean(resolvedModuleActiveCrawlId),
          has_strategy: Boolean(strategy),
          has_active_competitors: competitors.some((competitor) => competitor.is_active),
          gap_ready: false,
          missing_inputs: [],
          active_competitors_count: competitors.filter((competitor) => competitor.is_active).length,
          competitors_with_pages_count: competitors.filter((competitor) => competitor.pages_count > 0).length,
          competitors_with_current_extractions_count: competitors.filter((competitor) => competitor.extracted_pages_count > 0).length,
          total_competitor_pages_count: competitors.reduce((sum, competitor) => sum + competitor.pages_count, 0),
          total_current_extractions_count: competitors.reduce((sum, competitor) => sum + competitor.extracted_pages_count, 0),
        },
        semantic_diagnostics: {
          semantic_version: null,
          cluster_version: null,
          coverage_version: null,
          competitor_semantic_cards_count: 0,
          own_page_semantic_profiles_count: 0,
          canonical_pages_count: 0,
          duplicate_pages_count: 0,
          near_duplicate_pages_count: 0,
          clusters_count: 0,
          low_confidence_clusters_count: 0,
          latest_failure_stage: null,
          latest_failure_error_code: null,
          latest_failure_error_message: null,
          coverage_breakdown: {
            exact_coverage: 0,
            strong_semantic_coverage: 0,
            partial_coverage: 0,
            wrong_intent_coverage: 0,
            commercial_missing_supporting: 0,
            informational_missing_commercial: 0,
            no_meaningful_coverage: 0,
          },
        },
        empty_state_reason: null,
      },
      summary: {
        total_gaps: 0,
        high_priority_gaps: 0,
        competitors_considered: competitors.filter((competitor) => competitor.is_active).length,
        topics_covered: 0,
        counts_by_type: {
          NEW_TOPIC: 0,
          EXPAND_EXISTING_TOPIC: 0,
          MISSING_SUPPORTING_PAGE: 0,
        },
        counts_by_gap_detail_type: {
          NEW_TOPIC: 0,
          EXPAND_EXISTING_PAGE: 0,
          MISSING_SUPPORTING_CONTENT: 0,
          MISSING_MONEY_PAGE: 0,
          INTENT_MISMATCH: 0,
          FORMAT_GAP: 0,
          GEO_GAP: 0,
        },
        counts_by_coverage_type: {
          exact_coverage: 0,
          strong_semantic_coverage: 0,
          partial_coverage: 0,
          wrong_intent_coverage: 0,
          commercial_missing_supporting: 0,
          informational_missing_commercial: 0,
          no_meaningful_coverage: 0,
        },
        counts_by_page_type: {
          home: 0,
          category: 0,
          product: 0,
          service: 0,
          blog_article: 0,
          blog_index: 0,
          contact: 0,
          about: 0,
          faq: 0,
          location: 0,
          legal: 0,
          utility: 0,
          other: 0,
        },
        canonicalization_summary: {
          canonical_pages_count: 0,
          duplicate_pages_count: 0,
          near_duplicate_pages_count: 0,
          filtered_leftovers_count: 0,
        },
        cluster_quality_summary: {
          clusters_count: 0,
          low_confidence_clusters_count: 0,
          average_cluster_confidence: 0,
          average_cluster_member_count: 0,
        },
      },
      items: [],
      page: 1,
      page_size: effectiveGapParams.page_size,
      total_items: 0,
      total_pages: 1,
    }

  const readiness = payload?.context.data_readiness ?? {
    has_active_crawl: Boolean(resolvedModuleActiveCrawlId),
    has_strategy: Boolean(strategy),
    has_active_competitors: competitors.some((competitor) => competitor.is_active),
    gap_ready: false,
    missing_inputs: [],
    active_competitors_count: competitors.filter((competitor) => competitor.is_active).length,
    competitors_with_pages_count: competitors.filter((competitor) => competitor.pages_count > 0).length,
    competitors_with_current_extractions_count: competitors.filter((competitor) => competitor.extracted_pages_count > 0).length,
    total_competitor_pages_count: competitors.reduce((sum, competitor) => sum + competitor.pages_count, 0),
    total_current_extractions_count: competitors.reduce((sum, competitor) => sum + competitor.extracted_pages_count, 0),
  }
  const resolvedActiveCrawlId = payload?.context.active_crawl_id ?? activeCrawlId
  const dataSourceMode = payload?.context.data_source_mode ?? 'legacy'
  const reviewRunStatus = payload?.context.review_run_status ?? null
  const basisCrawlJobId = payload?.context.basis_crawl_job_id ?? null
  const isOutdatedForActiveCrawl = payload?.context.is_outdated_for_active_crawl ?? false
  const summaryTypeEntries = Object.entries(payload?.summary.counts_by_type ?? {}).filter(([, count]) => count > 0)
  const summaryCoverageEntries = Object.entries(payload?.summary.counts_by_coverage_type ?? {}).filter(([, count]) => count > 0)
  const semanticDiagnostics = payload?.context.semantic_diagnostics ?? {
    semantic_version: null,
    cluster_version: null,
    coverage_version: null,
    competitor_semantic_cards_count: 0,
    own_page_semantic_profiles_count: 0,
    canonical_pages_count: 0,
    duplicate_pages_count: 0,
    near_duplicate_pages_count: 0,
    clusters_count: 0,
    low_confidence_clusters_count: 0,
    latest_failure_stage: null,
    latest_failure_error_code: null,
    latest_failure_error_message: null,
    coverage_breakdown: {
      exact_coverage: 0,
      strong_semantic_coverage: 0,
      partial_coverage: 0,
      wrong_intent_coverage: 0,
      commercial_missing_supporting: 0,
      informational_missing_commercial: 0,
      no_meaningful_coverage: 0,
    },
  }
  const clusterQualitySummary = payload?.summary.cluster_quality_summary ?? {
    clusters_count: 0,
    low_confidence_clusters_count: 0,
    average_cluster_confidence: 0,
    average_cluster_member_count: 0,
  }
  const canonicalizationSummary = payload?.summary.canonicalization_summary ?? {
    canonical_pages_count: 0,
    duplicate_pages_count: 0,
    near_duplicate_pages_count: 0,
  }

  function gapTypeLabel(value: CompetitiveGapType) {
    return t(`competitiveGap.types.${value}.title`)
  }

  function sourceModeLabel(value: CompetitiveGapDataSourceMode | null | undefined) {
    return t(`competitiveGap.sourceMode.${value ?? 'legacy'}`)
  }

  function reviewDecisionLabel(value: CompetitiveGapDecisionAction | null | undefined) {
    return t(`competitiveGap.review.action.${value ?? 'keep'}`)
  }

  function gapDetailLabel(value: CompetitiveGapDetailType | null | undefined) {
    if (!value) {
      return t('competitiveGap.strategy.debug.notAvailable')
    }
    const key = `competitiveGap.typesDetail.${value}`
    const translated = t(key)
    return translated === key ? value.replaceAll('_', ' ').toLowerCase() : translated
  }

  function gapSegmentLabel(value: CompetitiveGapSegment) {
    return t(`competitiveGap.segments.${value}`)
  }

  function pageTypeLabel(value: PageType) {
    return t(`pages.taxonomy.pageTypes.${value}`)
  }

  function strategyStatusLabel(value: StrategyNormalizationStatus | null | undefined) {
    return t(`competitiveGap.strategy.status.${value ?? 'not_started'}`)
  }

  function competitorSyncStatusLabel(value: CompetitorSyncStatus | null | undefined) {
    if (value === 'not_started') {
      return t('competitiveGap.competitors.syncStatus.idle')
    }
    return t(`competitiveGap.competitors.syncStatus.${value ?? 'idle'}`)
  }

  function competitorSyncStageLabel(value: string | null | undefined) {
    return t(`competitiveGap.competitors.syncStage.${value ?? 'idle'}`)
  }

  function syncRunStatusLabel(value: string | null | undefined) {
    if (value === 'idle') {
      return t('competitiveGap.competitors.runStatus.idle')
    }
    return t(`competitiveGap.competitors.runStatus.${value ?? 'cancelled'}`)
  }

  function competitorProgressLabel(competitor: SiteCompetitor) {
    if (competitor.last_sync_stage === 'extracting' || competitor.last_sync_total_extractable_pages > 0) {
      return t('competitiveGap.competitors.progressExtracting', {
        current: competitor.last_sync_processed_extraction_pages,
        total: competitor.last_sync_total_extractable_pages,
      })
    }
    return t('competitiveGap.competitors.progressCrawling', {
      current: competitor.last_sync_processed_urls,
      total: competitor.last_sync_url_limit,
    })
  }

  function competitorUsesPartialData(competitor: SiteCompetitor) {
    return competitor.extracted_pages_count > 0
  }

  function getStrategyDebugTone() {
    if (!strategy) {
      return 'stone' as const
    }
    if (strategy.normalization_status === 'ready') {
      return 'teal' as const
    }
    if (strategy.normalization_status === 'failed') {
      return 'rose' as const
    }
    if (strategy.normalization_status === 'not_processed') {
      return 'amber' as const
    }
    return 'stone' as const
  }

  function getStrategyDebugHeadline() {
    if (!strategy) {
      return t('competitiveGap.strategy.emptyTitle')
    }
    if (strategy.normalization_status === 'ready') {
      return t('competitiveGap.strategy.debug.readyHeadline')
    }
    if (strategy.normalization_status === 'failed') {
      return t('competitiveGap.strategy.debug.failedHeadline')
    }
    if (strategy.normalization_status === 'not_processed') {
      return t('competitiveGap.strategy.debug.notProcessedHeadline')
    }
    return t('competitiveGap.strategy.emptyTitle')
  }

  function getStrategyDebugMessage() {
    if (!strategy) {
      return t('competitiveGap.strategy.emptyDescription')
    }
    return strategy.normalization_debug_message ?? t('competitiveGap.strategy.debug.notAvailable')
  }

  function getSyncErrorMessage(error: unknown) {
    if (error instanceof ApiError && error.status === 409) {
      return t('competitiveGap.competitors.errors.alreadyRunning')
    }
    return getUiErrorMessage(error, t)
  }

  function getCompetitorLastRunStatus(competitor: SiteCompetitor) {
    if (competitor.last_sync_run_id <= 0) {
      return 'idle'
    }
    if (competitor.last_sync_error_code === 'stale_run') {
      return 'stale'
    }
    if (competitor.last_sync_error_code === 'sync_cancelled') {
      return 'cancelled'
    }
    return competitor.last_sync_status
  }

  function shouldShowRetryAction(competitor: SiteCompetitor) {
    return competitor.last_sync_run_id > 0 && isRetryableRunStatus(getCompetitorLastRunStatus(competitor))
  }

  function shouldShowResetAction(competitor: SiteCompetitor) {
    return isCompetitorSyncBusy(competitor) || getCompetitorLastRunStatus(competitor) === 'stale' || competitor.last_sync_status === 'failed'
  }

  function getSyncSummaryReasonStats(competitor: SiteCompetitor): SyncReasonStat[] {
    const summary = competitor.last_sync_summary
    return [
      { key: 'filtered', count: syncSummaryCount(summary.skipped_filtered_count) },
      { key: 'lowValue', count: syncSummaryCount(summary.skipped_low_value_count) },
      { key: 'nonHtml', count: syncSummaryCount(summary.skipped_non_html_count) },
      { key: 'outOfScope', count: syncSummaryCount(summary.skipped_out_of_scope_count) },
      { key: 'duplicate', count: syncSummaryCount(summary.skipped_duplicate_url_count) },
      { key: 'fetchError', count: syncSummaryCount(summary.skipped_fetch_error_count) },
    ]
      .filter((item) => item.count > 0)
      .sort((left, right) => right.count - left.count)
  }

  function getCompetitorSyncHeadline(competitor: SiteCompetitor) {
    const summary = competitor.last_sync_summary
    const lastRunStatus = getCompetitorLastRunStatus(competitor)
    if (competitor.last_sync_status === 'queued') {
      return t('competitiveGap.competitors.syncHeadlineQueued')
    }
    if (competitor.last_sync_status === 'running') {
      return t('competitiveGap.competitors.syncHeadlineRunning', {
        visited: Math.max(competitor.last_sync_processed_urls, syncSummaryCount(summary.visited_urls_count)),
        stored: Math.max(competitor.pages_count, syncSummaryCount(summary.stored_pages_count)),
      })
    }
    if (competitor.last_sync_status === 'done') {
      return t('competitiveGap.competitors.syncHeadlineDone', {
        visited: Math.max(competitor.last_sync_processed_urls, syncSummaryCount(summary.visited_urls_count)),
        stored: Math.max(competitor.pages_count, syncSummaryCount(summary.stored_pages_count)),
        extracted: Math.max(competitor.extracted_pages_count, syncSummaryCount(summary.extracted_pages_count)),
      })
    }
    if (competitor.last_sync_status === 'failed') {
      return t('competitiveGap.competitors.syncHeadlineFailed', {
        visited: Math.max(competitor.last_sync_processed_urls, syncSummaryCount(summary.visited_urls_count)),
        stored: Math.max(competitor.pages_count, syncSummaryCount(summary.stored_pages_count)),
        extracted: Math.max(competitor.extracted_pages_count, syncSummaryCount(summary.extracted_pages_count)),
      })
    }
    if (lastRunStatus === 'stale') {
      return t('competitiveGap.competitors.syncHeadlineStale', {
        visited: Math.max(competitor.last_sync_processed_urls, syncSummaryCount(summary.visited_urls_count)),
        stored: Math.max(competitor.pages_count, syncSummaryCount(summary.stored_pages_count)),
        extracted: Math.max(competitor.extracted_pages_count, syncSummaryCount(summary.extracted_pages_count)),
      })
    }
    if (lastRunStatus === 'cancelled') {
      return t('competitiveGap.competitors.syncHeadlineCancelled')
    }
    return t('competitiveGap.competitors.syncHeadlineIdle')
  }

  function getCompetitorSyncButtonLabel(competitor: SiteCompetitor) {
    if (competitor.last_sync_status === 'queued') {
      return t('competitiveGap.competitors.syncQueued')
    }
    if (competitor.last_sync_status === 'running') {
      return t('competitiveGap.competitors.syncRunning')
    }
    return syncingCompetitorId === competitor.id ? t('competitiveGap.competitors.syncing') : t('competitiveGap.competitors.sync')
  }

  function getCompetitorSyncSummaryTitle(competitor: SiteCompetitor) {
    const lastRunStatus = getCompetitorLastRunStatus(competitor)
    if (competitor.last_sync_status === 'failed' && competitor.extracted_pages_count > 0) {
      return t('competitiveGap.competitors.summaryPartial')
    }
    if (competitor.last_sync_status === 'failed') {
      return t('competitiveGap.competitors.summaryFailed')
    }
    if (competitor.last_sync_status === 'done') {
      return t('competitiveGap.competitors.summaryDone')
    }
    if (isCompetitorSyncBusy(competitor)) {
      return t('competitiveGap.competitors.summaryInProgress')
    }
    if (lastRunStatus === 'stale') {
      return t('competitiveGap.competitors.summaryStale')
    }
    if (lastRunStatus === 'cancelled') {
      return t('competitiveGap.competitors.summaryCancelled')
    }
    return t('competitiveGap.competitors.summaryIdle')
  }

  function getReadinessMessage() {
    if (!readiness.has_strategy) {
      return t('competitiveGap.readiness.strategyMissing')
    }
    if (!readiness.gap_ready) {
      return t('competitiveGap.readiness.notReady')
    }
    return t('competitiveGap.readiness.ready')
  }

  function semanticStatusLabel(value: CompetitiveGapSemanticStatus | null | undefined) {
    return t(`competitiveGap.semantic.status.${value ?? 'not_started'}`)
  }

  function semanticAnalysisModeLabel(value: CompetitiveGapSemanticAnalysisMode | null | undefined) {
    return t(`competitiveGap.semantic.analysisMode.${value ?? 'not_started'}`)
  }

  function semanticRuntimeStateLabel(value: SemanticRuntimeState) {
    return t(`competitiveGap.readiness.semanticDebug.runtimeState.${value}`)
  }

  function semanticStageLabel(value: string | null | undefined) {
    if (!value) {
      return t('competitiveGap.strategy.debug.notAvailable')
    }
    const key = `competitiveGap.semantic.stage.${value}`
    const translated = t(key)
    return translated === key ? value : translated
  }

  function semanticMatchLabel(value: CompetitiveGapSemanticMatchStatus | null | undefined) {
    if (!value) {
      return t('competitiveGap.strategy.debug.notAvailable')
    }
    return t(`competitiveGap.semantic.matchStatus.${value ?? 'no_meaningful_match'}`)
  }

  function coverageTypeLabel(value: CompetitiveGapCoverageType | null | undefined) {
    if (!value) {
      return t('competitiveGap.strategy.debug.notAvailable')
    }
    const key = `competitiveGap.semantic.coverageType.${value}`
    const translated = t(key)
    return translated === key ? value.replaceAll('_', ' ').toLowerCase() : translated
  }

  function formatFitScore(value: number | null | undefined) {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return null
    }
    return `${Math.round(value)}/100`
  }

  function coverageTypeTone(value: CompetitiveGapCoverageType | null | undefined) {
    if (value === 'exact_coverage' || value === 'strong_semantic_coverage') {
      return 'teal' as const
    }
    if (value === 'partial_coverage') {
      return 'stone' as const
    }
    if (value === 'wrong_intent_coverage' || value === 'commercial_missing_supporting' || value === 'informational_missing_commercial') {
      return 'amber' as const
    }
    if (value === 'no_meaningful_coverage') {
      return 'rose' as const
    }
    return 'stone' as const
  }

  function gapDetailTone(value: CompetitiveGapDetailType | null | undefined) {
    if (value === 'NEW_TOPIC' || value === 'MISSING_MONEY_PAGE') {
      return 'teal' as const
    }
    if (value === 'INTENT_MISMATCH' || value === 'FORMAT_GAP' || value === 'GEO_GAP') {
      return 'amber' as const
    }
    return 'stone' as const
  }

  function getCompetitorSemanticAnalysisMode(competitor: SiteCompetitor): CompetitiveGapSemanticAnalysisMode {
    if (
      competitor.semantic_analysis_mode === 'not_started' ||
      competitor.semantic_analysis_mode === 'local_only' ||
      competitor.semantic_analysis_mode === 'llm_only' ||
      competitor.semantic_analysis_mode === 'mixed'
    ) {
      return competitor.semantic_analysis_mode
    }

    const semanticStatus = competitor.semantic_status ?? 'not_started'
    const semanticCandidatesCount = competitor.semantic_candidates_count ?? 0
    const semanticLlmJobsCount = competitor.semantic_llm_jobs_count ?? 0
    const semanticCacheHits = competitor.semantic_cache_hits ?? 0
    const semanticFallbackCount = competitor.semantic_fallback_count ?? 0
    const semanticLlmMergedUrlsCount = competitor.semantic_llm_merged_urls_count ?? 0
    const hasLlm = semanticLlmJobsCount > 0 || semanticCacheHits > 0 || semanticLlmMergedUrlsCount > 0
    const hasLocal = semanticFallbackCount > 0
    if (hasLlm && hasLocal) {
      return 'mixed'
    }
    if (hasLlm) {
      return 'llm_only'
    }
    if (hasLocal || (semanticCandidatesCount > 0 && ['ready', 'partial', 'failed', 'stale', 'cancelled'].includes(semanticStatus))) {
      return 'local_only'
    }
    return 'not_started'
  }

  function getAggregatedSemanticStatus(activeCompetitorsList: SiteCompetitor[]): CompetitiveGapSemanticStatus {
    const statuses = activeCompetitorsList.map((competitor) => competitor.semantic_status ?? 'not_started')
    if (!statuses.length || statuses.every((status) => status === 'not_started')) {
      return 'not_started'
    }
    if (statuses.some((status) => status === 'running')) {
      return 'running'
    }
    if (statuses.some((status) => status === 'queued')) {
      return 'queued'
    }
    if (statuses.every((status) => status === 'ready' || status === 'completed')) {
      return 'ready'
    }
    if (statuses.some((status) => status === 'failed')) {
      return statuses.some((status) => status === 'ready' || status === 'partial' || status === 'completed')
        ? 'partial'
        : 'failed'
    }
    if (statuses.some((status) => status === 'partial' || status === 'stale' || status === 'cancelled')) {
      return 'partial'
    }
    if (statuses.some((status) => status === 'ready' || status === 'completed')) {
      return 'partial'
    }
    return 'not_started'
  }

  function buildSemanticReadinessSummary(activeCompetitorsList: SiteCompetitor[]): SemanticReadinessSummary {
    const status = getAggregatedSemanticStatus(activeCompetitorsList)
    const activeRuntimeCompetitors = activeCompetitorsList.filter(
      (competitor) => competitor.semantic_status === 'queued' || competitor.semantic_status === 'running',
    )
    const runtimeState: SemanticRuntimeState = activeRuntimeCompetitors.some(
      (competitor) => competitor.semantic_status === 'running',
    )
      ? 'working'
      : activeRuntimeCompetitors.some((competitor) => competitor.semantic_status === 'queued')
        ? 'queued'
        : activeCompetitorsList.some((competitor) =>
            ['failed', 'stale', 'cancelled', 'partial'].includes(competitor.semantic_status ?? 'not_started'),
          )
          ? 'stopped'
          : 'idle'
    const analysisModes = activeCompetitorsList.map((competitor) => getCompetitorSemanticAnalysisMode(competitor))
    const hasLlm = analysisModes.some((mode) => mode === 'llm_only' || mode === 'mixed')
    const hasLocal = analysisModes.some((mode) => mode === 'local_only' || mode === 'mixed')
    const analysisMode: CompetitiveGapSemanticAnalysisMode = hasLlm && hasLocal
      ? 'mixed'
      : hasLlm
        ? 'llm_only'
        : hasLocal
          ? 'local_only'
          : 'not_started'

    const candidatesCount = activeCompetitorsList.reduce((sum, competitor) => sum + (competitor.semantic_candidates_count ?? 0), 0)
    const resolvedCount = activeCompetitorsList.reduce((sum, competitor) => sum + (competitor.semantic_resolved_count ?? 0), 0)
    const progressWeightedSum = activeCompetitorsList.reduce((sum, competitor) => {
      const competitorCandidatesCount = competitor.semantic_candidates_count ?? 0
      if (competitorCandidatesCount <= 0) {
        return sum
      }
      const fallbackProgressPercent = Math.max(
        0,
        Math.min(
          100,
          Math.round(((competitor.semantic_resolved_count ?? 0) / competitorCandidatesCount) * 100),
        ),
      )
      const competitorProgressPercent = competitor.semantic_progress_percent ?? fallbackProgressPercent
      return sum + competitorCandidatesCount * competitorProgressPercent
    }, 0)
    const progressPercent =
      candidatesCount > 0
        ? Math.max(0, Math.min(100, Math.round(progressWeightedSum / candidatesCount)))
        : status === 'ready'
          ? 100
          : 0

    const withTimestamp = activeCompetitorsList.map((competitor) => {
      const finishedAt = competitor.last_semantic_run_finished_at ? Date.parse(competitor.last_semantic_run_finished_at) : Number.NaN
      const startedAt = competitor.last_semantic_run_started_at ? Date.parse(competitor.last_semantic_run_started_at) : Number.NaN
      return {
        competitor,
        startedAt,
        finishedAt,
        eventAt: Number.isFinite(finishedAt) ? finishedAt : Number.isFinite(startedAt) ? startedAt : Number.NEGATIVE_INFINITY,
      }
    })
    const latestRunMeta = withTimestamp.reduce<(typeof withTimestamp)[number] | null>((latest, current) => {
      if (current.eventAt <= Number.NEGATIVE_INFINITY) {
        return latest
      }
      if (!latest || current.eventAt > latest.eventAt) {
        return current
      }
      return latest
    }, null)
    const latestErrorMeta = withTimestamp.reduce<(typeof withTimestamp)[number] | null>((latest, current) => {
      if (!current.competitor.last_semantic_error || current.eventAt <= Number.NEGATIVE_INFINITY) {
        return latest
      }
      if (!latest || current.eventAt > latest.eventAt) {
        return current
      }
      return latest
    }, null)
    const runtimeWithTimestamp = activeRuntimeCompetitors.map((competitor) => {
      const heartbeatAt = competitor.last_semantic_heartbeat_at ? Date.parse(competitor.last_semantic_heartbeat_at) : Number.NaN
      const startedAt = competitor.last_semantic_run_started_at ? Date.parse(competitor.last_semantic_run_started_at) : Number.NaN
      return {
        competitor,
        eventAt: Number.isFinite(heartbeatAt) ? heartbeatAt : Number.isFinite(startedAt) ? startedAt : Number.NEGATIVE_INFINITY,
      }
    })
    const latestRuntimeMeta = runtimeWithTimestamp.reduce<(typeof runtimeWithTimestamp)[number] | null>((latest, current) => {
      if (current.eventAt <= Number.NEGATIVE_INFINITY) {
        return latest
      }
      if (!latest || current.eventAt > latest.eventAt) {
        return current
      }
      return latest
    }, null)

    return {
      status,
      analysisMode,
      runtimeState,
      activeRunsCount: activeRuntimeCompetitors.length,
      currentStage: latestRuntimeMeta?.competitor.last_semantic_stage ?? latestRunMeta?.competitor.last_semantic_stage ?? null,
      currentBatchCandidatesCount: activeRuntimeCompetitors.reduce(
        (sum, competitor) => sum + (competitor.semantic_run_scope_candidates_count ?? 0),
        0,
      ),
      currentBatchResolvedCount: activeRuntimeCompetitors.reduce(
        (sum, competitor) => sum + (competitor.semantic_run_scope_resolved_count ?? 0),
        0,
      ),
      lastHeartbeatAt: latestRuntimeMeta?.competitor.last_semantic_heartbeat_at ?? null,
      leaseExpiresAt: latestRuntimeMeta?.competitor.last_semantic_lease_expires_at ?? null,
      candidatesCount,
      resolvedCount,
      progressPercent,
      llmJobsCount: activeCompetitorsList.reduce((sum, competitor) => sum + (competitor.semantic_llm_jobs_count ?? 0), 0),
      cacheHits: activeCompetitorsList.reduce((sum, competitor) => sum + (competitor.semantic_cache_hits ?? 0), 0),
      fallbackCount: activeCompetitorsList.reduce((sum, competitor) => sum + (competitor.semantic_fallback_count ?? 0), 0),
      llmMergedUrlsCount: activeCompetitorsList.reduce((sum, competitor) => sum + (competitor.semantic_llm_merged_urls_count ?? 0), 0),
      lastRunStartedAt: latestRunMeta?.competitor.last_semantic_run_started_at ?? null,
      lastRunFinishedAt: latestRunMeta?.competitor.last_semantic_run_finished_at ?? null,
      lastError: latestErrorMeta?.competitor.last_semantic_error ?? null,
      model: latestRunMeta?.competitor.semantic_model ?? null,
      promptVersion: latestRunMeta?.competitor.semantic_prompt_version ?? null,
    }
  }

  function getSemanticReadinessHeadline(summary: SemanticReadinessSummary) {
    if (summary.status === 'ready') {
      return t('competitiveGap.readiness.semanticDebug.readyHeadline')
    }
    if (summary.status === 'running' || summary.status === 'queued') {
      return t('competitiveGap.readiness.semanticDebug.runningHeadline')
    }
    if (summary.status === 'failed') {
      return t('competitiveGap.readiness.semanticDebug.failedHeadline')
    }
    if (summary.status === 'partial') {
      return t('competitiveGap.readiness.semanticDebug.partialHeadline')
    }
    return t('competitiveGap.readiness.semanticDebug.notStartedHeadline')
  }

  function getSemanticReadinessMessage(summary: SemanticReadinessSummary) {
    if (summary.status === 'not_started') {
      return t('competitiveGap.readiness.semanticDebug.notStartedMessage')
    }
    if (summary.analysisMode === 'llm_only') {
      return t('competitiveGap.readiness.semanticDebug.llmMessage', {
        count: summary.llmMergedUrlsCount,
      })
    }
    if (summary.analysisMode === 'mixed') {
      return t('competitiveGap.readiness.semanticDebug.mixedMessage', {
        count: summary.llmMergedUrlsCount,
      })
    }
    return t('competitiveGap.readiness.semanticDebug.localMessage')
  }

  function getSemanticRuntimeHint(summary: SemanticReadinessSummary) {
    if (summary.runtimeState === 'working') {
      return t('competitiveGap.readiness.semanticDebug.runtimeHintWorking')
    }
    if (summary.runtimeState === 'queued') {
      return t('competitiveGap.readiness.semanticDebug.runtimeHintQueued')
    }
    if (summary.runtimeState === 'stopped' && summary.lastError) {
      return t('competitiveGap.readiness.semanticDebug.runtimeHintStoppedWithError')
    }
    if (summary.runtimeState === 'stopped') {
      return t('competitiveGap.readiness.semanticDebug.runtimeHintStopped')
    }
    return null
  }

  function getGapEmptyStateCopy(reason: CompetitiveGapEmptyStateReason | null): EmptyStateCopy {
    if (reason === 'no_competitors') {
      return {
        title: t('competitiveGap.emptyStates.noCompetitorsTitle'),
        description: t('competitiveGap.emptyStates.noCompetitorsDescription'),
        tone: 'amber',
      }
    }
    if (reason === 'no_competitor_pages') {
      return {
        title: t('competitiveGap.emptyStates.noCompetitorPagesTitle'),
        description: t('competitiveGap.emptyStates.noCompetitorPagesDescription'),
        tone: 'amber',
      }
    }
    if (reason === 'no_competitor_extractions') {
      return {
        title: t('competitiveGap.emptyStates.noCompetitorExtractionsTitle'),
        description: t('competitiveGap.emptyStates.noCompetitorExtractionsDescription'),
        tone: 'amber',
      }
    }
    if (reason === 'no_own_pages') {
      return {
        title: t('competitiveGap.emptyStates.noOwnPagesTitle'),
        description: t('competitiveGap.emptyStates.noOwnPagesDescription'),
        tone: 'rose',
      }
    }
    if (reason === 'filters_excluded_all') {
      return {
        title: t('competitiveGap.emptyStates.filtersExcludedTitle'),
        description: t('competitiveGap.emptyStates.filtersExcludedDescription'),
        tone: 'stone',
      }
    }
    return {
      title: t('competitiveGap.emptyStates.noRealGapsTitle'),
      description: t('competitiveGap.emptyStates.noRealGapsDescription'),
      tone: 'teal',
    }
  }

  const strategyHints = strategy?.normalized_strategy_json
    ? [
        ...strategy.normalized_strategy_json.priority_topics.map((value) => ({ label: value, tone: 'teal' as const })),
        ...strategy.normalized_strategy_json.priority_page_types.map((value) => ({ label: pageTypeLabel(value), tone: 'amber' as const })),
        ...strategy.normalized_strategy_json.primary_goals.map((value) => ({ label: value, tone: 'stone' as const })),
      ].slice(0, 8)
    : []
  const activeCompetitors = competitors.filter((competitor) => competitor.is_active)
  const semanticReadiness = buildSemanticReadinessSummary(activeCompetitors)
  const allActiveCompetitorsBusy =
    activeCompetitors.length > 0 && activeCompetitors.every((competitor) => isCompetitorSyncBusy(competitor))
  const gapEmptyState = payload.items.length === 0 ? getGapEmptyStateCopy(payload.context.empty_state_reason) : null
  const viewCopy = {
    full: {
      title: t('competitiveGap.page.title'),
      description: t('competitiveGap.page.description', {
        active: formatCrawlDateTime(payload.context.active_crawl ?? site.active_crawl ?? null),
      }),
    },
    overview: {
      title: t('competitiveGap.views.overview.title'),
      description: t('competitiveGap.views.overview.description', {
        active: formatCrawlDateTime(payload.context.active_crawl ?? site.active_crawl ?? null),
      }),
    },
    strategy: {
      title: t('competitiveGap.views.strategy.title'),
      description: t('competitiveGap.views.strategy.description'),
    },
    competitors: {
      title: t('competitiveGap.views.competitors.title'),
      description: t('competitiveGap.views.competitors.description'),
    },
    sync: {
      title: t('competitiveGap.views.sync.title'),
      description: t('competitiveGap.views.sync.description', {
        active: formatCrawlDateTime(payload.context.active_crawl ?? site.active_crawl ?? null),
      }),
    },
    results: {
      title: t('competitiveGap.views.results.title'),
      description: t('competitiveGap.views.results.description', {
        active: formatCrawlDateTime(payload.context.active_crawl ?? site.active_crawl ?? null),
      }),
    },
  }[mode]
  const showWorkspaceSummary = mode === 'full' || mode === 'overview' || mode === 'sync' || mode === 'results'
  const showReadinessSection = mode === 'full' || mode === 'overview' || mode === 'sync'
  const showStrategySection = mode === 'full' || mode === 'strategy'
  const showCompetitorsSection = mode === 'full' || mode === 'competitors'
  const showSyncSection = mode === 'full' || mode === 'sync'
  const showResultsSection = mode === 'full' || mode === 'results'
  const showOverviewTopFive = mode === 'overview'
  const showOverviewShortcuts = mode === 'overview'
  const showReviewRunsSection = needsGapQuery && (mode === 'full' || mode === 'sync')
  const overviewItems = payload.items.slice(0, 5)
  const readinessItems = [
    {
      label: t('competitiveGap.readiness.activeCrawl'),
      value: readiness.has_active_crawl
        ? t('competitiveGap.readiness.readyShort')
        : t('competitiveGap.readiness.missingShort'),
      badgeLabel: readiness.has_active_crawl
        ? t('competitiveGap.readiness.readyShort')
        : t('competitiveGap.readiness.missingShort'),
      tone: readiness.has_active_crawl ? ('teal' as const) : ('rose' as const),
    },
    {
      label: t('competitiveGap.readiness.strategy'),
      value: readiness.has_strategy
        ? t('competitiveGap.readiness.readyShort')
        : t('competitiveGap.readiness.optionalShort'),
      badgeLabel: readiness.has_strategy
        ? t('competitiveGap.readiness.readyShort')
        : t('competitiveGap.readiness.optionalShort'),
      tone: readiness.has_strategy ? ('teal' as const) : ('amber' as const),
    },
    {
      label: t('competitiveGap.readiness.competitors'),
      value: readiness.active_competitors_count,
      badgeLabel:
        readiness.active_competitors_count > 0
          ? t('competitiveGap.readiness.readyShort')
          : t('competitiveGap.readiness.missingShort'),
      tone: readiness.has_active_competitors ? ('teal' as const) : ('amber' as const),
    },
    {
      label: t('competitiveGap.readiness.pages'),
      value: readiness.total_competitor_pages_count,
      badgeLabel:
        readiness.total_competitor_pages_count > 0
          ? t('competitiveGap.readiness.readyShort')
          : t('competitiveGap.readiness.missingShort'),
      tone: readiness.total_competitor_pages_count > 0 ? ('teal' as const) : ('amber' as const),
    },
    {
      label: t('competitiveGap.readiness.extractions'),
      value: readiness.total_current_extractions_count,
      badgeLabel:
        readiness.total_current_extractions_count > 0
          ? t('competitiveGap.readiness.readyShort')
          : t('competitiveGap.readiness.missingShort'),
      tone: readiness.total_current_extractions_count > 0 ? ('teal' as const) : ('amber' as const),
    },
  ]

  return (
    <div className="space-y-6">
      <section className={surfaceClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700 dark:text-teal-300">{t('competitiveGap.page.eyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950 dark:text-slate-50">{viewCopy.title}</h1>
            <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
              {viewCopy.description}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {renderBadge(
                t('competitiveGap.sourceModeBadge', { mode: sourceModeLabel(dataSourceMode) }),
                contentGapSourceModeTone(dataSourceMode),
              )}
              {reviewRunStatus ? renderBadge(t('competitiveGap.review.runStatusBadge', { status: reviewRunStatus }), reviewRunStatusTone(reviewRunStatus)) : null}
              {basisCrawlJobId ? renderBadge(t('competitiveGap.review.basisCrawlBadge', { crawlId: basisCrawlJobId })) : null}
            </div>
          </div>
        <div className="flex flex-wrap gap-2">
          {mode === 'full' || mode === 'sync' || mode === 'results' ? (
            <button type="button" onClick={() => void gapQuery.refetch()} className={actionClass}>
              {t('competitiveGap.page.refresh')}
            </button>
          ) : null}
          {mode === 'overview' ? (
            <>
              <Link to={buildSiteCompetitiveGapStrategyPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
                {t('competitiveGap.nav.strategy')}
              </Link>
              <Link to={buildSiteCompetitiveGapCompetitorsPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
                {t('competitiveGap.nav.competitors')}
              </Link>
              <Link to={buildSiteCompetitiveGapSyncPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
                {t('competitiveGap.nav.sync')}
              </Link>
            </>
          ) : null}
          {mode === 'competitors' ? (
            <Link to={buildSiteCompetitiveGapSyncPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
              {t('competitiveGap.nav.sync')}
            </Link>
          ) : null}
          {mode === 'sync' || mode === 'full' ? (
            <>
              <button
                type="button"
                onClick={() => void handleResumeSemanticMatching()}
                disabled={rerunSemanticMatchingMutation.isPending || !activeCrawlId}
                className={actionClass}
              >
                {rerunSemanticMatchingMutation.isPending && semanticActionMode === 'resume'
                  ? t('competitiveGap.semantic.resumePending')
                  : t('competitiveGap.semantic.resume')}
              </button>
              <button
                type="button"
                onClick={() => void handleRerunSemanticMatching()}
                disabled={rerunSemanticMatchingMutation.isPending || !activeCrawlId}
                className={actionClass}
              >
                {rerunSemanticMatchingMutation.isPending && semanticActionMode === 'rerun'
                  ? t('competitiveGap.semantic.rerunPending')
                  : t('competitiveGap.semantic.rerun')}
              </button>
            </>
          ) : null}
          {mode === 'strategy' || mode === 'competitors' || mode === 'sync' || mode === 'overview' ? (
            <Link to={buildSiteCompetitiveGapResultsPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
              {t('competitiveGap.nav.results')}
            </Link>
          ) : null}
          {mode === 'overview' ? (
            <Link
              to={buildSiteCompetitiveGapSemstormDiscoveryPath(site.id, { activeCrawlId, baselineCrawlId })}
              className={actionClass}
            >
              {t('competitiveGap.nav.semstormDiscovery')}
            </Link>
          ) : null}
          {mode !== 'results' ? (
            <Link to={buildSitePagesRecordsPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
              {t('competitiveGap.page.openPages')}
            </Link>
          ) : (
            <Link to={buildSiteCompetitiveGapSyncPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
              {t('competitiveGap.nav.sync')}
            </Link>
          )}
          {mode === 'results' || mode === 'full' ? (
            <a href={buildExportHref(site.id, gapParams)} className={actionClass}>
              {t('competitiveGap.page.export')}
            </a>
          ) : null}
        </div>
      </div>
      {rerunSemanticMatchingMutation.isError ? (
        <p className="mt-3 text-sm text-rose-700">
          {getSyncErrorMessage(rerunSemanticMatchingMutation.error)}
        </p>
      ) : null}
      {isOutdatedForActiveCrawl ? (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
          <p className="font-medium">{t('competitiveGap.review.outdatedTitle')}</p>
          <p className="mt-1">
            {t('competitiveGap.review.outdatedMessage', {
              activeCrawlId: payload.context.active_crawl_id ?? t('competitiveGap.strategy.debug.notAvailable'),
              basisCrawlId: basisCrawlJobId ?? t('competitiveGap.strategy.debug.notAvailable'),
            })}
          </p>
        </div>
      ) : null}
    </section>

      {showWorkspaceSummary ? (
        <SummaryCards
          items={[
            { label: t('competitiveGap.summary.totalGaps'), value: payload.summary.total_gaps },
            { label: t('competitiveGap.summary.highPriority'), value: payload.summary.high_priority_gaps },
            { label: t('competitiveGap.summary.topicsCovered'), value: payload.summary.topics_covered },
            { label: t('competitiveGap.summary.competitors'), value: payload.summary.competitors_considered },
            { label: t('competitiveGap.summary.strategyStatus'), value: strategyStatusLabel(strategy?.normalization_status), hint: strategy ? formatDateTime(strategy.last_normalization_attempt_at ?? strategy.normalized_at ?? strategy.updated_at) : t('competitiveGap.strategy.noStrategy') },
            { label: t('competitiveGap.summary.range'), value: gapParams.gsc_date_range === 'last_90_days' ? '90d' : '28d' },
            { label: t('competitiveGap.summary.activeCrawl'), value: `#${payload.context.active_crawl_id}` },
            { label: t('competitiveGap.summary.visibleRecommendations'), value: payload.total_items },
          ]}
        />
      ) : null}

      {showOverviewShortcuts ? (
        <section className={sectionClass}>
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                {t('competitiveGap.overview.shortcutsTitle')}
              </h2>
              <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                {t('competitiveGap.overview.shortcutsDescription')}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Link
              to={buildSiteCompetitiveGapStrategyPath(site.id, { activeCrawlId, baselineCrawlId })}
              className={panelClass}
            >
              <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                {t('competitiveGap.nav.strategy')}
              </p>
              <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
                {strategy ? strategyStatusLabel(strategy.normalization_status) : t('competitiveGap.strategy.noStrategy')}
              </p>
            </Link>
            <Link
              to={buildSiteCompetitiveGapCompetitorsPath(site.id, { activeCrawlId, baselineCrawlId })}
              className={panelClass}
            >
              <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                {t('competitiveGap.nav.competitors')}
              </p>
              <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
                {t('competitiveGap.competitors.count', { count: competitors.length })}
              </p>
            </Link>
            <Link
              to={buildSiteCompetitiveGapSyncPath(site.id, { activeCrawlId, baselineCrawlId })}
              className={panelClass}
            >
              <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                {t('competitiveGap.nav.sync')}
              </p>
              <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
                {semanticStatusLabel(semanticReadiness.status)}
              </p>
            </Link>
            <Link
              to={buildSiteCompetitiveGapResultsPath(site.id, { activeCrawlId, baselineCrawlId })}
              className={panelClass}
            >
              <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                {t('competitiveGap.nav.results')}
              </p>
              <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
                {t('competitiveGap.summary.totalGaps')}: {payload.summary.total_gaps}
              </p>
            </Link>
            <Link
              to={buildSiteCompetitiveGapSemstormDiscoveryPath(site.id, { activeCrawlId, baselineCrawlId })}
              className={panelClass}
            >
              <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                {t('competitiveGap.nav.semstormDiscovery')}
              </p>
              <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
                {t('competitiveGap.semstorm.overview.discoveryShortcut')}
              </p>
            </Link>
            <Link
              to={buildSiteCompetitiveGapSemstormOpportunitiesPath(site.id, { activeCrawlId, baselineCrawlId })}
              className={panelClass}
            >
              <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                {t('competitiveGap.nav.semstormOpportunities')}
              </p>
              <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
                {t('competitiveGap.semstorm.overview.opportunitiesShortcut')}
              </p>
            </Link>
          </div>
        </section>
      ) : null}

      {showReviewRunsSection ? (
        <ContentGapReviewRunsPanel
          siteId={site.id}
          activeCrawlId={payload.context.active_crawl_id ?? activeCrawlId}
          enabled
        />
      ) : null}

      {showReadinessSection ? (
      <section className={sectionClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{t('competitiveGap.readiness.title')}</h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{getReadinessMessage()}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {readiness.gap_ready
              ? renderBadge(t('competitiveGap.readiness.readyBadge'), 'teal')
              : renderBadge(t('competitiveGap.readiness.needsInputBadge'), 'amber')}
            {!readiness.has_strategy ? renderBadge(t('competitiveGap.readiness.strategyOptionalBadge'), 'amber') : null}
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {readinessItems.map((item) => (
            <div key={item.label} className={panelClass}>
              <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{item.label}</p>
              <div className="mt-2 flex items-center gap-2">
                <p className="text-lg font-semibold text-stone-950 dark:text-slate-50">{item.value}</p>
                {renderBadge(item.badgeLabel, item.tone)}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4">
          <div className={panelClass}>
            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
              {t('competitiveGap.readiness.semanticDebug.title')}
            </p>
            <div className={`mt-3 rounded-2xl border px-4 py-3 ${toneClass(semanticStatusTone(semanticReadiness.status))}`}>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold">{getSemanticReadinessHeadline(semanticReadiness)}</p>
                {renderBadge(semanticStatusLabel(semanticReadiness.status), semanticStatusTone(semanticReadiness.status))}
                {renderBadge(
                  semanticRuntimeStateLabel(semanticReadiness.runtimeState),
                  semanticRuntimeStateTone(semanticReadiness.runtimeState),
                )}
                {renderBadge(
                  semanticAnalysisModeLabel(semanticReadiness.analysisMode),
                  semanticAnalysisModeTone(semanticReadiness.analysisMode),
                )}
                {renderBadge(
                  t('competitiveGap.readiness.semanticDebug.progressBadge', {
                    percent: semanticReadiness.progressPercent,
                  }),
                  semanticReadiness.status === 'ready' ? 'teal' : 'amber',
                )}
                {semanticReadiness.llmMergedUrlsCount > 0
                  ? renderBadge(
                      t('competitiveGap.readiness.semanticDebug.mergedUrlsBadge', {
                        count: semanticReadiness.llmMergedUrlsCount,
                      }),
                      'teal',
                    )
                  : null}
              </div>
              <p className="mt-2 text-sm">{getSemanticReadinessMessage(semanticReadiness)}</p>
              {getSemanticRuntimeHint(semanticReadiness) ? (
                <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">{getSemanticRuntimeHint(semanticReadiness)}</p>
              ) : null}
            </div>

            <dl className="mt-3 grid gap-3 text-sm text-stone-700 sm:grid-cols-2 xl:grid-cols-4 dark:text-slate-300">
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.runtimeStatus')}
                </dt>
                <dd>{semanticRuntimeStateLabel(semanticReadiness.runtimeState)}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.currentStage')}
                </dt>
                <dd>{semanticStageLabel(semanticReadiness.currentStage)}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.activeRuns')}
                </dt>
                <dd>{semanticReadiness.activeRunsCount}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.currentBatch')}
                </dt>
                <dd>
                  {semanticReadiness.activeRunsCount > 0
                    ? `${semanticReadiness.currentBatchResolvedCount} / ${semanticReadiness.currentBatchCandidatesCount}`
                    : t('competitiveGap.strategy.debug.notAvailable')}
                </dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.lastRunStarted')}
                </dt>
                <dd>
                  {semanticReadiness.lastRunStartedAt
                    ? formatDateTime(semanticReadiness.lastRunStartedAt)
                    : t('competitiveGap.strategy.debug.notAvailable')}
                </dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.lastRunFinished')}
                </dt>
                <dd>
                  {semanticReadiness.lastRunFinishedAt
                    ? formatDateTime(semanticReadiness.lastRunFinishedAt)
                    : t('competitiveGap.strategy.debug.notAvailable')}
                </dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.lastHeartbeat')}
                </dt>
                <dd>
                  {semanticReadiness.lastHeartbeatAt
                    ? formatDateTime(semanticReadiness.lastHeartbeatAt)
                    : t('competitiveGap.strategy.debug.notAvailable')}
                </dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.leaseExpires')}
                </dt>
                <dd>
                  {semanticReadiness.leaseExpiresAt
                    ? formatDateTime(semanticReadiness.leaseExpiresAt)
                    : t('competitiveGap.strategy.debug.notAvailable')}
                </dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.mergedUrls')}
                </dt>
                <dd>{semanticReadiness.llmMergedUrlsCount}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.candidates')}
                </dt>
                <dd>{semanticReadiness.candidatesCount}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.resolved')}
                </dt>
                <dd>{semanticReadiness.resolvedCount}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.progress')}
                </dt>
                <dd>{semanticReadiness.progressPercent}%</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.llmJobs')}
                </dt>
                <dd>{semanticReadiness.llmJobsCount}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.cacheHits')}
                </dt>
                <dd>{semanticReadiness.cacheHits}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.fallbackCount')}
                </dt>
                <dd>{semanticReadiness.fallbackCount}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.model')}
                </dt>
                <dd>{semanticReadiness.model ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.promptVersion')}
                </dt>
                <dd>{semanticReadiness.promptVersion ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
              </div>
              <div className="space-y-1 sm:col-span-2 xl:col-span-2">
                <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                  {t('competitiveGap.readiness.semanticDebug.lastError')}
                </dt>
                <dd>{semanticReadiness.lastError ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>
      ) : null}

      {showOverviewTopFive ? (
        <section className={sectionClass}>
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{t('competitiveGap.overview.topFiveTitle')}</h2>
              <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.overview.topFiveDescription')}</p>
            </div>
            <Link to={buildSiteCompetitiveGapResultsPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
              {t('competitiveGap.overview.openResults')}
            </Link>
          </div>

          {overviewItems.length === 0 ? (
            <div className="mt-4">
              <EmptyState title={t('competitiveGap.emptyTitle')} description={t('competitiveGap.emptyDescription')} />
            </div>
          ) : (
            <div className="mt-4 grid gap-4 xl:grid-cols-2">
              {overviewItems.map((item) => (
                <article key={item.gap_key} className={panelClass}>
                  <div className="flex flex-wrap items-center gap-2">
                    {renderBadge(gapTypeLabel(item.gap_type), gapTypeTone(item.gap_type))}
                    {renderBadge(gapDetailLabel(item.gap_detail_type), gapDetailTone(item.gap_detail_type))}
                    {renderBadge(`${t('competitiveGap.card.priority')}: ${item.priority_score}/100`, scoreTone(item.priority_score))}
                  </div>
                  <h3 className="mt-3 text-base font-semibold text-stone-900 dark:text-slate-50">{item.canonical_topic_label ?? item.topic_label}</h3>
                  <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">{item.rationale}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {renderBadge(t('competitiveGap.card.competitorsCount', { count: item.competitor_count }))}
                    {renderBadge(coverageTypeLabel(item.coverage_type), coverageTypeTone(item.coverage_type))}
                    {item.target_url ? renderBadge(truncateText(item.target_url, 56)) : null}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {showStrategySection ? (
      <section className={sectionClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{t('competitiveGap.strategy.title')}</h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.strategy.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {renderBadge(strategyStatusLabel(strategy?.normalization_status), strategyStatusTone(strategy?.normalization_status))}
            {strategy?.normalization_fallback_used ? renderBadge(t('competitiveGap.strategy.debug.fallbackUsedYes'), 'amber') : null}
            {strategy?.llm_model ? renderBadge(strategy.llm_model) : null}
            {strategy?.prompt_version ? renderBadge(strategy.prompt_version) : null}
          </div>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
          <div className="space-y-3">
            <label className={fieldLabelClass}>
              <span>{t('competitiveGap.strategy.inputLabel')}</span>
              <textarea
                value={strategyInput}
                onChange={(event) => setStrategyInput(event.target.value)}
                rows={8}
                className={fieldControlClass}
                placeholder={t('competitiveGap.strategy.placeholder')}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => void handleSaveStrategy()} disabled={!strategyInput.trim() || upsertStrategyMutation.isPending} className={primaryActionClass}>
                {upsertStrategyMutation.isPending ? t('competitiveGap.strategy.saving') : t('competitiveGap.strategy.save')}
              </button>
              <button type="button" onClick={() => void handleRerunStrategyNormalization()} disabled={!strategyInput.trim() || upsertStrategyMutation.isPending} className={actionClass}>
                {upsertStrategyMutation.isPending ? t('competitiveGap.strategy.rerunning') : t('competitiveGap.strategy.rerun')}
              </button>
              <button type="button" onClick={() => void handleDeleteStrategy()} disabled={!strategy || deleteStrategyMutation.isPending} className={actionClass}>
                {deleteStrategyMutation.isPending ? t('competitiveGap.strategy.removing') : t('competitiveGap.strategy.remove')}
              </button>
            </div>
            {upsertStrategyMutation.isError ? <p className="text-sm text-rose-700">{getUiErrorMessage(upsertStrategyMutation.error, t)}</p> : null}
            {deleteStrategyMutation.isError ? <p className="text-sm text-rose-700">{getUiErrorMessage(deleteStrategyMutation.error, t)}</p> : null}
          </div>

          <div className="space-y-3">
            <div className={panelClass}>
              <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.strategy.normalizedTitle')}</p>
              {strategy?.normalized_strategy_json ? (
                <>
                  <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">{strategy.normalized_strategy_json.business_summary}</p>
                  {strategyHints.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {strategyHints.map((hint) => (
                        <span key={`${hint.tone}:${hint.label}`}>{renderBadge(hint.label, hint.tone)}</span>
                      ))}
                    </div>
                  ) : null}
                  <p className="mt-3 text-xs text-stone-600 dark:text-slate-300">
                    {t('competitiveGap.strategy.lastNormalized', { date: formatDateTime(strategy.normalized_at ?? strategy.updated_at) })}
                  </p>
                </>
              ) : (
                <div className="mt-3 space-y-2">
                  <p className="text-sm font-medium text-stone-900 dark:text-slate-50">
                    {strategy ? t('competitiveGap.strategy.notReadyTitle') : t('competitiveGap.strategy.emptyTitle')}
                  </p>
                  <p className="text-sm text-stone-600 dark:text-slate-300">
                    {strategy ? t('competitiveGap.strategy.notReadyHint') : t('competitiveGap.strategy.emptyDescription')}
                  </p>
                </div>
              )}
            </div>

            <div className={panelClass}>
              <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.strategy.debug.title')}</p>
              <div className={`mt-3 rounded-2xl border px-4 py-3 ${toneClass(getStrategyDebugTone())}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold">{getStrategyDebugHeadline()}</p>
                  {renderBadge(strategyStatusLabel(strategy?.normalization_status), getStrategyDebugTone())}
                  {strategy?.normalization_fallback_used ? renderBadge(t('competitiveGap.strategy.debug.fallbackUsedYes'), 'amber') : null}
                  {strategy?.normalization_debug_code ? renderBadge(strategy.normalization_debug_code, strategy?.normalization_status === 'failed' ? 'rose' : 'stone') : null}
                </div>
                <p className="mt-2 text-sm">{getStrategyDebugMessage()}</p>
              </div>

              <dl className="mt-3 grid gap-3 text-sm text-stone-700 sm:grid-cols-2 dark:text-slate-300">
                <div className="space-y-1">
                  <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">{t('competitiveGap.strategy.debug.lastAttempt')}</dt>
                  <dd>{strategy?.last_normalization_attempt_at ? formatDateTime(strategy.last_normalization_attempt_at) : t('competitiveGap.strategy.debug.notAvailable')}</dd>
                </div>
                <div className="space-y-1">
                  <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">{t('competitiveGap.strategy.debug.fallbackUsed')}</dt>
                  <dd>{strategy ? (strategy.normalization_fallback_used ? t('competitiveGap.strategy.debug.fallbackUsedYes') : t('competitiveGap.strategy.debug.fallbackUsedNo')) : t('competitiveGap.strategy.debug.notAvailable')}</dd>
                </div>
                <div className="space-y-1">
                  <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">{t('competitiveGap.strategy.debug.provider')}</dt>
                  <dd>{strategy?.llm_provider ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
                </div>
                <div className="space-y-1">
                  <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">{t('competitiveGap.strategy.debug.model')}</dt>
                  <dd>{strategy?.llm_model ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
                </div>
                <div className="space-y-1">
                  <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">{t('competitiveGap.strategy.debug.promptVersion')}</dt>
                  <dd>{strategy?.prompt_version ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
                </div>
                <div className="space-y-1">
                  <dt className="text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">{t('competitiveGap.strategy.debug.code')}</dt>
                  <dd>{strategy?.normalization_debug_code ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
                </div>
              </dl>
            </div>
          </div>
        </div>
      </section>
      ) : null}

      {showCompetitorsSection ? (
      <section className={sectionClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{t('competitiveGap.competitors.title')}</h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.competitors.description')}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.competitors.count', { count: competitors.length })}</p>
            <Link to={buildSiteCompetitiveGapSyncPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
              {t('competitiveGap.competitors.openSync')}
            </Link>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className={fieldLabelClass}>
            <span>{t('competitiveGap.competitors.form.rootUrl')}</span>
            <input type="url" value={newCompetitorRootUrl} onChange={(event) => setNewCompetitorRootUrl(event.target.value)} className={fieldControlClass} placeholder="https://competitor.com" />
          </label>
          <label className={fieldLabelClass}>
            <span>{t('competitiveGap.competitors.form.label')}</span>
            <input type="text" value={newCompetitorLabel} onChange={(event) => setNewCompetitorLabel(event.target.value)} className={fieldControlClass} placeholder={t('competitiveGap.competitors.form.labelPlaceholder')} />
          </label>
          <label className={fieldLabelClass}>
            <span>{t('competitiveGap.competitors.form.notes')}</span>
            <input type="text" value={newCompetitorNotes} onChange={(event) => setNewCompetitorNotes(event.target.value)} className={fieldControlClass} placeholder={t('competitiveGap.competitors.form.notesPlaceholder')} />
          </label>
          <div className="flex items-end">
            <button type="button" onClick={() => void handleCreateCompetitor()} disabled={!newCompetitorRootUrl.trim() || createCompetitorMutation.isPending} className={primaryActionClass}>
              {createCompetitorMutation.isPending ? t('competitiveGap.competitors.form.adding') : t('competitiveGap.competitors.form.add')}
            </button>
          </div>
        </div>
        {createCompetitorMutation.isError ? <p className="mt-3 text-sm text-rose-700">{getUiErrorMessage(createCompetitorMutation.error, t)}</p> : null}

        {competitors.length === 0 ? (
          <div className="mt-4">
            <EmptyState title={t('competitiveGap.competitors.emptyTitle')} description={t('competitiveGap.competitors.emptyDescription')} />
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {competitors.map((competitor) => {
              const isEditing = editingCompetitorId === competitor.id
              const lastRunStatus = getCompetitorLastRunStatus(competitor)

              return (
                <article key={competitor.id} className={panelClass}>
                  {isEditing ? (
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <label className={fieldLabelClass}>
                        <span>{t('competitiveGap.competitors.form.rootUrl')}</span>
                        <input type="url" value={editingCompetitorRootUrl} onChange={(event) => setEditingCompetitorRootUrl(event.target.value)} className={fieldControlClass} />
                      </label>
                      <label className={fieldLabelClass}>
                        <span>{t('competitiveGap.competitors.form.label')}</span>
                        <input type="text" value={editingCompetitorLabel} onChange={(event) => setEditingCompetitorLabel(event.target.value)} className={fieldControlClass} />
                      </label>
                      <label className={fieldLabelClass}>
                        <span>{t('competitiveGap.competitors.form.notes')}</span>
                        <input type="text" value={editingCompetitorNotes} onChange={(event) => setEditingCompetitorNotes(event.target.value)} className={fieldControlClass} />
                      </label>
                      <label className={fieldLabelClass}>
                        <span>{t('competitiveGap.competitors.form.active')}</span>
                        <select value={editingCompetitorIsActive ? 'true' : 'false'} onChange={(event) => setEditingCompetitorIsActive(event.target.value === 'true')} className={fieldControlClass}>
                          <option value="true">{t('common.yes')}</option>
                          <option value="false">{t('common.no')}</option>
                        </select>
                      </label>
                      <div className="flex flex-wrap gap-2 md:col-span-2 xl:col-span-4">
                        <button type="button" onClick={() => void handleSaveCompetitor()} disabled={!editingCompetitorRootUrl.trim() || updateCompetitorMutation.isPending} className={primaryActionClass}>
                          {updateCompetitorMutation.isPending ? t('competitiveGap.competitors.saving') : t('competitiveGap.competitors.save')}
                        </button>
                        <button type="button" onClick={() => setEditingCompetitorId(null)} className={actionClass}>{t('competitiveGap.competitors.cancel')}</button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap gap-2">
                          {renderBadge(competitor.is_active ? t('competitiveGap.competitors.active') : t('competitiveGap.competitors.inactive'), competitor.is_active ? 'teal' : 'stone')}
                          {renderBadge(competitor.domain)}
                          {renderBadge(competitorSyncStatusLabel(competitor.last_sync_status), competitorSyncStatusTone(competitor.last_sync_status))}
                          {renderBadge(competitorSyncStageLabel(competitor.last_sync_stage), competitorSyncStageTone(competitor.last_sync_stage))}
                          {renderBadge(t('competitiveGap.competitors.coverage', { pages: competitor.pages_count, extracted: competitor.extracted_pages_count }), competitor.extracted_pages_count > 0 ? 'teal' : 'amber')}
                        </div>
                        <p className="mt-3 text-base font-semibold text-stone-900 dark:text-slate-50">{competitor.label}</p>
                        <p className="mt-1 break-all text-sm text-stone-600 dark:text-slate-300">{competitor.root_url}</p>
                        {competitor.notes ? <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">{competitor.notes}</p> : null}
                        <div className="mt-3 grid gap-2 text-xs text-stone-600 sm:grid-cols-2 dark:text-slate-300">
                          <p>{t('competitiveGap.competitors.lastRun')}: {competitor.last_sync_run_id > 0 ? t('competitiveGap.competitors.lastRunValue', { runId: competitor.last_sync_run_id }) : t('competitiveGap.competitors.noRunYet')}</p>
                          <p>{t('competitiveGap.competitors.lastStatus')}: {syncRunStatusLabel(lastRunStatus)}</p>
                          <p>{t('competitiveGap.competitors.lastStarted')}: {competitor.last_sync_started_at ? formatDateTime(competitor.last_sync_started_at) : t('competitiveGap.strategy.debug.notAvailable')}</p>
                          <p>{t('competitiveGap.competitors.lastFinished')}: {competitor.last_sync_finished_at ? formatDateTime(competitor.last_sync_finished_at) : t('competitiveGap.strategy.debug.notAvailable')}</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 xl:max-w-64 xl:justify-end">
                        <Link to={buildSiteCompetitiveGapSyncPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
                          {t('competitiveGap.competitors.openSync')}
                        </Link>
                        <button type="button" onClick={() => startEditingCompetitor(competitor)} className={actionClass}>{t('competitiveGap.competitors.edit')}</button>
                        <button type="button" onClick={() => void deleteCompetitorMutation.mutateAsync(competitor.id)} disabled={deleteCompetitorMutation.isPending} className={actionClass}>
                          {deleteCompetitorMutation.isPending ? t('competitiveGap.competitors.removing') : t('competitiveGap.competitors.remove')}
                        </button>
                      </div>
                    </div>
                  )}
                </article>
              )
            })}
            {updateCompetitorMutation.isError ? <p className="text-sm text-rose-700">{getUiErrorMessage(updateCompetitorMutation.error, t)}</p> : null}
            {deleteCompetitorMutation.isError ? <p className="text-sm text-rose-700">{getUiErrorMessage(deleteCompetitorMutation.error, t)}</p> : null}
          </div>
        )}
      </section>
      ) : null}

      {showSyncSection ? (
      <section className={sectionClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{t('competitiveGap.sync.title')}</h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.sync.description')}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.competitors.count', { count: competitors.length })}</p>
            <button
              type="button"
              onClick={() => void handleSyncAllCompetitors()}
              disabled={activeCompetitors.length === 0 || syncAllPending || allActiveCompetitorsBusy}
              className={actionClass}
            >
              {syncAllPending ? t('competitiveGap.competitors.syncAllRunning') : t('competitiveGap.competitors.syncAll')}
            </button>
            <Link to={buildSiteCompetitiveGapResultsPath(site.id, { activeCrawlId, baselineCrawlId })} className={actionClass}>
              {t('competitiveGap.nav.results')}
            </Link>
          </div>
        </div>

        {syncAllCompetitorsMutation.isError ? <p className="mt-3 text-sm text-rose-700">{getSyncErrorMessage(syncAllCompetitorsMutation.error)}</p> : null}
        {syncAllCompetitorsMutation.data?.already_running_competitor_ids?.length ? (
          <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
            {t('competitiveGap.competitors.syncAllSkipped', { count: syncAllCompetitorsMutation.data.already_running_competitor_ids.length })}
          </p>
        ) : null}

        {competitors.length === 0 ? (
          <div className="mt-4">
            <EmptyState title={t('competitiveGap.competitors.emptyTitle')} description={t('competitiveGap.competitors.emptyDescription')} />
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {competitors.map((competitor) => {
              const progressPercent = getCompetitorSyncProgressPercent(competitor)
              const syncInFlight = isCompetitorSyncBusy(competitor)
              const summary = competitor.last_sync_summary
              const syncReasonStats = getSyncSummaryReasonStats(competitor)
              const lastRunStatus = getCompetitorLastRunStatus(competitor)
              const runHistoryExpanded = expandedRunHistoryIds[competitor.id] ?? false
              const showRetryAction = shouldShowRetryAction(competitor)
              const showResetAction = shouldShowResetAction(competitor)
              const retryQueued = recentlyRetriedCompetitorIds[competitor.id] ?? false
              const semanticStatus = competitor.semantic_status ?? 'not_started'
              const semanticCandidatesCount = competitor.semantic_candidates_count ?? 0
              const semanticLlmJobsCount = competitor.semantic_llm_jobs_count ?? 0
              const semanticResolvedCount = competitor.semantic_resolved_count ?? 0
              const semanticCacheHits = competitor.semantic_cache_hits ?? 0
              const semanticFallbackCount = competitor.semantic_fallback_count ?? 0
              return (
                <article key={competitor.id} className={panelClass}>
                  {(
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0 flex-1 space-y-4">
                        <div className="flex flex-wrap gap-2">
                          {renderBadge(competitor.is_active ? t('competitiveGap.competitors.active') : t('competitiveGap.competitors.inactive'), competitor.is_active ? 'teal' : 'stone')}
                          {renderBadge(competitor.domain)}
                          {renderBadge(competitorSyncStatusLabel(competitor.last_sync_status), competitorSyncStatusTone(competitor.last_sync_status))}
                          {renderBadge(competitorSyncStageLabel(competitor.last_sync_stage), competitorSyncStageTone(competitor.last_sync_stage))}
                          {competitor.last_sync_run_id > 0 ? renderBadge(t('competitiveGap.competitors.lastRunValue', { runId: competitor.last_sync_run_id })) : null}
                          {competitor.last_sync_run_id > 0 ? renderBadge(syncRunStatusLabel(lastRunStatus), syncRunStatusTone(lastRunStatus)) : null}
                          {retryQueued ? renderBadge(t('competitiveGap.competitors.retryQueuedBadge'), 'amber') : null}
                          {renderBadge(t('competitiveGap.competitors.coverage', { pages: competitor.pages_count, extracted: competitor.extracted_pages_count }), competitor.extracted_pages_count > 0 ? 'teal' : 'amber')}
                        </div>
                        <div>
                          <p className="text-base font-semibold text-stone-900 dark:text-slate-50">{competitor.label}</p>
                          <p className="mt-1 break-all text-sm text-stone-600 dark:text-slate-300">{competitor.root_url}</p>
                        </div>
                        {competitor.notes ? <p className="text-sm text-stone-600 dark:text-slate-300">{competitor.notes}</p> : null}

                        <div className={`rounded-2xl border px-4 py-3 ${toneClass(competitorSyncStatusTone(competitor.last_sync_status))}`}>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold">{getCompetitorSyncSummaryTitle(competitor)}</p>
                            {syncInFlight ? renderBadge(t('competitiveGap.competitors.inProgressBadge'), 'amber') : null}
                            {competitorUsesPartialData(competitor) ? renderBadge(t('competitiveGap.competitors.partialDataBadge'), 'teal') : null}
                          </div>
                          <p className="mt-2 text-sm">{getCompetitorSyncHeadline(competitor)}</p>
                          {competitorUsesPartialData(competitor) ? (
                            <p className="mt-2 text-xs">{t('competitiveGap.competitors.partialDataHint')}</p>
                          ) : null}
                        </div>

                        <div className="space-y-2">
                          <div className="flex items-center justify-between gap-3 text-xs text-stone-600 dark:text-slate-300">
                            <span>{competitorProgressLabel(competitor)}</span>
                            <span>{progressPercent}%</span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-stone-200 dark:bg-slate-800">
                            <div
                              className="h-full rounded-full bg-amber-500 transition-[width] dark:bg-amber-400"
                              style={{ width: `${progressPercent}%` }}
                            />
                          </div>
                        </div>

                        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                          <div className={panelClass}>
                            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.competitors.summary.visited')}</p>
                            <p className="mt-2 text-lg font-semibold text-stone-950 dark:text-slate-50">
                              {Math.max(competitor.last_sync_processed_urls, syncSummaryCount(summary.visited_urls_count))}
                            </p>
                          </div>
                          <div className={panelClass}>
                            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.competitors.summary.stored')}</p>
                            <p className="mt-2 text-lg font-semibold text-stone-950 dark:text-slate-50">
                              {Math.max(competitor.pages_count, syncSummaryCount(summary.stored_pages_count))}
                            </p>
                          </div>
                          <div className={panelClass}>
                            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.competitors.summary.extracted')}</p>
                            <p className="mt-2 text-lg font-semibold text-stone-950 dark:text-slate-50">
                              {Math.max(competitor.extracted_pages_count, syncSummaryCount(summary.extracted_pages_count))}
                            </p>
                          </div>
                          <div className={panelClass}>
                            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.competitors.summary.skipped')}</p>
                            <p className="mt-2 text-lg font-semibold text-stone-950 dark:text-slate-50">
                              {syncSummaryCount(summary.skipped_urls_count)}
                            </p>
                          </div>
                        </div>

                        <div className={panelClass}>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
                              {t('competitiveGap.competitors.semantic.title')}
                            </p>
                            {renderBadge(semanticStatusLabel(semanticStatus), semanticStatusTone(semanticStatus))}
                            {competitor.semantic_model ? renderBadge(competitor.semantic_model) : null}
                            {competitor.semantic_prompt_version ? renderBadge(competitor.semantic_prompt_version) : null}
                          </div>
                          <div className="mt-3 grid gap-2 text-xs text-stone-600 sm:grid-cols-2 xl:grid-cols-3 dark:text-slate-300">
                            <p>
                              {t('competitiveGap.competitors.semantic.lastRunStarted')}: {
                                competitor.last_semantic_run_started_at
                                  ? formatDateTime(competitor.last_semantic_run_started_at)
                                  : t('competitiveGap.strategy.debug.notAvailable')
                              }
                            </p>
                            <p>
                              {t('competitiveGap.competitors.semantic.lastRunFinished')}: {
                                competitor.last_semantic_run_finished_at
                                  ? formatDateTime(competitor.last_semantic_run_finished_at)
                                  : t('competitiveGap.strategy.debug.notAvailable')
                              }
                            </p>
                            <p>
                              {t('competitiveGap.competitors.semantic.candidates')}: {semanticCandidatesCount}
                            </p>
                            <p>
                              {t('competitiveGap.competitors.semantic.resolved')}: {semanticResolvedCount}
                            </p>
                            <p>
                              {t('competitiveGap.competitors.semantic.llmJobs')}: {semanticLlmJobsCount}
                            </p>
                            <p>
                              {t('competitiveGap.competitors.semantic.cacheHits')}: {semanticCacheHits}
                            </p>
                            <p>
                              {t('competitiveGap.competitors.semantic.fallbackCount')}: {semanticFallbackCount}
                            </p>
                            <p className="sm:col-span-2 xl:col-span-3">
                              {t('competitiveGap.competitors.semantic.lastError')}: {
                                competitor.last_semantic_error ?? t('competitiveGap.strategy.debug.notAvailable')
                              }
                            </p>
                          </div>
                          {semanticStatus === 'not_started' &&
                          semanticCandidatesCount === 0 &&
                          semanticLlmJobsCount === 0 &&
                          semanticResolvedCount === 0 &&
                          semanticCacheHits === 0 &&
                          semanticFallbackCount === 0 &&
                          !competitor.last_semantic_error ? (
                            <p className="mt-3 text-xs text-stone-600 dark:text-slate-300">
                              {t('competitiveGap.competitors.semantic.noData')}
                            </p>
                          ) : null}
                        </div>

                        {syncReasonStats.length > 0 ? (
                          <div className={panelClass}>
                            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.competitors.rejectionsTitle')}</p>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {syncReasonStats.slice(0, 4).map((item) => (
                                <span key={`${competitor.id}:${item.key}`}>
                                  {renderBadge(
                                    t(`competitiveGap.competitors.rejectionReasons.${item.key}`, { count: item.count }),
                                    'amber',
                                  )}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : null}

                        <CompetitorPageReviewPanel siteId={site.id} competitor={competitor} />

                        <div className="grid gap-2 text-xs text-stone-600 sm:grid-cols-2 dark:text-slate-300">
                          <p>
                            {t('competitiveGap.competitors.lastRun')}: {competitor.last_sync_run_id > 0 ? t('competitiveGap.competitors.lastRunValue', { runId: competitor.last_sync_run_id }) : t('competitiveGap.competitors.noRunYet')}
                          </p>
                          <p>
                            {t('competitiveGap.competitors.lastStarted')}: {competitor.last_sync_started_at ? formatDateTime(competitor.last_sync_started_at) : t('competitiveGap.strategy.debug.notAvailable')}
                          </p>
                          <p>
                            {t('competitiveGap.competitors.lastFinished')}: {competitor.last_sync_finished_at ? formatDateTime(competitor.last_sync_finished_at) : t('competitiveGap.strategy.debug.notAvailable')}
                          </p>
                          <p>
                            {t('competitiveGap.competitors.lastStatus')}: {syncRunStatusLabel(lastRunStatus)}
                          </p>
                          <p>
                            {t('competitiveGap.competitors.lastErrorCode')}: {competitor.last_sync_error_code ?? t('competitiveGap.strategy.debug.notAvailable')}
                          </p>
                        </div>

                        {competitor.last_sync_error ? (
                          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-100">
                            <p className="font-medium">{t('competitiveGap.competitors.lastErrorTitle')}</p>
                            <p className="mt-1">{competitor.last_sync_error}</p>
                          </div>
                        ) : null}

                        <CompetitorRecentRunsPanel
                          siteId={site.id}
                          competitor={competitor}
                          expanded={runHistoryExpanded}
                          onToggle={() => toggleCompetitorRunHistory(competitor.id)}
                        />
                      </div>
                      <div className="flex flex-wrap gap-2 xl:max-w-56 xl:justify-end">
                        <button
                          type="button"
                          onClick={() => void handleSyncCompetitor(competitor.id)}
                          disabled={
                            syncInFlight ||
                            syncingCompetitorId === competitor.id ||
                            syncAllPending ||
                            resettingCompetitorId === competitor.id ||
                            retryingCompetitorId === competitor.id
                          }
                          className={actionClass}
                        >
                          {getCompetitorSyncButtonLabel(competitor)}
                        </button>
                        {showRetryAction ? (
                          <button
                            type="button"
                            onClick={() => void handleRetryCompetitorSync(competitor.id)}
                            disabled={
                              retryingCompetitorId === competitor.id ||
                              syncingCompetitorId === competitor.id ||
                              resettingCompetitorId === competitor.id ||
                              syncAllPending ||
                              syncInFlight
                            }
                            className={actionClass}
                          >
                            {retryingCompetitorId === competitor.id ? t('competitiveGap.competitors.retryingSync') : t('competitiveGap.competitors.retrySync')}
                          </button>
                        ) : null}
                        {showResetAction ? (
                          <button
                            type="button"
                            onClick={() => void handleResetCompetitorSync(competitor.id)}
                            disabled={resettingCompetitorId === competitor.id || syncingCompetitorId === competitor.id || retryingCompetitorId === competitor.id || syncAllPending}
                            className={actionClass}
                          >
                            {resettingCompetitorId === competitor.id ? t('competitiveGap.competitors.resettingSync') : t('competitiveGap.competitors.resetSync')}
                          </button>
                        ) : null}
                      </div>
                    </div>
                  )}
                </article>
              )
            })}
            {syncCompetitorMutation.isError ? <p className="text-sm text-rose-700">{getSyncErrorMessage(syncCompetitorMutation.error)}</p> : null}
            {retryCompetitorSyncMutation.isError ? <p className="text-sm text-rose-700">{getSyncErrorMessage(retryCompetitorSyncMutation.error)}</p> : null}
            {resetCompetitorSyncMutation.isError ? <p className="text-sm text-rose-700">{getUiErrorMessage(resetCompetitorSyncMutation.error, t)}</p> : null}
          </div>
        )}
      </section>
      ) : null}

      {showResultsSection ? (
      <>
      <QuickFilterBar title={t('competitiveGap.quickFilters.title')} items={quickFilters} />

      <FilterPanel title={t('competitiveGap.filters.title')} description={t('competitiveGap.filters.description')} onReset={resetFilters}>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.dateRange')}</span>
          <select value={gapParams.gsc_date_range} onChange={(event) => updateFilter({ gsc_date_range: event.target.value })} className={fieldControlClass}>
            <option value="last_28_days">{t('competitiveGap.filters.last28Days')}</option>
            <option value="last_90_days">{t('competitiveGap.filters.last90Days')}</option>
          </select>
        </label>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.gapType')}</span>
          <select value={gapParams.gap_type ?? ''} onChange={(event) => updateFilter({ gap_type: event.target.value || undefined })} className={fieldControlClass}>
            <option value="">{t('common.any')}</option>
            {gapTypes.map((value) => <option key={value} value={value}>{gapTypeLabel(value)}</option>)}
          </select>
        </label>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.segment')}</span>
          <select value={gapParams.segment ?? ''} onChange={(event) => updateFilter({ segment: event.target.value || undefined })} className={fieldControlClass}>
            <option value="">{t('common.any')}</option>
            {gapSegments.map((value) => <option key={value} value={value}>{gapSegmentLabel(value)}</option>)}
          </select>
        </label>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.pageType')}</span>
          <select value={gapParams.page_type ?? ''} onChange={(event) => updateFilter({ page_type: event.target.value || undefined })} className={fieldControlClass}>
            <option value="">{t('common.any')}</option>
            {pageTypes.map((value) => <option key={value} value={value}>{pageTypeLabel(value)}</option>)}
          </select>
        </label>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.ownMatchStatus')}</span>
          <select value={gapParams.own_match_status ?? ''} onChange={(event) => updateFilter({ own_match_status: readOwnMatchStatus(event.target.value) })} className={fieldControlClass}>
            <option value="">{t('common.any')}</option>
            <option value="exact_match">{semanticMatchLabel('exact_match')}</option>
            <option value="semantic_match">{semanticMatchLabel('semantic_match')}</option>
            <option value="partial_coverage">{semanticMatchLabel('partial_coverage')}</option>
            <option value="no_meaningful_match">{semanticMatchLabel('no_meaningful_match')}</option>
          </select>
        </label>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.topic')}</span>
          <input type="text" value={gapParams.topic ?? ''} onChange={(event) => updateFilter({ topic: event.target.value || undefined })} className={fieldControlClass} placeholder={t('competitiveGap.filters.topicPlaceholder')} />
        </label>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.priorityMin')}</span>
          <input type="number" min={0} max={100} step={1} value={gapParams.priority_score_min ?? ''} onChange={(event) => updateFilter({ priority_score_min: event.target.value || undefined })} className={fieldControlClass} placeholder="70" />
        </label>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.consensusMin')}</span>
          <input type="number" min={0} max={100} step={1} value={gapParams.consensus_min ?? ''} onChange={(event) => updateFilter({ consensus_min: event.target.value || undefined })} className={fieldControlClass} placeholder="60" />
        </label>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.sortBy')}</span>
          <select value={gapParams.sort_by} onChange={(event) => updateFilter({ sort_by: event.target.value })} className={fieldControlClass}>
            <option value="priority_score">{t('competitiveGap.filters.sort.priorityScore')}</option>
            <option value="consensus_score">{t('competitiveGap.filters.sort.consensus')}</option>
            <option value="competitor_count">{t('competitiveGap.filters.sort.competitorCount')}</option>
            <option value="competitor_coverage_score">{t('competitiveGap.filters.sort.competitorCoverage')}</option>
            <option value="own_coverage_score">{t('competitiveGap.filters.sort.ownCoverage')}</option>
            <option value="strategy_alignment_score">{t('competitiveGap.filters.sort.strategyAlignment')}</option>
            <option value="business_value_score">{t('competitiveGap.filters.sort.businessValue')}</option>
            <option value="merged_topic_count">{t('competitiveGap.filters.sort.mergedTopics')}</option>
            <option value="confidence">{t('competitiveGap.filters.sort.confidence')}</option>
            <option value="topic_label">{t('competitiveGap.filters.sort.topic')}</option>
            <option value="gap_type">{t('competitiveGap.filters.sort.gapType')}</option>
            <option value="page_type">{t('competitiveGap.filters.sort.pageType')}</option>
          </select>
        </label>
        <label className={fieldLabelClass}>
          <span>{t('competitiveGap.filters.sortOrder')}</span>
          <select value={gapParams.sort_order} onChange={(event) => updateFilter({ sort_order: event.target.value })} className={fieldControlClass}>
            <option value="desc">{t('sort.descending')}</option>
            <option value="asc">{t('sort.ascending')}</option>
          </select>
        </label>
      </FilterPanel>

      <section className={sectionClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">{t('competitiveGap.mix.title')}</h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('competitiveGap.mix.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {summaryTypeEntries.map(([type, count]) => <span key={type}>{renderBadge(`${gapTypeLabel(type as CompetitiveGapType)}: ${count}`)}</span>)}
            {summaryCoverageEntries.map(([type, count]) => <span key={type}>{renderBadge(`${coverageTypeLabel(type as CompetitiveGapCoverageType)}: ${count}`, coverageTypeTone(type as CompetitiveGapCoverageType))}</span>)}
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className={panelClass}>
            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">Cluster quality</p>
            <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
              {clusterQualitySummary.clusters_count} clusters
            </p>
            <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">
              Avg confidence: {formatPercent(clusterQualitySummary.average_cluster_confidence, 0)}
            </p>
            <p className="mt-1 text-xs text-stone-600 dark:text-slate-300">
              Low-confidence clusters: {clusterQualitySummary.low_confidence_clusters_count}
            </p>
          </div>
          <div className={panelClass}>
            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">Canonicalization</p>
            <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
              {canonicalizationSummary.canonical_pages_count} canonical pages
            </p>
            <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">
              Duplicates: {canonicalizationSummary.duplicate_pages_count}
            </p>
            <p className="mt-1 text-xs text-stone-600 dark:text-slate-300">
              Near-duplicates: {canonicalizationSummary.near_duplicate_pages_count}
            </p>
          </div>
          <div className={panelClass}>
            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">Semantic assets</p>
            <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
              {semanticDiagnostics.competitor_semantic_cards_count} competitor cards
            </p>
            <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">
              Own profiles: {semanticDiagnostics.own_page_semantic_profiles_count}
            </p>
            <p className="mt-1 text-xs text-stone-600 dark:text-slate-300">
              Versions: {semanticDiagnostics.semantic_version ?? 'n/a'} / {semanticDiagnostics.cluster_version ?? 'n/a'}
            </p>
          </div>
          <div className={panelClass}>
            <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">Latest failure</p>
            <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">
              {semanticDiagnostics.latest_failure_stage ?? 'No active stage failure'}
            </p>
            <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">
              {semanticDiagnostics.latest_failure_error_code ?? 'No error code'}
            </p>
            <p className="mt-1 text-xs text-stone-600 dark:text-slate-300">
              {semanticDiagnostics.latest_failure_error_message ?? 'Semantic layer currently has no surfaced failure message.'}
            </p>
          </div>
        </div>
      </section>

      {payload.items.length === 0 && gapEmptyState ? (
        <section className={sectionClass}>
          <div className={`rounded-[28px] border px-6 py-8 ${toneClass(gapEmptyState.tone)}`}>
            <p className="text-lg font-semibold">{gapEmptyState.title}</p>
            <p className="mt-2 max-w-3xl text-sm">{gapEmptyState.description}</p>
            {payload.context.empty_state_reason === 'filters_excluded_all' ? (
              <div className="mt-4">
                <button type="button" onClick={resetFilters} className={actionClass}>
                  {t('competitiveGap.emptyStates.resetFilters')}
                </button>
              </div>
            ) : null}
          </div>
        </section>
      ) : (
        <div className="space-y-4">
          {payload.items.map((item) => {
            const explanation = loadedExplanations[item.gap_key] ?? null
            const isExpanded = expandedGapKey === item.gap_key
            const isExplanationLoading = loadingExplanationGapKey === item.gap_key
            const hasSemanticContext = Boolean(
              item.semantic_cluster_key ||
                item.canonical_topic_label ||
                item.merged_topic_count ||
                item.own_match_status ||
                item.own_match_source,
            )
            const reviewedDisplayLabel = item.reviewed_phrase?.trim() || item.reviewed_topic_label?.trim() || null
            const showsReviewedLabel =
              reviewedDisplayLabel !== null &&
              reviewedDisplayLabel.localeCompare(item.topic_label, undefined, { sensitivity: 'accent' }) !== 0
            const fitScoreLabel = formatFitScore(item.fit_score)
            const hasReviewSummary = Boolean(showsReviewedLabel || item.merge_target_phrase || item.remove_reason_text)

            return (
              <article key={item.gap_key} className={cardClass}>
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {renderBadge(gapTypeLabel(item.gap_type), gapTypeTone(item.gap_type))}
                      {item.gap_detail_type ? renderBadge(gapDetailLabel(item.gap_detail_type), gapDetailTone(item.gap_detail_type)) : null}
                      {renderBadge(gapSegmentLabel(item.segment))}
                      {renderBadge(pageTypeLabel(item.page_type), 'teal')}
                      {renderBadge(`${t('competitiveGap.card.priority')} ${item.priority_score}`, scoreTone(item.priority_score))}
                      {renderBadge(`${t('competitiveGap.card.consensus')} ${item.consensus_score}`)}
                      {item.decision_action ? renderBadge(reviewDecisionLabel(item.decision_action), reviewDecisionTone(item.decision_action)) : null}
                      {fitScoreLabel ? renderBadge(t('competitiveGap.review.fitScoreBadge', { score: fitScoreLabel }), item.fit_score && item.fit_score >= 75 ? 'teal' : 'stone') : null}
                    </div>
                    <div>
                      <button
                        type="button"
                        onClick={() => updateFilter({ topic: item.topic_label })}
                        className="text-left text-2xl font-semibold tracking-tight text-stone-950 transition hover:text-teal-700 dark:text-slate-50 dark:hover:text-teal-300"
                      >
                        {item.topic_label}
                      </button>
                      <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">{item.rationale}</p>
                      {hasSemanticContext ? (
                        <div className="mt-3 space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            {item.canonical_topic_label ? renderBadge(t('competitiveGap.semantic.canonicalTopicLabel', { label: item.canonical_topic_label }), 'teal') : null}
                            {item.own_match_status ? renderBadge(semanticMatchLabel(item.own_match_status), semanticMatchTone(item.own_match_status)) : null}
                            {item.coverage_type ? renderBadge(coverageTypeLabel(item.coverage_type), coverageTypeTone(item.coverage_type)) : null}
                            {typeof item.merged_topic_count === 'number'
                              ? renderBadge(t('competitiveGap.semantic.mergedTopics', { count: item.merged_topic_count }), item.merged_topic_count > 1 ? 'amber' : 'stone')
                              : null}
                            {typeof item.cluster_confidence === 'number'
                              ? renderBadge(`Cluster ${formatPercent(item.cluster_confidence, 0)}`, item.cluster_confidence >= 0.75 ? 'teal' : 'amber')
                              : null}
                          </div>
                          {typeof item.merged_topic_count === 'number' && item.merged_topic_count > 1 ? (
                            <p className="text-xs text-stone-600 dark:text-slate-300">
                              {t('competitiveGap.semantic.mergedHint', { count: item.merged_topic_count })}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                      {hasReviewSummary ? (
                        <div className="mt-3 rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3 text-xs text-stone-700 dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-200">
                          {showsReviewedLabel ? (
                            <p>
                              <span className="font-medium">{t('competitiveGap.review.reviewedPhraseLabel')}:</span> {reviewedDisplayLabel}
                            </p>
                          ) : null}
                          {item.merge_target_phrase ? (
                            <p className={showsReviewedLabel ? 'mt-1' : undefined}>
                              <span className="font-medium">{t('competitiveGap.review.mergeTargetLabel')}:</span> {item.merge_target_phrase}
                            </p>
                          ) : null}
                          {item.remove_reason_text ? (
                            <p className={showsReviewedLabel || item.merge_target_phrase ? 'mt-1' : undefined}>
                              <span className="font-medium">{t('competitiveGap.review.removeReasonLabel')}:</span> {item.remove_reason_text}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => void handleExplain(item, resolvedActiveCrawlId)} className={actionClass}>
                      {isExpanded ? t('competitiveGap.card.hideExplanation') : t('competitiveGap.card.showExplanation')}
                    </button>
                    {item.target_url ? (
                      <>
                        <a href={item.target_url} className={actionClass}>{t('competitiveGap.card.openTarget')}</a>
                        <Link to={buildPagesLink(site.id, item.target_url, activeCrawlId, baselineCrawlId)} className={actionClass}>
                          {t('competitiveGap.card.openInPages')}
                        </Link>
                      </>
                    ) : null}
                  </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <div className={panelClass}>
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.card.recommendedMove')}</p>
                    <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">{pageTypeLabel(item.page_type)}</p>
                    <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">
                      {t('competitiveGap.card.targetPage')}: {item.target_url ?? t('competitiveGap.card.newPage')}
                    </p>
                    {item.coverage_rationale ? (
                      <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">{truncateText(item.coverage_rationale, 120)}</p>
                    ) : null}
                  </div>
                  <div className={panelClass}>
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.card.scoreMix')}</p>
                    <dl className="mt-2 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                      <div className="flex items-center justify-between gap-3">
                        <dt>{t('competitiveGap.card.competitorCoverage')}</dt>
                        <dd className="font-medium text-stone-950 dark:text-slate-50">{item.competitor_coverage_score}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt>{t('competitiveGap.card.ownCoverage')}</dt>
                        <dd className="font-medium text-stone-950 dark:text-slate-50">{item.own_coverage_score}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt>{t('competitiveGap.card.businessValue')}</dt>
                        <dd className="font-medium text-stone-950 dark:text-slate-50">{item.business_value_score}</dd>
                      </div>
                    </dl>
                  </div>
                  <div className={panelClass}>
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.card.competitorSignal')}</p>
                    <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">{t('competitiveGap.card.competitorsCount', { count: item.competitor_count })}</p>
                    <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">{t('competitiveGap.card.confidence')}: {formatPercent(item.confidence, 0)}</p>
                    <div className="mt-3 space-y-1">
                      {item.competitor_urls.slice(0, 3).map((url) => (
                        <a key={url} href={url} className="block break-all text-xs text-teal-700 transition hover:text-teal-600 dark:text-teal-300 dark:hover:text-teal-200">
                          {truncateText(url, 72)}
                        </a>
                      ))}
                    </div>
                  </div>
                  <div className={panelClass}>
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{t('competitiveGap.card.strategyFit')}</p>
                    <p className="mt-2 text-sm font-medium text-stone-900 dark:text-slate-50">{item.strategy_alignment_score}/100</p>
                    <p className="mt-2 text-xs text-stone-600 dark:text-slate-300">{t('competitiveGap.card.topicKey')}: {item.topic_key}</p>
                    {item.cluster_geo_scope ? (
                      <p className="mt-1 text-xs text-stone-600 dark:text-slate-300">Geo: {item.cluster_geo_scope}</p>
                    ) : null}
                  </div>
                </div>

                {item.mismatch_notes && item.mismatch_notes.length > 0 ? (
                  <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
                    {item.mismatch_notes.join(' ')}
                  </div>
                ) : null}

                {isExpanded ? (
                  <section className="mt-4 rounded-3xl border border-teal-200 bg-teal-50/70 p-4 dark:border-teal-900 dark:bg-teal-950/25">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-teal-950 dark:text-teal-100">{t('competitiveGap.explanation.title')}</p>
                      {explanation ? (
                        <>
                          {renderBadge(explanation.used_llm ? t('competitiveGap.explanation.llm') : t('competitiveGap.explanation.fallback'), explanation.used_llm ? 'teal' : 'amber')}
                          {explanation.fallback_used ? renderBadge(t('competitiveGap.explanation.fallbackUsed'), 'amber') : null}
                        </>
                      ) : null}
                    </div>
                    {isExplanationLoading ? (
                      <p className="mt-3 text-sm text-teal-900 dark:text-teal-100">{t('competitiveGap.explanation.loading')}</p>
                    ) : explanationErrors[item.gap_key] ? (
                      <p className="mt-3 text-sm text-rose-700">{explanationErrors[item.gap_key]}</p>
                    ) : explanation ? (
                      <div className="mt-3 space-y-3">
                        <p className="text-sm text-teal-950 dark:text-teal-100">{explanation.explanation}</p>
                        <ul className="space-y-2 text-sm text-teal-950 dark:text-teal-100">
                          {explanation.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
                        </ul>
                      </div>
                    ) : null}
                    {hasSemanticContext ? (
                      <div className="mt-3 rounded-2xl border border-teal-200 bg-white/80 p-4 dark:border-teal-900 dark:bg-slate-950/60">
                        <p className="text-xs uppercase tracking-[0.18em] text-teal-700 dark:text-teal-300">
                          {t('competitiveGap.explanation.semanticDebugTitle')}
                        </p>
                        <dl className="mt-3 grid gap-3 text-xs text-teal-950 sm:grid-cols-2 xl:grid-cols-3 dark:text-teal-100">
                          <div className="space-y-1">
                            <dt className="uppercase tracking-[0.14em] text-teal-700 dark:text-teal-300">
                              {t('competitiveGap.explanation.semanticClusterKey')}
                            </dt>
                            <dd>{item.semantic_cluster_key ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
                          </div>
                          <div className="space-y-1">
                            <dt className="uppercase tracking-[0.14em] text-teal-700 dark:text-teal-300">
                              {t('competitiveGap.explanation.canonicalTopicLabel')}
                            </dt>
                            <dd>{item.canonical_topic_label ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
                          </div>
                          <div className="space-y-1">
                            <dt className="uppercase tracking-[0.14em] text-teal-700 dark:text-teal-300">
                              {t('competitiveGap.explanation.mergedTopicCount')}
                            </dt>
                            <dd>
                              {typeof item.merged_topic_count === 'number'
                                ? item.merged_topic_count
                                : t('competitiveGap.strategy.debug.notAvailable')}
                            </dd>
                          </div>
                          <div className="space-y-1">
                            <dt className="uppercase tracking-[0.14em] text-teal-700 dark:text-teal-300">
                              {t('competitiveGap.explanation.ownMatchStatus')}
                            </dt>
                            <dd>{semanticMatchLabel(item.own_match_status)}</dd>
                          </div>
                          <div className="space-y-1 sm:col-span-2 xl:col-span-2">
                            <dt className="uppercase tracking-[0.14em] text-teal-700 dark:text-teal-300">
                              {t('competitiveGap.explanation.ownMatchSource')}
                            </dt>
                            <dd>{item.own_match_source ?? t('competitiveGap.strategy.debug.notAvailable')}</dd>
                          </div>
                        </dl>
                      </div>
                    ) : null}
                  </section>
                ) : null}
              </article>
            )
          })}
        </div>
      )}

      <PaginationControls
        page={payload.page}
        pageSize={payload.page_size}
        totalItems={payload.total_items}
        totalPages={payload.total_pages}
        onPageChange={(page) => updateParams({ page })}
        onPageSizeChange={(pageSize) => updateParams({ page: 1, page_size: pageSize })}
      />
      </>
      ) : null}
    </div>
  )
}

export function SiteCompetitiveGapOverviewPage() {
  return <SiteCompetitiveGapPage mode="overview" />
}

export function SiteCompetitiveGapStrategyPage() {
  return <SiteCompetitiveGapPage mode="strategy" />
}

export function SiteCompetitiveGapCompetitorsPage() {
  return <SiteCompetitiveGapPage mode="competitors" />
}

export function SiteCompetitiveGapSyncPage() {
  return <SiteCompetitiveGapPage mode="sync" />
}

export function SiteCompetitiveGapResultsPage() {
  return <SiteCompetitiveGapPage mode="results" />
}
