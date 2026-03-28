import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import i18n from '../../i18n'
import { createTestQueryClient, jsonResponse, setTestLanguage } from '../../test/testUtils'
import type {
  EditorDocument,
  EditorDocumentBlock,
  EditorReviewIssue,
  EditorReviewRun,
  EditorDocumentVersion,
  EditorRewriteRun,
} from '../../types/api'
import { SiteWorkspaceLayout } from '../sites/SiteWorkspaceLayout'
import { AIReviewEditorDocumentPage } from './AIReviewEditorDocumentPage'
import { AIReviewEditorDocumentsPage } from './AIReviewEditorDocumentsPage'
import { AIReviewEditorNewDocumentPage } from './AIReviewEditorNewDocumentPage'

afterEach(() => {
  vi.restoreAllMocks()
})

beforeEach(async () => {
  await setTestLanguage('en')
})

function buildSitePayload() {
  return {
    id: 5,
    domain: 'example.com',
    root_url: 'https://example.com',
    created_at: '2026-03-26T10:00:00Z',
    selected_gsc_property_uri: null,
    selected_gsc_property_permission_level: null,
    summary: {
      total_crawls: 1,
      pending_crawls: 0,
      running_crawls: 0,
      finished_crawls: 1,
      failed_crawls: 0,
      stopped_crawls: 0,
      first_crawl_at: '2026-03-25T10:00:00Z',
      last_crawl_at: '2026-03-26T10:00:00Z',
    },
    active_crawl_id: 11,
    baseline_crawl_id: null,
    active_crawl: {
      id: 11,
      site_id: 5,
      status: 'finished',
      created_at: '2026-03-26T10:00:00Z',
      started_at: '2026-03-26T10:01:00Z',
      finished_at: '2026-03-26T10:10:00Z',
      settings_json: {
        start_url: 'https://example.com',
      },
      stats_json: {},
      summary_counts: {
        total_pages: 3,
        total_links: 3,
        total_internal_links: 3,
        total_external_links: 0,
        pages_missing_title: 0,
        pages_missing_meta_description: 0,
        pages_missing_h1: 0,
        pages_non_indexable_like: 0,
        rendered_pages: 0,
        js_heavy_like_pages: 0,
        pages_with_render_errors: 0,
        pages_with_schema: 0,
        pages_with_x_robots_tag: 0,
        pages_with_gsc_28d: 0,
        pages_with_gsc_90d: 0,
        gsc_opportunities_28d: 0,
        gsc_opportunities_90d: 0,
        broken_internal_links: 0,
        redirecting_internal_links: 0,
      },
      progress: {
        visited_pages: 3,
        queued_urls: 0,
        discovered_links: 3,
        internal_links: 3,
        external_links: 0,
        errors_count: 0,
      },
    },
    baseline_crawl: null,
    crawl_history: [
      {
        id: 11,
        site_id: 5,
        status: 'finished',
        root_url: 'https://example.com',
        created_at: '2026-03-26T10:00:00Z',
        started_at: '2026-03-26T10:01:00Z',
        finished_at: '2026-03-26T10:10:00Z',
        total_pages: 3,
        total_internal_links: 3,
        total_external_links: 0,
        total_errors: 0,
      },
    ],
  }
}

function buildMockContentHash(
  block: Pick<EditorDocumentBlock, 'block_key' | 'block_type' | 'block_level' | 'text_content' | 'context_path'>,
) {
  return [
    'hash',
    block.block_key,
    block.block_type,
    String(block.block_level ?? 'na'),
    (block.context_path ?? 'root').replace(/\s+/g, '_'),
    block.text_content.replace(/\s+/g, '_'),
  ].join('|')
}

function createAiReviewState() {
  const document: EditorDocument = {
    id: 12,
    site_id: 5,
    title: 'Pricing FAQ',
    document_type: 'landing_page',
    source_format: 'html',
    source_content:
      '<h1>Pricing guide</h1>\n<p>TODO add verified pricing details.</p>\n<p>All subscriptions renew monthly.</p>',
    normalized_content: 'Pricing guide\n\nTODO add verified pricing details.\n\nAll subscriptions renew monthly.',
    topic_brief_json: {
      topic: 'Pricing',
    },
    facts_context_json: {
      plans: ['Starter', 'Pro'],
    },
    status: 'parsed',
    active_block_count: 3,
    created_at: '2026-03-26T10:00:00Z',
    updated_at: '2026-03-26T10:10:00Z',
  }

  const blocks: EditorDocumentBlock[] = [
    {
      id: 1,
      document_id: 12,
      block_key: 'h1',
      block_type: 'heading',
      block_level: 1,
      parent_block_key: null,
      position_index: 0,
      text_content: 'Pricing guide',
      html_content: '<h1>Pricing guide</h1>',
      context_path: 'Pricing guide',
      content_hash: '',
      is_active: true,
      created_at: '2026-03-26T10:00:00Z',
      updated_at: '2026-03-26T10:10:00Z',
    },
    {
      id: 2,
      document_id: 12,
      block_key: 'p1',
      block_type: 'paragraph',
      block_level: null,
      parent_block_key: 'h1',
      position_index: 1,
      text_content: 'TODO add verified pricing details.',
      html_content: '<p>TODO add verified pricing details.</p>',
      context_path: 'Pricing guide',
      content_hash: '',
      is_active: true,
      created_at: '2026-03-26T10:00:00Z',
      updated_at: '2026-03-26T10:10:00Z',
    },
    {
      id: 3,
      document_id: 12,
      block_key: 'p2',
      block_type: 'paragraph',
      block_level: null,
      parent_block_key: 'h1',
      position_index: 2,
      text_content: 'All subscriptions renew monthly.',
      html_content: '<p>All subscriptions renew monthly.</p>',
      context_path: 'Pricing guide',
      content_hash: '',
      is_active: true,
      created_at: '2026-03-26T10:00:00Z',
      updated_at: '2026-03-26T10:10:00Z',
    },
  ]

  const issues: EditorReviewIssue[] = [
    {
      id: 101,
      review_run_id: 201,
      document_id: 12,
      block_key: 'p1',
      issue_type: 'todo_marker',
      severity: 'high',
      confidence: 0.96,
      message: 'Contains TODO marker.',
      reason: 'TODO markers should not ship in a reviewed document.',
      replacement_instruction: 'Rewrite this paragraph without TODO phrasing.',
      replacement_candidate_text: null,
      status: 'open',
      dismiss_reason: null,
      resolution_note: null,
      matches_current_block: true,
      created_at: '2026-03-26T10:11:00Z',
      updated_at: '2026-03-26T10:11:00Z',
      resolved_at: null,
    },
    {
      id: 102,
      review_run_id: 201,
      document_id: 12,
      block_key: 'h1',
      issue_type: 'weak_heading',
      severity: 'medium',
      confidence: 0.78,
      message: 'Heading is too generic.',
      reason: 'The heading does not express the page angle clearly enough.',
      replacement_instruction: null,
      replacement_candidate_text: null,
      status: 'open',
      dismiss_reason: null,
      resolution_note: null,
      matches_current_block: true,
      created_at: '2026-03-26T10:11:00Z',
      updated_at: '2026-03-26T10:11:00Z',
      resolved_at: null,
    },
  ]

  const reviewRuns: EditorReviewRun[] = [
    {
      id: 201,
      document_id: 12,
      document_version_hash: 'doc-v1',
      review_mode: 'standard',
      status: 'completed',
      model_name: 'gpt-review',
      prompt_version: 'editor-review-v1',
      schema_version: 'editor-review-v1',
      input_hash: 'input-v1',
      issue_count: 2,
      issue_block_count: 2,
      severity_counts: {
        low: 0,
        medium: 1,
        high: 1,
      },
      started_at: '2026-03-26T10:10:30Z',
      finished_at: '2026-03-26T10:11:00Z',
      error_code: null,
      error_message: null,
      matches_current_document: true,
      created_at: '2026-03-26T10:10:30Z',
      updated_at: '2026-03-26T10:11:00Z',
    },
  ]

  const versions: EditorDocumentVersion[] = [
    {
      id: 401,
      document_id: 12,
      version_no: 1,
      source_of_change: 'document_parse',
      source_description: 'Created a parsed document snapshot.',
      version_hash: 'version-001',
      block_count: blocks.length,
      metadata_json: {
        blocks_created_count: blocks.length,
      },
      created_at: '2026-03-26T10:10:00Z',
      is_current: true,
      snapshot: buildVersionSnapshot(document, blocks),
    },
  ]

  blocks.forEach((block) => {
    block.content_hash = buildMockContentHash(block)
  })

  const reviewedBlockHashesByKey = Object.fromEntries(blocks.map((block) => [block.block_key, block.content_hash]))

  return {
    site: buildSitePayload(),
    document,
    createdDocument: null as EditorDocument | null,
    blocks,
    issues,
    reviewRuns,
    versions,
    reviewedBlockHashesByKey,
    rewriteRunsByIssue: new Map<number, EditorRewriteRun[]>(),
    nextDocumentId: 13,
    nextRewriteRunId: 301,
    nextVersionId: 402,
    nextBlockId: 4,
    nextBlockOrdinal: 2,
  }
}

