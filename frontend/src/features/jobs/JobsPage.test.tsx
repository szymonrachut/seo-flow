import { screen, waitFor } from '@testing-library/react'
import { Route } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { renderRoute, jsonResponse } from '../../test/testUtils'
import { JobsPage } from './JobsPage'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('JobsPage', () => {
  test('renders the jobs list', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() =>
      jsonResponse([
        {
          id: 12,
          status: 'finished',
          root_url: 'https://example.com',
          created_at: '2026-03-13T12:00:00Z',
          started_at: '2026-03-13T12:01:00Z',
          finished_at: '2026-03-13T12:05:00Z',
          total_pages: 15,
          total_internal_links: 42,
          total_external_links: 9,
          total_errors: 1,
        },
      ]),
    )

    renderRoute(<JobsPage />, {
      path: '/jobs',
      route: '/jobs',
    })

    expect(screen.getByText('Jobs and crawl control')).toBeInTheDocument()
    expect(await screen.findByText('#12')).toBeInTheDocument()
    expect(screen.getByText('finished')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  test('creates a new crawl job and navigates to the detail route', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (method === 'POST' && url.includes('/crawl-jobs')) {
        return jsonResponse({ id: 77 })
      }

      if (method === 'GET' && url.includes('/crawl-jobs')) {
        return jsonResponse([])
      }

      throw new Error(`Unexpected request: ${method} ${url}`)
    })

    const { user } = renderRoute(<JobsPage />, {
      path: '/jobs',
      route: '/jobs',
      extraRoutes: [<Route key="detail" path="/jobs/:jobId" element={<div>Job detail route</div>} />],
    })

    await user.clear(await screen.findByLabelText('Root URL'))
    await user.type(screen.getByLabelText('Root URL'), 'https://site.test')
    await user.clear(screen.getByLabelText('Max URLs'))
    await user.type(screen.getByLabelText('Max URLs'), '120')
    await user.click(screen.getByRole('button', { name: 'Create crawl job' }))

    expect(await screen.findByText('Job detail route')).toBeInTheDocument()
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) => String(input).includes('/crawl-jobs') && (init?.method ?? 'GET') === 'POST',
        ),
      ).toBe(true),
    )

    const postCall = fetchMock.mock.calls.find(
      ([input, init]) => String(input).includes('/crawl-jobs') && (init?.method ?? 'GET') === 'POST',
    )

    expect(postCall).toBeDefined()
    expect(String(postCall?.[1]?.body)).toContain('"root_url":"https://site.test"')
  })
})
