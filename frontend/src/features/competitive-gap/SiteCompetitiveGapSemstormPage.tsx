import { startTransition, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api/client'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FilterPanel } from '../../components/FilterPanel'
import { LoadingState } from '../../components/LoadingState'
import { QuickFilterBar } from '../../components/QuickFilterBar'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type {
  SemstormBriefEnrichmentRun,
  SemstormBriefImplementationStatusUpdateInput,
  SemstormBriefSearchIntent,
  SemstormBriefStateStatus,
  SemstormExecutionQueryParams,
  SemstormBriefsQueryParams,
  SemstormBriefType,
  SemstormBriefUpdateInput,
  SemstormCoverageStatus,
  SemstormCreateBriefInput,
  SemstormCreatePlanInput,
  SemstormDecisionType,
  SemstormDiscoveryRunCreateInput,
  SemstormGscSignalStatus,
  SemstormImplementedQueryParams,
  SemstormImplementationStatus,
  SemstormOpportunitiesQueryParams,
  SemstormOpportunityBucket,
  SemstormOpportunityStateStatus,
  SemstormOutcomeStatus,
  SemstormPlanStateStatus,
  SemstormPlansQueryParams,
  SemstormPlanTargetPageType,
  SemstormPlanUpdateInput,
  SemstormResultType,
} from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime, formatPercent, truncateText } from '../../utils/format'
import { buildQueryString, mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { useSiteWorkspaceContext } from '../sites/context'
import {
  buildSiteCompetitiveGapPath,
  buildSiteCompetitiveGapResultsPath,
  buildSiteCompetitiveGapSemstormDiscoveryPath,
  buildSiteCompetitiveGapSemstormBriefsPath,
  buildSiteCompetitiveGapSemstormExecutionPath,
  buildSiteCompetitiveGapSemstormImplementedPath,
  buildSiteCompetitiveGapSemstormOpportunitiesPath,
  buildSiteCompetitiveGapSemstormPlansPath,
  buildSiteCompetitiveGapSemstormPromotedPath,
} from '../sites/routes'
import {
  useAcceptSiteCompetitiveGapSemstormOpportunitiesMutation,
  useCreateSiteCompetitiveGapSemstormBriefsMutation,
  useCreateSiteCompetitiveGapSemstormBriefEnrichmentMutation,
  useCreateSiteCompetitiveGapSemstormDiscoveryRunMutation,
  useCreateSiteCompetitiveGapSemstormPlansMutation,
  useApplySiteCompetitiveGapSemstormBriefEnrichmentMutation,
  useDismissSiteCompetitiveGapSemstormOpportunitiesMutation,
  usePromoteSiteCompetitiveGapSemstormOpportunitiesMutation,
  useSiteCompetitiveGapSemstormBriefQuery,
  useSiteCompetitiveGapSemstormBriefEnrichmentRunsQuery,
  useSiteCompetitiveGapSemstormBriefsQuery,
  useSiteCompetitiveGapSemstormDiscoveryRunQuery,
  useSiteCompetitiveGapSemstormDiscoveryRunsQuery,
  useSiteCompetitiveGapSemstormExecutionQuery,
  useSiteCompetitiveGapSemstormImplementedQuery,
  useSiteCompetitiveGapSemstormOpportunitiesQuery,
  useSiteCompetitiveGapSemstormPlanQuery,
  useSiteCompetitiveGapSemstormPlansQuery,
  useSiteCompetitiveGapSemstormPromotedQuery,
  useUpdateSiteCompetitiveGapSemstormBriefMutation,
  useUpdateSiteCompetitiveGapSemstormBriefExecutionMutation,
  useUpdateSiteCompetitiveGapSemstormBriefImplementationStatusMutation,
  useUpdateSiteCompetitiveGapSemstormBriefExecutionStatusMutation,
  useUpdateSiteCompetitiveGapSemstormBriefStatusMutation,
  useUpdateSiteCompetitiveGapSemstormPlanMutation,
  useUpdateSiteCompetitiveGapSemstormPlanStatusMutation,
} from './api'

const surfaceClass =
  'rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const sectionClass =
  'rounded-3xl border border-stone-300 bg-white/85 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const panelClass =
  'rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/85'
const actionClass =
  'inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:border-slate-500 dark:hover:bg-slate-800'
const primaryActionClass =
  'inline-flex rounded-full bg-teal-700 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-teal-600 disabled:cursor-not-allowed disabled:opacity-60'
const fieldLabelClass = 'grid gap-1 text-sm text-stone-700 dark:text-slate-300'
const fieldControlClass =
  'rounded-2xl border border-stone-300 bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-teal-400 dark:focus:ring-teal-500/30'
const textAreaClass = `${fieldControlClass} min-h-[120px] resize-y`

const opportunityBuckets: SemstormOpportunityBucket[] = ['quick_win', 'core_opportunity', 'watchlist']
const coverageStatuses: SemstormCoverageStatus[] = ['missing', 'weak_coverage', 'covered']
const decisionTypes: SemstormDecisionType[] = ['create_new_page', 'expand_existing_page', 'monitor_only']
const stateStatuses: SemstormOpportunityStateStatus[] = ['new', 'accepted', 'dismissed', 'promoted']
const planStateStatuses: SemstormPlanStateStatus[] = ['planned', 'in_progress', 'done', 'archived']
const planTargetPageTypes: SemstormPlanTargetPageType[] = [
  'new_page',
  'expand_existing',
  'refresh_existing',
  'cluster_support',
]
const briefStateStatuses: SemstormBriefStateStatus[] = [
  'draft',
  'ready',
  'in_execution',
  'completed',
  'archived',
]
const briefTypes: SemstormBriefType[] = ['new_page', 'expand_existing', 'refresh_existing', 'cluster_support']
const briefSearchIntents: SemstormBriefSearchIntent[] = [
  'informational',
  'commercial',
  'transactional',
  'navigational',
  'mixed',
]
const implementationStatuses: SemstormImplementationStatus[] = ['too_early', 'implemented', 'evaluated', 'archived']
const outcomeStatuses: SemstormOutcomeStatus[] = ['too_early', 'no_signal', 'weak_signal', 'positive_signal']

type Mode = 'discovery' | 'opportunities' | 'promoted' | 'plans' | 'briefs' | 'execution' | 'implemented'

function readResultType(value: string | null): SemstormResultType {
  return value === 'paid' ? 'paid' : 'organic'
}

function readCoverageStatus(value: string | null): SemstormCoverageStatus | undefined {
  return value === 'missing' || value === 'weak_coverage' || value === 'covered' ? value : undefined
}

function readBucket(value: string | null): SemstormOpportunityBucket | undefined {
  return value === 'quick_win' || value === 'core_opportunity' || value === 'watchlist' ? value : undefined
}

function readDecisionType(value: string | null): SemstormDecisionType | undefined {
  return value === 'create_new_page' || value === 'expand_existing_page' || value === 'monitor_only'
    ? value
    : undefined
}

function readStateStatus(value: string | null): SemstormOpportunityStateStatus | undefined {
  return value === 'new' || value === 'accepted' || value === 'dismissed' || value === 'promoted'
    ? value
    : undefined
}

function readPlanStateStatus(value: string | null): SemstormPlanStateStatus | undefined {
  return value === 'planned' || value === 'in_progress' || value === 'done' || value === 'archived'
    ? value
    : undefined
}

function readPlanTargetPageType(value: string | null): SemstormPlanTargetPageType | undefined {
  return value === 'new_page' ||
    value === 'expand_existing' ||
    value === 'refresh_existing' ||
    value === 'cluster_support'
    ? value
    : undefined
}

function readBriefStateStatus(value: string | null): SemstormBriefStateStatus | undefined {
  return value === 'draft' ||
    value === 'ready' ||
    value === 'in_execution' ||
    value === 'completed' ||
    value === 'archived'
    ? value
    : undefined
}

function readBriefType(value: string | null): SemstormBriefType | undefined {
  return value === 'new_page' ||
    value === 'expand_existing' ||
    value === 'refresh_existing' ||
    value === 'cluster_support'
    ? value
    : undefined
}

function readBriefSearchIntent(value: string | null): SemstormBriefSearchIntent | undefined {
  return value === 'informational' ||
    value === 'commercial' ||
    value === 'transactional' ||
    value === 'navigational' ||
    value === 'mixed'
    ? value
    : undefined
}

function readImplementationStatus(value: string | null): SemstormImplementationStatus | undefined {
  return value === 'too_early' || value === 'implemented' || value === 'evaluated' || value === 'archived'
    ? value
    : undefined
}

function readOutcomeStatus(value: string | null): SemstormOutcomeStatus | undefined {
  return value === 'too_early' || value === 'no_signal' || value === 'weak_signal' || value === 'positive_signal'
    ? value
    : undefined
}

function readHasGscSignal(value: string | null): boolean | undefined {
  if (value === 'true') return true
  if (value === 'false') return false
  return undefined
}

function appendQueryString(path: string, params: Record<string, string | number | boolean | undefined>) {
  const query = buildQueryString(params)
  return query ? `${path}${path.includes('?') ? '&' : '?'}${query}` : path
}

function formatNumber(value: number | null | undefined) {
  return value === null || value === undefined ? '-' : new Intl.NumberFormat().format(value)
}

function formatCpc(value: number | null | undefined) {
  return value === null || value === undefined ? '-' : `$${value.toFixed(2)}`
}

function toneClass(tone: 'stone' | 'teal' | 'amber' | 'rose') {
  if (tone === 'teal') {
    return 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/60 dark:text-teal-200'
  }
  if (tone === 'amber') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200'
  }
  if (tone === 'rose') {
    return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/60 dark:text-rose-200'
  }
  return 'border-stone-300 bg-stone-100 text-stone-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
}

function renderBadge(label: string, tone: 'stone' | 'teal' | 'amber' | 'rose' = 'stone') {
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${toneClass(tone)}`}>
      {label}
    </span>
  )
}

function RetriableErrorState({
  title,
  message,
  onRetry,
}: {
  title: string
  message: string
  onRetry: () => void
}) {
  return (
    <div className="space-y-3">
      <ErrorState title={title} message={message} />
      <div className="flex flex-wrap gap-2">
        <button type="button" className={actionClass} onClick={onRetry}>
          Retry
        </button>
      </div>
    </div>
  )
}

function countLabel(counts: Partial<Record<string, number>>, keys: string[], labels: Record<string, string>) {
  return keys.map((key) => `${labels[key]}: ${formatNumber(counts[key] ?? 0)}`).join(' | ')
}

function runStatusTone(status: string) {
  if (status === 'completed') return 'teal'
  if (status === 'failed') return 'rose'
  return 'amber'
}

function coverageTone(status: SemstormCoverageStatus) {
  if (status === 'missing') return 'rose'
  if (status === 'weak_coverage') return 'amber'
  return 'teal'
}

function decisionTone(status: SemstormDecisionType) {
  if (status === 'create_new_page') return 'rose'
  if (status === 'expand_existing_page') return 'amber'
  return 'stone'
}

function gscTone(status: SemstormGscSignalStatus) {
  if (status === 'present') return 'teal'
  if (status === 'weak') return 'amber'
  return 'stone'
}

function stateTone(status: SemstormOpportunityStateStatus) {
  if (status === 'accepted') return 'teal'
  if (status === 'dismissed') return 'stone'
  if (status === 'promoted') return 'rose'
  return 'amber'
}

function planStateTone(status: SemstormPlanStateStatus) {
  if (status === 'done') return 'teal'
  if (status === 'in_progress') return 'amber'
  if (status === 'archived') return 'stone'
  return 'rose'
}

function planTargetTone(targetPageType: SemstormPlanTargetPageType) {
  if (targetPageType === 'new_page') return 'rose'
  if (targetPageType === 'expand_existing') return 'amber'
  if (targetPageType === 'refresh_existing') return 'teal'
  return 'stone'
}

function briefStateTone(status: SemstormBriefStateStatus) {
  if (status === 'ready' || status === 'completed') return 'teal'
  if (status === 'in_execution') return 'amber'
  if (status === 'archived') return 'stone'
  return 'rose'
}

function briefTypeTone(briefType: SemstormBriefType) {
  return planTargetTone(briefType)
}

function briefIntentTone(searchIntent: SemstormBriefSearchIntent) {
  if (searchIntent === 'transactional') return 'rose'
  if (searchIntent === 'commercial') return 'amber'
  if (searchIntent === 'informational') return 'teal'
  return 'stone'
}

function briefEnrichmentStatusTone(status: SemstormBriefEnrichmentRun['status']) {
  return status === 'completed' ? 'teal' : 'rose'
}

function briefEnrichmentStatusLabel(status: SemstormBriefEnrichmentRun['status']) {
  return status === 'completed' ? 'Completed' : 'Failed'
}

function briefEnrichmentEngineModeLabel(engineMode: SemstormBriefEnrichmentRun['engine_mode']) {
  return engineMode === 'llm' ? 'LLM' : 'Mock'
}

function implementationTone(status: SemstormImplementationStatus | null | undefined) {
  if (status === 'evaluated') return 'teal'
  if (status === 'too_early' || status === 'implemented') return 'amber'
  if (status === 'archived') return 'stone'
  return 'stone'
}

function outcomeTone(status: SemstormOutcomeStatus) {
  if (status === 'positive_signal') return 'teal'
  if (status === 'weak_signal' || status === 'too_early') return 'amber'
  return 'stone'
}

function hasBriefEnrichmentSuggestions(run: SemstormBriefEnrichmentRun | null) {
  if (run == null) {
    return false
  }
  const suggestions = run.suggestions
  return Boolean(
    suggestions.improved_brief_title?.trim() ||
      suggestions.improved_page_title?.trim() ||
      suggestions.improved_h1?.trim() ||
      suggestions.improved_angle_summary?.trim() ||
      suggestions.improved_sections.length ||
      suggestions.improved_internal_link_targets.length ||
      suggestions.editorial_notes.length ||
      suggestions.risk_flags.length,
  )
}

function bucketLabel(bucket: SemstormOpportunityBucket) {
  return {
    quick_win: 'Quick win',
    core_opportunity: 'Core opportunity',
    watchlist: 'Watchlist',
  }[bucket]
}

function decisionLabel(decisionType: SemstormDecisionType) {
  return {
    create_new_page: 'Create new page',
    expand_existing_page: 'Expand existing page',
    monitor_only: 'Monitor only',
  }[decisionType]
}

function coverageLabel(coverageStatus: SemstormCoverageStatus) {
  return {
    missing: 'Missing',
    weak_coverage: 'Weak coverage',
    covered: 'Covered',
  }[coverageStatus]
}

function gscLabel(status: SemstormGscSignalStatus) {
  return {
    none: 'None',
    weak: 'Weak',
    present: 'Present',
  }[status]
}

function stateLabel(status: SemstormOpportunityStateStatus) {
  return {
    new: 'New',
    accepted: 'Accepted',
    dismissed: 'Dismissed',
    promoted: 'Promoted',
  }[status]
}

function planStateLabel(status: SemstormPlanStateStatus) {
  return {
    planned: 'Planned',
    in_progress: 'In progress',
    done: 'Done',
    archived: 'Archived',
  }[status]
}

function planTargetPageTypeLabel(targetPageType: SemstormPlanTargetPageType) {
  return {
    new_page: 'New page',
    expand_existing: 'Expand existing',
    refresh_existing: 'Refresh existing',
    cluster_support: 'Cluster support',
  }[targetPageType]
}

function briefStateLabel(status: SemstormBriefStateStatus) {
  return {
    draft: 'Draft',
    ready: 'Ready',
    in_execution: 'In execution',
    completed: 'Completed',
    archived: 'Archived',
  }[status]
}

function briefTypeLabel(briefType: SemstormBriefType) {
  return {
    new_page: 'New page',
    expand_existing: 'Expand existing',
    refresh_existing: 'Refresh existing',
    cluster_support: 'Cluster support',
  }[briefType]
}

function briefIntentLabel(searchIntent: SemstormBriefSearchIntent) {
  return {
    informational: 'Informational',
    commercial: 'Commercial',
    transactional: 'Transactional',
    navigational: 'Navigational',
    mixed: 'Mixed',
  }[searchIntent]
}

function implementationLabel(status: SemstormImplementationStatus | null | undefined) {
  if (status === 'too_early') return 'Too early'
  if (status === 'implemented') return 'Implemented'
  if (status === 'evaluated') return 'Evaluated'
  if (status === 'archived') return 'Archived'
  return 'Not tracked'
}

function outcomeLabel(status: SemstormOutcomeStatus) {
  return {
    too_early: 'Too early',
    no_signal: 'No signal',
    weak_signal: 'Weak signal',
    positive_signal: 'Positive signal',
  }[status]
}

function parseSecondaryKeywords(text: string) {
  const deduped = new Set<string>()
  return text
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .filter((item) => {
      const key = item.toLowerCase()
      if (deduped.has(key)) {
        return false
      }
      deduped.add(key)
      return true
    })
}

function formatSecondaryKeywords(values: string[] | null | undefined) {
  return (values ?? []).join('\n')
}

function formatStringList(values: string[] | null | undefined) {
  return (values ?? []).join('\n')
}

function canTransitionBriefExecution(
  from: SemstormBriefStateStatus,
  to: SemstormBriefStateStatus,
) {
  if (from === 'draft') {
    return to === 'ready' || to === 'archived'
  }
  if (from === 'ready') {
    return to === 'in_execution' || to === 'archived'
  }
  if (from === 'in_execution') {
    return to === 'ready' || to === 'completed' || to === 'archived'
  }
  if (from === 'completed') {
    return to === 'archived'
  }
  return false
}

function resolveSelectedId(selectedId: number | undefined, visibleIds: number[]) {
  if (selectedId !== undefined && visibleIds.includes(selectedId)) {
    return selectedId
  }
  return visibleIds[0] ?? null
}

function SemstormNav({
  siteId,
  activeCrawlId,
  baselineCrawlId,
  mode,
  selectedRunId,
  selectedPlanId,
  selectedBriefId,
  selectedEnrichmentRunId,
}: {
  siteId: number
  activeCrawlId?: number | null
  baselineCrawlId?: number | null
  mode: Mode
  selectedRunId?: number | null
  selectedPlanId?: number | null
  selectedBriefId?: number | null
  selectedEnrichmentRunId?: number | null
}) {
  const context = { activeCrawlId, baselineCrawlId }
  const items = [
    { label: 'Overview', href: buildSiteCompetitiveGapPath(siteId, context), active: false },
    { label: 'Results', href: buildSiteCompetitiveGapResultsPath(siteId, context), active: false },
    {
      label: 'Discovery',
      href: appendQueryString(buildSiteCompetitiveGapSemstormDiscoveryPath(siteId, context), {
        run_id: selectedRunId ?? undefined,
      }),
      active: mode === 'discovery',
    },
    {
      label: 'Opportunities',
      href: appendQueryString(buildSiteCompetitiveGapSemstormOpportunitiesPath(siteId, context), {
        run_id: selectedRunId ?? undefined,
      }),
      active: mode === 'opportunities',
    },
    {
      label: 'Promoted',
      href: buildSiteCompetitiveGapSemstormPromotedPath(siteId, context),
      active: mode === 'promoted',
    },
    {
      label: 'Plans',
      href: appendQueryString(buildSiteCompetitiveGapSemstormPlansPath(siteId, context), {
        plan_id: selectedPlanId ?? undefined,
      }),
      active: mode === 'plans',
    },
    {
      label: 'Briefs',
      href: appendQueryString(buildSiteCompetitiveGapSemstormBriefsPath(siteId, context), {
        brief_id: selectedBriefId ?? undefined,
        enrichment_run_id: selectedEnrichmentRunId ?? undefined,
      }),
      active: mode === 'briefs',
    },
    {
      label: 'Execution',
      href: appendQueryString(buildSiteCompetitiveGapSemstormExecutionPath(siteId, context), {
        brief_id: selectedBriefId ?? undefined,
      }),
      active: mode === 'execution',
    },
    {
      label: 'Implemented',
      href: appendQueryString(buildSiteCompetitiveGapSemstormImplementedPath(siteId, context), {
        brief_id: selectedBriefId ?? undefined,
      }),
      active: mode === 'implemented',
    },
  ]
  return (
    <nav className="flex flex-wrap gap-2">
      {items.map((item) => (
        <Link
          key={item.href}
          to={item.href}
          className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
            item.active
              ? 'border border-stone-950 bg-stone-950 text-white shadow-sm dark:border-teal-400 dark:bg-teal-400 dark:text-slate-950'
              : 'border border-stone-300 bg-white text-stone-700 hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:bg-slate-900/85 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800'
          }`}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  )
}

