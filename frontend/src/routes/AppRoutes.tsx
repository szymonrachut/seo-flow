import { Navigate, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { EmptyState } from '../components/EmptyState'
import { AuditPage } from '../features/audit/AuditPage'
import { SiteAuditComparePage } from '../features/audit/SiteAuditComparePage'
import { SiteAuditOverviewPage, SiteAuditSectionsPage } from '../features/audit/SiteAuditWorkspacePage'
import { CannibalizationPage } from '../features/cannibalization/CannibalizationPage'
import { SiteContentRecommendationsPage } from '../features/content-recommendations/SiteContentRecommendationsPage'
import {
  SiteCompetitiveGapCompetitorsPage,
  SiteCompetitiveGapOverviewPage,
  SiteCompetitiveGapResultsPage,
  SiteCompetitiveGapSyncPage,
  SiteCompetitiveGapStrategyPage,
} from '../features/competitive-gap/SiteCompetitiveGapPage'
import {
  SiteCompetitiveGapSemstormBriefsPage,
  SiteCompetitiveGapSemstormDiscoveryPage,
  SiteCompetitiveGapSemstormExecutionPage,
  SiteCompetitiveGapSemstormImplementedPage,
  SiteCompetitiveGapSemstormOpportunitiesPage,
  SiteCompetitiveGapSemstormPlansPage,
  SiteCompetitiveGapSemstormPromotedPage,
} from '../features/competitive-gap/SiteCompetitiveGapSemstormPage'
import { GscPage } from '../features/gsc/GscPage'
import { SiteGscPage } from '../features/gsc/SiteGscPage'
import { InternalLinkingPage } from '../features/internal-linking/InternalLinkingPage'
import { SiteInternalLinkingCurrentPage } from '../features/internal-linking/SiteInternalLinkingCurrentPage'
import { SiteInternalLinkingComparePage } from '../features/internal-linking/SiteInternalLinkingComparePage'
import { JobDetailPage } from '../features/jobs/JobDetailPage'
import { JobsPage } from '../features/jobs/JobsPage'
import { LinksPage } from '../features/links/LinksPage'
import { OpportunitiesPage } from '../features/opportunities/OpportunitiesPage'
import { SiteOpportunitiesCurrentPage } from '../features/opportunities/SiteOpportunitiesCurrentPage'
import { SiteOpportunitiesComparePage } from '../features/opportunities/SiteOpportunitiesComparePage'
import { PagesPage } from '../features/pages/PagesPage'
import { SitePagesComparePage } from '../features/pages/SitePagesComparePage'
import { SitePagesOverviewPage } from '../features/pages/SitePagesOverviewPage'
import { SitePagesRecordsPage } from '../features/pages/SitePagesRecordsPage'
import { SiteCrawlsPage } from '../features/sites/SiteCrawlsPage'
import { SiteChangesHubPage } from '../features/sites/SiteChangesHubPage'
import { NewSitePage } from '../features/sites/NewSitePage'
import { SiteNewCrawlPage } from '../features/sites/SiteNewCrawlPage'
import { SiteOverviewPage } from '../features/sites/SiteOverviewPage'
import { SiteProgressPage } from '../features/sites/SiteProgressPage'
import { SitesPage } from '../features/sites/SitesPage'
import { SiteWorkspaceLayout } from '../features/sites/SiteWorkspaceLayout'
import { TrendsPage } from '../features/trends/TrendsPage'
import { AppLayout } from '../layouts/AppLayout'

export function AppRoutes() {
  const { t } = useTranslation()

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate replace to="/sites" />} />
        <Route path="/sites" element={<SitesPage />} />
        <Route path="/sites/new" element={<NewSitePage />} />
        <Route path="/sites/:siteId" element={<SiteWorkspaceLayout />}>
          <Route index element={<SiteOverviewPage />} />
          <Route path="progress" element={<SiteProgressPage />} />
          <Route path="crawls">
            <Route index element={<SiteCrawlsPage />} />
            <Route path="new" element={<SiteNewCrawlPage />} />
          </Route>
          <Route path="changes">
            <Route index element={<SiteChangesHubPage />} />
            <Route path="pages" element={<SitePagesComparePage />} />
            <Route path="audit" element={<SiteAuditComparePage />} />
            <Route path="opportunities" element={<SiteOpportunitiesComparePage />} />
            <Route path="internal-linking" element={<SiteInternalLinkingComparePage />} />
          </Route>
          <Route path="pages">
            <Route index element={<SitePagesOverviewPage />} />
            <Route path="records" element={<SitePagesRecordsPage />} />
          </Route>
          <Route path="content-recommendations">
            <Route index element={<SiteContentRecommendationsPage />} />
            <Route path="active" element={<SiteContentRecommendationsPage mode="active" />} />
            <Route path="implemented" element={<SiteContentRecommendationsPage mode="implemented" />} />
          </Route>
          <Route path="competitive-gap">
            <Route index element={<SiteCompetitiveGapOverviewPage />} />
            <Route path="strategy" element={<SiteCompetitiveGapStrategyPage />} />
            <Route path="competitors" element={<SiteCompetitiveGapCompetitorsPage />} />
            <Route path="sync" element={<SiteCompetitiveGapSyncPage />} />
            <Route path="results" element={<SiteCompetitiveGapResultsPage />} />
            <Route path="semstorm" element={<Navigate replace to="discovery" />} />
            <Route path="semstorm/discovery" element={<SiteCompetitiveGapSemstormDiscoveryPage />} />
            <Route path="semstorm/opportunities" element={<SiteCompetitiveGapSemstormOpportunitiesPage />} />
            <Route path="semstorm/promoted" element={<SiteCompetitiveGapSemstormPromotedPage />} />
            <Route path="semstorm/plans" element={<SiteCompetitiveGapSemstormPlansPage />} />
            <Route path="semstorm/briefs" element={<SiteCompetitiveGapSemstormBriefsPage />} />
            <Route path="semstorm/execution" element={<SiteCompetitiveGapSemstormExecutionPage />} />
            <Route path="semstorm/implemented" element={<SiteCompetitiveGapSemstormImplementedPage />} />
          </Route>
          <Route path="audit">
            <Route index element={<SiteAuditOverviewPage />} />
            <Route path="sections" element={<SiteAuditSectionsPage />} />
          </Route>
          <Route path="opportunities">
            <Route index element={<SiteOpportunitiesCurrentPage />} />
            <Route path="records" element={<SiteOpportunitiesCurrentPage mode="records" />} />
          </Route>
          <Route path="internal-linking">
            <Route index element={<SiteInternalLinkingCurrentPage />} />
            <Route path="issues" element={<SiteInternalLinkingCurrentPage mode="issues" />} />
          </Route>
          <Route path="gsc">
            <Route index element={<SiteGscPage />} />
            <Route path="settings" element={<SiteGscPage mode="settings" />} />
            <Route path="import" element={<SiteGscPage mode="import" />} />
          </Route>
        </Route>
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        <Route path="/jobs/:jobId/pages" element={<PagesPage />} />
        <Route path="/jobs/:jobId/links" element={<LinksPage />} />
        <Route path="/jobs/:jobId/internal-linking" element={<InternalLinkingPage />} />
        <Route path="/jobs/:jobId/cannibalization" element={<CannibalizationPage />} />
        <Route path="/jobs/:jobId/audit" element={<AuditPage />} />
        <Route path="/jobs/:jobId/opportunities" element={<OpportunitiesPage />} />
        <Route path="/jobs/:jobId/gsc" element={<GscPage />} />
        <Route path="/jobs/:jobId/trends" element={<TrendsPage />} />
        <Route
          path="*"
          element={
            <EmptyState
              title={t('routes.notFound.title')}
              description={t('routes.notFound.description')}
            />
          }
        />
      </Route>
    </Routes>
  )
}
