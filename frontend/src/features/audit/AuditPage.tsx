import type { ReactNode } from 'react'
import { useParams } from 'react-router-dom'

import { buildApiUrl } from '../../api/client'
import { DataTable } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { DuplicateValueGroup, LinkIssue, NonIndexableLikeSignal, PageIssue } from '../../types/api'
import { formatNullable, truncateText } from '../../utils/format'
import { JobNavigation } from '../jobs/JobNavigation'
import { useAuditQuery } from './api'

function parseJobId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

function AuditSection({
  label,
  count,
  children,
}: {
  label: string
  count: number
  children: ReactNode
}) {
  return (
    <details open={count > 0} className="rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-left">
        <div>
          <p className="text-base font-semibold text-stone-950">{label}</p>
          <p className="mt-1 text-sm text-stone-600">{count} records</p>
        </div>
        <span className="rounded-full bg-stone-100 px-3 py-1 text-sm font-semibold text-stone-700">{count}</span>
      </summary>
      <div className="mt-4">
        {count === 0 ? (
          <EmptyState title="No records" description="This section is currently empty for the selected job." />
        ) : (
          children
        )}
      </div>
    </details>
  )
}

function PageIssueTable({ items }: { items: PageIssue[] }) {
  return (
    <DataTable
      columns={[
        { key: 'url', header: 'URL', cell: (item) => <span title={item.url}>{truncateText(item.url, 96)}</span> },
        { key: 'status', header: 'Status', cell: (item) => formatNullable(item.status_code) },
        { key: 'title', header: 'Title', cell: (item) => truncateText(item.title, 56) },
      ]}
      rows={items}
      rowKey={(item) => item.page_id}
    />
  )
}

function DuplicateGroupTable({ items, sectionKey }: { items: DuplicateValueGroup[]; sectionKey: string }) {
  return (
    <DataTable
      columns={[
        { key: 'value', header: 'Value', cell: (group) => truncateText(group.value, 80) },
        { key: 'count', header: 'Count', cell: (group) => group.count },
        {
          key: 'pages',
          header: 'Pages',
          cell: (group) => (
            <div className="space-y-1">
              {group.pages.map((page) => (
                <p key={page.page_id} className="break-all text-xs text-stone-600">
                  {page.url}
                </p>
              ))}
            </div>
          ),
        },
      ]}
      rows={items}
      rowKey={(group) => `${sectionKey}-${group.value}`}
    />
  )
}

function LinkIssueTable({ items }: { items: LinkIssue[] }) {
  return (
    <DataTable
      columns={[
        { key: 'source', header: 'Source URL', cell: (item) => truncateText(item.source_url, 72) },
        { key: 'target', header: 'Target URL', cell: (item) => truncateText(item.target_url, 72) },
        { key: 'status', header: 'Target status', cell: (item) => formatNullable(item.target_status_code) },
        { key: 'final', header: 'Final URL', cell: (item) => truncateText(item.final_url, 72) },
      ]}
      rows={items}
      rowKey={(item) => item.link_id}
    />
  )
}

function SignalTable({ items }: { items: NonIndexableLikeSignal[] }) {
  return (
    <DataTable
      columns={[
        { key: 'url', header: 'URL', cell: (item) => truncateText(item.url, 88) },
        { key: 'status', header: 'Status', cell: (item) => formatNullable(item.status_code) },
        { key: 'signals', header: 'Signals', cell: (item) => item.signals.join(', ') || '-' },
        { key: 'robots', header: 'Robots meta', cell: (item) => truncateText(item.robots_meta, 36) },
      ]}
      rows={items}
      rowKey={(item) => item.page_id}
    />
  )
}

export function AuditPage() {
  const params = useParams()
  const jobId = parseJobId(params.jobId)
  useDocumentTitle(jobId ? `Job #${jobId} audit` : 'Audit')

  if (jobId === null) {
    return <ErrorState title="Invalid job id" message="The route does not contain a valid numeric job id." />
  }

  const auditQuery = useAuditQuery(jobId)

  if (auditQuery.isLoading) {
    return <LoadingState label={`Loading audit for job #${jobId}...`} />
  }

  if (auditQuery.isError) {
    return (
      <ErrorState
        title="Audit request failed"
        message={auditQuery.error instanceof Error ? auditQuery.error.message : 'Unknown error'}
      />
    )
  }

  const audit = auditQuery.data
  if (!audit) {
    return <EmptyState title="Audit unavailable" description="The backend returned an empty audit response." />
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">Audit</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">
              Technical audit for job #{jobId}
            </h1>
            <p className="mt-2 text-sm text-stone-600">
              Summary counts on top, issue sections below. No charts, just actionable scan paths.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <JobNavigation jobId={jobId} />
            <a
              href={buildApiUrl(`/crawl-jobs/${jobId}/export/audit.csv`)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              Export audit.csv
            </a>
          </div>
        </div>
      </section>

      <SummaryCards
        items={[
          { label: 'Total pages', value: audit.summary.total_pages },
          { label: 'Missing title', value: audit.summary.pages_missing_title },
          { label: 'Missing meta', value: audit.summary.pages_missing_meta_description },
          { label: 'Missing H1', value: audit.summary.pages_missing_h1 },
          { label: 'Duplicate title groups', value: audit.summary.pages_duplicate_title_groups },
          { label: 'Duplicate meta groups', value: audit.summary.pages_duplicate_meta_description_groups },
          { label: 'Broken internal links', value: audit.summary.broken_internal_links },
          { label: 'Redirecting links', value: audit.summary.redirecting_internal_links },
        ]}
      />

      <div className="space-y-4">
        <AuditSection label="Pages missing title" count={audit.pages_missing_title.length}>
          <PageIssueTable items={audit.pages_missing_title} />
        </AuditSection>

        <AuditSection label="Pages missing meta description" count={audit.pages_missing_meta_description.length}>
          <PageIssueTable items={audit.pages_missing_meta_description} />
        </AuditSection>

        <AuditSection label="Pages missing H1" count={audit.pages_missing_h1.length}>
          <PageIssueTable items={audit.pages_missing_h1} />
        </AuditSection>

        <AuditSection label="Duplicate titles" count={audit.pages_duplicate_title.length}>
          <DuplicateGroupTable items={audit.pages_duplicate_title} sectionKey="pages_duplicate_title" />
        </AuditSection>

        <AuditSection label="Duplicate meta descriptions" count={audit.pages_duplicate_meta_description.length}>
          <DuplicateGroupTable
            items={audit.pages_duplicate_meta_description}
            sectionKey="pages_duplicate_meta_description"
          />
        </AuditSection>

        <AuditSection label="Broken internal links" count={audit.broken_internal_links.length}>
          <LinkIssueTable items={audit.broken_internal_links} />
        </AuditSection>

        <AuditSection label="Unresolved internal targets" count={audit.unresolved_internal_targets.length}>
          <LinkIssueTable items={audit.unresolved_internal_targets} />
        </AuditSection>

        <AuditSection label="Redirecting internal links" count={audit.redirecting_internal_links.length}>
          <LinkIssueTable items={audit.redirecting_internal_links} />
        </AuditSection>

        <AuditSection label="Non-indexable-like signals" count={audit.non_indexable_like_signals.length}>
          <SignalTable items={audit.non_indexable_like_signals} />
        </AuditSection>
      </div>
    </div>
  )
}
