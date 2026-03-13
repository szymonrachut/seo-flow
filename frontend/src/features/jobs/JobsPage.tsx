import { startTransition, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { SortControls } from '../../components/SortControls'
import { StatusBadge } from '../../components/StatusBadge'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { JobsListQueryParams } from '../../types/api'
import { formatDateTime } from '../../utils/format'
import { mergeSearchParams } from '../../utils/searchParams'
import { CreateJobForm } from './CreateJobForm'
import { useCreateCrawlJobMutation, useCrawlJobsQuery } from './api'

const sortOptions = [
  { label: 'Job ID', value: 'id' },
  { label: 'Created at', value: 'created_at' },
]

export function JobsPage() {
  useDocumentTitle('Jobs')

  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const sortBy = searchParams.get('sort_by') === 'created_at' ? 'created_at' : 'id'
  const sortOrder = searchParams.get('sort_order') === 'asc' ? 'asc' : 'desc'

  const queryParams = useMemo<JobsListQueryParams>(
    () => ({
      sort_by: sortBy,
      sort_order: sortOrder,
      limit: 100,
    }),
    [sortBy, sortOrder],
  )

  const jobsQuery = useCrawlJobsQuery(queryParams)
  const createMutation = useCreateCrawlJobMutation()

  async function handleCreateJob(payload: Parameters<typeof createMutation.mutateAsync>[0]) {
    const createdJob = await createMutation.mutateAsync(payload)
    navigate(`/jobs/${createdJob.id}`)
  }

  function updateSort(key: 'sort_by' | 'sort_order', value: string) {
    const next = mergeSearchParams(searchParams, { [key]: value })
    startTransition(() => setSearchParams(next))
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/75 p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.22em] text-teal-700">SEO crawler console</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-stone-950">Jobs and crawl control</h1>
        <p className="mt-3 max-w-3xl text-sm text-stone-600">
          Run local crawls, monitor status and jump into pages, links or audit output without leaving the browser.
        </p>
      </section>

      <div className="grid gap-6 xl:grid-cols-[380px,1fr]">
        <CreateJobForm
          onSubmit={handleCreateJob}
          isPending={createMutation.isPending}
          errorMessage={createMutation.error instanceof Error ? createMutation.error.message : null}
        />

        <div className="space-y-4">
          <SortControls
            label="Job ordering"
            sortBy={sortBy}
            sortOrder={sortOrder}
            options={sortOptions}
            onSortByChange={(value) => updateSort('sort_by', value)}
            onSortOrderChange={(value) => updateSort('sort_order', value)}
          />

          {jobsQuery.isLoading ? <LoadingState label="Loading crawl jobs..." /> : null}
          {jobsQuery.isError ? (
            <ErrorState
              title="Jobs list failed"
              message={jobsQuery.error instanceof Error ? jobsQuery.error.message : 'Unknown error'}
            />
          ) : null}
          {jobsQuery.isSuccess && jobsQuery.data.length === 0 ? (
            <EmptyState title="No crawl jobs yet" description="Create your first crawl job to populate the console." />
          ) : null}
          {jobsQuery.isSuccess && jobsQuery.data.length > 0 ? (
            <DataTable
              columns={[
                {
                  key: 'id',
                  header: 'Job',
                  cell: (job) => (
                    <div className="space-y-1">
                      <p className="font-semibold text-stone-900">#{job.id}</p>
                      <p className="max-w-xs break-all text-xs text-stone-500">{job.root_url ?? '-'}</p>
                    </div>
                  ),
                },
                {
                  key: 'status',
                  header: 'Status',
                  cell: (job) => <StatusBadge status={job.status} />,
                },
                {
                  key: 'started',
                  header: 'Started',
                  cell: (job) => formatDateTime(job.started_at),
                },
                {
                  key: 'finished',
                  header: 'Finished',
                  cell: (job) => formatDateTime(job.finished_at),
                },
                {
                  key: 'pages',
                  header: 'Pages',
                  cell: (job) => job.total_pages,
                },
                {
                  key: 'internal',
                  header: 'Internal links',
                  cell: (job) => job.total_internal_links,
                },
                {
                  key: 'external',
                  header: 'External links',
                  cell: (job) => job.total_external_links,
                },
                {
                  key: 'errors',
                  header: 'Errors',
                  cell: (job) => job.total_errors,
                },
                {
                  key: 'actions',
                  header: 'Actions',
                  cell: (job) => (
                    <Link
                      to={`/jobs/${job.id}`}
                      className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                    >
                      Open
                    </Link>
                  ),
                },
              ]}
              rows={jobsQuery.data}
              rowKey={(job) => job.id}
            />
          ) : null}
        </div>
      </div>
    </div>
  )
}
