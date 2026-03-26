import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import i18n from '../../i18n'
import { createTestQueryClient, jsonResponse, setTestLanguage } from '../../test/testUtils'
import type {
  GenerateSiteContentGeneratorAssetsResponse,
  SiteContentGeneratorAsset,
} from '../../types/api'
import { SiteContentGeneratorSection } from './SiteContentGeneratorSection'

const { copyText } = vi.hoisted(() => ({
  copyText: vi.fn().mockResolvedValue(true),
}))

vi.mock('../../utils/clipboard', () => ({
  copyText,
}))

afterEach(() => {
  vi.restoreAllMocks()
  copyText.mockReset()
  copyText.mockResolvedValue(true)
})

beforeEach(async () => {
  await setTestLanguage('en')
})

function buildAsset(overrides: Partial<SiteContentGeneratorAsset> = {}): SiteContentGeneratorAsset {
  return {
    site_id: 5,
    has_assets: true,
    can_regenerate: true,
    active_crawl_id: 11,
    active_crawl_status: 'finished',
    status: 'ready',
    basis_crawl_job_id: 11,
    surfer_custom_instructions: 'Use grounded, factual language only.',
    seowriting_details_to_include: 'Mention the verified offer, audience, and tone.',
    introductory_hook_brief: 'Lead with a precise problem statement and stay concrete.',
    source_urls: ['https://example.com/', 'https://example.com/contact'],
    source_pages_hash: 'hash-123',
    prompt_version: 'content-generator-assets-v1',
    llm_provider: 'openai',
    llm_model: 'gpt-5.4-mini',
    generated_at: '2026-03-26T12:00:00Z',
    last_error_code: null,
    last_error_message: null,
    ...overrides,
  }
}

function renderSection() {
  const queryClient = createTestQueryClient()
  const user = userEvent.setup()

  return {
    user,
    ...render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <SiteContentGeneratorSection siteId={5} activeCrawlId={11} activeCrawlStatus="finished" />
      </QueryClientProvider>
    </I18nextProvider>,
    ),
  }
}

function mockContentGeneratorFetch({
  getResponses,
  postResponses = [],
}: {
  getResponses: SiteContentGeneratorAsset[]
  postResponses?: GenerateSiteContentGeneratorAssetsResponse[]
}) {
  const remainingGets = [...getResponses]
  const remainingPosts = [...postResponses]

  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
    const method = init?.method ?? (input instanceof Request ? input.method : 'GET')

    if (url.includes('/sites/5/content-generator-assets/generate') && method.toUpperCase() === 'POST') {
      const payload = remainingPosts.shift()
      if (!payload) {
        throw new Error(`Unexpected POST request in SiteContentGeneratorSection.test.tsx: ${url}`)
      }
      return jsonResponse(payload)
    }

    if (url.includes('/sites/5/content-generator-assets') && method.toUpperCase() === 'GET') {
      const payload = remainingGets.shift()
      if (!payload) {
        throw new Error(`Unexpected GET request in SiteContentGeneratorSection.test.tsx: ${url}`)
      }
      return jsonResponse(payload)
    }

    throw new Error(`Unhandled fetch in SiteContentGeneratorSection.test.tsx: ${method} ${url}`)
  })
}

