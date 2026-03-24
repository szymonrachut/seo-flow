import { SitePagesWorkspaceView } from './SitePagesWorkspaceView'
import { useSiteWorkspaceContext } from '../sites/context'

export function SitePagesRecordsPage() {
  const { site } = useSiteWorkspaceContext()

  return <SitePagesWorkspaceView site={site} mode="records" />
}
