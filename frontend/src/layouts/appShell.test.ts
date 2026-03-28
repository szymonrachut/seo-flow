import { describe, expect, test } from 'vitest'

import i18n from '../i18n'
import type { SiteDetail } from '../types/api'
import {
  getActiveAuditSubsection,
  getActiveCrawlsSubsection,
  buildSiteMenuItems,
  getActiveChangesSubsection,
  getActiveContentRecommendationsSubsection,
  getActiveCompetitiveGapSubsection,
  getActiveGscSubsection,
  getActiveInternalLinkingSubsection,
  getActiveOpportunitiesSubsection,
  getActivePagesSubsection,
  getActiveSiteSection,
  resolveAppSectionTitle,
} from './appShell'

const site: SiteDetail = {
  id: 5,
  domain: 'example.com',
  root_url: 'https://example.com',
  created_at: '2026-03-10T12:00:00Z',
  selected_gsc_property_uri: null,
  selected_gsc_property_permission_level: null,
  summary: {
    total_crawls: 2,
    pending_crawls: 0,
    running_crawls: 0,
    finished_crawls: 2,
    failed_crawls: 0,
    stopped_crawls: 0,
    first_crawl_at: '2026-03-10T12:00:00Z',
    last_crawl_at: '2026-03-14T12:00:00Z',
  },
  active_crawl_id: 11,
  baseline_crawl_id: 10,
  active_crawl: null,
  baseline_crawl: null,
  crawl_history: [],
}

