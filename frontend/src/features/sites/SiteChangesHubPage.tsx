import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { EmptyState } from '../../components/EmptyState'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { formatCrawlDateTime } from '../../utils/format'
import { useSiteAuditCompareQuery } from '../audit/api'
import { useSiteInternalLinkingCompareQuery } from '../internal-linking/api'
import { useSiteOpportunitiesCompareQuery } from '../opportunities/api'
import { useSitePagesCompareQuery } from '../pages/api'
import { useSiteWorkspaceContext } from './context'
import {
  buildSiteChangesAuditPath,
  buildSiteChangesInternalLinkingPath,
  buildSiteChangesOpportunitiesPath,
  buildSiteChangesPagesPath,
} from './routes'

const defaultGscDateRange = 'last_28_days' as const

interface CompareSummaryMetric {
  label: string
  value: number
}

interface CompareEntryCard {
  key: string
  title: string
  description: string
  to: string
  status: 'ready' | 'loading' | 'error' | 'waiting'
  metrics: CompareSummaryMetric[]
}

function renderStatusBadge(
  label: string,
  tone: 'stone' | 'teal' | 'amber' | 'rose' = 'stone',
) {
  const toneClass =
    tone === 'teal'
      ? 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/60 dark:text-teal-200'
      : tone === 'amber'
        ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200'
        : tone === 'rose'
          ? 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/60 dark:text-rose-200'
          : 'border-stone-300 bg-stone-100 text-stone-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'

  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] ${toneClass}`}>{label}</span>
}

function cardStatusTone(status: CompareEntryCard['status']) {
  if (status === 'ready') {
    return 'teal' as const
  }
  if (status === 'loading' || status === 'waiting') {
    return 'amber' as const
  }
  if (status === 'error') {
    return 'rose' as const
  }
  return 'stone' as const
}

function CompareEntryCardView({ card }: { card: CompareEntryCard }) {
  const { t } = useTranslation()
  const isDisabled = card.status !== 'ready'
  const content = (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-teal-700 dark:text-teal-300">
            {t('sites.changes.card.eyebrow')}
          </p>
          <h2 className="mt-2 text-lg font-semibold text-stone-950 dark:text-slate-50">{card.title}</h2>
        </div>
        {renderStatusBadge(t(`sites.changes.card.status.${card.status}`), cardStatusTone(card.status))}
      </div>

      <p className="mt-3 text-sm text-stone-600 dark:text-slate-300">{card.description}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {card.metrics.length > 0 ? (
          card.metrics.map((metric) => (
            <span
              key={`${card.key}-${metric.label}`}
              className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs text-stone-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            >
              <span className="font-semibold text-stone-950 dark:text-slate-50">{metric.value}</span> {metric.label}
            </span>
          ))
        ) : (
          <span className="rounded-full border border-dashed border-stone-300 px-3 py-1 text-xs text-stone-500 dark:border-slate-700 dark:text-slate-400">
            {t('sites.changes.card.noSummary')}
          </span>
        )}
      </div>

      <p className="mt-4 text-sm font-medium text-teal-700 dark:text-teal-300">
        {isDisabled ? t('sites.changes.card.notReady') : t('sites.changes.card.open')}
      </p>
    </>
  )

  const className = `rounded-[28px] border border-stone-300 bg-white/90 p-5 shadow-sm transition dark:border-slate-800 dark:bg-slate-950/85 ${
    isDisabled
      ? 'cursor-default'
      : 'hover:border-stone-400 hover:bg-white dark:hover:border-slate-700 dark:hover:bg-slate-950'
  }`

  if (isDisabled) {
    return <div className={className}>{content}</div>
  }

  return (
    <Link to={card.to} className={className}>
      {content}
    </Link>
  )
}

export function SiteChangesHubPage() {
  const { t } = useTranslation()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()

  useDocumentTitle(t('documentTitle.siteChanges', { domain: site.domain }))

  const compareContext = useMemo(
    () => ({
      active_crawl_id: activeCrawlId ?? undefined,
      baseline_crawl_id: baselineCrawlId ?? undefined,
    }),
    [activeCrawlId, baselineCrawlId],
  )
  const compareContextReady = Boolean(compareContext.active_crawl_id && compareContext.baseline_crawl_id)

  const pagesCompareQuery = useSitePagesCompareQuery(
    site.id,
    {
      ...compareContext,
      gsc_date_range: defaultGscDateRange,
      page: 1,
      page_size: 1,
      sort_by: 'change_type',
      sort_order: 'desc',
    },
    compareContextReady,
  )
  const auditCompareQuery = useSiteAuditCompareQuery(site.id, compareContext, compareContextReady)
  const opportunitiesCompareQuery = useSiteOpportunitiesCompareQuery(
    site.id,
    {
      ...compareContext,
      gsc_date_range: defaultGscDateRange,
      page: 1,
      page_size: 1,
      sort_by: 'delta_priority_score',
      sort_order: 'desc',
    },
    compareContextReady,
  )
  const internalLinkingCompareQuery = useSiteInternalLinkingCompareQuery(
    site.id,
    {
      ...compareContext,
      gsc_date_range: defaultGscDateRange,
      page: 1,
      page_size: 1,
      sort_by: 'delta_internal_linking_score',
      sort_order: 'desc',
    },
    compareContextReady,
  )

  const compareUnavailableReason =
    pagesCompareQuery.data && !pagesCompareQuery.data.context.compare_available
      ? pagesCompareQuery.data.context.compare_unavailable_reason ?? t('sites.changes.empty.unavailableDescription')
      : null
  const compareReady = compareContextReady && !compareUnavailableReason

  const activeCrawlLabel = site.active_crawl
    ? formatCrawlDateTime(site.active_crawl)
    : t('sites.workspace.noActiveCrawl')
  const baselineCrawlLabel = site.baseline_crawl
    ? formatCrawlDateTime(site.baseline_crawl)
    : t('sites.workspace.noBaseline')

  const summaryCards = [
    {
      label: t('sites.workspace.activeCrawl'),
      value: activeCrawlLabel,
      hint: site.active_crawl ? t(`jobs.status.${site.active_crawl.status}`) : t('sites.changes.summary.activeHint'),
    },
    {
      label: t('sites.workspace.baselineCrawl'),
      value: baselineCrawlLabel,
      hint: site.baseline_crawl ? t(`jobs.status.${site.baseline_crawl.status}`) : t('sites.changes.summary.baselineHint'),
    },
    {
      label: t('sites.workspace.changesStatus'),
      value: compareReady ? t('sites.workspace.changesReady') : t('sites.workspace.changesWaiting'),
      hint: compareUnavailableReason ?? (compareReady ? t('sites.workspace.changesReadyHint') : t('sites.workspace.changesWaitingHint')),
    },
    {
      label: t('sites.changes.summary.compareAreasLabel'),
      value: compareReady ? 4 : 0,
      hint: compareReady ? t('sites.changes.summary.compareAreasReady') : t('sites.changes.summary.compareAreasWaiting'),
    },
  ]

  const compareCards: CompareEntryCard[] = [
    {
      key: 'pages',
      title: t('sites.changes.links.pages.title'),
      description: t('sites.changes.links.pages.description'),
      to: buildSiteChangesPagesPath(site.id, { activeCrawlId, baselineCrawlId }),
      status: !compareReady
        ? 'waiting'
        : pagesCompareQuery.isLoading
          ? 'loading'
          : pagesCompareQuery.isError
            ? 'error'
            : 'ready',
      metrics:
        pagesCompareQuery.data && pagesCompareQuery.data.context.compare_available
          ? [
              { label: t('pagesCompare.summary.newUrls'), value: pagesCompareQuery.data.summary.new_urls },
              { label: t('pagesCompare.summary.missingUrls'), value: pagesCompareQuery.data.summary.missing_urls },
              { label: t('pagesCompare.summary.changedUrls'), value: pagesCompareQuery.data.summary.changed_urls },
            ]
          : [],
    },
    {
      key: 'audit',
      title: t('sites.changes.links.audit.title'),
      description: t('sites.changes.links.audit.description'),
      to: buildSiteChangesAuditPath(site.id, { activeCrawlId, baselineCrawlId }),
      status: !compareReady
        ? 'waiting'
        : auditCompareQuery.isLoading
          ? 'loading'
          : auditCompareQuery.isError
            ? 'error'
            : 'ready',
      metrics:
        auditCompareQuery.data && auditCompareQuery.data.context.compare_available
          ? [
              { label: t('auditCompare.summary.resolvedIssues'), value: auditCompareQuery.data.summary.resolved_issues_total },
              { label: t('auditCompare.summary.newIssues'), value: auditCompareQuery.data.summary.new_issues_total },
              { label: t('auditCompare.summary.worsenedSections'), value: auditCompareQuery.data.summary.worsened_sections },
            ]
          : [],
    },
    {
      key: 'opportunities',
      title: t('sites.changes.links.opportunities.title'),
      description: t('sites.changes.links.opportunities.description'),
      to: buildSiteChangesOpportunitiesPath(site.id, { activeCrawlId, baselineCrawlId }),
      status: !compareReady
        ? 'waiting'
        : opportunitiesCompareQuery.isLoading
          ? 'loading'
          : opportunitiesCompareQuery.isError
            ? 'error'
            : 'ready',
      metrics:
        opportunitiesCompareQuery.data && opportunitiesCompareQuery.data.context.compare_available
          ? [
              { label: t('opportunitiesCompare.summary.newOpportunities'), value: opportunitiesCompareQuery.data.summary.new_opportunity_urls },
              { label: t('opportunitiesCompare.summary.resolvedOpportunities'), value: opportunitiesCompareQuery.data.summary.resolved_opportunity_urls },
              { label: t('opportunitiesCompare.summary.priorityDown'), value: opportunitiesCompareQuery.data.summary.priority_down_urls },
            ]
          : [],
    },
    {
      key: 'internal-linking',
      title: t('sites.changes.links.internalLinking.title'),
      description: t('sites.changes.links.internalLinking.description'),
      to: buildSiteChangesInternalLinkingPath(site.id, { activeCrawlId, baselineCrawlId }),
      status: !compareReady
        ? 'waiting'
        : internalLinkingCompareQuery.isLoading
          ? 'loading'
          : internalLinkingCompareQuery.isError
            ? 'error'
            : 'ready',
      metrics:
        internalLinkingCompareQuery.data && internalLinkingCompareQuery.data.context.compare_available
          ? [
              { label: t('internalLinkingCompare.summary.newOrphanLike'), value: internalLinkingCompareQuery.data.summary.new_orphan_like_urls },
              { label: t('internalLinkingCompare.summary.resolvedOrphanLike'), value: internalLinkingCompareQuery.data.summary.resolved_orphan_like_urls },
              { label: t('internalLinkingCompare.summary.weaklyLinkedWorsened'), value: internalLinkingCompareQuery.data.summary.weakly_linked_worsened_urls },
            ]
          : [],
    },
  ]

  const emptyState = !activeCrawlId
    ? {
        title: t('sites.changes.empty.noActiveTitle'),
        description: t('sites.changes.empty.noActiveDescription'),
      }
    : !baselineCrawlId
      ? {
          title: t('sites.changes.empty.noBaselineTitle'),
          description: t('sites.changes.empty.noBaselineDescription'),
        }
      : compareUnavailableReason
        ? {
            title: t('sites.changes.empty.unavailableTitle'),
            description: compareUnavailableReason,
          }
        : null

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/90 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <p className="text-xs uppercase tracking-[0.22em] text-teal-700 dark:text-teal-300">
          {t('sites.changes.eyebrow')}
        </p>
        <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-stone-950 dark:text-slate-50">
              {t('sites.changes.title')}
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-slate-300">
              {t('sites.changes.description')}
            </p>
          </div>
          {renderStatusBadge(
            compareReady ? t('sites.workspace.changesReady') : t('sites.workspace.changesWaiting'),
            compareReady ? 'teal' : 'amber',
          )}
        </div>
      </section>

      <SummaryCards items={summaryCards} />

      <section className="rounded-[32px] border border-stone-300 bg-white/85 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/80">
        <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
          {t('sites.changes.contextTitle')}
        </p>
        <p className="mt-3 text-sm text-stone-700 dark:text-slate-200">
          {t('sites.changes.contextDescription', {
            active: activeCrawlId ? `#${activeCrawlId} - ${activeCrawlLabel}` : t('sites.workspace.noActiveCrawl'),
            baseline: baselineCrawlId ? `#${baselineCrawlId} - ${baselineCrawlLabel}` : t('sites.workspace.noBaseline'),
          })}
        </p>
      </section>

      {emptyState ? <EmptyState title={emptyState.title} description={emptyState.description} /> : null}

      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-stone-950 dark:text-slate-50">{t('sites.changes.compareTitle')}</h2>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{t('sites.changes.compareDescription')}</p>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {compareCards.map((card) => (
            <CompareEntryCardView key={card.key} card={card} />
          ))}
        </div>
      </section>
    </div>
  )
}
