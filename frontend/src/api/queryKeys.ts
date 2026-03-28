export const queryKeys = {
  sitesRoot: ['sites'] as const,
  sitesList: ['sites', 'list'] as const,
  siteDetail: (siteId: number, search: string) => ['sites', siteId, 'detail', search] as const,
  siteCrawls: (siteId: number) => ['sites', siteId, 'crawls'] as const,
  siteContentGeneratorAsset: (siteId: number, search: string) =>
    ['sites', siteId, 'content-generator-assets', search] as const,
  sitePagesCompare: (siteId: number, search: string) => ['sites', siteId, 'pages', 'compare', search] as const,
  siteAuditCompare: (siteId: number, search: string) => ['sites', siteId, 'audit', 'compare', search] as const,
  siteOpportunitiesCompare: (siteId: number, search: string) =>
    ['sites', siteId, 'opportunities', 'compare', search] as const,
  siteInternalLinkingCompare: (siteId: number, search: string) =>
    ['sites', siteId, 'internal-linking', 'compare', search] as const,
  siteContentRecommendations: (siteId: number, search: string) =>
    ['sites', siteId, 'content-recommendations', search] as const,
  siteAiReviewDocuments: (siteId: number) => ['sites', siteId, 'ai-review-editor', 'documents'] as const,
  siteAiReviewDocument: (siteId: number, documentId: number) =>
    ['sites', siteId, 'ai-review-editor', 'documents', documentId] as const,
  siteAiReviewBlocks: (siteId: number, documentId: number) =>
    ['sites', siteId, 'ai-review-editor', 'documents', documentId, 'blocks'] as const,
  siteAiReviewIssues: (siteId: number, documentId: number) =>
    ['sites', siteId, 'ai-review-editor', 'documents', documentId, 'issues'] as const,
  siteAiReviewSummary: (siteId: number, documentId: number) =>
    ['sites', siteId, 'ai-review-editor', 'documents', documentId, 'summary'] as const,
  siteAiReviewRuns: (siteId: number, documentId: number) =>
    ['sites', siteId, 'ai-review-editor', 'documents', documentId, 'review-runs'] as const,
  siteAiReviewVersions: (siteId: number, documentId: number) =>
    ['sites', siteId, 'ai-review-editor', 'documents', documentId, 'versions'] as const,
  siteAiReviewVersion: (siteId: number, documentId: number, versionId: number) =>
    ['sites', siteId, 'ai-review-editor', 'documents', documentId, 'versions', versionId] as const,
  siteAiReviewVersionDiff: (
    siteId: number,
    documentId: number,
    versionId: number,
    compareToVersionId: number | null,
  ) =>
    ['sites', siteId, 'ai-review-editor', 'documents', documentId, 'versions', versionId, 'diff', compareToVersionId] as const,
  siteAiRewriteRuns: (siteId: number, documentId: number, issueId: number) =>
    ['sites', siteId, 'ai-review-editor', 'documents', documentId, 'issues', issueId, 'rewrite-runs'] as const,
  siteCompetitiveGap: (siteId: number, search: string) => ['sites', siteId, 'competitive-gap', search] as const,
  siteCompetitiveGapStrategy: (siteId: number) => ['sites', siteId, 'competitive-gap', 'strategy'] as const,
  siteCompetitiveGapCompetitors: (siteId: number) => ['sites', siteId, 'competitive-gap', 'competitors'] as const,
  siteCompetitiveGapReviewRuns: (siteId: number, limit: number) =>
    ['sites', siteId, 'competitive-gap', 'review-runs', limit] as const,
  siteCompetitiveGapCompetitorSyncRuns: (siteId: number, competitorId: number, limit: number) =>
    ['sites', siteId, 'competitive-gap', 'competitors', competitorId, 'sync-runs', limit] as const,
  siteGscSummary: (siteId: number, search: string) => ['sites', siteId, 'gsc', 'summary', search] as const,
  siteGscProperties: (siteId: number) => ['sites', siteId, 'gsc', 'properties'] as const,
  jobsRoot: ['crawl-jobs'] as const,
  jobsList: (search: string) => ['crawl-jobs', 'list', search] as const,
  jobDetail: (jobId: number) => ['crawl-jobs', 'detail', jobId] as const,
  jobPages: (jobId: number, search: string) => ['crawl-jobs', jobId, 'pages', search] as const,
  jobPageTaxonomySummary: (jobId: number) => ['crawl-jobs', jobId, 'page-taxonomy', 'summary'] as const,
  jobLinks: (jobId: number, search: string) => ['crawl-jobs', jobId, 'links', search] as const,
  jobAudit: (jobId: number) => ['crawl-jobs', jobId, 'audit'] as const,
  jobOpportunities: (jobId: number, search: string) => ['crawl-jobs', jobId, 'opportunities', search] as const,
  jobInternalLinkingOverview: (jobId: number, search: string) =>
    ['crawl-jobs', jobId, 'internal-linking', 'overview', search] as const,
  jobInternalLinkingIssues: (jobId: number, search: string) =>
    ['crawl-jobs', jobId, 'internal-linking', 'issues', search] as const,
  jobCannibalization: (jobId: number, search: string) =>
    ['crawl-jobs', jobId, 'cannibalization', search] as const,
  jobCannibalizationPage: (jobId: number, pageId: number, search: string) =>
    ['crawl-jobs', jobId, 'cannibalization', 'page', pageId, search] as const,
  jobGscSummary: (jobId: number) => ['crawl-jobs', jobId, 'gsc', 'summary'] as const,
  jobGscProperties: (jobId: number) => ['crawl-jobs', jobId, 'gsc', 'properties'] as const,
  jobGscTopQueries: (jobId: number, search: string) => ['crawl-jobs', jobId, 'gsc', 'top-queries', search] as const,
  jobTrendsOverview: (jobId: number) => ['crawl-jobs', jobId, 'trends', 'overview'] as const,
  jobCrawlCompare: (jobId: number, search: string) => ['crawl-jobs', jobId, 'trends', 'crawl', search] as const,
  jobGscCompare: (jobId: number, search: string) => ['crawl-jobs', jobId, 'trends', 'gsc', search] as const,
}
