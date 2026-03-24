import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute, setTestLanguage } from '../../test/testUtils'
import { AuditPage } from './AuditPage'

afterEach(() => {
  vi.restoreAllMocks()
})

const auditPayload = {
  crawl_job_id: 8,
  summary: {
    total_pages: 10,
    pages_missing_title: 1,
    pages_title_too_short: 2,
    pages_title_too_long: 1,
    pages_missing_meta_description: 2,
    pages_meta_description_too_short: 1,
    pages_meta_description_too_long: 1,
    pages_missing_h1: 1,
    pages_multiple_h1: 1,
    pages_missing_h2: 2,
    pages_missing_canonical: 1,
    pages_self_canonical: 4,
    pages_canonical_to_other_url: 3,
    pages_canonical_to_non_200: 1,
    pages_canonical_to_redirect: 1,
    pages_noindex_like: 1,
    pages_non_indexable_like: 2,
    pages_duplicate_title_groups: 1,
    pages_duplicate_meta_description_groups: 1,
    pages_thin_content: 2,
    pages_duplicate_content_groups: 1,
    pages_with_missing_alt_images: 1,
    pages_with_no_images: 1,
    oversized_pages: 1,
    js_heavy_like_pages: 1,
    rendered_pages: 1,
    pages_with_render_errors: 1,
    pages_with_schema: 1,
    pages_missing_schema: 9,
    pages_with_x_robots_tag: 1,
    pages_with_schema_types_summary: 1,
    broken_internal_links: 1,
    unresolved_internal_targets: 1,
    redirecting_internal_links: 1,
    internal_links_to_noindex_like_pages: 1,
    internal_links_to_canonicalized_pages: 1,
    redirect_chains_internal: 1,
  },
  pages_missing_title: [
    {
      page_id: 1,
      url: 'https://example.com/no-title',
      normalized_url: 'https://example.com/no-title',
      final_url: 'https://example.com/no-title',
      status_code: 200,
      title: null,
      title_length: null,
    },
  ],
  pages_title_too_short: [
    {
      page_id: 2,
      url: 'https://example.com/short-title',
      normalized_url: 'https://example.com/short-title',
      final_url: 'https://example.com/short-title',
      status_code: 200,
      title: 'Short',
      title_length: 5,
    },
  ],
  pages_title_too_long: [],
  pages_missing_meta_description: [],
  pages_meta_description_too_short: [],
  pages_meta_description_too_long: [],
  pages_missing_h1: [],
  pages_multiple_h1: [],
  pages_missing_h2: [],
  pages_missing_canonical: [],
  pages_self_canonical: [],
  pages_canonical_to_other_url: [],
  pages_canonical_to_non_200: [],
  pages_canonical_to_redirect: [],
  pages_noindex_like: [],
  pages_non_indexable_like: [],
  pages_duplicate_title: [
    {
      value: 'Shared title',
      count: 2,
      pages: [
        {
          page_id: 11,
          url: 'https://example.com/a',
          normalized_url: 'https://example.com/a',
          status_code: 200,
          title: 'Shared title',
        },
        {
          page_id: 12,
          url: 'https://example.com/b',
          normalized_url: 'https://example.com/b',
          status_code: 200,
          title: 'Shared title',
        },
      ],
    },
  ],
  pages_duplicate_meta_description: [
    {
      value: 'Shared meta',
      count: 2,
      pages: [
        {
          page_id: 21,
          url: 'https://example.com/c',
          normalized_url: 'https://example.com/c',
          status_code: 200,
          meta_description: 'Shared meta',
        },
        {
          page_id: 22,
          url: 'https://example.com/d',
          normalized_url: 'https://example.com/d',
          status_code: 200,
          meta_description: 'Shared meta',
        },
      ],
    },
  ],
  pages_thin_content: [],
  pages_duplicate_content: [
    {
      value: 'hash-shared',
      count: 2,
      pages: [
        {
          page_id: 61,
          url: 'https://example.com/e',
          normalized_url: 'https://example.com/e',
          status_code: 200,
          content_text_hash: 'hash-shared',
        },
        {
          page_id: 62,
          url: 'https://example.com/f',
          normalized_url: 'https://example.com/f',
          status_code: 200,
          content_text_hash: 'hash-shared',
        },
      ],
    },
  ],
  js_heavy_like_pages: [
    {
      page_id: 71,
      url: 'https://example.com/js-shell',
      normalized_url: 'https://example.com/js-shell',
      status_code: 200,
      js_heavy_like: true,
    },
  ],
  rendered_pages: [
    {
      page_id: 72,
      url: 'https://example.com/rendered',
      normalized_url: 'https://example.com/rendered',
      status_code: 200,
      was_rendered: true,
    },
  ],
  pages_with_render_errors: [
    {
      page_id: 73,
      url: 'https://example.com/render-error',
      normalized_url: 'https://example.com/render-error',
      status_code: 200,
      render_error_message: 'Navigation timeout',
    },
  ],
  pages_with_schema: [
    {
      page_id: 74,
      url: 'https://example.com/schema',
      normalized_url: 'https://example.com/schema',
      status_code: 200,
      schema_present: true,
      schema_types_json: ['Article'],
    },
  ],
  pages_missing_schema: [
    {
      page_id: 75,
      url: 'https://example.com/no-schema',
      normalized_url: 'https://example.com/no-schema',
      status_code: 200,
      schema_present: false,
    },
  ],
  pages_with_x_robots_tag: [
    {
      page_id: 76,
      url: 'https://example.com/xrobots',
      normalized_url: 'https://example.com/xrobots',
      status_code: 200,
      x_robots_tag: 'noindex',
    },
  ],
  pages_with_schema_types_summary: [
    {
      value: 'Article',
      count: 1,
      pages: [
        {
          page_id: 74,
          url: 'https://example.com/schema',
          normalized_url: 'https://example.com/schema',
          status_code: 200,
          schema_types_json: ['Article'],
        },
      ],
    },
  ],
  pages_with_missing_alt_images: [],
  pages_with_no_images: [],
  oversized_pages: [],
  broken_internal_links: [
    {
      link_id: 31,
      source_url: 'https://example.com/start',
      target_url: 'https://example.com/404',
      target_normalized_url: 'https://example.com/404',
      target_status_code: 404,
      final_url: 'https://example.com/404',
      signals: ['broken_internal'],
    },
  ],
  unresolved_internal_targets: [],
  redirecting_internal_links: [],
  internal_links_to_noindex_like_pages: [
    {
      link_id: 51,
      source_url: 'https://example.com/start',
      target_url: 'https://example.com/private',
      target_normalized_url: 'https://example.com/private',
      target_status_code: 200,
      final_url: 'https://example.com/private',
      signals: ['to_noindex_like'],
    },
  ],
  internal_links_to_canonicalized_pages: [],
  redirect_chains_internal: [],
}

