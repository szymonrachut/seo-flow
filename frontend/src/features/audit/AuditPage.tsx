import type { ReactNode } from 'react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { buildApiUrl } from '../../api/client'
import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type {
  DuplicateValueGroup,
  LinkIssue,
  PageIssue,
  SortOrder,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatBytes, formatNullable } from '../../utils/format'
import { buildQueryString } from '../../utils/searchParams'
import { JobNavigation } from '../jobs/JobNavigation'
import { useAuditQuery } from './api'

type SortableValue = boolean | number | string | null | undefined

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

function normalizeSortValue(value: SortableValue): number | string {
  if (typeof value === 'number') {
    return value
  }

  if (typeof value === 'boolean') {
    return value ? 1 : 0
  }

  return (value ?? '').toString().toLowerCase()
}

function sortRows<T>(rows: T[], accessor: (row: T) => SortableValue, sortOrder: SortOrder): T[] {
  const direction = sortOrder === 'asc' ? 1 : -1

  return [...rows].sort((left, right) => {
    const leftValue = normalizeSortValue(accessor(left))
    const rightValue = normalizeSortValue(accessor(right))

    if (leftValue < rightValue) {
      return -1 * direction
    }
    if (leftValue > rightValue) {
      return 1 * direction
    }
    return 0
  })
}

function buildJobLink(jobId: number, path: 'pages' | 'links', params: Record<string, string | number | boolean | undefined>) {
  const query = buildQueryString(params)
  return `/jobs/${jobId}/${path}${query ? `?${query}` : ''}`
}

function ActionLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
    >
      {label}
    </Link>
  )
}

function AuditSection({
  label,
  count,
  action,
  children,
}: {
  label: string
  count: number
  action?: ReactNode
  children: ReactNode
}) {
  const { t } = useTranslation()

  return (
    <details open={count > 0} className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-left">
        <div>
          <p className="text-base font-semibold text-stone-950">{label}</p>
          <p className="mt-1 text-sm text-stone-600">{t('audit.sectionRecords', { count })}</p>
        </div>
        <div className="flex items-center gap-2">
          {action}
          <span className="rounded-full bg-stone-100 px-3 py-1 text-sm font-semibold text-stone-700">{count}</span>
        </div>
      </summary>
      <div className="mt-4">
        {count === 0 ? (
          <EmptyState title={t('audit.sectionEmpty.title')} description={t('audit.sectionEmpty.description')} />
        ) : (
          children
        )}
      </div>
    </details>
  )
}

