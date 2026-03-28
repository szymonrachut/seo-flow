import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type {
  EditorDocument,
  EditorDocumentBlockListResponse,
  EditorDocumentBlockDeleteResponse,
  EditorDocumentBlockInsertInput,
  EditorDocumentBlockInsertResponse,
  EditorDocumentBlockUpdateInput,
  EditorDocumentBlockUpdateResponse,
  EditorDocumentListResponse,
  EditorDocumentParseResponse,
  EditorDocumentVersion,
  EditorDocumentVersionDiff,
  EditorDocumentVersionListResponse,
  EditorDocumentVersionRestoreResponse,
  EditorReviewIssueDismissInput,
  EditorReviewIssueListResponse,
  EditorReviewIssueManualResolveInput,
  EditorReviewRun,
  EditorReviewRunCreateInput,
  EditorReviewRunListResponse,
  EditorReviewSummary,
  EditorRewriteApplyResponse,
  EditorRewriteRun,
  EditorRewriteRunListResponse,
} from '../../types/api'

export async function listSiteAiReviewDocuments(siteId: number) {
  return apiRequest<EditorDocumentListResponse>(`/sites/${siteId}/ai-review-editor/documents`)
}

export async function getSiteAiReviewDocument(siteId: number, documentId: number) {
  return apiRequest<EditorDocument>(`/sites/${siteId}/ai-review-editor/documents/${documentId}`)
}

export async function parseSiteAiReviewDocument(siteId: number, documentId: number) {
  return apiRequest<EditorDocumentParseResponse>(`/sites/${siteId}/ai-review-editor/documents/${documentId}/parse`, {
    method: 'POST',
  })
}

export async function listSiteAiReviewBlocks(siteId: number, documentId: number) {
  return apiRequest<EditorDocumentBlockListResponse>(`/sites/${siteId}/ai-review-editor/documents/${documentId}/blocks`)
}

