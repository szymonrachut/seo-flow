import { screen } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute } from '../../test/testUtils'
import { AuditPage } from './AuditPage'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AuditPage', () => {
  test('renders audit summary and issue sections', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() =>
      jsonResponse({
        crawl_job_id: 8,
        summary: {
          total_pages: 10,
          pages_missing_title: 1,
          pages_missing_meta_description: 2,
          pages_missing_h1: 1,
          pages_duplicate_title_groups: 1,
          pages_duplicate_meta_description_groups: 0,
          broken_internal_links: 1,
          unresolved_internal_targets: 0,
          redirecting_internal_links: 1,
          non_indexable_like_signals: 2,
        },
        pages_missing_title: [
          {
            page_id: 1,
            url: 'https://example.com/no-title',
            normalized_url: 'https://example.com/no-title',
            status_code: 200,
            title: null,
          },
        ],
        pages_missing_meta_description: [],
        pages_missing_h1: [],
        pages_duplicate_title: [],
        pages_duplicate_meta_description: [],
        broken_internal_links: [],
        unresolved_internal_targets: [],
        redirecting_internal_links: [],
        non_indexable_like_signals: [],
      }),
    )

    renderRoute(<AuditPage />, {
      path: '/jobs/:jobId/audit',
      route: '/jobs/8/audit',
    })

    expect(await screen.findByText('Technical audit for job #8')).toBeInTheDocument()
    expect(await screen.findByText('Pages missing title')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('https://example.com/no-title')).toBeInTheDocument()
  })

  test('shows the error state when audit fetch fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('Network down'))

    renderRoute(<AuditPage />, {
      path: '/jobs/:jobId/audit',
      route: '/jobs/8/audit',
    })

    expect(await screen.findByText('Audit request failed')).toBeInTheDocument()
    expect(screen.getByText('Network down')).toBeInTheDocument()
  })
})