function buildVersionSnapshot(document: EditorDocument, blocks: EditorDocumentBlock[]) {
  return {
    title: document.title,
    document_type: document.document_type,
    source_format: document.source_format,
    source_content: document.source_content,
    normalized_content: document.normalized_content,
    topic_brief_json: document.topic_brief_json,
    facts_context_json: document.facts_context_json,
    status: document.status,
    blocks: blocks.map((block) => ({
      block_key: block.block_key,
      block_type: block.block_type,
      block_level: block.block_level,
      parent_block_key: block.parent_block_key,
      position_index: block.position_index,
      text_content: block.text_content,
      html_content: block.html_content,
      context_path: block.context_path,
      content_hash: block.content_hash,
    })),
  }
}

function renderBlockHtml(block: EditorDocumentBlock) {
  if (block.block_type === 'heading') {
    const level = Math.min(6, Math.max(1, block.block_level ?? 2))
    return `<h${level}>${block.text_content}</h${level}>`
  }
  if (block.block_type === 'list_item') {
    return `<li>${block.text_content}</li>`
  }
  return `<p>${block.text_content}</p>`
}

function buildNextMockBlockKey(
  state: ReturnType<typeof createAiReviewState>,
  blockType: EditorDocumentBlock['block_type'],
  _blockLevel: number | null,
) {
  state.nextBlockOrdinal += 1
  if (blockType === 'heading') {
    return `h${state.nextBlockOrdinal}`
  }
  if (blockType === 'list_item') {
    return `li${state.nextBlockOrdinal}`
  }
  return `p${state.nextBlockOrdinal}`
}

function syncDocumentFromBlocks(state: ReturnType<typeof createAiReviewState>, updatedAt: string) {
  const headingStack: Array<{ block_key: string; block_level: number; text_content: string }> = []
  state.blocks = state.blocks.map((block, index) => {
    let parent_block_key: string | null = null
    let context_path: string | null = null
    if (block.block_type === 'heading') {
      const blockLevel = block.block_level ?? 2
      while (headingStack.length > 0 && headingStack[headingStack.length - 1]!.block_level >= blockLevel) {
        headingStack.pop()
      }
      parent_block_key = headingStack[headingStack.length - 1]?.block_key ?? null
      context_path = [...headingStack.map((item) => item.text_content), block.text_content].join(' > ')
      headingStack.push({
        block_key: block.block_key,
        block_level: blockLevel,
        text_content: block.text_content,
      })
    } else {
      parent_block_key = headingStack[headingStack.length - 1]?.block_key ?? null
      context_path = headingStack.map((item) => item.text_content).join(' > ') || null
    }

    return {
      ...block,
      position_index: index,
      parent_block_key,
      context_path,
      html_content: renderBlockHtml(block),
      content_hash: buildMockContentHash({
        block_key: block.block_key,
        block_type: block.block_type,
        block_level: block.block_level,
        text_content: block.text_content,
        context_path,
      }),
      updated_at: updatedAt,
    }
  })
  state.document.updated_at = updatedAt
  state.document.source_content = state.blocks
    .map((block) => renderBlockHtml(block))
    .join('\n')
    .replace(/<li>.*?<\/li>(?:\n<li>.*?<\/li>)*/g, (listItems) => `<ul>${listItems.replace(/\n/g, '')}</ul>`)
  state.document.normalized_content = state.blocks.map((block) => block.text_content).join('\n\n')
}

function reviewSnapshotMatchesCurrentDocument(state: ReturnType<typeof createAiReviewState>) {
  const reviewedEntries = Object.entries(state.reviewedBlockHashesByKey)
  if (reviewedEntries.length !== state.blocks.length) {
    return false
  }
  return reviewedEntries.every(([blockKey, contentHash]) => {
    const currentBlock = state.blocks.find((candidate) => candidate.block_key === blockKey)
    return currentBlock?.content_hash === contentHash
  })
}

function markCurrentVersion(state: ReturnType<typeof createAiReviewState>, currentVersionId: number) {
  state.versions = state.versions.map((version) => ({
    ...version,
    is_current: version.id === currentVersionId,
  }))
}

