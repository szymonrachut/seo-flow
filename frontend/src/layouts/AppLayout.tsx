import { Outlet, useLocation, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useSiteDetailQuery, useSitesQuery } from '../features/sites/api'
import { parseIntegerParam } from '../utils/searchParams'
import { AppHeader } from './AppHeader'
import { AppSidebar } from './AppSidebar'
import {
  buildGlobalMenuItems,
  buildSiteMenuItems,
  parseSiteIdFromPathname,
  resolveAppSectionTitle,
} from './appShell'

export function AppLayout() {
  const { t } = useTranslation()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const siteId = parseSiteIdFromPathname(location.pathname)
  const requestedActiveCrawlId = parseIntegerParam(searchParams.get('active_crawl_id'), undefined)
  const requestedBaselineCrawlId = parseIntegerParam(searchParams.get('baseline_crawl_id'), undefined)

  const sitesQuery = useSitesQuery()
  const selectedSiteQuery = useSiteDetailQuery(
    siteId ?? 0,
    {
      active_crawl_id: requestedActiveCrawlId,
      baseline_crawl_id: requestedBaselineCrawlId,
    },
    {
      enabled: siteId !== null,
    },
  )

  const selectedSite = selectedSiteQuery.data ?? null
  const sectionTitle = resolveAppSectionTitle(t, location.pathname, selectedSite)
  const siteMenuItems = selectedSite ? buildSiteMenuItems(t, location.pathname, selectedSite) : []
  const globalMenuItems = buildGlobalMenuItems(t, location.pathname)

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(20,184,166,0.12),transparent_28%),linear-gradient(180deg,#f7f2ea_0%,#f3f1ec_100%)] dark:bg-[radial-gradient(circle_at_top_left,rgba(45,212,191,0.12),transparent_24%),linear-gradient(180deg,#020617_0%,#0f172a_100%)]">
      <AppHeader sectionTitle={sectionTitle} />

      <div className="flex flex-col gap-6 py-6 md:flex-row md:items-start">
        <AppSidebar
          sites={sitesQuery.data ?? []}
          sitesLoading={sitesQuery.isLoading}
          sitesError={sitesQuery.isError}
          siteMenuItems={siteMenuItems}
          globalMenuItems={globalMenuItems}
          selectedSite={selectedSite}
          selectedSiteId={siteId}
        />

        <main className="min-w-0 px-4 sm:px-6 lg:px-8 md:flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
