import { startTransition, useMemo } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'

import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { PaginationControls } from '../../components/PaginationControls'
import { SortControls } from '../../components/SortControls'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { PagesQueryParams, PagesSortBy, SortOrder } from '../../types/api'
import { formatDateTime, formatNullable, formatResponseTime, truncateText } from '../../utils/format'
import { mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
import { usePagesQuery } from './api'

const sortOptions = [
  { label: 'URL', value: 'url' },
  { label: 'Status code', value: 'status_code' },
  { label: 'Depth', value: 'depth' },
  { label: 'Title', value: 'title' },
  { label: 'Fetched at', value: 'fetched_at' },
  { label: 'Response time', value: 'response_time_ms' },
]

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

function getBooleanFilterValue(searchParams: URLSearchParams, key: string) {
  const value = searchParams.get(key)
  return value === 'true' || value === 'false' ? value : ''
}

function readPagesParams(searchParams: URLSearchParams): PagesQueryParams {
  const sortBy = searchParams.get('sort_by')
  const sortOrder = searchParams.get('sort_order')

  return {
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), 25),
    sort_by: (sortBy ?? 'url') as PagesSortBy,
    sort_order: sortOrder === 'desc' ? 'desc' : 'asc',
    has_title: searchParams.get('has_title') === null ? undefined : searchParams.get('has_title') === 'true',
    has_meta_description:
      searchParams.get('has_meta_description') === null
        ? undefined
        : searchParams.get('has_meta_description') === 'true',
    has_h1: searchParams.get('has_h1') === null ? undefined : searchParams.get('has_h1') === 'true',
    canonical_missing:
      searchParams.get('canonical_missing') === null
        ? undefined
        : searchParams.get('canonical_missing') === 'true',
    robots_meta_contains: searchParams.get('robots_meta_contains') || undefined,
    non_indexable_like:
      searchParams.get('non_indexable_like') === null
        ? undefined
        : searchParams.get('non_indexable_like') === 'true',
    status_code_min: parseIntegerParam(searchParams.get('status_code_min'), undefined),
    status_code_max: parseIntegerParam(searchParams.get('status_code_max'), undefined),
  }
}