export function SiteCompetitiveGapSemstormPage({ mode = 'discovery' }: { mode?: Mode }) {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedKeywords, setSelectedKeywords] = useState<string[]>([])
  const [selectedPromotedIds, setSelectedPromotedIds] = useState<number[]>([])
  const [selectedPlanIdsForBriefs, setSelectedPlanIdsForBriefs] = useState<number[]>([])
  const [createPlanTargetPageType, setCreatePlanTargetPageType] =
    useState<SemstormPlanTargetPageType>('new_page')
  const [executionDraft, setExecutionDraft] = useState({
    assignee: '',
    execution_note: '',
  })
  const [planDraft, setPlanDraft] = useState<SemstormPlanUpdateInput>({
    state_status: 'planned',
    plan_title: '',
    plan_note: '',
    target_page_type: 'new_page',
    proposed_slug: '',
    proposed_primary_keyword: '',
    proposed_secondary_keywords: [],
  })
  const [secondaryKeywordsText, setSecondaryKeywordsText] = useState('')
  const [briefDraft, setBriefDraft] = useState<SemstormBriefUpdateInput>({
    state_status: 'draft',
    brief_title: '',
    brief_type: 'new_page',
    primary_keyword: '',
    secondary_keywords: [],
    search_intent: 'mixed',
    target_url_existing: '',
    proposed_url_slug: '',
    recommended_page_title: '',
    recommended_h1: '',
    content_goal: '',
    angle_summary: '',
    sections: [],
    internal_link_targets: [],
    source_notes: [],
  })
  const [briefSecondaryKeywordsText, setBriefSecondaryKeywordsText] = useState('')
  const [briefSectionsText, setBriefSectionsText] = useState('')
  const [briefInternalLinksText, setBriefInternalLinksText] = useState('')
  const [briefSourceNotesText, setBriefSourceNotesText] = useState('')
  const [formState, setFormState] = useState<SemstormDiscoveryRunCreateInput>({
    max_competitors: 10,
    max_keywords_per_competitor: 25,
    include_basic_stats: true,
    result_type: 'organic',
    competitors_type: 'all',
  })

  const documentTitle = {
    discovery: `Semstorm discovery - ${site.domain}`,
    opportunities: `Semstorm opportunities - ${site.domain}`,
    promoted: `Semstorm promoted backlog - ${site.domain}`,
    plans: `Semstorm plans - ${site.domain}`,
    briefs: `Semstorm briefs - ${site.domain}`,
    execution: `Semstorm execution - ${site.domain}`,
    implemented: `Semstorm implemented - ${site.domain}`,
  }[mode]
  useDocumentTitle(documentTitle)

  const selectedRunId = parseIntegerParam(searchParams.get('run_id'), undefined)
  const selectedPlanId = parseIntegerParam(searchParams.get('plan_id'), undefined)
  const selectedBriefId = parseIntegerParam(searchParams.get('brief_id'), undefined)
  const selectedEnrichmentRunId = parseIntegerParam(searchParams.get('enrichment_run_id'), undefined)

  const discoveryRunsQuery = useSiteCompetitiveGapSemstormDiscoveryRunsQuery(site.id)
  const latestRun = discoveryRunsQuery.data?.[0]
  const discoveryRunIds = (discoveryRunsQuery.data ?? []).map((run) => run.run_id)
  const validatedSelectedRunId =
    selectedRunId !== undefined && discoveryRunIds.includes(selectedRunId) ? selectedRunId : undefined
  const effectiveRunId = validatedSelectedRunId ?? latestRun?.run_id ?? null
  const navigationRunId = mode === 'discovery' ? effectiveRunId : validatedSelectedRunId ?? null
  const discoveryRunQuery = useSiteCompetitiveGapSemstormDiscoveryRunQuery(
    site.id,
    effectiveRunId,
    mode === 'discovery' && discoveryRunsQuery.isSuccess && effectiveRunId !== null,
  )
  const createRunMutation = useCreateSiteCompetitiveGapSemstormDiscoveryRunMutation(site.id)

  const opportunityParams = useMemo<SemstormOpportunitiesQueryParams>(
    () => ({
      run_id: discoveryRunsQuery.isSuccess ? validatedSelectedRunId : selectedRunId,
      bucket: readBucket(searchParams.get('bucket')),
      coverage_status: readCoverageStatus(searchParams.get('coverage_status')),
      decision_type: readDecisionType(searchParams.get('decision_type')),
      state_status: readStateStatus(searchParams.get('state_status')),
      has_gsc_signal: readHasGscSignal(searchParams.get('has_gsc_signal')),
      only_actionable: searchParams.get('only_actionable') === 'true' ? true : undefined,
      limit: parseIntegerParam(searchParams.get('limit'), 100),
    }),
    [discoveryRunsQuery.isSuccess, searchParams, selectedRunId, validatedSelectedRunId],
  )
  const opportunitiesQuery = useSiteCompetitiveGapSemstormOpportunitiesQuery(
    site.id,
    opportunityParams,
    mode === 'opportunities',
  )
  const acceptMutation = useAcceptSiteCompetitiveGapSemstormOpportunitiesMutation(site.id)
  const dismissMutation = useDismissSiteCompetitiveGapSemstormOpportunitiesMutation(site.id)
  const promoteMutation = usePromoteSiteCompetitiveGapSemstormOpportunitiesMutation(site.id)

  const promotedQuery = useSiteCompetitiveGapSemstormPromotedQuery(site.id, mode === 'promoted')
  const createPlanMutation = useCreateSiteCompetitiveGapSemstormPlansMutation(site.id)

  const plansParams = useMemo<SemstormPlansQueryParams>(
    () => ({
      state_status: readPlanStateStatus(searchParams.get('state_status')),
      target_page_type: readPlanTargetPageType(searchParams.get('target_page_type')),
      search: searchParams.get('search') || undefined,
      limit: parseIntegerParam(searchParams.get('limit'), 100),
    }),
    [searchParams],
  )
  const plansQuery = useSiteCompetitiveGapSemstormPlansQuery(site.id, plansParams, mode === 'plans')
  const visiblePlanIds = (plansQuery.data?.items ?? []).map((item) => item.id)
  const effectivePlanId = resolveSelectedId(selectedPlanId, visiblePlanIds)
  const navigationPlanId = mode === 'plans' ? effectivePlanId : selectedPlanId ?? null
  const planQuery = useSiteCompetitiveGapSemstormPlanQuery(
    site.id,
    effectivePlanId,
    mode === 'plans' && plansQuery.isSuccess && effectivePlanId !== null,
  )
  const updatePlanStatusMutation = useUpdateSiteCompetitiveGapSemstormPlanStatusMutation(site.id)
  const updatePlanMutation = useUpdateSiteCompetitiveGapSemstormPlanMutation(site.id)
  const createBriefMutation = useCreateSiteCompetitiveGapSemstormBriefsMutation(site.id)

  const briefsParams = useMemo<SemstormBriefsQueryParams>(
    () => ({
      state_status: readBriefStateStatus(searchParams.get('state_status')),
      brief_type: readBriefType(searchParams.get('brief_type')),
      search_intent: readBriefSearchIntent(searchParams.get('search_intent')),
      search: searchParams.get('search') || undefined,
      limit: parseIntegerParam(searchParams.get('limit'), 100),
    }),
    [searchParams],
  )
  const briefsQuery = useSiteCompetitiveGapSemstormBriefsQuery(site.id, briefsParams, mode === 'briefs')
  const executionParams = useMemo<SemstormExecutionQueryParams>(
    () => ({
      execution_status: readBriefStateStatus(searchParams.get('execution_status')),
      assignee: searchParams.get('assignee') || undefined,
      brief_type: readBriefType(searchParams.get('brief_type')),
      search: searchParams.get('search') || undefined,
      limit: parseIntegerParam(searchParams.get('limit'), 100),
    }),
    [searchParams],
  )
  const executionQuery = useSiteCompetitiveGapSemstormExecutionQuery(site.id, executionParams, mode === 'execution')
  const implementedParams = useMemo<SemstormImplementedQueryParams>(
    () => ({
      implementation_status: readImplementationStatus(searchParams.get('implementation_status')),
      outcome_status: readOutcomeStatus(searchParams.get('outcome_status')),
      brief_type: readBriefType(searchParams.get('brief_type')),
      search: searchParams.get('search') || undefined,
      window_days: parseIntegerParam(searchParams.get('window_days'), 30),
      limit: parseIntegerParam(searchParams.get('limit'), 100),
    }),
    [searchParams],
  )
  const implementedQuery = useSiteCompetitiveGapSemstormImplementedQuery(
    site.id,
    implementedParams,
    mode === 'implemented',
  )
  const visibleBriefIds =
    mode === 'execution'
      ? (executionQuery.data?.items ?? []).map((item) => item.brief_id)
      : mode === 'implemented'
        ? (implementedQuery.data?.items ?? []).map((item) => item.brief_id)
        : (briefsQuery.data?.items ?? []).map((item) => item.id)
  const effectiveBriefId =
    mode === 'briefs' || mode === 'execution' || mode === 'implemented'
      ? resolveSelectedId(selectedBriefId, visibleBriefIds)
      : null
  const navigationBriefId =
    mode === 'briefs' || mode === 'execution' || mode === 'implemented'
      ? effectiveBriefId
      : selectedBriefId ?? null
  const briefQuery = useSiteCompetitiveGapSemstormBriefQuery(
    site.id,
    effectiveBriefId,
    (mode === 'briefs' || mode === 'execution' || mode === 'implemented') &&
      ((mode === 'briefs' && briefsQuery.isSuccess) ||
        (mode === 'execution' && executionQuery.isSuccess) ||
        (mode === 'implemented' && implementedQuery.isSuccess)) &&
      effectiveBriefId !== null,
  )
  const briefEnrichmentRunsQuery = useSiteCompetitiveGapSemstormBriefEnrichmentRunsQuery(
    site.id,
    effectiveBriefId,
    mode === 'briefs' && effectiveBriefId !== null,
  )
  const updateBriefStatusMutation = useUpdateSiteCompetitiveGapSemstormBriefStatusMutation(site.id)
  const updateBriefExecutionStatusMutation = useUpdateSiteCompetitiveGapSemstormBriefExecutionStatusMutation(site.id)
  const updateBriefMutation = useUpdateSiteCompetitiveGapSemstormBriefMutation(site.id)
  const updateBriefExecutionMutation = useUpdateSiteCompetitiveGapSemstormBriefExecutionMutation(site.id)
  const updateBriefImplementationStatusMutation =
    useUpdateSiteCompetitiveGapSemstormBriefImplementationStatusMutation(site.id)
  const createBriefEnrichmentMutation = useCreateSiteCompetitiveGapSemstormBriefEnrichmentMutation(site.id)
  const applyBriefEnrichmentMutation = useApplySiteCompetitiveGapSemstormBriefEnrichmentMutation(site.id)
  const visibleEnrichmentRunIds = (briefEnrichmentRunsQuery.data?.items ?? []).map((item) => item.id)
  const effectiveEnrichmentRunId = resolveSelectedId(selectedEnrichmentRunId, visibleEnrichmentRunIds)
  const navigationEnrichmentRunId = mode === 'briefs' ? effectiveEnrichmentRunId : selectedEnrichmentRunId ?? null
  const selectedEnrichmentRun = useMemo(
    () =>
      briefEnrichmentRunsQuery.data?.items.find((item) => item.id === effectiveEnrichmentRunId) ??
      briefEnrichmentRunsQuery.data?.items[0] ??
      null,
    [briefEnrichmentRunsQuery.data?.items, effectiveEnrichmentRunId],
  )
  const selectedEnrichmentRunHasSuggestions = hasBriefEnrichmentSuggestions(selectedEnrichmentRun)
  const effectiveImplementedItem = useMemo(
    () =>
      implementedQuery.data?.items.find((item) => item.brief_id === effectiveBriefId) ??
      implementedQuery.data?.items[0] ??
      null,
    [effectiveBriefId, implementedQuery.data?.items],
  )

  useEffect(() => {
    if (
      (mode !== 'discovery' && mode !== 'opportunities') ||
      !discoveryRunsQuery.isSuccess ||
      selectedRunId === validatedSelectedRunId ||
      (selectedRunId === undefined && validatedSelectedRunId === undefined)
    ) {
      return
    }
    startTransition(() =>
      setSearchParams(
        mergeSearchParams(searchParams, {
          run_id: mode === 'discovery' ? effectiveRunId ?? undefined : validatedSelectedRunId ?? undefined,
        }),
        { replace: true },
      ),
    )
  }, [
    discoveryRunsQuery.isSuccess,
    effectiveRunId,
    mode,
    searchParams,
    selectedRunId,
    setSearchParams,
    validatedSelectedRunId,
  ])

  useEffect(() => {
    if (
      mode !== 'plans' ||
      !plansQuery.isSuccess ||
      selectedPlanId === effectivePlanId ||
      (selectedPlanId === undefined && effectivePlanId === null)
    ) {
      return
    }
    startTransition(() =>
      setSearchParams(mergeSearchParams(searchParams, { plan_id: effectivePlanId ?? undefined }), { replace: true }),
    )
  }, [effectivePlanId, mode, plansQuery.isSuccess, searchParams, selectedPlanId, setSearchParams])

  useEffect(() => {
    if (
      mode !== 'briefs' ||
      !briefsQuery.isSuccess ||
      selectedBriefId === effectiveBriefId ||
      (selectedBriefId === undefined && effectiveBriefId === null)
    ) {
      return
    }
    startTransition(() =>
      setSearchParams(mergeSearchParams(searchParams, { brief_id: effectiveBriefId ?? undefined }), { replace: true }),
    )
  }, [briefsQuery.isSuccess, effectiveBriefId, mode, searchParams, selectedBriefId, setSearchParams])

  useEffect(() => {
    if (
      mode !== 'execution' ||
      !executionQuery.isSuccess ||
      selectedBriefId === effectiveBriefId ||
      (selectedBriefId === undefined && effectiveBriefId === null)
    ) {
      return
    }
    startTransition(() =>
      setSearchParams(mergeSearchParams(searchParams, { brief_id: effectiveBriefId ?? undefined }), {
        replace: true,
      }),
    )
  }, [effectiveBriefId, executionQuery.isSuccess, mode, searchParams, selectedBriefId, setSearchParams])

  useEffect(() => {
    if (
      mode !== 'implemented' ||
      !implementedQuery.isSuccess ||
      selectedBriefId === effectiveBriefId ||
      (selectedBriefId === undefined && effectiveBriefId === null)
    ) {
      return
    }
    startTransition(() =>
      setSearchParams(mergeSearchParams(searchParams, { brief_id: effectiveBriefId ?? undefined }), {
        replace: true,
      }),
    )
  }, [effectiveBriefId, implementedQuery.isSuccess, mode, searchParams, selectedBriefId, setSearchParams])

  useEffect(() => {
    if (
      mode !== 'briefs' ||
      !briefEnrichmentRunsQuery.isSuccess ||
      selectedEnrichmentRunId === effectiveEnrichmentRunId ||
      (selectedEnrichmentRunId === undefined && effectiveEnrichmentRunId === null)
    ) {
      return
    }
    startTransition(() =>
      setSearchParams(
        mergeSearchParams(searchParams, { enrichment_run_id: effectiveEnrichmentRunId ?? undefined }),
        { replace: true },
      ),
    )
  }, [
    briefEnrichmentRunsQuery.isSuccess,
    effectiveEnrichmentRunId,
    mode,
    searchParams,
    selectedEnrichmentRunId,
    setSearchParams,
  ])

  useEffect(() => {
    setSelectedKeywords((current) =>
      current.filter((keyword) => (opportunitiesQuery.data?.items ?? []).some((item) => item.keyword === keyword)),
    )
  }, [opportunitiesQuery.data?.items])

  useEffect(() => {
    setSelectedPromotedIds((current) =>
      current.filter((id) => (promotedQuery.data?.items ?? []).some((item) => item.id === id && !item.has_plan)),
    )
  }, [promotedQuery.data?.items])

  useEffect(() => {
    setSelectedPlanIdsForBriefs((current) =>
      current.filter((id) => (plansQuery.data?.items ?? []).some((item) => item.id === id && !item.has_brief)),
    )
  }, [plansQuery.data?.items])

  useEffect(() => {
    if (!planQuery.data) {
      return
    }
    setPlanDraft({
      state_status: planQuery.data.state_status,
      plan_title: planQuery.data.plan_title ?? '',
      plan_note: planQuery.data.plan_note ?? '',
      target_page_type: planQuery.data.target_page_type,
      proposed_slug: planQuery.data.proposed_slug ?? '',
      proposed_primary_keyword: planQuery.data.proposed_primary_keyword ?? '',
      proposed_secondary_keywords: [...planQuery.data.proposed_secondary_keywords],
    })
    setSecondaryKeywordsText(formatSecondaryKeywords(planQuery.data.proposed_secondary_keywords))
  }, [planQuery.data])

  useEffect(() => {
    if (!briefQuery.data) {
      return
    }
    setBriefDraft({
      state_status: briefQuery.data.state_status,
      brief_title: briefQuery.data.brief_title ?? '',
      brief_type: briefQuery.data.brief_type,
      primary_keyword: briefQuery.data.primary_keyword,
      secondary_keywords: [...briefQuery.data.secondary_keywords],
      search_intent: briefQuery.data.search_intent,
      target_url_existing: briefQuery.data.target_url_existing ?? '',
      proposed_url_slug: briefQuery.data.proposed_url_slug ?? '',
      recommended_page_title: briefQuery.data.recommended_page_title ?? '',
      recommended_h1: briefQuery.data.recommended_h1 ?? '',
      content_goal: briefQuery.data.content_goal ?? '',
      angle_summary: briefQuery.data.angle_summary ?? '',
      sections: [...briefQuery.data.sections],
      internal_link_targets: [...briefQuery.data.internal_link_targets],
      source_notes: [...briefQuery.data.source_notes],
    })
    setBriefSecondaryKeywordsText(formatStringList(briefQuery.data.secondary_keywords))
    setBriefSectionsText(formatStringList(briefQuery.data.sections))
    setBriefInternalLinksText(formatStringList(briefQuery.data.internal_link_targets))
    setBriefSourceNotesText(formatStringList(briefQuery.data.source_notes))
  }, [briefQuery.data])

  useEffect(() => {
    if (!briefQuery.data) {
      return
    }
    setExecutionDraft({
      assignee: briefQuery.data.assignee ?? '',
      execution_note: briefQuery.data.execution_note ?? '',
    })
  }, [briefQuery.data])

  function updateSearch(updates: Record<string, string | number | boolean | undefined>) {
    startTransition(() => setSearchParams(mergeSearchParams(searchParams, updates)))
  }

  function updateForm<K extends keyof SemstormDiscoveryRunCreateInput>(
    key: K,
    value: SemstormDiscoveryRunCreateInput[K],
  ) {
    setFormState((current) => ({ ...current, [key]: value }))
  }

  function updatePlanDraft<K extends keyof SemstormPlanUpdateInput>(
    key: K,
    value: SemstormPlanUpdateInput[K],
  ) {
    setPlanDraft((current) => ({ ...current, [key]: value }))
  }

  function updateBriefDraft<K extends keyof SemstormBriefUpdateInput>(
    key: K,
    value: SemstormBriefUpdateInput[K],
  ) {
    setBriefDraft((current) => ({ ...current, [key]: value }))
  }

  function updateExecutionDraft(key: 'assignee' | 'execution_note', value: string) {
    setExecutionDraft((current) => ({ ...current, [key]: value }))
  }

  async function handleRunDiscovery(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const created = await createRunMutation.mutateAsync(formState)
    updateSearch({ run_id: created.run_id })
  }

  async function handleBulkOpportunityAction(action: 'accept' | 'dismiss' | 'promote') {
    if (!selectedKeywords.length) {
      return
    }
    const payload = {
      run_id: opportunityParams.run_id ?? opportunitiesQuery.data?.run_id,
      keywords: selectedKeywords,
    }
    if (action === 'accept') {
      await acceptMutation.mutateAsync(payload)
    } else if (action === 'dismiss') {
      await dismissMutation.mutateAsync(payload)
    } else {
      await promoteMutation.mutateAsync(payload)
    }
    setSelectedKeywords([])
  }

  async function handleCreatePlansFromPromoted() {
    if (!selectedPromotedIds.length) {
      return
    }
    const payload: SemstormCreatePlanInput = {
      promoted_item_ids: selectedPromotedIds,
      defaults: {
        target_page_type: createPlanTargetPageType,
      },
    }
    const response = await createPlanMutation.mutateAsync(payload)
    setSelectedPromotedIds([])
    if (response.items[0]) {
      updateSearch({ plan_id: response.items[0].id })
    }
  }

  async function handleCreateBriefsFromPlans() {
    if (!selectedPlanIdsForBriefs.length) {
      return
    }
    const payload: SemstormCreateBriefInput = {
      plan_item_ids: selectedPlanIdsForBriefs,
    }
    const response = await createBriefMutation.mutateAsync(payload)
    setSelectedPlanIdsForBriefs([])
    if (response.items[0]) {
      updateSearch({ brief_id: response.items[0].id })
    }
  }

  async function handleSavePlan() {
    if (effectivePlanId === null) {
      return
    }
    await updatePlanMutation.mutateAsync({
      planId: effectivePlanId,
      payload: {
        ...planDraft,
        proposed_secondary_keywords: parseSecondaryKeywords(secondaryKeywordsText),
      },
    })
  }

  async function handleUpdatePlanStatus() {
    if (effectivePlanId === null || !planDraft.state_status) {
      return
    }
    await updatePlanStatusMutation.mutateAsync({
      planId: effectivePlanId,
      payload: {
        state_status: planDraft.state_status,
      },
    })
  }

  async function handleSaveBrief() {
    if (effectiveBriefId === null) {
      return
    }
    await updateBriefMutation.mutateAsync({
      briefId: effectiveBriefId,
      payload: {
        ...briefDraft,
        secondary_keywords: parseSecondaryKeywords(briefSecondaryKeywordsText),
        sections: parseSecondaryKeywords(briefSectionsText),
        internal_link_targets: parseSecondaryKeywords(briefInternalLinksText),
        source_notes: parseSecondaryKeywords(briefSourceNotesText),
      },
    })
  }

  async function handleUpdateBriefStatus() {
    if (effectiveBriefId === null || !briefDraft.state_status) {
      return
    }
    await updateBriefStatusMutation.mutateAsync({
      briefId: effectiveBriefId,
      payload: {
        state_status: briefDraft.state_status,
      },
    })
  }

  async function handleUpdateBriefExecutionStatus(nextStatus: SemstormBriefStateStatus) {
    if (effectiveBriefId === null) {
      return
    }
    await updateBriefExecutionStatusMutation.mutateAsync({
      briefId: effectiveBriefId,
      payload: {
        execution_status: nextStatus,
      },
    })
  }

  async function handleSaveExecutionMetadata() {
    if (effectiveBriefId === null) {
      return
    }
    await updateBriefExecutionMutation.mutateAsync({
      briefId: effectiveBriefId,
      payload: {
        assignee: executionDraft.assignee.trim() || null,
        execution_note: executionDraft.execution_note.trim() || null,
      },
    })
  }

  async function handleUpdateImplementationStatus(payload: SemstormBriefImplementationStatusUpdateInput) {
    if (effectiveBriefId === null) {
      return
    }
    await updateBriefImplementationStatusMutation.mutateAsync({
      briefId: effectiveBriefId,
      payload,
    })
  }

  async function handleEnrichBrief() {
    if (effectiveBriefId === null) {
      return
    }
    const createdRun = await createBriefEnrichmentMutation.mutateAsync(effectiveBriefId)
    updateSearch({ enrichment_run_id: createdRun.id })
  }

  async function handleApplyEnrichment() {
    if (effectiveBriefId === null || selectedEnrichmentRun == null) {
      return
    }
    const result = await applyBriefEnrichmentMutation.mutateAsync({
      briefId: effectiveBriefId,
      runId: selectedEnrichmentRun.id,
    })
    updateSearch({ enrichment_run_id: result.enrichment_run.id })
  }

  function renderExecutionStatusActions(currentStatus: SemstormBriefStateStatus) {
    const actions: Array<{ label: string; nextStatus: SemstormBriefStateStatus }> =
      currentStatus === 'draft'
        ? [
            { label: 'Mark ready', nextStatus: 'ready' },
            { label: 'Archive', nextStatus: 'archived' },
          ]
        : currentStatus === 'ready'
          ? [
              { label: 'Start execution', nextStatus: 'in_execution' },
              { label: 'Archive', nextStatus: 'archived' },
            ]
          : currentStatus === 'in_execution'
            ? [
                { label: 'Move back to ready', nextStatus: 'ready' },
                { label: 'Mark completed', nextStatus: 'completed' },
                { label: 'Archive', nextStatus: 'archived' },
              ]
            : currentStatus === 'completed'
              ? [{ label: 'Archive', nextStatus: 'archived' }]
              : []

    return (
      <div className="flex flex-wrap gap-2">
        {actions.map((action) => (
          <button
            key={`${currentStatus}-${action.nextStatus}-${action.label}`}
            type="button"
            className={action.nextStatus === 'archived' ? actionClass : primaryActionClass}
            disabled={
              effectiveBriefId === null ||
              executionActionPending ||
              !canTransitionBriefExecution(currentStatus, action.nextStatus)
            }
            onClick={() => void handleUpdateBriefExecutionStatus(action.nextStatus)}
          >
            {action.label}
          </button>
        ))}
      </div>
    )
  }

  function canMarkImplemented(
    executionStatus: SemstormBriefStateStatus,
    implementationStatus: SemstormImplementationStatus | null | undefined,
  ) {
    return (
      executionStatus === 'completed' &&
      implementationStatus !== 'implemented' &&
      implementationStatus !== 'too_early' &&
      implementationStatus !== 'evaluated' &&
      implementationStatus !== 'archived'
    )
  }

  function canArchiveImplementation(
    executionStatus: SemstormBriefStateStatus,
    implementationStatus: SemstormImplementationStatus | null | undefined,
  ) {
    if (implementationStatus === 'archived') {
      return false
    }
    if (
      implementationStatus === 'implemented' ||
      implementationStatus === 'too_early' ||
      implementationStatus === 'evaluated'
    ) {
      return true
    }
    return executionStatus === 'completed'
  }

  function renderImplementationActions(
    executionStatus: SemstormBriefStateStatus,
    implementationStatus: SemstormImplementationStatus | null | undefined,
  ) {
    return (
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={primaryActionClass}
          disabled={!canMarkImplemented(executionStatus, implementationStatus) || executionActionPending}
          onClick={() =>
            void handleUpdateImplementationStatus({
              implementation_status: 'implemented',
            })
          }
        >
          Mark implemented
        </button>
        <button
          type="button"
          className={actionClass}
          disabled={!canArchiveImplementation(executionStatus, implementationStatus) || executionActionPending}
          onClick={() =>
            void handleUpdateImplementationStatus({
              implementation_status: 'archived',
            })
          }
        >
          Archive
        </button>
      </div>
    )
  }

  function renderImplementationPanel() {
    if (!briefQuery.data) {
      return null
    }
    const detailItem = effectiveImplementedItem
    return (
      <div className={panelClass}>
        {updateBriefImplementationStatusMutation.isSuccess &&
        updateBriefImplementationStatusMutation.data.id === briefQuery.data.id ? (
          <div className={`mb-4 rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
            <p className="text-sm font-medium">
              Implementation state updated to{' '}
              {implementationLabel(updateBriefImplementationStatusMutation.data.implementation_status)}.
            </p>
          </div>
        ) : null}
        {updateBriefImplementationStatusMutation.isError ? (
          <div className="mb-4">
            <ErrorState
              title="Could not update implementation state"
              message={getUiErrorMessage(updateBriefImplementationStatusMutation.error, t)}
            />
          </div>
        ) : null}

        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Implementation & outcome</p>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
              Execution stays separate from outcome tracking. Mark completed briefs as implemented, then review the
              current active-crawl and GSC signal without turning this into a reporting module.
            </p>
          </div>
          {renderImplementationActions(
            briefQuery.data.execution_status,
            detailItem?.implementation_status ?? briefQuery.data.implementation_status,
          )}
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className={panelClass}>
            <div className="flex flex-wrap gap-2">
              {renderBadge(
                `Implemented: ${implementationLabel(detailItem?.implementation_status ?? briefQuery.data.implementation_status)}`,
                implementationTone(detailItem?.implementation_status ?? briefQuery.data.implementation_status),
              )}
              {detailItem
                ? renderBadge(`Outcome: ${outcomeLabel(detailItem.outcome_status)}`, outcomeTone(detailItem.outcome_status))
                : null}
              {detailItem ? renderBadge(gscLabel(detailItem.gsc_signal_status), gscTone(detailItem.gsc_signal_status)) : null}
            </div>
            <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
              <div className="flex items-center justify-between gap-3">
                <dt>Implemented at</dt>
                <dd>{formatDateTime(briefQuery.data.implemented_at)}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>Last checked</dt>
                <dd>{formatDateTime(detailItem?.last_outcome_checked_at ?? briefQuery.data.last_outcome_checked_at)}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>Override URL</dt>
                <dd className="max-w-[220px] truncate text-right">{briefQuery.data.implementation_url_override ?? '-'}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>Evaluation note</dt>
                <dd className="max-w-[220px] truncate text-right">{briefQuery.data.evaluation_note ?? '-'}</dd>
              </div>
            </dl>
          </div>
          <div className={panelClass}>
            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Observation context</p>
            {detailItem ? (
              <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <dt>Page present</dt>
                  <dd>{detailItem.page_present_in_active_crawl ? 'Yes' : 'No'}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>Matched page</dt>
                  <dd className="max-w-[220px] truncate text-right">{detailItem.matched_page?.url ?? '-'}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>Clicks / impressions</dt>
                  <dd>
                    {detailItem.gsc_summary
                      ? `${formatNumber(detailItem.gsc_summary.clicks)} / ${formatNumber(detailItem.gsc_summary.impressions)}`
                      : '-'}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>CTR / avg. position</dt>
                  <dd>
                    {detailItem.gsc_summary
                      ? `${formatPercent(detailItem.gsc_summary.ctr)} / ${formatNumber(detailItem.gsc_summary.avg_position)}`
                      : '-'}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt>Matching queries</dt>
                  <dd>{formatNumber(detailItem.query_match_count)}</dd>
                </div>
              </dl>
            ) : (
              <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                Mark the brief as implemented to move it into the lightweight observation flow.
              </p>
            )}
          </div>
        </div>

        {detailItem?.notes.length ? (
          <div className="mt-4">
            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Outcome notes</p>
            <ul className="mt-2 space-y-1 text-sm text-stone-700 dark:text-slate-300">
              {detailItem.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    )
  }

  const selectedKeywordSet = new Set(selectedKeywords)
  const selectedPromotedIdSet = new Set(selectedPromotedIds)
  const selectedPlanIdSetForBriefs = new Set(selectedPlanIdsForBriefs)
  const executionActionPending =
    updateBriefExecutionStatusMutation.isPending ||
    updateBriefExecutionMutation.isPending ||
    updateBriefImplementationStatusMutation.isPending
  const noCompletedRun =
    opportunitiesQuery.isError &&
    opportunitiesQuery.error instanceof ApiError &&
    opportunitiesQuery.error.status === 404
  const anyOpportunityActionPending =
    acceptMutation.isPending || dismissMutation.isPending || promoteMutation.isPending
  const visibleOpportunities = opportunitiesQuery.data?.items ?? []
  const allVisibleOpportunitiesSelected =
    visibleOpportunities.length > 0 &&
    visibleOpportunities.every((item) => selectedKeywordSet.has(item.keyword))
  const visiblePromoted = promotedQuery.data?.items ?? []
  const creatablePromotedItems = visiblePromoted.filter(
    (item) => item.promotion_status === 'active' && item.has_plan === false,
  )
  const allVisiblePromotedSelected =
    creatablePromotedItems.length > 0 &&
    creatablePromotedItems.every((item) => selectedPromotedIdSet.has(item.id))
  const visiblePlans = plansQuery.data?.items ?? []
  const creatablePlanBriefItems = visiblePlans.filter((item) => item.has_brief === false)
  const allVisiblePlansSelectedForBriefs =
    creatablePlanBriefItems.length > 0 &&
    creatablePlanBriefItems.every((item) => selectedPlanIdSetForBriefs.has(item.id))
  const discoveryHref = buildSiteCompetitiveGapSemstormDiscoveryPath(site.id, { activeCrawlId, baselineCrawlId })
  const discoveryOpportunitiesHref = appendQueryString(
    buildSiteCompetitiveGapSemstormOpportunitiesPath(site.id, { activeCrawlId, baselineCrawlId }),
    { run_id: navigationRunId ?? undefined },
  )
  const promotedHref = buildSiteCompetitiveGapSemstormPromotedPath(site.id, {
    activeCrawlId,
    baselineCrawlId,
  })
  const plansHref = appendQueryString(
    buildSiteCompetitiveGapSemstormPlansPath(site.id, { activeCrawlId, baselineCrawlId }),
    { plan_id: navigationPlanId ?? undefined },
  )
  const briefsHref = appendQueryString(
    buildSiteCompetitiveGapSemstormBriefsPath(site.id, { activeCrawlId, baselineCrawlId }),
    {
      brief_id: navigationBriefId ?? undefined,
      enrichment_run_id: navigationEnrichmentRunId ?? undefined,
    },
  )
  const executionHref = appendQueryString(
    buildSiteCompetitiveGapSemstormExecutionPath(site.id, { activeCrawlId, baselineCrawlId }),
    { brief_id: navigationBriefId ?? undefined },
  )
  const implementedHref = appendQueryString(
    buildSiteCompetitiveGapSemstormImplementedPath(site.id, { activeCrawlId, baselineCrawlId }),
    { brief_id: navigationBriefId ?? undefined },
  )

  const bucketLabels = {
    quick_win: bucketLabel('quick_win'),
    core_opportunity: bucketLabel('core_opportunity'),
    watchlist: bucketLabel('watchlist'),
  }
  const decisionLabels = {
    create_new_page: decisionLabel('create_new_page'),
    expand_existing_page: decisionLabel('expand_existing_page'),
    monitor_only: decisionLabel('monitor_only'),
  }
  const coverageLabels = {
    missing: coverageLabel('missing'),
    weak_coverage: coverageLabel('weak_coverage'),
    covered: coverageLabel('covered'),
  }
  const stateLabels = {
    new: stateLabel('new'),
    accepted: stateLabel('accepted'),
    dismissed: stateLabel('dismissed'),
    promoted: stateLabel('promoted'),
  }
  const planStateLabels = {
    planned: planStateLabel('planned'),
    in_progress: planStateLabel('in_progress'),
    done: planStateLabel('done'),
    archived: planStateLabel('archived'),
  }
  const planTargetLabels = {
    new_page: planTargetPageTypeLabel('new_page'),
    expand_existing: planTargetPageTypeLabel('expand_existing'),
    refresh_existing: planTargetPageTypeLabel('refresh_existing'),
    cluster_support: planTargetPageTypeLabel('cluster_support'),
  }
  const briefStateLabels = {
    draft: briefStateLabel('draft'),
    ready: briefStateLabel('ready'),
    in_execution: briefStateLabel('in_execution'),
    completed: briefStateLabel('completed'),
    archived: briefStateLabel('archived'),
  }
  const briefTypeLabels = {
    new_page: briefTypeLabel('new_page'),
    expand_existing: briefTypeLabel('expand_existing'),
    refresh_existing: briefTypeLabel('refresh_existing'),
    cluster_support: briefTypeLabel('cluster_support'),
  }
  const briefIntentLabels = {
    informational: briefIntentLabel('informational'),
    commercial: briefIntentLabel('commercial'),
    transactional: briefIntentLabel('transactional'),
    navigational: briefIntentLabel('navigational'),
    mixed: briefIntentLabel('mixed'),
  }
  const implementationLabels = {
    too_early: implementationLabel('too_early'),
    implemented: implementationLabel('implemented'),
    evaluated: implementationLabel('evaluated'),
    archived: implementationLabel('archived'),
  }
  const outcomeLabels = {
    too_early: outcomeLabel('too_early'),
    no_signal: outcomeLabel('no_signal'),
    weak_signal: outcomeLabel('weak_signal'),
    positive_signal: outcomeLabel('positive_signal'),
  }

  let body: ReactNode = null

  if (mode === 'discovery') {
    body = (
      <>
        <SummaryCards
          items={[
            {
              label: 'Last run status',
              value: latestRun ? latestRun.status : '-',
              hint: latestRun ? `Run #${latestRun.run_id}` : 'No Semstorm runs yet',
            },
            {
              label: 'Source domain',
              value: latestRun?.source_domain ?? '-',
              hint: latestRun ? formatDateTime(latestRun.created_at) : 'No Semstorm runs yet',
            },
            {
              label: 'Competitors',
              value: latestRun ? formatNumber(latestRun.summary.total_competitors) : '-',
            },
            {
              label: 'Total queries',
              value: latestRun ? formatNumber(latestRun.summary.total_queries) : '-',
            },
            {
              label: 'Unique keywords',
              value: latestRun ? formatNumber(latestRun.summary.unique_keywords) : '-',
            },
          ]}
        />

        <section className={sectionClass}>
          <div>
            <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">Run discovery</h2>
            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
              Start a persisted Semstorm discovery run for this site workspace.
            </p>
          </div>
          <form
            id="semstorm-discovery-form"
            className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4"
            onSubmit={handleRunDiscovery}
          >
            <label className={fieldLabelClass}>
              <span>Max competitors</span>
              <input
                className={fieldControlClass}
                type="number"
                min={1}
                max={50}
                value={formState.max_competitors}
                onChange={(event) =>
                  updateForm('max_competitors', Math.max(1, Number(event.target.value) || 1))
                }
              />
            </label>
            <label className={fieldLabelClass}>
              <span>Max keywords per competitor</span>
              <input
                className={fieldControlClass}
                type="number"
                min={1}
                max={50}
                value={formState.max_keywords_per_competitor}
                onChange={(event) =>
                  updateForm('max_keywords_per_competitor', Math.max(1, Number(event.target.value) || 1))
                }
              />
            </label>
            <label className={fieldLabelClass}>
              <span>Result type</span>
              <select
                className={fieldControlClass}
                value={formState.result_type}
                onChange={(event) => updateForm('result_type', readResultType(event.target.value))}
              >
                <option value="organic">Organic</option>
                <option value="paid">Paid</option>
              </select>
            </label>
            <label
              className={`${fieldLabelClass} flex items-center gap-3 rounded-3xl border border-stone-200 bg-stone-50/90 px-4 py-3 dark:border-slate-800 dark:bg-slate-900/85`}
            >
              <input
                className="h-4 w-4 rounded border-stone-300 text-teal-700 focus:ring-teal-500 dark:border-slate-600 dark:bg-slate-950"
                type="checkbox"
                checked={formState.include_basic_stats}
                onChange={(event) => updateForm('include_basic_stats', event.target.checked)}
              />
              <span>Include basic stats</span>
            </label>
          </form>
          {createRunMutation.isError ? (
            <div className="mt-4">
              <ErrorState
                title="Could not start Semstorm discovery"
                message={getUiErrorMessage(createRunMutation.error, t)}
              />
            </div>
          ) : null}
        </section>

        {discoveryRunsQuery.isLoading ? (
          <LoadingState label="Loading Semstorm discovery runs" />
        ) : discoveryRunsQuery.isError ? (
          <RetriableErrorState
            title="Could not load Semstorm discovery runs"
            message={getUiErrorMessage(discoveryRunsQuery.error, t)}
            onRetry={() => void discoveryRunsQuery.refetch()}
          />
        ) : discoveryRunsQuery.data?.length ? (
          <div className="grid gap-6 xl:grid-cols-[minmax(280px,0.9fr),minmax(0,1.1fr)]">
            <section className={sectionClass}>
              <div>
                <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                  Recent discovery runs
                </h2>
                <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                  Pick a run to inspect the stored Semstorm payload.
                </p>
              </div>
              <div className="mt-4 space-y-3">
                {discoveryRunsQuery.data.map((run) => (
                  <button
                    key={run.run_id}
                    type="button"
                    onClick={() => updateSearch({ run_id: run.run_id })}
                    className={`w-full rounded-3xl border p-4 text-left transition ${
                      effectiveRunId === run.run_id
                        ? 'border-teal-400 bg-teal-50/80 dark:border-teal-500 dark:bg-teal-950/30'
                        : 'border-stone-200 bg-stone-50/90 hover:border-stone-300 hover:bg-stone-100 dark:border-slate-800 dark:bg-slate-900/85'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-stone-950 dark:text-slate-50">
                          Run #{run.run_id}
                        </p>
                        <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{run.source_domain}</p>
                      </div>
                      {renderBadge(run.status, runStatusTone(run.status))}
                    </div>
                    <p className="mt-3 text-xs text-stone-500 dark:text-slate-400">
                      {formatDateTime(run.created_at)}
                    </p>
                  </button>
                ))}
              </div>
            </section>

            {discoveryRunQuery.isLoading ? (
              <LoadingState label="Loading discovery run detail" />
            ) : discoveryRunQuery.isError ? (
              <RetriableErrorState
                title="Could not load discovery run detail"
                message={getUiErrorMessage(discoveryRunQuery.error, t)}
                onRetry={() => void discoveryRunQuery.refetch()}
              />
            ) : discoveryRunQuery.data ? (
              <section className={sectionClass}>
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                      Run #{discoveryRunQuery.data.run_id}
                    </h2>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      {discoveryRunQuery.data.source_domain}
                    </p>
                  </div>
                  {renderBadge(discoveryRunQuery.data.status, runStatusTone(discoveryRunQuery.data.status))}
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div className={panelClass}>
                    <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Params</p>
                    <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                      <div className="flex items-center justify-between gap-3">
                        <dt>Max competitors</dt>
                        <dd>{discoveryRunQuery.data.params.max_competitors}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt>Max keywords / competitor</dt>
                        <dd>{discoveryRunQuery.data.params.max_keywords_per_competitor}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt>Result type</dt>
                        <dd>{discoveryRunQuery.data.params.result_type}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt>Basic stats</dt>
                        <dd>{discoveryRunQuery.data.params.include_basic_stats ? 'Yes' : 'No'}</dd>
                      </div>
                    </dl>
                  </div>
                  <div className={panelClass}>
                    <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Summary</p>
                    <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                      <div className="flex items-center justify-between gap-3">
                        <dt>Competitors</dt>
                        <dd>{formatNumber(discoveryRunQuery.data.summary.total_competitors)}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt>Total queries</dt>
                        <dd>{formatNumber(discoveryRunQuery.data.summary.total_queries)}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt>Unique keywords</dt>
                        <dd>{formatNumber(discoveryRunQuery.data.summary.unique_keywords)}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt>Created at</dt>
                        <dd>{formatDateTime(discoveryRunQuery.data.created_at)}</dd>
                      </div>
                    </dl>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {discoveryRunQuery.data.competitors.map((competitor) => (
                    <article key={competitor.domain} className={panelClass}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                            {competitor.domain}
                          </p>
                          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                            Common keywords: {formatNumber(competitor.common_keywords)} | Traffic:{' '}
                            {formatNumber(competitor.traffic)}
                          </p>
                        </div>
                        {renderBadge(`Queries: ${formatNumber(competitor.queries_count)}`, 'stone')}
                      </div>
                      {competitor.top_queries.length ? (
                        <div className="mt-3 space-y-2">
                          {competitor.top_queries.slice(0, 3).map((query) => (
                            <div
                              key={`${competitor.domain}:${query.keyword}`}
                              className="rounded-2xl border border-stone-200 bg-white/80 p-3 text-sm dark:border-slate-700 dark:bg-slate-950/60"
                            >
                              <p className="font-medium text-stone-950 dark:text-slate-50">{query.keyword}</p>
                              <p className="mt-1 text-stone-600 dark:text-slate-300">
                                Position: {formatNumber(query.position)} | Volume: {formatNumber(query.volume)} | Traffic:{' '}
                                {formatNumber(query.traffic)}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              </section>
            ) : null}
          </div>
        ) : (
          <EmptyState
            title="No Semstorm discovery runs yet"
            description="Run discovery to persist competitors and keyword previews for this site."
          />
        )}
      </>
    )
  }

  if (mode === 'opportunities') {
    body = (
      <>
        <QuickFilterBar
          title="Bucket"
          items={opportunityBuckets.map((bucket) => ({
            label: bucketLabel(bucket),
            isActive: opportunityParams.bucket === bucket,
            onClick: () =>
              updateSearch({ bucket: opportunityParams.bucket === bucket ? undefined : bucket }),
          }))}
          onReset={() => updateSearch({ bucket: undefined })}
        />
        <QuickFilterBar
          title="Coverage"
          items={coverageStatuses.map((status) => ({
            label: coverageLabel(status),
            isActive: opportunityParams.coverage_status === status,
            onClick: () =>
              updateSearch({
                coverage_status: opportunityParams.coverage_status === status ? undefined : status,
              }),
          }))}
          onReset={() => updateSearch({ coverage_status: undefined })}
        />
        <QuickFilterBar
          title="Decision"
          items={decisionTypes.map((decisionType) => ({
            label: decisionLabel(decisionType),
            isActive: opportunityParams.decision_type === decisionType,
            onClick: () =>
              updateSearch({
                decision_type: opportunityParams.decision_type === decisionType ? undefined : decisionType,
              }),
          }))}
          onReset={() => updateSearch({ decision_type: undefined })}
        />
        <QuickFilterBar
          title="State"
          items={stateStatuses.map((status) => ({
            label: stateLabel(status),
            isActive: opportunityParams.state_status === status,
            onClick: () =>
              updateSearch({ state_status: opportunityParams.state_status === status ? undefined : status }),
          }))}
          onReset={() => updateSearch({ state_status: undefined })}
        />
        <QuickFilterBar
          title="GSC"
          items={[
            {
              label: 'Has GSC signal',
              isActive: opportunityParams.has_gsc_signal === true,
              onClick: () =>
                updateSearch({
                  has_gsc_signal: opportunityParams.has_gsc_signal === true ? undefined : true,
                }),
            },
            {
              label: 'No GSC signal',
              isActive: opportunityParams.has_gsc_signal === false,
              onClick: () =>
                updateSearch({
                  has_gsc_signal: opportunityParams.has_gsc_signal === false ? undefined : false,
                }),
            },
            {
              label: 'Only actionable',
              isActive: opportunityParams.only_actionable === true,
              onClick: () =>
                updateSearch({
                  only_actionable: opportunityParams.only_actionable === true ? undefined : true,
                }),
            },
          ]}
          onReset={() => updateSearch({ has_gsc_signal: undefined, only_actionable: undefined })}
        />
        <FilterPanel
          title="Opportunity filters"
          description="Pick a discovery run and limit the current Semstorm list."
          bodyClassName="grid gap-3 md:grid-cols-2"
          onReset={() =>
            updateSearch({
              run_id: undefined,
              limit: undefined,
              bucket: undefined,
              coverage_status: undefined,
              decision_type: undefined,
              state_status: undefined,
              has_gsc_signal: undefined,
              only_actionable: undefined,
            })
          }
        >
          <label className={fieldLabelClass}>
            <span>Run</span>
            <select
              className={fieldControlClass}
              value={String(opportunityParams.run_id ?? '')}
              onChange={(event) =>
                updateSearch({ run_id: parseIntegerParam(event.target.value, undefined) })
              }
            >
              <option value="">Any</option>
              {(discoveryRunsQuery.data ?? []).map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  #{run.run_id} - {formatDateTime(run.created_at)}
                </option>
              ))}
            </select>
          </label>
          <label className={fieldLabelClass}>
            <span>Limit</span>
            <input
              className={fieldControlClass}
              type="number"
              min={1}
              max={500}
              value={opportunityParams.limit ?? 100}
              onChange={(event) =>
                updateSearch({ limit: Math.max(1, Number(event.target.value) || 1) })
              }
            />
          </label>
        </FilterPanel>

        {opportunitiesQuery.isLoading ? (
          <LoadingState label="Loading Semstorm opportunities" />
        ) : noCompletedRun ? (
          <EmptyState
            title="No completed discovery run"
            description="Run Semstorm discovery first, then use this screen to review opportunities."
          />
        ) : opportunitiesQuery.isError ? (
          <RetriableErrorState
            title="Could not load Semstorm opportunities"
            message={getUiErrorMessage(opportunitiesQuery.error, t)}
            onRetry={() => void opportunitiesQuery.refetch()}
          />
        ) : opportunitiesQuery.data ? (
          <>
            <SummaryCards
              items={[
                {
                  label: 'Total items',
                  value: formatNumber(opportunitiesQuery.data.summary.total_items),
                  hint: `Run #${opportunitiesQuery.data.run_id}`,
                },
                {
                  label: 'Bucket counts',
                  value: formatNumber(opportunitiesQuery.data.summary.total_items),
                  hint: countLabel(
                    opportunitiesQuery.data.summary.bucket_counts,
                    opportunityBuckets,
                    bucketLabels,
                  ),
                },
                {
                  label: 'Decision counts',
                  value: formatNumber(opportunitiesQuery.data.summary.total_competitors),
                  hint: countLabel(
                    opportunitiesQuery.data.summary.decision_type_counts,
                    decisionTypes,
                    decisionLabels,
                  ),
                },
                {
                  label: 'Coverage counts',
                  value: formatNumber(opportunitiesQuery.data.summary.unique_keywords),
                  hint: countLabel(
                    opportunitiesQuery.data.summary.coverage_status_counts,
                    coverageStatuses,
                    coverageLabels,
                  ),
                },
                {
                  label: 'State counts',
                  value: formatNumber(opportunitiesQuery.data.summary.total_items),
                  hint: countLabel(
                    opportunitiesQuery.data.summary.state_counts,
                    stateStatuses,
                    stateLabels,
                  ),
                },
              ]}
            />
            {opportunitiesQuery.data.active_crawl_id === null ? (
              <div className={`rounded-3xl border px-5 py-4 ${toneClass('amber')}`}>
                <p className="text-sm font-semibold">No active crawl coverage context</p>
                <p className="mt-1 text-sm">
                  The opportunity list still works, but own-site coverage signals are limited until the
                  site has an active crawl snapshot.
                </p>
              </div>
            ) : null}
            {!opportunitiesQuery.data.items.length ? (
              <EmptyState
                title="No Semstorm opportunities for current filters"
                description="Try another run or reset the filters."
              />
            ) : (
              <>
                <section className={sectionClass}>
                  <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                    <div>
                      <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                        Bulk actions
                      </h2>
                      <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                        {selectedKeywords.length} selected from the current list.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className={actionClass}
                        disabled={!selectedKeywords.length || anyOpportunityActionPending}
                        onClick={() => void handleBulkOpportunityAction('accept')}
                      >
                        Accept
                      </button>
                      <button
                        type="button"
                        className={actionClass}
                        disabled={!selectedKeywords.length || anyOpportunityActionPending}
                        onClick={() => void handleBulkOpportunityAction('dismiss')}
                      >
                        Dismiss
                      </button>
                      <button
                        type="button"
                        className={primaryActionClass}
                        disabled={!selectedKeywords.length || anyOpportunityActionPending}
                        onClick={() => void handleBulkOpportunityAction('promote')}
                      >
                        Promote
                      </button>
                    </div>
                  </div>
                </section>

                <section className={sectionClass}>
                  <div>
                    <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                      Opportunity list
                    </h2>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      Run #{opportunitiesQuery.data.run_id} for {opportunitiesQuery.data.source_domain}
                    </p>
                  </div>
                  <div className="mt-4 overflow-x-auto">
                    <table className="min-w-full border-separate border-spacing-y-2">
                      <thead>
                        <tr className="text-left text-xs uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
                          <th className="px-3 py-2">
                            <input
                              aria-label="Select all current opportunities"
                              type="checkbox"
                              checked={allVisibleOpportunitiesSelected}
                              onChange={(event) =>
                                setSelectedKeywords(
                                  event.target.checked
                                    ? visibleOpportunities.map((item) => item.keyword)
                                    : [],
                                )
                              }
                              className="h-4 w-4 rounded border-stone-300 text-teal-700 focus:ring-teal-500 dark:border-slate-600 dark:bg-slate-950"
                            />
                          </th>
                          <th className="px-3 py-2">Keyword</th>
                          <th className="px-3 py-2">State</th>
                          <th className="px-3 py-2">Competitors</th>
                          <th className="px-3 py-2">Best position</th>
                          <th className="px-3 py-2">Max volume</th>
                          <th className="px-3 py-2">Max traffic</th>
                          <th className="px-3 py-2">Avg CPC</th>
                          <th className="px-3 py-2">Bucket</th>
                          <th className="px-3 py-2">Decision</th>
                          <th className="px-3 py-2">Coverage</th>
                          <th className="px-3 py-2">GSC</th>
                          <th className="px-3 py-2">Score</th>
                          <th className="px-3 py-2">Details</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleOpportunities.map((item) => (
                          <tr key={item.keyword} className="rounded-3xl bg-stone-50/90 align-top dark:bg-slate-900/85">
                            <td className="px-3 py-3 text-sm">
                              <input
                                aria-label={`Select ${item.keyword}`}
                                type="checkbox"
                                checked={selectedKeywordSet.has(item.keyword)}
                                onChange={(event) =>
                                  setSelectedKeywords((current) =>
                                    event.target.checked
                                      ? Array.from(new Set([...current, item.keyword]))
                                      : current.filter((keyword) => keyword !== item.keyword),
                                  )
                                }
                                className="h-4 w-4 rounded border-stone-300 text-teal-700 focus:ring-teal-500 dark:border-slate-600 dark:bg-slate-950"
                              />
                            </td>
                            <td className="px-3 py-3 text-sm font-medium text-stone-950 dark:text-slate-50">
                              <div>{item.keyword}</div>
                              {item.state_note ? (
                                <div className="mt-1 text-xs font-normal text-stone-500 dark:text-slate-400">
                                  {item.state_note}
                                </div>
                              ) : null}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(stateLabel(item.state_status), stateTone(item.state_status))}
                            </td>
                            <td className="px-3 py-3 text-sm">{formatNumber(item.competitor_count)}</td>
                            <td className="px-3 py-3 text-sm">{formatNumber(item.best_position)}</td>
                            <td className="px-3 py-3 text-sm">{formatNumber(item.max_volume)}</td>
                            <td className="px-3 py-3 text-sm">{formatNumber(item.max_traffic)}</td>
                            <td className="px-3 py-3 text-sm">{formatCpc(item.avg_cpc)}</td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(
                                bucketLabel(item.bucket),
                                item.bucket === 'core_opportunity'
                                  ? 'rose'
                                  : item.bucket === 'quick_win'
                                    ? 'teal'
                                    : 'stone',
                              )}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(decisionLabel(item.decision_type), decisionTone(item.decision_type))}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(coverageLabel(item.coverage_status), coverageTone(item.coverage_status))}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(gscLabel(item.gsc_signal_status), gscTone(item.gsc_signal_status))}
                            </td>
                            <td className="px-3 py-3 text-sm font-medium text-stone-950 dark:text-slate-50">
                              {formatNumber(item.opportunity_score_v2)}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              <details>
                                <summary className="cursor-pointer list-none text-teal-700 dark:text-teal-300">
                                  Details
                                </summary>
                                <div className="mt-3 min-w-[280px] space-y-3">
                                  <div className={panelClass}>
                                    <p className="text-sm text-stone-700 dark:text-slate-200">
                                      Coverage score v1: {item.coverage_score_v1}
                                    </p>
                                    <p className="mt-1 text-sm text-stone-700 dark:text-slate-200">
                                      Matched pages: {item.matched_pages_count}
                                    </p>
                                    <p className="mt-2 text-sm text-stone-700 dark:text-slate-200">
                                      Best match page:{' '}
                                      {item.best_match_page ? item.best_match_page.title || item.best_match_page.url : 'None'}
                                    </p>
                                    {item.best_match_page?.match_signals.length ? (
                                      <div className="mt-2 flex flex-wrap gap-2">
                                        {item.best_match_page.match_signals.map((signal) =>
                                          renderBadge(signal, 'teal'),
                                        )}
                                      </div>
                                    ) : null}
                                  </div>
                                  <div className={panelClass}>
                                    <p className="text-sm text-stone-700 dark:text-slate-200">
                                      GSC summary: clicks {formatNumber(item.gsc_summary?.clicks)}, impressions{' '}
                                      {formatNumber(item.gsc_summary?.impressions)}, CTR{' '}
                                      {formatPercent(item.gsc_summary?.ctr, 1)}, avg position{' '}
                                      {item.gsc_summary?.avg_position ?? '-'}
                                    </p>
                                    <p className="mt-2 text-sm text-stone-700 dark:text-slate-200">
                                      Sample competitors:{' '}
                                      {item.sample_competitors.length ? item.sample_competitors.join(', ') : '-'}
                                    </p>
                                  </div>
                                </div>
                              </details>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}
          </>
        ) : null}
      </>
    )
  }

  if (mode === 'promoted') {
    body = promotedQuery.isLoading ? (
      <LoadingState label="Loading promoted Semstorm backlog" />
    ) : promotedQuery.isError ? (
      <RetriableErrorState
        title="Could not load promoted Semstorm backlog"
        message={getUiErrorMessage(promotedQuery.error, t)}
        onRetry={() => void promotedQuery.refetch()}
      />
    ) : promotedQuery.data ? (
      <>
        <SummaryCards
          items={[
            {
              label: 'Total items',
              value: formatNumber(promotedQuery.data.summary.total_items),
            },
            {
              label: 'Active items',
              value: formatNumber(promotedQuery.data.summary.promotion_status_counts.active ?? 0),
            },
            {
              label: 'Archived items',
              value: formatNumber(promotedQuery.data.summary.promotion_status_counts.archived ?? 0),
            },
            {
              label: 'Items with plan',
              value: formatNumber(promotedQuery.data.items.filter((item) => item.has_plan).length),
            },
          ]}
        />
        {!promotedQuery.data.items.length ? (
          <EmptyState
            title="No promoted Semstorm items yet"
            description="Promote useful opportunities first, then turn them into planning items."
          />
        ) : (
          <>
            <section className={sectionClass}>
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div>
                  <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                    Create plans from promoted items
                  </h2>
                  <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                    {selectedPromotedIds.length} selected from the promoted backlog.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <label className={fieldLabelClass}>
                    <span>Default target type</span>
                    <select
                      className={fieldControlClass}
                      value={createPlanTargetPageType}
                      onChange={(event) =>
                        setCreatePlanTargetPageType(
                          readPlanTargetPageType(event.target.value) ?? 'new_page',
                        )
                      }
                    >
                      {planTargetPageTypes.map((item) => (
                        <option key={item} value={item}>
                          {planTargetPageTypeLabel(item)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className={primaryActionClass}
                    disabled={!selectedPromotedIds.length || createPlanMutation.isPending}
                    onClick={() => void handleCreatePlansFromPromoted()}
                  >
                    Create plan
                  </button>
                </div>
              </div>
              {createPlanMutation.isSuccess ? (
                <div className={`mt-4 rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                  <p className="text-sm font-medium">
                    Created {createPlanMutation.data.created_count} plan items. Skipped{' '}
                    {createPlanMutation.data.skipped_count}.
                  </p>
                </div>
              ) : null}
            </section>

            <section className={sectionClass}>
              <div>
                <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                  Promoted backlog
                </h2>
                <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                  Promote first, plan second. This backlog is still separate from content recommendations and
                  final competitive gap results.
                </p>
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full border-separate border-spacing-y-2">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
                      <th className="px-3 py-2">
                        <input
                          aria-label="Select all current promoted items"
                          type="checkbox"
                          checked={allVisiblePromotedSelected}
                          onChange={(event) =>
                            setSelectedPromotedIds(
                              event.target.checked ? creatablePromotedItems.map((item) => item.id) : [],
                            )
                          }
                          className="h-4 w-4 rounded border-stone-300 text-teal-700 focus:ring-teal-500 dark:border-slate-600 dark:bg-slate-950"
                        />
                      </th>
                      <th className="px-3 py-2">Keyword</th>
                      <th className="px-3 py-2">Planning</th>
                      <th className="px-3 py-2">Bucket</th>
                      <th className="px-3 py-2">Decision</th>
                      <th className="px-3 py-2">Coverage</th>
                      <th className="px-3 py-2">GSC</th>
                      <th className="px-3 py-2">Score</th>
                      <th className="px-3 py-2">Source run</th>
                      <th className="px-3 py-2">Created at</th>
                    </tr>
                  </thead>
                  <tbody>
                    {promotedQuery.data.items.map((item) => (
                      <tr key={item.opportunity_key} className="rounded-3xl bg-stone-50/90 align-top dark:bg-slate-900/85">
                        <td className="px-3 py-3 text-sm">
                          <input
                            aria-label={`Select promoted ${item.keyword}`}
                            type="checkbox"
                            disabled={item.has_plan}
                            checked={selectedPromotedIdSet.has(item.id)}
                            onChange={(event) =>
                              setSelectedPromotedIds((current) =>
                                event.target.checked
                                  ? Array.from(new Set([...current, item.id]))
                                  : current.filter((candidateId) => candidateId !== item.id),
                              )
                            }
                            className="h-4 w-4 rounded border-stone-300 text-teal-700 focus:ring-teal-500 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-950"
                          />
                        </td>
                        <td className="px-3 py-3 text-sm font-medium text-stone-950 dark:text-slate-50">
                          {item.keyword}
                        </td>
                        <td className="px-3 py-3 text-sm">
                          {item.has_plan && item.plan_id ? (
                            <Link
                              to={appendQueryString(plansHref, { plan_id: item.plan_id })}
                              className="inline-flex items-center gap-2"
                            >
                              {renderBadge(
                                item.plan_state_status ? planStateLabel(item.plan_state_status) : 'In plans',
                                item.plan_state_status ? planStateTone(item.plan_state_status) : 'teal',
                              )}
                            </Link>
                          ) : (
                            renderBadge('Ready to plan', 'amber')
                          )}
                        </td>
                        <td className="px-3 py-3 text-sm">
                          {renderBadge(
                            bucketLabel(item.bucket),
                            item.bucket === 'core_opportunity'
                              ? 'rose'
                              : item.bucket === 'quick_win'
                                ? 'teal'
                                : 'stone',
                          )}
                        </td>
                        <td className="px-3 py-3 text-sm">
                          {renderBadge(decisionLabel(item.decision_type), decisionTone(item.decision_type))}
                        </td>
                        <td className="px-3 py-3 text-sm">
                          {renderBadge(coverageLabel(item.coverage_status), coverageTone(item.coverage_status))}
                        </td>
                        <td className="px-3 py-3 text-sm">
                          {renderBadge(gscLabel(item.gsc_signal_status), gscTone(item.gsc_signal_status))}
                        </td>
                        <td className="px-3 py-3 text-sm font-medium text-stone-950 dark:text-slate-50">
                          {formatNumber(item.opportunity_score_v2)}
                        </td>
                        <td className="px-3 py-3 text-sm">#{item.source_run_id}</td>
                        <td className="px-3 py-3 text-sm">{formatDateTime(item.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </>
    ) : null
  }

  if (mode === 'plans') {
    body = (
      <>
        <QuickFilterBar
          title="Plan state"
          items={planStateStatuses.map((status) => ({
            label: planStateLabel(status),
            isActive: plansParams.state_status === status,
            onClick: () =>
              updateSearch({
                state_status: plansParams.state_status === status ? undefined : status,
                plan_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ state_status: undefined, plan_id: undefined })}
        />
        <QuickFilterBar
          title="Target page type"
          items={planTargetPageTypes.map((targetPageType) => ({
            label: planTargetPageTypeLabel(targetPageType),
            isActive: plansParams.target_page_type === targetPageType,
            onClick: () =>
              updateSearch({
                target_page_type:
                  plansParams.target_page_type === targetPageType ? undefined : targetPageType,
                plan_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ target_page_type: undefined, plan_id: undefined })}
        />
        <FilterPanel
          title="Plan filters"
          description="Filter the current planning backlog for Semstorm-promoted keywords."
          bodyClassName="grid gap-3 md:grid-cols-2"
          onReset={() =>
            updateSearch({
              state_status: undefined,
              target_page_type: undefined,
              search: undefined,
              limit: undefined,
              plan_id: undefined,
            })
          }
        >
          <label className={fieldLabelClass}>
            <span>Search</span>
            <input
              className={fieldControlClass}
              type="text"
              value={plansParams.search ?? ''}
              onChange={(event) =>
                updateSearch({ search: event.target.value || undefined, plan_id: undefined })
              }
              placeholder="Keyword, title, slug"
            />
          </label>
          <label className={fieldLabelClass}>
            <span>Limit</span>
            <input
              className={fieldControlClass}
              type="number"
              min={1}
              max={500}
              value={plansParams.limit ?? 100}
              onChange={(event) =>
                updateSearch({ limit: Math.max(1, Number(event.target.value) || 1) })
              }
            />
          </label>
        </FilterPanel>

        {plansQuery.isLoading ? (
          <LoadingState label="Loading Semstorm plans" />
        ) : plansQuery.isError ? (
          <RetriableErrorState
            title="Could not load Semstorm plans"
            message={getUiErrorMessage(plansQuery.error, t)}
            onRetry={() => void plansQuery.refetch()}
          />
        ) : plansQuery.data ? (
          <>
            <SummaryCards
              items={[
                {
                  label: 'Total plans',
                  value: formatNumber(plansQuery.data.summary.total_count),
                },
                {
                  label: 'State counts',
                  value: formatNumber(plansQuery.data.summary.total_count),
                  hint: countLabel(plansQuery.data.summary.state_counts, planStateStatuses, planStateLabels),
                },
                {
                  label: 'Target page types',
                  value: formatNumber(plansQuery.data.summary.total_count),
                  hint: countLabel(
                    plansQuery.data.summary.target_page_type_counts,
                    planTargetPageTypes,
                    planTargetLabels,
                  ),
                },
                {
                  label: 'Selected plan',
                  value: effectivePlanId ? `#${effectivePlanId}` : '-',
                },
              ]}
            />

            {createBriefMutation.isSuccess ? (
              <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                <p className="text-sm font-medium">
                  Created {formatNumber(createBriefMutation.data?.created_count ?? 0)} briefs and skipped{' '}
                  {formatNumber(createBriefMutation.data?.skipped_count ?? 0)} items.
                </p>
              </div>
            ) : null}

            {!plansQuery.data.items.length ? (
              <EmptyState
                title="No Semstorm plans yet"
                description="Create plans from the promoted backlog to turn Semstorm ideas into a lightweight planning workflow."
              />
            ) : (
              <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.95fr),minmax(0,1.05fr)]">
                <section className={sectionClass}>
                  <div>
                    <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                      Planning list
                    </h2>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      Choose a plan item to edit its working details or batch-create execution briefs.
                    </p>
                  </div>
                  <div className="mt-4 rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/85">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <p className="text-sm font-medium text-stone-900 dark:text-slate-50">
                          {selectedPlanIdsForBriefs.length} selected for brief creation.
                        </p>
                        <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                          Only plan items without an existing brief can be selected.
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className={actionClass}
                          onClick={() =>
                            setSelectedPlanIdsForBriefs(
                              allVisiblePlansSelectedForBriefs ? [] : creatablePlanBriefItems.map((item) => item.id),
                            )
                          }
                        >
                          {allVisiblePlansSelectedForBriefs ? 'Clear selection' : 'Select all visible'}
                        </button>
                        <button
                          type="button"
                          className={primaryActionClass}
                          disabled={!selectedPlanIdsForBriefs.length || createBriefMutation.isPending}
                          onClick={() => void handleCreateBriefsFromPlans()}
                        >
                          {createBriefMutation.isPending ? 'Creating...' : 'Create brief'}
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 overflow-x-auto">
                    <table className="min-w-full border-separate border-spacing-y-2">
                      <thead>
                        <tr className="text-left text-xs uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
                          <th className="px-3 py-2">Select</th>
                          <th className="px-3 py-2">Keyword</th>
                          <th className="px-3 py-2">Title</th>
                          <th className="px-3 py-2">State</th>
                          <th className="px-3 py-2">Target type</th>
                          <th className="px-3 py-2">Brief</th>
                          <th className="px-3 py-2">Decision</th>
                          <th className="px-3 py-2">Coverage</th>
                          <th className="px-3 py-2">Score</th>
                          <th className="px-3 py-2">Edit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {plansQuery.data.items.map((item) => (
                          <tr
                            key={item.id}
                            className={`rounded-3xl align-top ${
                              effectivePlanId === item.id
                                ? 'bg-teal-50/80 dark:bg-teal-950/30'
                                : 'bg-stone-50/90 dark:bg-slate-900/85'
                            }`}
                          >
                            <td className="px-3 py-3 text-sm">
                              <input
                                aria-label={`Select plan ${item.keyword}`}
                                type="checkbox"
                                checked={selectedPlanIdSetForBriefs.has(item.id)}
                                disabled={item.has_brief}
                                onChange={(event) =>
                                  setSelectedPlanIdsForBriefs((current) => {
                                    if (event.target.checked) {
                                      return [...current, item.id]
                                    }
                                    return current.filter((value) => value !== item.id)
                                  })
                                }
                              />
                            </td>
                            <td className="px-3 py-3 text-sm font-medium text-stone-950 dark:text-slate-50">
                              {item.keyword}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {truncateText(item.plan_title ?? '-', 56)}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(planStateLabel(item.state_status), planStateTone(item.state_status))}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(
                                planTargetPageTypeLabel(item.target_page_type),
                                planTargetTone(item.target_page_type),
                              )}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {item.has_brief
                                ? renderBadge(
                                    item.brief_state_status
                                      ? `Brief: ${briefStateLabel(item.brief_state_status)}`
                                      : 'Brief ready',
                                    item.brief_state_status ? briefStateTone(item.brief_state_status) : 'teal',
                                  )
                                : renderBadge('No brief', 'stone')}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(
                                decisionLabel(item.decision_type_snapshot),
                                decisionTone(item.decision_type_snapshot),
                              )}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(
                                coverageLabel(item.coverage_status_snapshot),
                                coverageTone(item.coverage_status_snapshot),
                              )}
                            </td>
                            <td className="px-3 py-3 text-sm font-medium text-stone-950 dark:text-slate-50">
                              {formatNumber(item.opportunity_score_v2_snapshot)}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              <button
                                type="button"
                                className={actionClass}
                                onClick={() => updateSearch({ plan_id: item.id })}
                              >
                                Edit
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                {planQuery.isLoading ? (
                  <LoadingState label="Loading plan details" />
                ) : planQuery.isError ? (
                  <RetriableErrorState
                    title="Could not load plan details"
                    message={getUiErrorMessage(planQuery.error, t)}
                    onRetry={() => void planQuery.refetch()}
                  />
                ) : planQuery.data ? (
                  <section className={sectionClass}>
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div>
                        <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                          Plan #{planQuery.data.id}
                        </h2>
                        <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                          {planQuery.data.keyword}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {renderBadge(planStateLabel(planQuery.data.state_status), planStateTone(planQuery.data.state_status))}
                        {renderBadge(
                          planTargetPageTypeLabel(planQuery.data.target_page_type),
                          planTargetTone(planQuery.data.target_page_type),
                        )}
                        {planQuery.data.has_brief
                          ? renderBadge(
                              planQuery.data.brief_state_status
                                ? `Brief: ${briefStateLabel(planQuery.data.brief_state_status)}`
                                : 'Brief linked',
                              planQuery.data.brief_state_status ? briefStateTone(planQuery.data.brief_state_status) : 'teal',
                            )
                          : null}
                        {planQuery.data.brief_id ? (
                          <Link
                            to={appendQueryString(briefsHref, { brief_id: planQuery.data.brief_id })}
                            className={actionClass}
                          >
                            Open brief
                          </Link>
                        ) : null}
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Source snapshot</p>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>Decision</dt>
                            <dd>{decisionLabel(planQuery.data.decision_type_snapshot)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Bucket</dt>
                            <dd>{bucketLabel(planQuery.data.bucket_snapshot)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Coverage</dt>
                            <dd>{coverageLabel(planQuery.data.coverage_status_snapshot)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Score</dt>
                            <dd>{formatNumber(planQuery.data.opportunity_score_v2_snapshot)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>GSC signal</dt>
                            <dd>{gscLabel(planQuery.data.gsc_signal_status_snapshot)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Source run</dt>
                            <dd>#{planQuery.data.source_run_id}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Brief status</dt>
                            <dd>
                              {planQuery.data.has_brief && planQuery.data.brief_state_status
                                ? briefStateLabel(planQuery.data.brief_state_status)
                                : 'Not created'}
                            </dd>
                          </div>
                        </dl>
                      </div>
                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Dates</p>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>Created at</dt>
                            <dd>{formatDateTime(planQuery.data.created_at)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Updated at</dt>
                            <dd>{formatDateTime(planQuery.data.updated_at)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Best match page</dt>
                            <dd className="max-w-[220px] truncate text-right">
                              {planQuery.data.best_match_page_url_snapshot ?? '-'}
                            </dd>
                          </div>
                        </dl>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4">
                      {updatePlanStatusMutation.isSuccess && updatePlanStatusMutation.data.id === planQuery.data.id ? (
                        <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                          <p className="text-sm font-medium">
                            Status updated to{' '}
                            {planDraft.state_status ? planStateLabel(planDraft.state_status) : 'Planned'}.
                          </p>
                        </div>
                      ) : null}
                      {updatePlanMutation.isSuccess && updatePlanMutation.data.id === planQuery.data.id ? (
                        <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                          <p className="text-sm font-medium">Plan changes saved.</p>
                        </div>
                      ) : null}

                      <div className={panelClass}>
                        <div className="grid gap-4 md:grid-cols-2">
                          <label className={fieldLabelClass}>
                            <span>Plan title</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={planDraft.plan_title ?? ''}
                              onChange={(event) => updatePlanDraft('plan_title', event.target.value)}
                            />
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Status</span>
                            <div className="flex gap-2">
                              <select
                                className={fieldControlClass}
                                value={planDraft.state_status ?? 'planned'}
                                onChange={(event) =>
                                  updatePlanDraft(
                                    'state_status',
                                    readPlanStateStatus(event.target.value) ?? 'planned',
                                  )
                                }
                              >
                                {planStateStatuses.map((status) => (
                                  <option key={status} value={status}>
                                    {planStateLabel(status)}
                                  </option>
                                ))}
                              </select>
                              <button
                                type="button"
                                className={actionClass}
                                disabled={updatePlanStatusMutation.isPending}
                                onClick={() => void handleUpdatePlanStatus()}
                              >
                                Update status
                              </button>
                            </div>
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Target page type</span>
                            <select
                              className={fieldControlClass}
                              value={planDraft.target_page_type ?? 'new_page'}
                              onChange={(event) =>
                                updatePlanDraft(
                                  'target_page_type',
                                  readPlanTargetPageType(event.target.value) ?? 'new_page',
                                )
                              }
                            >
                              {planTargetPageTypes.map((targetPageType) => (
                                <option key={targetPageType} value={targetPageType}>
                                  {planTargetPageTypeLabel(targetPageType)}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Proposed slug</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={planDraft.proposed_slug ?? ''}
                              onChange={(event) => updatePlanDraft('proposed_slug', event.target.value)}
                            />
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Primary keyword</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={planDraft.proposed_primary_keyword ?? ''}
                              onChange={(event) =>
                                updatePlanDraft('proposed_primary_keyword', event.target.value)
                              }
                            />
                          </label>
                          <div className={fieldLabelClass}>
                            <span>Secondary keywords</span>
                            <textarea
                              className={textAreaClass}
                              value={secondaryKeywordsText}
                              onChange={(event) => setSecondaryKeywordsText(event.target.value)}
                              placeholder="One per line or comma separated"
                            />
                          </div>
                        </div>
                        <label className={`${fieldLabelClass} mt-4`}>
                          <span>Planning note</span>
                          <textarea
                            className={textAreaClass}
                            value={planDraft.plan_note ?? ''}
                            onChange={(event) => updatePlanDraft('plan_note', event.target.value)}
                          />
                        </label>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            type="button"
                            className={primaryActionClass}
                            disabled={updatePlanMutation.isPending}
                            onClick={() => void handleSavePlan()}
                          >
                            Save plan
                          </button>
                        </div>
                      </div>
                    </div>
                  </section>
                ) : (
                  <EmptyState
                    title="Select a plan item"
                    description="Pick one item from the list to open its lightweight planning panel."
                  />
                )}
              </div>
            )}
          </>
        ) : null}
      </>
    )
  }

  if (mode === 'briefs') {
    body = (
      <>
        <QuickFilterBar
          title="Brief state"
          items={briefStateStatuses.map((status) => ({
            label: briefStateLabel(status),
            isActive: briefsParams.state_status === status,
            onClick: () =>
              updateSearch({
                state_status: briefsParams.state_status === status ? undefined : status,
                brief_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ state_status: undefined, brief_id: undefined })}
        />
        <QuickFilterBar
          title="Brief type"
          items={briefTypes.map((briefType) => ({
            label: briefTypeLabel(briefType),
            isActive: briefsParams.brief_type === briefType,
            onClick: () =>
              updateSearch({
                brief_type: briefsParams.brief_type === briefType ? undefined : briefType,
                brief_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ brief_type: undefined, brief_id: undefined })}
        />
        <QuickFilterBar
          title="Intent"
          items={briefSearchIntents.map((searchIntent) => ({
            label: briefIntentLabel(searchIntent),
            isActive: briefsParams.search_intent === searchIntent,
            onClick: () =>
              updateSearch({
                search_intent: briefsParams.search_intent === searchIntent ? undefined : searchIntent,
                brief_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ search_intent: undefined, brief_id: undefined })}
        />
        <FilterPanel
          title="Brief filters"
          description="Keep the Semstorm execution backlog easy to scan and easy to edit."
          bodyClassName="grid gap-3 md:grid-cols-2"
          onReset={() =>
            updateSearch({
              state_status: undefined,
              brief_type: undefined,
              search_intent: undefined,
              search: undefined,
              limit: undefined,
              brief_id: undefined,
            })
          }
        >
          <label className={fieldLabelClass}>
            <span>Search</span>
            <input
              className={fieldControlClass}
              type="text"
              value={briefsParams.search ?? ''}
              onChange={(event) =>
                updateSearch({ search: event.target.value || undefined, brief_id: undefined })
              }
              placeholder="Title, keyword, slug"
            />
          </label>
          <label className={fieldLabelClass}>
            <span>Limit</span>
            <input
              className={fieldControlClass}
              type="number"
              min={1}
              max={500}
              value={briefsParams.limit ?? 100}
              onChange={(event) =>
                updateSearch({ limit: Math.max(1, Number(event.target.value) || 1) })
              }
            />
          </label>
        </FilterPanel>

        {briefsQuery.isLoading ? (
          <LoadingState label="Loading Semstorm briefs" />
        ) : briefsQuery.isError ? (
          <RetriableErrorState
            title="Could not load Semstorm briefs"
            message={getUiErrorMessage(briefsQuery.error, t)}
            onRetry={() => void briefsQuery.refetch()}
          />
        ) : briefsQuery.data ? (
          <>
            <SummaryCards
              items={[
                {
                  label: 'Total briefs',
                  value: formatNumber(briefsQuery.data.summary.total_count),
                },
                {
                  label: 'State counts',
                  value: formatNumber(briefsQuery.data.summary.total_count),
                  hint: countLabel(briefsQuery.data.summary.state_counts, briefStateStatuses, briefStateLabels),
                },
                {
                  label: 'Brief types',
                  value: formatNumber(briefsQuery.data.summary.total_count),
                  hint: countLabel(briefsQuery.data.summary.brief_type_counts, briefTypes, briefTypeLabels),
                },
                {
                  label: 'Intent mix',
                  value: formatNumber(briefsQuery.data.summary.total_count),
                  hint: countLabel(briefsQuery.data.summary.intent_counts, briefSearchIntents, briefIntentLabels),
                },
              ]}
            />

            {!briefsQuery.data.items.length ? (
              <EmptyState
                title="No Semstorm briefs yet"
                description="Create briefs from plan items to build lightweight execution packets without mixing them into content recommendations."
              />
            ) : (
              <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.95fr),minmax(0,1.05fr)]">
                <section className={sectionClass}>
                  <div>
                    <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">Brief list</h2>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      Open one brief at a time to adjust the execution packet.
                    </p>
                  </div>
                  <div className="mt-4 overflow-x-auto">
                    <table className="min-w-full border-separate border-spacing-y-2">
                      <thead>
                        <tr className="text-left text-xs uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
                          <th className="px-3 py-2">Title</th>
                          <th className="px-3 py-2">Primary keyword</th>
                          <th className="px-3 py-2">Type</th>
                          <th className="px-3 py-2">Intent</th>
                          <th className="px-3 py-2">Execution</th>
                          <th className="px-3 py-2">Implemented</th>
                          <th className="px-3 py-2">Page title</th>
                          <th className="px-3 py-2">Slug</th>
                          <th className="px-3 py-2">Edit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {briefsQuery.data.items.map((item) => (
                          <tr
                            key={item.id}
                            className={`rounded-3xl align-top ${
                              effectiveBriefId === item.id
                                ? 'bg-teal-50/80 dark:bg-teal-950/30'
                                : 'bg-stone-50/90 dark:bg-slate-900/85'
                            }`}
                          >
                            <td className="px-3 py-3 text-sm font-medium text-stone-950 dark:text-slate-50">
                              {truncateText(item.brief_title ?? '-', 44)}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {item.primary_keyword}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(briefTypeLabel(item.brief_type), briefTypeTone(item.brief_type))}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(briefIntentLabel(item.search_intent), briefIntentTone(item.search_intent))}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(briefStateLabel(item.execution_status), briefStateTone(item.execution_status))}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(
                                implementationLabel(item.implementation_status),
                                implementationTone(item.implementation_status),
                              )}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {truncateText(item.recommended_page_title ?? '-', 44)}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {truncateText(item.proposed_url_slug ?? '-', 32)}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              <button
                                type="button"
                                className={actionClass}
                                onClick={() => updateSearch({ brief_id: item.id, enrichment_run_id: undefined })}
                              >
                                Edit
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                {briefQuery.isLoading ? (
                  <LoadingState label="Loading brief details" />
                ) : briefQuery.isError ? (
                  <RetriableErrorState
                    title="Could not load brief details"
                    message={getUiErrorMessage(briefQuery.error, t)}
                    onRetry={() => void briefQuery.refetch()}
                  />
                ) : briefQuery.data ? (
                  <section className={sectionClass}>
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div>
                        <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                          Brief #{briefQuery.data.id}
                        </h2>
                        <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                          {briefQuery.data.primary_keyword}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {renderBadge(
                          `Execution: ${briefStateLabel(briefQuery.data.execution_status)}`,
                          briefStateTone(briefQuery.data.execution_status),
                        )}
                        {renderBadge(
                          `Implemented: ${implementationLabel(briefQuery.data.implementation_status)}`,
                          implementationTone(briefQuery.data.implementation_status),
                        )}
                        {renderBadge(briefTypeLabel(briefQuery.data.brief_type), briefTypeTone(briefQuery.data.brief_type))}
                        {renderBadge(briefIntentLabel(briefQuery.data.search_intent), briefIntentTone(briefQuery.data.search_intent))}
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Execution context</p>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>Plan item</dt>
                            <dd>#{briefQuery.data.plan_item_id}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Existing URL</dt>
                            <dd className="max-w-[220px] truncate text-right">
                              {briefQuery.data.target_url_existing ?? '-'}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Recommended title</dt>
                            <dd className="max-w-[220px] truncate text-right">
                              {briefQuery.data.recommended_page_title ?? '-'}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Decision</dt>
                            <dd>{briefQuery.data.decision_type_snapshot ? decisionLabel(briefQuery.data.decision_type_snapshot) : '-'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Coverage</dt>
                            <dd>{briefQuery.data.coverage_status_snapshot ? coverageLabel(briefQuery.data.coverage_status_snapshot) : '-'}</dd>
                          </div>
                        </dl>
                      </div>
                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Dates</p>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>Created at</dt>
                            <dd>{formatDateTime(briefQuery.data.created_at)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Updated at</dt>
                            <dd>{formatDateTime(briefQuery.data.updated_at)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Ready at</dt>
                            <dd>{formatDateTime(briefQuery.data.ready_at)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Started at</dt>
                            <dd>{formatDateTime(briefQuery.data.started_at)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Completed at</dt>
                            <dd>{formatDateTime(briefQuery.data.completed_at)}</dd>
                          </div>
                        </dl>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4">
                      {updateBriefStatusMutation.isSuccess && updateBriefStatusMutation.data.id === briefQuery.data.id ? (
                        <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                          <p className="text-sm font-medium">
                            Brief status updated to{' '}
                            {briefDraft.state_status ? briefStateLabel(briefDraft.state_status) : 'Draft'}.
                          </p>
                        </div>
                      ) : null}
                      {updateBriefMutation.isSuccess && updateBriefMutation.data.id === briefQuery.data.id ? (
                        <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                          <p className="text-sm font-medium">Brief changes saved.</p>
                        </div>
                      ) : null}
                      {updateBriefExecutionStatusMutation.isSuccess &&
                      updateBriefExecutionStatusMutation.data.id === briefQuery.data.id ? (
                        <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                          <p className="text-sm font-medium">
                            Execution status updated to {briefStateLabel(updateBriefExecutionStatusMutation.data.execution_status)}.
                          </p>
                        </div>
                      ) : null}
                      {updateBriefExecutionMutation.isSuccess &&
                      updateBriefExecutionMutation.data.id === briefQuery.data.id ? (
                        <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                          <p className="text-sm font-medium">Execution handoff details saved.</p>
                        </div>
                      ) : null}
                      {createBriefEnrichmentMutation.isSuccess &&
                      createBriefEnrichmentMutation.data.brief_item_id === briefQuery.data.id ? (
                        <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                          <p className="text-sm font-medium">
                            AI enrichment run #{createBriefEnrichmentMutation.data.id} is ready for review.
                          </p>
                        </div>
                      ) : null}
                      {createBriefEnrichmentMutation.isError ? (
                        <ErrorState
                          title="Could not enrich this brief"
                          message={getUiErrorMessage(createBriefEnrichmentMutation.error, t)}
                        />
                      ) : null}
                      {applyBriefEnrichmentMutation.isSuccess &&
                      applyBriefEnrichmentMutation.data.brief_id === briefQuery.data.id ? (
                        <div
                          className={`rounded-3xl border px-4 py-3 ${
                            applyBriefEnrichmentMutation.data.applied ? toneClass('teal') : toneClass('amber')
                          }`}
                        >
                          <p className="text-sm font-medium">
                            {applyBriefEnrichmentMutation.data.applied
                              ? 'AI suggestions applied to the brief.'
                              : `AI apply skipped: ${applyBriefEnrichmentMutation.data.skipped_reason ?? 'no changes'}.`}
                          </p>
                        </div>
                      ) : null}
                      {applyBriefEnrichmentMutation.isError ? (
                        <ErrorState
                          title="Could not apply AI suggestions"
                          message={getUiErrorMessage(applyBriefEnrichmentMutation.error, t)}
                        />
                      ) : null}

                      <div className={panelClass}>
                        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                          <div>
                            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                              Execution handoff
                            </p>
                            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                              Brief stays the execution packet. This lifecycle only tracks whether it is ready,
                              actively worked on, completed, or archived.
                            </p>
                          </div>
                          {renderExecutionStatusActions(briefQuery.data.execution_status)}
                        </div>
                        <div className="mt-4 grid gap-4 md:grid-cols-2">
                          <label className={fieldLabelClass}>
                            <span>Assignee</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={executionDraft.assignee}
                              onChange={(event) => updateExecutionDraft('assignee', event.target.value)}
                              placeholder="SEO lead, editor, freelancer"
                            />
                          </label>
                          <div className={panelClass}>
                            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                              Execution timestamps
                            </p>
                            <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                              <div className="flex items-center justify-between gap-3">
                                <dt>Ready</dt>
                                <dd>{formatDateTime(briefQuery.data.ready_at)}</dd>
                              </div>
                              <div className="flex items-center justify-between gap-3">
                                <dt>Started</dt>
                                <dd>{formatDateTime(briefQuery.data.started_at)}</dd>
                              </div>
                              <div className="flex items-center justify-between gap-3">
                                <dt>Completed</dt>
                                <dd>{formatDateTime(briefQuery.data.completed_at)}</dd>
                              </div>
                              <div className="flex items-center justify-between gap-3">
                                <dt>Archived</dt>
                                <dd>{formatDateTime(briefQuery.data.archived_at)}</dd>
                              </div>
                            </dl>
                          </div>
                        </div>
                        <label className={`${fieldLabelClass} mt-4`}>
                          <span>Execution note</span>
                          <textarea
                            className={textAreaClass}
                            value={executionDraft.execution_note}
                            onChange={(event) => updateExecutionDraft('execution_note', event.target.value)}
                            placeholder="Short handoff note, constraints, dependencies"
                          />
                        </label>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            type="button"
                            className={actionClass}
                            disabled={updateBriefExecutionMutation.isPending}
                            onClick={() => void handleSaveExecutionMetadata()}
                          >
                            Save execution details
                          </button>
                        </div>
                      </div>

                      {renderImplementationPanel()}

                      <div className={panelClass}>
                        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                          <div>
                            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                              AI enrichment
                            </p>
                            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                              The scaffold brief stays your base. AI enrichment adds optional suggestions you can
                              review and apply to the execution packet.
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              className={primaryActionClass}
                              disabled={createBriefEnrichmentMutation.isPending}
                              onClick={() => void handleEnrichBrief()}
                            >
                              {createBriefEnrichmentMutation.isPending ? 'Enriching...' : 'Enrich with AI'}
                            </button>
                            <button
                              type="button"
                              className={actionClass}
                              disabled={
                                selectedEnrichmentRun == null ||
                                selectedEnrichmentRun.status !== 'completed' ||
                                selectedEnrichmentRun.is_applied ||
                                !selectedEnrichmentRunHasSuggestions ||
                                applyBriefEnrichmentMutation.isPending
                              }
                              onClick={() => void handleApplyEnrichment()}
                            >
                              {applyBriefEnrichmentMutation.isPending ? 'Applying...' : 'Apply suggestions'}
                            </button>
                          </div>
                        </div>

                        {briefEnrichmentRunsQuery.isLoading ? (
                          <div className="mt-4">
                            <LoadingState label="Loading AI enrichment runs" />
                          </div>
                        ) : briefEnrichmentRunsQuery.isError ? (
                          <div className="mt-4">
                            <RetriableErrorState
                              title="Could not load AI enrichment runs"
                              message={getUiErrorMessage(briefEnrichmentRunsQuery.error, t)}
                              onRetry={() => void briefEnrichmentRunsQuery.refetch()}
                            />
                          </div>
                        ) : !briefEnrichmentRunsQuery.data?.items.length ? (
                          <div className="mt-4 rounded-3xl border border-dashed border-stone-300 px-4 py-5 text-sm text-stone-600 dark:border-slate-700 dark:text-slate-300">
                            No AI enrichment runs yet. Use the scaffold brief as your base, then run optional AI
                            suggestions when you want a refinement pass.
                          </div>
                        ) : (
                          <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(220px,0.72fr),minmax(0,1.28fr)]">
                            <div className="space-y-3">
                              <div className="rounded-3xl border border-stone-200 bg-white/80 p-4 text-sm dark:border-slate-700 dark:bg-slate-950/60">
                                <p className="font-semibold text-stone-900 dark:text-slate-50">Run history</p>
                                <p className="mt-1 text-stone-600 dark:text-slate-300">
                                  Total: {formatNumber(briefEnrichmentRunsQuery.data.summary.total_count)} | Applied:{' '}
                                  {formatNumber(briefEnrichmentRunsQuery.data.summary.applied_count)}
                                </p>
                              </div>
                              {briefEnrichmentRunsQuery.data.items.map((item) => (
                                <button
                                  key={item.id}
                                  type="button"
                                  aria-label={`Open enrichment run ${item.id}`}
                                  onClick={() => updateSearch({ enrichment_run_id: item.id })}
                                  className={`w-full rounded-3xl border p-4 text-left transition ${
                                    selectedEnrichmentRun?.id === item.id
                                      ? 'border-teal-400 bg-teal-50/80 dark:border-teal-500 dark:bg-teal-950/30'
                                      : 'border-stone-200 bg-white/80 hover:border-stone-300 hover:bg-stone-100 dark:border-slate-700 dark:bg-slate-950/60 dark:hover:border-slate-500 dark:hover:bg-slate-900'
                                  }`}
                                >
                                  <div className="flex flex-wrap items-start justify-between gap-2">
                                    <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                                      Run #{item.id}
                                    </p>
                                    <div className="flex flex-wrap gap-2">
                                      {renderBadge(
                                        briefEnrichmentStatusLabel(item.status),
                                        briefEnrichmentStatusTone(item.status),
                                      )}
                                      {renderBadge(briefEnrichmentEngineModeLabel(item.engine_mode), 'stone')}
                                      {item.is_applied ? renderBadge('Applied', 'teal') : null}
                                    </div>
                                  </div>
                                  <p className="mt-2 text-xs text-stone-500 dark:text-slate-400">
                                    {formatDateTime(item.created_at)}
                                  </p>
                                  <p className="mt-1 text-xs text-stone-500 dark:text-slate-400">
                                    {item.model_name ?? 'No model name'}
                                  </p>
                                </button>
                              ))}
                            </div>

                            {selectedEnrichmentRun ? (
                              <div className="space-y-4">
                                <div className="rounded-3xl border border-stone-200 bg-white/80 p-4 dark:border-slate-700 dark:bg-slate-950/60">
                                  <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                                    <div>
                                      <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                                        AI suggestions
                                      </p>
                                      <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                                        Review changes before applying them to the brief.
                                      </p>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                      {renderBadge(
                                        briefEnrichmentStatusLabel(selectedEnrichmentRun.status),
                                        briefEnrichmentStatusTone(selectedEnrichmentRun.status),
                                      )}
                                      {renderBadge(
                                        briefEnrichmentEngineModeLabel(selectedEnrichmentRun.engine_mode),
                                        'stone',
                                      )}
                                      {selectedEnrichmentRun.is_applied ? renderBadge('Applied', 'teal') : null}
                                    </div>
                                  </div>
                                  <div className="mt-3 grid gap-2 text-sm text-stone-600 dark:text-slate-300 md:grid-cols-2">
                                    <p>Created: {formatDateTime(selectedEnrichmentRun.created_at)}</p>
                                    <p>Model: {selectedEnrichmentRun.model_name ?? 'Unavailable'}</p>
                                  </div>

                                  {selectedEnrichmentRun.status === 'failed' ? (
                                    <div className={`mt-4 rounded-3xl border px-4 py-3 ${toneClass('rose')}`}>
                                      <p className="text-sm font-medium">
                                        {selectedEnrichmentRun.error_message_safe ?? 'AI enrichment failed.'}
                                      </p>
                                      {selectedEnrichmentRun.error_code ? (
                                        <p className="mt-1 text-xs uppercase tracking-[0.14em]">
                                          {selectedEnrichmentRun.error_code}
                                        </p>
                                      ) : null}
                                    </div>
                                  ) : (
                                    <div className="mt-4 grid gap-4 xl:grid-cols-2">
                                      <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-700 dark:bg-slate-900/80">
                                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                                          Current scaffold
                                        </p>
                                        <dl className="mt-3 grid gap-3 text-sm text-stone-700 dark:text-slate-300">
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Brief title</dt>
                                            <dd className="mt-1">{briefQuery.data.brief_title ?? '-'}</dd>
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Page title</dt>
                                            <dd className="mt-1">{briefQuery.data.recommended_page_title ?? '-'}</dd>
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">H1</dt>
                                            <dd className="mt-1">{briefQuery.data.recommended_h1 ?? '-'}</dd>
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Angle summary</dt>
                                            <dd className="mt-1 whitespace-pre-wrap">
                                              {briefQuery.data.angle_summary ?? '-'}
                                            </dd>
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Sections</dt>
                                            {briefQuery.data.sections.length ? (
                                              <ul className="mt-2 space-y-1">
                                                {briefQuery.data.sections.map((section) => (
                                                  <li key={`current-section-${section}`}>{section}</li>
                                                ))}
                                              </ul>
                                            ) : (
                                              <dd className="mt-1">-</dd>
                                            )}
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Internal links</dt>
                                            {briefQuery.data.internal_link_targets.length ? (
                                              <ul className="mt-2 space-y-1 break-all">
                                                {briefQuery.data.internal_link_targets.map((link) => (
                                                  <li key={`current-link-${link}`}>{link}</li>
                                                ))}
                                              </ul>
                                            ) : (
                                              <dd className="mt-1">-</dd>
                                            )}
                                          </div>
                                        </dl>
                                      </div>

                                      <div className="rounded-3xl border border-teal-200 bg-teal-50/80 p-4 dark:border-teal-900 dark:bg-teal-950/30">
                                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                                          Suggested changes
                                        </p>
                                        <dl className="mt-3 grid gap-3 text-sm text-stone-700 dark:text-slate-300">
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Brief title</dt>
                                            <dd className="mt-1">
                                              {selectedEnrichmentRun.suggestions.improved_brief_title ?? '-'}
                                            </dd>
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Page title</dt>
                                            <dd className="mt-1">
                                              {selectedEnrichmentRun.suggestions.improved_page_title ?? '-'}
                                            </dd>
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">H1</dt>
                                            <dd className="mt-1">{selectedEnrichmentRun.suggestions.improved_h1 ?? '-'}</dd>
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Angle summary</dt>
                                            <dd className="mt-1 whitespace-pre-wrap">
                                              {selectedEnrichmentRun.suggestions.improved_angle_summary ?? '-'}
                                            </dd>
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Sections</dt>
                                            {selectedEnrichmentRun.suggestions.improved_sections.length ? (
                                              <ul className="mt-2 space-y-1">
                                                {selectedEnrichmentRun.suggestions.improved_sections.map((section) => (
                                                  <li key={`suggested-section-${section}`}>{section}</li>
                                                ))}
                                              </ul>
                                            ) : (
                                              <dd className="mt-1">-</dd>
                                            )}
                                          </div>
                                          <div>
                                            <dt className="font-medium text-stone-900 dark:text-slate-50">Internal links</dt>
                                            {selectedEnrichmentRun.suggestions.improved_internal_link_targets.length ? (
                                              <ul className="mt-2 space-y-1 break-all">
                                                {selectedEnrichmentRun.suggestions.improved_internal_link_targets.map(
                                                  (link) => (
                                                    <li key={`suggested-link-${link}`}>{link}</li>
                                                  ),
                                                )}
                                              </ul>
                                            ) : (
                                              <dd className="mt-1">-</dd>
                                            )}
                                          </div>
                                        </dl>
                                      </div>
                                    </div>
                                  )}

                                  {selectedEnrichmentRun.status === 'completed' ? (
                                    <div className="mt-4 grid gap-4 xl:grid-cols-2">
                                      <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-700 dark:bg-slate-900/80">
                                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                                          Editorial notes
                                        </p>
                                        {selectedEnrichmentRun.suggestions.editorial_notes.length ? (
                                          <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                                            {selectedEnrichmentRun.suggestions.editorial_notes.map((note) => (
                                              <li key={`editorial-note-${note}`}>{note}</li>
                                            ))}
                                          </ul>
                                        ) : (
                                          <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                                            No editorial notes returned for this run.
                                          </p>
                                        )}
                                      </div>
                                      <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-700 dark:bg-slate-900/80">
                                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                                          Risk flags
                                        </p>
                                        {selectedEnrichmentRun.suggestions.risk_flags.length ? (
                                          <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-300">
                                            {selectedEnrichmentRun.suggestions.risk_flags.map((risk) => (
                                              <li key={`risk-flag-${risk}`}>{risk}</li>
                                            ))}
                                          </ul>
                                        ) : (
                                          <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">
                                            No risk flags returned for this run.
                                          </p>
                                        )}
                                      </div>
                                    </div>
                                  ) : null}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        )}
                      </div>

                      <div className={panelClass}>
                        <div className="grid gap-4 md:grid-cols-2">
                          <label className={fieldLabelClass}>
                            <span>Brief title</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={briefDraft.brief_title ?? ''}
                              onChange={(event) => updateBriefDraft('brief_title', event.target.value)}
                            />
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Status</span>
                            <div className="flex gap-2">
                              <select
                                className={fieldControlClass}
                                value={briefDraft.state_status ?? 'draft'}
                                onChange={(event) =>
                                  updateBriefDraft(
                                    'state_status',
                                    readBriefStateStatus(event.target.value) ?? 'draft',
                                  )
                                }
                              >
                                {briefStateStatuses.map((status) => (
                                  <option key={status} value={status}>
                                    {briefStateLabel(status)}
                                  </option>
                                ))}
                              </select>
                              <button
                                type="button"
                                className={actionClass}
                                disabled={updateBriefStatusMutation.isPending}
                                onClick={() => void handleUpdateBriefStatus()}
                              >
                                Update status
                              </button>
                            </div>
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Brief type</span>
                            <select
                              className={fieldControlClass}
                              value={briefDraft.brief_type ?? 'new_page'}
                              onChange={(event) =>
                                updateBriefDraft('brief_type', readBriefType(event.target.value) ?? 'new_page')
                              }
                            >
                              {briefTypes.map((briefType) => (
                                <option key={briefType} value={briefType}>
                                  {briefTypeLabel(briefType)}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Search intent</span>
                            <select
                              className={fieldControlClass}
                              value={briefDraft.search_intent ?? 'mixed'}
                              onChange={(event) =>
                                updateBriefDraft(
                                  'search_intent',
                                  readBriefSearchIntent(event.target.value) ?? 'mixed',
                                )
                              }
                            >
                              {briefSearchIntents.map((searchIntent) => (
                                <option key={searchIntent} value={searchIntent}>
                                  {briefIntentLabel(searchIntent)}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Primary keyword</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={briefDraft.primary_keyword ?? ''}
                              onChange={(event) => updateBriefDraft('primary_keyword', event.target.value)}
                            />
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Proposed slug</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={briefDraft.proposed_url_slug ?? ''}
                              onChange={(event) => updateBriefDraft('proposed_url_slug', event.target.value)}
                            />
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Existing target URL</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={briefDraft.target_url_existing ?? ''}
                              onChange={(event) => updateBriefDraft('target_url_existing', event.target.value)}
                            />
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Recommended page title</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={briefDraft.recommended_page_title ?? ''}
                              onChange={(event) => updateBriefDraft('recommended_page_title', event.target.value)}
                            />
                          </label>
                          <label className={fieldLabelClass}>
                            <span>Recommended H1</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={briefDraft.recommended_h1 ?? ''}
                              onChange={(event) => updateBriefDraft('recommended_h1', event.target.value)}
                            />
                          </label>
                          <div className={fieldLabelClass}>
                            <span>Secondary keywords</span>
                            <textarea
                              className={textAreaClass}
                              value={briefSecondaryKeywordsText}
                              onChange={(event) => setBriefSecondaryKeywordsText(event.target.value)}
                              placeholder="One per line or comma separated"
                            />
                          </div>
                          <div className={fieldLabelClass}>
                            <span>Sections</span>
                            <textarea
                              className={textAreaClass}
                              value={briefSectionsText}
                              onChange={(event) => setBriefSectionsText(event.target.value)}
                              placeholder="One per line or comma separated"
                            />
                          </div>
                          <div className={fieldLabelClass}>
                            <span>Internal links</span>
                            <textarea
                              className={textAreaClass}
                              value={briefInternalLinksText}
                              onChange={(event) => setBriefInternalLinksText(event.target.value)}
                              placeholder="One per line or comma separated"
                            />
                          </div>
                          <div className={fieldLabelClass}>
                            <span>Source notes</span>
                            <textarea
                              className={textAreaClass}
                              value={briefSourceNotesText}
                              onChange={(event) => setBriefSourceNotesText(event.target.value)}
                              placeholder="One per line or comma separated"
                            />
                          </div>
                        </div>
                        <label className={`${fieldLabelClass} mt-4`}>
                          <span>Content goal</span>
                          <textarea
                            className={textAreaClass}
                            value={briefDraft.content_goal ?? ''}
                            onChange={(event) => updateBriefDraft('content_goal', event.target.value)}
                          />
                        </label>
                        <label className={`${fieldLabelClass} mt-4`}>
                          <span>Angle summary</span>
                          <textarea
                            className={textAreaClass}
                            value={briefDraft.angle_summary ?? ''}
                            onChange={(event) => updateBriefDraft('angle_summary', event.target.value)}
                          />
                        </label>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            type="button"
                            className={primaryActionClass}
                            disabled={updateBriefMutation.isPending}
                            onClick={() => void handleSaveBrief()}
                          >
                            Save brief
                          </button>
                        </div>
                      </div>
                    </div>
                  </section>
                ) : (
                  <EmptyState
                    title="Select a brief"
                    description="Pick one execution packet from the list to open its lightweight editing panel."
                  />
                )}
              </div>
            )}
          </>
        ) : null}
      </>
    )
  }

  if (mode === 'execution') {
    const executionAssigneeOptions = Array.from(
      new Set((executionQuery.data?.items ?? []).map((item) => item.assignee?.trim()).filter(Boolean)),
    ) as string[]

    body = (
      <>
        <QuickFilterBar
          title="Execution status"
          items={briefStateStatuses.map((status) => ({
            label: briefStateLabel(status),
            isActive: executionParams.execution_status === status,
            onClick: () =>
              updateSearch({
                execution_status: executionParams.execution_status === status ? undefined : status,
                brief_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ execution_status: undefined, brief_id: undefined })}
        />
        <QuickFilterBar
          title="Brief type"
          items={briefTypes.map((briefType) => ({
            label: briefTypeLabel(briefType),
            isActive: executionParams.brief_type === briefType,
            onClick: () =>
              updateSearch({
                brief_type: executionParams.brief_type === briefType ? undefined : briefType,
                brief_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ brief_type: undefined, brief_id: undefined })}
        />
        <QuickFilterBar
          title="Assignee"
          items={executionAssigneeOptions.map((assignee) => ({
            label: assignee,
            isActive: executionParams.assignee === assignee,
            onClick: () =>
              updateSearch({
                assignee: executionParams.assignee === assignee ? undefined : assignee,
                brief_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ assignee: undefined, brief_id: undefined })}
        />
        <FilterPanel
          title="Execution filters"
          description="Keep the handoff queue easy to scan without turning it into a mini project manager."
          bodyClassName="grid gap-3 md:grid-cols-3"
          onReset={() =>
            updateSearch({
              execution_status: undefined,
              brief_type: undefined,
              assignee: undefined,
              search: undefined,
              limit: undefined,
              brief_id: undefined,
            })
          }
        >
          <label className={fieldLabelClass}>
            <span>Assignee</span>
            <input
              className={fieldControlClass}
              type="text"
              value={executionParams.assignee ?? ''}
              onChange={(event) => updateSearch({ assignee: event.target.value || undefined, brief_id: undefined })}
              placeholder="SEO lead, editor, freelancer"
            />
          </label>
          <label className={fieldLabelClass}>
            <span>Search</span>
            <input
              className={fieldControlClass}
              type="text"
              value={executionParams.search ?? ''}
              onChange={(event) => updateSearch({ search: event.target.value || undefined, brief_id: undefined })}
              placeholder="Title, keyword, slug"
            />
          </label>
          <label className={fieldLabelClass}>
            <span>Limit</span>
            <input
              className={fieldControlClass}
              type="number"
              min={1}
              max={500}
              value={executionParams.limit ?? 100}
              onChange={(event) => updateSearch({ limit: Math.max(1, Number(event.target.value) || 1) })}
            />
          </label>
        </FilterPanel>

        {executionQuery.isLoading ? (
          <LoadingState label="Loading Semstorm execution queue" />
        ) : executionQuery.isError ? (
          <RetriableErrorState
            title="Could not load Semstorm execution items"
            message={getUiErrorMessage(executionQuery.error, t)}
            onRetry={() => void executionQuery.refetch()}
          />
        ) : executionQuery.data ? (
          <>
            <SummaryCards
              items={[
                {
                  label: 'Total briefs',
                  value: formatNumber(executionQuery.data.summary.total_count),
                },
                {
                  label: 'Execution states',
                  value: formatNumber(executionQuery.data.summary.total_count),
                  hint: countLabel(
                    executionQuery.data.summary.execution_status_counts,
                    briefStateStatuses,
                    briefStateLabels,
                  ),
                },
                {
                  label: 'Ready',
                  value: formatNumber(executionQuery.data.summary.ready_count),
                },
                {
                  label: 'In execution',
                  value: formatNumber(executionQuery.data.summary.in_execution_count),
                },
                {
                  label: 'Completed',
                  value: formatNumber(executionQuery.data.summary.completed_count),
                },
              ]}
            />

            {!executionQuery.data.items.length ? (
              <EmptyState
                title="No Semstorm execution items yet"
                description="Move briefs beyond draft to build a lightweight execution board for the current Semstorm workflow."
              />
            ) : (
              <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.95fr),minmax(0,1.05fr)]">
                <section className={sectionClass}>
                  <div>
                    <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">Execution board</h2>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      Review handoff status, ownership and the brief context without leaving the Semstorm slice.
                    </p>
                  </div>
                  <div className="mt-4 overflow-x-auto">
                    <table className="min-w-full border-separate border-spacing-y-2">
                      <thead>
                        <tr className="text-left text-xs uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
                          <th className="px-3 py-2">Brief</th>
                          <th className="px-3 py-2">Keyword</th>
                          <th className="px-3 py-2">Type</th>
                          <th className="px-3 py-2">Execution</th>
                          <th className="px-3 py-2">Implemented</th>
                          <th className="px-3 py-2">Assignee</th>
                          <th className="px-3 py-2">Page title</th>
                          <th className="px-3 py-2">Slug</th>
                          <th className="px-3 py-2">Open</th>
                        </tr>
                      </thead>
                      <tbody>
                        {executionQuery.data.items.map((item) => (
                          <tr
                            key={item.brief_id}
                            className={`rounded-3xl align-top ${
                              effectiveBriefId === item.brief_id
                                ? 'bg-teal-50/80 dark:bg-teal-950/30'
                                : 'bg-stone-50/90 dark:bg-slate-900/85'
                            }`}
                          >
                            <td className="px-3 py-3 text-sm font-medium text-stone-950 dark:text-slate-50">
                              {truncateText(item.brief_title ?? '-', 44)}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {item.primary_keyword}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(briefTypeLabel(item.brief_type), briefTypeTone(item.brief_type))}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(briefStateLabel(item.execution_status), briefStateTone(item.execution_status))}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(
                                implementationLabel(item.implementation_status),
                                implementationTone(item.implementation_status),
                              )}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {item.assignee ?? '-'}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {truncateText(item.recommended_page_title ?? '-', 44)}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {truncateText(item.proposed_url_slug ?? '-', 32)}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              <button
                                type="button"
                                className={actionClass}
                                onClick={() => updateSearch({ brief_id: item.brief_id })}
                              >
                                Open
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                {briefQuery.isLoading ? (
                  <LoadingState label="Loading execution brief details" />
                ) : briefQuery.isError ? (
                  <RetriableErrorState
                    title="Could not load execution brief details"
                    message={getUiErrorMessage(briefQuery.error, t)}
                    onRetry={() => void briefQuery.refetch()}
                  />
                ) : briefQuery.data ? (
                  <section className={sectionClass}>
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div>
                        <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                          Execution packet #{briefQuery.data.id}
                        </h2>
                        <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                          {briefQuery.data.primary_keyword}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {renderBadge(
                          `Execution: ${briefStateLabel(briefQuery.data.execution_status)}`,
                          briefStateTone(briefQuery.data.execution_status),
                        )}
                        {renderBadge(
                          `Implemented: ${implementationLabel(briefQuery.data.implementation_status)}`,
                          implementationTone(briefQuery.data.implementation_status),
                        )}
                        {renderBadge(briefTypeLabel(briefQuery.data.brief_type), briefTypeTone(briefQuery.data.brief_type))}
                        {renderBadge(
                          briefIntentLabel(briefQuery.data.search_intent),
                          briefIntentTone(briefQuery.data.search_intent),
                        )}
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Brief summary</p>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>Recommended title</dt>
                            <dd className="max-w-[220px] truncate text-right">
                              {briefQuery.data.recommended_page_title ?? '-'}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Recommended H1</dt>
                            <dd className="max-w-[220px] truncate text-right">{briefQuery.data.recommended_h1 ?? '-'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Slug</dt>
                            <dd>{briefQuery.data.proposed_url_slug ?? '-'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Existing URL</dt>
                            <dd className="max-w-[220px] truncate text-right">
                              {briefQuery.data.target_url_existing ?? '-'}
                            </dd>
                          </div>
                        </dl>
                      </div>
                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Source context</p>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>Decision</dt>
                            <dd>{briefQuery.data.decision_type_snapshot ? decisionLabel(briefQuery.data.decision_type_snapshot) : '-'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Coverage</dt>
                            <dd>{briefQuery.data.coverage_status_snapshot ? coverageLabel(briefQuery.data.coverage_status_snapshot) : '-'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>GSC signal</dt>
                            <dd>{briefQuery.data.gsc_signal_status_snapshot ? gscLabel(briefQuery.data.gsc_signal_status_snapshot) : '-'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Opportunity score</dt>
                            <dd>{formatNumber(briefQuery.data.opportunity_score_v2_snapshot)}</dd>
                          </div>
                        </dl>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4">
                      {updateBriefExecutionStatusMutation.isSuccess &&
                      updateBriefExecutionStatusMutation.data.id === briefQuery.data.id ? (
                        <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                          <p className="text-sm font-medium">
                            Execution status updated to {briefStateLabel(updateBriefExecutionStatusMutation.data.execution_status)}.
                          </p>
                        </div>
                      ) : null}
                      {updateBriefExecutionMutation.isSuccess &&
                      updateBriefExecutionMutation.data.id === briefQuery.data.id ? (
                        <div className={`rounded-3xl border px-4 py-3 ${toneClass('teal')}`}>
                          <p className="text-sm font-medium">Execution handoff details saved.</p>
                        </div>
                      ) : null}

                      <div className={panelClass}>
                        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                          <div>
                            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                              Execution lifecycle
                            </p>
                            <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                              Move the execution packet from draft to ready, active work, completed, or archived.
                            </p>
                          </div>
                          {renderExecutionStatusActions(briefQuery.data.execution_status)}
                        </div>
                        <div className="mt-4 grid gap-4 md:grid-cols-2">
                          <label className={fieldLabelClass}>
                            <span>Assignee</span>
                            <input
                              className={fieldControlClass}
                              type="text"
                              value={executionDraft.assignee}
                              onChange={(event) => updateExecutionDraft('assignee', event.target.value)}
                              placeholder="SEO lead, editor, freelancer"
                            />
                          </label>
                          <div className={panelClass}>
                            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Execution dates</p>
                            <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                              <div className="flex items-center justify-between gap-3">
                                <dt>Ready</dt>
                                <dd>{formatDateTime(briefQuery.data.ready_at)}</dd>
                              </div>
                              <div className="flex items-center justify-between gap-3">
                                <dt>Started</dt>
                                <dd>{formatDateTime(briefQuery.data.started_at)}</dd>
                              </div>
                              <div className="flex items-center justify-between gap-3">
                                <dt>Completed</dt>
                                <dd>{formatDateTime(briefQuery.data.completed_at)}</dd>
                              </div>
                              <div className="flex items-center justify-between gap-3">
                                <dt>Archived</dt>
                                <dd>{formatDateTime(briefQuery.data.archived_at)}</dd>
                              </div>
                            </dl>
                          </div>
                        </div>
                        <label className={`${fieldLabelClass} mt-4`}>
                          <span>Execution note</span>
                          <textarea
                            className={textAreaClass}
                            value={executionDraft.execution_note}
                            onChange={(event) => updateExecutionDraft('execution_note', event.target.value)}
                            placeholder="Handoff context, blockers, editorial notes"
                          />
                        </label>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            type="button"
                            className={actionClass}
                            disabled={updateBriefExecutionMutation.isPending}
                            onClick={() => void handleSaveExecutionMetadata()}
                          >
                            Save execution details
                          </button>
                          <Link to={briefsHref} className={actionClass}>
                            Open full brief editor
                          </Link>
                        </div>
                      </div>

                      {renderImplementationPanel()}

                      <div className={panelClass}>
                        <div className="grid gap-4 md:grid-cols-2">
                          <div>
                            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Content goal</p>
                            <p className="mt-2 text-sm text-stone-700 dark:text-slate-300">
                              {briefQuery.data.content_goal ?? '-'}
                            </p>
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Angle summary</p>
                            <p className="mt-2 text-sm text-stone-700 dark:text-slate-300">
                              {briefQuery.data.angle_summary ?? '-'}
                            </p>
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Sections</p>
                            {briefQuery.data.sections.length ? (
                              <ul className="mt-2 space-y-1 text-sm text-stone-700 dark:text-slate-300">
                                {briefQuery.data.sections.map((section) => (
                                  <li key={section}>{section}</li>
                                ))}
                              </ul>
                            ) : (
                              <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">No sections yet.</p>
                            )}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">
                              Internal link targets
                            </p>
                            {briefQuery.data.internal_link_targets.length ? (
                              <ul className="mt-2 space-y-1 text-sm text-stone-700 dark:text-slate-300">
                                {briefQuery.data.internal_link_targets.map((link) => (
                                  <li key={link}>{link}</li>
                                ))}
                              </ul>
                            ) : (
                              <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">No internal link targets yet.</p>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </section>
                ) : (
                  <EmptyState
                    title="Select an execution packet"
                    description="Pick one brief from the execution queue to review handoff status, ownership and core packet details."
                  />
                )}
              </div>
            )}
          </>
        ) : null}
      </>
    )
  }

  if (mode === 'implemented') {
    body = (
      <>
        <QuickFilterBar
          title="Implementation status"
          items={implementationStatuses.map((status) => ({
            label: implementationLabel(status),
            isActive: implementedParams.implementation_status === status,
            onClick: () =>
              updateSearch({
                implementation_status: implementedParams.implementation_status === status ? undefined : status,
                brief_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ implementation_status: undefined, brief_id: undefined })}
        />
        <QuickFilterBar
          title="Outcome status"
          items={outcomeStatuses.map((status) => ({
            label: outcomeLabel(status),
            isActive: implementedParams.outcome_status === status,
            onClick: () =>
              updateSearch({
                outcome_status: implementedParams.outcome_status === status ? undefined : status,
                brief_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ outcome_status: undefined, brief_id: undefined })}
        />
        <QuickFilterBar
          title="Brief type"
          items={briefTypes.map((briefType) => ({
            label: briefTypeLabel(briefType),
            isActive: implementedParams.brief_type === briefType,
            onClick: () =>
              updateSearch({
                brief_type: implementedParams.brief_type === briefType ? undefined : briefType,
                brief_id: undefined,
              }),
          }))}
          onReset={() => updateSearch({ brief_type: undefined, brief_id: undefined })}
        />
        <FilterPanel
          title="Outcome filters"
          description="Review implemented briefs against the current active crawl and available GSC context without turning this into a BI dashboard."
          bodyClassName="grid gap-3 md:grid-cols-3"
          onReset={() =>
            updateSearch({
              implementation_status: undefined,
              outcome_status: undefined,
              brief_type: undefined,
              search: undefined,
              window_days: undefined,
              limit: undefined,
              brief_id: undefined,
            })
          }
        >
          <label className={fieldLabelClass}>
            <span>Search</span>
            <input
              className={fieldControlClass}
              type="text"
              value={implementedParams.search ?? ''}
              onChange={(event) => updateSearch({ search: event.target.value || undefined, brief_id: undefined })}
              placeholder="Title, keyword, matched URL"
            />
          </label>
          <label className={fieldLabelClass}>
            <span>Outcome window (days)</span>
            <input
              className={fieldControlClass}
              type="number"
              min={1}
              max={365}
              value={implementedParams.window_days ?? 30}
              onChange={(event) =>
                updateSearch({ window_days: Math.max(1, Math.min(365, Number(event.target.value) || 1)) })
              }
            />
          </label>
          <label className={fieldLabelClass}>
            <span>Limit</span>
            <input
              className={fieldControlClass}
              type="number"
              min={1}
              max={500}
              value={implementedParams.limit ?? 100}
              onChange={(event) => updateSearch({ limit: Math.max(1, Number(event.target.value) || 1) })}
            />
          </label>
        </FilterPanel>

        {implementedQuery.isLoading ? (
          <LoadingState label="Loading implemented Semstorm briefs" />
        ) : implementedQuery.isError ? (
          <RetriableErrorState
            title="Could not load Semstorm implemented items"
            message={getUiErrorMessage(implementedQuery.error, t)}
            onRetry={() => void implementedQuery.refetch()}
          />
        ) : implementedQuery.data ? (
          <>
            <SummaryCards
              items={[
                {
                  label: 'Total implemented',
                  value: formatNumber(implementedQuery.data.summary.total_count),
                },
                {
                  label: 'Implementation states',
                  value: formatNumber(implementedQuery.data.summary.total_count),
                  hint: countLabel(
                    implementedQuery.data.summary.implementation_status_counts,
                    implementationStatuses,
                    implementationLabels,
                  ),
                },
                {
                  label: 'Outcome states',
                  value: formatNumber(implementedQuery.data.summary.total_count),
                  hint: countLabel(
                    implementedQuery.data.summary.outcome_status_counts,
                    outcomeStatuses,
                    outcomeLabels,
                  ),
                },
                {
                  label: 'Too early',
                  value: formatNumber(implementedQuery.data.summary.too_early_count),
                },
                {
                  label: 'Positive signal',
                  value: formatNumber(implementedQuery.data.summary.positive_signal_count),
                },
              ]}
            />

            {implementedQuery.data.active_crawl_id === null ? (
              <div className={`rounded-3xl border px-4 py-3 ${toneClass('amber')}`}>
                <p className="text-sm font-medium">
                  No active crawl is available. Outcome checks can still show stored implementation state, but page
                  and GSC matching will stay limited until the site has an active snapshot.
                </p>
              </div>
            ) : null}

            {!implementedQuery.data.items.length ? (
              <EmptyState
                title="No implemented Semstorm briefs yet"
                description="Mark completed execution packets as implemented to start the lightweight feedback loop over the active crawl and available GSC data."
              />
            ) : (
              <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.95fr),minmax(0,1.05fr)]">
                <section className={sectionClass}>
                  <div>
                    <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">Implemented list</h2>
                    <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                      Review which execution packets are already live, still too early to judge, or starting to show a
                      signal.
                    </p>
                  </div>
                  <div className="mt-4 overflow-x-auto">
                    <table className="min-w-full border-separate border-spacing-y-2">
                      <thead>
                        <tr className="text-left text-xs uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
                          <th className="px-3 py-2">Brief</th>
                          <th className="px-3 py-2">Keyword</th>
                          <th className="px-3 py-2">Implemented</th>
                          <th className="px-3 py-2">Outcome</th>
                          <th className="px-3 py-2">Page present</th>
                          <th className="px-3 py-2">GSC</th>
                          <th className="px-3 py-2">Implemented at</th>
                          <th className="px-3 py-2">Open</th>
                        </tr>
                      </thead>
                      <tbody>
                        {implementedQuery.data.items.map((item) => (
                          <tr
                            key={item.brief_id}
                            className={`rounded-3xl align-top ${
                              effectiveBriefId === item.brief_id
                                ? 'bg-teal-50/80 dark:bg-teal-950/30'
                                : 'bg-stone-50/90 dark:bg-slate-900/85'
                            }`}
                          >
                            <td className="px-3 py-3 text-sm font-medium text-stone-950 dark:text-slate-50">
                              {truncateText(item.brief_title ?? '-', 44)}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {item.primary_keyword}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(
                                implementationLabel(item.implementation_status),
                                implementationTone(item.implementation_status),
                              )}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(outcomeLabel(item.outcome_status), outcomeTone(item.outcome_status))}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {item.page_present_in_active_crawl ? 'Yes' : 'No'}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              {renderBadge(gscLabel(item.gsc_signal_status), gscTone(item.gsc_signal_status))}
                            </td>
                            <td className="px-3 py-3 text-sm text-stone-700 dark:text-slate-300">
                              {formatDateTime(item.implemented_at)}
                            </td>
                            <td className="px-3 py-3 text-sm">
                              <button
                                type="button"
                                className={actionClass}
                                onClick={() => updateSearch({ brief_id: item.brief_id })}
                              >
                                Open
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                {briefQuery.isLoading ? (
                  <LoadingState label="Loading implemented brief details" />
                ) : briefQuery.isError ? (
                  <RetriableErrorState
                    title="Could not load implemented brief details"
                    message={getUiErrorMessage(briefQuery.error, t)}
                    onRetry={() => void briefQuery.refetch()}
                  />
                ) : briefQuery.data && effectiveImplementedItem ? (
                  <section className={sectionClass}>
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div>
                        <h2 className="text-base font-semibold text-stone-900 dark:text-slate-50">
                          Implemented brief #{briefQuery.data.id}
                        </h2>
                        <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">
                          {briefQuery.data.primary_keyword}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {renderBadge(
                          `Execution: ${briefStateLabel(briefQuery.data.execution_status)}`,
                          briefStateTone(briefQuery.data.execution_status),
                        )}
                        {renderBadge(
                          `Implemented: ${implementationLabel(effectiveImplementedItem.implementation_status)}`,
                          implementationTone(effectiveImplementedItem.implementation_status),
                        )}
                        {renderBadge(
                          `Outcome: ${outcomeLabel(effectiveImplementedItem.outcome_status)}`,
                          outcomeTone(effectiveImplementedItem.outcome_status),
                        )}
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Brief summary</p>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>Brief type</dt>
                            <dd>{briefTypeLabel(briefQuery.data.brief_type)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Recommended title</dt>
                            <dd className="max-w-[220px] truncate text-right">
                              {briefQuery.data.recommended_page_title ?? '-'}
                            </dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Slug</dt>
                            <dd>{briefQuery.data.proposed_url_slug ?? '-'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Decision</dt>
                            <dd>{briefQuery.data.decision_type_snapshot ? decisionLabel(briefQuery.data.decision_type_snapshot) : '-'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Coverage</dt>
                            <dd>{briefQuery.data.coverage_status_snapshot ? coverageLabel(briefQuery.data.coverage_status_snapshot) : '-'}</dd>
                          </div>
                        </dl>
                      </div>
                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Outcome summary</p>
                        <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                          <div className="flex items-center justify-between gap-3">
                            <dt>Active crawl</dt>
                            <dd>{implementedQuery.data.active_crawl_id ?? '-'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Window</dt>
                            <dd>{implementedQuery.data.window_days} days</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Page present</dt>
                            <dd>{effectiveImplementedItem.page_present_in_active_crawl ? 'Yes' : 'No'}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Query matches</dt>
                            <dd>{formatNumber(effectiveImplementedItem.query_match_count)}</dd>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <dt>Last checked</dt>
                            <dd>{formatDateTime(effectiveImplementedItem.last_outcome_checked_at)}</dd>
                          </div>
                        </dl>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4">
                      {renderImplementationPanel()}

                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">Matched page</p>
                        {effectiveImplementedItem.matched_page ? (
                          <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                            <div className="flex items-center justify-between gap-3">
                              <dt>URL</dt>
                              <dd className="max-w-[320px] truncate text-right">{effectiveImplementedItem.matched_page.url}</dd>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <dt>Title</dt>
                              <dd className="max-w-[320px] truncate text-right">{effectiveImplementedItem.matched_page.title ?? '-'}</dd>
                            </div>
                          </dl>
                        ) : (
                          <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                            No matched page is present in the current active crawl.
                          </p>
                        )}
                      </div>

                      <div className={panelClass}>
                        <p className="text-sm font-semibold text-stone-900 dark:text-slate-50">GSC summary</p>
                        {effectiveImplementedItem.gsc_summary ? (
                          <dl className="mt-3 grid gap-2 text-sm text-stone-700 dark:text-slate-300">
                            <div className="flex items-center justify-between gap-3">
                              <dt>Clicks</dt>
                              <dd>{formatNumber(effectiveImplementedItem.gsc_summary.clicks)}</dd>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <dt>Impressions</dt>
                              <dd>{formatNumber(effectiveImplementedItem.gsc_summary.impressions)}</dd>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <dt>CTR</dt>
                              <dd>{formatPercent(effectiveImplementedItem.gsc_summary.ctr)}</dd>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <dt>Average position</dt>
                              <dd>{formatNumber(effectiveImplementedItem.gsc_summary.avg_position)}</dd>
                            </div>
                          </dl>
                        ) : (
                          <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">
                            No GSC summary is available for this implemented brief yet.
                          </p>
                        )}
                      </div>
                    </div>
                  </section>
                ) : (
                  <EmptyState
                    title="Select an implemented brief"
                    description="Pick one tracked item from the list to inspect the lightweight outcome summary over the active crawl and available GSC context."
                  />
                )}
              </div>
            )}
          </>
        ) : null}
      </>
    )
  }

  return (
    <div className="space-y-6">
      <section className={surfaceClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700 dark:text-teal-300">Semstorm workflow</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-stone-950 dark:text-slate-50">
              {mode === 'discovery'
                ? 'Semstorm discovery'
                : mode === 'opportunities'
                  ? 'Semstorm opportunities'
                  : mode === 'promoted'
                    ? 'Semstorm promoted backlog'
                    : mode === 'plans'
                      ? 'Semstorm plans'
                      : mode === 'briefs'
                        ? 'Semstorm briefs'
                        : mode === 'execution'
                          ? 'Semstorm execution'
                          : 'Semstorm implemented'}
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-slate-300">
              {mode === 'discovery'
                ? 'Run and inspect persisted Semstorm discovery payloads for the current site workspace.'
                : mode === 'opportunities'
                  ? 'Review Semstorm opportunities with coverage and GSC enrichment before promoting useful seeds.'
                  : mode === 'promoted'
                    ? 'Turn promoted Semstorm seeds into a practical backlog before planning detailed execution.'
                    : mode === 'plans'
                      ? 'Manage lightweight planning items for promoted Semstorm keywords without mixing them into content recommendations or competitive gap results.'
                      : mode === 'briefs'
                        ? 'Edit deterministic execution packets that turn Semstorm plans into ready-to-use manual briefs.'
                        : mode === 'execution'
                          ? 'Track handoff and execution status for Semstorm briefs without turning the workspace into a mini Jira board.'
                          : 'Observe implemented Semstorm briefs against the active crawl and available GSC context without turning the slice into a BI dashboard.'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {mode === 'discovery' ? (
              <>
                <button
                  type="submit"
                  form="semstorm-discovery-form"
                  className={primaryActionClass}
                  disabled={createRunMutation.isPending}
                >
                  {createRunMutation.isPending ? 'Running...' : 'Run discovery'}
                </button>
                <Link to={discoveryOpportunitiesHref} className={actionClass}>
                  Open opportunities
                </Link>
              </>
            ) : mode === 'opportunities' ? (
              <>
                <Link to={discoveryHref} className={actionClass}>
                  Open discovery
                </Link>
                <Link to={promotedHref} className={actionClass}>
                  Open promoted
                </Link>
              </>
            ) : mode === 'promoted' ? (
              <>
                <Link
                  to={buildSiteCompetitiveGapSemstormOpportunitiesPath(site.id, {
                    activeCrawlId,
                    baselineCrawlId,
                  })}
                  className={actionClass}
                >
                  Open opportunities
                </Link>
                <Link to={plansHref} className={actionClass}>
                  Open plans
                </Link>
              </>
            ) : mode === 'plans' ? (
              <>
                <Link to={promotedHref} className={actionClass}>
                  Open promoted
                </Link>
                <Link to={briefsHref} className={actionClass}>
                  Open briefs
                </Link>
              </>
            ) : mode === 'briefs' ? (
              <>
                <Link to={plansHref} className={actionClass}>
                  Open plans
                </Link>
                <Link to={executionHref} className={actionClass}>
                  Open execution
                </Link>
                <Link to={implementedHref} className={actionClass}>
                  Open implemented
                </Link>
                <Link
                  to={buildSiteCompetitiveGapSemstormOpportunitiesPath(site.id, {
                    activeCrawlId,
                    baselineCrawlId,
                  })}
                  className={actionClass}
                >
                  Open opportunities
                </Link>
              </>
            ) : mode === 'execution' ? (
              <>
                <Link to={briefsHref} className={actionClass}>
                  Open briefs
                </Link>
                <Link to={implementedHref} className={actionClass}>
                  Open implemented
                </Link>
              </>
            ) : (
              <>
                <Link to={executionHref} className={actionClass}>
                  Open execution
                </Link>
                <Link to={briefsHref} className={actionClass}>
                  Open briefs
                </Link>
              </>
            )}
          </div>
        </div>
        <div className="mt-5">
          <SemstormNav
            siteId={site.id}
            activeCrawlId={activeCrawlId}
            baselineCrawlId={baselineCrawlId}
            mode={mode}
            selectedRunId={navigationRunId}
            selectedPlanId={navigationPlanId}
            selectedBriefId={navigationBriefId}
            selectedEnrichmentRunId={navigationEnrichmentRunId}
          />
        </div>
      </section>
      {body}
    </div>
  )
}

export function SiteCompetitiveGapSemstormDiscoveryPage() {
  return <SiteCompetitiveGapSemstormPage mode="discovery" />
}

export function SiteCompetitiveGapSemstormOpportunitiesPage() {
  return <SiteCompetitiveGapSemstormPage mode="opportunities" />
}

export function SiteCompetitiveGapSemstormPromotedPage() {
  return <SiteCompetitiveGapSemstormPage mode="promoted" />
}

export function SiteCompetitiveGapSemstormPlansPage() {
  return <SiteCompetitiveGapSemstormPage mode="plans" />
}

export function SiteCompetitiveGapSemstormBriefsPage() {
  return <SiteCompetitiveGapSemstormPage mode="briefs" />
}

export function SiteCompetitiveGapSemstormExecutionPage() {
  return <SiteCompetitiveGapSemstormPage mode="execution" />
}

export function SiteCompetitiveGapSemstormImplementedPage() {
  return <SiteCompetitiveGapSemstormPage mode="implemented" />
}
