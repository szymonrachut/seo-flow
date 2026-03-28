import { startTransition, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { buildApiUrl } from '../../api/client'
import { DataViewHeader } from '../../components/DataViewHeader'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { PaginationControls } from '../../components/PaginationControls'
import { QuickFilterBar } from '../../components/QuickFilterBar'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { AuditReport, SortOrder } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import {
  mergeSearchParams,
  parseCsvParam,
  parseIntegerParam,
  serializeCsvParam,
  toggleCsvParamValue,
} from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import { buildSiteAuditPath, buildSiteAuditSectionsPath, buildSiteChangesAuditPath } from '../sites/routes'
import { useAuditQuery } from './api'
import {
  AUDIT_SECTION_DEFINITIONS,
  type AuditSectionDefinition,
  type AuditWorkspaceContext,
  type AuditWorkspaceGroup,
  buildAuditSectionActionHref,
  renderAuditSectionBody,
  AuditSectionCard,
} from './auditWorkspace'

const AUDIT_GROUPS: Array<{ key: AuditWorkspaceGroup; label: string }> = [
  { key: 'pages', label: 'Pages' },
  { key: 'links', label: 'Links' },
  { key: 'content', label: 'Content' },
  { key: 'technical', label: 'Technical' },
  { key: 'schema', label: 'Schema' },
  { key: 'media', label: 'Media' },
]

type AuditWorkspaceSortBy = 'count' | 'label'

function readGroupFilters(searchParams: URLSearchParams) {
  return Array.from(
    parseCsvParam(
      searchParams.get('groups'),
      AUDIT_GROUPS.map((group) => group.key),
    ),
  )
}

function readSortBy(searchParams: URLSearchParams): AuditWorkspaceSortBy {
  return searchParams.get('sort_by') === 'label' ? 'label' : 'count'
}

function readSortOrder(searchParams: URLSearchParams): SortOrder {
  return searchParams.get('sort_order') === 'asc' ? 'asc' : 'desc'
}

function readBooleanParam(searchParams: URLSearchParams, key: string, fallback: boolean) {
  const value = searchParams.get(key)
  if (value === 'true') {
    return true
  }
  if (value === 'false') {
    return false
  }
  return fallback
}

function formatSectionCount(report: AuditReport, definition: AuditSectionDefinition) {
  return (report[definition.key] as Array<unknown>).length
}

function buildSectionMetrics(report: AuditReport) {
  const countsByGroup = AUDIT_GROUPS.reduce<Record<AuditWorkspaceGroup, number>>((accumulator, group) => {
    accumulator[group.key] = 0
    return accumulator
  }, {
    pages: 0,
    links: 0,
    content: 0,
    technical: 0,
    schema: 0,
    media: 0,
  })

  let openSections = 0
  let totalRows = 0

  AUDIT_SECTION_DEFINITIONS.forEach((definition) => {
    const count = formatSectionCount(report, definition)
    countsByGroup[definition.group] += count
    totalRows += count
    if (count > 0) {
      openSections += 1
    }
  })

  return { countsByGroup, openSections, totalRows }
}

function matchesSearch(definition: AuditSectionDefinition, label: string, searchTerm: string) {
  if (!searchTerm) {
    return true
  }

  const haystack = `${definition.key} ${label}`.toLowerCase()
  return haystack.includes(searchTerm.toLowerCase())
}

function matchesGroups(definition: AuditSectionDefinition, selectedGroups: AuditWorkspaceGroup[]) {
  if (selectedGroups.length === 0) {
    return true
  }

  return selectedGroups.includes(definition.group)
}

function sortDefinitions(
  left: { label: string; count: number; definition: AuditSectionDefinition },
  right: { label: string; count: number; definition: AuditSectionDefinition },
  sortBy: AuditWorkspaceSortBy,
  sortOrder: SortOrder,
) {
  const direction = sortOrder === 'asc' ? 1 : -1

  const leftValue = sortBy === 'count' ? left.count : left.label.toLowerCase()
  const rightValue = sortBy === 'count' ? right.count : right.label.toLowerCase()

  if (leftValue < rightValue) {
    return -1 * direction
  }
  if (leftValue > rightValue) {
    return 1 * direction
  }
  return 0
}

function buildOverviewSummary(report: AuditReport, t: (key: string) => string) {
  const metrics = buildSectionMetrics(report)
  return [
    { label: t('siteAudit.summary.auditedPages'), value: report.summary.total_pages },
    { label: t('siteAudit.summary.openSections'), value: metrics.openSections },
    { label: t('siteAudit.summary.problemRows'), value: metrics.totalRows },
    { label: t('siteAudit.summary.pagesIssues'), value: metrics.countsByGroup.pages },
    { label: t('siteAudit.summary.linksIssues'), value: metrics.countsByGroup.links },
    {
      label: t('siteAudit.summary.technicalIssues'),
      value: metrics.countsByGroup.technical + metrics.countsByGroup.schema + metrics.countsByGroup.media,
    },
  ]
}

function buildAuditSectionCards(
  report: AuditReport,
  context: AuditWorkspaceContext,
  selectedGroups: AuditWorkspaceGroup[],
  searchTerm: string,
  showEmptySections: boolean,
  sortBy: AuditWorkspaceSortBy,
  sortOrder: SortOrder,
  translate: (key: string) => string,
) {
  return AUDIT_SECTION_DEFINITIONS
    .map((definition) => {
      const label = translate(definition.labelKey)
      const count = formatSectionCount(report, definition)
      return { definition, label, count }
    })
    .filter((entry) => showEmptySections || entry.count > 0)
    .filter((entry) => matchesGroups(entry.definition, selectedGroups))
    .filter((entry) => matchesSearch(entry.definition, entry.label, searchTerm))
    .sort((left, right) => sortDefinitions(left, right, sortBy, sortOrder))
    .map((entry) => ({
      ...entry,
      actionHref: buildAuditSectionActionHref(entry.definition, report, context),
    }))
}

function AuditWorkspaceSubnav({ siteId, mode }: { siteId: number; mode: 'overview' | 'sections' }) {
  const { t } = useTranslation()
  const location = useLocation()

  return (
    <div className="flex flex-wrap gap-2">
      <Link
        to={`/sites/${siteId}/audit${location.search}`}
        className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
          mode === 'overview'
            ? 'border-stone-950 bg-stone-950 !text-white'
            : 'border-stone-300 bg-white text-stone-700 hover:border-stone-400 hover:bg-stone-100'
        }`}
      >
        {t('nav.overview')}
      </Link>
      <Link
        to={`/sites/${siteId}/audit/sections${location.search}`}
        className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${
          mode === 'sections'
            ? 'border-stone-950 bg-stone-950 !text-white'
            : 'border-stone-300 bg-white text-stone-700 hover:border-stone-400 hover:bg-stone-100'
        }`}
      >
        {t('sites.audit.sectionsPage.navLabel')}
      </Link>
    </div>
  )
}

