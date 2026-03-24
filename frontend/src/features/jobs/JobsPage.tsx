import { startTransition, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { JobsListQueryParams, JobStatus, SortOrder } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime } from '../../utils/format'
import { mergeSearchParams } from '../../utils/searchParams'
import { buildSiteOverviewPath } from '../sites/routes'
import { CreateJobForm } from './CreateJobForm'
import { useCreateCrawlJobMutation, useCrawlJobsQuery } from './api'

const allowedSortKeys = new Set([
  'id',
  'created_at',
  'status',
  'started_at',
  'finished_at',
  'total_pages',
  'total_internal_links',
  'total_external_links',
  'total_errors',
])

export function JobsPage() {
  const { t } = useTranslation()
  useDocumentTitle(t('documentTitle.jobs'))

  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const rawSortBy = searchParams.get('sort_by')
  const sortBy = allowedSortKeys.has(rawSortBy ?? '') ? rawSortBy ?? 'id' : 'id'
  const sortOrder = searchParams.get('sort_order') === 'asc' ? 'asc' : 'desc'
  const statusFilter = searchParams.get('status_filter') || undefined
  const search = searchParams.get('search') || undefined

  const queryParams = useMemo<JobsListQueryParams>(
    () => ({
      sort_by: sortBy as JobsListQueryParams['sort_by'],
      sort_order: sortOrder,
      limit: 100,
      status_filter: statusFilter as JobStatus | undefined,
      search,
    }),
    [search, sortBy, sortOrder, statusFilter],
  )

  const jobsQuery = useCrawlJobsQuery(queryParams)
  const createMutation = useCreateCrawlJobMutation()

  async function handleCreateJob(payload: Parameters<typeof createMutation.mutateAsync>[0]) {
    const createdJob = await createMutation.mutateAsync(payload)
    navigate(
      buildSiteOverviewPath(createdJob.site_id, {
        activeCrawlId: createdJob.id,
      }),
    )
  }

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function handleTableSort(nextSortBy: string, nextSortOrder: SortOrder) {
    updateParams({
      sort_by: nextSortBy,
      sort_order: nextSortOrder,
    })
  }

  function resetFilters() {
    updateParams({
      status_filter: undefined,
      search: undefined,
    })
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/75 p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('jobs.page.eyebrow')}</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-stone-950">{t('jobs.page.title')}</h1>
        <p className="mt-3 max-w-3xl text-sm text-stone-600">{t('jobs.page.description')}</p>
      </section>

      <div className="grid gap-6 xl:grid-cols-[380px,1fr]">
        <CreateJobForm
          onSubmit={handleCreateJob}
          isPending={createMutation.isPending}
          errorMessage={createMutation.error ? getUiErrorMessage(createMutation.error, t) : null}
        />

        <div className="space-y-4">
          <FilterPanel
            title={t('jobs.filters.title')}
            description={t('jobs.filters.description')}
            onReset={resetFilters}
          >
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('common.status')}</span>
              <select
                value={statusFilter ?? ''}
                onChange={(event) => updateParams({ status_filter: event.target.value || undefined })}
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
              >
                <option value="">{t('common.any')}</option>
                <option value="pending">{t('jobs.status.pending')}</option>
                <option value="running">{t('jobs.status.running')}</option>
                <option value="finished">{t('jobs.status.finished')}</option>
                <option value="failed">{t('jobs.status.failed')}</option>
                <option value="stopped">{t('jobs.status.stopped')}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('common.search')}</span>
              <input
                value={search ?? ''}
                onChange={(event) => updateParams({ search: event.target.value || undefined })}
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
                placeholder={t('jobs.filters.searchPlaceholder')}
              />
            </label>
          </FilterPanel>

          {jobsQuery.isLoading ? <LoadingState label={t('jobs.page.loading')} /> : null}
          {jobsQuery.isError ? (
            <ErrorState
              title={t('jobs.errors.listTitle')}
              message={getUiErrorMessage(jobsQuery.error, t)}
            />
          ) : null}
          {jobsQuery.isSuccess && jobsQuery.data.length === 0 ? (
            <EmptyState title={t('jobs.empty.title')} description={t('jobs.empty.description')} />
          ) : null}
          {jobsQuery.isSuccess && jobsQuery.data.length > 0 ? (
            <DataTable
              columns={[
                {
                  key: 'id',
                  header: t('jobs.table.job'),
                  sortKey: 'id',
                  cell: (job) => (
                    <div className="max-w-[15rem] space-y-1">
                      <p className="font-semibold text-stone-900">#{job.id}</p>
                      <p className="text-xs text-stone-500 [overflow-wrap:anywhere]" title={job.root_url ?? ''}>
                        {job.root_url ?? '-'}
                      </p>
                    </div>
                  ),
                },
                {
                  key: 'status',
                  header: t('jobs.table.status'),
                  sortKey: 'status',
                  cell: (job) => <StatusBadge status={job.status} />,
                },
                {
                  key: 'started',
                  header: t('jobs.table.started'),
                  sortKey: 'started_at',
                  cell: (job) => formatDateTime(job.started_at),
                  cellClassName: 'whitespace-nowrap',
                },
                {
                  key: 'finished',
                  header: t('jobs.table.finished'),
                  sortKey: 'finished_at',
                  cell: (job) => formatDateTime(job.finished_at),
                  cellClassName: 'whitespace-nowrap',
                },
                {
                  key: 'pages',
                  header: t('jobs.table.pages'),
                  sortKey: 'total_pages',
                  cell: (job) => job.total_pages,
                  cellClassName: 'whitespace-nowrap',
                },
                {
                  key: 'internal',
                  header: t('jobs.table.internalLinks'),
                  sortKey: 'total_internal_links',
                  cell: (job) => job.total_internal_links,
                  cellClassName: 'whitespace-nowrap',
                },
                {
                  key: 'external',
                  header: t('jobs.table.externalLinks'),
                  sortKey: 'total_external_links',
                  cell: (job) => job.total_external_links,
                  cellClassName: 'whitespace-nowrap',
                },
                {
                  key: 'errors',
                  header: t('jobs.table.errors'),
                  sortKey: 'total_errors',
                  cell: (job) => job.total_errors,
                  cellClassName: 'whitespace-nowrap',
                },
                {
                  key: 'actions',
                  header: t('jobs.table.open'),
                  cell: (job) => (
                    <Link
                      to={`/jobs/${job.id}`}
                      className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                    >
                      {t('jobs.table.open')}
                    </Link>
                  ),
                },
              ]}
              rows={jobsQuery.data}
              rowKey={(job) => job.id}
              sortBy={sortBy}
              sortOrder={sortOrder}
              onSortChange={handleTableSort}
            />
          ) : null}
        </div>
      </div>
    </div>
  )
}
