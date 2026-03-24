import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import i18n, { LANGUAGE_STORAGE_KEY } from '../i18n'
import { THEME_STORAGE_KEY } from '../theme'
import { createTestQueryClient, jsonResponse, syncTestLanguageFromStorage } from '../test/testUtils'
import { AppLayout } from './AppLayout'

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

afterEach(() => {
  vi.restoreAllMocks()
})

async function renderLayout() {
  vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = String(input)
    if (url.includes('/sites')) {
      return jsonResponse(sitesPayload)
    }

    throw new Error(`Unexpected request: ${url}`)
  })

  await syncTestLanguageFromStorage()
  const queryClient = createTestQueryClient()
  const user = userEvent.setup()

  return {
    user,
    ...render(
      <I18nextProvider i18n={i18n}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/jobs']}>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/jobs" element={<div>Jobs content</div>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </I18nextProvider>,
    ),
  }
}

describe('AppLayout', () => {
  test('renders the sticky shell in English by default', async () => {
    await renderLayout()

    expect(screen.getByText('SEO Flow')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Operations' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('link', { name: 'Add Site' })).toHaveAttribute('href', '/sites/new')
  })

  test('switches the shell language to Polish and stores the choice', async () => {
    const view = await renderLayout()

    await view.user.click(screen.getByRole('button', { name: 'Polski' }))

    expect(await screen.findByRole('heading', { name: 'Operacje' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Polski' })).toHaveAttribute('aria-pressed', 'true')
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('pl')
  })

  test('switches the theme to dark and stores the choice', async () => {
    const view = await renderLayout()

    await view.user.click(screen.getByRole('button', { name: 'Dark' }))

    expect(screen.getByRole('button', { name: 'Dark' })).toHaveAttribute('aria-pressed', 'true')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(document.documentElement).toHaveClass('dark')
  })

  test('keeps the selected language after remount', async () => {
    const firstRender = await renderLayout()

    await firstRender.user.click(screen.getByRole('button', { name: 'Polski' }))
    expect(await screen.findByRole('heading', { name: 'Operacje' })).toBeInTheDocument()
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('pl')

    firstRender.unmount()
    await i18n.changeLanguage('en')
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, 'pl')
    await syncTestLanguageFromStorage()

    await renderLayout()

    expect(await screen.findByRole('heading', { name: 'Operacje' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Polski' })).toHaveAttribute('aria-pressed', 'true')
  })
})
