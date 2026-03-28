import type {
  EditorReviewIssueStatus,
  EditorReviewIssueSeverity,
  EditorReviewKnownIssueType,
} from '../../types/api'

export const AI_REVIEW_ISSUE_QUICK_FILTERS = [
  'all',
  'open',
  'high',
  'dismissed',
  'resolved_manual',
  'rewrite_ready',
  'applied',
] as const

export type AIReviewIssueQuickFilter = (typeof AI_REVIEW_ISSUE_QUICK_FILTERS)[number]

export const AI_REVIEW_ISSUE_TYPES: readonly EditorReviewKnownIssueType[] = [
  'weak_heading',
  'short_paragraph',
  'placeholder_text',
  'todo_marker',
  'generic_heading',
  'factuality',
  'off_topic',
  'unsupported_claim',
  'irrelevant_entity',
  'brand_mismatch',
  'product_hallucination',
  'unclear',
  'terminology_inconsistency',
]

export const AI_REVIEW_ISSUE_STATUSES: readonly EditorReviewIssueStatus[] = [
  'open',
  'dismissed',
  'rewrite_requested',
  'rewrite_ready',
  'applied',
  'resolved_manual',
]

export const AI_REVIEW_SEVERITIES: readonly EditorReviewIssueSeverity[] = ['low', 'medium', 'high']