function PageIssueTable({ items }: { items: PageIssue[] }) {
  const { t } = useTranslation()
  const [sortBy, setSortBy] = useState<'url' | 'status_code' | 'title' | 'details'>('url')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')

  const sortedItems = useMemo(() => {
    const accessors = {
      url: (item: PageIssue) => item.url,
      status_code: (item: PageIssue) => item.status_code,
      title: (item: PageIssue) => item.title,
      details: (item: PageIssue) =>
        [item.title_length, item.meta_description_length, item.word_count, item.images_missing_alt_count, item.html_size_bytes]
          .filter((value) => value !== null && value !== undefined)
          .join('-'),
    }

    return sortRows(items, accessors[sortBy], sortOrder)
  }, [items, sortBy, sortOrder])

  return (
    <DataTable
      columns={[
        {
          key: 'url',
          header: t('audit.table.url'),
          sortKey: 'url',
          cell: (item) => (
            <div className="max-w-[28rem] space-y-1">
              <span className="block [overflow-wrap:anywhere]" title={item.url}>
                {item.url}
              </span>
              <span className="block text-xs text-stone-500 [overflow-wrap:anywhere]" title={item.normalized_url}>
                {item.normalized_url}
              </span>
            </div>
          ),
        },
        { key: 'status', header: t('audit.table.status'), sortKey: 'status_code', cell: (item) => formatNullable(item.status_code) },
        { key: 'title', header: t('audit.table.title'), sortKey: 'title', cell: (item) => <span className="[overflow-wrap:anywhere]">{item.title ?? '-'}</span> },
        {
          key: 'details',
          header: t('audit.table.details'),
          sortKey: 'details',
          cell: (item) => (
            <div className="space-y-1 text-xs text-stone-600">
              {item.title_length !== undefined && item.title_length !== null ? (
                <p>{t('audit.details.titleLength', { count: item.title_length })}</p>
              ) : null}
              {item.meta_description_length !== undefined && item.meta_description_length !== null ? (
                <p>{t('audit.details.metaLength', { count: item.meta_description_length })}</p>
              ) : null}
              {item.h1_count !== undefined && item.h1_count !== null ? <p>{t('audit.details.h1Count', { count: item.h1_count })}</p> : null}
              {item.h2_count !== undefined && item.h2_count !== null ? <p>{t('audit.details.h2Count', { count: item.h2_count })}</p> : null}
              {item.word_count !== undefined && item.word_count !== null ? <p>{t('audit.details.wordCount', { count: item.word_count })}</p> : null}
              {item.images_missing_alt_count !== undefined && item.images_missing_alt_count !== null ? (
                <p>{t('audit.details.missingAlt', { count: item.images_missing_alt_count })}</p>
              ) : null}
              {item.html_size_bytes !== undefined && item.html_size_bytes !== null ? (
                <p>{t('audit.details.htmlSize', { size: formatBytes(item.html_size_bytes) })}</p>
              ) : null}
              {item.canonical_url ? <p>{t('audit.details.canonical', { value: item.canonical_url })}</p> : null}
              {item.canonical_target_status_code !== undefined && item.canonical_target_status_code !== null ? (
                <p>{t('audit.details.canonicalTargetStatus', { count: item.canonical_target_status_code })}</p>
              ) : null}
              {item.x_robots_tag ? <p>{t('audit.details.xRobots', { value: item.x_robots_tag })}</p> : null}
              {item.was_rendered ? <p>{t('audit.details.rendered')}</p> : null}
              {item.js_heavy_like ? <p>{t('audit.details.jsHeavyLike')}</p> : null}
              {item.render_error_message ? <p>{t('audit.details.renderError', { value: item.render_error_message })}</p> : null}
              {item.schema_types_json && item.schema_types_json.length > 0 ? (
                <p>{t('audit.details.schemaTypes', { value: item.schema_types_json.join(', ') })}</p>
              ) : null}
            </div>
          ),
        },
      ]}
      rows={sortedItems}
      rowKey={(item) => item.page_id}
      sortBy={sortBy}
      sortOrder={sortOrder}
      onSortChange={(nextSortBy, nextSortOrder) => {
        setSortBy(nextSortBy as typeof sortBy)
        setSortOrder(nextSortOrder)
      }}
    />
  )
}

function DuplicateGroupTable({
  items,
  sectionKey,
  jobId,
  filterKey,
}: {
  items: DuplicateValueGroup[]
  sectionKey: string
  jobId: number
  filterKey: 'title_exact' | 'meta_description_exact' | 'content_text_hash_exact' | 'schema_type'
}) {
  const { t } = useTranslation()
  const [sortBy, setSortBy] = useState<'value' | 'count' | 'pages'>('count')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')

  const sortedItems = useMemo(() => {
    const accessors = {
      value: (group: DuplicateValueGroup) => group.value,
      count: (group: DuplicateValueGroup) => group.count,
      pages: (group: DuplicateValueGroup) => group.pages.map((page) => page.url).join(' | '),
    }

    return sortRows(items, accessors[sortBy], sortOrder)
  }, [items, sortBy, sortOrder])

  return (
    <DataTable
      columns={[
        { key: 'value', header: t('audit.table.value'), sortKey: 'value', cell: (group) => <span className="[overflow-wrap:anywhere]">{group.value || '-'}</span> },
        { key: 'count', header: t('audit.table.count'), sortKey: 'count', cell: (group) => group.count },
        {
          key: 'pages',
          header: t('audit.table.pages'),
          sortKey: 'pages',
          cell: (group) => (
            <div className="space-y-1">
              {group.pages.map((page) => (
                <p key={page.page_id} className="max-w-[26rem] text-xs text-stone-600 [overflow-wrap:anywhere]" title={page.url}>
                  {page.url}
                </p>
              ))}
            </div>
          ),
        },
        {
          key: 'actions',
          header: t('audit.table.open'),
          cell: (group) => (
            <ActionLink
              to={buildJobLink(jobId, 'pages', {
                [filterKey]: group.value,
                sort_by:
                  filterKey === 'title_exact'
                    ? 'title_length'
                    : filterKey === 'meta_description_exact'
                      ? 'meta_description_length'
                      : filterKey === 'content_text_hash_exact'
                        ? 'word_count'
                        : 'schema_count',
                sort_order: 'asc',
              })}
              label={t('common.showInPages')}
            />
          ),
        },
      ]}
      rows={sortedItems}
      rowKey={(group) => `${sectionKey}-${group.value}`}
      sortBy={sortBy}
      sortOrder={sortOrder}
      onSortChange={(nextSortBy, nextSortOrder) => {
        setSortBy(nextSortBy as typeof sortBy)
        setSortOrder(nextSortOrder)
      }}
    />
  )
}

