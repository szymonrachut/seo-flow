import type { ChangeEvent, ReactNode } from 'react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { StatusBadge } from '../components/StatusBadge'
import { buildSitesNewPath } from '../features/sites/routes'
import type { SiteDetail, SiteListItem } from '../types/api'
import { formatDateTime } from '../utils/format'
import type { AppShellMenuItem } from './appShell'

interface AppSidebarProps {
  sites: SiteListItem[]
  sitesLoading: boolean
  sitesError: boolean
  siteMenuItems: AppShellMenuItem[]
  globalMenuItems: AppShellMenuItem[]
  selectedSite: SiteDetail | null
  selectedSiteId: number | null
}

const activeMenuClass =
  'border-stone-950 bg-stone-950 text-white shadow-sm dark:border-teal-400 dark:bg-teal-400 dark:text-slate-950'
const inactiveMenuClass =
  'border-stone-200 bg-white/80 text-stone-700 hover:border-stone-400 hover:bg-stone-100 dark:border-slate-800 dark:bg-slate-950/70 dark:text-slate-200 dark:hover:border-slate-700 dark:hover:bg-slate-900'
const disabledMenuClass =
  'border-stone-200 bg-stone-100/80 text-stone-400 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-500'

export function AppSidebar({
  sites,
  sitesLoading,
  sitesError,
  siteMenuItems,
  globalMenuItems,
  selectedSite,
  selectedSiteId,
}: AppSidebarProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [siteSearch, setSiteSearch] = useState('')

  const filteredSites = sites.filter((site) => {
    const needle = siteSearch.trim().toLowerCase()
    if (!needle) {
      return true
    }

    return `${site.domain} ${site.root_url}`.toLowerCase().includes(needle)
  })

  function handleSiteSwitch(event: ChangeEvent<HTMLSelectElement>) {
    const siteId = Number(event.target.value)
    const targetSite = sites.find((site) => site.id === siteId)
    if (!targetSite) {
      return
    }

    const activeCrawlId = targetSite.latest_crawl?.id
    const suffix = activeCrawlId ? `?active_crawl_id=${activeCrawlId}` : ''
    navigate(`/sites/${siteId}${suffix}`)
  }

  return (
    <aside className="w-full md:w-[320px] md:flex-none">
      <div className="flex h-full flex-col gap-6 rounded-[32px] border border-stone-300 bg-white/82 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/78">
        <div className="space-y-4">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700 dark:text-teal-300">{t('shell.sidebar.eyebrow')}</p>
            <p className="mt-2 text-lg font-semibold text-stone-950 dark:text-slate-50">{t('shell.sidebar.title')}</p>
          </div>

          <div className="space-y-3 rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
            <label className="grid gap-1 text-sm text-stone-700 dark:text-slate-200">
              <span>{t('shell.sidebar.siteSearch')}</span>
              <input
                type="search"
                value={siteSearch}
                onChange={(event) => setSiteSearch(event.target.value)}
                placeholder={t('shell.sidebar.siteSearchPlaceholder')}
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-teal-400 dark:focus:ring-teal-500/30"
              />
            </label>

            <label className="grid gap-1 text-sm text-stone-700 dark:text-slate-200">
              <span>{t('shell.sidebar.siteSwitcher')}</span>
              <select
                value={selectedSiteId ? String(selectedSiteId) : ''}
                onChange={handleSiteSwitch}
                className="rounded-2xl border border-stone-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-teal-400 dark:focus:ring-teal-500/30"
                disabled={sitesLoading || filteredSites.length === 0}
              >
                <option value="">{t('shell.sidebar.siteSwitcherPlaceholder')}</option>
                {filteredSites.map((site) => (
                  <option key={site.id} value={site.id}>
                    {site.domain}
                  </option>
                ))}
              </select>
            </label>

            <Link
              to={buildSitesNewPath()}
              className="inline-flex w-full items-center justify-center rounded-full bg-stone-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-stone-800 dark:bg-teal-400 dark:text-slate-950 dark:hover:bg-teal-300"
            >
              {t('shell.sidebar.addSite')}
            </Link>

            {sitesError ? <p className="text-sm text-rose-700 dark:text-rose-300">{t('shell.sidebar.sitesError')}</p> : null}
            {!sitesLoading && !sitesError && filteredSites.length === 0 ? (
              <p className="text-sm text-stone-500 dark:text-slate-400">{t('shell.sidebar.noSites')}</p>
            ) : null}
          </div>
        </div>

        <div className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
            {t('shell.sidebar.currentSite')}
          </p>

          {selectedSite ? (
            <div className="space-y-3 rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
              <div>
                <p className="text-lg font-semibold text-stone-950 dark:text-slate-50">{selectedSite.domain}</p>
                <p className="mt-1 break-all text-sm text-stone-600 dark:text-slate-300">{selectedSite.root_url}</p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {selectedSite.active_crawl ? (
                  <>
                    <StatusBadge status={selectedSite.active_crawl.status} />
                    <span className="text-xs text-stone-500 dark:text-slate-400">
                      {t('shell.site.activeCrawlLabel', { id: selectedSite.active_crawl.id })}
                    </span>
                  </>
                ) : (
                  <span className="rounded-full border border-stone-200 px-2.5 py-1 text-xs font-medium text-stone-600 dark:border-slate-700 dark:text-slate-300">
                    {t('shell.site.noActiveCrawl')}
                  </span>
                )}
              </div>

              <div className="grid gap-2 text-sm text-stone-600 dark:text-slate-300">
                {selectedSite.summary.last_crawl_at ? (
                  <p>
                    {t('shell.site.lastCrawl')}: <span className="font-medium text-stone-900 dark:text-slate-100">{formatDateTime(selectedSite.summary.last_crawl_at)}</span>
                  </p>
                ) : null}
                <p>
                  {t('shell.site.gsc')}: <span className="font-medium text-stone-900 dark:text-slate-100">
                    {selectedSite.selected_gsc_property_uri ? t('shell.site.gscConnected') : t('shell.site.gscNotConnected')}
                  </span>
                </p>
              </div>
            </div>
          ) : (
            <div className="rounded-3xl border border-dashed border-stone-300 bg-stone-50/70 p-4 text-sm text-stone-600 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-300">
              {t('shell.site.empty')}
            </div>
          )}
        </div>

        <nav className="space-y-2" aria-label={t('shell.sidebar.siteNavigation')}>
          {selectedSite ? siteMenuItems.map((item) => <SidebarMenuItem key={item.key} item={item} />) : null}
        </nav>

        <div className="mt-auto space-y-3 border-t border-stone-200 pt-4 dark:border-slate-800">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">
            {t('shell.sidebar.global')}
          </p>
          <nav className="space-y-2" aria-label={t('shell.sidebar.globalNavigation')}>
            {globalMenuItems.map((item) => (
              <SidebarMenuItem key={item.key} item={item} compact />
            ))}
          </nav>
        </div>
      </div>
    </aside>
  )
}

