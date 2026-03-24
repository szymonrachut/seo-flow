import { type ReactNode, startTransition, useEffect } from 'react'
import { Link, Outlet, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ActionMenu } from '../../components/ActionMenu'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import { getUiErrorMessage } from '../../utils/errors'
import { formatCrawlDateTime, formatCrawlOptionLabel, formatDateTime } from '../../utils/format'
import { mergeSearchParams, parseIntegerParam } from '../../utils/searchParams'
import { useSiteDetailQuery } from './api'
import type { SiteWorkspaceContextValue } from './context'
import { buildSiteChangesPath, buildSiteCrawlsNewPath } from './routes'

function parseSiteId(rawValue: string | undefined): number | null {
  if (!rawValue) {
    return null
  }

  const parsed = Number(rawValue)
  return Number.isInteger(parsed) ? parsed : null
}

export function SiteWorkspaceLayout() {
  const { t } = useTranslation()
  const params = useParams()
  const siteId = parseSiteId(params.siteId)

  if (siteId === null) {
    return <ErrorState title={t('sites.invalidIdTitle')} message={t('sites.invalidIdMessage')} />
  }

  const [searchParams, setSearchParams] = useSearchParams()
  const requestedActiveCrawlId = parseIntegerParam(searchParams.get('active_crawl_id'), undefined)
  const requestedBaselineCrawlId = parseIntegerParam(searchParams.get('baseline_crawl_id'), undefined)
  const siteQuery = useSiteDetailQuery(siteId, {
    active_crawl_id: requestedActiveCrawlId,
    baseline_crawl_id: requestedBaselineCrawlId,
  })

  useEffect(() => {
    if (!siteQuery.data) {
      return
    }

    const resolvedActiveCrawlId = siteQuery.data.active_crawl_id ?? undefined
    const resolvedBaselineCrawlId = siteQuery.data.baseline_crawl_id ?? undefined
    if (
      requestedActiveCrawlId === resolvedActiveCrawlId &&
      requestedBaselineCrawlId === resolvedBaselineCrawlId
    ) {
      return
    }

    const next = mergeSearchParams(searchParams, {
      active_crawl_id: resolvedActiveCrawlId,
      baseline_crawl_id: resolvedBaselineCrawlId,
    })
    startTransition(() => setSearchParams(next, { replace: true }))
  }, [requestedActiveCrawlId, requestedBaselineCrawlId, searchParams, setSearchParams, siteQuery.data])

  if (siteQuery.isLoading) {
    return <LoadingState label={t('sites.workspace.loading')} />
  }

  if (siteQuery.isError) {
    return <ErrorState title={t('sites.workspace.errorTitle')} message={getUiErrorMessage(siteQuery.error, t)} />
  }

  const site = siteQuery.data
  if (!site) {
    return <EmptyState title={t('sites.workspace.emptyTitle')} description={t('sites.workspace.emptyDescription')} />
  }

  const workspaceSite = site

  function updateCrawlContext(updates: { active_crawl_id?: number; baseline_crawl_id?: number }) {
    const nextActiveCrawlId = updates.active_crawl_id ?? workspaceSite.active_crawl_id ?? undefined
    const nextBaselineCrawlId =
      updates.baseline_crawl_id !== undefined
        ? updates.baseline_crawl_id
        : workspaceSite.baseline_crawl_id ?? undefined
    const normalizedUpdates = {
      ...updates,
      baseline_crawl_id:
        nextActiveCrawlId && nextBaselineCrawlId && nextActiveCrawlId === nextBaselineCrawlId
          ? undefined
          : updates.baseline_crawl_id,
    }
    const next = mergeSearchParams(searchParams, normalizedUpdates)
    startTransition(() => setSearchParams(next))
  }

  const routeContext: SiteWorkspaceContextValue = {
    site: workspaceSite,
    activeCrawlId: workspaceSite.active_crawl_id,
    baselineCrawlId: workspaceSite.baseline_crawl_id,
    updateCrawlContext,
  }

  const newCrawlPath = buildSiteCrawlsNewPath(workspaceSite.id, {
    activeCrawlId: workspaceSite.active_crawl_id,
    baselineCrawlId: workspaceSite.baseline_crawl_id,
  })
  const changesPath = buildSiteChangesPath(workspaceSite.id, {
    activeCrawlId: workspaceSite.active_crawl_id,
    baselineCrawlId: workspaceSite.baseline_crawl_id,
  })

  const activeCrawlLabel = workspaceSite.active_crawl
    ? formatCrawlDateTime(workspaceSite.active_crawl)
    : t('sites.workspace.noActiveCrawl')
  const shellOperations = [
    {
      key: 'changes',
      label: t('sites.workspace.openChanges'),
      to: changesPath,
    },
    ...(workspaceSite.active_crawl_id
      ? [
          {
            key: 'active-crawl',
            label: t('sites.workspace.openActiveCrawl'),
            to: `/jobs/${workspaceSite.active_crawl_id}`,
          },
        ]
      : []),
  ]

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-stone-300 bg-white/88 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700 dark:text-teal-300">
              {t('sites.workspace.eyebrow')}
            </p>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-stone-950 dark:text-slate-50">{workspaceSite.domain}</h1>
              <p className="mt-2 break-all text-sm text-stone-600 dark:text-slate-300">
                {t('common.rootUrl')}: <span className="font-medium text-stone-900 dark:text-slate-100">{workspaceSite.root_url}</span>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={newCrawlPath}
              className="inline-flex rounded-full bg-stone-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-stone-800 dark:bg-teal-400 dark:text-slate-950 dark:hover:bg-teal-300"
            >
              {t('nav.newCrawl')}
            </Link>
            <ActionMenu label={t('common.operations')} items={shellOperations} />
          </div>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <ContextCard
            label={t('sites.workspace.activeCrawl')}
            value={activeCrawlLabel}
            detail={t('sites.workspace.activeCrawlHint')}
          >
            {workspaceSite.active_crawl ? <StatusBadge status={workspaceSite.active_crawl.status} /> : null}
          </ContextCard>
          <ContextCard
            label={t('sites.workspace.gscStatus')}
            value={workspaceSite.selected_gsc_property_uri ? t('sites.workspace.gscConnected') : t('sites.workspace.gscNotConnected')}
            detail={workspaceSite.selected_gsc_property_uri ?? t('sites.workspace.gscNotConnectedHint')}
          />
        </div>

        <div className="mt-5 grid gap-4 lg:max-w-xl">
          <label className="grid gap-1 text-sm text-stone-700 dark:text-slate-200">
            <span>{t('sites.workspace.activeCrawl')}</span>
            <select
              value={String(workspaceSite.active_crawl_id ?? '')}
              onChange={(event) => updateCrawlContext({ active_crawl_id: parseIntegerParam(event.target.value, undefined) })}
              className="rounded-2xl border border-stone-300 bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-teal-400 dark:focus:ring-teal-500/30"
              disabled={workspaceSite.crawl_history.length === 0}
            >
              {workspaceSite.crawl_history.length === 0 ? <option value="">{t('sites.workspace.noActiveCrawl')}</option> : null}
              {workspaceSite.crawl_history.map((crawl) => (
                <option key={crawl.id} value={crawl.id}>
                  {formatCrawlOptionLabel(crawl, workspaceSite.root_url)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-5 flex flex-wrap gap-3 text-sm text-stone-600 dark:text-slate-300">
          {workspaceSite.summary.last_crawl_at ? (
            <span>
              {t('sites.workspace.lastCrawl')}:{' '}
              <span className="font-medium text-stone-900 dark:text-slate-100">
                {formatDateTime(workspaceSite.summary.last_crawl_at)}
              </span>
            </span>
          ) : null}
          {workspaceSite.selected_gsc_property_uri ? (
            <span>
              {t('sites.workspace.gscProperty')}:{' '}
              <span className="font-medium text-stone-900 dark:text-slate-100">{workspaceSite.selected_gsc_property_uri}</span>
            </span>
          ) : null}
          <span>
            {t('sites.workspace.changesHelper')}{' '}
            <Link
              to={changesPath}
              className="font-medium text-teal-700 underline decoration-teal-300 underline-offset-4 transition hover:text-teal-800 dark:text-teal-300 dark:decoration-teal-700 dark:hover:text-teal-200"
            >
              {t('sites.workspace.openChanges')}
            </Link>
          </span>
        </div>
      </section>

      <Outlet context={routeContext} />
    </div>
  )
}

interface ContextCardProps {
  label: string
  value: string
  detail?: string
  children?: ReactNode
}

function ContextCard({ label, value, detail, children }: ContextCardProps) {
  return (
    <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">{label}</p>
          <p className="mt-2 text-sm font-semibold text-stone-950 dark:text-slate-100">{value}</p>
          {detail ? <p className="mt-1 text-sm text-stone-600 dark:text-slate-300">{detail}</p> : null}
        </div>
        {children}
      </div>
    </div>
  )
}