function AuditWorkspaceView({ mode }: { mode: 'overview' | 'sections' }) {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const [searchParams, setSearchParams] = useSearchParams()
  const auditQuery = useAuditQuery(activeCrawlId ?? -1, { enabled: Boolean(activeCrawlId) })

  useDocumentTitle(
    t(mode === 'overview' ? 'documentTitle.siteAudit' : 'documentTitle.siteAuditSections', { domain: site.domain }),
  )

  const selectedGroups = useMemo(() => readGroupFilters(searchParams), [searchParams])
  const sortBy = useMemo(() => readSortBy(searchParams), [searchParams])
  const sortOrder = useMemo(() => readSortOrder(searchParams), [searchParams])
  const showEmptySections = useMemo(() => readBooleanParam(searchParams, 'show_empty', false), [searchParams])
  const page = useMemo(() => parseIntegerParam(searchParams.get('page'), 1), [searchParams])
  const pageSize = useMemo(() => parseIntegerParam(searchParams.get('page_size'), mode === 'sections' ? 8 : 6), [mode, searchParams])
  const searchTerm = searchParams.get('q') ?? ''
  const minCount = parseIntegerParam(searchParams.get('min_count'), 0)

  function updateSearchParams(updates: Record<string, string | number | boolean | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function resetFilters() {
    updateSearchParams({
      groups: undefined,
      q: undefined,
      sort_by: undefined,
      sort_order: undefined,
      show_empty: undefined,
      min_count: undefined,
      page: 1,
      page_size: mode === 'sections' ? 8 : 6,
    })
  }

  function toggleGroup(group: AuditWorkspaceGroup) {
    updateSearchParams({
      groups: serializeCsvParam(toggleCsvParamValue(selectedGroups, group)),
      page: 1,
    })
  }

  const audit = auditQuery.data
  const context = {
    siteId: site.id,
    activeCrawlId: activeCrawlId ?? 0,
    baselineCrawlId,
  }

  const filteredSections = useMemo(() => {
    if (!audit) {
      return []
    }

    return buildAuditSectionCards(
      audit,
      context,
      selectedGroups,
      searchTerm,
      showEmptySections,
      sortBy,
      sortOrder,
      t,
    ).filter((entry) => entry.count >= minCount)
  }, [audit, context, minCount, searchTerm, selectedGroups, showEmptySections, sortBy, sortOrder, t])

  const pagedSections = useMemo(() => {
    const offset = (page - 1) * pageSize
    return filteredSections.slice(offset, offset + pageSize)
  }, [filteredSections, page, pageSize])

  const summaryItems = useMemo(() => (audit ? buildOverviewSummary(audit, t) : []), [audit, t])

  const quickFilters = AUDIT_GROUPS.map((group) => ({
    label: group.label,
    isActive: selectedGroups.includes(group.key),
    onClick: () => toggleGroup(group.key),
  }))

  const activeCompareLink = buildSiteChangesAuditPath(site.id, {
    activeCrawlId: activeCrawlId ?? undefined,
    baselineCrawlId: baselineCrawlId ?? undefined,
  })
  const currentStatePath =
    mode === 'overview'
      ? buildSiteAuditSectionsPath(site.id, { activeCrawlId, baselineCrawlId })
      : buildSiteAuditPath(site.id, { activeCrawlId, baselineCrawlId })

  if (!activeCrawlId) {
    return (
      <div className="space-y-6">
        <DataViewHeader
          eyebrow={t('nav.audit')}
          title={mode === 'overview' ? t('shell.routeTitles.audit') : t('shell.routeTitles.auditSections')}
          description={t('siteAudit.description')}
          contextChips={[
            { label: t('siteAudit.context.active'), value: t('siteAudit.context.notSelected'), tone: 'warning' },
          ]}
          primaryAction={{
            key: mode === 'overview' ? 'open-sections' : 'open-overview',
            label: mode === 'overview' ? t('sites.audit.sectionsPage.navLabel') : t('nav.overview'),
            to: currentStatePath,
          }}
          operations={[
            {
              key: 'open-changes',
              label: t('siteAudit.actions.openChanges'),
              to: activeCompareLink,
            },
          ]}
        />
        <EmptyState
          title={t('siteAudit.empty.noActiveTitle')}
          description={t('siteAudit.empty.noActiveDescription')}
        />
      </div>
    )
  }

  if (auditQuery.isLoading) {
    return <LoadingState label={t('siteAudit.loading')} />
  }

  if (auditQuery.isError) {
    return <ErrorState title={t('siteAudit.errors.requestTitle')} message={getUiErrorMessage(auditQuery.error, t)} />
  }

  if (!audit) {
    return <EmptyState title={t('siteAudit.empty.unavailableTitle')} description={t('siteAudit.empty.unavailableDescription')} />
  }

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('nav.audit')}
        title={mode === 'overview' ? t('shell.routeTitles.audit') : t('shell.routeTitles.auditSections')}
        description={t('siteAudit.description')}
        contextChips={[
          { label: t('siteAudit.context.active'), value: `#${activeCrawlId}` },
        ]}
        primaryAction={{
          key: mode === 'overview' ? 'open-sections' : 'open-overview',
          label: mode === 'overview' ? t('sites.audit.sectionsPage.navLabel') : t('nav.overview'),
          to: currentStatePath,
        }}
        operations={[
          {
            key: 'open-changes',
            label: t('siteAudit.actions.openChanges'),
            to: activeCompareLink,
          },
          {
            key: 'open-active-crawl',
            label: t('siteAudit.actions.openActiveCrawl'),
            to: `/jobs/${activeCrawlId}`,
          },
        ]}
        exports={[
          {
            key: 'export-audit',
            label: t('siteAudit.actions.exportAudit'),
            href: buildApiUrl(`/crawl-jobs/${activeCrawlId}/export/audit.csv`),
          },
        ]}
      />

      <AuditWorkspaceSubnav siteId={site.id} mode={mode} />

      <SummaryCards items={summaryItems} />

      <QuickFilterBar title={t('siteAudit.quickFilters.title')} items={quickFilters} onReset={resetFilters} />

      <FilterPanel title={t('siteAudit.filters.title')} description={t('siteAudit.filters.description')} onReset={resetFilters}>
        <label className="grid gap-1 text-sm text-stone-700 dark:text-slate-300">
          <span>{t('siteAudit.filters.searchLabel')}</span>
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => updateSearchParams({ q: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
            placeholder={t('siteAudit.filters.searchPlaceholder')}
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700 dark:text-slate-300">
          <span>{t('siteAudit.filters.minimumCount')}</span>
          <input
            type="number"
            min="0"
            value={minCount}
            onChange={(event) => updateSearchParams({ min_count: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          />
        </label>
        <label className="grid gap-1 text-sm text-stone-700 dark:text-slate-300">
          <span>{t('siteAudit.filters.sortBy')}</span>
          <select
            value={sortBy}
            onChange={(event) => updateSearchParams({ sort_by: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          >
            <option value="count">{t('siteAudit.filters.sort.count')}</option>
            <option value="label">{t('siteAudit.filters.sort.label')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700 dark:text-slate-300">
          <span>{t('siteAudit.filters.sortOrder')}</span>
          <select
            value={sortOrder}
            onChange={(event) => updateSearchParams({ sort_order: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          >
            <option value="desc">{t('sort.descending')}</option>
            <option value="asc">{t('sort.ascending')}</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700 dark:text-slate-300">
          <span>{t('siteAudit.filters.pageSize')}</span>
          <select
            value={pageSize}
            onChange={(event) => updateSearchParams({ page_size: event.target.value || undefined, page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          >
            {[4, 6, 8, 12].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm text-stone-700 dark:text-slate-300">
          <span>{t('siteAudit.filters.openOnly')}</span>
          <button
            type="button"
            onClick={() => updateSearchParams({ show_empty: String(!showEmptySections), page: 1 })}
            className="rounded-2xl border border-stone-300 bg-white px-3 py-2 text-left dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
          >
            {showEmptySections ? t('siteAudit.filters.showAllState') : t('siteAudit.filters.showOpenOnlyState')}
          </button>
        </label>
      </FilterPanel>

      <div className="space-y-4">
        {pagedSections.length === 0 ? (
          <EmptyState
            title={t('siteAudit.empty.filteredTitle')}
            description={t('siteAudit.empty.filteredDescription')}
          />
        ) : (
          pagedSections.map((section) => {
            const label = section.label
            const detailsOpen = mode === 'sections'

            return (
              <AuditSectionCard
                key={section.definition.key}
                label={label}
                count={section.count}
                group={section.definition.group}
                open={detailsOpen}
                action={
                  <Link
                    to={section.actionHref}
                    className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                  >
                    {section.definition.kind === 'link' ? t('siteAudit.actions.openLinks') : t('siteAudit.actions.openPages')}
                  </Link>
                }
              >
                {renderAuditSectionBody(section.definition, audit)}
              </AuditSectionCard>
            )
          })
        )}
      </div>

      <PaginationControls
        page={page}
        pageSize={pageSize}
        totalItems={filteredSections.length}
        totalPages={Math.max(1, Math.ceil(filteredSections.length / pageSize))}
        onPageChange={(nextPage) => updateSearchParams({ page: nextPage })}
        onPageSizeChange={(nextPageSize) => updateSearchParams({ page_size: nextPageSize, page: 1 })}
      />
    </div>
  )
}

export function SiteAuditOverviewPage() {
  return <AuditWorkspaceView mode="overview" />
}

export function SiteAuditSectionsPage() {
  return <AuditWorkspaceView mode="sections" />
}