export async function updateSiteAiReviewBlock(
  siteId: number,
  documentId: number,
  blockKey: string,
  payload: EditorDocumentBlockUpdateInput,
) {
  return apiRequest<EditorDocumentBlockUpdateResponse>(
    `/sites/${siteId}/ai-review-editor/documents/${documentId}/blocks/${encodeURIComponent(blockKey)}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )
}

export async function insertSiteAiReviewBlock(siteId: number, documentId: number, payload: EditorDocumentBlockInsertInput) {
  return apiRequest<EditorDocumentBlockInsertResponse>(`/sites/${siteId}/ai-review-editor/documents/${documentId}/blocks`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteSiteAiReviewBlock(siteId: number, documentId: number, blockKey: string) {
  return apiRequest<EditorDocumentBlockDeleteResponse>(
    `/sites/${siteId}/ai-review-editor/documents/${documentId}/blocks/${encodeURIComponent(blockKey)}`,
    {
      method: 'DELETE',
    },
  )
}

export async function listSiteAiReviewIssues(siteId: number, documentId: number) {
  return apiRequest<EditorReviewIssueListResponse>(`/sites/${siteId}/ai-review-editor/documents/${documentId}/issues`)
}

export async function listSiteAiReviewVersions(siteId: number, documentId: number) {
  return apiRequest<EditorDocumentVersionListResponse>(`/sites/${siteId}/ai-review-editor/documents/${documentId}/versions`)
}

export async function getSiteAiReviewVersion(siteId: number, documentId: number, versionId: number) {
  return apiRequest<EditorDocumentVersion>(
    `/sites/${siteId}/ai-review-editor/documents/${documentId}/versions/${versionId}`,
  )
}

export async function getSiteAiReviewVersionDiff(
  siteId: number,
  documentId: number,
  versionId: number,
  compareToVersionId?: number | null,
) {
  const search = compareToVersionId ? `?compare_to_version_id=${compareToVersionId}` : ''
  return apiRequest<EditorDocumentVersionDiff>(
    `/sites/${siteId}/ai-review-editor/documents/${documentId}/versions/${versionId}/diff${search}`,
  )
}

export async function restoreSiteAiReviewVersion(siteId: number, documentId: number, versionId: number) {
  return apiRequest<EditorDocumentVersionRestoreResponse>(
    `/sites/${siteId}/ai-review-editor/documents/${documentId}/versions/${versionId}/restore`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    },
  )
}

export async function getSiteAiReviewSummary(siteId: number, documentId: number) {
  return apiRequest<EditorReviewSummary>(`/sites/${siteId}/ai-review-editor/documents/${documentId}/review-summary`)
}

export async function listSiteAiReviewRuns(siteId: number, documentId: number) {
  return apiRequest<EditorReviewRunListResponse>(`/sites/${siteId}/ai-review-editor/documents/${documentId}/review-runs`)
}

export async function createSiteAiReviewRun(siteId: number, documentId: number, payload: EditorReviewRunCreateInput) {
  return apiRequest<EditorReviewRun>(`/sites/${siteId}/ai-review-editor/documents/${documentId}/review-runs`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function dismissSiteAiReviewIssue(
  siteId: number,
  documentId: number,
  issueId: number,
  payload: EditorReviewIssueDismissInput,
) {
  return apiRequest(`/sites/${siteId}/ai-review-editor/documents/${documentId}/issues/${issueId}/dismiss`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function resolveSiteAiReviewIssueManually(
  siteId: number,
  documentId: number,
  issueId: number,
  payload: EditorReviewIssueManualResolveInput,
) {
  return apiRequest(`/sites/${siteId}/ai-review-editor/documents/${documentId}/issues/${issueId}/resolve-manual`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function requestSiteAiRewriteRun(siteId: number, documentId: number, issueId: number) {
  return apiRequest<EditorRewriteRun>(
    `/sites/${siteId}/ai-review-editor/documents/${documentId}/issues/${issueId}/rewrite-runs`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    },
  )
}

export async function listSiteAiRewriteRuns(siteId: number, documentId: number, issueId: number) {
  return apiRequest<EditorRewriteRunListResponse>(
    `/sites/${siteId}/ai-review-editor/documents/${documentId}/issues/${issueId}/rewrite-runs`,
  )
}

export async function applySiteAiRewriteRun(siteId: number, documentId: number, rewriteRunId: number) {
  return apiRequest<EditorRewriteApplyResponse>(
    `/sites/${siteId}/ai-review-editor/documents/${documentId}/rewrite-runs/${rewriteRunId}/apply`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    },
  )
}

function invalidateAiReviewDocumentScope(
  queryClient: ReturnType<typeof useQueryClient>,
  siteId: number,
  documentId: number,
  issueId?: number,
) {
  const invalidations = [
    queryClient.invalidateQueries({ queryKey: queryKeys.siteAiReviewDocuments(siteId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.siteAiReviewDocument(siteId, documentId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.siteAiReviewBlocks(siteId, documentId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.siteAiReviewIssues(siteId, documentId) }),
    queryClient.invalidateQueries({
      queryKey: ['sites', siteId, 'ai-review-editor', 'documents', documentId, 'issues'],
    }),
    queryClient.invalidateQueries({ queryKey: queryKeys.siteAiReviewSummary(siteId, documentId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.siteAiReviewRuns(siteId, documentId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.siteAiReviewVersions(siteId, documentId) }),
  ]
  if (issueId !== undefined) {
    invalidations.push(
      queryClient.invalidateQueries({
        queryKey: queryKeys.siteAiRewriteRuns(siteId, documentId, issueId),
      }),
    )
  }
  return Promise.all(invalidations)
}

export function useSiteAiReviewDocumentsQuery(siteId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteAiReviewDocuments(siteId),
    queryFn: () => listSiteAiReviewDocuments(siteId),
    enabled,
  })
}

export function useSiteAiReviewDocumentQuery(siteId: number, documentId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteAiReviewDocument(siteId, documentId),
    queryFn: () => getSiteAiReviewDocument(siteId, documentId),
    enabled,
  })
}

export function useSiteAiReviewBlocksQuery(siteId: number, documentId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteAiReviewBlocks(siteId, documentId),
    queryFn: () => listSiteAiReviewBlocks(siteId, documentId),
    enabled,
  })
}

export function useSiteAiReviewIssuesQuery(siteId: number, documentId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteAiReviewIssues(siteId, documentId),
    queryFn: () => listSiteAiReviewIssues(siteId, documentId),
    enabled,
  })
}

export function useUpdateSiteAiReviewBlockMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ blockKey, payload }: { blockKey: string; payload: EditorDocumentBlockUpdateInput }) =>
      updateSiteAiReviewBlock(siteId, documentId, blockKey, payload),
    onSuccess: async () => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId)
    },
  })
}

export function useInsertSiteAiReviewBlockMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: EditorDocumentBlockInsertInput) => insertSiteAiReviewBlock(siteId, documentId, payload),
    onSuccess: async () => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId)
    },
  })
}

export function useDeleteSiteAiReviewBlockMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (blockKey: string) => deleteSiteAiReviewBlock(siteId, documentId, blockKey),
    onSuccess: async () => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId)
    },
  })
}

export function useSiteAiReviewVersionsQuery(siteId: number, documentId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteAiReviewVersions(siteId, documentId),
    queryFn: () => listSiteAiReviewVersions(siteId, documentId),
    enabled,
  })
}

export function useSiteAiReviewVersionQuery(siteId: number, documentId: number, versionId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteAiReviewVersion(siteId, documentId, versionId),
    queryFn: () => getSiteAiReviewVersion(siteId, documentId, versionId),
    enabled,
  })
}

export function useSiteAiReviewVersionDiffQuery(
  siteId: number,
  documentId: number,
  versionId: number,
  compareToVersionId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.siteAiReviewVersionDiff(siteId, documentId, versionId, compareToVersionId),
    queryFn: () => getSiteAiReviewVersionDiff(siteId, documentId, versionId, compareToVersionId),
    enabled,
  })
}

export function useSiteAiReviewSummaryQuery(siteId: number, documentId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteAiReviewSummary(siteId, documentId),
    queryFn: () => getSiteAiReviewSummary(siteId, documentId),
    enabled,
  })
}

export function useSiteAiReviewRunsQuery(siteId: number, documentId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteAiReviewRuns(siteId, documentId),
    queryFn: () => listSiteAiReviewRuns(siteId, documentId),
    enabled,
  })
}

export function useSiteAiRewriteRunsQuery(siteId: number, documentId: number, issueId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteAiRewriteRuns(siteId, documentId, issueId),
    queryFn: () => listSiteAiRewriteRuns(siteId, documentId, issueId),
    enabled,
  })
}

export function useParseSiteAiReviewDocumentMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => parseSiteAiReviewDocument(siteId, documentId),
    onSuccess: async () => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId)
    },
  })
}

export function useCreateSiteAiReviewRunMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: EditorReviewRunCreateInput) => createSiteAiReviewRun(siteId, documentId, payload),
    onSuccess: async () => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId)
    },
  })
}

export function useDismissSiteAiReviewIssueMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ issueId, payload }: { issueId: number; payload: EditorReviewIssueDismissInput }) =>
      dismissSiteAiReviewIssue(siteId, documentId, issueId, payload),
    onSuccess: async (_data, variables) => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId, variables.issueId)
    },
  })
}

export function useResolveSiteAiReviewIssueManuallyMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ issueId, payload }: { issueId: number; payload: EditorReviewIssueManualResolveInput }) =>
      resolveSiteAiReviewIssueManually(siteId, documentId, issueId, payload),
    onSuccess: async (_data, variables) => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId, variables.issueId)
    },
  })
}

export function useRequestSiteAiRewriteRunMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (issueId: number) => requestSiteAiRewriteRun(siteId, documentId, issueId),
    onSuccess: async (_data, issueId) => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId, issueId)
    },
  })
}

export function useApplySiteAiRewriteRunMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ rewriteRunId, issueId: _issueId }: { rewriteRunId: number; issueId: number }) =>
      applySiteAiRewriteRun(siteId, documentId, rewriteRunId),
    onSuccess: async (_data, variables) => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId, variables.issueId)
    },
  })
}

export function useRestoreSiteAiReviewVersionMutation(siteId: number, documentId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (versionId: number) => restoreSiteAiReviewVersion(siteId, documentId, versionId),
    onSuccess: async () => {
      await invalidateAiReviewDocumentScope(queryClient, siteId, documentId)
    },
  })
}
