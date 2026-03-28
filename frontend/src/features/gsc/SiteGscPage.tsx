import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { buildApiUrl } from '../../api/client'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import { SummaryCards } from '../../components/SummaryCards'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import type { GscDateRangeLabel, SiteGscSummary } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime } from '../../utils/format'
import {
  buildSiteGscPath,
  buildSiteGscImportPath,
  buildSiteGscSettingsPath,
  buildSiteOpportunitiesPath,
  buildSiteOverviewPath,
  buildSitePagesPath,
} from '../sites/routes'
import { useSiteWorkspaceContext } from '../sites/context'
import {
  useImportSiteGscDataMutation,
  useSelectSiteGscPropertyMutation,
  useSiteGscPropertiesQuery,
  useSiteGscSummaryQuery,
} from './api'

type SiteGscPageMode = 'overview' | 'settings' | 'import'

interface SiteGscPageProps {
  mode?: SiteGscPageMode
}

function formatRangeLabel(range: GscDateRangeLabel, t: ReturnType<typeof useTranslation>['t']) {
  return t(`sites.gsc.ranges.${range}`)
}

function buildSiteGscOauthStartHref(
  siteId: number,
  activeCrawlId: number | null,
  baselineCrawlId: number | null,
) {
  const apiParams = new URLSearchParams()
  const frontendRedirectUrl = new URL(
    buildSiteGscPath(
      siteId,
      buildWorkspaceContext(activeCrawlId, baselineCrawlId),
    ),
    globalThis.location.origin,
  )

  if (activeCrawlId) {
    frontendRedirectUrl.searchParams.set('active_crawl_id', String(activeCrawlId))
    apiParams.set('active_crawl_id', String(activeCrawlId))
  }

  apiParams.set('frontend_redirect_url', frontendRedirectUrl.toString())
  return buildApiUrl(`/sites/${siteId}/gsc/oauth/start?${apiParams.toString()}`)
}

function buildWorkspaceContext(activeCrawlId: number | null, baselineCrawlId: number | null) {
  return {
    activeCrawlId,
    baselineCrawlId,
  }
}

function resolveLatestImportAt(summary: SiteGscSummary) {
  return (
    summary.ranges
      .map((item) => item.last_imported_at)
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1) ?? null
  )
}

function getImportedRange(summary: SiteGscSummary) {
  return summary.ranges.find((item) => item.last_imported_at) ?? null
}

function SiteGscHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string
  title: string
  description: string
  children?: ReactNode
}) {
  return (
    <section className="rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-teal-700">{eyebrow}</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">{title}</h2>
          <p className="mt-2 max-w-3xl text-sm text-stone-600">{description}</p>
        </div>
        {children ? <div className="flex flex-wrap gap-2">{children}</div> : null}
      </div>
    </section>
  )
}

