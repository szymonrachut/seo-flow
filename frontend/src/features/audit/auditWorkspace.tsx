import type { ReactNode } from 'react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import type {
  AuditReport,
  DuplicateValueGroup,
  LinkIssue,
  PageIssue,
  SortOrder,
} from '../../types/api'
import { formatBytes, formatNullable } from '../../utils/format'
import { buildSitePagesRecordsPath } from '../sites/routes'

export type AuditWorkspaceGroup =
  | 'pages'
  | 'links'
  | 'content'
  | 'technical'
  | 'schema'
  | 'media'

export type AuditSectionKind = 'page' | 'duplicate' | 'link'

export interface AuditSectionDefinition {
  key: keyof Pick<
    AuditReport,
    | 'pages_missing_title'
    | 'pages_title_too_short'
    | 'pages_title_too_long'
    | 'pages_missing_meta_description'
    | 'pages_meta_description_too_short'
    | 'pages_meta_description_too_long'
    | 'pages_missing_h1'
    | 'pages_multiple_h1'
    | 'pages_missing_h2'
    | 'pages_duplicate_title'
    | 'pages_duplicate_meta_description'
    | 'pages_missing_canonical'
    | 'pages_self_canonical'
    | 'pages_canonical_to_other_url'
    | 'pages_canonical_to_non_200'
    | 'pages_canonical_to_redirect'
    | 'pages_noindex_like'
    | 'pages_non_indexable_like'
    | 'broken_internal_links'
    | 'unresolved_internal_targets'
    | 'redirecting_internal_links'
    | 'internal_links_to_noindex_like_pages'
    | 'internal_links_to_canonicalized_pages'
    | 'redirect_chains_internal'
    | 'pages_thin_content'
    | 'pages_duplicate_content'
    | 'js_heavy_like_pages'
    | 'rendered_pages'
    | 'pages_with_render_errors'
    | 'pages_with_schema'
    | 'pages_missing_schema'
    | 'pages_with_x_robots_tag'
    | 'pages_with_schema_types_summary'
    | 'pages_with_missing_alt_images'
    | 'pages_with_no_images'
    | 'oversized_pages'
  > & string
  labelKey: string
  group: AuditWorkspaceGroup
  kind: AuditSectionKind
}

export interface AuditWorkspaceContext {
  siteId: number
  activeCrawlId: number
  baselineCrawlId: number | null
}

