import { Navigate, useLocation, useParams } from 'react-router-dom'

import {
  buildSiteChangesInternalLinkingPath,
  buildSiteChangesOpportunitiesPath,
} from './routes'

type LegacyCompareSection = 'opportunities' | 'internal-linking'

interface SiteCompareLegacyRedirectProps {
  section: LegacyCompareSection
}

export function SiteCompareLegacyRedirect({ section }: SiteCompareLegacyRedirectProps) {
  const { siteId } = useParams()
  const location = useLocation()
  const parsedSiteId = siteId ? Number(siteId) : null

  if (!parsedSiteId || !Number.isInteger(parsedSiteId)) {
    return <Navigate replace to="/sites" />
  }

  const targetPath =
    section === 'opportunities'
      ? buildSiteChangesOpportunitiesPath(parsedSiteId)
      : buildSiteChangesInternalLinkingPath(parsedSiteId)

  return <Navigate replace to={`${targetPath}${location.search}${location.hash}`} />
}