export function PagesPage() {
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? `Job #${jobId} pages` : 'Pages')

  if (jobId === null) {
    return <ErrorState title="Invalid job id" message="The route does not contain a valid numeric job id." />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const pagesParams = useMemo(() => readPagesParams(searchParams), [searchParams])
  const pagesQuery = usePagesQuery(jobId, pagesParams)

  function updateParams(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function updateFilter(key: string, value: string) {
    updateParams({
      [key]: value || undefined,
      page: 1,
    })
  }

  function resetFilters() {
    updateParams({
      page: 1,
      has_title: undefined,
      has_meta_description: undefined,
      has_h1: undefined,
      canonical_missing: undefined,
      robots_meta_contains: undefined,
      non_indexable_like: undefined,
      status_code_min: undefined,
      status_code_max: undefined,
    })
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.22em] text-teal-700">Pages</p>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-stone-950">Crawled pages for job #{jobId}</h1>
            <p className="mt-2 text-sm text-stone-600">
              Filter and sort directly from the URL to keep the current analysis shareable and refresh-safe.
            </p>
          </div>
          <JobNavigation jobId={jobId} />
        </div>
      </section>

      <FilterPanel
        title="Filters"
        description="Changes update the query string and refetch the backend list."
        onReset={resetFilters}
      >
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Has title</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_title')}
            onChange={(event) => updateFilter('has_title', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Has meta description</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_meta_description')}
            onChange={(event) => updateFilter('has_meta_description', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Has H1</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_h1')}
            onChange={(event) => updateFilter('has_h1', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Canonical missing</span>
          <select
            value={getBooleanFilterValue(searchParams, 'canonical_missing')}
            onChange={(event) => updateFilter('canonical_missing', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Robots meta contains</span>
          <input
            value={searchParams.get('robots_meta_contains') ?? ''}
            onChange={(event) => updateFilter('robots_meta_contains', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="noindex"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Non-indexable like</span>
          <select
            value={getBooleanFilterValue(searchParams, 'non_indexable_like')}
            onChange={(event) => updateFilter('non_indexable_like', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Status code min</span>
          <input
            type="number"
            value={searchParams.get('status_code_min') ?? ''}
            onChange={(event) => updateFilter('status_code_min', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="200"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Status code max</span>
          <input
            type="number"
            value={searchParams.get('status_code_max') ?? ''}
            onChange={(event) => updateFilter('status_code_max', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="299"
          />
        </label>
      </FilterPanel>

      <SortControls
        sortBy={pagesParams.sort_by}
        sortOrder={pagesParams.sort_order as SortOrder}
        options={sortOptions}
        onSortByChange={(value) => updateParams({ sort_by: value, page: 1 })}
        onSortOrderChange={(value) => updateParams({ sort_order: value, page: 1 })}
      />

      {pagesQuery.isLoading ? <LoadingState label="Loading pages..." /> : null}
      {pagesQuery.isError ? (
        <ErrorState
          title="Pages request failed"
          message={pagesQuery.error instanceof Error ? pagesQuery.error.message : 'Unknown error'}
        />
      ) : null}
      {pagesQuery.isSuccess && pagesQuery.data.items.length === 0 ? (
        <EmptyState
          title="No pages matched the current filters"
          description="Adjust the filters or move back to the overview to inspect broader results."
        />
      ) : null}
      {pagesQuery.isSuccess && pagesQuery.data.items.length > 0 ? (
        <>
          <DataTable
            columns={[
              {
                key: 'url',
                header: 'URL',
                cell: (page) => (
                  <div className="max-w-md space-y-1">
                    <p className="break-all font-medium text-stone-900" title={page.url}>
                      {truncateText(page.url, 100)}
                    </p>
                    <p className="text-xs text-stone-500">{page.normalized_url}</p>
                  </div>
                ),
              },
              {
                key: 'status',
                header: 'Status',
                cell: (page) => formatNullable(page.status_code),
              },
              {
                key: 'title',
                header: 'Title',
                cell: (page) => <span title={page.title ?? ''}>{truncateText(page.title, 72)}</span>,
              },
              {
                key: 'meta',
                header: 'Meta description',
                cell: (page) => (
                  <span title={page.meta_description ?? ''}>{truncateText(page.meta_description, 72)}</span>
                ),
              },
              {
                key: 'h1',
                header: 'H1',
                cell: (page) => <span title={page.h1 ?? ''}>{truncateText(page.h1, 52)}</span>,
              },
              {
                key: 'canonical',
                header: 'Canonical',
                cell: (page) => <span title={page.canonical_url ?? ''}>{truncateText(page.canonical_url, 72)}</span>,
              },
              {
                key: 'robots',
                header: 'Robots',
                cell: (page) => <span title={page.robots_meta ?? ''}>{truncateText(page.robots_meta, 40)}</span>,
              },
              {
                key: 'depth',
                header: 'Depth',
                cell: (page) => page.depth,
              },
              {
                key: 'response',
                header: 'Response',
                cell: (page) => formatResponseTime(page.response_time_ms),
              },
              {
                key: 'fetched',
                header: 'Fetched at',
                cell: (page) => formatDateTime(page.fetched_at),
              },
            ]}
            rows={pagesQuery.data.items}
            rowKey={(page) => page.id}
          />
          <PaginationControls
            page={pagesQuery.data.page}
            pageSize={pagesQuery.data.page_size}
            totalItems={pagesQuery.data.total_items}
            totalPages={pagesQuery.data.total_pages}
            onPageChange={(page) => updateParams({ page })}
            onPageSizeChange={(pageSize) => updateParams({ page_size: pageSize, page: 1 })}
          />
        </>
      ) : null}
    </div>
  )
}