export const AUDIT_SECTION_DEFINITIONS: AuditSectionDefinition[] = [
  { key: 'pages_missing_title', labelKey: 'audit.sections.pages_missing_title', group: 'pages', kind: 'page' },
  { key: 'pages_title_too_short', labelKey: 'audit.sections.pages_title_too_short', group: 'pages', kind: 'page' },
  { key: 'pages_title_too_long', labelKey: 'audit.sections.pages_title_too_long', group: 'pages', kind: 'page' },
  {
    key: 'pages_missing_meta_description',
    labelKey: 'audit.sections.pages_missing_meta_description',
    group: 'pages',
    kind: 'page',
  },
  {
    key: 'pages_meta_description_too_short',
    labelKey: 'audit.sections.pages_meta_description_too_short',
    group: 'pages',
    kind: 'page',
  },
  {
    key: 'pages_meta_description_too_long',
    labelKey: 'audit.sections.pages_meta_description_too_long',
    group: 'pages',
    kind: 'page',
  },
  { key: 'pages_missing_h1', labelKey: 'audit.sections.pages_missing_h1', group: 'pages', kind: 'page' },
  { key: 'pages_multiple_h1', labelKey: 'audit.sections.pages_multiple_h1', group: 'pages', kind: 'page' },
  { key: 'pages_missing_h2', labelKey: 'audit.sections.pages_missing_h2', group: 'pages', kind: 'page' },
  { key: 'pages_duplicate_title', labelKey: 'audit.sections.pages_duplicate_title', group: 'pages', kind: 'duplicate' },
  {
    key: 'pages_duplicate_meta_description',
    labelKey: 'audit.sections.pages_duplicate_meta_description',
    group: 'pages',
    kind: 'duplicate',
  },
  { key: 'pages_missing_canonical', labelKey: 'audit.sections.pages_missing_canonical', group: 'pages', kind: 'page' },
  { key: 'pages_self_canonical', labelKey: 'audit.sections.pages_self_canonical', group: 'pages', kind: 'page' },
  {
    key: 'pages_canonical_to_other_url',
    labelKey: 'audit.sections.pages_canonical_to_other_url',
    group: 'pages',
    kind: 'page',
  },
  {
    key: 'pages_canonical_to_non_200',
    labelKey: 'audit.sections.pages_canonical_to_non_200',
    group: 'pages',
    kind: 'page',
  },
  {
    key: 'pages_canonical_to_redirect',
    labelKey: 'audit.sections.pages_canonical_to_redirect',
    group: 'pages',
    kind: 'page',
  },
  { key: 'pages_noindex_like', labelKey: 'audit.sections.pages_noindex_like', group: 'pages', kind: 'page' },
  {
    key: 'pages_non_indexable_like',
    labelKey: 'audit.sections.pages_non_indexable_like',
    group: 'pages',
    kind: 'page',
  },
  { key: 'broken_internal_links', labelKey: 'audit.sections.broken_internal_links', group: 'links', kind: 'link' },
  {
    key: 'unresolved_internal_targets',
    labelKey: 'audit.sections.unresolved_internal_targets',
    group: 'links',
    kind: 'link',
  },
  {
    key: 'redirecting_internal_links',
    labelKey: 'audit.sections.redirecting_internal_links',
    group: 'links',
    kind: 'link',
  },
  {
    key: 'internal_links_to_noindex_like_pages',
    labelKey: 'audit.sections.internal_links_to_noindex_like_pages',
    group: 'links',
    kind: 'link',
  },
  {
    key: 'internal_links_to_canonicalized_pages',
    labelKey: 'audit.sections.internal_links_to_canonicalized_pages',
    group: 'links',
    kind: 'link',
  },
  {
    key: 'redirect_chains_internal',
    labelKey: 'audit.sections.redirect_chains_internal',
    group: 'links',
    kind: 'link',
  },
  { key: 'pages_thin_content', labelKey: 'audit.sections.pages_thin_content', group: 'content', kind: 'page' },
  { key: 'pages_duplicate_content', labelKey: 'audit.sections.pages_duplicate_content', group: 'content', kind: 'duplicate' },
  { key: 'js_heavy_like_pages', labelKey: 'audit.sections.js_heavy_like_pages', group: 'technical', kind: 'page' },
  { key: 'rendered_pages', labelKey: 'audit.sections.rendered_pages', group: 'technical', kind: 'page' },
  {
    key: 'pages_with_render_errors',
    labelKey: 'audit.sections.pages_with_render_errors',
    group: 'technical',
    kind: 'page',
  },
  { key: 'pages_with_schema', labelKey: 'audit.sections.pages_with_schema', group: 'schema', kind: 'page' },
  { key: 'pages_missing_schema', labelKey: 'audit.sections.pages_missing_schema', group: 'schema', kind: 'page' },
  {
    key: 'pages_with_x_robots_tag',
    labelKey: 'audit.sections.pages_with_x_robots_tag',
    group: 'technical',
    kind: 'page',
  },
  {
    key: 'pages_with_schema_types_summary',
    labelKey: 'audit.sections.pages_with_schema_types_summary',
    group: 'schema',
    kind: 'duplicate',
  },
  {
    key: 'pages_with_missing_alt_images',
    labelKey: 'audit.sections.pages_with_missing_alt_images',
    group: 'media',
    kind: 'page',
  },
  { key: 'pages_with_no_images', labelKey: 'audit.sections.pages_with_no_images', group: 'media', kind: 'page' },
  { key: 'oversized_pages', labelKey: 'audit.sections.oversized_pages', group: 'media', kind: 'page' },
]

type SortableValue = boolean | number | string | null | undefined

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