describe('SiteContentGeneratorSection', () => {
  test('renders ready assets with metadata, source URLs and copyable blocks', async () => {
    mockContentGeneratorFetch({
      getResponses: [buildAsset()],
    })

    renderSection()

    expect(await screen.findByText('Surfer Custom Instructions')).toBeInTheDocument()
    expect(screen.getByText('Instructions for content generators')).toBeInTheDocument()
    expect(screen.getByText('SEO Writing.ai - Details to Include')).toBeInTheDocument()
    expect(screen.getByText('Introductory Hook Brief')).toBeInTheDocument()
    expect(screen.getAllByText(/^Length:/).length).toBe(3)
    expect(screen.getByText('gpt-5.4-mini')).toBeInTheDocument()
    expect(screen.getByText('Source URLs (2)')).toBeInTheDocument()
    expect(screen.getByText('hash-123')).toBeInTheDocument()
  })

  test.each(['pending', 'running'] as const)('renders busy state for asset status=%s', async (status) => {
    mockContentGeneratorFetch({
      getResponses: [
        buildAsset({
          status,
          generated_at: null,
          surfer_custom_instructions: null,
          seowriting_details_to_include: null,
          introductory_hook_brief: null,
        }),
      ],
    })

    renderSection()

    expect(await screen.findByText('Instructions are being prepared')).toBeInTheDocument()
    expect(screen.getByText('The current site-level asset is being generated from crawl #11.')).toBeInTheDocument()
  })

  test('renders empty state when the site has no assets yet', async () => {
    mockContentGeneratorFetch({
      getResponses: [
        buildAsset({
          has_assets: false,
          status: null,
          basis_crawl_job_id: null,
          surfer_custom_instructions: null,
          seowriting_details_to_include: null,
          introductory_hook_brief: null,
          source_urls: [],
          source_pages_hash: null,
          prompt_version: null,
          llm_provider: null,
          llm_model: null,
          generated_at: null,
        }),
      ],
    })

    renderSection()

    expect(await screen.findByText('No generator instructions yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generate instructions for content generators' })).toBeInTheDocument()
  })

  test('renders failed state with diagnostics and retry action', async () => {
    mockContentGeneratorFetch({
      getResponses: [
        buildAsset({
          status: 'failed',
          surfer_custom_instructions: null,
          seowriting_details_to_include: null,
          introductory_hook_brief: null,
          last_error_code: 'LLM_TIMEOUT',
          last_error_message: 'The model timed out during generation.',
        }),
      ],
    })

    renderSection()

    expect(await screen.findByText('Instruction generation failed')).toBeInTheDocument()
    expect(screen.getByText('The model timed out during generation.')).toBeInTheDocument()
    expect(screen.getByText('LLM_TIMEOUT')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try generating instructions again' })).toBeInTheDocument()
  })

  test('copies block content to clipboard', async () => {
    mockContentGeneratorFetch({
      getResponses: [buildAsset()],
    })

    const view = renderSection()

    expect(await screen.findByText('Surfer Custom Instructions')).toBeInTheDocument()
    await view.user.click(screen.getAllByRole('button', { name: 'Copy' })[0])

    expect(copyText).toHaveBeenCalledWith('Use grounded, factual language only.')
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument()
  })

  test('regenerates assets and refreshes the GET payload after a successful POST', async () => {
    const refreshedAsset = buildAsset({
      surfer_custom_instructions: 'Refreshed instructions based on the latest crawl.',
      seowriting_details_to_include: 'Refreshed details block.',
      introductory_hook_brief: 'Refreshed hook brief.',
      source_pages_hash: 'hash-456',
    })

    const fetchMock = mockContentGeneratorFetch({
      getResponses: [buildAsset(), refreshedAsset],
      postResponses: [
        {
          success: true,
          generation_triggered: true,
          asset: refreshedAsset,
          error_code: null,
          error_message: null,
        },
      ],
    })

    const view = renderSection()

    expect(await screen.findByText('Use grounded, factual language only.')).toBeInTheDocument()
    await view.user.click(screen.getByRole('button', { name: 'Generate instructions for content generators again' }))

    await screen.findByText('Refreshed instructions based on the latest crawl.')
    expect(screen.getByText('hash-456')).toBeInTheDocument()

    const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(postCall?.[1]?.body).toBe(JSON.stringify({ output_language: 'en' }))
  })

  test('shows failed state when POST returns 200 but business success is false', async () => {
    const failedAsset = buildAsset({
      status: 'failed',
      surfer_custom_instructions: null,
      seowriting_details_to_include: null,
      introductory_hook_brief: null,
      last_error_code: 'generation_failed',
      last_error_message: 'The model returned a policy-safe failure.',
    })

    mockContentGeneratorFetch({
      getResponses: [
        buildAsset({
          has_assets: false,
          status: null,
          basis_crawl_job_id: null,
          surfer_custom_instructions: null,
          seowriting_details_to_include: null,
          introductory_hook_brief: null,
          source_urls: [],
          source_pages_hash: null,
          prompt_version: null,
          llm_provider: null,
          llm_model: null,
          generated_at: null,
        }),
        failedAsset,
      ],
      postResponses: [
        {
          success: false,
          generation_triggered: true,
          asset: failedAsset,
          error_code: 'generation_failed',
          error_message: 'The model returned a policy-safe failure.',
        },
      ],
    })

    const view = renderSection()

    expect(await screen.findByText('No generator instructions yet')).toBeInTheDocument()
    await view.user.click(screen.getByRole('button', { name: 'Generate instructions for content generators' }))

    await waitFor(() => {
      expect(screen.getByText('Instruction generation failed')).toBeInTheDocument()
    })
    expect(screen.getByText('The model returned a policy-safe failure.')).toBeInTheDocument()
  })
})
