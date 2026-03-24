import { screen } from '@testing-library/react'
import { Route } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute } from '../../test/testUtils'
import { SitesPage } from './SitesPage'

afterEach(() => {
  vi.restoreAllMocks()
})

const sitesPayload = [
  {
    id: 5,
    domain: 'example.com',
    root_url: 'https://example.com',
    created_at: '2026-03-14T12:00:00Z',
    selected_gsc_property_uri: 'sc-domain:example.com',
    summary: {
      total_crawls: 2,
      pending_crawls: 0,
      running_crawls: 1,
      finished_crawls: 1,
      failed_crawls: 0,
      stopped_crawls: 0,
      first_crawl_at: '2026-03-13T12:00:00Z',
      last_crawl_at: '2026-03-14T12:00:00Z',
    },
    latest_crawl: {
      id: 11,
      site_id: 5,
      status: 'running',
      root_url: 'https://example.com',
      created_at: '2026-03-14T12:00:00Z',
      started_at: '2026-03-14T12:01:00Z',
      finished_at: null,
      total_pages: 42,
      total_internal_links: 210,
      total_external_links: 12,
      total_errors: 1,
    },
  },
]

describe('SitesPage', () => {
  test('renders sites list and redirects a new crawl into the site workspace', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (method === 'GET' && url.includes('/sites')) {
        return jsonResponse(sitesPayload)
      }

      if (method === 'POST' && url.includes('/crawl-jobs')) {
        return jsonResponse({ id: 77, site_id: 5 })
      }

      throw new Error(`Unexpected request: ${method} ${url}`)
    })

    const { user } = renderRoute(<SitesPage />, {
      path: '/sites',
      route: '/sites',
      extraRoutes: [<Route key="workspace" path="/sites/:siteId" element={<div>Site workspace route</div>} />],
    })

    expect(screen.getByText('Sites and workspaces')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Add site' })).toHaveAttribute('href', '/sites/new')
    expect(await screen.findByText('example.com')).toBeInTheDocument()
    expect(screen.getByText('sc-domain:example.com')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Root URL'))
    await user.type(screen.getByLabelText('Root URL'), 'https://example.com/blog')
    await user.click(screen.getByRole('button', { name: 'Create crawl job' }))

    expect(await screen.findByText('Site workspace route')).toBeInTheDocument()
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) => String(input).includes('/crawl-jobs') && (init?.method ?? 'GET') === 'POST',
      ),
    ).toBe(true)
  }, 15000)
})