function LinkIssueTable({ items }: { items: LinkIssue[] }) {
  const { t } = useTranslation()
  const [sortBy, setSortBy] = useState<'source_url' | 'target_url' | 'target_status_code' | 'final_url' | 'redirect_hops'>('source_url')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')

  const sortedItems = useMemo(() => {
    const accessors = {
      source_url: (item: LinkIssue) => item.source_url,
      target_url: (item: LinkIssue) => item.target_url,
      target_status_code: (item: LinkIssue) => item.target_status_code,
      final_url: (item: LinkIssue) => item.final_url,
      redirect_hops: (item: LinkIssue) => item.redirect_hops,
    }

    return sortRows(items, accessors[sortBy], sortOrder)
  }, [items, sortBy, sortOrder])

  return (
    <DataTable
      columns={[
        { key: 'source', header: t('audit.table.sourceUrl'), sortKey: 'source_url', cell: (item) => <span className="[overflow-wrap:anywhere]">{item.source_url}</span> },
        { key: 'target', header: t('audit.table.targetUrl'), sortKey: 'target_url', cell: (item) => <span className="[overflow-wrap:anywhere]">{item.target_url}</span> },
        {
          key: 'status',
          header: t('audit.table.targetStatus'),
          sortKey: 'target_status_code',
          cell: (item) => formatNullable(item.target_status_code),
        },
        {
          key: 'hops',
          header: t('audit.table.redirectHops'),
          sortKey: 'redirect_hops',
          cell: (item) => formatNullable(item.redirect_hops),
        },
        { key: 'final', header: t('audit.table.finalUrl'), sortKey: 'final_url', cell: (item) => <span className="[overflow-wrap:anywhere]">{item.final_url || '-'}</span> },
        {
          key: 'signals',
          header: t('audit.table.signals'),
          cell: (item) => item.signals.join(', ') || '-',
        },
      ]}
      rows={sortedItems}
      rowKey={(item) => item.link_id}
      sortBy={sortBy}
      sortOrder={sortOrder}
      onSortChange={(nextSortBy, nextSortOrder) => {
        setSortBy(nextSortBy as typeof sortBy)
        setSortOrder(nextSortOrder)
      }}
    />
  )
}

