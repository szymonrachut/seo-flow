export interface SiteWorkspaceRouteContext {
  activeCrawlId?: number | null
  baselineCrawlId?: number | null
}

function buildSiteWorkspaceSearch({ activeCrawlId, baselineCrawlId }: SiteWorkspaceRouteContext) {
  const params = new URLSearchParams()
  if (activeCrawlId) {
    params.set('active_crawl_id', String(activeCrawlId))
  }
  if (baselineCrawlId) {
    params.set('baseline_crawl_id', String(baselineCrawlId))
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

export function buildSiteOverviewPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}${buildSiteWorkspaceSearch(context)}`
}

export function buildSitesNewPath() {
  return '/sites/new'
}

export function buildSiteCrawlsPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/crawls${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteCrawlsNewPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/crawls/new${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteProgressPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/progress${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteChangesPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/changes${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteChangesPagesPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/changes/pages${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteChangesAuditPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/changes/audit${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteChangesOpportunitiesPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/changes/opportunities${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteChangesInternalLinkingPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/changes/internal-linking${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteGscPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/gsc${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteGscSettingsPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/gsc/settings${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteGscImportPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/gsc/import${buildSiteWorkspaceSearch(context)}`
}

export function buildSitePagesPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/pages${buildSiteWorkspaceSearch(context)}`
}

export function buildSitePagesRecordsPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/pages/records${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteContentRecommendationsPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/content-recommendations${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteContentRecommendationsActivePath(
  siteId: number,
  context: SiteWorkspaceRouteContext = {},
) {
  return `/sites/${siteId}/content-recommendations/active${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteContentRecommendationsImplementedPath(
  siteId: number,
  context: SiteWorkspaceRouteContext = {},
) {
  return `/sites/${siteId}/content-recommendations/implemented${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteCompetitiveGapPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/competitive-gap${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteCompetitiveGapStrategyPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/competitive-gap/strategy${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteCompetitiveGapCompetitorsPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/competitive-gap/competitors${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteCompetitiveGapSyncPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/competitive-gap/sync${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteCompetitiveGapResultsPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/competitive-gap/results${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteAuditPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/audit${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteAuditSectionsPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/audit/sections${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteOpportunitiesPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/opportunities${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteOpportunitiesRecordsPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/opportunities/records${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteInternalLinkingPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/internal-linking${buildSiteWorkspaceSearch(context)}`
}

export function buildSiteInternalLinkingIssuesPath(siteId: number, context: SiteWorkspaceRouteContext = {}) {
  return `/sites/${siteId}/internal-linking/issues${buildSiteWorkspaceSearch(context)}`
}
