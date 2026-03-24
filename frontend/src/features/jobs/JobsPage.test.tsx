import { screen, waitFor, within } from '@testing-library/react'
import { Route } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute, setTestLanguage } from '../../test/testUtils'
import { JobsPage } from './JobsPage'

afterEach(() => {
  vi.restoreAllMocks()
})

const jobsPayload = [
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
]

describe('JobsPage', () => {
  test('renders the jobs list in English by default', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse(jobsPayload))

    renderRoute(<JobsPage />, {
      path: '/jobs',
      route: '/jobs',
    })

    expect(screen.getByText('Jobs and crawl control')).toBeInTheDocument()
    expect(await screen.findByText('#12')).toBeInTheDocument()
    expect(within(screen.getByRole('table')).getAllByText('Finished').length).toBeGreaterThan(0)
    expect(within(screen.getByRole('table')).getByText('42')).toBeInTheDocument()
  })

  test('renders translated jobs UI in Polish', async () => {
    await setTestLanguage('pl')
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse(jobsPayload))

    renderRoute(<JobsPage />, {
      path: '/jobs',
      route: '/jobs',
    })

    expect(screen.getByText('Zadania i kontrola crawlowania')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Utworz zadanie crawla' })).toBeInTheDocument()
    expect(await screen.findByText('Zakonczone')).toBeInTheDocument()
    expect(screen.getByText('Filtry zadan')).toBeInTheDocument()
  })

  test('renders stage 5 render controls in the create job form', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse([]))

    renderRoute(<JobsPage />, {
      path: '/jobs',
      route: '/jobs',
      extraRoutes: [<Route key="detail" path="/jobs/:jobId" element={<div>Job detail route</div>} />],
    })

    await screen.findByText('Launch a local audit')
    expect(screen.getByLabelText('Render mode')).toBeInTheDocument()
    expect(screen.getByLabelText('Render timeout (ms)')).toHaveValue(8000)
    expect(screen.getByLabelText('Render timeout (ms)')).toHaveAttribute('min', '1000')
    expect(screen.getByLabelText('Render timeout (ms)')).toHaveAttribute('max', '60000')
    expect(screen.getByLabelText('Max depth')).toHaveValue(10)
    expect(screen.getByLabelText('Rendered pages limit')).toHaveValue(25)
  })

  test('filters the jobs list by status in the URL', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => jsonResponse(jobsPayload))
      .mockImplementationOnce(() => jsonResponse(jobsPayload))

    const { user } = renderRoute(<JobsPage />, {
      path: '/jobs',
      route: '/jobs',
      showLocation: true,
    })

    await screen.findByText('#12')
    await user.selectOptions(screen.getByLabelText('Status'), 'finished')

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('status_filter=finished'))
  })

  test('changes sorting from the jobs table header', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => jsonResponse(jobsPayload))
      .mockImplementationOnce(() => jsonResponse(jobsPayload))

    const { user } = renderRoute(<JobsPage />, {
      path: '/jobs',
      route: '/jobs',
      showLocation: true,
    })

    await screen.findByText('#12')
    await user.click(screen.getByRole('button', { name: 'Sort by Errors' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('sort_by=total_errors'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('sort_order=asc')
  })

  test('shows a clear message when the API is unavailable', async () => {
    await setTestLanguage('pl')
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('Failed to fetch'))

    renderRoute(<JobsPage />, {
      path: '/jobs',
      route: '/jobs',
    })

    expect(await screen.findByText('Nie udalo sie pobrac listy zadan')).toBeInTheDocument()
    expect(
      screen.getByText('Nie mozna polaczyc sie z API pod adresem http://localhost:8000. Sprawdz, czy backend FastAPI jest uruchomiony.'),
    ).toBeInTheDocument()
  })
})
