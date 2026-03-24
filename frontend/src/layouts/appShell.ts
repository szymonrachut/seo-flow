import type { TFunction } from 'i18next'
import { matchPath } from 'react-router-dom'

import type { SiteDetail } from '../types/api'
import {
  buildSiteChangesPath,
  buildSiteChangesAuditPath,
  buildSiteChangesInternalLinkingPath,
  buildSiteChangesOpportunitiesPath,
  buildSiteChangesPagesPath,
  buildSiteAuditPath,
  buildSiteAuditSectionsPath,
  buildSiteCompetitiveGapCompetitorsPath,
  buildSiteCompetitiveGapPath,
  buildSiteCompetitiveGapResultsPath,
  buildSiteCompetitiveGapSyncPath,
  buildSiteCompetitiveGapStrategyPath,
  buildSiteContentRecommendationsActivePath,
  buildSiteContentRecommendationsImplementedPath,
  buildSiteContentRecommendationsPath,
  buildSiteCrawlsPath,
  buildSiteCrawlsNewPath,
  buildSiteGscPath,
  buildSiteGscImportPath,
  buildSiteGscSettingsPath,
  buildSiteInternalLinkingIssuesPath,
  buildSiteInternalLinkingPath,
  buildSiteOverviewPath,
  buildSiteOpportunitiesPath,
  buildSiteOpportunitiesRecordsPath,
  buildSitePagesPath,
  buildSitePagesRecordsPath,
  buildSiteProgressPath,
} from '../features/sites/routes'

export interface AppShellSubItem {
  label: string
  to?: string
  active: boolean
  disabled?: boolean
  badge?: string
}

export interface AppShellMenuItem {
  key: string
  label: string
  to?: string
  active: boolean
  disabled?: boolean
  badge?: string
  subItems?: AppShellSubItem[]
}

export type AppShellSiteSection =
  | 'overview'
  | 'progress'
  | 'pages'
  | 'audit'
  | 'opportunities'
  | 'internal-linking'
  | 'content-recommendations'
  | 'competitive-gap'
  | 'gsc'
  | 'crawls'
  | 'changes'

function pathMatches(pathname: string, patterns: string[]) {
  return patterns.some((pattern) => Boolean(matchPath(pattern, pathname)))
}

export function getActiveCrawlsSubsection(pathname: string) {
  if (pathMatches(pathname, ['/sites/:siteId/crawls/new'])) {
    return 'new'
  }

  if (pathMatches(pathname, ['/sites/:siteId/crawls'])) {
    return 'history'
  }

  return null
}

function buildSiteContext(site: SiteDetail) {
  return {
    activeCrawlId: site.active_crawl_id,
    baselineCrawlId: site.baseline_crawl_id,
  }
}

export function parseSiteIdFromPathname(pathname: string) {
  const match =
    matchPath('/sites/:siteId/*', pathname) ??
    matchPath('/sites/:siteId', pathname)

  const rawSiteId = match?.params.siteId
  if (!rawSiteId || rawSiteId === 'new') {
    return null
  }

  const parsed = Number(rawSiteId)
  return Number.isInteger(parsed) ? parsed : null
}

export function getActiveSiteSection(pathname: string): AppShellSiteSection | null {
  if (pathMatches(pathname, ['/sites/:siteId/progress'])) {
    return 'progress'
  }

  if (
    pathMatches(pathname, [
      '/sites/:siteId/changes',
      '/sites/:siteId/changes/*',
    ])
  ) {
    return 'changes'
  }

  if (pathMatches(pathname, ['/sites/:siteId/pages', '/sites/:siteId/pages/*'])) {
    return 'pages'
  }

  if (pathMatches(pathname, ['/sites/:siteId/audit', '/sites/:siteId/audit/*'])) {
    return 'audit'
  }

  if (pathMatches(pathname, ['/sites/:siteId/opportunities', '/sites/:siteId/opportunities/*'])) {
    return 'opportunities'
  }

  if (pathMatches(pathname, ['/sites/:siteId/internal-linking', '/sites/:siteId/internal-linking/*'])) {
    return 'internal-linking'
  }

  if (pathMatches(pathname, ['/sites/:siteId/content-recommendations', '/sites/:siteId/content-recommendations/*'])) {
    return 'content-recommendations'
  }

  if (pathMatches(pathname, ['/sites/:siteId/competitive-gap', '/sites/:siteId/competitive-gap/*'])) {
    return 'competitive-gap'
  }

  if (pathMatches(pathname, ['/sites/:siteId/gsc', '/sites/:siteId/gsc/*'])) {
    return 'gsc'
  }

  if (pathMatches(pathname, ['/sites/:siteId/crawls', '/sites/:siteId/crawls/*'])) {
    return 'crawls'
  }

  if (pathMatches(pathname, ['/sites/:siteId'])) {
    return 'overview'
  }

  return null
}

