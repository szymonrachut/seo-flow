import { startTransition, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useSearchParams } from 'react-router-dom'

import { buildApiUrl } from '../../api/client'
import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { PaginationControls } from '../../components/PaginationControls'
import { QuickFilterBar } from '../../components/QuickFilterBar'
import { UrlActions } from '../../components/UrlActions'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { LinkRecord, LinksQueryParams, SortOrder } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatBoolean, formatNullable } from '../../utils/format'
import { mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
import { useLinksQuery } from './api'

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
    sort_by: (sortBy ?? 'source_url') as LinksQueryParams['sort_by'],
    sort_order: searchParams.get('sort_order') === 'desc' ? 'desc' : 'asc',
    is_internal:
      searchParams.get('is_internal') === null ? undefined : searchParams.get('is_internal') === 'true',
    is_nofollow:
      searchParams.get('is_nofollow') === null ? undefined : searchParams.get('is_nofollow') === 'true',
    target_domain: searchParams.get('target_domain') || undefined,
    has_anchor:
      searchParams.get('has_anchor') === null ? undefined : searchParams.get('has_anchor') === 'true',
    broken_internal:
      searchParams.get('broken_internal') === null ? undefined : searchParams.get('broken_internal') === 'true',
    redirecting_internal:
      searchParams.get('redirecting_internal') === null
        ? undefined
        : searchParams.get('redirecting_internal') === 'true',
    unresolved_internal:
      searchParams.get('unresolved_internal') === null
        ? undefined
        : searchParams.get('unresolved_internal') === 'true',
    to_noindex_like:
      searchParams.get('to_noindex_like') === null
        ? undefined
        : searchParams.get('to_noindex_like') === 'true',
    to_canonicalized:
      searchParams.get('to_canonicalized') === null
        ? undefined
        : searchParams.get('to_canonicalized') === 'true',
    redirect_chain:
      searchParams.get('redirect_chain') === null
        ? undefined
        : searchParams.get('redirect_chain') === 'true',
  }
}

function buildLinksExportHref(jobId: number, searchParams: URLSearchParams, filtered: boolean) {
  const query = filtered ? searchParams.toString() : ''
  return buildApiUrl(`/crawl-jobs/${jobId}/export/links.csv${query ? `?${query}` : ''}`)
}

function isLinksViewFiltered(searchParams: URLSearchParams) {
  return Array.from(searchParams.keys()).some((key) => key !== 'page' && key !== 'page_size' && key !== 'sort_by' && key !== 'sort_order')
}

function buildLinkSignals(link: LinkRecord, translate: (key: string) => string) {
  const signals: string[] = []

  if (link.broken_internal) {
    signals.push(translate('links.signals.brokenInternal'))
  }
  if (link.redirecting_internal) {
    signals.push(translate('links.signals.redirectingInternal'))
  }
  if (link.unresolved_internal) {
    signals.push(translate('links.signals.unresolvedInternal'))
  }
  if (link.to_noindex_like) {
    signals.push(translate('links.signals.toNoindexLike'))
  }
  if (link.to_canonicalized) {
    signals.push(translate('links.signals.toCanonicalized'))
  }
  if (link.redirect_chain) {
    signals.push(translate('links.signals.redirectChain'))
  }
  if (!link.anchor_text) {
    signals.push(translate('links.signals.noAnchor'))
  }

  return signals
}

function renderSignal(label: string) {
  return (
    <span className="inline-flex rounded-full border border-stone-300 bg-stone-100 px-2 py-0.5 text-[11px] font-medium text-stone-700">
      {label}
    </span>
  )
}

