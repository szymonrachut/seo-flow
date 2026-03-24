import { screen, waitFor } from '@testing-library/react'
import { Route } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute } from '../../test/testUtils'
import { JobDetailPage } from './JobDetailPage'

afterEach(() => {
  vi.restoreAllMocks()
})

const runningJob = {
  id: 7,
  site_id: 1,
  status: 'running',
  created_at: '2026-03-13T12:00:00Z',
  started_at: '2026-03-13T12:01:00Z',
  finished_at: null,
  settings_json: {
    start_url: 'https://example.com',
    max_urls: 500,
    max_depth: 3,
    delay: 0.25,
    request_delay: 0.25,
    render_mode: 'auto',
    render_timeout_ms: 8000,
    max_rendered_pages_per_job: 25,
  },
  stats_json: {},
  summary_counts: {
    total_pages: 4,
    total_links: 8,
    total_internal_links: 6,
    total_external_links: 2,
    pages_missing_title: 1,
    pages_missing_meta_description: 1,
    pages_missing_h1: 1,
    pages_non_indexable_like: 2,
    rendered_pages: 1,
    js_heavy_like_pages: 2,
    pages_with_render_errors: 1,
    pages_with_schema: 1,
    pages_with_x_robots_tag: 1,
    pages_with_gsc_28d: 2,
    pages_with_gsc_90d: 3,
    gsc_opportunities_28d: 1,
    gsc_opportunities_90d: 2,
    broken_internal_links: 1,
    redirecting_internal_links: 1,
  },
  progress: {
    visited_pages: 4,
    queued_urls: 2,
    discovered_links: 8,
    internal_links: 6,
    external_links: 2,
    errors_count: 1,
  },
}

describe('JobDetailPage', () => {
  test('stops a running job', async () => {
    const stoppedJob = {
      ...runningJob,
      status: 'stopped',
      finished_at: '2026-03-13T12:04:00Z',
      stats_json: { stop_requested: true },
      progress: {
        ...runningJob.progress,
        queued_urls: 0,
      },
    }

    let stopRequested = false

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (method === 'POST' && url.includes('/crawl-jobs/7/stop')) {
        stopRequested = true
        return jsonResponse(stoppedJob)
      }

      if (method === 'GET' && url.includes('/crawl-jobs/7')) {
        return jsonResponse(stopRequested ? stoppedJob : runningJob)
      }

      throw new Error(`Unexpected request: ${method} ${url}`)
    })

    const { user } = renderRoute(<JobDetailPage />, {
      path: '/jobs/:jobId',
      route: '/jobs/7',
    })

    await user.click(await screen.findByRole('button', { name: 'Stop job' }))

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) => String(input).includes('/crawl-jobs/7/stop') && (init?.method ?? 'GET') === 'POST',
        ),
      ).toBe(true),
    )
    expect(await screen.findByText('Stopped')).toBeInTheDocument()
  })

  test('duplicates the job config and navigates to the new job', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (method === 'POST' && url.includes('/crawl-jobs') && !url.includes('/stop')) {
        return jsonResponse({ id: 77, site_id: 1 })
      }

      if (method === 'GET' && url.includes('/crawl-jobs/7')) {
        return jsonResponse(runningJob)
      }

      throw new Error(`Unexpected request: ${method} ${url}`)
    })

    const { user } = renderRoute(<JobDetailPage />, {
      path: '/jobs/:jobId',
      route: '/jobs/7',
      extraRoutes: [<Route key="detail" path="/sites/:siteId" element={<div>Site workspace route</div>} />],
    })

    await user.click(await screen.findByRole('button', { name: 'Run again with same settings' }))

    expect(await screen.findByText('Site workspace route')).toBeInTheDocument()
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
    const body = JSON.parse(String(postCall?.[1]?.body))
    expect(body).toMatchObject({
      render_mode: 'auto',
      render_timeout_ms: 8000,
      max_rendered_pages_per_job: 25,
    })
  })
})