describe('AuditPage', () => {
  test('renders audit summary and issue sections', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse(auditPayload))

    renderRoute(<AuditPage />, {
      path: '/jobs/:jobId/audit',
      route: '/jobs/8/audit',
    })

    expect(await screen.findByText('Technical audit for job #8')).toBeInTheDocument()
    expect(await screen.findByText('Pages missing title')).toBeInTheDocument()
    expect(await screen.findByText('Pages with short title')).toBeInTheDocument()
    expect(await screen.findByText('Rendered pages')).toBeInTheDocument()
    expect(await screen.findByText('Pages with schema')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getAllByText('https://example.com/no-title').length).toBeGreaterThan(0)
  })

  test('renders translated audit UI in Polish', async () => {
    await setTestLanguage('pl')
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse(auditPayload))

    renderRoute(<AuditPage />, {
      path: '/jobs/:jobId/audit',
      route: '/jobs/8/audit',
    })

    expect(await screen.findByText('Audyt techniczny dla zadania #8')).toBeInTheDocument()
    expect(await screen.findByText('Strony bez title')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Pokaz w Stronach' }).length).toBeGreaterThan(0)
  }, 15000)

  test('deep-links from audit to pages and links views', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse(auditPayload))

    renderRoute(<AuditPage />, {
      path: '/jobs/:jobId/audit',
      route: '/jobs/8/audit',
    })

    const pageLinks = await screen.findAllByRole('link', { name: 'Show in Pages' })
    const linkLinks = screen.getAllByRole('link', { name: 'Show in Links' })

    expect(pageLinks.some((element) => element.getAttribute('href')?.includes('/jobs/8/pages?has_title=false'))).toBe(true)
    expect(linkLinks.some((element) => element.getAttribute('href')?.includes('/jobs/8/links?broken_internal=true'))).toBe(true)
    expect(pageLinks.some((element) => element.getAttribute('href')?.includes('title_exact=Shared+title'))).toBe(true)
    expect(pageLinks.some((element) => element.getAttribute('href')?.includes('title_too_short=true'))).toBe(true)
    expect(pageLinks.some((element) => element.getAttribute('href')?.includes('was_rendered=true'))).toBe(true)
    expect(pageLinks.some((element) => element.getAttribute('href')?.includes('schema_present=true'))).toBe(true)
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

  test('sorts audit tables locally from the header controls', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() =>
      jsonResponse({
        ...auditPayload,
        summary: {
          ...auditPayload.summary,
          pages_missing_title: 2,
        },
        pages_missing_title: [
          {
            page_id: 1,
            url: 'https://example.com/zeta',
            normalized_url: 'https://example.com/zeta',
            status_code: 200,
            title: null,
          },
          {
            page_id: 2,
            url: 'https://example.com/alpha',
            normalized_url: 'https://example.com/alpha',
            status_code: 404,
            title: null,
          },
        ],
      }),
    )

    const { user } = renderRoute(<AuditPage />, {
      path: '/jobs/:jobId/audit',
      route: '/jobs/8/audit',
    })

    await screen.findByText('Technical audit for job #8')
    const statusButtons = screen.getAllByRole('button', { name: 'Sort by Status' })
    await user.click(statusButtons[0])
    await user.click(statusButtons[0])

    await waitFor(() => {
      const rows = screen.getAllByRole('table')[0].querySelectorAll('tr')
      expect(rows[1]).toHaveTextContent('https://example.com/alpha')
      expect(rows[2]).toHaveTextContent('https://example.com/zeta')
    })
  })
})
