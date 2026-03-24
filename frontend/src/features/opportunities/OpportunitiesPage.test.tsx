import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute, setTestLanguage } from '../../test/testUtils'
import { OpportunitiesPage } from './OpportunitiesPage'

afterEach(() => {
  vi.restoreAllMocks()
})

function requestUrl(input: string | URL | RequestInfo): string {
  if (typeof input === 'string') {
    return input
  }
  if (input instanceof Request) {
    return input.url
  }
  return String(input)
}

const opportunitiesPayload = {
  crawl_job_id: 3,
  gsc_date_range: 'last_28_days',
  total_pages: 5,
  pages_with_opportunities: 4,
  high_priority_pages: 2,
  critical_priority_pages: 1,
  top_priority_pages: [
    {
      page_id: 4,
      url: 'https://example.com/high-risk',
      priority_score: 78,
      priority_level: 'critical',
      priority_rationale: 'URL already has visibility but is exposed to a high-risk indexability or canonical problem.',
      primary_opportunity_type: 'HIGH_RISK_PAGES',
      opportunity_count: 2,
      opportunity_types: ['HIGH_RISK_PAGES', 'TRAFFIC_WITH_TECHNICAL_ISSUES'],
      clicks: 12,
      impressions: 140,
      ctr: 0.0857,
      position: 5.6,
      incoming_internal_links: 3,
      incoming_internal_linking_pages: 2,
      opportunities: [
        {
          type: 'HIGH_RISK_PAGES',
          opportunity_score: 88,
          impact_level: 'high',
          effort_level: 'high',
          rationale: 'URL already has visibility but is exposed to a high-risk indexability or canonical problem.',
        },
      ],
      opportunity_score: null,
      impact_level: null,
      effort_level: null,
      rationale: 'URL already has visibility but is exposed to a high-risk indexability or canonical problem.',
    },
  ],
  groups: [
    {
      type: 'QUICK_WINS',
      count: 1,
      top_priority_score: 68,
      top_opportunity_score: 74,
      top_pages: [
        {
          page_id: 1,
          url: 'https://example.com/quick-win',
          priority_score: 68,
          priority_level: 'high',
          priority_rationale: 'URL sits in the 4-15 position range with room to improve snippet or on-page signals.',
          primary_opportunity_type: 'QUICK_WINS',
          opportunity_count: 3,
          opportunity_types: ['QUICK_WINS', 'HIGH_IMPRESSIONS_LOW_CTR', 'LOW_HANGING_FRUIT'],
          clicks: 12,
          impressions: 500,
          ctr: 0.01,
          position: 8.2,
          incoming_internal_links: 6,
          incoming_internal_linking_pages: 3,
          opportunities: [
            {
              type: 'QUICK_WINS',
              opportunity_score: 74,
              impact_level: 'high',
              effort_level: 'low',
              rationale: 'URL sits in the 4-15 position range with room to improve snippet or on-page signals.',
            },
          ],
          opportunity_score: 74,
          impact_level: 'high',
          effort_level: 'low',
          rationale: 'URL sits in the 4-15 position range with room to improve snippet or on-page signals.',
        },
      ],
    },
    {
      type: 'UNDERLINKED_OPPORTUNITIES',
      count: 1,
      top_priority_score: 31,
      top_opportunity_score: 58,
      top_pages: [
        {
          page_id: 5,
          url: 'https://example.com/underlinked',
          priority_score: 31,
          priority_level: 'medium',
          priority_rationale: 'URL shows demand but has weak internal linking support.',
          primary_opportunity_type: 'UNDERLINKED_OPPORTUNITIES',
          opportunity_count: 1,
          opportunity_types: ['UNDERLINKED_OPPORTUNITIES'],
          clicks: 4,
          impressions: 220,
          ctr: 0.018,
          position: 7.9,
          incoming_internal_links: 1,
          incoming_internal_linking_pages: 1,
          opportunities: [
            {
              type: 'UNDERLINKED_OPPORTUNITIES',
              opportunity_score: 58,
              impact_level: 'medium',
              effort_level: 'medium',
              rationale: 'URL shows demand but has weak internal linking support.',
            },
          ],
          opportunity_score: 58,
          impact_level: 'medium',
          effort_level: 'medium',
          rationale: 'URL shows demand but has weak internal linking support.',
        },
      ],
    },
  ],
}

