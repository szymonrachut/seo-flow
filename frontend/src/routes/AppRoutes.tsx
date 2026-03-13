import { Navigate, Route, Routes } from 'react-router-dom'

import { EmptyState } from '../components/EmptyState'
import { AuditPage } from '../features/audit/AuditPage'
import { JobDetailPage } from '../features/jobs/JobDetailPage'
import { JobsPage } from '../features/jobs/JobsPage'
import { LinksPage } from '../features/links/LinksPage'
import { PagesPage } from '../features/pages/PagesPage'
import { AppLayout } from '../layouts/AppLayout'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate replace to="/jobs" />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        <Route path="/jobs/:jobId/pages" element={<PagesPage />} />
        <Route path="/jobs/:jobId/links" element={<LinksPage />} />
        <Route path="/jobs/:jobId/audit" element={<AuditPage />} />
        <Route
          path="*"
          element={
            <EmptyState
              title="Route not found"
              description="This local console does not know the route you requested."
            />
          }
        />
      </Route>
    </Routes>
  )
}