export function getActiveChangesSubsection(pathname: string) {
  if (pathMatches(pathname, ['/sites/:siteId/changes/pages'])) {
    return 'pages'
  }

  if (pathMatches(pathname, ['/sites/:siteId/changes/audit'])) {
    return 'audit'
  }

  if (pathMatches(pathname, ['/sites/:siteId/changes/opportunities'])) {
    return 'opportunities'
  }

  if (pathMatches(pathname, ['/sites/:siteId/changes/internal-linking'])) {
    return 'internal-linking'
  }

  if (pathMatches(pathname, ['/sites/:siteId/changes'])) {
    return 'overview'
  }

  return null
}

export function getActivePagesSubsection(pathname: string) {
  if (pathMatches(pathname, ['/sites/:siteId/pages/records'])) {
    return 'records'
  }

  if (pathMatches(pathname, ['/sites/:siteId/pages'])) {
    return 'overview'
  }

  return null
}

export function getActiveAuditSubsection(pathname: string) {
  if (pathMatches(pathname, ['/sites/:siteId/audit/sections'])) {
    return 'sections'
  }

  if (pathMatches(pathname, ['/sites/:siteId/audit'])) {
    return 'overview'
  }

  return null
}

export function getActiveOpportunitiesSubsection(pathname: string) {
  if (pathMatches(pathname, ['/sites/:siteId/opportunities/records'])) {
    return 'records'
  }

  if (pathMatches(pathname, ['/sites/:siteId/opportunities'])) {
    return 'overview'
  }

  return null
}

export function getActiveInternalLinkingSubsection(pathname: string) {
  if (pathMatches(pathname, ['/sites/:siteId/internal-linking/issues'])) {
    return 'issues'
  }

  if (pathMatches(pathname, ['/sites/:siteId/internal-linking'])) {
    return 'overview'
  }

  return null
}

export function getActiveCompetitiveGapSubsection(pathname: string) {
  if (pathMatches(pathname, ['/sites/:siteId/competitive-gap/strategy'])) {
    return 'strategy'
  }
  if (pathMatches(pathname, ['/sites/:siteId/competitive-gap/competitors'])) {
    return 'competitors'
  }
  if (pathMatches(pathname, ['/sites/:siteId/competitive-gap/sync'])) {
    return 'sync'
  }
  if (pathMatches(pathname, ['/sites/:siteId/competitive-gap/results'])) {
    return 'results'
  }
  if (pathMatches(pathname, ['/sites/:siteId/competitive-gap'])) {
    return 'overview'
  }
  return null
}

export function getActiveContentRecommendationsSubsection(pathname: string) {
  if (pathMatches(pathname, ['/sites/:siteId/content-recommendations/active'])) {
    return 'active'
  }

  if (pathMatches(pathname, ['/sites/:siteId/content-recommendations/implemented'])) {
    return 'implemented'
  }

  if (pathMatches(pathname, ['/sites/:siteId/content-recommendations'])) {
    return 'overview'
  }

  return null
}

export function getActiveGscSubsection(pathname: string) {
  if (pathMatches(pathname, ['/sites/:siteId/gsc/settings'])) {
    return 'settings'
  }

  if (pathMatches(pathname, ['/sites/:siteId/gsc/import'])) {
    return 'import'
  }

  if (pathMatches(pathname, ['/sites/:siteId/gsc'])) {
    return 'overview'
  }

  return null
}