interface SidebarMenuItemProps {
  item: AppShellMenuItem
  compact?: boolean
}

function SidebarMenuItem({ item, compact = false }: SidebarMenuItemProps) {
  const baseClass = `flex w-full items-center justify-between rounded-2xl border px-3 py-2.5 text-left text-sm font-medium transition ${
    item.disabled ? disabledMenuClass : item.active ? activeMenuClass : inactiveMenuClass
  } ${compact ? 'py-2' : ''}`

  return (
    <div className="space-y-2">
      {item.to && !item.disabled ? (
        <Link to={item.to} className={baseClass}>
          <span>{item.label}</span>
          {item.badge ? <MenuBadge active={item.active}>{item.badge}</MenuBadge> : null}
        </Link>
      ) : (
        <div className={baseClass} aria-disabled={item.disabled}>
          <span>{item.label}</span>
          {item.badge ? <MenuBadge active={item.active}>{item.badge}</MenuBadge> : null}
        </div>
      )}

      {item.active && item.subItems?.length ? (
        <div className="ml-2 space-y-2 border-l border-stone-200 pl-4 dark:border-slate-800">
          {item.subItems.map((subItem) =>
            subItem.to && !subItem.disabled ? (
              <Link
                key={`${item.key}-${subItem.label}`}
                to={subItem.to}
                className={`flex items-center justify-between rounded-2xl px-3 py-2 text-sm transition ${
                  subItem.active
                    ? 'bg-stone-950 text-white dark:bg-teal-400 dark:text-slate-950'
                    : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900 dark:text-slate-300 dark:hover:bg-slate-900 dark:hover:text-slate-100'
                }`}
              >
                <span>{subItem.label}</span>
                {subItem.badge ? <MenuBadge active={subItem.active}>{subItem.badge}</MenuBadge> : null}
              </Link>
            ) : (
              <div
                key={`${item.key}-${subItem.label}`}
                className="flex items-center justify-between rounded-2xl bg-stone-100/80 px-3 py-2 text-sm text-stone-400 dark:bg-slate-900/50 dark:text-slate-500"
                aria-disabled={subItem.disabled}
              >
                <span>{subItem.label}</span>
                {subItem.badge ? <MenuBadge active={subItem.active}>{subItem.badge}</MenuBadge> : null}
              </div>
            ),
          )}
        </div>
      ) : null}
    </div>
  )
}

interface MenuBadgeProps {
  active: boolean
  children: ReactNode
}

function MenuBadge({ active, children }: MenuBadgeProps) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] ${
        active
          ? 'bg-white/15 text-current dark:bg-slate-950/20'
          : 'bg-stone-200 text-stone-600 dark:bg-slate-800 dark:text-slate-300'
      }`}
    >
      {children}
    </span>
  )
}