describe('OpportunitiesPage', () => {
  test('renders opportunity groups and export links', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = requestUrl(input)
      if (url.includes('/crawl-jobs/3/opportunities')) {
        return jsonResponse(opportunitiesPayload)
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    renderRoute(<OpportunitiesPage />, {
      path: '/jobs/:jobId/opportunities',
      route: '/jobs/3/opportunities?opportunity_type=QUICK_WINS&priority_score_min=45&sort_by=count&top_pages_limit=3',
    })

    expect(screen.getByText('Opportunities for job #3')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Quick wins' }, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Underlinked opportunities' })).toBeInTheDocument()
    expect(screen.getByText('URL shows demand but has weak internal linking support.')).toBeInTheDocument()

    expect(screen.getByRole('link', { name: 'Export pages with priority' })).toHaveAttribute(
      'href',
      expect.stringContaining('opportunity_type=QUICK_WINS'),
    )
    expect(screen.getByRole('link', { name: 'Export pages with priority' })).toHaveAttribute(
      'href',
      expect.not.stringContaining('sort_by=count'),
    )
    expect(screen.getByRole('link', { name: 'Export opportunities CSV' })).toHaveAttribute(
      'href',
      expect.not.stringContaining('top_pages_limit=3'),
    )
  })

  test('renders translated rationale and traffic labels in Polish', async () => {
    await setTestLanguage('pl')

    const localizedPayload = {
      ...opportunitiesPayload,
      top_priority_pages: [
        {
          ...opportunitiesPayload.top_priority_pages[0],
          priority_rationale:
            'URL sits in the 4-15 position range with room to improve snippet or on-page signals: 4003 impressions, 60 clicks, CTR 1.50%, position 11.4; issues: duplicate content, meta description too short.',
          rationale:
            'URL sits in the 4-15 position range with room to improve snippet or on-page signals: 4003 impressions, 60 clicks, CTR 1.50%, position 11.4; issues: duplicate content, meta description too short.',
          clicks: 60,
          impressions: 4003,
          ctr: 0.015,
          position: 11.4,
        },
      ],
      groups: [
        {
          ...opportunitiesPayload.groups[0],
          top_pages: [
            {
              ...opportunitiesPayload.groups[0].top_pages[0],
              rationale:
                'URL sits in the 4-15 position range with room to improve snippet or on-page signals: 4003 impressions, 60 clicks, CTR 1.50%, position 11.4; issues: duplicate content, meta description too short.',
              clicks: 60,
              impressions: 4003,
              ctr: 0.015,
              position: 11.4,
            },
          ],
        },
      ],
    }

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = requestUrl(input)
      if (url.includes('/crawl-jobs/3/opportunities')) {
        return jsonResponse(localizedPayload)
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    renderRoute(<OpportunitiesPage />, {
      path: '/jobs/:jobId/opportunities',
      route: '/jobs/3/opportunities',
    })

    expect(await screen.findByText('Szanse dla zadania #3')).toBeInTheDocument()
    expect((await screen.findAllByText('Klikniecia: 60')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Wyswietlenia: 4003').length).toBeGreaterThan(0)
    expect(
      screen.getAllByText(
        'URL jest w zakresie pozycji 4-15 i ma przestrzen do poprawy snippetu lub sygnalow on-page: 4003 wyswietlen, 60 klikniec, CTR 1.50%, pozycja 11.4; problemy: zduplikowana tresc, zbyt krotki meta description.',
      ).length,
    ).toBeGreaterThan(0)
  })

  test('quick filters and deep links keep opportunity state in the URL', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => jsonResponse(opportunitiesPayload))
      .mockImplementationOnce(() => jsonResponse(opportunitiesPayload))
      .mockImplementationOnce(() => jsonResponse(opportunitiesPayload))

    const { user } = renderRoute(<OpportunitiesPage />, {
      path: '/jobs/:jobId/opportunities',
      route: '/jobs/3/opportunities',
      showLocation: true,
    })

    await screen.findByRole('heading', { name: 'Quick wins' }, { timeout: 5000 })
    await user.click(screen.getByRole('button', { name: 'High priority' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('priority_score_min=45'))

    await user.click(screen.getByRole('button', { name: 'Quick wins' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('opportunity_type=QUICK_WINS'))
    expect(screen.getAllByRole('link', { name: 'Show in Pages' })[1]).toHaveAttribute(
      'href',
      expect.stringContaining('/jobs/3/pages?gsc_date_range=last_28_days&sort_by=priority_score&sort_order=desc&opportunity_type=QUICK_WINS'),
    )
  })
})