export function AuditPage() {
  const { t } = useTranslation()
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? t('documentTitle.audit', { jobId }) : t('nav.audit'))

  if (jobId === null) {
    return <ErrorState title={t('audit.invalidIdTitle')} message={t('audit.invalidIdMessage')} />
  }

  const auditQuery = useAuditQuery(jobId)

  if (auditQuery.isLoading) {
    return <LoadingState label={t('audit.loading', { jobId })} />
  }

  if (auditQuery.isError) {
    return (
      <ErrorState
        title={t('audit.errors.requestTitle')}
        message={getUiErrorMessage(auditQuery.error, t)}
      />
    )
  }

  const audit = auditQuery.data
  if (!audit) {
    return <EmptyState title={t('audit.empty.title')} description={t('audit.empty.description')} />
  }

  const duplicateTitleLink =
    audit.pages_duplicate_title.length === 1
      ? buildJobLink(jobId, 'pages', {
          title_exact: audit.pages_duplicate_title[0].value,
          sort_by: 'title',
          sort_order: 'asc',
        })
      : buildJobLink(jobId, 'pages', { has_title: true, sort_by: 'title', sort_order: 'asc' })

  const duplicateMetaLink =
    audit.pages_duplicate_meta_description.length === 1
      ? buildJobLink(jobId, 'pages', {
          meta_description_exact: audit.pages_duplicate_meta_description[0].value,
          sort_by: 'meta_description_length',
          sort_order: 'asc',
        })
      : buildJobLink(jobId, 'pages', {
          has_meta_description: true,
          sort_by: 'meta_description_length',
          sort_order: 'asc',
        })

  const duplicateContentLink =
    audit.pages_duplicate_content.length === 1
      ? buildJobLink(jobId, 'pages', {
          content_text_hash_exact: audit.pages_duplicate_content[0].value,
          sort_by: 'word_count',
          sort_order: 'asc',
        })
      : buildJobLink(jobId, 'pages', {
          duplicate_content: true,
          sort_by: 'word_count',
          sort_order: 'asc',
        })

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{t('audit.page.eyebrow')}</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">
              {t('audit.page.title', { jobId })}
            </h1>
            <p className="mt-2 text-sm text-stone-600">{t('audit.page.description')}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <JobNavigation jobId={jobId} />
            <a
              href={buildApiUrl(`/crawl-jobs/${jobId}/export/audit.csv`)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('audit.page.export')}
            </a>
          </div>
        </div>
      </section>

      <SummaryCards
        items={[
          { label: t('audit.summary.total_pages'), value: audit.summary.total_pages },
          {
            label: t('audit.summary.titleMetaIssues'),
            value:
              audit.summary.pages_missing_title +
              audit.summary.pages_title_too_short +
              audit.summary.pages_title_too_long +
              audit.summary.pages_missing_meta_description +
              audit.summary.pages_meta_description_too_short +
              audit.summary.pages_meta_description_too_long,
          },
          {
            label: t('audit.summary.headingIssues'),
            value: audit.summary.pages_missing_h1 + audit.summary.pages_multiple_h1 + audit.summary.pages_missing_h2,
          },
          {
            label: t('audit.summary.renderInsights'),
            value:
              audit.summary.rendered_pages +
              audit.summary.js_heavy_like_pages +
              audit.summary.pages_with_render_errors,
          },
          {
            label: t('audit.summary.schemaInsights'),
            value: audit.summary.pages_with_schema + audit.summary.pages_with_schema_types_summary,
          },
          { label: t('audit.summary.xRobots'), value: audit.summary.pages_with_x_robots_tag },
          {
            label: t('audit.summary.canonicalIndexabilityIssues'),
            value:
              audit.summary.pages_missing_canonical +
              audit.summary.pages_canonical_to_other_url +
              audit.summary.pages_canonical_to_non_200 +
              audit.summary.pages_canonical_to_redirect +
              audit.summary.pages_non_indexable_like,
          },
          { label: t('audit.summary.broken_internal_links'), value: audit.summary.broken_internal_links },
          {
            label: t('audit.summary.contentIssues'),
            value: audit.summary.pages_thin_content + audit.summary.pages_duplicate_content_groups,
          },
          {
            label: t('audit.summary.mediaIssues'),
            value:
              audit.summary.pages_with_missing_alt_images +
              audit.summary.pages_with_no_images +
              audit.summary.oversized_pages,
          },
          { label: t('audit.summary.redirecting_internal_links'), value: audit.summary.redirecting_internal_links },
        ]}
      />

      <div className="space-y-4">
        <AuditSection
          label={t('audit.sections.pages_missing_title')}
          count={audit.pages_missing_title.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { has_title: false })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_missing_title} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_title_too_short')}
          count={audit.pages_title_too_short.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { title_too_short: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_title_too_short} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_title_too_long')}
          count={audit.pages_title_too_long.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { title_too_long: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_title_too_long} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_missing_meta_description')}
          count={audit.pages_missing_meta_description.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { has_meta_description: false })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_missing_meta_description} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_meta_description_too_short')}
          count={audit.pages_meta_description_too_short.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { meta_too_short: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_meta_description_too_short} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_meta_description_too_long')}
          count={audit.pages_meta_description_too_long.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { meta_too_long: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_meta_description_too_long} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_missing_h1')}
          count={audit.pages_missing_h1.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { has_h1: false })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_missing_h1} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_multiple_h1')}
          count={audit.pages_multiple_h1.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { multiple_h1: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_multiple_h1} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_missing_h2')}
          count={audit.pages_missing_h2.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { missing_h2: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_missing_h2} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_duplicate_title')}
          count={audit.pages_duplicate_title.length}
          action={<ActionLink to={duplicateTitleLink} label={t('common.showInPages')} />}
        >
          <DuplicateGroupTable items={audit.pages_duplicate_title} sectionKey="pages_duplicate_title" jobId={jobId} filterKey="title_exact" />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_duplicate_meta_description')}
          count={audit.pages_duplicate_meta_description.length}
          action={<ActionLink to={duplicateMetaLink} label={t('common.showInPages')} />}
        >
          <DuplicateGroupTable
            items={audit.pages_duplicate_meta_description}
            sectionKey="pages_duplicate_meta_description"
            jobId={jobId}
            filterKey="meta_description_exact"
          />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_missing_canonical')}
          count={audit.pages_missing_canonical.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { canonical_missing: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_missing_canonical} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_self_canonical')}
          count={audit.pages_self_canonical.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { self_canonical: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_self_canonical} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_canonical_to_other_url')}
          count={audit.pages_canonical_to_other_url.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { canonical_to_other_url: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_canonical_to_other_url} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_canonical_to_non_200')}
          count={audit.pages_canonical_to_non_200.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { canonical_to_non_200: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_canonical_to_non_200} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_canonical_to_redirect')}
          count={audit.pages_canonical_to_redirect.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { canonical_to_redirect: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_canonical_to_redirect} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_noindex_like')}
          count={audit.pages_noindex_like.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { noindex_like: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_noindex_like} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_non_indexable_like')}
          count={audit.pages_non_indexable_like.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { non_indexable_like: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_non_indexable_like} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.broken_internal_links')}
          count={audit.broken_internal_links.length}
          action={<ActionLink to={buildJobLink(jobId, 'links', { broken_internal: true })} label={t('common.showInLinks')} />}
        >
          <LinkIssueTable items={audit.broken_internal_links} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.unresolved_internal_targets')}
          count={audit.unresolved_internal_targets.length}
          action={<ActionLink to={buildJobLink(jobId, 'links', { unresolved_internal: true })} label={t('common.showInLinks')} />}
        >
          <LinkIssueTable items={audit.unresolved_internal_targets} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.redirecting_internal_links')}
          count={audit.redirecting_internal_links.length}
          action={<ActionLink to={buildJobLink(jobId, 'links', { redirecting_internal: true })} label={t('common.showInLinks')} />}
        >
          <LinkIssueTable items={audit.redirecting_internal_links} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.internal_links_to_noindex_like_pages')}
          count={audit.internal_links_to_noindex_like_pages.length}
          action={<ActionLink to={buildJobLink(jobId, 'links', { to_noindex_like: true })} label={t('common.showInLinks')} />}
        >
          <LinkIssueTable items={audit.internal_links_to_noindex_like_pages} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.internal_links_to_canonicalized_pages')}
          count={audit.internal_links_to_canonicalized_pages.length}
          action={<ActionLink to={buildJobLink(jobId, 'links', { to_canonicalized: true })} label={t('common.showInLinks')} />}
        >
          <LinkIssueTable items={audit.internal_links_to_canonicalized_pages} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.redirect_chains_internal')}
          count={audit.redirect_chains_internal.length}
          action={<ActionLink to={buildJobLink(jobId, 'links', { redirect_chain: true })} label={t('common.showInLinks')} />}
        >
          <LinkIssueTable items={audit.redirect_chains_internal} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_thin_content')}
          count={audit.pages_thin_content.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { thin_content: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_thin_content} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_duplicate_content')}
          count={audit.pages_duplicate_content.length}
          action={<ActionLink to={duplicateContentLink} label={t('common.showInPages')} />}
        >
          <DuplicateGroupTable
            items={audit.pages_duplicate_content}
            sectionKey="pages_duplicate_content"
            jobId={jobId}
            filterKey="content_text_hash_exact"
          />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.js_heavy_like_pages')}
          count={audit.js_heavy_like_pages.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { js_heavy_like: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.js_heavy_like_pages} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.rendered_pages')}
          count={audit.rendered_pages.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { was_rendered: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.rendered_pages} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_with_render_errors')}
          count={audit.pages_with_render_errors.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { has_render_error: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_with_render_errors} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_with_schema')}
          count={audit.pages_with_schema.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { schema_present: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_with_schema} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_missing_schema')}
          count={audit.pages_missing_schema.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { schema_present: false })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_missing_schema} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_with_x_robots_tag')}
          count={audit.pages_with_x_robots_tag.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { has_x_robots_tag: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_with_x_robots_tag} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_with_schema_types_summary')}
          count={audit.pages_with_schema_types_summary.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { schema_present: true })} label={t('common.showInPages')} />}
        >
          <DuplicateGroupTable
            items={audit.pages_with_schema_types_summary}
            sectionKey="pages_with_schema_types_summary"
            jobId={jobId}
            filterKey="schema_type"
          />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_with_missing_alt_images')}
          count={audit.pages_with_missing_alt_images.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { missing_alt_images: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_with_missing_alt_images} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.pages_with_no_images')}
          count={audit.pages_with_no_images.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { no_images: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.pages_with_no_images} />
        </AuditSection>

        <AuditSection
          label={t('audit.sections.oversized_pages')}
          count={audit.oversized_pages.length}
          action={<ActionLink to={buildJobLink(jobId, 'pages', { oversized: true })} label={t('common.showInPages')} />}
        >
          <PageIssueTable items={audit.oversized_pages} />
        </AuditSection>
      </div>
    </div>
  )
}