function renderBadge(
  label: string,
  tone: 'stone' | 'rose' | 'amber' | 'teal' = 'stone',
  selected = false,
) {
  const styles = {
    stone: selected
      ? 'border-stone-950 bg-stone-950 !text-white shadow-sm'
      : 'border-stone-300 bg-stone-100 text-stone-700',
    rose: selected
      ? 'border-rose-700 bg-rose-700 !text-white shadow-sm'
      : 'border-rose-200 bg-rose-50 text-rose-700',
    amber: selected
      ? 'border-amber-600 bg-amber-600 !text-white shadow-sm'
      : 'border-amber-200 bg-amber-50 text-amber-700',
    teal: selected
      ? 'border-teal-700 bg-teal-700 !text-white shadow-sm'
      : 'border-teal-200 bg-teal-50 text-teal-700',
  }

  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${styles[tone]}`}>{label}</span>
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
}: {
  items: DuplicateValueGroup[]
  sectionKey: string
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

export function buildAuditSectionActionHref(
  section: AuditSectionDefinition,
  audit: AuditReport,
  context: AuditWorkspaceContext,
) {
  const query = new URLSearchParams()

  const appendQuery = (params: Record<string, string | number | boolean | undefined>) => {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === '' || value === false) {
        return
      }
      query.set(key, String(value))
    })
  }

  if (section.kind === 'link') {
    appendQuery(
      section.key === 'broken_internal_links'
        ? { broken_internal: true }
        : section.key === 'unresolved_internal_targets'
          ? { unresolved_internal: true }
          : section.key === 'redirecting_internal_links'
            ? { redirecting_internal: true }
            : section.key === 'internal_links_to_noindex_like_pages'
            ? { to_noindex_like: true }
            : section.key === 'internal_links_to_canonicalized_pages'
              ? { to_canonicalized: true }
              : { redirect_chain: true },
    )
    const base = `/jobs/${context.activeCrawlId}/links`
    const suffix = query.toString()
    return suffix ? `${base}?${suffix}` : base
  }

  if (section.kind === 'duplicate') {
    if (section.key === 'pages_duplicate_title') {
      const group = audit.pages_duplicate_title[0]
      appendQuery(
        group && audit.pages_duplicate_title.length === 1
          ? { title_exact: group.value, sort_by: 'title', sort_order: 'asc' }
          : { has_title: true, sort_by: 'title', sort_order: 'asc' },
      )
    } else if (section.key === 'pages_duplicate_meta_description') {
      const group = audit.pages_duplicate_meta_description[0]
      appendQuery(
        group && audit.pages_duplicate_meta_description.length === 1
          ? { meta_description_exact: group.value, sort_by: 'meta_description_length', sort_order: 'asc' }
          : { has_meta_description: true, sort_by: 'meta_description_length', sort_order: 'asc' },
      )
    } else if (section.key === 'pages_duplicate_content') {
      const group = audit.pages_duplicate_content[0]
      appendQuery(
        group && audit.pages_duplicate_content.length === 1
          ? { content_text_hash_exact: group.value, sort_by: 'word_count', sort_order: 'asc' }
          : { duplicate_content: true, sort_by: 'word_count', sort_order: 'asc' },
      )
    } else if (section.key === 'pages_with_schema_types_summary') {
      const group = audit.pages_with_schema_types_summary[0]
      appendQuery(
        group && audit.pages_with_schema_types_summary.length === 1
          ? { schema_type: group.value, sort_by: 'schema_count', sort_order: 'asc' }
          : { schema_present: true, sort_by: 'schema_count', sort_order: 'asc' },
      )
    }
    const base = buildSitePagesRecordsPath(context.siteId, {
      activeCrawlId: context.activeCrawlId,
      baselineCrawlId: context.baselineCrawlId,
    })
    const suffix = query.toString()
    return suffix ? `${base}&${suffix}` : base
  }

  appendQuery(
    section.key === 'pages_missing_title'
      ? { has_title: false, sort_by: 'title', sort_order: 'asc' }
      : section.key === 'pages_title_too_short'
        ? { title_too_short: true, sort_by: 'title_length', sort_order: 'asc' }
        : section.key === 'pages_title_too_long'
          ? { title_too_long: true, sort_by: 'title_length', sort_order: 'desc' }
          : section.key === 'pages_missing_meta_description'
            ? { has_meta_description: false, sort_by: 'meta_description_length', sort_order: 'asc' }
            : section.key === 'pages_meta_description_too_short'
              ? { meta_too_short: true, sort_by: 'meta_description_length', sort_order: 'asc' }
              : section.key === 'pages_meta_description_too_long'
                ? { meta_too_long: true, sort_by: 'meta_description_length', sort_order: 'desc' }
                : section.key === 'pages_missing_h1'
                  ? { has_h1: false, sort_by: 'h1_length', sort_order: 'asc' }
                  : section.key === 'pages_multiple_h1'
                    ? { multiple_h1: true, sort_by: 'h1_count', sort_order: 'desc' }
                    : section.key === 'pages_missing_h2'
                      ? { missing_h2: true, sort_by: 'h2_count', sort_order: 'desc' }
                      : section.key === 'pages_missing_canonical'
                        ? { canonical_missing: true, sort_by: 'canonical_url', sort_order: 'asc' }
                        : section.key === 'pages_self_canonical'
                          ? { self_canonical: true, sort_by: 'canonical_url', sort_order: 'asc' }
                          : section.key === 'pages_canonical_to_other_url'
                            ? { canonical_to_other_url: true, sort_by: 'canonical_url', sort_order: 'asc' }
                            : section.key === 'pages_canonical_to_non_200'
                              ? { canonical_to_non_200: true, sort_by: 'canonical_url', sort_order: 'asc' }
                              : section.key === 'pages_canonical_to_redirect'
                                ? { canonical_to_redirect: true, sort_by: 'canonical_url', sort_order: 'asc' }
                                : section.key === 'pages_noindex_like'
                                  ? { noindex_like: true, sort_by: 'url', sort_order: 'asc' }
                                  : section.key === 'pages_non_indexable_like'
                                    ? { non_indexable_like: true, sort_by: 'url', sort_order: 'asc' }
                                    : section.key === 'pages_thin_content'
                                      ? { thin_content: true, sort_by: 'word_count', sort_order: 'asc' }
                                      : section.key === 'js_heavy_like_pages'
                                        ? { js_heavy_like: true, sort_by: 'url', sort_order: 'asc' }
                                        : section.key === 'rendered_pages'
                                          ? { was_rendered: true, sort_by: 'url', sort_order: 'asc' }
                                          : section.key === 'pages_with_render_errors'
                                            ? { has_render_error: true, sort_by: 'url', sort_order: 'asc' }
                                            : section.key === 'pages_with_schema'
                                              ? { schema_present: true, sort_by: 'schema_count', sort_order: 'desc' }
                                              : section.key === 'pages_missing_schema'
                                                ? { schema_present: false, sort_by: 'schema_count', sort_order: 'asc' }
                                                : section.key === 'pages_with_x_robots_tag'
                                                  ? { has_x_robots_tag: true, sort_by: 'url', sort_order: 'asc' }
                                                  : section.key === 'pages_with_missing_alt_images'
                                                    ? { missing_alt_images: true, sort_by: 'images_missing_alt_count', sort_order: 'desc' }
                                                    : section.key === 'pages_with_no_images'
                                                      ? { no_images: true, sort_by: 'url', sort_order: 'asc' }
                                                      : { oversized: true, sort_by: 'html_size_bytes', sort_order: 'desc' },
  )

  const base = buildSitePagesRecordsPath(context.siteId, {
    activeCrawlId: context.activeCrawlId,
    baselineCrawlId: context.baselineCrawlId,
  })
  const suffix = query.toString()
  return suffix ? `${base}&${suffix}` : base
}

export function renderAuditSectionBody(section: AuditSectionDefinition, audit: AuditReport) {
  if (section.kind === 'link') {
    const items = audit[section.key] as LinkIssue[]
    return <LinkIssueTable items={items} />
  }

  if (section.kind === 'duplicate') {
    const items = audit[section.key] as DuplicateValueGroup[]
    return <DuplicateGroupTable items={items} sectionKey={section.key} />
  }

  const items = audit[section.key] as PageIssue[]
  return <PageIssueTable items={items} />
}

export function AuditSectionCard({
  label,
  count,
  group,
  open = false,
  action,
  children,
}: {
  label: string
  count: number
  group: AuditWorkspaceGroup
  open?: boolean
  action?: ReactNode
  children: ReactNode
}) {
  const { t } = useTranslation()
  const tone =
    group === 'links'
      ? 'amber'
      : group === 'content'
        ? 'rose'
        : group === 'technical'
          ? 'stone'
          : group === 'schema'
            ? 'teal'
            : 'amber'

  return (
    <details open={open && count > 0} className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/80">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-left">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-base font-semibold text-stone-950 dark:text-slate-50">{label}</p>
            {renderBadge(group, tone)}
          </div>
          <p className="text-sm text-stone-600 dark:text-slate-300">{t('audit.sectionRecords', { count })}</p>
        </div>
        <div className="flex items-center gap-2">
          {action}
          <span className="rounded-full bg-stone-100 px-3 py-1 text-sm font-semibold text-stone-700 dark:bg-slate-900 dark:text-slate-200">
            {count}
          </span>
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
