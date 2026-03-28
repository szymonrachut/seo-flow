import type {
  EditorDocumentBlock,
  EditorDocumentListItem,
  EditorReviewIssue,
  EditorReviewIssueSeverity,
  EditorReviewIssueStatus,
  EditorRewriteRun,
} from '../../types/api'

import type { AIReviewIssueQuickFilter } from './constants'

export interface AIReviewIssueStatusCounts {
  open: number
  dismissed: number
  rewrite_requested: number
  rewrite_ready: number
  applied: number
  resolved_manual: number
}

export interface AIReviewIssueSummary {
  total: number
  blockCount: number
  statusCounts: AIReviewIssueStatusCounts
  severityCounts: {
    low: number
    medium: number
    high: number
  }
}

const severityRank: Record<EditorReviewIssueSeverity, number> = {
  low: 1,
  medium: 2,
  high: 3,
}

export function humanizeAiReviewValue(value: string) {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(' ')
}

export function normalizeInlineEditText(value: string) {
  return value.replace(/\s+/g, ' ').trim()
}

export function summarizeIssues(issues: EditorReviewIssue[]): AIReviewIssueSummary {
  const statusCounts: AIReviewIssueStatusCounts = {
    open: 0,
    dismissed: 0,
    rewrite_requested: 0,
    rewrite_ready: 0,
    applied: 0,
    resolved_manual: 0,
  }
  const severityCounts = { low: 0, medium: 0, high: 0 }
  const blockKeys = new Set<string>()

  for (const issue of issues) {
    blockKeys.add(issue.block_key)
    statusCounts[issue.status] += 1
    severityCounts[issue.severity] += 1
  }

  return {
    total: issues.length,
    blockCount: blockKeys.size,
    statusCounts,
    severityCounts,
  }
}

export function summarizeDocuments(items: EditorDocumentListItem[]) {
  return items.reduce(
    (summary, item) => {
      summary.total += 1
      summary.blocks += item.active_block_count
      if (item.status === 'parsed') {
        summary.parsed += 1
      }
      if (item.status === 'draft') {
        summary.draft += 1
      }
      if (item.status === 'archived') {
        summary.archived += 1
      }
      return summary
    },
    {
      total: 0,
      parsed: 0,
      draft: 0,
      archived: 0,
      blocks: 0,
    },
  )
}

export function filterIssues(
  issues: EditorReviewIssue[],
  quickFilter: AIReviewIssueQuickFilter,
  issueType?: string,
) {
  return issues.filter((issue) => {
    if (issueType && issue.issue_type !== issueType) {
      return false
    }
    if (quickFilter === 'all') {
      return true
    }
    if (quickFilter === 'high') {
      return issue.severity === 'high'
    }
    return issue.status === quickFilter
  })
}

export function groupIssuesByBlock(issues: EditorReviewIssue[]) {
  return issues.reduce<Record<string, EditorReviewIssue[]>>((groups, issue) => {
    const existing = groups[issue.block_key] ?? []
    existing.push(issue)
    groups[issue.block_key] = existing
    return groups
  }, {})
}

export function getHighestSeverity(issues: EditorReviewIssue[]): EditorReviewIssueSeverity | null {
  if (issues.length === 0) {
    return null
  }
  return issues.reduce<EditorReviewIssueSeverity>((current, issue) => {
    return severityRank[issue.severity] > severityRank[current] ? issue.severity : current
  }, issues[0].severity)
}

export function getLatestRewriteRun(runs: EditorRewriteRun[]) {
  return runs[0] ?? null
}

export function getLatestCompletedRewriteRun(runs: EditorRewriteRun[]) {
  return runs.find((run) => run.status === 'completed' || run.status === 'applied') ?? null
}

export function isRewriteRunStale(run: EditorRewriteRun | null, block: EditorDocumentBlock | null) {
  if (!run) {
    return false
  }
  if (typeof run.is_stale === 'boolean') {
    return run.is_stale
  }
  if (!run || !block || !run.source_block_content_hash) {
    return false
  }
  return run.source_block_content_hash !== block.content_hash
}

export function isDismissableStatus(status: EditorReviewIssueStatus) {
  return status === 'open' || status === 'rewrite_requested' || status === 'rewrite_ready'
}

export function isManualResolvableStatus(status: EditorReviewIssueStatus) {
  return status === 'open' || status === 'rewrite_requested' || status === 'rewrite_ready'
}

export function isRewriteRequestableStatus(status: EditorReviewIssueStatus) {
  return status === 'open' || status === 'rewrite_ready'
}

export function isApplyableStatus(status: EditorReviewIssueStatus) {
  return status === 'rewrite_ready'
}
