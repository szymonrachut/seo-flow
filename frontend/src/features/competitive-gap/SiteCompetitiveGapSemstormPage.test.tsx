import { QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Navigate, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import i18n from '../../i18n'
import { createTestQueryClient, jsonResponse, setTestLanguage } from '../../test/testUtils'
import type {
  SemstormBriefEnrichmentRunsResponse,
  SemstormBriefItem,
  SemstormBriefsResponse,
  SemstormExecutionResponse,
  SemstormImplementedResponse,
  SemstormPlansResponse,
  SemstormPromotedItemsResponse,
} from '../../types/api'
import { SiteWorkspaceLayout } from '../sites/SiteWorkspaceLayout'
import {
  SiteCompetitiveGapSemstormBriefsPage,
  SiteCompetitiveGapSemstormDiscoveryPage,
  SiteCompetitiveGapSemstormExecutionPage,
  SiteCompetitiveGapSemstormImplementedPage,
  SiteCompetitiveGapSemstormOpportunitiesPage,
  SiteCompetitiveGapSemstormPlansPage,
  SiteCompetitiveGapSemstormPromotedPage,
} from './SiteCompetitiveGapSemstormPage'

afterEach(() => {
  vi.restoreAllMocks()
})

beforeEach(async () => {
  await setTestLanguage('en')
})

const sitePayload = {
  id: 5,
  domain: 'example.com',
  root_url: 'https://example.com',
  created_at: '2026-03-20T10:00:00Z',
  selected_gsc_property_uri: 'sc-domain:example.com',
  selected_gsc_property_permission_level: 'siteOwner',
  summary: {
    total_crawls: 2,
    pending_crawls: 0,
    running_crawls: 0,
    finished_crawls: 2,
    failed_crawls: 0,
    stopped_crawls: 0,
    first_crawl_at: '2026-03-18T10:00:00Z',
    last_crawl_at: '2026-03-20T10:00:00Z',
  },
  active_crawl_id: 11,
  baseline_crawl_id: 10,
  active_crawl: {
    id: 11,
    site_id: 5,
    status: 'finished',
    created_at: '2026-03-20T10:00:00Z',
    started_at: '2026-03-20T10:01:00Z',
    finished_at: '2026-03-20T10:12:00Z',
    settings_json: { start_url: 'https://example.com' },
    stats_json: {},
    summary_counts: {
      total_pages: 42,
      total_links: 200,
      total_internal_links: 160,
      total_external_links: 40,
      pages_missing_title: 1,
      pages_missing_meta_description: 2,
      pages_missing_h1: 1,
      pages_non_indexable_like: 0,
      rendered_pages: 4,
      js_heavy_like_pages: 1,
      pages_with_render_errors: 0,
      pages_with_schema: 5,
      pages_with_x_robots_tag: 0,
      pages_with_gsc_28d: 20,
      pages_with_gsc_90d: 22,
      gsc_opportunities_28d: 4,
      gsc_opportunities_90d: 5,
      broken_internal_links: 0,
      redirecting_internal_links: 0,
    },
    progress: {
      visited_pages: 42,
      queued_urls: 0,
      discovered_links: 200,
      internal_links: 160,
      external_links: 40,
      errors_count: 0,
    },
  },
  baseline_crawl: {
    id: 10,
    site_id: 5,
    status: 'finished',
    created_at: '2026-03-18T10:00:00Z',
    started_at: '2026-03-18T10:01:00Z',
    finished_at: '2026-03-18T10:08:00Z',
    settings_json: { start_url: 'https://example.com' },
    stats_json: {},
    summary_counts: {
      total_pages: 40,
      total_links: 180,
      total_internal_links: 145,
      total_external_links: 35,
      pages_missing_title: 2,
      pages_missing_meta_description: 3,
      pages_missing_h1: 1,
      pages_non_indexable_like: 0,
      rendered_pages: 3,
      js_heavy_like_pages: 1,
      pages_with_render_errors: 0,
      pages_with_schema: 4,
      pages_with_x_robots_tag: 0,
      pages_with_gsc_28d: 18,
      pages_with_gsc_90d: 20,
      gsc_opportunities_28d: 3,
      gsc_opportunities_90d: 4,
      broken_internal_links: 0,
      redirecting_internal_links: 0,
    },
    progress: {
      visited_pages: 40,
      queued_urls: 0,
      discovered_links: 180,
      internal_links: 145,
      external_links: 35,
      errors_count: 0,
    },
  },
  crawl_history: [
    {
      id: 11,
      site_id: 5,
      status: 'finished',
      root_url: 'https://example.com',
      created_at: '2026-03-20T10:00:00Z',
      started_at: '2026-03-20T10:01:00Z',
      finished_at: '2026-03-20T10:12:00Z',
      total_pages: 42,
      total_internal_links: 160,
      total_external_links: 40,
      total_errors: 0,
    },
    {
      id: 10,
      site_id: 5,
      status: 'finished',
      root_url: 'https://example.com',
      created_at: '2026-03-18T10:00:00Z',
      started_at: '2026-03-18T10:01:00Z',
      finished_at: '2026-03-18T10:08:00Z',
      total_pages: 40,
      total_internal_links: 145,
      total_external_links: 35,
      total_errors: 0,
    },
  ],
}

const discoveryRunsPayload = [
  {
    id: 1,
    site_id: 5,
    run_id: 1,
    status: 'completed',
    stage: 'completed',
    source_domain: 'example.com',
    params: {
      max_competitors: 10,
      max_keywords_per_competitor: 25,
      result_type: 'organic',
      include_basic_stats: true,
      competitors_type: 'all',
    },
    summary: {
      total_competitors: 2,
      total_queries: 5,
      unique_keywords: 4,
      created_at: '2026-03-21T10:00:00Z',
    },
    error_code: null,
    error_message_safe: null,
    started_at: '2026-03-21T10:00:00Z',
    finished_at: '2026-03-21T10:00:02Z',
    created_at: '2026-03-21T10:00:00Z',
    updated_at: '2026-03-21T10:00:02Z',
  },
]

const discoveryRunDetailPayload = {
  ...discoveryRunsPayload[0],
  competitors: [
    {
      rank: 1,
      domain: 'competitor-a.com',
      common_keywords: 32,
      traffic: 140,
      queries_count: 3,
      basic_stats: {
        keywords: 120,
        keywords_top: 12,
        traffic: 140,
        traffic_potential: 200,
        search_volume: 1000,
        search_volume_top: 220,
      },
      top_queries: [
        {
          keyword: 'seo audit checklist',
          position: 2,
          position_change: 1,
          url: 'https://competitor-a.com/seo-audit-checklist',
          traffic: 80,
          traffic_change: 5,
          volume: 1200,
          competitors: 4,
          cpc: 2.7,
          trends: [1, 2, 3],
        },
      ],
    },
  ],
}

const opportunitiesPayload = {
  site_id: 5,
  run_id: 1,
  source_domain: 'example.com',
  active_crawl_id: 11,
  summary: {
    total_items: 2,
    bucket_counts: {
      quick_win: 1,
      core_opportunity: 1,
      watchlist: 0,
    },
    decision_type_counts: {
      create_new_page: 1,
      expand_existing_page: 1,
      monitor_only: 0,
    },
    coverage_status_counts: {
      missing: 1,
      weak_coverage: 1,
      covered: 0,
    },
    state_counts: {
      new: 2,
      accepted: 0,
      dismissed: 0,
      promoted: 0,
    },
    total_competitors: 2,
    total_queries: 5,
    unique_keywords: 4,
    created_at: '2026-03-21T10:00:00Z',
  },
  items: [
    {
      keyword: 'seo audit checklist',
      competitor_count: 2,
      best_position: 2,
      max_traffic: 80,
      max_volume: 1200,
      avg_cpc: 2.7,
      bucket: 'core_opportunity',
      decision_type: 'create_new_page',
      opportunity_score_v1: 88,
      opportunity_score_v2: 93,
      coverage_status: 'missing',
      coverage_score_v1: 10,
      matched_pages_count: 0,
      best_match_page: null,
      gsc_signal_status: 'none',
      gsc_summary: null,
      state_status: 'new',
      state_note: null,
      can_promote: true,
      can_dismiss: true,
      can_accept: true,
      sample_competitors: ['competitor-a.com', 'competitor-b.com'],
    },
    {
      keyword: 'technical seo guide',
      competitor_count: 2,
      best_position: 5,
      max_traffic: 35,
      max_volume: 500,
      avg_cpc: 1.8,
      bucket: 'quick_win',
      decision_type: 'expand_existing_page',
      opportunity_score_v1: 66,
      opportunity_score_v2: 72,
      coverage_status: 'weak_coverage',
      coverage_score_v1: 48,
      matched_pages_count: 1,
      best_match_page: {
        page_id: 101,
        url: 'https://example.com/technical-seo',
        title: 'Technical SEO Basics',
        match_signals: ['title', 'url'],
      },
      gsc_signal_status: 'present',
      gsc_summary: {
        clicks: 12,
        impressions: 240,
        ctr: 0.05,
        avg_position: 16.4,
      },
      state_status: 'new',
      state_note: null,
      can_promote: true,
      can_dismiss: true,
      can_accept: true,
      sample_competitors: ['competitor-a.com'],
    },
  ],
}

const promotedPayload: SemstormPromotedItemsResponse = {
  site_id: 5,
  summary: {
    total_items: 1,
    promotion_status_counts: {
      active: 1,
      archived: 0,
    },
  },
  items: [
    {
      id: 91,
      site_id: 5,
      opportunity_key: 'semstorm:abc123',
      source_run_id: 1,
      keyword: 'seo audit checklist',
      normalized_keyword: 'seo audit checklist',
      bucket: 'core_opportunity',
      decision_type: 'create_new_page',
      opportunity_score_v2: 93,
      coverage_status: 'missing',
      best_match_page_url: null,
      gsc_signal_status: 'none',
      promotion_status: 'active',
      has_plan: true,
      plan_id: 301,
      plan_state_status: 'planned',
      created_at: '2026-03-21T12:00:00Z',
      updated_at: '2026-03-21T12:00:00Z',
    },
  ],
}

const plansPayload: SemstormPlansResponse = {
  site_id: 5,
  summary: {
    total_count: 1,
    state_counts: {
      planned: 1,
      in_progress: 0,
      done: 0,
      archived: 0,
    },
    target_page_type_counts: {
      new_page: 1,
      expand_existing: 0,
      refresh_existing: 0,
      cluster_support: 0,
    },
  },
  items: [
    {
      id: 301,
      site_id: 5,
      promoted_item_id: 91,
      keyword: 'seo audit checklist',
      normalized_keyword: 'seo audit checklist',
      source_run_id: 1,
      state_status: 'planned',
      decision_type_snapshot: 'create_new_page',
      bucket_snapshot: 'core_opportunity',
      coverage_status_snapshot: 'missing',
      opportunity_score_v2_snapshot: 93,
      best_match_page_url_snapshot: null,
      gsc_signal_status_snapshot: 'none',
      plan_title: 'Create page for seo audit checklist',
      plan_note: null,
      target_page_type: 'new_page',
      proposed_slug: 'seo-audit-checklist',
      proposed_primary_keyword: 'seo audit checklist',
      proposed_secondary_keywords: ['audit checklist'],
      has_brief: true,
      brief_id: 401,
      brief_state_status: 'draft',
      created_at: '2026-03-21T13:00:00Z',
      updated_at: '2026-03-21T13:00:00Z',
    },
  ],
}

const briefsPayload: SemstormBriefsResponse = {
  site_id: 5,
  summary: {
    total_count: 1,
    state_counts: {
      draft: 1,
      ready: 0,
      in_execution: 0,
      completed: 0,
      archived: 0,
    },
    brief_type_counts: {
      new_page: 1,
      expand_existing: 0,
      refresh_existing: 0,
      cluster_support: 0,
    },
    intent_counts: {
      informational: 0,
      commercial: 0,
      transactional: 1,
      navigational: 0,
      mixed: 0,
    },
  },
  items: [
    {
      id: 401,
      site_id: 5,
      plan_item_id: 301,
      brief_title: 'New page brief: SEO Audit Checklist',
      primary_keyword: 'seo audit checklist',
      brief_type: 'new_page',
      search_intent: 'transactional',
      state_status: 'draft',
      execution_status: 'draft',
      assignee: null,
      execution_note: null,
      ready_at: null,
      started_at: null,
      completed_at: null,
      archived_at: null,
      implementation_status: null,
      implemented_at: null,
      last_outcome_checked_at: null,
      recommended_page_title: 'SEO Audit Checklist | Pricing and Options',
      proposed_url_slug: 'seo-audit-checklist',
      decision_type_snapshot: 'create_new_page',
      bucket_snapshot: 'core_opportunity',
      coverage_status_snapshot: 'missing',
      gsc_signal_status_snapshot: 'none',
      opportunity_score_v2_snapshot: 93,
      created_at: '2026-03-21T14:00:00Z',
      updated_at: '2026-03-21T14:00:00Z',
    },
  ],
}

const briefDetailPayload: SemstormBriefItem = {
  ...briefsPayload.items[0],
  secondary_keywords: ['audit checklist'],
  target_url_existing: null,
  implementation_url_override: null,
  evaluation_note: null,
  recommended_h1: 'SEO Audit Checklist',
  content_goal: 'Create a practical execution packet for a new SEO audit checklist page.',
  angle_summary: 'Use the brief to package a transactional checklist topic into a clean execution packet.',
  sections: ['Introduction', 'Checklist', 'Pricing', 'FAQs'],
  internal_link_targets: ['https://example.com/seo-audit'],
  source_notes: ['Source run: #1', 'Coverage status: missing'],
}

const briefEnrichmentRunsPayload: SemstormBriefEnrichmentRunsResponse = {
  site_id: 5,
  brief_id: 401,
  summary: {
    total_count: 1,
    completed_count: 1,
    failed_count: 0,
    applied_count: 0,
  },
  items: [
    {
      id: 501,
      site_id: 5,
      brief_item_id: 401,
      status: 'completed',
      engine_mode: 'mock',
      model_name: 'mock-semstorm-brief-enrichment-v1',
      input_hash: 'brief-hash-501',
      suggestions: {
        improved_brief_title: 'Execution brief: SEO Audit Checklist',
        improved_page_title: 'SEO Audit Checklist for Teams | Steps, Pricing and Scope',
        improved_h1: 'SEO Audit Checklist for Teams',
        improved_angle_summary:
          'Refine the execution packet around a practical audit checklist with clearer pricing and scope signals.',
        improved_sections: ['Checklist scope', 'Audit workflow', 'Pricing and scope', 'FAQs'],
        improved_internal_link_targets: [
          'https://example.com/seo-audit',
          'https://example.com/technical-seo',
        ],
        editorial_notes: ['Keep the intro practical and outcome-focused.'],
        risk_flags: ['Avoid turning the brief into a generic SEO basics article.'],
      },
      error_code: null,
      error_message_safe: null,
      is_applied: false,
      applied_at: null,
      created_at: '2026-03-21T14:35:00Z',
      updated_at: '2026-03-21T14:35:00Z',
    },
  ],
}

function renderSemstormRoute(
  route: string,
  {
    discoveryRuns = discoveryRunsPayload,
    discoveryRunDetail = discoveryRunDetailPayload,
    opportunities = opportunitiesPayload,
    promoted = promotedPayload,
    plans = plansPayload,
    briefs = briefsPayload,
    briefEnrichmentRuns = briefEnrichmentRunsPayload,
    opportunitiesStatus = 200,
    briefEnrichmentRunsStatus = 200,
    briefEnrichmentRunsDelayMs = 0,
  }: {
    discoveryRuns?: unknown
    discoveryRunDetail?: unknown
    opportunities?: unknown
    promoted?: unknown
    plans?: unknown
    briefs?: unknown
    briefEnrichmentRuns?: SemstormBriefEnrichmentRunsResponse
    opportunitiesStatus?: number
    briefEnrichmentRunsStatus?: number
    briefEnrichmentRunsDelayMs?: number
  } = {},
) {
  let currentOpportunities = structuredClone(opportunities) as typeof opportunitiesPayload
  let currentPromoted = structuredClone(promoted) as SemstormPromotedItemsResponse
  let currentPlans = structuredClone(plans) as SemstormPlansResponse
  const baseBriefs = structuredClone(briefs) as SemstormBriefsResponse
  let currentBriefs: {
    site_id: number
    summary: SemstormBriefsResponse['summary']
    items: SemstormBriefItem[]
  } = {
    site_id: baseBriefs.site_id,
    summary: baseBriefs.summary,
    items: baseBriefs.items.map((item) =>
      item.id === briefDetailPayload.id
        ? { ...briefDetailPayload, ...item }
        : {
            ...item,
            secondary_keywords: [],
            target_url_existing: null,
            implementation_url_override: null,
            evaluation_note: null,
            recommended_h1: null,
            content_goal: null,
            angle_summary: null,
            sections: [],
            internal_link_targets: [],
            source_notes: [],
            implementation_status: null,
            implemented_at: null,
            last_outcome_checked_at: null,
          },
    ),
  }
  let currentBriefEnrichmentRuns = structuredClone(
    briefEnrichmentRuns,
  ) as SemstormBriefEnrichmentRunsResponse

  function recalculateStateCounts() {
    const counts = { new: 0, accepted: 0, dismissed: 0, promoted: 0 }
    for (const item of currentOpportunities.items) {
      counts[item.state_status as keyof typeof counts] += 1
    }
    currentOpportunities = {
      ...currentOpportunities,
      summary: {
        ...currentOpportunities.summary,
        state_counts: counts,
      },
    }
  }

  function recalculatePlanSummary() {
    const stateCounts = { planned: 0, in_progress: 0, done: 0, archived: 0 }
    const targetCounts = { new_page: 0, expand_existing: 0, refresh_existing: 0, cluster_support: 0 }
    for (const item of currentPlans.items) {
      stateCounts[item.state_status as keyof typeof stateCounts] += 1
      targetCounts[item.target_page_type as keyof typeof targetCounts] += 1
    }
    currentPlans = {
      ...currentPlans,
      summary: {
        total_count: currentPlans.items.length,
        state_counts: stateCounts,
        target_page_type_counts: targetCounts,
      },
    }
  }

  function recalculateBriefSummary() {
    const stateCounts = { draft: 0, ready: 0, in_execution: 0, completed: 0, archived: 0 }
    const typeCounts = { new_page: 0, expand_existing: 0, refresh_existing: 0, cluster_support: 0 }
    const intentCounts = {
      informational: 0,
      commercial: 0,
      transactional: 0,
      navigational: 0,
      mixed: 0,
    }
    for (const item of currentBriefs.items) {
      stateCounts[item.state_status as keyof typeof stateCounts] += 1
      typeCounts[item.brief_type as keyof typeof typeCounts] += 1
      intentCounts[item.search_intent as keyof typeof intentCounts] += 1
    }
    currentBriefs = {
      ...currentBriefs,
      summary: {
        total_count: currentBriefs.items.length,
        state_counts: stateCounts,
        brief_type_counts: typeCounts,
        intent_counts: intentCounts,
      },
    }
  }

  function buildExecutionResponse(): SemstormExecutionResponse {
    return {
      site_id: 5,
      summary: {
        total_count: currentBriefs.items.length,
        execution_status_counts: { ...currentBriefs.summary.state_counts },
        ready_count: currentBriefs.items.filter((item) => item.execution_status === 'ready').length,
        in_execution_count: currentBriefs.items.filter((item) => item.execution_status === 'in_execution').length,
        completed_count: currentBriefs.items.filter((item) => item.execution_status === 'completed').length,
      },
      items: currentBriefs.items.map((item) => ({
        brief_id: item.id,
        plan_item_id: item.plan_item_id,
        brief_title: item.brief_title,
        primary_keyword: item.primary_keyword,
        brief_type: item.brief_type,
        search_intent: item.search_intent,
        execution_status: item.execution_status,
        assignee: item.assignee,
        execution_note: item.execution_note,
        implementation_status: item.implementation_status,
        implemented_at: item.implemented_at,
        recommended_page_title: item.recommended_page_title,
        proposed_url_slug: item.proposed_url_slug,
        ready_at: item.ready_at,
        started_at: item.started_at,
        completed_at: item.completed_at,
        archived_at: item.archived_at,
        decision_type_snapshot: item.decision_type_snapshot,
        bucket_snapshot: item.bucket_snapshot,
        coverage_status_snapshot: item.coverage_status_snapshot,
        gsc_signal_status_snapshot: item.gsc_signal_status_snapshot,
        opportunity_score_v2_snapshot: item.opportunity_score_v2_snapshot,
        updated_at: item.updated_at,
      })),
    }
  }

  function buildImplementedResponse(windowDays = 30): SemstormImplementedResponse {
    const now = new Date('2026-03-27T12:00:00Z')
    const items: SemstormImplementedResponse['items'] = currentBriefs.items
      .filter((item) => item.implementation_status !== null)
      .map((item): SemstormImplementedResponse['items'][number] => {
        const implementedAtDate = item.implemented_at ? new Date(item.implemented_at) : null
        const daysSinceImplemented =
          implementedAtDate == null
            ? Number.POSITIVE_INFINITY
            : Math.floor((now.getTime() - implementedAtDate.getTime()) / (1000 * 60 * 60 * 24))
        const tooEarly = item.implementation_status !== 'archived' && daysSinceImplemented < windowDays
        const implementationStatus: SemstormImplementedResponse['items'][number]['implementation_status'] =
          item.implementation_status === 'archived'
            ? 'archived'
            : tooEarly
              ? 'too_early'
              : 'evaluated'
        const matchedPage =
          implementationStatus === 'archived'
            ? null
            : {
                page_id: 801,
                url: item.implementation_url_override ?? item.target_url_existing ?? `https://example.com/${item.proposed_url_slug ?? 'brief'}`,
                title: item.recommended_page_title ?? item.brief_title ?? item.primary_keyword,
                match_signals: ['url'],
              }
        const gscSignalStatus: SemstormImplementedResponse['items'][number]['gsc_signal_status'] =
          implementationStatus === 'too_early'
            ? 'weak'
            : implementationStatus === 'archived'
              ? 'none'
              : 'present'
        const gscSummary =
          gscSignalStatus === 'none'
            ? null
            : {
                clicks: implementationStatus === 'too_early' ? 1 : 14,
                impressions: implementationStatus === 'too_early' ? 12 : 120,
                ctr: implementationStatus === 'too_early' ? 0.08 : 0.117,
                avg_position: implementationStatus === 'too_early' ? 18.4 : 6.2,
              }
        const outcomeStatus: SemstormImplementedResponse['items'][number]['outcome_status'] =
          implementationStatus === 'too_early'
            ? 'too_early'
            : gscSignalStatus === 'present'
              ? 'positive_signal'
              : matchedPage
                ? 'weak_signal'
                : 'no_signal'
        return {
          brief_id: item.id,
          plan_item_id: item.plan_item_id,
          brief_title: item.brief_title,
          primary_keyword: item.primary_keyword,
          brief_type: item.brief_type,
          execution_status: item.execution_status,
          implementation_status: implementationStatus,
          implemented_at: item.implemented_at,
          evaluation_note: item.evaluation_note ?? null,
          implementation_url_override: item.implementation_url_override ?? null,
          outcome_status: outcomeStatus,
          page_present_in_active_crawl: matchedPage !== null,
          matched_page: matchedPage,
          gsc_signal_status: gscSignalStatus,
          gsc_summary: gscSummary,
          query_match_count: gscSignalStatus === 'present' ? 2 : gscSignalStatus === 'weak' ? 1 : 0,
          notes:
            implementationStatus === 'too_early'
              ? [`Too early to evaluate against the ${windowDays}-day outcome window.`]
              : gscSignalStatus === 'present'
                ? ['Active crawl and GSC both show a positive post-implementation signal.']
                : ['No clear signal yet.'],
          decision_type_snapshot: item.decision_type_snapshot,
          coverage_status_snapshot: item.coverage_status_snapshot,
          opportunity_score_v2_snapshot: item.opportunity_score_v2_snapshot,
          updated_at: item.updated_at,
          last_outcome_checked_at: '2026-03-27T12:00:00Z',
        }
      })

    const summary = {
      total_count: items.length,
      implementation_status_counts: { too_early: 0, implemented: 0, evaluated: 0, archived: 0 },
      outcome_status_counts: { too_early: 0, no_signal: 0, weak_signal: 0, positive_signal: 0 },
      too_early_count: 0,
      positive_signal_count: 0,
    }
    for (const item of items) {
      summary.implementation_status_counts[
        item.implementation_status as keyof typeof summary.implementation_status_counts
      ] += 1
      summary.outcome_status_counts[item.outcome_status as keyof typeof summary.outcome_status_counts] += 1
    }
    summary.too_early_count = summary.outcome_status_counts.too_early
    summary.positive_signal_count = summary.outcome_status_counts.positive_signal

    return {
      site_id: 5,
      active_crawl_id: 11,
      window_days: windowDays,
      summary,
      items,
    }
  }

  function applyBriefExecutionTransition(brief: SemstormBriefItem, nextStatus: SemstormBriefItem['execution_status']) {
    brief.state_status = nextStatus
    brief.execution_status = nextStatus
    if (nextStatus === 'ready' && !brief.ready_at) {
      brief.ready_at = '2026-03-21T14:18:00Z'
    }
    if (nextStatus === 'in_execution') {
      brief.started_at = '2026-03-21T14:22:00Z'
    }
    if (nextStatus === 'completed') {
      brief.completed_at = '2026-03-21T14:30:00Z'
    }
    if (nextStatus === 'archived') {
      brief.archived_at = '2026-03-21T14:32:00Z'
    }
    if (nextStatus === 'ready') {
      brief.completed_at = null
      brief.archived_at = null
    }
    brief.updated_at = '2026-03-21T14:32:00Z'
  }

  function applyBriefImplementationTransition(
    brief: SemstormBriefItem,
    nextStatus: 'implemented' | 'archived',
    payload: { evaluation_note?: string | null; implementation_url_override?: string | null } = {},
  ) {
    if (nextStatus === 'implemented') {
      brief.implementation_status = 'implemented'
      brief.implemented_at = brief.implemented_at ?? '2026-03-27T09:00:00Z'
      brief.last_outcome_checked_at = null
    } else {
      brief.implementation_status = 'archived'
    }
    if (payload.evaluation_note !== undefined) {
      brief.evaluation_note = payload.evaluation_note
    }
    if (payload.implementation_url_override !== undefined) {
      brief.implementation_url_override = payload.implementation_url_override
    }
    brief.updated_at = '2026-03-27T09:05:00Z'
  }

  function buildBriefEnrichmentRunsResponse(briefId: number): SemstormBriefEnrichmentRunsResponse {
    const items = currentBriefEnrichmentRuns.items.filter((item) => item.brief_item_id === briefId)
    return {
      site_id: 5,
      brief_id: briefId,
      summary: {
        total_count: items.length,
        completed_count: items.filter((item) => item.status === 'completed').length,
        failed_count: items.filter((item) => item.status === 'failed').length,
        applied_count: items.filter((item) => item.is_applied).length,
      },
      items,
    }
  }

  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const rawUrl =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    const method = init?.method?.toUpperCase() ?? (typeof input === 'string' || input instanceof URL ? 'GET' : input.method.toUpperCase())
    const url = new URL(rawUrl)

    if (url.pathname === '/sites/5') {
      return jsonResponse(sitePayload)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/discovery-runs') {
      return jsonResponse(discoveryRuns)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/discovery-runs/1') {
      return jsonResponse(discoveryRunDetail)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/opportunities' && method === 'GET') {
      return jsonResponse(currentOpportunities, { status: opportunitiesStatus })
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/promoted') {
      return jsonResponse(currentPromoted)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs' && method === 'GET') {
      let filteredItems = [...currentBriefs.items]
      const stateStatus = url.searchParams.get('state_status')
      const briefType = url.searchParams.get('brief_type')
      const searchIntent = url.searchParams.get('search_intent')
      const search = url.searchParams.get('search')?.toLowerCase()
      const limit = Number(url.searchParams.get('limit') ?? '100')

      if (stateStatus) {
        filteredItems = filteredItems.filter((item) => item.state_status === stateStatus)
      }
      if (briefType) {
        filteredItems = filteredItems.filter((item) => item.brief_type === briefType)
      }
      if (searchIntent) {
        filteredItems = filteredItems.filter((item) => item.search_intent === searchIntent)
      }
      if (search) {
        filteredItems = filteredItems.filter((item) =>
          [item.brief_title ?? '', item.primary_keyword, item.recommended_page_title ?? '', item.proposed_url_slug ?? '']
            .join(' ')
            .toLowerCase()
            .includes(search),
        )
      }

      return jsonResponse({
        site_id: 5,
        summary: {
          total_count: filteredItems.length,
          state_counts: currentBriefs.summary.state_counts,
          brief_type_counts: currentBriefs.summary.brief_type_counts,
          intent_counts: currentBriefs.summary.intent_counts,
        },
        items: filteredItems.slice(0, limit),
      })
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/implemented' && method === 'GET') {
      const windowDays = Number(url.searchParams.get('window_days') ?? '30')
      const response = buildImplementedResponse(Number.isFinite(windowDays) ? windowDays : 30)
      let filteredItems = [...response.items]
      const implementationStatus = url.searchParams.get('implementation_status')
      const outcomeStatus = url.searchParams.get('outcome_status')
      const briefType = url.searchParams.get('brief_type')
      const search = url.searchParams.get('search')?.trim().toLowerCase()
      const limit = Number(url.searchParams.get('limit') ?? '100')

      if (implementationStatus) {
        filteredItems = filteredItems.filter((item) => item.implementation_status === implementationStatus)
      }
      if (outcomeStatus) {
        filteredItems = filteredItems.filter((item) => item.outcome_status === outcomeStatus)
      }
      if (briefType) {
        filteredItems = filteredItems.filter((item) => item.brief_type === briefType)
      }
      if (search) {
        filteredItems = filteredItems.filter(
          (item) =>
            item.primary_keyword.toLowerCase().includes(search) ||
            String(item.brief_title ?? '')
              .toLowerCase()
              .includes(search) ||
            String(item.matched_page?.url ?? '')
              .toLowerCase()
              .includes(search),
        )
      }

      const summary = {
        total_count: filteredItems.length,
        implementation_status_counts: { too_early: 0, implemented: 0, evaluated: 0, archived: 0 },
        outcome_status_counts: { too_early: 0, no_signal: 0, weak_signal: 0, positive_signal: 0 },
        too_early_count: 0,
        positive_signal_count: 0,
      }
      for (const item of filteredItems) {
        summary.implementation_status_counts[item.implementation_status] += 1
        summary.outcome_status_counts[item.outcome_status] += 1
      }
      summary.too_early_count = summary.outcome_status_counts.too_early
      summary.positive_signal_count = summary.outcome_status_counts.positive_signal

      return jsonResponse({
        ...response,
        summary,
        items: filteredItems.slice(0, Number.isFinite(limit) ? limit : 100),
      })
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/execution' && method === 'GET') {
      let filteredItems = [...currentBriefs.items]
      const executionStatus = url.searchParams.get('execution_status')
      const briefType = url.searchParams.get('brief_type')
      const assignee = url.searchParams.get('assignee')?.toLowerCase()
      const search = url.searchParams.get('search')?.toLowerCase()
      const limit = Number(url.searchParams.get('limit') ?? '100')

      if (executionStatus) {
        filteredItems = filteredItems.filter((item) => item.execution_status === executionStatus)
      }
      if (briefType) {
        filteredItems = filteredItems.filter((item) => item.brief_type === briefType)
      }
      if (assignee) {
        filteredItems = filteredItems.filter((item) => (item.assignee ?? '').toLowerCase() === assignee)
      }
      if (search) {
        filteredItems = filteredItems.filter((item) =>
          [item.brief_title ?? '', item.primary_keyword, item.recommended_page_title ?? '', item.proposed_url_slug ?? '']
            .join(' ')
            .toLowerCase()
            .includes(search),
        )
      }

      const response = buildExecutionResponse()
      return jsonResponse({
        ...response,
        summary: {
          total_count: filteredItems.length,
          execution_status_counts: response.summary.execution_status_counts,
          ready_count: filteredItems.filter((item) => item.execution_status === 'ready').length,
          in_execution_count: filteredItems.filter((item) => item.execution_status === 'in_execution').length,
          completed_count: filteredItems.filter((item) => item.execution_status === 'completed').length,
        },
        items: filteredItems.slice(0, limit).map((item) => ({
          brief_id: item.id,
          plan_item_id: item.plan_item_id,
          brief_title: item.brief_title,
          primary_keyword: item.primary_keyword,
          brief_type: item.brief_type,
          search_intent: item.search_intent,
          execution_status: item.execution_status,
          assignee: item.assignee,
          execution_note: item.execution_note,
          recommended_page_title: item.recommended_page_title,
          proposed_url_slug: item.proposed_url_slug,
          ready_at: item.ready_at,
          started_at: item.started_at,
          completed_at: item.completed_at,
          archived_at: item.archived_at,
          decision_type_snapshot: item.decision_type_snapshot,
          bucket_snapshot: item.bucket_snapshot,
          coverage_status_snapshot: item.coverage_status_snapshot,
          gsc_signal_status_snapshot: item.gsc_signal_status_snapshot,
          opportunity_score_v2_snapshot: item.opportunity_score_v2_snapshot,
          updated_at: item.updated_at,
        })),
      })
    }
    const briefEnrichmentRunsMatch = url.pathname.match(
      /^\/sites\/5\/competitive-content-gap\/semstorm\/briefs\/(\d+)\/enrichment-runs$/,
    )
    if (briefEnrichmentRunsMatch && method === 'GET') {
      if (briefEnrichmentRunsStatus !== 200) {
        return jsonResponse(
          { detail: 'AI enrichment runs are temporarily unavailable.' },
          { status: briefEnrichmentRunsStatus },
        )
      }
      const payload = buildBriefEnrichmentRunsResponse(Number(briefEnrichmentRunsMatch[1]))
      if (briefEnrichmentRunsDelayMs > 0) {
        return new Promise((resolve) => {
          setTimeout(() => resolve(jsonResponse(payload)), briefEnrichmentRunsDelayMs)
        })
      }
      return jsonResponse(payload)
    }
    const briefEnrichMatch = url.pathname.match(
      /^\/sites\/5\/competitive-content-gap\/semstorm\/briefs\/(\d+)\/enrich$/,
    )
    if (briefEnrichMatch && method === 'POST') {
      const briefId = Number(briefEnrichMatch[1])
      const brief = currentBriefs.items.find((item) => item.id === briefId)
      if (!brief) {
        return jsonResponse({ detail: 'Brief not found' }, { status: 404 })
      }
      const nextId = currentBriefEnrichmentRuns.items.length
        ? Math.max(...currentBriefEnrichmentRuns.items.map((item) => item.id)) + 1
        : 501
      const keywordTitle = brief.primary_keyword.replace(/\b\w/g, (match) => match.toUpperCase())
      const briefTitleSeed =
        brief.brief_title?.replace(/^New page brief:\s*/i, '').trim() || keywordTitle
      const createdRun = {
        id: nextId,
        site_id: 5,
        brief_item_id: briefId,
        status: 'completed',
        engine_mode: 'mock',
        model_name: 'mock-semstorm-brief-enrichment-v1',
        input_hash: `brief-hash-${nextId}`,
        suggestions: {
          improved_brief_title: `Execution brief: ${briefTitleSeed}`,
          improved_page_title: `${briefTitleSeed} | Execution Scope and Next Steps`,
          improved_h1: `${briefTitleSeed} Execution Guide`,
          improved_angle_summary:
            'Tighten the brief around a cleaner execution angle, practical outcomes and clearer on-page scope.',
          improved_sections: ['Core angle', 'Execution scope', 'Supporting proof points', 'FAQs'],
          improved_internal_link_targets: ['https://example.com/seo-audit'],
          editorial_notes: ['Keep the content operational and easy to hand off.'],
          risk_flags: ['Do not drift into a broad SEO explainer.'],
        },
        error_code: null,
        error_message_safe: null,
        is_applied: false,
        applied_at: null,
        created_at: '2026-03-21T14:40:00Z',
        updated_at: '2026-03-21T14:40:00Z',
      } as SemstormBriefEnrichmentRunsResponse['items'][number]
      currentBriefEnrichmentRuns = {
        ...currentBriefEnrichmentRuns,
        items: [createdRun, ...currentBriefEnrichmentRuns.items],
      }
      return jsonResponse(createdRun, { status: 201 })
    }
    const briefEnrichmentApplyMatch = url.pathname.match(
      /^\/sites\/5\/competitive-content-gap\/semstorm\/briefs\/(\d+)\/enrichment-runs\/(\d+)\/apply$/,
    )
    if (briefEnrichmentApplyMatch && method === 'POST') {
      const briefId = Number(briefEnrichmentApplyMatch[1])
      const runId = Number(briefEnrichmentApplyMatch[2])
      const brief = currentBriefs.items.find((item) => item.id === briefId)
      const enrichmentRun = currentBriefEnrichmentRuns.items.find(
        (item) => item.id === runId && item.brief_item_id === briefId,
      )
      if (!brief || !enrichmentRun) {
        return jsonResponse({ detail: 'Enrichment run not found' }, { status: 404 })
      }
      if (enrichmentRun.is_applied) {
        return jsonResponse({
          site_id: 5,
          brief_id: briefId,
          run_id: runId,
          applied: false,
          skipped_reason: 'already_applied',
          applied_fields: [],
          brief,
          enrichment_run: enrichmentRun,
        })
      }

      const appliedFields: string[] = []
      if (enrichmentRun.suggestions.improved_brief_title) {
        brief.brief_title = enrichmentRun.suggestions.improved_brief_title
        appliedFields.push('brief_title')
      }
      if (enrichmentRun.suggestions.improved_page_title) {
        brief.recommended_page_title = enrichmentRun.suggestions.improved_page_title
        appliedFields.push('recommended_page_title')
      }
      if (enrichmentRun.suggestions.improved_h1) {
        brief.recommended_h1 = enrichmentRun.suggestions.improved_h1
        appliedFields.push('recommended_h1')
      }
      if (enrichmentRun.suggestions.improved_angle_summary) {
        brief.angle_summary = enrichmentRun.suggestions.improved_angle_summary
        appliedFields.push('angle_summary')
      }
      if (enrichmentRun.suggestions.improved_sections.length) {
        brief.sections = [...enrichmentRun.suggestions.improved_sections]
        appliedFields.push('sections')
      }
      if (enrichmentRun.suggestions.improved_internal_link_targets.length) {
        brief.internal_link_targets = [...enrichmentRun.suggestions.improved_internal_link_targets]
        appliedFields.push('internal_link_targets')
      }
      if (enrichmentRun.suggestions.editorial_notes.length || enrichmentRun.suggestions.risk_flags.length) {
        brief.source_notes = [
          ...brief.source_notes,
          ...enrichmentRun.suggestions.editorial_notes.map((note) => `AI note: ${note}`),
          ...enrichmentRun.suggestions.risk_flags.map((risk) => `Risk flag: ${risk}`),
        ]
        appliedFields.push('source_notes')
      }
      brief.updated_at = '2026-03-21T14:45:00Z'
      enrichmentRun.is_applied = true
      enrichmentRun.applied_at = '2026-03-21T14:45:00Z'
      enrichmentRun.updated_at = '2026-03-21T14:45:00Z'

      return jsonResponse({
        site_id: 5,
        brief_id: briefId,
        run_id: runId,
        applied: true,
        skipped_reason: null,
        applied_fields: appliedFields,
        brief,
        enrichment_run: enrichmentRun,
      })
    }
    if (
      url.pathname === '/sites/5/competitive-content-gap/semstorm/promoted/actions/create-plan' &&
      method === 'POST'
    ) {
      const body = JSON.parse(init?.body ? String(init.body) : '{"promoted_item_ids":[]}')
      const createdItems = []
      const skipped = []

      for (const promotedItemId of body.promoted_item_ids as number[]) {
        const promotedItem = currentPromoted.items.find((candidate) => candidate.id === promotedItemId)
        if (!promotedItem) {
          skipped.push({ promoted_item_id: promotedItemId, keyword: null, reason: 'promoted_item_not_found' })
          continue
        }
        if (promotedItem.has_plan) {
          skipped.push({ promoted_item_id: promotedItemId, keyword: promotedItem.keyword, reason: 'already_exists' })
          continue
        }
        const targetPageType = body.defaults?.target_page_type ?? 'new_page'
        const createdItem = {
          id: currentPlans.items.length ? Math.max(...currentPlans.items.map((item) => item.id)) + 1 : 301,
          site_id: 5,
          promoted_item_id: promotedItem.id,
          keyword: promotedItem.keyword,
          normalized_keyword: promotedItem.normalized_keyword,
          source_run_id: promotedItem.source_run_id,
          state_status: 'planned',
          decision_type_snapshot: promotedItem.decision_type,
          bucket_snapshot: promotedItem.bucket,
          coverage_status_snapshot: promotedItem.coverage_status,
          opportunity_score_v2_snapshot: promotedItem.opportunity_score_v2,
          best_match_page_url_snapshot: promotedItem.best_match_page_url,
          gsc_signal_status_snapshot: promotedItem.gsc_signal_status,
          plan_title: `Create page for ${promotedItem.keyword}`,
          plan_note: null,
          target_page_type: targetPageType,
          proposed_slug: promotedItem.keyword.replace(/\s+/g, '-'),
          proposed_primary_keyword: promotedItem.keyword,
          proposed_secondary_keywords: [],
          has_brief: false,
          brief_id: null,
          brief_state_status: null,
          created_at: '2026-03-21T13:30:00Z',
          updated_at: '2026-03-21T13:30:00Z',
        } as SemstormPlansResponse['items'][number]
        currentPlans = {
          ...currentPlans,
          items: [createdItem, ...currentPlans.items],
        }
        promotedItem.has_plan = true
        promotedItem.plan_id = createdItem.id
        promotedItem.plan_state_status = createdItem.state_status
        createdItems.push(createdItem)
      }
      recalculatePlanSummary()
      return jsonResponse({
        site_id: 5,
        requested_count: body.promoted_item_ids.length,
        created_count: createdItems.length,
        updated_count: 0,
        skipped_count: skipped.length,
        items: createdItems,
        skipped,
      })
    }
    if (
      url.pathname === '/sites/5/competitive-content-gap/semstorm/plans/actions/create-brief' &&
      method === 'POST'
    ) {
      const body = JSON.parse(init?.body ? String(init.body) : '{"plan_item_ids":[]}')
      const createdItems: SemstormBriefItem[] = []
      const skipped = []

      for (const planItemId of body.plan_item_ids as number[]) {
        const planItem = currentPlans.items.find((candidate) => candidate.id === planItemId)
        if (!planItem) {
          skipped.push({ plan_item_id: planItemId, brief_title: null, reason: 'plan_not_found' })
          continue
        }
        if (planItem.has_brief) {
          skipped.push({
            plan_item_id: planItemId,
            brief_title: planItem.keyword ? `New page brief: ${planItem.keyword.replace(/\b\w/g, (match) => match.toUpperCase())}` : null,
            reason: 'already_exists',
          })
          continue
        }

        const createdItem: SemstormBriefItem = {
          id: currentBriefs.items.length ? Math.max(...currentBriefs.items.map((item) => item.id)) + 1 : 401,
          site_id: 5,
          plan_item_id: planItem.id,
          brief_title: `New page brief: ${planItem.keyword.replace(/\b\w/g, (match) => match.toUpperCase())}`,
          primary_keyword: planItem.proposed_primary_keyword ?? planItem.keyword,
          brief_type: planItem.target_page_type,
          search_intent: 'transactional',
          state_status: 'draft',
          execution_status: 'draft',
          assignee: null,
          execution_note: null,
          ready_at: null,
          started_at: null,
          completed_at: null,
          archived_at: null,
          implementation_status: null,
          implemented_at: null,
          last_outcome_checked_at: null,
          recommended_page_title: `${planItem.keyword.replace(/\b\w/g, (match) => match.toUpperCase())} | Pricing and Options`,
          proposed_url_slug: planItem.proposed_slug,
          decision_type_snapshot: planItem.decision_type_snapshot,
          bucket_snapshot: planItem.bucket_snapshot,
          coverage_status_snapshot: planItem.coverage_status_snapshot,
          gsc_signal_status_snapshot: planItem.gsc_signal_status_snapshot,
          opportunity_score_v2_snapshot: planItem.opportunity_score_v2_snapshot,
          created_at: '2026-03-21T14:00:00Z',
          updated_at: '2026-03-21T14:00:00Z',
          secondary_keywords: [...planItem.proposed_secondary_keywords],
          target_url_existing: null,
          implementation_url_override: null,
          evaluation_note: null,
          recommended_h1: planItem.keyword.replace(/\b\w/g, (match) => match.toUpperCase()),
          content_goal: `Create a practical execution packet for ${planItem.keyword}.`,
          angle_summary: 'Use the brief as a lightweight execution packet.',
          sections: ['Introduction', 'Checklist', 'Pricing', 'FAQs'],
          internal_link_targets: ['https://example.com/seo-audit'],
          source_notes: ['Source run: #1', 'Coverage status: missing'],
        }
        currentBriefs = {
          ...currentBriefs,
          items: [createdItem, ...currentBriefs.items],
        }
        planItem.has_brief = true
        planItem.brief_id = createdItem.id
        planItem.brief_state_status = createdItem.state_status
        createdItems.push(createdItem)
      }

      recalculateBriefSummary()
      recalculatePlanSummary()
      return jsonResponse({
        site_id: 5,
        requested_count: body.plan_item_ids.length,
        created_count: createdItems.length,
        updated_count: 0,
        skipped_count: skipped.length,
        items: createdItems,
        skipped,
      })
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/plans' && method === 'GET') {
      let filteredItems = [...currentPlans.items]
      const stateStatus = url.searchParams.get('state_status')
      const targetPageType = url.searchParams.get('target_page_type')
      const search = url.searchParams.get('search')?.toLowerCase()
      const limit = Number(url.searchParams.get('limit') ?? '100')

      if (stateStatus) {
        filteredItems = filteredItems.filter((item) => item.state_status === stateStatus)
      }
      if (targetPageType) {
        filteredItems = filteredItems.filter((item) => item.target_page_type === targetPageType)
      }
      if (search) {
        filteredItems = filteredItems.filter((item) =>
          [item.keyword, item.plan_title ?? '', item.proposed_slug ?? '', item.proposed_primary_keyword ?? '']
            .join(' ')
            .toLowerCase()
            .includes(search),
        )
      }
      return jsonResponse({
        site_id: 5,
        summary: {
          total_count: filteredItems.length,
          state_counts: currentPlans.summary.state_counts,
          target_page_type_counts: currentPlans.summary.target_page_type_counts,
        },
        items: filteredItems.slice(0, limit),
      })
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/plans/301' && method === 'GET') {
      return jsonResponse(currentPlans.items.find((item) => item.id === 301))
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/plans/302' && method === 'GET') {
      return jsonResponse(currentPlans.items.find((item) => item.id === 302))
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/plans/301/status' && method === 'POST') {
      const body = JSON.parse(init?.body ? String(init.body) : '{"state_status":"planned"}')
      const plan = currentPlans.items.find((item) => item.id === 301)
      if (plan) {
        plan.state_status = body.state_status
        plan.updated_at = '2026-03-21T13:40:00Z'
      }
      const promoted = currentPromoted.items.find((item) => item.plan_id === 301)
      if (promoted) {
        promoted.plan_state_status = body.state_status
      }
      recalculatePlanSummary()
      return jsonResponse(plan)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/plans/302/status' && method === 'POST') {
      const body = JSON.parse(init?.body ? String(init.body) : '{"state_status":"planned"}')
      const plan = currentPlans.items.find((item) => item.id === 302)
      if (plan) {
        plan.state_status = body.state_status
        plan.updated_at = '2026-03-21T13:40:00Z'
      }
      const promoted = currentPromoted.items.find((item) => item.plan_id === 302)
      if (promoted) {
        promoted.plan_state_status = body.state_status
      }
      recalculatePlanSummary()
      return jsonResponse(plan)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/plans/301' && method === 'PUT') {
      const body = JSON.parse(init?.body ? String(init.body) : '{}')
      const plan = currentPlans.items.find((item) => item.id === 301)
      if (plan) {
        Object.assign(plan, body, { updated_at: '2026-03-21T13:45:00Z' })
      }
      recalculatePlanSummary()
      return jsonResponse(plan)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/plans/302' && method === 'PUT') {
      const body = JSON.parse(init?.body ? String(init.body) : '{}')
      const plan = currentPlans.items.find((item) => item.id === 302)
      if (plan) {
        Object.assign(plan, body, { updated_at: '2026-03-21T13:45:00Z' })
      }
      recalculatePlanSummary()
      return jsonResponse(plan)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/401' && method === 'GET') {
      return jsonResponse(currentBriefs.items.find((item) => item.id === 401))
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/402' && method === 'GET') {
      return jsonResponse(currentBriefs.items.find((item) => item.id === 402))
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/401/status' && method === 'POST') {
      const body = JSON.parse(init?.body ? String(init.body) : '{"state_status":"draft"}')
      const brief = currentBriefs.items.find((item) => item.id === 401)
      if (brief) {
        applyBriefExecutionTransition(brief, body.state_status)
      }
      const plan = currentPlans.items.find((item) => item.brief_id === 401)
      if (plan) {
        plan.brief_state_status = body.state_status
      }
      recalculateBriefSummary()
      recalculatePlanSummary()
      return jsonResponse(brief)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/402/status' && method === 'POST') {
      const body = JSON.parse(init?.body ? String(init.body) : '{"state_status":"draft"}')
      const brief = currentBriefs.items.find((item) => item.id === 402)
      if (brief) {
        applyBriefExecutionTransition(brief, body.state_status)
      }
      const plan = currentPlans.items.find((item) => item.brief_id === 402)
      if (plan) {
        plan.brief_state_status = body.state_status
      }
      recalculateBriefSummary()
      recalculatePlanSummary()
      return jsonResponse(brief)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/401/execution-status' && method === 'POST') {
      const body = JSON.parse(init?.body ? String(init.body) : '{"execution_status":"draft"}')
      const brief = currentBriefs.items.find((item) => item.id === 401)
      if (brief) {
        applyBriefExecutionTransition(brief, body.execution_status)
      }
      const plan = currentPlans.items.find((item) => item.brief_id === 401)
      if (plan && brief) {
        plan.brief_state_status = brief.execution_status
      }
      recalculateBriefSummary()
      recalculatePlanSummary()
      return jsonResponse(brief)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/402/execution-status' && method === 'POST') {
      const body = JSON.parse(init?.body ? String(init.body) : '{"execution_status":"draft"}')
      const brief = currentBriefs.items.find((item) => item.id === 402)
      if (brief) {
        applyBriefExecutionTransition(brief, body.execution_status)
      }
      const plan = currentPlans.items.find((item) => item.brief_id === 402)
      if (plan && brief) {
        plan.brief_state_status = brief.execution_status
      }
      recalculateBriefSummary()
      recalculatePlanSummary()
      return jsonResponse(brief)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/401/implementation-status' && method === 'POST') {
      const body = JSON.parse(init?.body ? String(init.body) : '{"implementation_status":"implemented"}')
      const brief = currentBriefs.items.find((item) => item.id === 401)
      if (brief) {
        applyBriefImplementationTransition(brief, body.implementation_status, body)
      }
      recalculateBriefSummary()
      return jsonResponse(brief)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/402/implementation-status' && method === 'POST') {
      const body = JSON.parse(init?.body ? String(init.body) : '{"implementation_status":"implemented"}')
      const brief = currentBriefs.items.find((item) => item.id === 402)
      if (brief) {
        applyBriefImplementationTransition(brief, body.implementation_status, body)
      }
      recalculateBriefSummary()
      return jsonResponse(brief)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/401' && method === 'PUT') {
      const body = JSON.parse(init?.body ? String(init.body) : '{}')
      const brief = currentBriefs.items.find((item) => item.id === 401)
      if (brief) {
        Object.assign(brief, body, { updated_at: '2026-03-21T14:25:00Z' })
      }
      recalculateBriefSummary()
      return jsonResponse(brief)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/401/execution' && method === 'PUT') {
      const body = JSON.parse(init?.body ? String(init.body) : '{}')
      const brief = currentBriefs.items.find((item) => item.id === 401)
      if (brief) {
        Object.assign(brief, body, { updated_at: '2026-03-21T14:28:00Z' })
      }
      recalculateBriefSummary()
      return jsonResponse(brief)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/402/execution' && method === 'PUT') {
      const body = JSON.parse(init?.body ? String(init.body) : '{}')
      const brief = currentBriefs.items.find((item) => item.id === 402)
      if (brief) {
        Object.assign(brief, body, { updated_at: '2026-03-21T14:28:00Z' })
      }
      recalculateBriefSummary()
      return jsonResponse(brief)
    }
    if (url.pathname === '/sites/5/competitive-content-gap/semstorm/briefs/402' && method === 'PUT') {
      const body = JSON.parse(init?.body ? String(init.body) : '{}')
      const brief = currentBriefs.items.find((item) => item.id === 402)
      if (brief) {
        Object.assign(brief, body, { updated_at: '2026-03-21T14:25:00Z' })
      }
      recalculateBriefSummary()
      return jsonResponse(brief)
    }
    if (
      url.pathname === '/sites/5/competitive-content-gap/semstorm/opportunities/actions/accept' &&
      method === 'POST'
    ) {
      const body = JSON.parse(init?.body ? String(init.body) : '{"keywords":[]}')
      for (const keyword of body.keywords as string[]) {
        const item = currentOpportunities.items.find((candidate) => candidate.keyword === keyword)
        if (!item) {
          continue
        }
        item.state_status = 'accepted'
        item.state_note = body.note ?? null
        item.can_accept = false
        item.can_dismiss = true
        item.can_promote = true
      }
      recalculateStateCounts()
      return jsonResponse({
        action: 'accept',
        site_id: 5,
        run_id: 1,
        note: body.note ?? null,
        requested_count: body.keywords.length,
        updated_count: 1,
        promoted_count: 0,
        state_status: 'accepted',
        updated_keywords: ['seo audit checklist'],
        promoted_items: [],
        skipped_count: 0,
        skipped: [],
      })
    }
    if (
      url.pathname === '/sites/5/competitive-content-gap/semstorm/opportunities/actions/dismiss' &&
      method === 'POST'
    ) {
      const body = JSON.parse(init?.body ? String(init.body) : '{"keywords":[]}')
      for (const keyword of body.keywords as string[]) {
        const item = currentOpportunities.items.find((candidate) => candidate.keyword === keyword)
        if (!item) {
          continue
        }
        item.state_status = 'dismissed'
        item.state_note = body.note ?? null
        item.can_accept = true
        item.can_dismiss = false
        item.can_promote = false
      }
      recalculateStateCounts()
      return jsonResponse({
        action: 'dismiss',
        site_id: 5,
        run_id: 1,
        note: body.note ?? null,
        requested_count: body.keywords.length,
        updated_count: 1,
        promoted_count: 0,
        state_status: 'dismissed',
        updated_keywords: ['seo audit checklist'],
        promoted_items: [],
        skipped_count: 0,
        skipped: [],
      })
    }
    if (
      url.pathname === '/sites/5/competitive-content-gap/semstorm/opportunities/actions/promote' &&
      method === 'POST'
    ) {
      const body = JSON.parse(init?.body ? String(init.body) : '{"keywords":[]}')
      for (const keyword of body.keywords as string[]) {
        const item = currentOpportunities.items.find((candidate) => candidate.keyword === keyword)
        if (!item) {
          continue
        }
        item.state_status = 'promoted'
        item.state_note = body.note ?? null
        item.can_accept = false
        item.can_dismiss = false
        item.can_promote = false
      }
      recalculateStateCounts()
      currentPromoted = {
        ...currentPromoted,
        summary: {
          total_items: currentPromoted.items.length + 1,
          promotion_status_counts: {
            active: (currentPromoted.summary.promotion_status_counts.active ?? 0) + 1,
            archived: currentPromoted.summary.promotion_status_counts.archived ?? 0,
          },
        },
        items: [
          ...currentPromoted.items,
          {
            id: 92,
            site_id: 5,
            opportunity_key: 'semstorm:def456',
            source_run_id: 1,
            keyword: 'technical seo guide',
            normalized_keyword: 'technical seo guide',
            bucket: 'quick_win',
            decision_type: 'expand_existing_page',
            opportunity_score_v2: 72,
            coverage_status: 'weak_coverage',
            best_match_page_url: 'https://example.com/technical-seo',
            gsc_signal_status: 'present',
            promotion_status: 'active',
            has_plan: false,
            plan_id: null,
            plan_state_status: null,
            created_at: '2026-03-21T12:10:00Z',
            updated_at: '2026-03-21T12:10:00Z',
          },
        ],
      }
      return jsonResponse({
        action: 'promote',
        site_id: 5,
        run_id: 1,
        note: body.note ?? null,
        requested_count: body.keywords.length,
        updated_count: 1,
        promoted_count: 1,
        state_status: 'promoted',
        updated_keywords: ['technical seo guide'],
        promoted_items: currentPromoted.items.slice(-1),
        skipped_count: 0,
        skipped: [],
      })
    }

    throw new Error(`Unhandled fetch: ${url.pathname}${url.search}`)
  })

  vi.stubGlobal('fetch', fetchMock)

  const queryClient = createTestQueryClient()
  const user = userEvent.setup()
  const view = render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/sites/:siteId" element={<SiteWorkspaceLayout />}>
              <Route path="competitive-gap/semstorm" element={<Navigate replace to="discovery" />} />
              <Route path="competitive-gap/semstorm/discovery" element={<SiteCompetitiveGapSemstormDiscoveryPage />} />
              <Route
                path="competitive-gap/semstorm/opportunities"
                element={<SiteCompetitiveGapSemstormOpportunitiesPage />}
              />
              <Route path="competitive-gap/semstorm/promoted" element={<SiteCompetitiveGapSemstormPromotedPage />} />
              <Route path="competitive-gap/semstorm/plans" element={<SiteCompetitiveGapSemstormPlansPage />} />
              <Route path="competitive-gap/semstorm/briefs" element={<SiteCompetitiveGapSemstormBriefsPage />} />
              <Route path="competitive-gap/semstorm/execution" element={<SiteCompetitiveGapSemstormExecutionPage />} />
              <Route path="competitive-gap/semstorm/implemented" element={<SiteCompetitiveGapSemstormImplementedPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  )

  return { ...view, user, fetchMock }
}