export function resolveAppSectionTitle(t: TFunction, pathname: string, site: SiteDetail | null) {
  const siteLabel = site?.domain ?? null

  const title = (() => {
    if (pathname === '/' || pathname === '/sites') {
      return t('shell.routeTitles.sites')
    }

    if (pathname === '/sites/new') {
      return t('shell.routeTitles.newSite')
    }

    if (pathMatches(pathname, ['/sites/:siteId/progress'])) {
      return t('shell.routeTitles.progress')
    }

    if (pathMatches(pathname, ['/sites/:siteId/pages/records'])) {
      return t('shell.routeTitles.pagesRecords')
    }

    if (pathMatches(pathname, ['/sites/:siteId/pages'])) {
      return t('shell.routeTitles.pages')
    }

    if (pathMatches(pathname, ['/sites/:siteId/changes/pages'])) {
      return t('shell.routeTitles.changesPages')
    }

    if (pathMatches(pathname, ['/sites/:siteId/audit/sections'])) {
      return t('shell.routeTitles.auditSections')
    }

    if (pathMatches(pathname, ['/sites/:siteId/audit'])) {
      return t('shell.routeTitles.audit')
    }

    if (pathMatches(pathname, ['/sites/:siteId/changes/audit'])) {
      return t('shell.routeTitles.changesAudit')
    }

    if (pathMatches(pathname, ['/sites/:siteId/opportunities/records'])) {
      return t('shell.routeTitles.opportunitiesRecords')
    }

    if (pathMatches(pathname, ['/sites/:siteId/opportunities'])) {
      return t('shell.routeTitles.opportunities')
    }

    if (pathMatches(pathname, ['/sites/:siteId/changes/opportunities'])) {
      return t('shell.routeTitles.changesOpportunities')
    }

    if (pathMatches(pathname, ['/sites/:siteId/internal-linking/issues'])) {
      return t('shell.routeTitles.internalLinkingIssues')
    }

    if (pathMatches(pathname, ['/sites/:siteId/internal-linking'])) {
      return t('shell.routeTitles.internalLinking')
    }

    if (pathMatches(pathname, ['/sites/:siteId/changes/internal-linking'])) {
      return t('shell.routeTitles.changesInternalLinking')
    }

    if (pathMatches(pathname, ['/sites/:siteId/changes', '/sites/:siteId/changes/*'])) {
      return t('shell.routeTitles.changes')
    }

    if (pathMatches(pathname, ['/sites/:siteId/content-recommendations/active'])) {
      return t('shell.routeTitles.contentRecommendationsActive')
    }

    if (pathMatches(pathname, ['/sites/:siteId/content-recommendations/implemented'])) {
      return t('shell.routeTitles.contentRecommendationsImplemented')
    }

    if (pathMatches(pathname, ['/sites/:siteId/content-recommendations'])) {
      return t('shell.routeTitles.contentRecommendationsOverview')
    }

    if (pathMatches(pathname, ['/sites/:siteId/competitive-gap/results'])) {
      return t('competitiveGap.nav.results')
    }

    if (pathMatches(pathname, ['/sites/:siteId/competitive-gap/competitors'])) {
      return t('competitiveGap.nav.competitors')
    }

    if (pathMatches(pathname, ['/sites/:siteId/competitive-gap/sync'])) {
      return t('competitiveGap.nav.sync')
    }

    if (pathMatches(pathname, ['/sites/:siteId/competitive-gap/strategy'])) {
      return t('competitiveGap.nav.strategy')
    }

    if (pathMatches(pathname, ['/sites/:siteId/competitive-gap', '/sites/:siteId/competitive-gap/*'])) {
      return t('nav.competitiveGap')
    }

    if (pathMatches(pathname, ['/sites/:siteId/gsc/settings'])) {
      return t('shell.routeTitles.gscSettings')
    }

    if (pathMatches(pathname, ['/sites/:siteId/gsc/import'])) {
      return t('shell.routeTitles.gscImport')
    }

    if (pathMatches(pathname, ['/sites/:siteId/gsc'])) {
      return t('shell.routeTitles.gscOverview')
    }

    if (pathMatches(pathname, ['/sites/:siteId/crawls/new'])) {
      return t('shell.routeTitles.crawlsNew')
    }

    if (pathMatches(pathname, ['/sites/:siteId/crawls'])) {
      return t('shell.routeTitles.crawlsHistory')
    }

    if (pathMatches(pathname, ['/sites/:siteId'])) {
      return t('nav.overview')
    }

    if (pathname === '/jobs') {
      return t('shell.routeTitles.operations')
    }

    const jobDetailMatch = matchPath('/jobs/:jobId', pathname)
    if (jobDetailMatch?.params.jobId) {
      return t('shell.routeTitles.jobDetail', { jobId: jobDetailMatch.params.jobId })
    }

    const jobPagesMatch = matchPath('/jobs/:jobId/pages', pathname)
    if (jobPagesMatch?.params.jobId) {
      return t('shell.routeTitles.jobPages', { jobId: jobPagesMatch.params.jobId })
    }

    const jobLinksMatch = matchPath('/jobs/:jobId/links', pathname)
    if (jobLinksMatch?.params.jobId) {
      return t('shell.routeTitles.jobLinks', { jobId: jobLinksMatch.params.jobId })
    }

    const jobInternalLinkingMatch = matchPath('/jobs/:jobId/internal-linking', pathname)
    if (jobInternalLinkingMatch?.params.jobId) {
      return t('shell.routeTitles.jobInternalLinking', { jobId: jobInternalLinkingMatch.params.jobId })
    }

    const jobCannibalizationMatch = matchPath('/jobs/:jobId/cannibalization', pathname)
    if (jobCannibalizationMatch?.params.jobId) {
      return t('shell.routeTitles.jobCannibalization', { jobId: jobCannibalizationMatch.params.jobId })
    }

    const jobAuditMatch = matchPath('/jobs/:jobId/audit', pathname)
    if (jobAuditMatch?.params.jobId) {
      return t('shell.routeTitles.jobAudit', { jobId: jobAuditMatch.params.jobId })
    }

    const jobOpportunitiesMatch = matchPath('/jobs/:jobId/opportunities', pathname)
    if (jobOpportunitiesMatch?.params.jobId) {
      return t('shell.routeTitles.jobOpportunities', { jobId: jobOpportunitiesMatch.params.jobId })
    }

    const jobGscMatch = matchPath('/jobs/:jobId/gsc', pathname)
    if (jobGscMatch?.params.jobId) {
      return t('shell.routeTitles.jobGsc', { jobId: jobGscMatch.params.jobId })
    }

    const jobTrendsMatch = matchPath('/jobs/:jobId/trends', pathname)
    if (jobTrendsMatch?.params.jobId) {
      return t('shell.routeTitles.jobTrends', { jobId: jobTrendsMatch.params.jobId })
    }

    return t('routes.notFound.title')
  })()

  return siteLabel ? `${title} - ${siteLabel}` : title
}

