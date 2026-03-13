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
import type { LinksQueryParams, LinksSortBy, SortOrder } from '../../types/api'
import { formatBoolean, truncateText } from '../../utils/format'
import { mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
import { useLinksQuery } from './api'

const sortOptions = [
  { label: 'Source URL', value: 'source_url' },
  { label: 'Target URL', value: 'target_url' },
  { label: 'Target domain', value: 'target_domain' },
  { label: 'Is internal', value: 'is_internal' },
  { label: 'Is nofollow', value: 'is_nofollow' },
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

function readLinksParams(searchParams: URLSearchParams): LinksQueryParams {
  const sortBy = searchParams.get('sort_by')

  return {
    page: parseIntegerParam(searchParams.get('page'), 1),
    page_size: parseIntegerParam(searchParams.get('page_size'), 25),
    sort_by: (sortBy ?? 'source_url') as LinksSortBy,
    sort_order: searchParams.get('sort_order') === 'desc' ? 'desc' : 'asc',
    is_internal:
      searchParams.get('is_internal') === null ? undefined : searchParams.get('is_internal') === 'true',
    is_nofollow:
      searchParams.get('is_nofollow') === null ? undefined : searchParams.get('is_nofollow') === 'true',
    target_domain: searchParams.get('target_domain') || undefined,
    has_anchor:
      searchParams.get('has_anchor') === null ? undefined : searchParams.get('has_anchor') === 'true',
  }
}

export function LinksPage() {
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? `Job #${jobId} links` : 'Links')

  if (jobId === null) {
    return <ErrorState title="Invalid job id" message="The route does not contain a valid numeric job id." />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const linksParams = useMemo(() => readLinksParams(searchParams), [searchParams])
  const linksQuery = useLinksQuery(jobId, linksParams)

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
      is_internal: undefined,
      is_nofollow: undefined,
      target_domain: undefined,
      has_anchor: undefined,
    })
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.22em] text-teal-700">Links</p>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-stone-950">Link graph for job #{jobId}</h1>
            <p className="mt-2 text-sm text-stone-600">
              Inspect internal and external links without reimplementing crawler logic in the browser.
            </p>
          </div>
          <JobNavigation jobId={jobId} />
        </div>
      </section>

      <FilterPanel
        title="Filters"
        description="Filters and pagination remain in the URL so the current view can be refreshed safely."
        onReset={resetFilters}
      >
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Is internal</span>
          <select
            value={getBooleanFilterValue(searchParams, 'is_internal')}
            onChange={(event) => updateFilter('is_internal', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Is nofollow</span>
          <select
            value={getBooleanFilterValue(searchParams, 'is_nofollow')}
            onChange={(event) => updateFilter('is_nofollow', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Target domain</span>
          <input
            value={searchParams.get('target_domain') ?? ''}
            onChange={(event) => updateFilter('target_domain', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder="example.com"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>Has anchor</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_anchor')}
            onChange={(event) => updateFilter('has_anchor', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">Any</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
      </FilterPanel>

      <SortControls
        sortBy={linksParams.sort_by}
        sortOrder={linksParams.sort_order as SortOrder}
        options={sortOptions}
        onSortByChange={(value) => updateParams({ sort_by: value, page: 1 })}
        onSortOrderChange={(value) => updateParams({ sort_order: value, page: 1 })}
      />

      {linksQuery.isLoading ? <LoadingState label="Loading links..." /> : null}
      {linksQuery.isError ? (
        <ErrorState
          title="Links request failed"
          message={linksQuery.error instanceof Error ? linksQuery.error.message : 'Unknown error'}
        />
      ) : null}
      {linksQuery.isSuccess && linksQuery.data.items.length === 0 ? (
        <EmptyState
          title="No links matched the current filters"
          description="Clear one or more filters to widen the current link slice."
        />
      ) : null}
      {linksQuery.isSuccess && linksQuery.data.items.length > 0 ? (
        <>
          <DataTable
            columns={[
              {
                key: 'source',
                header: 'Source URL',
                cell: (link) => <span title={link.source_url}>{truncateText(link.source_url, 80)}</span>,
              },
              {
                key: 'target',
                header: 'Target URL',
                cell: (link) => <span title={link.target_url}>{truncateText(link.target_url, 80)}</span>,
              },
              {
                key: 'domain',
                header: 'Target domain',
                cell: (link) => truncateText(link.target_domain, 36),
              },
              {
                key: 'anchor',
                header: 'Anchor text',
                cell: (link) => <span title={link.anchor_text ?? ''}>{truncateText(link.anchor_text, 48)}</span>,
              },
              {
                key: 'internal',
                header: 'Internal',
                cell: (link) => formatBoolean(link.is_internal),
              },
              {
                key: 'nofollow',
                header: 'Nofollow',
                cell: (link) => formatBoolean(link.is_nofollow),
              },
            ]}
            rows={linksQuery.data.items}
            rowKey={(link) => link.id}
          />
          <PaginationControls
            page={linksQuery.data.page}
            pageSize={linksQuery.data.page_size}
            totalItems={linksQuery.data.total_items}
            totalPages={linksQuery.data.total_pages}
            onPageChange={(page) => updateParams({ page })}
            onPageSizeChange={(pageSize) => updateParams({ page_size: pageSize, page: 1 })}
          />
        </>
      ) : null}
    </div>
  )
}