describe('SiteCompetitiveGapSemstormPage', () => {
  test('renders discovery page with runs and detail panel', async () => {
    renderSemstormRoute('/sites/5/competitive-gap/semstorm/discovery?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Semstorm discovery')).toBeInTheDocument()
    expect(await screen.findByText('Recent discovery runs')).toBeInTheDocument()
    expect((await screen.findAllByText('Run #1')).length).toBeGreaterThan(0)
    expect(await screen.findByText('competitor-a.com')).toBeInTheDocument()
  })

  test('renders opportunities page', async () => {
    renderSemstormRoute('/sites/5/competitive-gap/semstorm/opportunities?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Semstorm opportunities')).toBeInTheDocument()
    expect(await screen.findByText('Opportunity list')).toBeInTheDocument()
    expect(await screen.findByText('seo audit checklist')).toBeInTheDocument()
    expect(await screen.findAllByText('New')).not.toHaveLength(0)
  })

  test('shows discovery empty state when there are no runs', async () => {
    renderSemstormRoute('/sites/5/competitive-gap/semstorm/discovery?active_crawl_id=11&baseline_crawl_id=10', {
      discoveryRuns: [],
    })

    expect(await screen.findByText('No Semstorm discovery runs yet')).toBeInTheDocument()
  })

  test('updates opportunities filters through quick filter interactions', async () => {
    const { user, fetchMock } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/opportunities?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('Opportunity list')
    await user.click(screen.getByRole('button', { name: 'Missing' }))

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some((call) => String(call[0]).includes('coverage_status=missing')),
      ).toBe(true)
    })
  })

  test('filters opportunities by lifecycle state quick filter', async () => {
    const { user, fetchMock } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/opportunities?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('Opportunity list')
    await user.click(screen.getByRole('button', { name: 'Accepted' }))

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some((call) => String(call[0]).includes('state_status=accepted')),
      ).toBe(true)
    })
  })

  test('supports bulk accept and updates state badge', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/opportunities?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('Opportunity list')
    await user.click(screen.getByLabelText('Select seo audit checklist'))
    await user.click(screen.getByRole('button', { name: 'Accept' }))

    const row = (await screen.findByText('seo audit checklist')).closest('tr')
    expect(row).not.toBeNull()
    expect(within(row as HTMLElement).getByText('Accepted')).toBeInTheDocument()
  })

  test('supports bulk dismiss and updates state badge', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/opportunities?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('Opportunity list')
    await user.click(screen.getByLabelText('Select seo audit checklist'))
    await user.click(screen.getByRole('button', { name: 'Dismiss' }))

    const row = (await screen.findByText('seo audit checklist')).closest('tr')
    expect(row).not.toBeNull()
    expect(within(row as HTMLElement).getByText('Dismissed')).toBeInTheDocument()
  })

  test('supports bulk promote and renders promoted route', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/opportunities?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('Opportunity list')
    await user.click(screen.getByLabelText('Select technical seo guide'))
    await user.click(screen.getByRole('button', { name: 'Promote' }))

    const row = (await screen.findByText('technical seo guide')).closest('tr')
    expect(row).not.toBeNull()
    expect(within(row as HTMLElement).getByText('Promoted')).toBeInTheDocument()

    renderSemstormRoute('/sites/5/competitive-gap/semstorm/promoted?active_crawl_id=11&baseline_crawl_id=10')
    expect(await screen.findByText('Semstorm promoted backlog')).toBeInTheDocument()
    expect(await screen.findByText('Promoted backlog')).toBeInTheDocument()
    expect((await screen.findAllByText('seo audit checklist')).length).toBeGreaterThan(0)
  })

  test('creates a plan from promoted selection', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/promoted?active_crawl_id=11&baseline_crawl_id=10',
      {
        promoted: {
          site_id: 5,
          summary: {
            total_items: 1,
            promotion_status_counts: {
              active: 1,
              archived: 0,
            },
          },
          items: [
            {
              id: 92,
              site_id: 5,
              opportunity_key: 'semstorm:def456',
              source_run_id: 1,
              keyword: 'technical seo guide',
              normalized_keyword: 'technical seo guide',
              bucket: 'quick_win',
              decision_type: 'expand_existing_page',
              opportunity_score_v2: 72,
              coverage_status: 'weak_coverage',
              best_match_page_url: 'https://example.com/technical-seo',
              gsc_signal_status: 'present',
              promotion_status: 'active',
              has_plan: false,
              plan_id: null,
              plan_state_status: null,
              created_at: '2026-03-21T12:10:00Z',
              updated_at: '2026-03-21T12:10:00Z',
            },
          ],
        },
        plans: {
          site_id: 5,
          summary: {
            total_count: 0,
            state_counts: { planned: 0, in_progress: 0, done: 0, archived: 0 },
            target_page_type_counts: {
              new_page: 0,
              expand_existing: 0,
              refresh_existing: 0,
              cluster_support: 0,
            },
          },
          items: [],
        },
      },
    )

    await screen.findByText('Promoted backlog')
    await user.click(screen.getByLabelText('Select promoted technical seo guide'))
    await user.click(screen.getByRole('button', { name: 'Create plan' }))

    expect(await screen.findByText(/Created 1 plan items/)).toBeInTheDocument()
    expect(await screen.findByText('Planned')).toBeInTheDocument()
  })

  test('renders plans route and supports filters', async () => {
    const { user, fetchMock } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/plans?active_crawl_id=11&baseline_crawl_id=10',
    )

    expect(await screen.findByText('Semstorm plans')).toBeInTheDocument()
    expect(await screen.findByText('Planning list')).toBeInTheDocument()
    expect(await screen.findByText('Create page for seo audit checklist')).toBeInTheDocument()
    expect((await screen.findAllByText('Brief: Draft')).length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Select plan seo audit checklist')).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Planned' }))

    await waitFor(() => {
      expect(fetchMock.mock.calls.some((call) => String(call[0]).includes('state_status=planned'))).toBe(true)
    })
  })

  test('supports editing plan details and updating plan status', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/plans?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('Plan #301')
    const titleInput = screen.getByLabelText('Plan title')
    await user.clear(titleInput)
    await user.type(titleInput, 'SEO audit working plan')

    const noteInput = screen.getByLabelText('Planning note')
    await user.clear(noteInput)
    await user.type(noteInput, 'Draft outline for next sprint')

    await user.selectOptions(screen.getByLabelText('Target page type'), 'cluster_support')
    await user.click(screen.getByRole('button', { name: 'Save plan' }))

    expect(await screen.findByText('Plan changes saved.')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Status'), 'in_progress')
    await user.click(screen.getByRole('button', { name: 'Update status' }))

    expect(await screen.findByText('Status updated to In progress.')).toBeInTheDocument()
  })

  test('realigns stale plan_id with the visible filtered plan list', async () => {
    renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/plans?active_crawl_id=11&baseline_crawl_id=10&plan_id=302&search=checklist',
      {
        plans: {
          site_id: 5,
          summary: {
            total_count: 2,
            state_counts: { planned: 2, in_progress: 0, done: 0, archived: 0 },
            target_page_type_counts: {
              new_page: 1,
              expand_existing: 1,
              refresh_existing: 0,
              cluster_support: 0,
            },
          },
          items: [
            plansPayload.items[0],
            {
              id: 302,
              site_id: 5,
              promoted_item_id: 92,
              keyword: 'technical seo guide',
              normalized_keyword: 'technical seo guide',
              source_run_id: 1,
              state_status: 'planned',
              decision_type_snapshot: 'expand_existing_page',
              bucket_snapshot: 'quick_win',
              coverage_status_snapshot: 'weak_coverage',
              opportunity_score_v2_snapshot: 72,
              best_match_page_url_snapshot: 'https://example.com/technical-seo',
              gsc_signal_status_snapshot: 'present',
              plan_title: 'Expand page for technical seo guide',
              plan_note: null,
              target_page_type: 'expand_existing',
              proposed_slug: null,
              proposed_primary_keyword: 'technical seo guide',
              proposed_secondary_keywords: ['technical seo'],
              has_brief: false,
              brief_id: null,
              brief_state_status: null,
              created_at: '2026-03-21T13:30:00Z',
              updated_at: '2026-03-21T13:30:00Z',
            },
          ],
        },
      },
    )

    expect(await screen.findByText('Planning list')).toBeInTheDocument()
    expect(await screen.findByText('Plan #301')).toBeInTheDocument()
    expect(screen.queryByText('Plan #302')).not.toBeInTheDocument()
  })

  test('creates a brief from plan selection', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/plans?active_crawl_id=11&baseline_crawl_id=10',
      {
        plans: {
          site_id: 5,
          summary: {
            total_count: 1,
            state_counts: { planned: 1, in_progress: 0, done: 0, archived: 0 },
            target_page_type_counts: {
              new_page: 1,
              expand_existing: 0,
              refresh_existing: 0,
              cluster_support: 0,
            },
          },
          items: [
            {
              id: 302,
              site_id: 5,
              promoted_item_id: 92,
              keyword: 'technical seo guide',
              normalized_keyword: 'technical seo guide',
              source_run_id: 1,
              state_status: 'planned',
              decision_type_snapshot: 'expand_existing_page',
              bucket_snapshot: 'quick_win',
              coverage_status_snapshot: 'weak_coverage',
              opportunity_score_v2_snapshot: 72,
              best_match_page_url_snapshot: 'https://example.com/technical-seo',
              gsc_signal_status_snapshot: 'present',
              plan_title: 'Expand page for technical seo guide',
              plan_note: null,
              target_page_type: 'expand_existing',
              proposed_slug: null,
              proposed_primary_keyword: 'technical seo guide',
              proposed_secondary_keywords: ['technical seo'],
              has_brief: false,
              brief_id: null,
              brief_state_status: null,
              created_at: '2026-03-21T13:30:00Z',
              updated_at: '2026-03-21T13:30:00Z',
            },
          ],
        },
        briefs: {
          site_id: 5,
          summary: {
            total_count: 0,
            state_counts: { draft: 0, ready: 0, in_execution: 0, completed: 0, archived: 0 },
            brief_type_counts: {
              new_page: 0,
              expand_existing: 0,
              refresh_existing: 0,
              cluster_support: 0,
            },
            intent_counts: {
              informational: 0,
              commercial: 0,
              transactional: 0,
              navigational: 0,
              mixed: 0,
            },
          },
          items: [],
        },
      },
    )

    await screen.findByText('Planning list')
    await user.click(screen.getByLabelText('Select plan technical seo guide'))
    await user.click(screen.getByRole('button', { name: 'Create brief' }))

    expect(await screen.findByText(/Created 1 briefs/)).toBeInTheDocument()
    expect((await screen.findAllByText('Brief: Draft')).length).toBeGreaterThan(0)
  })

  test('renders briefs route and supports filters', async () => {
    renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10',
    )

    expect(await screen.findByText('Semstorm briefs')).toBeInTheDocument()
    expect(await screen.findByText('Brief list')).toBeInTheDocument()
    expect(await screen.findByText('New page brief: SEO Audit Checklist')).toBeInTheDocument()

    const searchInput = screen.getByPlaceholderText('Title, keyword, slug')
    fireEvent.change(searchInput, { target: { value: 'checklist' } })

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Title, keyword, slug')).toHaveValue('checklist')
    })
  })

  test('supports editing brief details and updating brief status', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('Brief #401')

    const titleInput = screen.getByLabelText('Brief title')
    await user.clear(titleInput)
    await user.type(titleInput, 'SEO audit checklist execution brief')

    const goalInput = screen.getByLabelText('Content goal')
    await user.clear(goalInput)
    await user.type(goalInput, 'Turn the checklist topic into a publish-ready execution packet.')

    await user.selectOptions(screen.getByLabelText('Search intent'), 'commercial')
    await user.click(screen.getByRole('button', { name: 'Save brief' }))

    expect(await screen.findByText('Brief changes saved.')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Status'), 'ready')
    await user.click(screen.getByRole('button', { name: 'Update status' }))

    expect(await screen.findByText('Brief status updated to Ready.')).toBeInTheDocument()
  })

  test('supports execution actions and metadata on briefs page', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('Execution handoff')
    expect(screen.queryByRole('button', { name: 'Mark completed' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Mark ready' }))
    expect(await screen.findByText('Execution status updated to Ready.')).toBeInTheDocument()

    const assigneeInput = screen.getByLabelText('Assignee')
    await user.clear(assigneeInput)
    await user.type(assigneeInput, 'Marta')

    const noteInput = screen.getByLabelText('Execution note')
    await user.clear(noteInput)
    await user.type(noteInput, 'Ready for editorial handoff this sprint.')

    await user.click(screen.getByRole('button', { name: 'Save execution details' }))

    expect(await screen.findByText('Execution handoff details saved.')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Marta')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Ready for editorial handoff this sprint.')).toBeInTheDocument()
  })

  test('renders execution route and supports filters plus status actions', async () => {
    const { user, fetchMock } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/execution?active_crawl_id=11&baseline_crawl_id=10',
      {
        briefs: {
          ...briefsPayload,
          items: [
            {
              ...briefsPayload.items[0],
              state_status: 'ready',
              execution_status: 'ready',
              assignee: 'Marta',
              ready_at: '2026-03-21T14:18:00Z',
            },
          ],
        },
      },
    )

    expect(await screen.findByText('Semstorm execution')).toBeInTheDocument()
    expect(await screen.findByText('Execution board')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Marta' })).toBeInTheDocument()
    expect(await screen.findByText('Execution packet #401')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Start execution' }))
    expect(await screen.findByText('Execution status updated to In execution.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Marta' }))
    await waitFor(() => {
      expect(fetchMock.mock.calls.some((call) => String(call[0]).includes('assignee=Marta'))).toBe(true)
    })
  })

  test('preserves the selected brief when navigating from briefs to execution', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10&brief_id=402',
      {
        briefs: {
          site_id: 5,
          summary: {
            total_count: 2,
            state_counts: {
              draft: 2,
              ready: 0,
              in_execution: 0,
              completed: 0,
              archived: 0,
            },
            brief_type_counts: {
              new_page: 1,
              expand_existing: 1,
              refresh_existing: 0,
              cluster_support: 0,
            },
            intent_counts: {
              informational: 1,
              commercial: 0,
              transactional: 1,
              navigational: 0,
              mixed: 0,
            },
          },
          items: [
            briefsPayload.items[0],
            {
              id: 402,
              site_id: 5,
              plan_item_id: 302,
              brief_title: 'Expand existing brief: Technical SEO Guide',
              primary_keyword: 'technical seo guide',
              brief_type: 'expand_existing',
              search_intent: 'informational',
              state_status: 'draft',
              execution_status: 'draft',
              assignee: null,
              execution_note: null,
              ready_at: null,
              started_at: null,
              completed_at: null,
              archived_at: null,
              implementation_status: null,
              implemented_at: null,
              last_outcome_checked_at: null,
              recommended_page_title: 'Technical SEO Guide',
              proposed_url_slug: null,
              decision_type_snapshot: 'expand_existing_page',
              bucket_snapshot: 'quick_win',
              coverage_status_snapshot: 'weak_coverage',
              gsc_signal_status_snapshot: 'present',
              opportunity_score_v2_snapshot: 72,
              created_at: '2026-03-21T14:10:00Z',
              updated_at: '2026-03-21T14:10:00Z',
            },
          ],
        },
      },
    )

    expect(await screen.findByText('Brief #402')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Open execution' }))

    expect(await screen.findByText('Semstorm execution')).toBeInTheDocument()
    expect(await screen.findByText('Execution packet #402')).toBeInTheDocument()
  })

  test('marks a completed brief as implemented from execution view', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/execution?active_crawl_id=11&baseline_crawl_id=10',
      {
        briefs: {
          ...briefsPayload,
          items: [
            {
              ...briefsPayload.items[0],
              state_status: 'completed',
              execution_status: 'completed',
              completed_at: '2026-03-21T14:30:00Z',
            },
          ],
        },
      },
    )

    expect(await screen.findByText('Execution lifecycle')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Mark implemented' }))

    expect(await screen.findByText('Implementation state updated to Implemented.')).toBeInTheDocument()
    expect(await screen.findAllByText('Implemented: Implemented')).not.toHaveLength(0)
  })

  test('renders implemented route with outcome details and filters', async () => {
    const { user, fetchMock } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/implemented?active_crawl_id=11&baseline_crawl_id=10',
      {
        briefs: {
          ...briefsPayload,
          items: [
            {
              ...briefsPayload.items[0],
              state_status: 'completed',
              execution_status: 'completed',
              completed_at: '2026-02-12T14:30:00Z',
              implementation_status: 'implemented',
              implemented_at: '2026-02-13T09:00:00Z',
              last_outcome_checked_at: '2026-03-20T12:00:00Z',
            },
          ],
        },
      },
    )

    expect(await screen.findByText('Semstorm implemented')).toBeInTheDocument()
    expect(await screen.findByText('Implemented list')).toBeInTheDocument()
    expect(await screen.findByText('Outcome summary')).toBeInTheDocument()
    expect(await screen.findAllByText('Positive signal')).not.toHaveLength(0)
    expect((await screen.findAllByText('https://example.com/seo-audit-checklist')).length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Positive signal' }))
    await waitFor(() => {
      expect(fetchMock.mock.calls.some((call) => String(call[0]).includes('outcome_status=positive_signal'))).toBe(
        true,
      )
    })
  })

  test('shows implemented empty state when nothing is tracked yet', async () => {
    renderSemstormRoute('/sites/5/competitive-gap/semstorm/implemented?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('No implemented Semstorm briefs yet')).toBeInTheDocument()
  })

  test('renders brief AI enrichment suggestions and action', async () => {
    renderSemstormRoute('/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByRole('button', { name: 'Enrich with AI' })).toBeInTheDocument()
    expect(await screen.findByText('Current scaffold')).toBeInTheDocument()
    expect(await screen.findByText('Suggested changes')).toBeInTheDocument()
    expect(await screen.findByText('Execution brief: SEO Audit Checklist')).toBeInTheDocument()
    expect(await screen.findByText('Keep the intro practical and outcome-focused.')).toBeInTheDocument()
    expect(
      await screen.findByText('Avoid turning the brief into a generic SEO basics article.'),
    ).toBeInTheDocument()
  })

  test('applies brief AI suggestions and updates the brief draft', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('AI suggestions')
    await user.click(screen.getByRole('button', { name: 'Apply suggestions' }))

    expect(await screen.findByText('AI suggestions applied to the brief.')).toBeInTheDocument()
    expect(await screen.findByDisplayValue('Execution brief: SEO Audit Checklist')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Apply suggestions' })).toBeDisabled()
  })

  test('creates a new AI enrichment run from an empty brief state', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10',
      {
        briefEnrichmentRuns: {
          site_id: 5,
          brief_id: 401,
          summary: {
            total_count: 0,
            completed_count: 0,
            failed_count: 0,
            applied_count: 0,
          },
          items: [],
        },
      },
    )

    expect(await screen.findByText(/No AI enrichment runs yet/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Enrich with AI' }))

    expect(await screen.findByText('AI enrichment run #501 is ready for review.')).toBeInTheDocument()
    expect(await screen.findByText('Execution brief: SEO Audit Checklist')).toBeInTheDocument()
  })

  test('renders AI enrichment loading state', async () => {
    renderSemstormRoute('/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10', {
      briefEnrichmentRunsDelayMs: 2000,
    })

    expect(await screen.findByText('Semstorm briefs')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('Loading AI enrichment runs')).toBeInTheDocument()
    })
  })

  test('renders AI enrichment error state', async () => {
    renderSemstormRoute('/sites/5/competitive-gap/semstorm/briefs?active_crawl_id=11&baseline_crawl_id=10', {
      briefEnrichmentRunsStatus: 500,
    })

    expect(await screen.findByText('Could not load AI enrichment runs')).toBeInTheDocument()
  })

  test('opens opportunity details drawer content', async () => {
    const { user } = renderSemstormRoute(
      '/sites/5/competitive-gap/semstorm/opportunities?active_crawl_id=11&baseline_crawl_id=10',
    )

    await screen.findByText('technical seo guide')
    await user.click(screen.getAllByText('Details')[0])

    expect(await screen.findByText('Coverage score v1: 10')).toBeInTheDocument()
    expect(await screen.findByText(/competitor-a.com, competitor-b.com/)).toBeInTheDocument()
  })

  test('renders semstorm base route via discovery redirect', async () => {
    renderSemstormRoute('/sites/5/competitive-gap/semstorm?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Semstorm discovery')).toBeInTheDocument()
  })
})
