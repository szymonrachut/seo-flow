import { startTransition, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { DataViewHeader } from '../../components/DataViewHeader'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { QuickFilterBar } from '../../components/QuickFilterBar'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type {
  EditorDocumentBlock,
  EditorDocumentBlockType,
  EditorReviewIssue,
  EditorReviewMode,
  EditorReviewIssueSeverity,
  EditorReviewIssueStatus,
  EditorReviewRunStatus,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime } from '../../utils/format'
import { mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import { buildSiteAiReviewEditorDocumentsPath } from '../sites/routes'
import { AIReviewEditorDiffPreviewSection } from './AIReviewEditorDiffPreviewSection'
import { AIReviewEditorVersionHistorySection } from './AIReviewEditorVersionHistorySection'
import {
  useApplySiteAiRewriteRunMutation,
  useCreateSiteAiReviewRunMutation,
  useDeleteSiteAiReviewBlockMutation,
  useDismissSiteAiReviewIssueMutation,
  useInsertSiteAiReviewBlockMutation,
  useParseSiteAiReviewDocumentMutation,
  useRequestSiteAiRewriteRunMutation,
  useRestoreSiteAiReviewVersionMutation,
  useResolveSiteAiReviewIssueManuallyMutation,
  useSiteAiReviewBlocksQuery,
  useSiteAiReviewDocumentQuery,
  useSiteAiReviewIssuesQuery,
  useSiteAiReviewRunsQuery,
  useSiteAiReviewSummaryQuery,
  useSiteAiReviewVersionDiffQuery,
  useSiteAiReviewVersionsQuery,
  useSiteAiRewriteRunsQuery,
  useUpdateSiteAiReviewBlockMutation,
} from './api'
import { AI_REVIEW_ISSUE_QUICK_FILTERS, AI_REVIEW_ISSUE_TYPES, type AIReviewIssueQuickFilter } from './constants'
import {
  filterIssues,
  getHighestSeverity,
  getLatestCompletedRewriteRun,
  getLatestRewriteRun,
  groupIssuesByBlock,
  humanizeAiReviewValue,
  isDismissableStatus,
  isManualResolvableStatus,
  isRewriteRunStale,
  isRewriteRequestableStatus,
  normalizeInlineEditText,
  summarizeIssues,
} from './utils'

type BadgeTone = 'stone' | 'rose' | 'amber' | 'teal'
type HeaderTone = 'default' | 'warning' | 'success'

const surfaceClass =
  'rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const sectionClass =
  'rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const panelClass =
  'rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/85'
const actionClass =
  'inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-100 dark:hover:border-slate-600 dark:hover:bg-slate-900'
const primaryActionClass =
  'inline-flex rounded-full bg-stone-950 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-teal-400 dark:text-slate-950 dark:hover:bg-teal-300'
const fieldLabelClass = 'grid gap-1 text-sm text-stone-700 dark:text-slate-300'
const fieldControlClass =
  'rounded-2xl border border-stone-300 bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-teal-400 dark:focus:ring-teal-500/30'

function parseDocumentId(rawValue: string | undefined) {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

function readQuickFilter(value: string | null): AIReviewIssueQuickFilter {
  return AI_REVIEW_ISSUE_QUICK_FILTERS.includes(value as AIReviewIssueQuickFilter)
    ? (value as AIReviewIssueQuickFilter)
    : 'all'
}

function readIssueTypeFilter(value: string | null) {
  return value && AI_REVIEW_ISSUE_TYPES.includes(value as (typeof AI_REVIEW_ISSUE_TYPES)[number]) ? value : undefined
}

function normalizeReviewMode(value: string | null | undefined): EditorReviewMode {
  if (value === 'light' || value === 'strict') {
    return value
  }
  return 'standard'
}

function toneClass(tone: BadgeTone) {
  if (tone === 'rose') {
    return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/60 dark:text-rose-200'
  }
  if (tone === 'amber') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200'
  }
  if (tone === 'teal') {
    return 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/60 dark:text-teal-200'
  }
  return 'border-stone-300 bg-stone-100 text-stone-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
}

function toHeaderTone(tone: BadgeTone): HeaderTone {
  if (tone === 'teal') {
    return 'success'
  }
  if (tone === 'amber' || tone === 'rose') {
    return 'warning'
  }
  return 'default'
}

function issueStatusTone(status: EditorReviewIssueStatus): BadgeTone {
  if (status === 'applied' || status === 'resolved_manual') {
    return 'teal'
  }
  if (status === 'rewrite_ready' || status === 'rewrite_requested') {
    return 'amber'
  }
  if (status === 'dismissed') {
    return 'stone'
  }
  return 'rose'
}

function issueSeverityTone(severity: EditorReviewIssueSeverity): BadgeTone {
  if (severity === 'high') {
    return 'rose'
  }
  if (severity === 'medium') {
    return 'amber'
  }
  return 'stone'
}

function reviewRunTone(status: EditorReviewRunStatus | null | undefined): BadgeTone {
  if (status === 'completed') {
    return 'teal'
  }
  if (status === 'queued' || status === 'running') {
    return 'amber'
  }
  if (status === 'failed' || status === 'cancelled') {
    return 'rose'
  }
  return 'stone'
}

function documentStatusTone(status: string): BadgeTone {
  if (status === 'parsed') {
    return 'teal'
  }
  if (status === 'draft') {
    return 'amber'
  }
  return 'stone'
}

function renderBadge(label: string, tone: BadgeTone = 'stone') {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${toneClass(tone)}`}
    >
      {label}
    </span>
  )
}

function BlockBody({ block }: { block: EditorDocumentBlock }) {
  if (block.block_type === 'heading') {
    const level = Math.min(6, Math.max(1, block.block_level ?? 2))
    const className =
      level === 1
        ? 'text-3xl font-semibold tracking-tight text-stone-950 dark:text-slate-50'
        : level === 2
          ? 'text-2xl font-semibold tracking-tight text-stone-950 dark:text-slate-50'
          : level === 3
            ? 'text-xl font-semibold text-stone-950 dark:text-slate-50'
            : 'text-lg font-semibold text-stone-950 dark:text-slate-50'

    if (level === 1) {
      return <h1 className={className}>{block.text_content}</h1>
    }
    if (level === 2) {
      return <h2 className={className}>{block.text_content}</h2>
    }
    if (level === 3) {
      return <h3 className={className}>{block.text_content}</h3>
    }
    return <h4 className={className}>{block.text_content}</h4>
  }

  if (block.block_type === 'list_item') {
    return (
      <div role="listitem" className="flex gap-3 text-base leading-7 text-stone-700 dark:text-slate-200">
        <span className="mt-1 text-sm font-semibold text-stone-500 dark:text-slate-400">*</span>
        <span>{block.text_content}</span>
      </div>
    )
  }

  return <p className="text-base leading-7 text-stone-700 dark:text-slate-200">{block.text_content}</p>
}

interface BlockInlineEditorProps {
  block: EditorDocumentBlock
  editingText: string
  onChange: (nextValue: string) => void
  onSave: () => void
  onCancel: () => void
  isSaving: boolean
  saveDisabled: boolean
  fieldLabelClass: string
  fieldControlClass: string
  actionClass: string
  primaryActionClass: string
  helperLabel: string
  saveLabel: string
  cancelLabel: string
}

function BlockInlineEditor({
  block,
  editingText,
  onChange,
  onSave,
  onCancel,
  isSaving,
  saveDisabled,
  fieldLabelClass,
  fieldControlClass,
  actionClass,
  primaryActionClass,
  helperLabel,
  saveLabel,
  cancelLabel,
}: BlockInlineEditorProps) {
  const isHeading = block.block_type === 'heading'

  return (
    <div className="space-y-4">
      <label className={fieldLabelClass}>
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
          {helperLabel}
        </span>
        {isHeading ? (
          <input
            value={editingText}
            onChange={(event) => onChange(event.target.value)}
            className={fieldControlClass}
            maxLength={12000}
          />
        ) : (
          <textarea
            value={editingText}
            onChange={(event) => onChange(event.target.value)}
            className={`${fieldControlClass} min-h-32 resize-y`}
            maxLength={12000}
          />
        )}
      </label>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={saveDisabled || isSaving}
          className={primaryActionClass}
        >
          {saveLabel}
        </button>
        <button type="button" onClick={onCancel} disabled={isSaving} className={actionClass}>
          {cancelLabel}
        </button>
      </div>
    </div>
  )
}

interface BlockInsertDraft {
  targetBlockKey: string
  position: 'before' | 'after'
  blockType: EditorDocumentBlockType
  blockLevel: number
  textContent: string
}

interface BlockInsertComposerProps {
  draft: BlockInsertDraft
  onTypeChange: (nextType: EditorDocumentBlockType) => void
  onLevelChange: (nextLevel: number) => void
  onTextChange: (nextValue: string) => void
  onSave: () => void
  onCancel: () => void
  isSaving: boolean
  saveDisabled: boolean
  fieldLabelClass: string
  fieldControlClass: string
  actionClass: string
  primaryActionClass: string
}

function BlockInsertComposer({
  draft,
  onTypeChange,
  onLevelChange,
  onTextChange,
  onSave,
  onCancel,
  isSaving,
  saveDisabled,
  fieldLabelClass,
  fieldControlClass,
  actionClass,
  primaryActionClass,
}: BlockInsertComposerProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <label className={fieldLabelClass}>
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
            {t('aiReviewEditor.document.insertTypeLabel')}
          </span>
          <select
            value={draft.blockType}
            onChange={(event) => onTypeChange(event.target.value as EditorDocumentBlockType)}
            className={fieldControlClass}
          >
            <option value="paragraph">{humanizeAiReviewValue('paragraph')}</option>
            <option value="heading">{humanizeAiReviewValue('heading')}</option>
            <option value="list_item">{humanizeAiReviewValue('list_item')}</option>
          </select>
        </label>
        {draft.blockType === 'heading' ? (
          <label className={fieldLabelClass}>
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
              {t('aiReviewEditor.document.insertLevelLabel')}
            </span>
            <select
              value={draft.blockLevel}
              onChange={(event) => onLevelChange(Number(event.target.value))}
              className={fieldControlClass}
            >
              {[1, 2, 3, 4, 5, 6].map((level) => (
                <option key={level} value={level}>
                  H{level}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
      <label className={fieldLabelClass}>
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
          {t('aiReviewEditor.document.insertFieldLabel')}
        </span>
        {draft.blockType === 'heading' ? (
          <input
            value={draft.textContent}
            onChange={(event) => onTextChange(event.target.value)}
            className={fieldControlClass}
            maxLength={12000}
          />
        ) : (
          <textarea
            value={draft.textContent}
            onChange={(event) => onTextChange(event.target.value)}
            className={`${fieldControlClass} min-h-32 resize-y`}
            maxLength={12000}
          />
        )}
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onSave} disabled={saveDisabled || isSaving} className={primaryActionClass}>
          {t('aiReviewEditor.actions.insertBlock')}
        </button>
        <button type="button" onClick={onCancel} disabled={isSaving} className={actionClass}>
          {t('aiReviewEditor.actions.cancelInsert')}
        </button>
      </div>
    </div>
  )
}

export function AIReviewEditorDocumentPage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const params = useParams()
  const documentId = parseDocumentId(params.documentId)
  const isDocumentIdValid = documentId !== null
  const [searchParams, setSearchParams] = useSearchParams()
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionNotice, setActionNotice] = useState<string | null>(null)
  const [editingBlockKey, setEditingBlockKey] = useState<string | null>(null)
  const [editingText, setEditingText] = useState('')
  const [insertDraft, setInsertDraft] = useState<BlockInsertDraft | null>(null)

  const quickFilter = readQuickFilter(searchParams.get('issue_filter'))
  const issueTypeFilter = readIssueTypeFilter(searchParams.get('issue_type'))
  const selectedBlockKey = searchParams.get('block') || undefined
  const selectedIssueId = parseIntegerParam(searchParams.get('issue'), undefined)
  const selectedVersionId = parseIntegerParam(searchParams.get('version'), undefined)

  const documentQuery = useSiteAiReviewDocumentQuery(site.id, documentId ?? 0, isDocumentIdValid)
  const blocksQuery = useSiteAiReviewBlocksQuery(site.id, documentId ?? 0, isDocumentIdValid)
  const issuesQuery = useSiteAiReviewIssuesQuery(site.id, documentId ?? 0, isDocumentIdValid)
  const summaryQuery = useSiteAiReviewSummaryQuery(site.id, documentId ?? 0, isDocumentIdValid)
  const reviewRunsQuery = useSiteAiReviewRunsQuery(site.id, documentId ?? 0, isDocumentIdValid)
  const versionsQuery = useSiteAiReviewVersionsQuery(site.id, documentId ?? 0, isDocumentIdValid)
  const parseDocumentMutation = useParseSiteAiReviewDocumentMutation(site.id, documentId ?? 0)
  const runReviewMutation = useCreateSiteAiReviewRunMutation(site.id, documentId ?? 0)
  const dismissIssueMutation = useDismissSiteAiReviewIssueMutation(site.id, documentId ?? 0)
  const resolveManualMutation = useResolveSiteAiReviewIssueManuallyMutation(site.id, documentId ?? 0)
  const requestRewriteMutation = useRequestSiteAiRewriteRunMutation(site.id, documentId ?? 0)
  const applyRewriteMutation = useApplySiteAiRewriteRunMutation(site.id, documentId ?? 0)
  const restoreVersionMutation = useRestoreSiteAiReviewVersionMutation(site.id, documentId ?? 0)
  const updateBlockMutation = useUpdateSiteAiReviewBlockMutation(site.id, documentId ?? 0)
  const insertBlockMutation = useInsertSiteAiReviewBlockMutation(site.id, documentId ?? 0)
  const deleteBlockMutation = useDeleteSiteAiReviewBlockMutation(site.id, documentId ?? 0)

  const document = documentQuery.data
  const blocks = blocksQuery.data?.items ?? []
  const activeBlockKeys = useMemo(() => new Set(blocks.map((block) => block.block_key)), [blocks])
  const allIssues = issuesQuery.data?.items ?? []
  const filteredIssues = useMemo(
    () => filterIssues(allIssues, quickFilter, issueTypeFilter),
    [allIssues, quickFilter, issueTypeFilter],
  )
  const visibleIssues = useMemo(
    () => filteredIssues.filter((issue) => activeBlockKeys.has(issue.block_key)),
    [activeBlockKeys, filteredIssues],
  )
  const issuesByBlock = useMemo(() => groupIssuesByBlock(visibleIssues), [visibleIssues])
  const issueSummary = useMemo(() => summarizeIssues(allIssues), [allIssues])
  const reviewRuns = reviewRunsQuery.data?.items ?? []
  const latestRun = reviewRuns[0] ?? null
  const reviewMatchesCurrentDocument =
    issuesQuery.data?.review_matches_current_document ?? summaryQuery.data?.latest_review_matches_current_document ?? null
  const reviewNeedsRefresh = reviewMatchesCurrentDocument === false
  const hasReviewRuns = reviewRuns.length > 0
  const hasAnyIssues = allIssues.length > 0
  const latestReviewFailed = latestRun?.status === 'failed'
  const latestReviewInProgress = latestRun?.status === 'queued' || latestRun?.status === 'running'
  const versions = versionsQuery.data?.items ?? []
  const currentVersion = versions.find((version) => version.is_current) ?? versions[0] ?? null
  const selectedVersion = versions.find((version) => version.id === selectedVersionId) ?? null
  const compareToVersionId =
    selectedVersion == null
      ? null
      : selectedVersion.is_current
        ? versions.find((version) => version.id !== selectedVersion.id)?.id ?? null
        : currentVersion?.id ?? null
  const versionDiffQuery = useSiteAiReviewVersionDiffQuery(
    site.id,
    documentId ?? 0,
    selectedVersion?.id ?? 0,
    compareToVersionId,
    isDocumentIdValid && Boolean(selectedVersion),
  )

  const selectedBlock = selectedBlockKey ? blocks.find((block) => block.block_key === selectedBlockKey) ?? null : null
  const selectedBlockIssues = selectedBlock ? issuesByBlock[selectedBlock.block_key] ?? [] : []
  const selectedIssue = selectedBlockIssues.find((issue) => issue.id === selectedIssueId) ?? selectedBlockIssues[0] ?? null
  const rewriteRunsQuery = useSiteAiRewriteRunsQuery(
    site.id,
    documentId ?? 0,
    selectedIssue?.id ?? 0,
    isDocumentIdValid && Boolean(selectedIssue),
  )
  const rewriteRuns = rewriteRunsQuery.data?.items ?? []
  const latestRewriteRun = useMemo(() => getLatestRewriteRun(rewriteRuns), [rewriteRuns])
  const latestCompletedRewriteRun = useMemo(() => getLatestCompletedRewriteRun(rewriteRuns), [rewriteRuns])
  const rewritePreviewText = latestCompletedRewriteRun?.result_text ?? selectedIssue?.replacement_candidate_text ?? null
  const canApplyRewrite =
    selectedIssue?.status === 'rewrite_ready' &&
    !reviewNeedsRefresh &&
    !isRewriteRunStale(latestCompletedRewriteRun, selectedBlock) &&
    latestCompletedRewriteRun?.status === 'completed' &&
    Boolean(latestCompletedRewriteRun.result_text)
  const isRefreshing =
    documentQuery.isFetching ||
    blocksQuery.isFetching ||
    issuesQuery.isFetching ||
    summaryQuery.isFetching ||
    reviewRunsQuery.isFetching ||
    versionsQuery.isFetching

  useDocumentTitle(
    document?.title
      ? t('documentTitle.aiReviewEditorDocument', { domain: site.domain, title: document.title })
      : t('documentTitle.aiReviewEditorDocuments', { domain: site.domain }),
  )

  useEffect(() => {
    if (!isDocumentIdValid) {
      return
    }

    if (visibleIssues.length === 0) {
      if (!selectedBlockKey && !selectedIssueId) {
        return
      }
      const next = mergeSearchParams(searchParams, {
        block: undefined,
        issue: undefined,
      })
      startTransition(() => setSearchParams(next, { replace: true }))
      return
    }

    let nextBlockKey = selectedBlockKey
    if (!nextBlockKey || !activeBlockKeys.has(nextBlockKey) || !issuesByBlock[nextBlockKey]) {
      nextBlockKey = visibleIssues[0]?.block_key
    }

    let nextIssueId = selectedIssueId
    const nextBlockIssues = nextBlockKey ? issuesByBlock[nextBlockKey] ?? [] : []
    if (!nextIssueId || !nextBlockIssues.some((issue) => issue.id === nextIssueId)) {
      nextIssueId = nextBlockIssues[0]?.id
    }

    if (nextBlockKey !== selectedBlockKey || nextIssueId !== selectedIssueId) {
      const next = mergeSearchParams(searchParams, {
        block: nextBlockKey,
        issue: nextIssueId,
      })
      startTransition(() => setSearchParams(next, { replace: true }))
    }
  }, [
    activeBlockKeys,
    isDocumentIdValid,
    issuesByBlock,
    searchParams,
    selectedBlockKey,
    selectedIssueId,
    setSearchParams,
    visibleIssues,
  ])

  useEffect(() => {
    if (!selectedVersionId) {
      return
    }
    if (versionsQuery.isLoading || versionsQuery.isError) {
      return
    }
    if (versions.some((version) => version.id === selectedVersionId)) {
      return
    }
    const next = mergeSearchParams(searchParams, {
      version: undefined,
    })
    startTransition(() => setSearchParams(next, { replace: true }))
  }, [searchParams, selectedVersionId, setSearchParams, versions, versionsQuery.isError, versionsQuery.isLoading])

  useEffect(() => {
    if (!actionNotice) {
      return
    }
    const timeoutId = window.setTimeout(() => {
      setActionNotice(null)
    }, 4500)
    return () => window.clearTimeout(timeoutId)
  }, [actionNotice])

  function updateSearch(updates: Record<string, string | number | undefined>) {
    const next = mergeSearchParams(searchParams, updates)
    startTransition(() => setSearchParams(next))
  }

  function clearInlineDraftState() {
    setEditingBlockKey(null)
    setEditingText('')
    setInsertDraft(null)
  }

  function selectIssue(issue: EditorReviewIssue) {
    updateSearch({
      block: issue.block_key,
      issue: issue.id,
    })
  }

  function startEditingBlock(block: EditorDocumentBlock, blockIssues: EditorReviewIssue[]) {
    setActionError(null)
    setActionNotice(null)
    setInsertDraft(null)
    setEditingBlockKey(block.block_key)
    setEditingText(block.text_content)
    if (blockIssues.length > 0) {
      updateSearch({
        block: block.block_key,
        issue: blockIssues[0]?.id,
      })
    }
  }

  function cancelBlockEdit() {
    setEditingBlockKey(null)
    setEditingText('')
  }

  function startInsertBlock(block: EditorDocumentBlock, position: 'before' | 'after') {
    setActionError(null)
    setActionNotice(null)
    setEditingBlockKey(null)
    setEditingText('')
    setInsertDraft({
      targetBlockKey: block.block_key,
      position,
      blockType: 'paragraph',
      blockLevel: 2,
      textContent: '',
    })
  }

  function cancelInsertBlock() {
    setInsertDraft(null)
  }

  async function parseDocument() {
    const payload = await parseDocumentMutation.mutateAsync()
    clearInlineDraftState()
    setActionNotice(
      t('aiReviewEditor.document.parseSaved', {
        blocksCount: payload.blocks_created_count,
      }),
    )
  }

  async function runReview() {
    const payload = await runReviewMutation.mutateAsync({
      review_mode: normalizeReviewMode(latestRun?.review_mode),
    })
    if (payload.status === 'completed') {
      setActionNotice(
        t('aiReviewEditor.document.reviewCompleted', {
          runId: payload.id,
          issueCount: payload.issue_count,
        }),
      )
      return
    }
    setActionError(payload.error_message ?? t('aiReviewEditor.document.reviewFailed'))
  }

  async function dismissIssue(issueId: number) {
    await dismissIssueMutation.mutateAsync({
      issueId,
      payload: {},
    })
    setActionNotice(t('aiReviewEditor.document.issueDismissed'))
  }

  async function resolveIssueManually(issueId: number) {
    await resolveManualMutation.mutateAsync({
      issueId,
      payload: {},
    })
    setActionNotice(t('aiReviewEditor.document.issueResolvedManually'))
  }

  async function requestRewrite(issueId: number) {
    const payload = await requestRewriteMutation.mutateAsync(issueId)
    if (payload.status === 'completed') {
      setActionNotice(t('aiReviewEditor.document.rewriteReady'))
      return
    }
    setActionError(payload.error_message ?? t('aiReviewEditor.document.rewriteFailed'))
  }

  async function applyRewrite(issueId: number, rewriteRunId: number) {
    const payload = await applyRewriteMutation.mutateAsync({
      rewriteRunId,
      issueId,
    })
    setActionNotice(
      t('aiReviewEditor.document.rewriteApplied', {
        blockKey: payload.updated_block.block_key,
      }),
    )
  }

  async function restoreVersion(versionId: number) {
    clearInlineDraftState()
    const restored = await restoreVersionMutation.mutateAsync(versionId)
    setActionNotice(
      t('aiReviewEditor.document.restoreSaved', {
        versionNo: restored.current_version.version_no,
      }),
    )
    updateSearch({
      version: restored.current_version.id,
    })
  }

  async function saveBlockEdit(block: EditorDocumentBlock) {
    const payload = await updateBlockMutation.mutateAsync({
      blockKey: block.block_key,
      payload: {
        text_content: editingText,
        expected_content_hash: block.content_hash,
      },
    })
    setEditingBlockKey(null)
    setEditingText('')
    setActionNotice(
      payload.changed
        ? t('aiReviewEditor.document.manualEditSaved', { versionNo: payload.current_version.version_no })
        : t('aiReviewEditor.document.manualEditNoChanges'),
    )
    updateSearch({
      version: payload.current_version.id,
    })
  }

  async function saveInsertedBlock() {
    if (!insertDraft) {
      return
    }
    const payload = await insertBlockMutation.mutateAsync({
      target_block_key: insertDraft.targetBlockKey,
      position: insertDraft.position,
      block_type: insertDraft.blockType,
      block_level: insertDraft.blockType === 'heading' ? insertDraft.blockLevel : undefined,
      text_content: insertDraft.textContent,
    })
    setInsertDraft(null)
    setActionNotice(t('aiReviewEditor.document.insertSaved', { versionNo: payload.current_version.version_no }))
    updateSearch({
      block: payload.inserted_block.block_key,
      issue: undefined,
      version: payload.current_version.id,
    })
  }

  async function deleteBlock(block: EditorDocumentBlock) {
    const payload = await deleteBlockMutation.mutateAsync(block.block_key)
    if (editingBlockKey === block.block_key) {
      cancelBlockEdit()
    }
    if (insertDraft?.targetBlockKey === block.block_key) {
      cancelInsertBlock()
    }
    setActionNotice(t('aiReviewEditor.document.deleteSaved', { versionNo: payload.current_version.version_no }))
    updateSearch({
      block: selectedBlockKey === block.block_key ? undefined : selectedBlockKey,
      issue: selectedBlockKey === block.block_key ? undefined : selectedIssueId,
      version: payload.current_version.id,
    })
  }

  async function runAction(action: () => Promise<unknown>) {
    setActionError(null)
    setActionNotice(null)
    try {
      await action()
    } catch (error) {
      setActionError(getUiErrorMessage(error, t))
    }
  }

  if (!isDocumentIdValid) {
    return (
      <ErrorState
        title={t('aiReviewEditor.document.invalidIdTitle')}
        message={t('aiReviewEditor.document.invalidIdMessage')}
      />
    )
  }

  if (
    documentQuery.isLoading ||
    blocksQuery.isLoading ||
    issuesQuery.isLoading ||
    summaryQuery.isLoading ||
    reviewRunsQuery.isLoading ||
    versionsQuery.isLoading
  ) {
    return <LoadingState label={t('aiReviewEditor.document.loading')} />
  }

  if (
    documentQuery.isError ||
    blocksQuery.isError ||
    issuesQuery.isError ||
    summaryQuery.isError ||
    reviewRunsQuery.isError ||
    versionsQuery.isError
  ) {
    const error =
      documentQuery.error ??
      blocksQuery.error ??
      issuesQuery.error ??
      summaryQuery.error ??
      reviewRunsQuery.error ??
      versionsQuery.error
    return <ErrorState title={t('aiReviewEditor.document.errorTitle')} message={getUiErrorMessage(error, t)} />
  }

  if (!document || !summaryQuery.data) {
    return (
      <EmptyState
        title={t('aiReviewEditor.document.emptyTitle')}
        description={t('aiReviewEditor.document.emptyDescription')}
      />
    )
  }

  const isBlockMutationPending =
    updateBlockMutation.isPending || insertBlockMutation.isPending || deleteBlockMutation.isPending
  const normalizedInsertText = insertDraft ? normalizeInlineEditText(insertDraft.textContent) : ''
  const insertSaveDisabled = !insertDraft || normalizedInsertText.length === 0
  const issueActionsLockedReason = reviewNeedsRefresh
    ? t('aiReviewEditor.issuePanel.actionsLockedDescription')
    : latestReviewFailed
      ? latestRun?.error_message ?? t('aiReviewEditor.document.reviewFailed')
      : latestReviewInProgress
        ? t('aiReviewEditor.document.reviewRunningNotice')
        : null
  const issuePanelEmptyState =
    !hasReviewRuns
      ? {
          title: t('aiReviewEditor.document.noReviewYetTitle'),
          description: t('aiReviewEditor.document.noReviewYetDescription'),
        }
      : latestReviewInProgress
        ? {
            title: t('aiReviewEditor.document.reviewRunningTitle'),
            description: t('aiReviewEditor.document.reviewRunningNotice'),
          }
      : latestReviewFailed
        ? {
            title: t('aiReviewEditor.document.reviewFailedTitle'),
            description: latestRun?.error_message ?? t('aiReviewEditor.document.reviewFailed'),
          }
        : !hasAnyIssues
          ? {
              title: t('aiReviewEditor.document.noVisibleIssuesTitle'),
              description: t('aiReviewEditor.document.noVisibleIssuesDescription'),
            }
          : visibleIssues.length === 0
            ? {
                title: t('aiReviewEditor.issuePanel.emptyFilteredTitle'),
                description: t('aiReviewEditor.issuePanel.emptyFilteredDescription'),
              }
            : {
                title: t('aiReviewEditor.issuePanel.emptySelectionTitle'),
                description: t('aiReviewEditor.issuePanel.emptySelectionDescription'),
              }

  const primaryAction =
    blocks.length > 0
      ? {
          key: 'run-review',
          label: runReviewMutation.isPending
            ? t('aiReviewEditor.actions.reviewRunning')
            : t('aiReviewEditor.actions.runReview'),
          onClick: () => void runAction(() => runReview()),
          disabled: runReviewMutation.isPending || Boolean(editingBlockKey || insertDraft) || isBlockMutationPending,
        }
      : {
          key: 'parse-document',
          label: parseDocumentMutation.isPending
            ? t('aiReviewEditor.actions.parsing')
            : t('aiReviewEditor.actions.parse'),
          onClick: () => void runAction(() => parseDocument()),
          disabled: parseDocumentMutation.isPending,
        }

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('aiReviewEditor.header.eyebrow')}
        title={document.title}
        description={t('aiReviewEditor.document.description')}
        contextChips={[
          {
            label: t('aiReviewEditor.document.context.type'),
            value: document.document_type,
          },
          {
            label: t('aiReviewEditor.document.context.status'),
            value: t(`aiReviewEditor.documentStatus.${document.status}`),
            tone: toHeaderTone(documentStatusTone(document.status)),
          },
          {
            label: t('aiReviewEditor.document.context.blocks'),
            value: String(document.active_block_count),
          },
          {
            label: t('aiReviewEditor.document.context.latestRun'),
            value: latestRun ? t(`aiReviewEditor.reviewRunStatus.${latestRun.status}`) : t('aiReviewEditor.common.none'),
            tone: latestRun ? toHeaderTone(reviewRunTone(latestRun.status)) : 'default',
          },
        ]}
        primaryAction={primaryAction}
        operations={[
          {
            key: 'documents',
            label: t('aiReviewEditor.actions.openDocuments'),
            to: buildSiteAiReviewEditorDocumentsPath(site.id, {
              activeCrawlId,
              baselineCrawlId,
            }),
          },
        ]}
      />

      {isRefreshing ? (
        <section className="rounded-3xl border border-stone-300 bg-stone-50/90 p-4 text-sm text-stone-700 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-200">
          {t('aiReviewEditor.document.refreshing')}
        </section>
      ) : null}

      {actionError ? (
        <section className="rounded-3xl border border-rose-200 bg-rose-50/90 p-4 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          {actionError}
        </section>
      ) : null}

      {actionNotice ? (
        <section className="rounded-3xl border border-teal-200 bg-teal-50/90 p-4 text-sm text-teal-700 dark:border-teal-900 dark:bg-teal-950/40 dark:text-teal-200">
          {actionNotice}
        </section>
      ) : null}

      {latestRun?.status === 'failed' ? (
        <section className="rounded-3xl border border-rose-200 bg-rose-50/90 p-4 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          <p className="font-semibold">{t('aiReviewEditor.document.reviewFailedBannerTitle')}</p>
          <p className="mt-1">
            {latestRun.error_message ?? t('aiReviewEditor.document.reviewFailed')}
          </p>
        </section>
      ) : null}

      {latestReviewInProgress ? (
        <section className="rounded-3xl border border-amber-200 bg-amber-50/90 p-4 text-sm text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <p className="font-semibold">{t('aiReviewEditor.document.reviewRunningTitle')}</p>
          <p className="mt-1">{t('aiReviewEditor.document.reviewRunningNotice')}</p>
        </section>
      ) : null}

      {reviewNeedsRefresh ? (
        <section className="rounded-3xl border border-amber-200 bg-amber-50/90 p-4 text-sm text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <p className="font-semibold">{t('aiReviewEditor.document.reviewStaleTitle')}</p>
          <p className="mt-1">{t('aiReviewEditor.document.reviewStaleDescription')}</p>
        </section>
      ) : null}

      {Boolean(editingBlockKey || insertDraft) ? (
        <section className="rounded-3xl border border-stone-300 bg-stone-50/90 p-4 text-sm text-stone-700 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-200">
          {t('aiReviewEditor.document.localDraftNotice')}
        </section>
      ) : null}

      <SummaryCards
        items={[
          {
            label: t('aiReviewEditor.document.summary.totalIssues'),
            value: summaryQuery.data.issue_count,
          },
          {
            label: t('aiReviewEditor.document.summary.blocksWithIssues'),
            value: summaryQuery.data.issue_block_count,
          },
          {
            label: t('aiReviewEditor.document.summary.openIssues'),
            value: issueSummary.statusCounts.open,
          },
          {
            label: t('aiReviewEditor.document.summary.highSeverity'),
            value: summaryQuery.data.severity_counts.high,
          },
        ]}
      />

      {latestRun?.status === 'completed' && reviewMatchesCurrentDocument && visibleIssues.length === 0 ? (
        <section className="rounded-3xl border border-teal-200 bg-teal-50/90 p-4 text-sm text-teal-700 dark:border-teal-900 dark:bg-teal-950/40 dark:text-teal-200">
          <p className="font-semibold">{t('aiReviewEditor.document.noVisibleIssuesTitle')}</p>
          <p className="mt-1">
            {quickFilter === 'all' && !issueTypeFilter
              ? t('aiReviewEditor.document.noVisibleIssuesDescription')
              : t('aiReviewEditor.issuePanel.emptyFilteredDescription')}
          </p>
        </section>
      ) : null}

      <section className={sectionClass}>
        <div className="flex flex-wrap gap-2">
          {renderBadge(`${t('aiReviewEditor.issueStatus.open')}: ${issueSummary.statusCounts.open}`, 'rose')}
          {renderBadge(`${t('aiReviewEditor.issueStatus.dismissed')}: ${issueSummary.statusCounts.dismissed}`)}
          {renderBadge(`${t('aiReviewEditor.issueStatus.resolved_manual')}: ${issueSummary.statusCounts.resolved_manual}`, 'teal')}
          {renderBadge(`${t('aiReviewEditor.issueStatus.rewrite_ready')}: ${issueSummary.statusCounts.rewrite_ready}`, 'amber')}
          {renderBadge(`${t('aiReviewEditor.issueStatus.applied')}: ${issueSummary.statusCounts.applied}`, 'teal')}
          {renderBadge(`${t('aiReviewEditor.severity.high')}: ${issueSummary.severityCounts.high}`, 'rose')}
          {renderBadge(`${t('aiReviewEditor.severity.medium')}: ${issueSummary.severityCounts.medium}`, 'amber')}
          {renderBadge(`${t('aiReviewEditor.severity.low')}: ${issueSummary.severityCounts.low}`)}
        </div>
      </section>

      <QuickFilterBar
        title={t('aiReviewEditor.filters.quickTitle')}
        items={AI_REVIEW_ISSUE_QUICK_FILTERS.map((filter) => ({
          label: t(`aiReviewEditor.filters.quick.${filter}`),
          isActive: quickFilter === filter,
          onClick: () =>
            updateSearch({
              issue_filter: filter,
              issue: undefined,
              block: undefined,
            }),
        }))}
        onReset={() =>
          updateSearch({
            issue_filter: 'all',
            issue_type: undefined,
            issue: undefined,
            block: undefined,
          })
        }
      />

      <FilterPanel
        title={t('aiReviewEditor.filters.title')}
        description={t('aiReviewEditor.filters.description')}
        onReset={() => updateSearch({ issue_type: undefined, issue: undefined, block: undefined })}
        bodyClassName="grid gap-3 md:grid-cols-1 xl:grid-cols-1"
        defaultOpen={Boolean(issueTypeFilter)}
      >
        <label className={fieldLabelClass}>
          <span>{t('aiReviewEditor.filters.issueType')}</span>
          <select
            value={issueTypeFilter ?? ''}
            onChange={(event) =>
              updateSearch({
                issue_type: event.target.value || undefined,
                issue: undefined,
                block: undefined,
              })
            }
            className={fieldControlClass}
          >
            <option value="">{t('aiReviewEditor.filters.allIssueTypes')}</option>
            {AI_REVIEW_ISSUE_TYPES.map((issueType) => (
              <option key={issueType} value={issueType}>
                {t(`aiReviewEditor.issueType.${issueType}`, {
                  defaultValue: humanizeAiReviewValue(issueType),
                })}
              </option>
            ))}
          </select>
        </label>
      </FilterPanel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className={surfaceClass}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-stone-950 dark:text-slate-50">
                {t('aiReviewEditor.document.canvasTitle')}
              </h2>
              <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                {t('aiReviewEditor.document.canvasDescription')}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {renderBadge(
                t(`aiReviewEditor.documentStatus.${document.status}`),
                documentStatusTone(document.status),
              )}
              {renderBadge(
                `${t('aiReviewEditor.document.context.filteredIssues')}: ${visibleIssues.length}`,
                visibleIssues.length > 0 ? 'amber' : 'stone',
              )}
            </div>
          </div>

          {blocks.length === 1 ? (
            <div className="mt-4 rounded-2xl border border-stone-300 bg-stone-50/90 p-3 text-sm text-stone-700 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-200">
              {t('aiReviewEditor.document.singleBlockNotice')}
            </div>
          ) : null}

          {blocks.length === 0 ? (
            <div className="mt-6">
              <EmptyState
                title={t('aiReviewEditor.document.noBlocksTitle')}
                description={t('aiReviewEditor.document.noBlocksDescription')}
              />
            </div>
          ) : (
            <div className="mt-6 space-y-4">
              {blocks.map((block) => {
                const blockIssues = issuesByBlock[block.block_key] ?? []
                const topSeverity = getHighestSeverity(blockIssues)
                const blockTone =
                  topSeverity === 'high' ? 'rose' : topSeverity === 'medium' ? 'amber' : 'stone'
                const isEditingBlock = editingBlockKey === block.block_key
                const isInsertBeforeTarget =
                  insertDraft?.targetBlockKey === block.block_key && insertDraft.position === 'before'
                const isInsertAfterTarget =
                  insertDraft?.targetBlockKey === block.block_key && insertDraft.position === 'after'
                const isInsertTarget = isInsertBeforeTarget || isInsertAfterTarget
                const normalizedEditingText = isEditingBlock ? normalizeInlineEditText(editingText) : ''
                const saveDisabled =
                  !isEditingBlock ||
                  normalizedEditingText.length === 0 ||
                  normalizedEditingText === block.text_content
                const blockActionsDisabled = Boolean(editingBlockKey || insertDraft) || isBlockMutationPending

                function renderInsertComposer(position: 'before' | 'after') {
                  if (!insertDraft || insertDraft.targetBlockKey !== block.block_key || insertDraft.position !== position) {
                    return null
                  }

                  return (
                    <div
                      className="grid gap-3 md:grid-cols-[56px_minmax(0,1fr)]"
                      data-testid={`ai-review-insert-${position}-${block.block_key}`}
                    >
                      <div className="flex justify-end pt-1">
                        <span className="min-h-10 min-w-10" aria-hidden="true" />
                      </div>
                      <div className="rounded-[28px] border border-teal-300 bg-teal-50/70 px-5 py-4 dark:border-teal-700 dark:bg-teal-950/20">
                        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                          <span>{block.block_key}</span>
                          {renderBadge(t('aiReviewEditor.document.insertingBadge'), 'teal')}
                          {renderBadge(
                            position === 'before'
                              ? t('aiReviewEditor.actions.addBlockBefore')
                              : t('aiReviewEditor.actions.addBlockAfter'),
                          )}
                        </div>
                        <BlockInsertComposer
                          draft={insertDraft}
                          onTypeChange={(nextType) =>
                            setInsertDraft((current) =>
                              current
                                ? {
                                    ...current,
                                    blockType: nextType,
                                    blockLevel: nextType === 'heading' ? current.blockLevel || 2 : current.blockLevel,
                                  }
                                : current,
                            )
                          }
                          onLevelChange={(nextLevel) =>
                            setInsertDraft((current) => (current ? { ...current, blockLevel: nextLevel } : current))
                          }
                          onTextChange={(nextValue) =>
                            setInsertDraft((current) => (current ? { ...current, textContent: nextValue } : current))
                          }
                          onSave={() => void runAction(() => saveInsertedBlock())}
                          onCancel={cancelInsertBlock}
                          isSaving={insertBlockMutation.isPending}
                          saveDisabled={insertSaveDisabled}
                          fieldLabelClass={fieldLabelClass}
                          fieldControlClass={fieldControlClass}
                          actionClass={actionClass}
                          primaryActionClass={primaryActionClass}
                        />
                      </div>
                    </div>
                  )
                }

                return (
                  <div key={block.id} className="space-y-3">
                    {renderInsertComposer('before')}
                    <div
                      className="grid gap-3 md:grid-cols-[56px_minmax(0,1fr)]"
                      data-testid={`ai-review-block-${block.block_key}`}
                    >
                      <div className="flex justify-end pt-1">
                        {blockIssues.length > 0 ? (
                          <button
                            type="button"
                            onClick={() => selectIssue(blockIssues[0])}
                            className={`inline-flex min-h-10 min-w-10 items-center justify-center rounded-full border text-sm font-semibold ${toneClass(blockTone)}`}
                            data-testid={`ai-review-block-marker-${block.block_key}`}
                            aria-label={t('aiReviewEditor.document.blockMarkerAria', {
                              count: blockIssues.length,
                              blockKey: block.block_key,
                            })}
                          >
                            {blockIssues.length}
                          </button>
                        ) : (
                          <span className="min-h-10 min-w-10" aria-hidden="true" />
                        )}
                      </div>
                      <div
                        className={`rounded-[28px] border px-5 py-4 ${
                          isEditingBlock
                            ? 'border-amber-300 bg-amber-50/70 dark:border-amber-700 dark:bg-amber-950/20'
                            : isInsertTarget
                              ? 'border-teal-300 bg-teal-50/70 dark:border-teal-700 dark:bg-teal-950/20'
                              : selectedBlock?.block_key === block.block_key
                                ? 'border-teal-400 bg-teal-50/70 dark:border-teal-500 dark:bg-teal-950/30'
                                : blockIssues.length > 0
                                  ? 'border-stone-300 bg-white/90 dark:border-slate-700 dark:bg-slate-950/80'
                                  : 'border-stone-200 bg-stone-50/80 dark:border-slate-800 dark:bg-slate-950/60'
                        }`}
                      >
                        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                          <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                            <span>{block.block_key}</span>
                            {block.context_path ? <span>{block.context_path}</span> : null}
                            {isEditingBlock ? renderBadge(t('aiReviewEditor.document.editingBadge'), 'amber') : null}
                            {isInsertTarget ? renderBadge(t('aiReviewEditor.document.insertingBadge'), 'teal') : null}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => startEditingBlock(block, blockIssues)}
                              disabled={blockActionsDisabled}
                              className={actionClass}
                            >
                              {t('aiReviewEditor.actions.editBlock')}
                            </button>
                            <button
                              type="button"
                              onClick={() => startInsertBlock(block, 'before')}
                              disabled={blockActionsDisabled}
                              className={actionClass}
                            >
                              {t('aiReviewEditor.actions.addBlockBefore')}
                            </button>
                            <button
                              type="button"
                              onClick={() => startInsertBlock(block, 'after')}
                              disabled={blockActionsDisabled}
                              className={actionClass}
                            >
                              {t('aiReviewEditor.actions.addBlockAfter')}
                            </button>
                            <button
                              type="button"
                              onClick={() => void runAction(() => deleteBlock(block))}
                              disabled={blockActionsDisabled || blocks.length <= 1}
                              className={actionClass}
                            >
                              {t('aiReviewEditor.actions.deleteBlock')}
                            </button>
                          </div>
                        </div>
                        {isEditingBlock ? (
                          <BlockInlineEditor
                            block={block}
                            editingText={editingText}
                            onChange={setEditingText}
                            onSave={() => void runAction(() => saveBlockEdit(block))}
                            onCancel={cancelBlockEdit}
                            isSaving={updateBlockMutation.isPending}
                            saveDisabled={saveDisabled}
                            fieldLabelClass={fieldLabelClass}
                            fieldControlClass={fieldControlClass}
                            actionClass={actionClass}
                            primaryActionClass={primaryActionClass}
                            helperLabel={t('aiReviewEditor.document.editFieldLabel')}
                            saveLabel={t('aiReviewEditor.actions.saveBlock')}
                            cancelLabel={t('aiReviewEditor.actions.cancelEdit')}
                          />
                        ) : (
                          <BlockBody block={block} />
                        )}
                      </div>
                    </div>
                    {renderInsertComposer('after')}
                  </div>
                )
              })}
            </div>
          )}
        </section>

        <aside className="space-y-6 xl:sticky xl:top-6 xl:self-start">
          <section className={sectionClass}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
                  {t('aiReviewEditor.issuePanel.title')}
                </h2>
                <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                  {t('aiReviewEditor.issuePanel.description')}
                </p>
              </div>
              {selectedBlock ? renderBadge(selectedBlock.block_key) : null}
            </div>

            {!selectedBlock || selectedBlockIssues.length === 0 ? (
              <div className="mt-4">
                <EmptyState
                  title={issuePanelEmptyState.title}
                  description={issuePanelEmptyState.description}
                />
              </div>
            ) : (
              <div className="mt-4 space-y-4">
                <div className={panelClass}>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                    {t('aiReviewEditor.issuePanel.blockContext')}
                  </p>
                  {selectedBlock.context_path ? (
                    <p className="mt-2 text-sm text-stone-700 dark:text-slate-200">
                      {selectedBlock.context_path}
                    </p>
                  ) : null}
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-stone-700 dark:text-slate-200">
                    {selectedBlock.text_content}
                  </p>
                </div>

                {selectedBlockIssues.map((issue) => {
                  const isSelected = selectedIssue?.id === issue.id
                  const rewriteIsStale = isSelected && isRewriteRunStale(latestCompletedRewriteRun, selectedBlock)
                  const latestRewriteAttemptPending =
                    isSelected &&
                    (latestRewriteRun?.status === 'queued' ||
                      latestRewriteRun?.status === 'running' ||
                      issue.status === 'rewrite_requested')
                  const showPreview = isSelected && Boolean(rewritePreviewText) && issue.status === 'rewrite_ready'
                  const issueCanApply =
                    isSelected &&
                    issue.status === 'rewrite_ready' &&
                    !reviewNeedsRefresh &&
                    !rewriteIsStale &&
                    latestCompletedRewriteRun?.status === 'completed' &&
                    Boolean(latestCompletedRewriteRun.result_text)
                  const issueActionsDisabled = Boolean(issueActionsLockedReason)
                  const latestRewriteAttemptFailed = isSelected && latestRewriteRun?.status === 'failed'

                  return (
                    <article
                      key={issue.id}
                      className={`rounded-[28px] border p-4 shadow-sm ${
                        isSelected
                          ? 'border-teal-300 bg-white dark:border-teal-700 dark:bg-slate-950/85'
                          : 'border-stone-200 bg-stone-50/80 dark:border-slate-800 dark:bg-slate-900/70'
                      }`}
                      data-testid={`ai-review-issue-${issue.id}`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-2">
                          <div className="flex flex-wrap gap-2">
                            {renderBadge(
                              t(`aiReviewEditor.issueStatus.${issue.status}`),
                              issueStatusTone(issue.status),
                            )}
                            {renderBadge(
                              t(`aiReviewEditor.severity.${issue.severity}`),
                              issueSeverityTone(issue.severity),
                            )}
                            {renderBadge(
                              t(`aiReviewEditor.issueType.${issue.issue_type}`, {
                                defaultValue: humanizeAiReviewValue(issue.issue_type),
                              }),
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => selectIssue(issue)}
                            className="text-left text-sm font-semibold text-stone-950 hover:text-teal-700 dark:text-slate-50 dark:hover:text-teal-300"
                          >
                            {issue.message}
                          </button>
                        </div>
                        {!isSelected ? (
                          <button type="button" onClick={() => selectIssue(issue)} className={actionClass}>
                            {t('aiReviewEditor.issue.select')}
                          </button>
                        ) : null}
                      </div>

                      {issue.reason ? (
                        <p className="mt-3 text-sm leading-6 text-stone-600 dark:text-slate-300">{issue.reason}</p>
                      ) : null}
                      {issue.replacement_instruction ? (
                        <p className="mt-3 text-sm text-stone-500 dark:text-slate-400">
                          {issue.replacement_instruction}
                        </p>
                      ) : null}
                      {issue.dismiss_reason ? (
                        <p className="mt-3 text-sm text-stone-500 dark:text-slate-400">
                          {t('aiReviewEditor.issue.dismissReason')}: {issue.dismiss_reason}
                        </p>
                      ) : null}
                      {issue.resolution_note ? (
                        <p className="mt-3 text-sm text-stone-500 dark:text-slate-400">
                          {t('aiReviewEditor.issue.resolutionNote')}: {issue.resolution_note}
                        </p>
                      ) : null}

                      {isSelected && rewriteRunsQuery.isError ? (
                        <p className="mt-3 text-sm text-rose-700 dark:text-rose-200">
                          {getUiErrorMessage(rewriteRunsQuery.error, t)}
                        </p>
                      ) : null}

                      {latestRewriteAttemptPending ? (
                        <div className="mt-3 rounded-2xl border border-stone-300 bg-stone-50/90 p-3 text-sm text-stone-700 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-200">
                          <p className="font-semibold">{t('aiReviewEditor.document.rewritePendingTitle')}</p>
                          <p className="mt-1">{t('aiReviewEditor.document.rewritePendingDescription')}</p>
                        </div>
                      ) : null}

                      {latestRewriteAttemptFailed ? (
                        <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50/90 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
                          <p className="font-semibold">{t('aiReviewEditor.document.rewriteFailedTitle')}</p>
                          <p className="mt-1">
                            {latestRewriteRun?.error_message ?? t('aiReviewEditor.document.rewriteFailed')}
                          </p>
                        </div>
                      ) : null}

                      {showPreview ? (
                        <div className={`${panelClass} mt-3 space-y-3`} data-testid="ai-review-rewrite-preview">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                              {t('aiReviewEditor.rewrite.before')}
                            </p>
                            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-stone-700 dark:text-slate-200">
                              {selectedBlock.text_content}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500 dark:text-slate-400">
                              {t('aiReviewEditor.rewrite.after')}
                            </p>
                            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-stone-700 dark:text-slate-200">
                              {rewritePreviewText}
                            </p>
                          </div>
                        </div>
                      ) : null}

                      {isSelected && rewriteIsStale ? (
                        <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50/90 p-3 text-sm text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                          <p className="font-semibold">{t('aiReviewEditor.rewrite.staleTitle')}</p>
                          <p className="mt-1">{t('aiReviewEditor.rewrite.staleDescription')}</p>
                        </div>
                      ) : null}

                      {isSelected ? (
                        <div className="mt-4 space-y-3">
                          {issueActionsDisabled ? (
                            <div className="rounded-2xl border border-amber-200 bg-amber-50/90 p-3 text-sm text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                              <p className="font-semibold">{t('aiReviewEditor.issuePanel.actionsLockedTitle')}</p>
                              <p className="mt-1">{issueActionsLockedReason}</p>
                            </div>
                          ) : null}
                          <div className="flex flex-wrap gap-2">
                          {isDismissableStatus(issue.status) ? (
                            <button
                              type="button"
                              onClick={() => void runAction(() => dismissIssue(issue.id))}
                              disabled={dismissIssueMutation.isPending || issueActionsDisabled}
                              className={actionClass}
                            >
                              {t('aiReviewEditor.actions.dismiss')}
                            </button>
                          ) : null}
                          {isManualResolvableStatus(issue.status) ? (
                            <button
                              type="button"
                              onClick={() => void runAction(() => resolveIssueManually(issue.id))}
                              disabled={resolveManualMutation.isPending || issueActionsDisabled}
                              className={actionClass}
                            >
                              {t('aiReviewEditor.actions.resolveManual')}
                            </button>
                          ) : null}
                          {isRewriteRequestableStatus(issue.status) ? (
                            <button
                              type="button"
                              onClick={() => void runAction(() => requestRewrite(issue.id))}
                              disabled={requestRewriteMutation.isPending || issueActionsDisabled}
                              className={actionClass}
                            >
                              {t('aiReviewEditor.actions.requestRewrite')}
                            </button>
                          ) : null}
                          {issueCanApply ? (
                            <button
                              type="button"
                              onClick={() =>
                                latestCompletedRewriteRun
                                  ? void runAction(() =>
                                      applyRewrite(issue.id, latestCompletedRewriteRun.id),
                                    )
                                  : undefined
                              }
                              disabled={!canApplyRewrite || applyRewriteMutation.isPending || issueActionsDisabled}
                              className={primaryActionClass}
                            >
                              {t('aiReviewEditor.actions.applyRewrite')}
                            </button>
                          ) : null}
                          </div>
                        </div>
                      ) : null}
                    </article>
                  )
                })}
              </div>
            )}
          </section>

          {reviewRuns.length > 0 ? (
            <section className={sectionClass}>
              <h2 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
                {t('aiReviewEditor.runs.title')}
              </h2>
              <div className="mt-4 space-y-3">
                {reviewRuns.slice(0, 5).map((run) => (
                  <article key={run.id} className={panelClass}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap gap-2">
                        {renderBadge(
                          t(`aiReviewEditor.reviewRunStatus.${run.status}`),
                          reviewRunTone(run.status),
                        )}
                        {renderBadge(
                          t(`aiReviewEditor.reviewMode.${run.review_mode}`, {
                            defaultValue: humanizeAiReviewValue(run.review_mode),
                          }),
                        )}
                        {renderBadge(
                          run.matches_current_document
                            ? t('aiReviewEditor.document.reviewScopeCurrent')
                            : t('aiReviewEditor.document.reviewScopeStale'),
                          run.matches_current_document ? 'teal' : 'amber',
                        )}
                      </div>
                      <span className="text-xs text-stone-500 dark:text-slate-400">#{run.id}</span>
                    </div>
                    <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                      {t('aiReviewEditor.runs.issueCount')}: {run.issue_count}
                    </p>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      {t('aiReviewEditor.runs.finishedAt')}: {formatDateTime(run.finished_at ?? run.created_at)}
                    </p>
                    {run.status === 'failed' && run.error_message ? (
                      <p className="mt-2 text-sm text-rose-700 dark:text-rose-200">{run.error_message}</p>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          <AIReviewEditorVersionHistorySection
            versions={versions}
            selectedVersionId={selectedVersion?.id}
            onSelectVersion={(versionId) =>
              updateSearch({
                version: versionId,
              })
            }
          />

          <section className={sectionClass}>
            <h2 className="text-lg font-semibold text-stone-950 dark:text-slate-50">
              {t('aiReviewEditor.document.metaTitle')}
            </h2>
            <div className="mt-4 grid gap-2 text-sm text-stone-600 dark:text-slate-300">
              <p>
                {t('aiReviewEditor.document.metaUpdatedAt')}:{' '}
                <span className="font-medium text-stone-900 dark:text-slate-100">
                  {formatDateTime(document.updated_at)}
                </span>
              </p>
              <p>
                {t('aiReviewEditor.document.metaSourceFormat')}:{' '}
                <span className="font-medium text-stone-900 dark:text-slate-100">
                  {document.source_format}
                </span>
              </p>
              <p>
                {t('aiReviewEditor.document.metaReviewRuns')}:{' '}
                <span className="font-medium text-stone-900 dark:text-slate-100">
                  {summaryQuery.data.review_run_count}
                </span>
              </p>
              <p>
                {t('aiReviewEditor.document.metaCurrentVersion')}:{' '}
                <span className="font-medium text-stone-900 dark:text-slate-100">
                  {currentVersion ? `v${currentVersion.version_no}` : t('aiReviewEditor.common.none')}
                </span>
              </p>
              <p>
                {t('aiReviewEditor.document.metaLatestReviewScope')}:{' '}
                <span className="font-medium text-stone-900 dark:text-slate-100">
                  {summaryQuery.data.review_run_count === 0
                    ? t('aiReviewEditor.common.none')
                    : summaryQuery.data.latest_review_matches_current_document === false
                      ? t('aiReviewEditor.document.reviewScopeStale')
                      : t('aiReviewEditor.document.reviewScopeCurrent')}
                </span>
              </p>
              <p>
                {t('aiReviewEditor.document.metaCanonicalSource')}:{' '}
                <span className="font-medium text-stone-900 dark:text-slate-100">
                  {t('aiReviewEditor.document.canonicalSourceValue')}
                </span>
              </p>
            </div>
            <div className="mt-4">
              <Link
                to={buildSiteAiReviewEditorDocumentsPath(site.id, {
                  activeCrawlId,
                  baselineCrawlId,
                })}
                className={actionClass}
              >
                {t('aiReviewEditor.actions.backToDocuments')}
              </Link>
            </div>
          </section>
        </aside>
      </div>

      {selectedVersion ? (
        <AIReviewEditorDiffPreviewSection
          selectedVersion={selectedVersion}
          diff={versionDiffQuery.data}
          isLoading={versionDiffQuery.isLoading}
          errorMessage={versionDiffQuery.isError ? getUiErrorMessage(versionDiffQuery.error, t) : null}
          onRestore={
            selectedVersion.is_current
              ? null
              : () => void runAction(() => restoreVersion(selectedVersion.id))
          }
          restoreDisabled={
            restoreVersionMutation.isPending || Boolean(editingBlockKey || insertDraft) || isBlockMutationPending
          }
        />
      ) : null}
    </div>
  )
}
