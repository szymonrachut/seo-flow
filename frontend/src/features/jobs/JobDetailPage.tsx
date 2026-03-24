import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { buildApiUrl } from '../../api/client'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { CrawlJobCreateInput, CrawlJobSummaryCounts } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime, prettyJson } from '../../utils/format'
import { JobNavigation } from './JobNavigation'
import { useCreateCrawlJobMutation, useCrawlJobDetailQuery, useStopCrawlJobMutation } from './api'
import { buildSiteOverviewPath } from '../sites/routes'

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

export function JobDetailPage() {
  const { t } = useTranslation()
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  const navigate = useNavigate()
  useDocumentTitle(jobId ? t('documentTitle.jobDetail', { jobId }) : t('documentTitle.job'))

  if (jobId === null) {
    return <ErrorState title={t('jobs.detail.invalidIdTitle')} message={t('jobs.detail.invalidIdMessage')} />
  }

  const summaryCountLabels: Record<keyof CrawlJobSummaryCounts, string> = {
    total_pages: t('jobs.detail.summaryCounts.total_pages'),
    total_links: t('jobs.detail.summaryCounts.total_links'),
    total_internal_links: t('jobs.detail.summaryCounts.total_internal_links'),
    total_external_links: t('jobs.detail.summaryCounts.total_external_links'),
    pages_missing_title: t('jobs.detail.summaryCounts.pages_missing_title'),
    pages_missing_meta_description: t('jobs.detail.summaryCounts.pages_missing_meta_description'),
    pages_missing_h1: t('jobs.detail.summaryCounts.pages_missing_h1'),
    pages_non_indexable_like: t('jobs.detail.summaryCounts.pages_non_indexable_like'),
    rendered_pages: t('jobs.detail.summaryCounts.rendered_pages'),
    js_heavy_like_pages: t('jobs.detail.summaryCounts.js_heavy_like_pages'),
    pages_with_render_errors: t('jobs.detail.summaryCounts.pages_with_render_errors'),
    pages_with_schema: t('jobs.detail.summaryCounts.pages_with_schema'),
    pages_with_x_robots_tag: t('jobs.detail.summaryCounts.pages_with_x_robots_tag'),
    pages_with_gsc_28d: t('jobs.detail.summaryCounts.pages_with_gsc_28d'),
    pages_with_gsc_90d: t('jobs.detail.summaryCounts.pages_with_gsc_90d'),
    gsc_opportunities_28d: t('jobs.detail.summaryCounts.gsc_opportunities_28d'),
    gsc_opportunities_90d: t('jobs.detail.summaryCounts.gsc_opportunities_90d'),
    broken_internal_links: t('jobs.detail.summaryCounts.broken_internal_links'),
    redirecting_internal_links: t('jobs.detail.summaryCounts.redirecting_internal_links'),
  }

  const jobQuery = useCrawlJobDetailQuery(jobId)
  const stopMutation = useStopCrawlJobMutation(jobId)
  const duplicateMutation = useCreateCrawlJobMutation()

  if (jobQuery.isLoading) {
    return <LoadingState label={t('jobs.detail.loading', { jobId })} />
  }

  if (jobQuery.isError) {
    return (
      <ErrorState
        title={t('jobs.detail.errorTitle')}
        message={getUiErrorMessage(jobQuery.error, t)}
      />
    )
  }

  const job = jobQuery.data
  if (!job) {
    return <EmptyState title={t('jobs.detail.emptyTitle')} description={t('jobs.detail.emptyDescription')} />
  }

  const stopAllowed = job.status === 'pending' || job.status === 'running'
  const duplicatePayload = buildDuplicatePayload(job.settings_json)

  async function handleDuplicateJob() {
    if (!duplicatePayload) {
      return
    }

    const createdJob = await duplicateMutation.mutateAsync(duplicatePayload)
    navigate(
      buildSiteOverviewPath(createdJob.site_id, {
        activeCrawlId: createdJob.id,
        baselineCrawlId: job?.id,
      }),
    )
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('jobs.detail.overviewEyebrow')}</p>
              <StatusBadge status={job.status} />
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-stone-950">
              {t('jobs.detail.title', { jobId: job.id })}
            </h1>
            <p className="text-sm text-stone-600">
              {t('jobs.detail.timeRange', {
                started: formatDateTime(job.started_at),
                finished: formatDateTime(job.finished_at),
              })}
            </p>
            <p className="break-all text-sm text-stone-600">
              {t('common.rootUrl')}: {' '}
              <span className="font-medium text-stone-900">
                {typeof job.settings_json.start_url === 'string' ? job.settings_json.start_url : '-'}
              </span>
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <a
              href={buildApiUrl(`/crawl-jobs/${job.id}/export/pages.csv`)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('jobs.detail.exportPages')}
            </a>
            <a
              href={buildApiUrl(`/crawl-jobs/${job.id}/export/links.csv`)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('jobs.detail.exportLinks')}
            </a>
            <a
              href={buildApiUrl(`/crawl-jobs/${job.id}/export/audit.csv`)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('jobs.detail.exportAudit')}
            </a>
            <Link
              to={buildSiteOverviewPath(job.site_id, {
                activeCrawlId: job.id,
              })}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('jobs.detail.openSiteWorkspace')}
            </Link>
            {duplicatePayload ? (
              <button
                type="button"
                onClick={() => void handleDuplicateJob()}
                disabled={duplicateMutation.isPending}
                className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {duplicateMutation.isPending ? t('jobs.detail.duplicatePending') : t('jobs.detail.duplicate')}
              </button>
            ) : null}
            {stopAllowed ? (
              <button
                type="button"
                onClick={() => stopMutation.mutate()}
                disabled={stopMutation.isPending}
                className="inline-flex rounded-full bg-rose-600 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-rose-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {stopMutation.isPending ? t('jobs.detail.stopPending') : t('jobs.detail.stop')}
              </button>
            ) : null}
          </div>
        </div>

        {stopMutation.isError ? (
          <div className="mt-4">
            <ErrorState
              title={t('jobs.detail.stopErrorTitle')}
              message={getUiErrorMessage(stopMutation.error, t)}
            />
          </div>
        ) : null}
        {duplicateMutation.isError ? (
          <div className="mt-4">
            <ErrorState
              title={t('jobs.detail.duplicateErrorTitle')}
              message={getUiErrorMessage(duplicateMutation.error, t)}
            />
          </div>
        ) : null}

        <div className="mt-5">
          <JobNavigation jobId={job.id} />
        </div>
      </section>

      <SummaryCards
        items={[
          { label: t('jobs.detail.summaryCards.pages'), value: job.summary_counts.total_pages },
          { label: t('jobs.detail.summaryCards.links'), value: job.summary_counts.total_links },
          { label: t('jobs.detail.summaryCards.renderedPages'), value: job.summary_counts.rendered_pages },
          { label: t('jobs.detail.summaryCards.jsHeavyLike'), value: job.summary_counts.js_heavy_like_pages },
          { label: t('jobs.detail.summaryCards.renderErrors'), value: job.summary_counts.pages_with_render_errors },
          { label: t('jobs.detail.summaryCards.schema'), value: job.summary_counts.pages_with_schema },
          { label: t('jobs.detail.summaryCards.gsc28d'), value: job.summary_counts.pages_with_gsc_28d },
          { label: t('jobs.detail.summaryCards.gscOpportunities'), value: job.summary_counts.gsc_opportunities_28d },
          { label: t('jobs.detail.summaryCards.queuedUrls'), value: job.progress.queued_urls },
          { label: t('jobs.detail.summaryCards.visitedPages'), value: job.progress.visited_pages },
          { label: t('jobs.detail.summaryCards.discoveredLinks'), value: job.progress.discovered_links },
          { label: t('jobs.detail.summaryCards.errors'), value: job.progress.errors_count },
        ]}
      />

      <div className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
        <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-stone-950">{t('jobs.detail.summaryCountsTitle')}</h2>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            {(Object.entries(job.summary_counts) as Array<[keyof CrawlJobSummaryCounts, number]>).map(([key, value]) => (
              <div key={key} className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3">
                <dt className="text-xs uppercase tracking-[0.18em] text-stone-500">{summaryCountLabels[key]}</dt>
                <dd className="mt-2 text-xl font-semibold text-stone-950">{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-stone-950">{t('jobs.detail.runtimeTitle')}</h2>
          <div className="mt-4 grid gap-3">
            <div className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3 text-sm text-stone-700">
              <p className="font-semibold text-stone-900">{t('common.created')}</p>
              <p className="mt-1">{formatDateTime(job.created_at)}</p>
            </div>
            <div className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3 text-sm text-stone-700">
              <p className="font-semibold text-stone-900">{t('jobs.detail.renderSettingsTitle')}</p>
              <dl className="mt-2 grid gap-2 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <dt>{t('jobs.detail.renderMode')}</dt>
                  <dd className="font-medium text-stone-900">{String(job.settings_json.render_mode ?? 'never')}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>{t('jobs.detail.renderTimeout')}</dt>
                  <dd className="font-medium text-stone-900">{String(job.settings_json.render_timeout_ms ?? '-')}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>{t('jobs.detail.renderLimit')}</dt>
                  <dd className="font-medium text-stone-900">
                    {String(job.settings_json.max_rendered_pages_per_job ?? '-')}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3">
              <p className="text-sm font-semibold text-stone-900">settings_json</p>
              <pre className="mt-2 overflow-x-auto text-xs text-stone-700">{prettyJson(job.settings_json)}</pre>
            </div>
            <div className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3">
              <p className="text-sm font-semibold text-stone-900">stats_json</p>
              <pre className="mt-2 overflow-x-auto text-xs text-stone-700">{prettyJson(job.stats_json)}</pre>
            </div>
          </div>
        </section>
      </div>

      <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-stone-950">{t('jobs.detail.nextStepsTitle')}</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            to={`/jobs/${job.id}/pages`}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('jobs.detail.inspectPages')}
          </Link>
          <Link
            to={`/jobs/${job.id}/links`}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('jobs.detail.inspectLinks')}
          </Link>
          <Link
            to={`/jobs/${job.id}/audit`}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('jobs.detail.openAudit')}
          </Link>
          <Link
            to={`/jobs/${job.id}/opportunities`}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('jobs.detail.openOpportunities')}
          </Link>
          <Link
            to={`/jobs/${job.id}/gsc`}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('jobs.detail.openGsc')}
          </Link>
          <Link
            to={`/jobs/${job.id}/trends`}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('jobs.detail.openTrends')}
          </Link>
        </div>
      </section>
      {job.summary_counts.total_pages === 0 && job.status === 'pending' ? (
        <EmptyState
          title={t('jobs.detail.waitingTitle')}
          description={t('jobs.detail.waitingDescription')}
        />
      ) : null}
    </div>
  )
}

