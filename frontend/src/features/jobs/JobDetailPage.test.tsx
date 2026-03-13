import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute } from '../../test/testUtils'
import { JobDetailPage } from './JobDetailPage'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('JobDetailPage', () => {
  test('stops a running job', async () => {
    const runningJob = {
      id: 7,
      site_id: 1,
      status: 'running',
      created_at: '2026-03-13T12:00:00Z',
      started_at: '2026-03-13T12:01:00Z',
      finished_at: null,
      settings_json: { start_url: 'https://example.com' },
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
    expect(await screen.findByText('stopped')).toBeInTheDocument()
  })
})
