import { Link, useParams } from 'react-router-dom'

import { buildApiUrl } from '../../api/client'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { formatDateTime, prettyJson } from '../../utils/format'
import { JobNavigation } from './JobNavigation'
import { useCrawlJobDetailQuery, useStopCrawlJobMutation } from './api'

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

export function JobDetailPage() {
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? `Job #${jobId}` : 'Job')

  if (jobId === null) {
    return <ErrorState title="Invalid job id" message="The route does not contain a valid numeric job id." />
  }

  const jobQuery = useCrawlJobDetailQuery(jobId)
  const stopMutation = useStopCrawlJobMutation(jobId)

  if (jobQuery.isLoading) {
    return <LoadingState label={`Loading job #${jobId}...`} />
  }

  if (jobQuery.isError) {
    return (
      <ErrorState
        title="Job detail failed"
        message={jobQuery.error instanceof Error ? jobQuery.error.message : 'Unknown error'}
      />
    )
  }

  const job = jobQuery.data
  if (!job) {
    return <EmptyState title="Job not available" description="The backend returned an empty job response." />
  }

  const stopAllowed = job.status === 'pending' || job.status === 'running'

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <p className="text-xs uppercase tracking-[0.22em] text-teal-700">Job overview</p>
              <StatusBadge status={job.status} />
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-stone-950">Crawl job #{job.id}</h1>
            <p className="text-sm text-stone-600">
              Started {formatDateTime(job.started_at)} - Finished {formatDateTime(job.finished_at)}
            </p>
            <p className="break-all text-sm text-stone-600">
              Root URL:{' '}
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
              Export pages.csv
            </a>
            <a
              href={buildApiUrl(`/crawl-jobs/${job.id}/export/links.csv`)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              Export links.csv
            </a>
            <a
              href={buildApiUrl(`/crawl-jobs/${job.id}/export/audit.csv`)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              Export audit.csv
            </a>
            {stopAllowed ? (
              <button
                type="button"
                onClick={() => stopMutation.mutate()}
                disabled={stopMutation.isPending}
                className="inline-flex rounded-full bg-rose-600 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-rose-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {stopMutation.isPending ? 'Stopping...' : 'Stop job'}
              </button>
            ) : null}
          </div>
        </div>

        {stopMutation.isError ? (
          <div className="mt-4">
            <ErrorState
              title="Stop request failed"
              message={stopMutation.error instanceof Error ? stopMutation.error.message : 'Unknown error'}
            />
          </div>
        ) : null}

        <div className="mt-5">
          <JobNavigation jobId={job.id} />
        </div>
      </section>

      <SummaryCards
        items={[
          { label: 'Pages', value: job.summary_counts.total_pages },
          { label: 'Links', value: job.summary_counts.total_links },
          { label: 'Missing title', value: job.summary_counts.pages_missing_title },
          { label: 'Broken internal', value: job.summary_counts.broken_internal_links },
          { label: 'Queued URLs', value: job.progress.queued_urls },
          { label: 'Visited pages', value: job.progress.visited_pages },
          { label: 'Discovered links', value: job.progress.discovered_links },
          { label: 'Errors', value: job.progress.errors_count },
        ]}
      />

      <div className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
        <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-stone-950">Summary counts</h2>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            {Object.entries(job.summary_counts).map(([key, value]) => (
              <div key={key} className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3">
                <dt className="text-xs uppercase tracking-[0.18em] text-stone-500">{key}</dt>
                <dd className="mt-2 text-xl font-semibold text-stone-950">{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-stone-950">Settings and runtime</h2>
          <div className="mt-4 grid gap-3">
            <div className="rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3 text-sm text-stone-700">
              <p className="font-semibold text-stone-900">Created</p>
              <p className="mt-1">{formatDateTime(job.created_at)}</p>
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
        <h2 className="text-lg font-semibold text-stone-950">Next steps</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            to={`/jobs/${job.id}/pages`}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            Inspect pages
          </Link>
          <Link
            to={`/jobs/${job.id}/links`}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            Inspect links
          </Link>
          <Link
            to={`/jobs/${job.id}/audit`}
            className="rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            Open audit
          </Link>
        </div>
      </section>
      {job.summary_counts.total_pages === 0 && job.status === 'pending' ? (
        <EmptyState
          title="Waiting for first results"
          description="This job has been created but no pages have been persisted yet. The overview polls automatically while the job is active."
        />
      ) : null}
    </div>
  )
}