function markReviewRunsStale(state: ReturnType<typeof createAiReviewState>) {
  const matchesCurrentDocument = reviewSnapshotMatchesCurrentDocument(state)
  state.issues = state.issues.map((issue) => {
    const currentBlock = state.blocks.find((candidate) => candidate.block_key === issue.block_key)
    return {
      ...issue,
      matches_current_block: currentBlock?.content_hash === state.reviewedBlockHashesByKey[issue.block_key],
    }
  })
  state.reviewRuns = state.reviewRuns.map((run) => ({
    ...run,
    matches_current_document: matchesCurrentDocument,
  }))
  state.rewriteRunsByIssue = new Map(
    Array.from(state.rewriteRunsByIssue.entries()).map(([issueId, runs]) => [
      issueId,
      runs.map((run) => ({
        ...run,
        matches_current_document: matchesCurrentDocument,
        matches_current_block:
          (state.blocks.find((candidate) => candidate.block_key === run.block_key)?.content_hash ?? null) ===
          (run.source_block_content_hash ?? null),
        is_stale:
          run.status !== 'applied' &&
          (state.blocks.find((candidate) => candidate.block_key === run.block_key)?.content_hash ?? null) !==
            (run.source_block_content_hash ?? null),
      })),
    ]),
  )
}

function pushCurrentVersion(
  state: ReturnType<typeof createAiReviewState>,
  sourceOfChange: EditorDocumentVersion['source_of_change'],
  sourceDescription: string,
  createdAt: string,
) {
  const version: EditorDocumentVersion = {
    id: state.nextVersionId,
    document_id: state.document.id,
    version_no: (state.versions[0]?.version_no ?? 0) + 1,
    source_of_change: sourceOfChange,
    source_description: sourceDescription,
    version_hash: `version-${state.nextVersionId}`,
    block_count: state.blocks.length,
    metadata_json: null,
    created_at: createdAt,
    is_current: true,
    snapshot: buildVersionSnapshot(state.document, state.blocks),
  }

  state.nextVersionId += 1
  state.versions = state.versions.map((existing) => ({ ...existing, is_current: false }))
  state.versions.unshift(version)
  return version
}

function buildSeverityCounts(issues: EditorReviewIssue[]) {
  return issues.reduce(
    (counts, issue) => {
      counts[issue.severity] += 1
      return counts
    },
    {
      low: 0,
      medium: 0,
      high: 0,
    },
  )
}

function buildIssueBlockCount(issues: EditorReviewIssue[]) {
  return new Set(issues.map((issue) => issue.block_key)).size
}

function findMockDocument(state: ReturnType<typeof createAiReviewState>, documentId: number) {
  if (state.document.id === documentId) {
    return state.document
  }
  if (state.createdDocument?.id === documentId) {
    return state.createdDocument
  }
  return null
}

function buildDocumentResponse(
  state: ReturnType<typeof createAiReviewState>,
  document = state.document,
) {
  return {
    ...document,
    active_block_count: document.id === state.document.id ? state.blocks.length : document.active_block_count,
  }
}

function buildDocumentListResponse(state: ReturnType<typeof createAiReviewState>) {
  return {
    site_id: state.document.site_id,
    items: [state.createdDocument, state.document]
      .filter((document): document is EditorDocument => Boolean(document))
      .map((document) => ({
        id: document.id,
        site_id: document.site_id,
        title: document.title,
        document_type: document.document_type,
        source_format: document.source_format,
        status: document.status,
        active_block_count: document.id === state.document.id ? state.blocks.length : document.active_block_count,
        created_at: document.created_at,
        updated_at: document.updated_at,
      })),
  }
}

function buildBlocksResponse(state: ReturnType<typeof createAiReviewState>, documentId = state.document.id) {
  return {
    document_id: documentId,
    items: documentId === state.document.id ? state.blocks : [],
  }
}

function buildIssuesResponse(state: ReturnType<typeof createAiReviewState>, documentId = state.document.id) {
  return {
    document_id: documentId,
    review_run_id: documentId === state.document.id ? state.reviewRuns[0]?.id ?? null : null,
    review_run_status: documentId === state.document.id ? state.reviewRuns[0]?.status ?? null : null,
    review_mode: documentId === state.document.id ? state.reviewRuns[0]?.review_mode ?? 'standard' : null,
    review_matches_current_document:
      documentId === state.document.id ? state.reviewRuns[0]?.matches_current_document ?? null : null,
    items: documentId === state.document.id ? state.issues : [],
  }
}

function buildSummaryResponse(state: ReturnType<typeof createAiReviewState>, documentId = state.document.id) {
  return {
    document_id: documentId,
    review_run_count: documentId === state.document.id ? state.reviewRuns.length : 0,
    latest_review_run_id: documentId === state.document.id ? state.reviewRuns[0]?.id ?? null : null,
    latest_review_run_status: documentId === state.document.id ? state.reviewRuns[0]?.status ?? null : null,
    latest_review_run_finished_at: documentId === state.document.id ? state.reviewRuns[0]?.finished_at ?? null : null,
    latest_review_matches_current_document:
      documentId === state.document.id ? state.reviewRuns[0]?.matches_current_document ?? null : null,
    issue_count: documentId === state.document.id ? state.issues.length : 0,
    issue_block_count: documentId === state.document.id ? buildIssueBlockCount(state.issues) : 0,
    severity_counts: documentId === state.document.id ? buildSeverityCounts(state.issues) : { low: 0, medium: 0, high: 0 },
  }
}

function buildReviewRunsResponse(state: ReturnType<typeof createAiReviewState>, documentId = state.document.id) {
  const severityCounts = buildSeverityCounts(state.issues)
  const issueBlockCount = buildIssueBlockCount(state.issues)

  return {
    document_id: documentId,
    items:
      documentId === state.document.id
        ? state.reviewRuns.map((run) => ({
            ...run,
            issue_count: state.issues.length,
            issue_block_count: issueBlockCount,
            severity_counts: severityCounts,
          }))
        : [],
  }
}

function buildRewriteRunsResponse(state: ReturnType<typeof createAiReviewState>, issueId: number) {
  return {
    document_id: state.document.id,
    review_issue_id: issueId,
    items: state.rewriteRunsByIssue.get(issueId) ?? [],
  }
}

function buildVersionsResponse(state: ReturnType<typeof createAiReviewState>, documentId = state.document.id) {
  return {
    document_id: documentId,
    current_version_id: documentId === state.document.id ? state.versions.find((version) => version.is_current)?.id ?? null : null,
    items: documentId === state.document.id ? state.versions : [],
  }
}