function SiteGscOverview({
  summary,
  siteId,
  rootUrl,
  activeCrawlId,
  baselineCrawlId,
}: {
  summary: SiteGscSummary
  siteId: number
  rootUrl: string
  activeCrawlId: number | null
  baselineCrawlId: number | null
}) {
  const { t } = useTranslation()
  const context = buildWorkspaceContext(activeCrawlId, baselineCrawlId)
  const latestImportAt = resolveLatestImportAt(summary)
  const importedRange = getImportedRange(summary)

  return (
    <div className="space-y-6">
      <SiteGscHeader
        eyebrow={t('sites.gsc.overview.eyebrow')}
        title={t('sites.gsc.overview.title')}
        description={t('sites.gsc.overview.description')}
      >
        <Link
          to={buildSiteGscSettingsPath(siteId, context)}
          className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
        >
          {t('sites.gsc.actions.openSettings')}
        </Link>
        <Link
          to={buildSiteGscImportPath(siteId, context)}
          className="inline-flex rounded-full bg-teal-700 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-teal-600"
        >
          {t('sites.gsc.actions.openImport')}
        </Link>
      </SiteGscHeader>

      <SummaryCards
        items={[
          {
            label: t('sites.gsc.cards.propertyStatus'),
            value: summary.selected_property_uri ? t('sites.gsc.status.connected') : t('sites.gsc.status.missingProperty'),
            hint: summary.selected_property_uri ?? t('sites.gsc.status.noPropertyHint'),
          },
          {
            label: t('sites.gsc.cards.activeCrawlImport'),
            value: summary.active_crawl_has_gsc_data ? t('sites.gsc.status.imported') : t('sites.gsc.status.notImported'),
            hint: summary.active_crawl_id ? t('sites.gsc.overview.cards.activeCrawlHint', { id: summary.active_crawl_id }) : t('sites.gsc.overview.cards.noActiveCrawlHint'),
          },
          {
            label: t('sites.gsc.cards.lastImport'),
            value: formatDateTime(latestImportAt),
            hint: importedRange ? formatRangeLabel(importedRange.date_range_label, t) : t('sites.gsc.status.noImportHint'),
          },
          {
            label: t('sites.gsc.cards.rootUrl'),
            value: rootUrl,
            hint: t('sites.gsc.overview.cards.rootUrlHint'),
          },
        ]}
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <section className="rounded-3xl border border-stone-300 bg-white/90 p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold text-stone-950">{t('sites.gsc.overview.integrationTitle')}</h3>
              <p className="mt-1 text-sm text-stone-600">{t('sites.gsc.overview.integrationDescription')}</p>
            </div>
            <StatusBadge status={summary.auth_connected ? 'finished' : 'pending'} />
          </div>

          <dl className="mt-4 grid gap-3 text-sm text-stone-700">
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3">
              <dt>{t('sites.gsc.overview.propertyLabel')}</dt>
              <dd className="font-medium text-stone-950">{summary.selected_property_uri ?? t('sites.gsc.status.noProperty')}</dd>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3">
              <dt>{t('sites.gsc.overview.permissionLabel')}</dt>
              <dd className="font-medium text-stone-950">{summary.selected_property_permission_level ?? '-'}</dd>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-3">
              <dt>{t('sites.gsc.overview.importStatusLabel')}</dt>
              <dd className="font-medium text-stone-950">
                {summary.active_crawl_has_gsc_data ? t('sites.gsc.status.imported') : t('sites.gsc.status.notImported')}
              </dd>
            </div>
          </dl>

          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              to={buildSiteGscSettingsPath(siteId, context)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('sites.gsc.actions.manageProperty')}
            </Link>
            <Link
              to={buildSiteGscImportPath(siteId, context)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('sites.gsc.actions.importData')}
            </Link>
          </div>
        </section>

        <section className="rounded-3xl border border-stone-300 bg-white/90 p-5 shadow-sm">
          <div>
            <h3 className="text-lg font-semibold text-stone-950">{t('sites.gsc.overview.activeCrawlTitle')}</h3>
            <p className="mt-1 text-sm text-stone-600">{t('sites.gsc.overview.activeCrawlDescription')}</p>
          </div>

          {summary.active_crawl ? (
            <div className="mt-4 space-y-3">
              <div className="rounded-3xl border border-stone-200 bg-stone-50/80 p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm font-semibold text-stone-950">#{summary.active_crawl.id}</p>
                  <StatusBadge status={summary.active_crawl.status} />
                </div>
                <p className="mt-2 text-sm text-stone-700">
                  {t('common.created')}: <span className="font-medium text-stone-950">{formatDateTime(summary.active_crawl.created_at)}</span>
                </p>
                <p className="mt-1 text-sm text-stone-700">
                  {t('common.rootUrl')}: <span className="font-medium text-stone-950">{summary.active_crawl.root_url ?? rootUrl}</span>
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  to={`/jobs/${summary.active_crawl.id}`}
                  className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                >
                  {t('sites.gsc.actions.openActiveCrawl')}
                </Link>
                <Link
                  to={`/jobs/${summary.active_crawl.id}/gsc`}
                  className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
                >
                  {t('sites.gsc.actions.openSnapshotDetails')}
                </Link>
              </div>
            </div>
          ) : (
            <div className="mt-4 rounded-3xl border border-dashed border-stone-300 bg-stone-50/70 p-4 text-sm text-stone-600">
              {t('sites.gsc.overview.noActiveCrawl')}
            </div>
          )}
        </section>
      </div>

      <SummaryCards
        items={summary.ranges.map((range) => ({
          label: formatRangeLabel(range.date_range_label, t),
          value: range.pages_with_clicks,
          hint: t('sites.gsc.overview.rangeHint', {
            importedPages: range.imported_pages,
            lastImportedAt: formatDateTime(range.last_imported_at),
          }),
        }))}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {summary.ranges.map((range) => (
          <section key={range.date_range_label} className="rounded-3xl border border-stone-300 bg-white/90 p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-stone-950">{t('sites.gsc.overview.summaryTitle', { range: formatRangeLabel(range.date_range_label, t) })}</h3>
                <p className="mt-1 text-sm text-stone-600">{t('sites.gsc.overview.summaryDescription')}</p>
              </div>
              <span className="text-xs uppercase tracking-[0.18em] text-stone-500">{formatRangeLabel(range.date_range_label, t)}</span>
            </div>
            <dl className="mt-4 grid gap-3 text-sm text-stone-700">
              <div className="flex items-center justify-between gap-3">
                <dt>{t('sites.gsc.rangeMetrics.importedPages')}</dt>
                <dd className="font-medium text-stone-950">{range.imported_pages}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>{t('sites.gsc.rangeMetrics.pagesWithImpressions')}</dt>
                <dd className="font-medium text-stone-950">{range.pages_with_impressions}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>{t('sites.gsc.rangeMetrics.pagesWithClicks')}</dt>
                <dd className="font-medium text-stone-950">{range.pages_with_clicks}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>{t('sites.gsc.rangeMetrics.opportunities')}</dt>
                <dd className="font-medium text-stone-950">{range.opportunities_with_impressions}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>{t('sites.gsc.rangeMetrics.lastImported')}</dt>
                <dd className="font-medium text-stone-950">{formatDateTime(range.last_imported_at)}</dd>
              </div>
            </dl>
          </section>
        ))}
      </div>

      <section className="rounded-3xl border border-stone-300 bg-white/90 p-5 shadow-sm">
        <div className="flex flex-col gap-2">
          <h3 className="text-lg font-semibold text-stone-950">{t('sites.gsc.overview.shortcutsTitle')}</h3>
          <p className="text-sm text-stone-600">{t('sites.gsc.overview.shortcutsDescription')}</p>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            to={buildSiteGscSettingsPath(siteId, context)}
            className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('sites.gsc.actions.openSettings')}
          </Link>
          <Link
            to={buildSiteGscImportPath(siteId, context)}
            className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('sites.gsc.actions.openImport')}
          </Link>
          <Link
            to={buildSitePagesPath(siteId, context)}
            className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('sites.gsc.actions.openPages')}
          </Link>
          <Link
            to={buildSiteOpportunitiesPath(siteId, context)}
            className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('sites.gsc.actions.openOpportunities')}
          </Link>
          <Link
            to={buildSiteOverviewPath(siteId, context)}
            className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('sites.gsc.actions.openWorkspace')}
          </Link>
        </div>
      </section>
    </div>
  )
}