function buildDuplicatePayload(settings: Record<string, unknown>): CrawlJobCreateInput | null {
  const rootUrl = typeof settings.start_url === 'string' ? settings.start_url : null
  if (!rootUrl) {
    return null
  }

  const maxUrls = typeof settings.max_urls === 'number' && Number.isFinite(settings.max_urls) ? settings.max_urls : 500
  const maxDepth = typeof settings.max_depth === 'number' && Number.isFinite(settings.max_depth) ? settings.max_depth : 10
  const requestDelay =
    typeof settings.delay === 'number' && Number.isFinite(settings.delay)
      ? settings.delay
      : typeof settings.request_delay === 'number' && Number.isFinite(settings.request_delay)
        ? settings.request_delay
        : 0.25
  const renderMode =
    typeof settings.render_mode === 'string' &&
    ['never', 'auto', 'always'].includes(settings.render_mode)
      ? (settings.render_mode as CrawlJobCreateInput['render_mode'])
      : 'auto'
  const renderTimeoutMs =
    typeof settings.render_timeout_ms === 'number' && Number.isFinite(settings.render_timeout_ms)
      ? settings.render_timeout_ms
      : 8000
  const maxRenderedPagesPerJob =
    typeof settings.max_rendered_pages_per_job === 'number' &&
    Number.isFinite(settings.max_rendered_pages_per_job)
      ? settings.max_rendered_pages_per_job
      : 25

  return {
    root_url: rootUrl,
    max_urls: maxUrls,
    max_depth: maxDepth,
    delay: requestDelay,
    render_mode: renderMode,
    render_timeout_ms: renderTimeoutMs,
    max_rendered_pages_per_job: maxRenderedPagesPerJob,
  }
}