function buildVersionDiffResponse(
  state: ReturnType<typeof createAiReviewState>,
  targetVersionId: number,
  compareToVersionId?: number | null,
) {
  const targetVersion = state.versions.find((version) => version.id === targetVersionId)
  const baseVersion =
    compareToVersionId != null ? state.versions.find((version) => version.id === compareToVersionId) ?? null : null

  if (!targetVersion) {
    throw new Error(`Missing version ${targetVersionId}`)
  }

  const baseBlocks = new Map((baseVersion?.snapshot?.blocks ?? []).map((block) => [block.block_key, block]))
  const targetBlocks = new Map((targetVersion.snapshot?.blocks ?? []).map((block) => [block.block_key, block]))
  const blockKeys = Array.from(new Set([...baseBlocks.keys(), ...targetBlocks.keys()])).sort()
  const blockChanges: Array<{
    block_key: string
    change_type: 'added' | 'removed' | 'changed'
    block_type: string | null
    before_context_path: string | null
    after_context_path: string | null
    before_text: string | null
    after_text: string | null
  }> = []

  blockKeys.forEach((blockKey) => {
    const before = baseBlocks.get(blockKey)
    const after = targetBlocks.get(blockKey)
    if (!before && after) {
      blockChanges.push({
        block_key: blockKey,
        change_type: 'added',
        block_type: after.block_type,
        before_context_path: null,
        after_context_path: after.context_path,
        before_text: null,
        after_text: after.text_content,
      })
      return
    }
    if (before && !after) {
      blockChanges.push({
        block_key: blockKey,
        change_type: 'removed',
        block_type: before.block_type,
        before_context_path: before.context_path,
        after_context_path: null,
        before_text: before.text_content,
        after_text: null,
      })
      return
    }
    if (!before || !after) {
      return
    }
    if (
      before.text_content === after.text_content &&
      before.context_path === after.context_path &&
      before.block_type === after.block_type
    ) {
      return
    }
    blockChanges.push({
      block_key: blockKey,
      change_type: 'changed',
      block_type: after.block_type,
      before_context_path: before.context_path,
      after_context_path: after.context_path,
      before_text: before.text_content,
      after_text: after.text_content,
    })
  })

  return {
    document_id: state.document.id,
    base_version: baseVersion,
    target_version: targetVersion,
    summary: {
      added_blocks: blockChanges.filter((change) => change.change_type === 'added').length,
      removed_blocks: blockChanges.filter((change) => change.change_type === 'removed').length,
      changed_blocks: blockChanges.filter((change) => change.change_type === 'changed').length,
      changed_fields: 0,
    },
    document_changes: [],
    block_changes: blockChanges,
  }
}

