export const queryKeys = {
  jobsRoot: ['crawl-jobs'] as const,
  jobsList: (search: string) => ['crawl-jobs', 'list', search] as const,
  jobDetail: (jobId: number) => ['crawl-jobs', 'detail', jobId] as const,
  jobPages: (jobId: number, search: string) => ['crawl-jobs', jobId, 'pages', search] as const,
  jobLinks: (jobId: number, search: string) => ['crawl-jobs', jobId, 'links', search] as const,
  jobAudit: (jobId: number) => ['crawl-jobs', jobId, 'audit'] as const,
}