describe('appShell changes navigation', () => {
  test('treats canonical /changes/* routes as the active compare section', async () => {
    await i18n.changeLanguage('en')

    expect(getActiveSiteSection('/sites/5/changes/pages')).toBe('changes')
    expect(getActiveChangesSubsection('/sites/5/changes/pages')).toBe('pages')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/changes/pages', site)).toBe('Pages Changes - example.com')
  })

  test('builds the Changes submenu with canonical /changes/* targets', async () => {
    await i18n.changeLanguage('en')

    const menuItems = buildSiteMenuItems(i18n.t.bind(i18n), '/sites/5/changes/opportunities', site)
    const changesItem = menuItems.find((item) => item.key === 'changes')

    expect(changesItem).toBeDefined()
    expect(changesItem?.active).toBe(true)
    expect(changesItem?.subItems?.map((item) => item.to)).toEqual([
      '/sites/5/changes?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/changes/pages?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/changes/audit?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/changes/opportunities?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/changes/internal-linking?active_crawl_id=11&baseline_crawl_id=10',
    ])
    expect(changesItem?.subItems?.find((item) => item.label === 'SEO Opportunities')?.active).toBe(true)
  })

  test('treats top-level pages and audit as current-state sections', async () => {
    await i18n.changeLanguage('en')

    expect(getActiveSiteSection('/sites/5/pages')).toBe('pages')
    expect(getActivePagesSubsection('/sites/5/pages/records')).toBe('records')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/pages', site)).toBe('Pages - example.com')

    expect(getActiveSiteSection('/sites/5/audit')).toBe('audit')
    expect(getActiveAuditSubsection('/sites/5/audit/sections')).toBe('sections')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/audit/sections', site)).toBe('Audit Sections - example.com')

    const menuItems = buildSiteMenuItems(i18n.t.bind(i18n), '/sites/5/pages/records', site)
    const pagesItem = menuItems.find((item) => item.key === 'pages')
    const auditItem = menuItems.find((item) => item.key === 'audit')

    expect(pagesItem?.subItems?.map((item) => item.to)).toEqual([
      '/sites/5/pages?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/pages/records?active_crawl_id=11&baseline_crawl_id=10',
    ])
    expect(auditItem?.subItems?.map((item) => item.to)).toEqual([
      '/sites/5/audit?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/audit/sections?active_crawl_id=11&baseline_crawl_id=10',
    ])
  })

  test('treats top-level opportunities and internal linking as current-state sections', async () => {
    await i18n.changeLanguage('en')

    expect(getActiveSiteSection('/sites/5/opportunities')).toBe('opportunities')
    expect(getActiveOpportunitiesSubsection('/sites/5/opportunities/records')).toBe('records')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/opportunities', site)).toBe('SEO Opportunities - example.com')

    expect(getActiveSiteSection('/sites/5/internal-linking')).toBe('internal-linking')
    expect(getActiveInternalLinkingSubsection('/sites/5/internal-linking/issues')).toBe('issues')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/internal-linking/issues', site)).toBe('Internal Linking Issues - example.com')

    const menuItems = buildSiteMenuItems(i18n.t.bind(i18n), '/sites/5/opportunities/records', site)
    const opportunitiesItem = menuItems.find((item) => item.key === 'opportunities')
    const internalLinkingItem = menuItems.find((item) => item.key === 'internal-linking')

    expect(opportunitiesItem?.disabled).toBeFalsy()
    expect(opportunitiesItem?.subItems?.map((item) => item.to)).toEqual([
      '/sites/5/opportunities?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/opportunities/records?active_crawl_id=11&baseline_crawl_id=10',
    ])
    expect(internalLinkingItem?.disabled).toBeFalsy()
    expect(internalLinkingItem?.subItems?.map((item) => item.to)).toEqual([
      '/sites/5/internal-linking?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/internal-linking/issues?active_crawl_id=11&baseline_crawl_id=10',
    ])
  })

  test('treats GSC overview, settings and import as site-level subsections', async () => {
    await i18n.changeLanguage('en')

    expect(getActiveSiteSection('/sites/5/gsc')).toBe('gsc')
    expect(getActiveGscSubsection('/sites/5/gsc')).toBe('overview')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/gsc', site)).toBe('GSC Overview - example.com')

    expect(getActiveGscSubsection('/sites/5/gsc/settings')).toBe('settings')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/gsc/settings', site)).toBe('GSC Settings - example.com')

    expect(getActiveGscSubsection('/sites/5/gsc/import')).toBe('import')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/gsc/import', site)).toBe('GSC Import - example.com')

    const menuItems = buildSiteMenuItems(i18n.t.bind(i18n), '/sites/5/gsc/import', site)
    const gscItem = menuItems.find((item) => item.key === 'gsc')

    expect(gscItem?.subItems?.map((item) => item.to)).toEqual([
      '/sites/5/gsc?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/gsc/settings?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/gsc/import?active_crawl_id=11&baseline_crawl_id=10',
    ])
    expect(gscItem?.subItems?.find((item) => item.label === 'Import')?.active).toBe(true)
  })

  test('treats crawls history and new crawl as dedicated site-level subsections', async () => {
    await i18n.changeLanguage('en')

    expect(getActiveSiteSection('/sites/5/crawls')).toBe('crawls')
    expect(getActiveCrawlsSubsection('/sites/5/crawls')).toBe('history')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/crawls', site)).toBe('Crawl History - example.com')

    expect(getActiveCrawlsSubsection('/sites/5/crawls/new')).toBe('new')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/crawls/new', site)).toBe('New Crawl - example.com')

    const menuItems = buildSiteMenuItems(i18n.t.bind(i18n), '/sites/5/crawls/new', site)
    const crawlsItem = menuItems.find((item) => item.key === 'crawls')

    expect(crawlsItem?.subItems?.map((item) => item.to)).toEqual([
      '/sites/5/crawls?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/crawls/new?active_crawl_id=11&baseline_crawl_id=10',
    ])
    expect(crawlsItem?.subItems?.find((item) => item.label === 'New Crawl')?.active).toBe(true)
  })

  test('treats content recommendations overview, active and implemented as site-level subsections', async () => {
    await i18n.changeLanguage('en')

    expect(getActiveSiteSection('/sites/5/content-recommendations')).toBe('content-recommendations')
    expect(getActiveContentRecommendationsSubsection('/sites/5/content-recommendations')).toBe('overview')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/content-recommendations', site)).toBe(
      'Content Recommendations Overview - example.com',
    )

    expect(getActiveContentRecommendationsSubsection('/sites/5/content-recommendations/active')).toBe('active')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/content-recommendations/active', site)).toBe(
      'Active Content Recommendations - example.com',
    )

    expect(getActiveContentRecommendationsSubsection('/sites/5/content-recommendations/implemented')).toBe('implemented')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/content-recommendations/implemented', site)).toBe(
      'Implemented Content Recommendations - example.com',
    )

    const menuItems = buildSiteMenuItems(i18n.t.bind(i18n), '/sites/5/content-recommendations/implemented', site)
    const item = menuItems.find((menuItem) => menuItem.key === 'content-recommendations')

    expect(item?.subItems?.map((subItem) => subItem.to)).toEqual([
      '/sites/5/content-recommendations?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/content-recommendations/active?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10',
    ])
    expect(item?.subItems?.find((subItem) => subItem.label === 'Implemented')?.active).toBe(true)
  })

  test('treats competitive gap and semstorm routes as site-level subsections', async () => {
    await i18n.changeLanguage('en')

    expect(getActiveSiteSection('/sites/5/competitive-gap')).toBe('competitive-gap')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/competitive-gap', site)).toBe(
      'Competitive Gap - example.com',
    )

    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/competitive-gap/strategy', site)).toBe(
      'Strategy Brief - example.com',
    )
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/competitive-gap/competitors', site)).toBe(
      'Competitor Selection - example.com',
    )
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/competitive-gap/sync', site)).toBe(
      'Synchronization - example.com',
    )
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/competitive-gap/results', site)).toBe(
      'Results - example.com',
    )
    expect(getActiveCompetitiveGapSubsection('/sites/5/competitive-gap/semstorm/discovery')).toBe('semstorm-discovery')
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/competitive-gap/semstorm/discovery', site)).toBe(
      'Semstorm Discovery - example.com',
    )
    expect(resolveAppSectionTitle(i18n.t.bind(i18n), '/sites/5/competitive-gap/semstorm/execution', site)).toBe(
      'Semstorm Execution - example.com',
    )

    const menuItems = buildSiteMenuItems(i18n.t.bind(i18n), '/sites/5/competitive-gap/semstorm/plans', site)
    const item = menuItems.find((menuItem) => menuItem.key === 'competitive-gap')

    expect(item?.subItems?.map((subItem) => subItem.to)).toEqual([
      '/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/strategy?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/competitors?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/sync?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/results?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/semstorm/discovery?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/semstorm/opportunities?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/semstorm/promoted?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/semstorm/plans?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/semstorm/execution?active_crawl_id=11&baseline_crawl_id=10',
      '/sites/5/competitive-gap/semstorm/implemented?active_crawl_id=11&baseline_crawl_id=10',
    ])
    expect(item?.subItems?.find((subItem) => subItem.label === 'Semstorm Plans')?.active).toBe(true)
  })
})