function installAiReviewFetchMock(state: ReturnType<typeof createAiReviewState>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const requestUrl =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    const url = new URL(requestUrl)
    const method = (init?.method ?? 'GET').toUpperCase()
    const pathname = url.pathname

    if (method === 'GET' && pathname === '/sites/5') {
      return jsonResponse(state.site)
    }

    if (method === 'GET' && pathname === '/sites/5/ai-review-editor/documents') {
      return jsonResponse(buildDocumentListResponse(state))
    }

    if (method === 'POST' && pathname === '/sites/5/ai-review-editor/documents') {
      const requestBody = init?.body ? JSON.parse(String(init.body)) : {}
      const createdAt = '2026-03-27T09:00:00Z'

      state.createdDocument = {
        id: state.nextDocumentId,
        site_id: 5,
        title: String(requestBody.title ?? ''),
        document_type: String(requestBody.document_type ?? ''),
        source_format: String(requestBody.source_format ?? 'html'),
        source_content: String(requestBody.source_content ?? ''),
        normalized_content: null,
        topic_brief_json: null,
        facts_context_json: null,
        status: 'draft',
        active_block_count: 0,
        created_at: createdAt,
        updated_at: createdAt,
      }
      state.nextDocumentId += 1

      return jsonResponse(state.createdDocument, { status: 201 })
    }

    const documentDetailMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/(\d+)$/)
    if (method === 'GET' && documentDetailMatch) {
      const documentId = Number(documentDetailMatch[1])
      const document = findMockDocument(state, documentId)
      if (!document) {
        return Promise.resolve(jsonResponse({ detail: `Missing document ${documentId}` }, { status: 404 }))
      }
      return jsonResponse(buildDocumentResponse(state, document))
    }

    const blocksMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/(\d+)\/blocks$/)
    if (method === 'GET' && blocksMatch) {
      return jsonResponse(buildBlocksResponse(state, Number(blocksMatch[1])))
    }

    const issuesMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/(\d+)\/issues$/)
    if (method === 'GET' && issuesMatch) {
      return jsonResponse(buildIssuesResponse(state, Number(issuesMatch[1])))
    }

    const summaryMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/(\d+)\/review-summary$/)
    if (method === 'GET' && summaryMatch) {
      return jsonResponse(buildSummaryResponse(state, Number(summaryMatch[1])))
    }

    const reviewRunsMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/(\d+)\/review-runs$/)
    if (method === 'GET' && reviewRunsMatch) {
      return jsonResponse(buildReviewRunsResponse(state, Number(reviewRunsMatch[1])))
    }

    const versionsMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/(\d+)\/versions$/)
    if (method === 'GET' && versionsMatch) {
      return jsonResponse(buildVersionsResponse(state, Number(versionsMatch[1])))
    }

    const versionDetailMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/12\/versions\/(\d+)$/)
    if (method === 'GET' && versionDetailMatch) {
      const version = state.versions.find((candidate) => candidate.id === Number(versionDetailMatch[1]))
      if (!version) {
        return Promise.reject(new Error(`Missing version ${versionDetailMatch[1]}`))
      }
      return jsonResponse(version)
    }

    const versionDiffMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/12\/versions\/(\d+)\/diff$/)
    if (method === 'GET' && versionDiffMatch) {
      const compareToVersionId = url.searchParams.get('compare_to_version_id')
      return jsonResponse(
        buildVersionDiffResponse(
          state,
          Number(versionDiffMatch[1]),
          compareToVersionId ? Number(compareToVersionId) : null,
        ),
      )
    }

    const rewriteRunsMatch = pathname.match(
      /^\/sites\/5\/ai-review-editor\/documents\/12\/issues\/(\d+)\/rewrite-runs$/,
    )
    if (method === 'GET' && rewriteRunsMatch) {
      return jsonResponse(buildRewriteRunsResponse(state, Number(rewriteRunsMatch[1])))
    }

    if (method === 'POST' && pathname === '/sites/5/ai-review-editor/documents/12/issues/101/dismiss') {
      const issue = state.issues.find((candidate) => candidate.id === 101)
      if (!issue) {
        return Promise.reject(new Error('Missing issue 101'))
      }
      issue.status = 'dismissed'
      issue.updated_at = '2026-03-27T09:05:00Z'
      issue.resolved_at = '2026-03-27T09:05:00Z'
      return jsonResponse(issue)
    }

    if (method === 'POST' && pathname === '/sites/5/ai-review-editor/documents/12/issues/102/resolve-manual') {
      const issue = state.issues.find((candidate) => candidate.id === 102)
      if (!issue) {
        return Promise.reject(new Error('Missing issue 102'))
      }
      issue.status = 'resolved_manual'
      issue.resolution_note = 'Updated manually.'
      issue.updated_at = '2026-03-27T09:06:00Z'
      issue.resolved_at = '2026-03-27T09:06:00Z'
      return jsonResponse(issue)
    }

    if (method === 'POST' && pathname === '/sites/5/ai-review-editor/documents/12/issues/101/rewrite-runs') {
      const issue = state.issues.find((candidate) => candidate.id === 101)
      if (!issue) {
        return Promise.reject(new Error('Missing issue 101'))
      }

      const rewriteRun: EditorRewriteRun = {
        id: state.nextRewriteRunId,
        document_id: state.document.id,
        review_issue_id: 101,
        block_key: 'p1',
        status: 'completed',
        model_name: 'gpt-cheap-rewrite',
        prompt_version: 'editor-rewrite-v1',
        schema_version: 'editor-rewrite-v1',
        input_hash: 'rewrite-input-v1',
        source_block_content_hash: issue ? state.blocks.find((candidate) => candidate.block_key === 'p1')?.content_hash ?? null : null,
        result_text: 'Verified pricing details for every plan are outlined below.',
        started_at: '2026-03-27T09:07:00Z',
      finished_at: '2026-03-27T09:07:01Z',
      applied_at: null,
      error_code: null,
      error_message: null,
      matches_current_document: true,
      matches_current_block: true,
      is_stale: false,
      created_at: '2026-03-27T09:07:00Z',
      updated_at: '2026-03-27T09:07:01Z',
    }

      state.nextRewriteRunId += 1
      state.rewriteRunsByIssue.set(101, [rewriteRun])
      issue.status = 'rewrite_ready'
      issue.replacement_candidate_text = rewriteRun.result_text
      issue.updated_at = '2026-03-27T09:07:01Z'
      return jsonResponse(rewriteRun)
    }

    const applyRewriteMatch = pathname.match(
      /^\/sites\/5\/ai-review-editor\/documents\/12\/rewrite-runs\/(\d+)\/apply$/,
    )
    if (method === 'POST' && applyRewriteMatch) {
      const rewriteRunId = Number(applyRewriteMatch[1])
      const rewriteRun = (state.rewriteRunsByIssue.get(101) ?? []).find((candidate) => candidate.id === rewriteRunId)
      const issue = state.issues.find((candidate) => candidate.id === 101)
      const block = state.blocks.find((candidate) => candidate.block_key === 'p1')

      if (!rewriteRun || !issue || !block || !rewriteRun.result_text) {
        return Promise.reject(new Error('Missing rewrite state'))
      }

      rewriteRun.status = 'applied'
      rewriteRun.applied_at = '2026-03-27T09:08:00Z'
      rewriteRun.updated_at = '2026-03-27T09:08:00Z'
      issue.status = 'applied'
      issue.resolution_note = 'Applied AI rewrite.'
      issue.updated_at = '2026-03-27T09:08:00Z'
      issue.resolved_at = '2026-03-27T09:08:00Z'
      block.text_content = rewriteRun.result_text
      block.html_content = `<p>${rewriteRun.result_text}</p>`
      block.content_hash = 'hash-p1-applied'
      block.updated_at = '2026-03-27T09:08:00Z'
      syncDocumentFromBlocks(state, '2026-03-27T09:08:00Z')
      markReviewRunsStale(state)
      pushCurrentVersion(state, 'rewrite_apply', 'Applied AI rewrite to p1.', '2026-03-27T09:08:00Z')

      return jsonResponse({
        document: buildDocumentResponse(state),
        issue,
        rewrite_run: rewriteRun,
        updated_block: block,
      })
    }

    const updateBlockMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/12\/blocks\/(.+)$/)
    if (method === 'PUT' && updateBlockMatch) {
      const blockKey = decodeURIComponent(updateBlockMatch[1])
      const requestBody = init?.body ? JSON.parse(String(init.body)) : {}
      const block = state.blocks.find((candidate) => candidate.block_key === blockKey)
      if (!block) {
        return Promise.reject(new Error(`Missing block ${blockKey}`))
      }
      if (
        requestBody.expected_content_hash &&
        requestBody.expected_content_hash !== block.content_hash
      ) {
        return Promise.resolve(
          jsonResponse(
            { detail: 'The block changed after the editor loaded it. Refresh the document and try again.' },
            { status: 409 },
          ),
        )
      }

      const normalizedText = String(requestBody.text_content ?? '').replace(/\s+/g, ' ').trim()
      const changed = normalizedText.length > 0 && normalizedText !== block.text_content
      if (changed) {
        block.text_content = normalizedText
        block.html_content = renderBlockHtml(block)
        block.content_hash = `hash-${block.block_key.toLowerCase()}-${state.nextVersionId}`
        block.updated_at = '2026-03-27T09:09:00Z'
        syncDocumentFromBlocks(state, '2026-03-27T09:09:00Z')
        markReviewRunsStale(state)
        const currentVersion = pushCurrentVersion(
          state,
          'manual_block_edit',
          `Edited block ${block.block_key} manually.`,
          '2026-03-27T09:09:00Z',
        )
        return jsonResponse({
          changed: true,
          document: buildDocumentResponse(state),
          updated_block: block,
          current_version: currentVersion,
        })
      }

      return jsonResponse({
        changed: false,
        document: buildDocumentResponse(state),
        updated_block: block,
        current_version: state.versions.find((version) => version.is_current) ?? state.versions[0],
      })
    }

    if (method === 'POST' && pathname === '/sites/5/ai-review-editor/documents/12/blocks') {
      const requestBody = init?.body ? JSON.parse(String(init.body)) : {}
      const position = requestBody.position ?? 'after'
      const targetBlockKey = requestBody.target_block_key
      const blockType = requestBody.block_type ?? 'paragraph'
      const normalizedText = String(requestBody.text_content ?? '').replace(/\s+/g, ' ').trim()
      const blockLevel =
        blockType === 'heading' && requestBody.block_level != null ? Number(requestBody.block_level) : null

      if (!normalizedText) {
        return Promise.resolve(jsonResponse({ detail: 'Edited block text cannot be empty.' }, { status: 400 }))
      }

      let insertIndex = state.blocks.length
      if (position !== 'end') {
        insertIndex = state.blocks.findIndex((candidate) => candidate.block_key === targetBlockKey)
        if (insertIndex < 0) {
          return Promise.resolve(jsonResponse({ detail: `Missing block ${targetBlockKey}` }, { status: 404 }))
        }
        if (position === 'after') {
          insertIndex += 1
        }
      }

      const insertedBlock: EditorDocumentBlock = {
        id: state.nextBlockId,
        document_id: state.document.id,
        block_key: buildNextMockBlockKey(state, blockType, blockLevel),
        block_type: blockType,
        block_level: blockLevel,
        parent_block_key: null,
        position_index: insertIndex,
        text_content: normalizedText,
        html_content: null,
        context_path: null,
        content_hash: `hash-${state.nextBlockId}`,
        is_active: true,
        created_at: '2026-03-27T09:10:00Z',
        updated_at: '2026-03-27T09:10:00Z',
      }

      state.nextBlockId += 1
      state.blocks.splice(insertIndex, 0, insertedBlock)
      syncDocumentFromBlocks(state, '2026-03-27T09:10:00Z')
      markReviewRunsStale(state)
      const currentVersion = pushCurrentVersion(
        state,
        'block_insert',
        targetBlockKey && position !== 'end'
          ? `Inserted block ${insertedBlock.block_key} ${position} ${targetBlockKey}.`
          : `Inserted block ${insertedBlock.block_key}.`,
        '2026-03-27T09:10:00Z',
      )

      const hydratedInsertedBlock = state.blocks.find((candidate) => candidate.id === insertedBlock.id) ?? insertedBlock
      return jsonResponse({
        document: buildDocumentResponse(state),
        inserted_block: hydratedInsertedBlock,
        current_version: currentVersion,
      })
    }

    const deleteBlockMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/12\/blocks\/(.+)$/)
    if (method === 'DELETE' && deleteBlockMatch) {
      const blockKey = decodeURIComponent(deleteBlockMatch[1])
      const blockIndex = state.blocks.findIndex((candidate) => candidate.block_key === blockKey)
      if (blockIndex < 0) {
        return Promise.resolve(jsonResponse({ detail: `Missing block ${blockKey}` }, { status: 404 }))
      }
      if (state.blocks.length <= 1) {
        return Promise.resolve(
          jsonResponse(
            { detail: 'The last active block cannot be deleted. Keep at least one block in the document.' },
            { status: 400 },
          ),
        )
      }

      state.blocks.splice(blockIndex, 1)
      syncDocumentFromBlocks(state, '2026-03-27T09:11:00Z')
      markReviewRunsStale(state)
      const currentVersion = pushCurrentVersion(
        state,
        'block_delete',
        `Deleted block ${blockKey}.`,
        '2026-03-27T09:11:00Z',
      )

      return jsonResponse({
        document: buildDocumentResponse(state),
        deleted_block_key: blockKey,
        remaining_block_count: state.blocks.length,
        current_version: currentVersion,
      })
    }

    const restoreVersionMatch = pathname.match(/^\/sites\/5\/ai-review-editor\/documents\/12\/versions\/(\d+)\/restore$/)
    if (method === 'POST' && restoreVersionMatch) {
      const restoredFromVersion = state.versions.find((candidate) => candidate.id === Number(restoreVersionMatch[1]))
      if (!restoredFromVersion?.snapshot) {
        return Promise.reject(new Error(`Missing version ${restoreVersionMatch[1]}`))
      }

      state.document.title = restoredFromVersion.snapshot.title
      state.document.document_type = restoredFromVersion.snapshot.document_type
      state.document.source_format = restoredFromVersion.snapshot.source_format
      state.document.source_content = restoredFromVersion.snapshot.source_content
      state.document.normalized_content = restoredFromVersion.snapshot.normalized_content
      state.document.topic_brief_json = restoredFromVersion.snapshot.topic_brief_json
      state.document.facts_context_json = restoredFromVersion.snapshot.facts_context_json
      state.document.status = restoredFromVersion.snapshot.status as EditorDocument['status']
      state.document.updated_at = '2026-03-27T09:12:00Z'
      state.blocks = restoredFromVersion.snapshot.blocks.map((block, index) => ({
        id: 700 + index,
        document_id: state.document.id,
        block_key: block.block_key,
        block_type: block.block_type,
        block_level: block.block_level,
        parent_block_key: block.parent_block_key,
        position_index: block.position_index,
        text_content: block.text_content,
        html_content: block.html_content,
        context_path: block.context_path,
        content_hash: block.content_hash,
        is_active: true,
        created_at: '2026-03-27T09:12:00Z',
        updated_at: '2026-03-27T09:12:00Z',
      }))
      markReviewRunsStale(state)
      const currentVersion = pushCurrentVersion(
        state,
        'rollback',
        `Restored version ${restoredFromVersion.version_no}.`,
        '2026-03-27T09:12:00Z',
      )
      markCurrentVersion(state, currentVersion.id)

      return jsonResponse({
        document: buildDocumentResponse(state),
        restored_from_version: restoredFromVersion,
        current_version: currentVersion,
        blocks_restored_count: state.blocks.length,
      })
    }

    return Promise.reject(new Error(`Unhandled ${method} ${pathname}`))
  })
}

