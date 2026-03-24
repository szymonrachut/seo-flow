import { startTransition, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { DataTable } from '../../components/DataTable'
import { DataViewHeader } from '../../components/DataViewHeader'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { QuickFilterBar } from '../../components/QuickFilterBar'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { AuditCompareSectionStatus, SortOrder } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatCrawlDateTime } from '../../utils/format'
import {
  mergeSearchParams,
  parseCsvParam,
  serializeCsvParam,
  toggleCsvParamValue,
} from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import { buildSiteAuditPath } from '../sites/routes'
import { useSiteAuditCompareQuery } from './api'

const AUDIT_COMPARE_STATUSES: AuditCompareSectionStatus[] = [
  'resolved',
  'new',
  'improved',
  'worsened',
  'unchanged',
]

function readSingleStatus(value: string | null) {
  const values = Array.from(parseCsvParam(value, AUDIT_COMPARE_STATUSES))
  return values.length === 1 ? values[0] : ''
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

function statusTone(status: AuditCompareSectionStatus): 'stone' | 'rose' | 'amber' | 'teal' {
  if (status === 'worsened' || status === 'new') {
    return 'rose'
  }
  if (status === 'improved' || status === 'resolved') {
    return 'teal'
  }
  return 'stone'
}

export function SiteAuditComparePage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  useDocumentTitle(t('documentTitle.auditCompare', { domain: site.domain }))

  const [searchParams, setSearchParams] = useSearchParams()
  const selectedStatuses = useMemo(() => parseCsvParam(searchParams.get('status'), AUDIT_COMPARE_STATUSES), [searchParams])
  const params = useMemo(
    () => ({
      active_crawl_id: activeCrawlId ?? undefined,
      baseline_crawl_id: baselineCrawlId ?? undefined,
      status: searchParams.get('status') || undefined,
    }),
    [activeCrawlId, baselineCrawlId, searchParams],
  )
  const compareQuery = useSiteAuditCompareQuery(site.id, params)

  function updateParams(updates: Record<string, string | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function toggleStatus(status: AuditCompareSectionStatus) {
    const next = toggleCsvParamValue(selectedStatuses, status)
    updateParams({ status: serializeCsvParam(next) })
  }

  function resetFilters() {
    updateParams({ status: undefined })
  }

  const quickFilters = [
    { label: t('auditCompare.quickFilters.resolved'), isActive: selectedStatuses.has('resolved'), onClick: () => toggleStatus('resolved') },
    { label: t('auditCompare.quickFilters.new'), isActive: selectedStatuses.has('new'), onClick: () => toggleStatus('new') },
    { label: t('auditCompare.quickFilters.improved'), isActive: selectedStatuses.has('improved'), onClick: () => toggleStatus('improved') },
    { label: t('auditCompare.quickFilters.worsened'), isActive: selectedStatuses.has('worsened'), onClick: () => toggleStatus('worsened') },
    { label: t('auditCompare.quickFilters.unchanged'), isActive: selectedStatuses.has('unchanged'), onClick: () => toggleStatus('unchanged') },
  ]

  if (compareQuery.isLoading) {
    return <LoadingState label={t('auditCompare.loading')} />
  }

  if (compareQuery.isError) {
    return <ErrorState title={t('auditCompare.errorTitle')} message={getUiErrorMessage(compareQuery.error, t)} />
  }

  const payload = compareQuery.data
  if (!payload) {
    return <EmptyState title={t('auditCompare.emptyTitle')} description={t('auditCompare.emptyDescription')} />
  }

  if (!payload.context.compare_available) {
    return (
      <EmptyState
        title={t('auditCompare.compareUnavailableTitle')}
        description={payload.context.compare_unavailable_reason ?? t('auditCompare.compareUnavailableDescription')}
      />
    )
  }

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('auditCompare.eyebrow')}
        title={t('auditCompare.title')}
        description={t('auditCompare.description', {
          active: formatCrawlDateTime(payload.context.active_crawl),
          baseline: formatCrawlDateTime(payload.context.baseline_crawl),
        })}
        contextChips={[
          {
            label: 'Active',
            value: payload.context.active_crawl_id ? `#${payload.context.active_crawl_id}` : '-',
          },
          {
            label: 'Baseline',
            value: payload.context.baseline_crawl_id ? `#${payload.context.baseline_crawl_id}` : '-',
          },
          {
            label: 'Compare',
            value: payload.context.compare_available ? 'Ready' : 'Waiting',
            tone: payload.context.compare_available ? 'success' : 'warning',
          },
        ]}
        primaryAction={{
          key: 'open-current-state-audit',
          label: t('auditCompare.actions.openCurrentState'),
          to: buildSiteAuditPath(site.id, { activeCrawlId, baselineCrawlId }),
        }}
        operations={
          activeCrawlId
            ? [
                {
                  key: 'open-active-crawl',
                  label: t('auditCompare.actions.openActiveCrawl'),
                  to: `/jobs/${activeCrawlId}`,
                },
              ]
            : []
        }
      />

      <SummaryCards
        items={[
          { label: t('auditCompare.summary.resolvedSections'), value: payload.summary.resolved_sections },
          { label: t('auditCompare.summary.newSections'), value: payload.summary.new_sections },
          { label: t('auditCompare.summary.improvedSections'), value: payload.summary.improved_sections },
          { label: t('auditCompare.summary.worsenedSections'), value: payload.summary.worsened_sections },
          { label: t('auditCompare.summary.resolvedIssues'), value: payload.summary.resolved_issues_total },
          { label: t('auditCompare.summary.newIssues'), value: payload.summary.new_issues_total },
          { label: t('auditCompare.summary.activeIssues'), value: payload.summary.active_issues_total },
          { label: t('auditCompare.summary.baselineIssues'), value: payload.summary.baseline_issues_total },
        ]}
      />

      <QuickFilterBar title={t('auditCompare.quickFilters.title')} items={quickFilters} onReset={resetFilters} />

      <FilterPanel title={t('auditCompare.filters.title')} description={t('auditCompare.filters.description')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700">
          <span>{t('auditCompare.filters.status')}</span>
          <select
            value={readSingleStatus(params.status ?? null)}
            onChange={(event) => updateParams({ status: event.target.value || undefined })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2"
          >
            <option value="">{t('common.any')}</option>
            <option value="resolved">{t('auditCompare.status.resolved')}</option>
            <option value="new">{t('auditCompare.status.new')}</option>
            <option value="improved">{t('auditCompare.status.improved')}</option>
            <option value="worsened">{t('auditCompare.status.worsened')}</option>
            <option value="unchanged">{t('auditCompare.status.unchanged')}</option>
          </select>
        </label>
      </FilterPanel>

      {payload.sections.length === 0 ? (
        <EmptyState title={t('auditCompare.emptyTitle')} description={t('auditCompare.emptyDescription')} />
      ) : (
        <DataTable
          columns={[
            {
              key: 'section',
              header: t('auditCompare.table.section'),
              minWidth: 260,
              cell: (row) => (
                <div className="space-y-1">
                  <p className="font-medium text-stone-900">{t(`audit.sections.${row.key}`)}</p>
                  <p className="text-xs text-stone-500">{t(`auditCompare.area.${row.area}`)}</p>
                </div>
              ),
            },
            {
              key: 'status',
              header: t('auditCompare.table.status'),
              sortKey: 'status',
              minWidth: 120,
              cell: (row) => renderBadge(t(`auditCompare.status.${row.status}`), statusTone(row.status)),
            },
            {
              key: 'counts',
              header: t('auditCompare.table.counts'),
              minWidth: 180,
              cell: (row) => (
                <div className="space-y-1 text-xs text-stone-600">
                  <p>{t('auditCompare.table.active')}: <span className="font-medium text-stone-900">{row.active_count}</span></p>
                  <p>{t('auditCompare.table.baseline')}: <span className="font-medium text-stone-900">{row.baseline_count}</span></p>
                  <p>{t('auditCompare.table.delta')}: <span className="font-medium text-stone-900">{row.delta > 0 ? `+${row.delta}` : row.delta}</span></p>
                </div>
              ),
            },
            {
              key: 'changes',
              header: t('auditCompare.table.changes'),
              minWidth: 220,
              cell: (row) => (
                <div className="space-y-1 text-xs text-stone-600">
                  <p>{t('auditCompare.table.resolvedItems')}: <span className="font-medium text-stone-900">{row.resolved_items_count}</span></p>
                  <p>{t('auditCompare.table.newItems')}: <span className="font-medium text-stone-900">{row.new_items_count}</span></p>
                  {row.sample_resolved_items.length > 0 ? (
                    <p className="[overflow-wrap:anywhere]">
                      {t('auditCompare.table.sampleResolved')}: {row.sample_resolved_items.join(', ')}
                    </p>
                  ) : null}
                  {row.sample_new_items.length > 0 ? (
                    <p className="[overflow-wrap:anywhere]">
                      {t('auditCompare.table.sampleNew')}: {row.sample_new_items.join(', ')}
                    </p>
                  ) : null}
                </div>
              ),
            },
          ]}
          rows={payload.sections}
          rowKey={(row) => row.key}
          sortBy="status"
          sortOrder={'desc' as SortOrder}
        />
      )}
    </div>
  )
}