export function LinksPage() {
  const { t } = useTranslation()
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? t('documentTitle.links', { jobId }) : t('nav.links'))

  if (jobId === null) {
    return <ErrorState title={t('links.invalidIdTitle')} message={t('links.invalidIdMessage')} />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const linksParams = useMemo(() => readLinksParams(searchParams), [searchParams])
  const linksQuery = useLinksQuery(jobId, linksParams)
  const filteredView = isLinksViewFiltered(searchParams)

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

  function applyPreset(updates: Record<string, string | number | undefined>) {
    updateParams({
      page: 1,
      ...updates,
    })
  }

  function resetFilters() {
    updateParams({
      page: 1,
      is_internal: undefined,
      is_nofollow: undefined,
      target_domain: undefined,
      has_anchor: undefined,
      broken_internal: undefined,
      redirecting_internal: undefined,
      unresolved_internal: undefined,
      to_noindex_like: undefined,
      to_canonicalized: undefined,
      redirect_chain: undefined,
    })
  }

  function handleTableSort(sortBy: string, sortOrder: SortOrder) {
    updateParams({
      sort_by: sortBy,
      sort_order: sortOrder,
      page: 1,
    })
  }

  const quickFilters = [
    {
      label: t('links.quickFilters.external'),
      isActive: linksParams.is_internal === false,
      onClick: () => applyPreset({ is_internal: 'false' }),
    },
    {
      label: t('links.quickFilters.internal'),
      isActive: linksParams.is_internal === true,
      onClick: () => applyPreset({ is_internal: 'true' }),
    },
    {
      label: t('links.quickFilters.nofollow'),
      isActive: linksParams.is_nofollow === true,
      onClick: () => applyPreset({ is_nofollow: 'true' }),
    },
    {
      label: t('links.quickFilters.missingAnchor'),
      isActive: linksParams.has_anchor === false,
      onClick: () => applyPreset({ has_anchor: 'false' }),
    },
    {
      label: t('links.quickFilters.brokenInternal'),
      isActive: linksParams.broken_internal === true,
      onClick: () => applyPreset({ broken_internal: 'true' }),
    },
    {
      label: t('links.quickFilters.redirectingInternal'),
      isActive: linksParams.redirecting_internal === true,
      onClick: () => applyPreset({ redirecting_internal: 'true' }),
    },
    {
      label: t('links.quickFilters.unresolvedInternal'),
      isActive: linksParams.unresolved_internal === true,
      onClick: () => applyPreset({ unresolved_internal: 'true' }),
    },
    {
      label: t('links.quickFilters.toNoindexLike'),
      isActive: linksParams.to_noindex_like === true,
      onClick: () => applyPreset({ to_noindex_like: 'true' }),
    },
    {
      label: t('links.quickFilters.toCanonicalized'),
      isActive: linksParams.to_canonicalized === true,
      onClick: () => applyPreset({ to_canonicalized: 'true' }),
    },
    {
      label: t('links.quickFilters.redirectChain'),
      isActive: linksParams.redirect_chain === true,
      onClick: () => applyPreset({ redirect_chain: 'true' }),
    },
  ]

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('links.page.eyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">
              {t('links.page.title', { jobId })}
            </h1>
            <p className="mt-2 text-sm text-stone-600">{t('links.page.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <JobNavigation jobId={jobId} />
            <a
              href={buildLinksExportHref(jobId, searchParams, false)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('links.page.exportFull')}
            </a>
            <a
              href={buildLinksExportHref(jobId, searchParams, true)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {filteredView ? t('links.page.exportCurrentView') : t('links.page.exportCurrentView')}
            </a>
          </div>
        </div>
      </section>

      <QuickFilterBar title={t('links.quickFilters.title')} items={quickFilters} />

      <FilterPanel
        title={t('links.filters.title')}
        description={t('links.filters.description')}
        onReset={resetFilters}
      >
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.isInternal')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'is_internal')}
            onChange={(event) => updateFilter('is_internal', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.isNofollow')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'is_nofollow')}
            onChange={(event) => updateFilter('is_nofollow', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.targetDomain')}</span>
          <input
            value={searchParams.get('target_domain') ?? ''}
            onChange={(event) => updateFilter('target_domain', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
            placeholder={t('links.filters.targetDomainPlaceholder')}
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.hasAnchor')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'has_anchor')}
            onChange={(event) => updateFilter('has_anchor', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.brokenInternal')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'broken_internal')}
            onChange={(event) => updateFilter('broken_internal', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.redirectingInternal')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'redirecting_internal')}
            onChange={(event) => updateFilter('redirecting_internal', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.unresolvedInternal')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'unresolved_internal')}
            onChange={(event) => updateFilter('unresolved_internal', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.toNoindexLike')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'to_noindex_like')}
            onChange={(event) => updateFilter('to_noindex_like', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.toCanonicalized')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'to_canonicalized')}
            onChange={(event) => updateFilter('to_canonicalized', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('links.filters.redirectChain')}</span>
          <select
            value={getBooleanFilterValue(searchParams, 'redirect_chain')}
            onChange={(event) => updateFilter('redirect_chain', event.target.value)}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="true">{t('common.yes')}</option>
            <option value="false">{t('common.no')}</option>
          </select>
        </label>
      </FilterPanel>

      {linksQuery.isLoading ? <LoadingState label={t('links.page.loading')} /> : null}
      {linksQuery.isError ? (
        <ErrorState
          title={t('links.errors.requestTitle')}
          message={getUiErrorMessage(linksQuery.error, t)}
        />
      ) : null}
      {linksQuery.isSuccess && linksQuery.data.items.length === 0 ? (
        <EmptyState title={t('links.empty.title')} description={t('links.empty.description')} />
      ) : null}
      {linksQuery.isSuccess && linksQuery.data.items.length > 0 ? (
        <>
          <DataTable
            columns={[
              {
                key: 'source',
                header: t('links.table.sourceUrl'),
                sortKey: 'source_url',
                cell: (link) => (
                  <div className="max-w-[18rem]">
                    <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={link.source_url}>
                      {link.source_url}
                    </p>
                    <UrlActions
                      url={link.source_url}
                      openLabel={t('links.urlActions.openSource')}
                      copyLabel={t('links.urlActions.copySource')}
                    />
                  </div>
                ),
              },
              {
                key: 'target',
                header: t('links.table.targetUrl'),
                sortKey: 'target_url',
                cell: (link) => (
                  <div className="max-w-[18rem]">
                    <p className="font-medium text-stone-900 [overflow-wrap:anywhere]" title={link.target_url}>
                      {link.target_url}
                    </p>
                    <UrlActions
                      url={link.target_url}
                      openLabel={t('links.urlActions.openTarget')}
                      copyLabel={t('links.urlActions.copyTarget')}
                    />
                  </div>
                ),
              },
              {
                key: 'domain',
                header: t('links.table.targetDomain'),
                sortKey: 'target_domain',
                cell: (link) => (
                  <span className="block max-w-[10rem] [overflow-wrap:anywhere]" title={link.target_domain ?? ''}>
                    {link.target_domain ?? '-'}
                  </span>
                ),
              },
              {
                key: 'anchor',
                header: t('links.table.anchorText'),
                sortKey: 'anchor_text',
                cell: (link) => (
                  <span className="block max-w-[12rem] [overflow-wrap:anywhere]" title={link.anchor_text ?? ''}>
                    {link.anchor_text ?? '-'}
                  </span>
                ),
              },
              {
                key: 'status',
                header: t('links.table.targetStatus'),
                cell: (link) => formatNullable(link.target_status_code),
                cellClassName: 'whitespace-nowrap',
              },
              {
                key: 'hops',
                header: t('links.table.redirectHops'),
                cell: (link) => formatNullable(link.redirect_hops),
                cellClassName: 'whitespace-nowrap',
              },
              {
                key: 'final',
                header: t('links.table.finalUrl'),
                cell: (link) => (
                  <span className="block max-w-[16rem] [overflow-wrap:anywhere]" title={link.final_url ?? ''}>
                    {link.final_url ?? '-'}
                  </span>
                ),
              },
              {
                key: 'internal',
                header: t('links.table.internal'),
                sortKey: 'is_internal',
                cell: (link) => formatBoolean(link.is_internal),
                cellClassName: 'whitespace-nowrap',
              },
              {
                key: 'nofollow',
                header: t('links.table.nofollow'),
                sortKey: 'is_nofollow',
                cell: (link) => formatBoolean(link.is_nofollow),
                cellClassName: 'whitespace-nowrap',
              },
              {
                key: 'signals',
                header: t('links.table.signals'),
                cell: (link) => (
                  <div className="flex max-w-[13rem] flex-wrap gap-1.5">
                    {buildLinkSignals(link, t).map((signal) => renderSignal(signal))}
                  </div>
                ),
              },
            ]}
            rows={linksQuery.data.items}
            rowKey={(link) => link.id}
            sortBy={linksParams.sort_by}
            sortOrder={linksParams.sort_order as SortOrder}
            onSortChange={handleTableSort}
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
