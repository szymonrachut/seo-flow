import { SitePagesWorkspaceView } from './SitePagesWorkspaceView'
import { useSiteWorkspaceContext } from '../sites/context'

export function SitePagesOverviewPage() {
  const { site } = useSiteWorkspaceContext()

  return <SitePagesWorkspaceView site={site} mode="overview" />
}