function SiteGscSettings({
  summary,
  siteId,
  rootUrl,
  activeCrawlId,
  baselineCrawlId,
  gscProperties,
  selectedPropertyUri,
  setSelectedPropertyUri,
  isSelectingProperty,
  selectPropertyError,
  onSelectProperty,
  oauthSuccess,
}: {
  summary: SiteGscSummary
  siteId: number
  rootUrl: string
  activeCrawlId: number | null
  baselineCrawlId: number | null
  gscProperties: Array<{
    property_uri: string
    matches_site: boolean
  }>
  selectedPropertyUri: string
  setSelectedPropertyUri: (value: string) => void
  isSelectingProperty: boolean
  selectPropertyError: unknown
  onSelectProperty: () => Promise<void>
  oauthSuccess: boolean
}) {
  const { t } = useTranslation()
  const context = buildWorkspaceContext(activeCrawlId, baselineCrawlId)
  const oauthHref = buildSiteGscOauthStartHref(siteId, activeCrawlId, baselineCrawlId)

  return (
    <div className="space-y-6">
      <SiteGscHeader
        eyebrow={t('sites.gsc.settings.eyebrow')}
        title={t('sites.gsc.settings.title')}
        description={t('sites.gsc.settings.description')}
      >
        {!summary.auth_connected ? (
          <a
            href={oauthHref}
            className="inline-flex rounded-full bg-teal-700 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-teal-600"
          >
            {t('gsc.connection.connect')}
          </a>
        ) : (
          <Link
            to={buildSiteGscImportPath(siteId, context)}
            className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
          >
            {t('sites.gsc.actions.openImport')}
          </Link>
        )}
      </SiteGscHeader>

      <SummaryCards
        items={[
          {
            label: t('sites.gsc.cards.propertyStatus'),
            value: summary.selected_property_uri ? t('sites.gsc.status.connected') : t('sites.gsc.status.awaitingSetup'),
            hint: summary.selected_property_uri ?? t('sites.gsc.status.noPropertyHint'),
          },
          {
            label: t('sites.gsc.cards.connectionStatus'),
            value: summary.auth_connected ? t('sites.gsc.status.oauthConnected') : t('sites.gsc.status.oauthMissing'),
            hint: t('sites.gsc.settings.connectionHint'),
          },
          {
            label: t('sites.gsc.cards.rootUrl'),
            value: rootUrl,
            hint: t('sites.gsc.settings.rootUrlHint'),
          },
        ]}
      />

      <section className="rounded-3xl border border-stone-300 bg-white/90 p-5 shadow-sm">
        <div className="flex flex-col gap-2">
          <h3 className="text-lg font-semibold text-stone-950">{t('sites.gsc.settings.connectionTitle')}</h3>
          <p className="text-sm text-stone-600">{t('sites.gsc.settings.connectionDescription')}</p>
        </div>

        {!summary.auth_connected ? (
          <div className="mt-4 rounded-3xl border border-dashed border-stone-300 bg-stone-50/70 p-4">
            <p className="text-sm text-stone-700">{t('sites.gsc.settings.connectEmpty')}</p>
            <a
              href={oauthHref}
              className="mt-4 inline-flex rounded-full bg-teal-700 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-teal-600"
            >
              {t('gsc.connection.connect')}
            </a>
          </div>
        ) : (
          <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <label className="grid gap-1 text-sm text-stone-700">
              <span>{t('sites.gsc.settings.propertyLabel')}</span>
              <select
                value={selectedPropertyUri}
                onChange={(event) => setSelectedPropertyUri(event.target.value)}
                className="min-w-[18rem] rounded-2xl border border-stone-300 bg-white px-4 py-2 text-sm text-stone-800"
              >
                {(gscProperties ?? []).map((property) => (
                  <option key={property.property_uri} value={property.property_uri}>
                    {property.matches_site ? `${property.property_uri} *` : property.property_uri}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => void onSelectProperty()}
              disabled={!selectedPropertyUri || isSelectingProperty}
              className="inline-flex rounded-full bg-teal-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSelectingProperty ? t('gsc.connection.saving') : t('sites.gsc.settings.saveProperty')}
            </button>
          </div>
        )}

        {oauthSuccess ? <p className="mt-4 text-sm text-teal-700">{t('gsc.connection.oauthSuccess')}</p> : null}
        {selectPropertyError ? (
          <div className="mt-4">
            <ErrorState title={t('gsc.errors.propertyTitle')} message={getUiErrorMessage(selectPropertyError, t)} />
          </div>
        ) : null}
      </section>

      <section className="rounded-3xl border border-teal-200 bg-teal-50/70 p-5 text-sm text-teal-950 shadow-sm">
        <h3 className="text-lg font-semibold text-teal-950">{t('sites.gsc.settings.reuseTitle')}</h3>
        <p className="mt-2">{t('sites.gsc.settings.reuseDescription')}</p>
      </section>
    </div>
  )
}

function SiteGscImport({
  summary,
  siteId,
  activeCrawlId,
  baselineCrawlId,
  topQueriesLimitInput,
  setTopQueriesLimitInput,
  selectedRange,
  setSelectedRange,
  isImporting,
  importError,
  onImportCurrentRange,
  onImportAll,
}: {
  summary: SiteGscSummary
  siteId: number
  activeCrawlId: number | null
  baselineCrawlId: number | null
  topQueriesLimitInput: string
  setTopQueriesLimitInput: (value: string) => void
  selectedRange: GscDateRangeLabel
  setSelectedRange: (value: GscDateRangeLabel) => void
  isImporting: boolean
  importError: unknown
  onImportCurrentRange: () => Promise<void>
  onImportAll: () => Promise<void>
}) {
  const { t } = useTranslation()
  const context = buildWorkspaceContext(activeCrawlId, baselineCrawlId)
  const latestImportAt = resolveLatestImportAt(summary)
  const topQueriesLimitInputId = 'site-gsc-top-queries-limit'

  return (
    <div className="space-y-6">
      <SiteGscHeader
        eyebrow={t('sites.gsc.import.eyebrow')}
        title={t('sites.gsc.import.title')}
        description={t('sites.gsc.import.description')}
      >
        <Link
          to={buildSiteGscSettingsPath(siteId, context)}
          className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
        >
          {t('sites.gsc.actions.openSettings')}
        </Link>
      </SiteGscHeader>

      <SummaryCards
        items={[
          {
            label: t('sites.gsc.cards.propertyStatus'),
            value: summary.selected_property_uri ? t('sites.gsc.status.readyToImport') : t('sites.gsc.status.missingProperty'),
            hint: summary.selected_property_uri ?? t('sites.gsc.status.noPropertyHint'),
          },
          {
            label: t('sites.gsc.cards.activeCrawl'),
            value: summary.active_crawl_id ? `#${summary.active_crawl_id}` : t('sites.gsc.status.noActiveCrawl'),
            hint: summary.active_crawl ? formatDateTime(summary.active_crawl.created_at) : t('sites.gsc.status.noActiveCrawlHint'),
          },
          {
            label: t('sites.gsc.cards.lastImport'),
            value: formatDateTime(latestImportAt),
            hint: latestImportAt ? t('sites.gsc.import.lastImportHint') : t('sites.gsc.status.noImportHint'),
          },
        ]}
      />

      {!summary.selected_property_uri ? (
        <div className="space-y-4 rounded-3xl border border-dashed border-stone-300 bg-white/70 px-6 py-10 text-center shadow-sm">
          <EmptyState title={t('sites.gsc.import.noPropertyTitle')} description={t('sites.gsc.import.noPropertyDescription')} />
          <div className="flex justify-center">
            <Link
              to={buildSiteGscSettingsPath(siteId, context)}
              className="inline-flex rounded-full bg-teal-700 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-teal-600"
            >
              {t('sites.gsc.actions.openSettings')}
            </Link>
          </div>
        </div>
      ) : !summary.active_crawl ? (
        <div className="space-y-4 rounded-3xl border border-dashed border-stone-300 bg-white/70 px-6 py-10 text-center shadow-sm">
          <EmptyState title={t('sites.gsc.noActiveCrawlTitle')} description={t('sites.gsc.noActiveCrawlDescription')} />
          <div className="flex justify-center">
            <Link
              to={buildSiteOverviewPath(siteId, context)}
              className="inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100"
            >
              {t('sites.gsc.actions.openWorkspace')}
            </Link>
          </div>
        </div>
      ) : (
        <>
          <section className="rounded-3xl border border-stone-300 bg-white/90 p-5 shadow-sm">
            <div className="flex flex-col gap-2">
              <h3 className="text-lg font-semibold text-stone-950">{t('sites.gsc.import.activeCrawlTitle')}</h3>
              <p className="text-sm text-stone-600">{t('sites.gsc.import.activeCrawlDescription')}</p>
            </div>

            <div className="mt-4 rounded-3xl border border-stone-200 bg-stone-50/80 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-sm font-semibold text-stone-950">#{summary.active_crawl.id}</p>
                <StatusBadge status={summary.active_crawl.status} />
              </div>
              <p className="mt-2 text-sm text-stone-700">
                {t('common.created')}: <span className="font-medium text-stone-950">{formatDateTime(summary.active_crawl.created_at)}</span>
              </p>
              <p className="mt-1 text-sm text-stone-700">
                {t('sites.gsc.import.importStatusLabel')}:{' '}
                <span className="font-medium text-stone-950">
                  {summary.active_crawl_has_gsc_data ? t('sites.gsc.status.imported') : t('sites.gsc.status.notImported')}
                </span>
              </p>
            </div>

            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto] xl:items-end">
              <label className="grid gap-1 text-sm text-stone-700">
                <span>{t('sites.gsc.import.importRange')}</span>
                <select
                  value={selectedRange}
                  onChange={(event) => setSelectedRange(event.target.value as GscDateRangeLabel)}
                  className="rounded-2xl border border-stone-300 bg-white px-4 py-2 text-sm text-stone-800"
                >
                  {summary.available_date_ranges.map((range) => (
                    <option key={range} value={range}>
                      {formatRangeLabel(range, t)}
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-1 text-sm text-stone-700">
                <span>{t('gsc.connection.topQueriesLimit')}</span>
                <input
                  id={topQueriesLimitInputId}
                  type="number"
                  min={1}
                  step={1}
                  value={topQueriesLimitInput}
                  onChange={(event) => setTopQueriesLimitInput(event.target.value)}
                  placeholder="20"
                  aria-label={t('gsc.connection.topQueriesLimit')}
                  className="rounded-2xl border border-stone-300 bg-white px-4 py-2 text-sm text-stone-800"
                />
              </label>

              <button
                type="button"
                onClick={() => void onImportCurrentRange()}
                disabled={isImporting}
                className="inline-flex rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isImporting ? t('gsc.connection.importing') : t('sites.gsc.import.importCurrentRange')}
              </button>
              <button
                type="button"
                onClick={() => void onImportAll()}
                disabled={isImporting}
                className="inline-flex rounded-full bg-teal-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isImporting ? t('gsc.connection.importing') : t('sites.gsc.import.importAll')}
              </button>
            </div>

            <p className="mt-4 text-xs text-stone-600">{t('gsc.connection.topQueriesLimitHint')}</p>
            {importError ? (
              <div className="mt-4">
                <ErrorState title={t('gsc.errors.importTitle')} message={getUiErrorMessage(importError, t)} />
              </div>
            ) : null}
          </section>

          <div className="grid gap-4 lg:grid-cols-2">
            {summary.ranges.map((range) => (
              <section key={range.date_range_label} className="rounded-3xl border border-stone-300 bg-white/90 p-5 shadow-sm">
                <h3 className="text-lg font-semibold text-stone-950">{t('sites.gsc.import.rangeSummaryTitle', { range: formatRangeLabel(range.date_range_label, t) })}</h3>
                <dl className="mt-4 grid gap-3 text-sm text-stone-700">
                  <div className="flex items-center justify-between gap-3">
                    <dt>{t('sites.gsc.rangeMetrics.importedPages')}</dt>
                    <dd className="font-medium text-stone-950">{range.imported_pages}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt>{t('sites.gsc.rangeMetrics.pagesWithTopQueries')}</dt>
                    <dd className="font-medium text-stone-950">{range.pages_with_top_queries}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt>{t('sites.gsc.rangeMetrics.topQueries')}</dt>
                    <dd className="font-medium text-stone-950">{range.total_top_queries}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt>{t('sites.gsc.rangeMetrics.lastImported')}</dt>
                    <dd className="font-medium text-stone-950">{formatDateTime(range.last_imported_at)}</dd>
                  </div>
                </dl>
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export function SiteGscPage({ mode = 'overview' }: SiteGscPageProps) {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const [selectedPropertyUri, setSelectedPropertyUri] = useState('')
  const [topQueriesLimitInput, setTopQueriesLimitInput] = useState('')
  const [selectedRange, setSelectedRange] = useState<GscDateRangeLabel>('last_28_days')

  const documentTitleKey = {
    overview: 'documentTitle.siteGsc',
    settings: 'documentTitle.siteGscSettings',
    import: 'documentTitle.siteGscImport',
  }[mode]

  useDocumentTitle(t(documentTitleKey, { domain: site.domain }))

  const gscSummaryQuery = useSiteGscSummaryQuery(site.id, {
    active_crawl_id: activeCrawlId ?? undefined,
  })
  const gscPropertiesQuery = useSiteGscPropertiesQuery(site.id, gscSummaryQuery.data?.auth_connected === true)
  const selectPropertyMutation = useSelectSiteGscPropertyMutation(site.id)
  const importMutation = useImportSiteGscDataMutation(site.id, activeCrawlId)

  useEffect(() => {
    if (!gscPropertiesQuery.data || gscPropertiesQuery.data.length === 0) {
      return
    }

    const selected = gscPropertiesQuery.data.find((item) => item.is_selected) ?? gscPropertiesQuery.data[0]
    setSelectedPropertyUri(selected.property_uri)
  }, [gscPropertiesQuery.data])

  const availableRanges = gscSummaryQuery.data?.available_date_ranges ?? ['last_28_days']

  useEffect(() => {
    if (!availableRanges.includes(selectedRange)) {
      setSelectedRange(availableRanges[0] ?? 'last_28_days')
    }
  }, [availableRanges, selectedRange])

  const resolvedTopQueriesLimit = useMemo(() => {
    const raw = topQueriesLimitInput.trim()
    if (!raw) {
      return undefined
    }

    const parsed = Number(raw)
    if (!Number.isInteger(parsed) || parsed < 1) {
      return undefined
    }

    return parsed
  }, [topQueriesLimitInput])

  async function handleSelectProperty() {
    if (!selectedPropertyUri) {
      return
    }
    await selectPropertyMutation.mutateAsync(selectedPropertyUri)
  }

  async function handleImportCurrentRange() {
    await importMutation.mutateAsync({
      date_ranges: [selectedRange],
      top_queries_limit: resolvedTopQueriesLimit,
    })
  }

  async function handleImportAll() {
    await importMutation.mutateAsync({
      date_ranges: ['last_28_days', 'last_90_days'],
      top_queries_limit: resolvedTopQueriesLimit,
    })
  }

  if (gscSummaryQuery.isLoading) {
    return <LoadingState label={t('sites.gsc.loading')} />
  }

  if (gscSummaryQuery.isError) {
    return <ErrorState title={t('sites.gsc.errorTitle')} message={getUiErrorMessage(gscSummaryQuery.error, t)} />
  }

  const summary = gscSummaryQuery.data
  if (!summary) {
    return <EmptyState title={t('sites.gsc.emptyTitle')} description={t('sites.gsc.emptyDescription')} />
  }

  if (mode === 'settings') {
    return (
      <SiteGscSettings
        summary={summary}
        siteId={site.id}
        rootUrl={site.root_url}
        activeCrawlId={activeCrawlId}
        baselineCrawlId={baselineCrawlId}
        gscProperties={gscPropertiesQuery.data ?? []}
        selectedPropertyUri={selectedPropertyUri}
        setSelectedPropertyUri={setSelectedPropertyUri}
        isSelectingProperty={selectPropertyMutation.isPending}
        selectPropertyError={selectPropertyMutation.error}
        onSelectProperty={handleSelectProperty}
        oauthSuccess={searchParams.get('oauth') === 'success'}
      />
    )
  }

  if (mode === 'import') {
    return (
      <SiteGscImport
        summary={summary}
        siteId={site.id}
        activeCrawlId={activeCrawlId}
        baselineCrawlId={baselineCrawlId}
        topQueriesLimitInput={topQueriesLimitInput}
        setTopQueriesLimitInput={setTopQueriesLimitInput}
        selectedRange={selectedRange}
        setSelectedRange={setSelectedRange}
        isImporting={importMutation.isPending}
        importError={importMutation.error}
        onImportCurrentRange={handleImportCurrentRange}
        onImportAll={handleImportAll}
      />
    )
  }

  return (
    <SiteGscOverview
      summary={summary}
      siteId={site.id}
      rootUrl={site.root_url}
      activeCrawlId={activeCrawlId}
      baselineCrawlId={baselineCrawlId}
    />
  )
}