function renderAiReviewRoute(route: string) {
  const queryClient = createTestQueryClient()
  const user = userEvent.setup()

  const result = render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/sites/:siteId" element={<SiteWorkspaceLayout />}>
              <Route path="ai-review-editor">
                <Route path="documents" element={<AIReviewEditorDocumentsPage />} />
                <Route path="new" element={<AIReviewEditorNewDocumentPage />} />
                <Route path="documents/:documentId" element={<AIReviewEditorDocumentPage />} />
              </Route>
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  )

  return {
    user,
    queryClient,
    ...result,
  }
}

describe('AIReviewEditor frontend', () => {
  test('renders documents list and opens a document review screen', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents')

    await screen.findByRole('heading', { name: 'AI review documents' })
    await screen.findByText('Pricing FAQ')

    await user.click(screen.getByRole('link', { name: 'Open' }))

    await screen.findByRole('heading', { name: 'Pricing FAQ' })
  })

  test('shows new document navigation and creates a document from the AI review workspace', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents')

    await screen.findByRole('heading', { name: 'AI review documents' })

    await user.click(screen.getByRole('link', { name: 'New document' }))

    await screen.findByRole('heading', { name: 'New AI review document' })

    await user.type(screen.getByLabelText('Title'), 'Orthodontics pricing guide')
    await user.clear(screen.getByLabelText('Document type'))
    await user.type(screen.getByLabelText('Document type'), 'landing_page')
    await user.type(
      screen.getByLabelText('Source HTML'),
      '<h1>Orthodontics pricing guide</h1><p>Verified treatment pricing details.</p>',
    )

    await user.click(screen.getByRole('button', { name: 'Create document' }))

    await screen.findByRole('heading', { name: 'Orthodontics pricing guide' })
  })

  test('renders document blocks and shows gutter markers only for blocks with issues', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    await screen.findByTestId('ai-review-block-h1')
    expect(screen.getByTestId('ai-review-block-marker-h1')).toBeInTheDocument()
    expect(screen.getByTestId('ai-review-block-marker-p1')).toBeInTheDocument()
    expect(screen.queryByTestId('ai-review-block-marker-p2')).not.toBeInTheDocument()

    expect(within(screen.getByTestId('ai-review-block-h1')).getByRole('heading', { name: 'Pricing guide' })).toBeInTheDocument()
    expect(
      within(screen.getByTestId('ai-review-block-p1')).getByText('TODO add verified pricing details.'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('ai-review-block-p2')).getByText('All subscriptions renew monthly.'),
    ).toBeInTheDocument()
  })

  test('switches to whole-document view and downloads the current HTML', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const createObjectUrlMock = vi.fn(() => 'blob:ai-review-document')
    const revokeObjectUrlMock = vi.fn()
    const originalCreateObjectUrl = URL.createObjectURL
    const originalRevokeObjectUrl = URL.revokeObjectURL
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: createObjectUrlMock,
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: revokeObjectUrlMock,
    })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    try {
      const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

      await screen.findByTestId('ai-review-block-h1')
      await user.click(screen.getByRole('button', { name: 'Whole document' }))

      const fullDocument = await screen.findByTestId('ai-review-full-document')
      expect(within(fullDocument).getByText('Pricing guide')).toBeInTheDocument()
      expect(within(fullDocument).getByText('TODO add verified pricing details.')).toBeInTheDocument()

      await user.click(screen.getAllByRole('button', { name: 'Download HTML' }).at(-1)!)

      await waitFor(() => {
        expect(createObjectUrlMock).toHaveBeenCalledTimes(1)
      })
      expect(clickSpy).toHaveBeenCalledTimes(1)
      expect(revokeObjectUrlMock).toHaveBeenCalledWith('blob:ai-review-document')
      const exportedBlob = (createObjectUrlMock.mock.calls as unknown[][])[0]?.[0] as Blob | undefined
      expect(exportedBlob).toBeInstanceOf(Blob)
      await expect(exportedBlob?.text()).resolves.toContain('<h1>Pricing guide</h1>')
    } finally {
      clickSpy.mockRestore()
      Object.defineProperty(URL, 'createObjectURL', {
        configurable: true,
        writable: true,
        value: originalCreateObjectUrl,
      })
      Object.defineProperty(URL, 'revokeObjectURL', {
        configurable: true,
        writable: true,
        value: originalRevokeObjectUrl,
      })
    }
  })

  test('enters block edit mode and allows cancel without persisting changes', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    const block = await screen.findByTestId('ai-review-block-p2')
    await user.click(within(block).getByRole('button', { name: 'Edit' }))

    const editor = within(block).getByRole('textbox')
    expect(editor).toHaveValue('All subscriptions renew monthly.')

    await user.clear(editor)
    await user.type(editor, 'All subscriptions renew yearly.')
    await user.click(within(block).getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(within(block).getByText('All subscriptions renew monthly.')).toBeInTheDocument()
    })
    expect(screen.queryByDisplayValue('All subscriptions renew yearly.')).not.toBeInTheDocument()
    expect(state.versions).toHaveLength(1)
  })

  test('saves inline block edits, refreshes the document, and creates a manual edit version', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    const block = await screen.findByTestId('ai-review-block-p2')
    await user.click(within(block).getByRole('button', { name: 'Edit' }))

    const editor = within(block).getByRole('textbox')
    await user.clear(editor)
    await user.type(editor, 'All subscriptions renew yearly.')
    await user.click(within(block).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(within(screen.getByTestId('ai-review-block-p2')).getByText('All subscriptions renew yearly.')).toBeInTheDocument()
    })
    expect(await screen.findByText('Block saved. Version 2 is now current.')).toBeInTheDocument()
    expect(await screen.findByTestId('ai-review-version-402')).toHaveTextContent('Edited block p2 manually.')
  })

  test('opens block insert UI and allows cancel without changing the document', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    const block = await screen.findByTestId('ai-review-block-p2')
    await user.click(within(block).getByRole('button', { name: 'Add before' }))

    const insertForm = await screen.findByTestId('ai-review-insert-before-p2')
    expect(within(insertForm).getByText('Inserting')).toBeInTheDocument()

    await user.click(within(insertForm).getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(screen.queryByTestId('ai-review-insert-before-p2')).not.toBeInTheDocument()
    })
    expect(state.blocks).toHaveLength(3)
    expect(state.versions).toHaveLength(1)
  })

  test('insert before adds a new block in the expected position and creates a version entry', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    const block = await screen.findByTestId('ai-review-block-p2')
    await user.click(within(block).getByRole('button', { name: 'Add before' }))

    const insertForm = await screen.findByTestId('ai-review-insert-before-p2')
    await user.type(within(insertForm).getByRole('textbox'), 'Key pricing variables include seats and usage volume.')
    await user.click(within(insertForm).getByRole('button', { name: 'Insert block' }))

    await waitFor(() => {
      expect(screen.getByText('Block inserted. Version 2 is now current.')).toBeInTheDocument()
    })
    expect(await screen.findByText('Key pricing variables include seats and usage volume.')).toBeInTheDocument()
    expect(await screen.findByTestId('ai-review-version-402')).toHaveTextContent('Inserted block p3 before p2.')
  })

  test('insert after supports another block type and refreshes the canvas', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    const block = await screen.findByTestId('ai-review-block-p1')
    await user.click(within(block).getByRole('button', { name: 'Add after' }))

    const insertForm = await screen.findByTestId('ai-review-insert-after-p1')
    await user.selectOptions(within(insertForm).getByLabelText('Block type'), 'heading')
    await user.selectOptions(within(insertForm).getByLabelText('Heading level'), '2')
    const textInput = within(insertForm).getByRole('textbox')
    await user.type(textInput, 'Plan details')
    await user.click(within(insertForm).getByRole('button', { name: 'Insert block' }))

    await waitFor(() => {
      expect(screen.getByText('Block inserted. Version 2 is now current.')).toBeInTheDocument()
    })
    expect(await screen.findByText('Plan details')).toBeInTheDocument()
  })

  test('delete removes the target block, refreshes the canvas, and records a new version', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    const block = await screen.findByTestId('ai-review-block-p1')
    await user.click(within(block).getByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(screen.getByText('Block removed. Version 2 is now current.')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('ai-review-block-p1')).not.toBeInTheDocument()
    expect(screen.queryByTestId('ai-review-block-marker-p1')).not.toBeInTheDocument()
    expect(await screen.findByTestId('ai-review-version-402')).toHaveTextContent('Deleted block p1.')
    expect(within(screen.getByTestId('ai-review-block-p2')).getByText('All subscriptions renew monthly.')).toBeInTheDocument()
  })

  test('marks an existing rewrite preview as stale after manual block edit', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    await screen.findByTestId('ai-review-issue-101')
    await user.click(screen.getByRole('button', { name: 'Rewrite with AI' }))
    await screen.findByTestId('ai-review-rewrite-preview')

    const block = screen.getByTestId('ai-review-block-p1')
    await user.click(within(block).getByRole('button', { name: 'Edit' }))
    const editor = within(block).getByRole('textbox')
    await user.clear(editor)
    await user.type(editor, 'Verified pricing details are updated manually.')
    await user.click(within(block).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(within(screen.getByTestId('ai-review-block-p1')).getByText('Verified pricing details are updated manually.')).toBeInTheDocument()
    })
    expect(await screen.findByText('Rewrite preview is stale')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Apply rewrite' })).not.toBeInTheDocument()
  })

  test('keeps issue actions available when a different block was edited manually', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    await screen.findByTestId('ai-review-issue-101')
    await user.click(screen.getByRole('button', { name: 'Rewrite with AI' }))
    await screen.findByTestId('ai-review-rewrite-preview')

    const otherBlock = screen.getByTestId('ai-review-block-p2')
    await user.click(within(otherBlock).getByRole('button', { name: 'Edit' }))
    const editor = within(otherBlock).getByRole('textbox')
    await user.clear(editor)
    await user.type(editor, 'All subscriptions still renew monthly, with verified billing terms.')
    await user.click(within(otherBlock).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(
        within(screen.getByTestId('ai-review-block-p2')).getByText(
          'All subscriptions still renew monthly, with verified billing terms.',
        ),
      ).toBeInTheDocument()
    })
    expect(screen.queryByText('Rewrite preview is stale')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Apply rewrite' })).toBeInTheDocument()
  })

  test('dismiss action refreshes issue status', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    await screen.findByTestId('ai-review-issue-101')
    await user.click(screen.getByRole('button', { name: 'Dismiss' }))

    await waitFor(() => {
      expect(within(screen.getByTestId('ai-review-issue-101')).getByText('Dismissed')).toBeInTheDocument()
    })
  })

  test('manual resolve action closes issue without creating a rewrite run', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12?block=h1&issue=102')

    await screen.findByTestId('ai-review-issue-102')
    await user.click(within(screen.getByTestId('ai-review-issue-102')).getByRole('button', { name: 'Resolved manually' }))

    await waitFor(() => {
      expect(
        within(screen.getByTestId('ai-review-issue-102')).getByText('Resolved manually'),
      ).toBeInTheDocument()
    })
    expect(state.rewriteRunsByIssue.get(102) ?? []).toHaveLength(0)
  })

  test('rewrite action creates preview for the selected issue', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    await screen.findByTestId('ai-review-issue-101')
    await user.click(screen.getByRole('button', { name: 'Rewrite with AI' }))

    await screen.findByTestId('ai-review-rewrite-preview')
    expect(
      within(screen.getByTestId('ai-review-rewrite-preview')).getByText(
        'Verified pricing details for every plan are outlined below.',
      ),
    ).toBeInTheDocument()
    expect(within(screen.getByTestId('ai-review-issue-101')).getByText('Rewrite ready')).toBeInTheDocument()
  })

  test('apply rewrite updates only the target block and marks issue as applied', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    await screen.findByTestId('ai-review-issue-101')
    await user.click(screen.getByRole('button', { name: 'Rewrite with AI' }))
    await screen.findByTestId('ai-review-rewrite-preview')

    await user.click(screen.getByRole('button', { name: 'Apply rewrite' }))

    await waitFor(() => {
      expect(within(screen.getByTestId('ai-review-issue-101')).getByText('Applied')).toBeInTheDocument()
    })
    expect(
      within(screen.getByTestId('ai-review-block-p1')).getByText(
        'Verified pricing details for every plan are outlined below.',
      ),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('ai-review-block-p2')).getByText('All subscriptions renew monthly.'),
    ).toBeInTheDocument()
  })

  test('filters update the visible issue markers', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    await screen.findByTestId('ai-review-block-marker-h1')
    await user.click(screen.getByRole('button', { name: 'High severity' }))

    await waitFor(() => {
      expect(screen.getByTestId('ai-review-block-marker-p1')).toBeInTheDocument()
      expect(screen.queryByTestId('ai-review-block-marker-h1')).not.toBeInTheDocument()
    })
  })

  test('renders version history, shows diff preview, and restores an older version', async () => {
    const state = createAiReviewState()
    installAiReviewFetchMock(state)

    const { user } = renderAiReviewRoute('/sites/5/ai-review-editor/documents/12')

    await screen.findByTestId('ai-review-version-401')
    expect(screen.getByTestId('ai-review-current-version-badge')).toBeInTheDocument()
    await screen.findByTestId('ai-review-issue-101')

    await user.click(screen.getByRole('button', { name: 'Rewrite with AI' }))
    await screen.findByTestId('ai-review-rewrite-preview')

    await user.click(screen.getByRole('button', { name: 'Apply rewrite' }))
    await waitFor(() => {
      expect(within(screen.getByTestId('ai-review-issue-101')).getByText('Applied')).toBeInTheDocument()
    })

    const olderVersion = await screen.findByTestId('ai-review-version-401')
    await user.click(olderVersion)
    const diffSection = await screen.findByTestId('ai-review-version-diff')
    expect(
      within(diffSection).getAllByText('Verified pricing details for every plan are outlined below.').length,
    ).toBeGreaterThan(0)
    expect(within(diffSection).getAllByText('TODO add verified pricing details.').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Restore version' }))

    await waitFor(() => {
      expect(
        within(screen.getByTestId('ai-review-block-p1')).getByText('TODO add verified pricing details.'),
      ).toBeInTheDocument()
    })
    expect(
      within(screen.getByTestId('ai-review-block-p2')).getByText('All subscriptions renew monthly.'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('ai-review-version-402')).getByText('Applied AI rewrite to p1.'),
    ).toBeInTheDocument()
    expect(
      within(screen.getByTestId('ai-review-version-403')).getByText('Restored version 1.'),
    ).toBeInTheDocument()
  })
})