export function buildSiteMenuItems(t: TFunction, pathname: string, site: SiteDetail): AppShellMenuItem[] {
  const context = buildSiteContext(site)
  const activeSection = getActiveSiteSection(pathname)
  const activeChangesSubsection = getActiveChangesSubsection(pathname)
  const activePagesSubsection = getActivePagesSubsection(pathname)
  const activeAuditSubsection = getActiveAuditSubsection(pathname)
  const activeOpportunitiesSubsection = getActiveOpportunitiesSubsection(pathname)
  const activeInternalLinkingSubsection = getActiveInternalLinkingSubsection(pathname)
  const activeCompetitiveGapSubsection = getActiveCompetitiveGapSubsection(pathname)
  const activeContentRecommendationsSubsection = getActiveContentRecommendationsSubsection(pathname)
  const activeGscSubsection = getActiveGscSubsection(pathname)
  const activeCrawlsSubsection = getActiveCrawlsSubsection(pathname)

  return [
    {
      key: 'overview',
      label: t('nav.overview'),
      to: buildSiteOverviewPath(site.id, context),
      active: activeSection === 'overview',
      subItems: [
        {
          label: t('nav.overview'),
          to: buildSiteOverviewPath(site.id, context),
          active: activeSection === 'overview',
        },
      ],
    },
    {
      key: 'progress',
      label: t('nav.progress'),
      to: buildSiteProgressPath(site.id, context),
      active: activeSection === 'progress',
      subItems: [
        {
          label: t('nav.progress'),
          to: buildSiteProgressPath(site.id, context),
          active: activeSection === 'progress',
        },
      ],
    },
    {
      key: 'pages',
      label: t('nav.pages'),
      to: buildSitePagesPath(site.id, context),
      active: activeSection === 'pages',
      subItems: [
        {
          label: t('nav.overview'),
          to: buildSitePagesPath(site.id, context),
          active: activeSection === 'pages' && activePagesSubsection === 'overview',
        },
        {
          label: t('sites.pages.records.navLabel'),
          to: buildSitePagesRecordsPath(site.id, context),
          active: activePagesSubsection === 'records',
        },
      ],
    },
    {
      key: 'audit',
      label: t('nav.audit'),
      to: buildSiteAuditPath(site.id, context),
      active: activeSection === 'audit',
      subItems: [
        {
          label: t('nav.overview'),
          to: buildSiteAuditPath(site.id, context),
          active: activeSection === 'audit' && activeAuditSubsection === 'overview',
        },
        {
          label: t('sites.audit.sectionsPage.navLabel'),
          to: buildSiteAuditSectionsPath(site.id, context),
          active: activeAuditSubsection === 'sections',
        },
      ],
    },
    {
      key: 'opportunities',
      label: t('nav.opportunities'),
      to: buildSiteOpportunitiesPath(site.id, context),
      active: activeSection === 'opportunities',
      subItems: [
        {
          label: t('nav.overview'),
          to: buildSiteOpportunitiesPath(site.id, context),
          active: activeSection === 'opportunities' && activeOpportunitiesSubsection === 'overview',
        },
        {
          label: t('siteOpportunities.navRecords'),
          to: buildSiteOpportunitiesRecordsPath(site.id, context),
          active: activeOpportunitiesSubsection === 'records',
        },
      ],
    },
    {
      key: 'internal-linking',
      label: t('nav.internalLinking'),
      to: buildSiteInternalLinkingPath(site.id, context),
      active: activeSection === 'internal-linking',
      subItems: [
        {
          label: t('nav.overview'),
          to: buildSiteInternalLinkingPath(site.id, context),
          active: activeSection === 'internal-linking' && activeInternalLinkingSubsection === 'overview',
        },
        {
          label: t('siteInternalLinking.navIssues'),
          to: buildSiteInternalLinkingIssuesPath(site.id, context),
          active: activeInternalLinkingSubsection === 'issues',
        },
      ],
    },
    {
      key: 'content-recommendations',
      label: t('nav.contentRecommendations'),
      to: buildSiteContentRecommendationsPath(site.id, context),
      active: activeSection === 'content-recommendations',
      subItems: [
        {
          label: t('nav.overview'),
          to: buildSiteContentRecommendationsPath(site.id, context),
          active:
            activeSection === 'content-recommendations' &&
            activeContentRecommendationsSubsection === 'overview',
        },
        {
          label: t('contentRecommendations.nav.active'),
          to: buildSiteContentRecommendationsActivePath(site.id, context),
          active: activeContentRecommendationsSubsection === 'active',
        },
        {
          label: t('contentRecommendations.nav.implemented'),
          to: buildSiteContentRecommendationsImplementedPath(site.id, context),
          active: activeContentRecommendationsSubsection === 'implemented',
        },
      ],
    },
    {
      key: 'competitive-gap',
      label: t('nav.competitiveGap'),
      to: buildSiteCompetitiveGapPath(site.id, context),
      active: activeSection === 'competitive-gap',
      subItems: [
        {
          label: t('nav.overview'),
          to: buildSiteCompetitiveGapPath(site.id, context),
          active: activeCompetitiveGapSubsection === 'overview',
        },
        {
          label: t('competitiveGap.nav.strategy'),
          to: buildSiteCompetitiveGapStrategyPath(site.id, context),
          active: activeCompetitiveGapSubsection === 'strategy',
        },
        {
          label: t('competitiveGap.nav.competitors'),
          to: buildSiteCompetitiveGapCompetitorsPath(site.id, context),
          active: activeCompetitiveGapSubsection === 'competitors',
        },
        {
          label: t('competitiveGap.nav.sync'),
          to: buildSiteCompetitiveGapSyncPath(site.id, context),
          active: activeCompetitiveGapSubsection === 'sync',
        },
        {
          label: t('competitiveGap.nav.results'),
          to: buildSiteCompetitiveGapResultsPath(site.id, context),
          active: activeCompetitiveGapSubsection === 'results',
        },
      ],
    },
    {
      key: 'gsc',
      label: t('nav.gsc'),
      to: buildSiteGscPath(site.id, context),
      active: activeSection === 'gsc',
      subItems: [
        {
          label: t('nav.overview'),
          to: buildSiteGscPath(site.id, context),
          active: activeSection === 'gsc' && activeGscSubsection === 'overview',
        },
        {
          label: t('sites.gsc.nav.settings'),
          to: buildSiteGscSettingsPath(site.id, context),
          active: activeGscSubsection === 'settings',
        },
        {
          label: t('sites.gsc.nav.import'),
          to: buildSiteGscImportPath(site.id, context),
          active: activeGscSubsection === 'import',
        },
      ],
    },
    {
      key: 'crawls',
      label: t('nav.crawls'),
      to: buildSiteCrawlsPath(site.id, context),
      active: activeSection === 'crawls',
      subItems: [
        {
          label: t('nav.crawlsHistory'),
          to: buildSiteCrawlsPath(site.id, context),
          active: activeSection === 'crawls' && activeCrawlsSubsection === 'history',
        },
        {
          label: t('nav.newCrawl'),
          to: buildSiteCrawlsNewPath(site.id, context),
          active: activeCrawlsSubsection === 'new',
        },
      ],
    },
    {
      key: 'changes',
      label: t('nav.changes'),
      to: buildSiteChangesPath(site.id, context),
      active: activeSection === 'changes',
      subItems: [
        {
          label: t('nav.overview'),
          to: buildSiteChangesPath(site.id, context),
          active: activeSection === 'changes' && activeChangesSubsection === 'overview',
        },
        {
          label: t('nav.pages'),
          to: buildSiteChangesPagesPath(site.id, context),
          active: activeChangesSubsection === 'pages',
        },
        {
          label: t('nav.audit'),
          to: buildSiteChangesAuditPath(site.id, context),
          active: activeChangesSubsection === 'audit',
        },
        {
          label: t('nav.opportunities'),
          to: buildSiteChangesOpportunitiesPath(site.id, context),
          active: activeChangesSubsection === 'opportunities',
        },
        {
          label: t('nav.internalLinking'),
          to: buildSiteChangesInternalLinkingPath(site.id, context),
          active: activeChangesSubsection === 'internal-linking',
        },
      ],
    },
  ]
}

export function buildGlobalMenuItems(t: TFunction, pathname: string): AppShellMenuItem[] {
  const soonBadge = t('common.soon')

  return [
    {
      key: 'sites',
      label: t('shell.global.sites'),
      to: '/sites',
      active: pathMatches(pathname, ['/sites', '/sites/new']),
    },
    {
      key: 'operations',
      label: t('shell.global.operations'),
      to: '/jobs',
      active: pathMatches(pathname, ['/jobs', '/jobs/:jobId', '/jobs/:jobId/*']),
    },
    {
      key: 'system',
      label: t('shell.global.systemSettings'),
      active: false,
      disabled: true,
      badge: soonBadge,
    },
    {
      key: 'account',
      label: t('shell.global.account'),
      active: false,
      disabled: true,
      badge: soonBadge,
    },
  ]
}
