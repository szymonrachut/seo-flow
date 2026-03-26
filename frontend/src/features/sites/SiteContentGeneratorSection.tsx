import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ErrorState } from '../../components/ErrorState'
import { EmptyState } from '../../components/EmptyState'
import { getCurrentLanguage } from '../../i18n'
import type { ContentGeneratorAssetStatus, JobStatus, SiteContentGeneratorAsset } from '../../types/api'
import { getUiErrorMessage } from '../../utils/errors'
import { formatDateTime } from '../../utils/format'
import { copyText } from '../../utils/clipboard'
import {
  useGenerateSiteContentGeneratorAssetMutation,
  useSiteContentGeneratorAssetQuery,
} from './api'

interface SiteContentGeneratorSectionProps {
  siteId: number
  activeCrawlId: number | null
  activeCrawlStatus: JobStatus | null
}

interface ContentBlockProps {
  title: string
  content: string
  compact?: boolean
}

const actionClassName =
  'inline-flex rounded-full bg-teal-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-600 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-teal-500 dark:text-slate-950 dark:hover:bg-teal-400'

const secondaryActionClassName =
  'inline-flex rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900'

export function SiteContentGeneratorSection({
  siteId,
  activeCrawlId,
  activeCrawlStatus,
}: SiteContentGeneratorSectionProps) {
  const { t } = useTranslation()
  const assetQuery = useSiteContentGeneratorAssetQuery(
    siteId,
    { active_crawl_id: activeCrawlId ?? undefined },
    true,
  )
  const generateMutation = useGenerateSiteContentGeneratorAssetMutation(siteId)
  const asset = assetQuery.data
  const [businessFailureMessage, setBusinessFailureMessage] = useState<string | null>(null)

  useEffect(() => {
    if (asset?.status !== 'failed') {
      setBusinessFailureMessage(null)
    }
  }, [asset?.generated_at, asset?.status])

  const effectiveActiveCrawlId = asset?.active_crawl_id ?? activeCrawlId
  const effectiveActiveCrawlStatus = asset?.active_crawl_status ?? activeCrawlStatus
  const isBusy = asset?.status === 'pending' || asset?.status === 'running'
  const canTriggerGeneration = Boolean(asset?.can_regenerate)
  const isActionDisabled = generateMutation.isPending || isBusy || !canTriggerGeneration

  async function handleGenerate() {
    setBusinessFailureMessage(null)

    try {
      const response = await generateMutation.mutateAsync({
        output_language: getCurrentLanguage(),
      })
      await assetQuery.refetch()

      if (!response.success) {
        setBusinessFailureMessage(
          response.error_message ?? t('sites.overview.contentGenerator.failedFallbackMessage'),
        )
      }
    } catch {
      // The mutation error is rendered from React Query state below.
    }
  }

  return (
    <section className="rounded-[32px] border border-stone-300 bg-white/90 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950/82">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">
            {t('sites.overview.contentGenerator.eyebrow')}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-stone-950 dark:text-slate-50">
            {t('sites.overview.contentGenerator.title')}
          </h2>
          <p className="mt-2 max-w-3xl text-sm text-stone-600 dark:text-slate-300">
            {t('sites.overview.contentGenerator.description')}
          </p>
        </div>

        {asset ? (
          <div className="flex flex-col items-start gap-2 xl:items-end">
            <div className="flex flex-wrap items-center gap-2">
              {asset.status ? <ContentGeneratorStatusBadge status={asset.status} /> : null}
              <button
                type="button"
                onClick={() => void handleGenerate()}
                disabled={isActionDisabled}
                className={actionClassName}
              >
                {generateMutation.isPending || isBusy
                  ? t('sites.overview.contentGenerator.actions.generating')
                  : resolveActionLabel(asset, t)}
              </button>
            </div>
            {!canTriggerGeneration ? (
              <p className="text-sm text-stone-600 dark:text-slate-300">
                {effectiveActiveCrawlId
                  ? t('sites.overview.contentGenerator.waitForFinishedCrawl', {
                      crawlId: effectiveActiveCrawlId,
                    })
                  : t('sites.overview.contentGenerator.noActiveCrawlHint')}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      {assetQuery.isLoading && !asset ? (
        <div className="mt-5">
          <BusyContentState
            title={t('sites.overview.contentGenerator.loadingTitle')}
            description={
              effectiveActiveCrawlId
                ? t('sites.overview.contentGenerator.loadingDescription', {
                    crawlId: effectiveActiveCrawlId,
                  })
                : t('sites.overview.contentGenerator.loadingWithoutCrawlDescription')
            }
          />
        </div>
      ) : null}

      {assetQuery.isError ? (
        <div className="mt-5">
          <ErrorState
            title={t('sites.overview.contentGenerator.requestErrorTitle')}
            message={getUiErrorMessage(assetQuery.error, t)}
          />
        </div>
      ) : null}

      {!assetQuery.isLoading && !assetQuery.isError && asset ? (
        <div className="mt-5 space-y-4">
          {!asset.has_assets ? (
            <div className="space-y-4">
              <EmptyState
                title={t('sites.overview.contentGenerator.emptyTitle')}
                description={
                  effectiveActiveCrawlId
                    ? t('sites.overview.contentGenerator.emptyDescription', {
                        crawlId: effectiveActiveCrawlId,
                      })
                    : t('sites.overview.contentGenerator.emptyWithoutCrawlDescription')
                }
              />
            </div>
          ) : null}

          {asset.has_assets && isBusy ? (
            <BusyContentState
              title={t('sites.overview.contentGenerator.busyTitle')}
              description={t('sites.overview.contentGenerator.busyDescription', {
                crawlId: asset.basis_crawl_job_id ?? effectiveActiveCrawlId ?? '-',
              })}
            />
          ) : null}

          {asset.has_assets && asset.status === 'failed' ? (
            <div className="space-y-4">
              <ErrorState
                title={t('sites.overview.contentGenerator.failedTitle')}
                message={
                  businessFailureMessage ??
                  asset.last_error_message ??
                  t('sites.overview.contentGenerator.failedDescription')
                }
              />
              <FailureDiagnostics asset={asset} />
            </div>
          ) : null}

          {asset.has_assets && asset.status === 'ready' ? (
            <>
              <MetadataGrid asset={asset} />
              <div className="grid gap-4 xl:grid-cols-3">
                <ContentBlock
                  title={t('sites.overview.contentGenerator.blocks.surferTitle')}
                  content={asset.surfer_custom_instructions ?? ''}
                />
                <ContentBlock
                  title={t('sites.overview.contentGenerator.blocks.seoWritingTitle')}
                  content={asset.seowriting_details_to_include ?? ''}
                />
                <ContentBlock
                  title={t('sites.overview.contentGenerator.blocks.hookTitle')}
                  content={asset.introductory_hook_brief ?? ''}
                  compact
                />
              </div>
            </>
          ) : null}

          {asset.has_assets && asset.status !== 'ready' ? <MetadataGrid asset={asset} /> : null}

          {generateMutation.isError ? (
            <p className="text-sm text-rose-700 dark:text-rose-300">
              {getUiErrorMessage(generateMutation.error, t)}
            </p>
          ) : null}

          {effectiveActiveCrawlStatus === 'running' || effectiveActiveCrawlStatus === 'pending' ? (
            <p className="text-sm text-stone-600 dark:text-slate-300">
              {t('sites.overview.contentGenerator.activeCrawlInProgress', {
                crawlId: effectiveActiveCrawlId ?? '-',
              })}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function resolveActionLabel(
  asset: SiteContentGeneratorAsset,
  t: (key: string, options?: Record<string, unknown>) => string,
) {
  if (!asset.has_assets) {
    return t('sites.overview.contentGenerator.actions.generate')
  }

  if (asset.status === 'failed') {
    return t('sites.overview.contentGenerator.actions.retry')
  }

  return t('sites.overview.contentGenerator.actions.regenerate')
}

function MetadataGrid({ asset }: { asset: SiteContentGeneratorAsset }) {
  const { t } = useTranslation()

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetadataCard
          label={t('sites.overview.contentGenerator.metadata.generatedAt')}
          value={formatDateTime(asset.generated_at)}
        />
        <MetadataCard
          label={t('sites.overview.contentGenerator.metadata.basisCrawl')}
          value={asset.basis_crawl_job_id ? `#${asset.basis_crawl_job_id}` : '-'}
        />
        <MetadataCard
          label={t('sites.overview.contentGenerator.metadata.llmModel')}
          value={asset.llm_model ?? '-'}
        />
        <MetadataCard
          label={t('sites.overview.contentGenerator.metadata.promptVersion')}
          value={asset.prompt_version ?? '-'}
        />
        <MetadataCard
          label={t('sites.overview.contentGenerator.metadata.sourcePagesHash')}
          value={asset.source_pages_hash ?? '-'}
          breakAll
        />
      </div>

      {asset.source_urls.length > 0 ? (
        <details className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
          <summary className="cursor-pointer list-none text-sm font-semibold text-stone-900 dark:text-slate-100">
            {t('sites.overview.contentGenerator.metadata.sourceUrls', { count: asset.source_urls.length })}
          </summary>
          <ul className="mt-3 space-y-2 text-sm text-stone-700 dark:text-slate-200">
            {asset.source_urls.map((url) => (
              <li key={url} className="break-all">
                <a href={url} target="_blank" rel="noreferrer" className="hover:underline">
                  {url}
                </a>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  )
}

function FailureDiagnostics({ asset }: { asset: SiteContentGeneratorAsset }) {
  const { t } = useTranslation()

  return (
    <div className="rounded-3xl border border-rose-200 bg-rose-50/80 p-4 text-sm text-rose-950 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-100">
      <dl className="grid gap-3 sm:grid-cols-2">
        <MetadataItem
          label={t('sites.overview.contentGenerator.failure.errorCode')}
          value={asset.last_error_code ?? '-'}
        />
        <MetadataItem
          label={t('sites.overview.contentGenerator.failure.basisCrawl')}
          value={asset.basis_crawl_job_id ? `#${asset.basis_crawl_job_id}` : '-'}
        />
        <MetadataItem
          label={t('sites.overview.contentGenerator.failure.generatedAt')}
          value={formatDateTime(asset.generated_at)}
        />
        <MetadataItem
          label={t('sites.overview.contentGenerator.failure.activeStatus')}
          value={resolveStatusLabel(asset.status, t)}
        />
      </dl>
    </div>
  )
}

function BusyContentState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-5 dark:border-slate-800 dark:bg-slate-900/80">
      <p className="text-lg font-semibold text-stone-950 dark:text-slate-50">{title}</p>
      <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">{description}</p>
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        {[0, 1, 2].map((index) => (
          <div
            key={index}
            className="space-y-3 rounded-3xl border border-stone-200 bg-white/80 p-4 dark:border-slate-800 dark:bg-slate-950/70"
          >
            <div className="h-4 w-40 animate-pulse rounded-full bg-stone-200 dark:bg-slate-800" />
            <div className="space-y-2">
              <div className="h-3 w-full animate-pulse rounded-full bg-stone-200 dark:bg-slate-800" />
              <div className="h-3 w-5/6 animate-pulse rounded-full bg-stone-200 dark:bg-slate-800" />
              <div className="h-3 w-4/6 animate-pulse rounded-full bg-stone-200 dark:bg-slate-800" />
              <div className="h-24 animate-pulse rounded-2xl bg-stone-100 dark:bg-slate-900" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ContentBlock({ title, content, compact = false }: ContentBlockProps) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const contentLength = content.trim().length

  useEffect(() => {
    if (!copied) {
      return undefined
    }

    const timeout = window.setTimeout(() => setCopied(false), 1400)
    return () => window.clearTimeout(timeout)
  }, [copied])

  async function handleCopy() {
    const copiedToClipboard = await copyText(content)
    if (copiedToClipboard) {
      setCopied(true)
    }
  }

  return (
    <article className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/80">
      <h3 className="text-base font-semibold text-stone-950 dark:text-slate-50">{title}</h3>
      <div
        className={`mt-3 overflow-auto rounded-2xl border border-stone-200 bg-white/90 p-4 text-sm leading-6 whitespace-pre-wrap text-stone-800 dark:border-slate-800 dark:bg-slate-950/80 dark:text-slate-100 ${
          compact ? 'min-h-[160px]' : 'min-h-[220px]'
        }`}
      >
        {content}
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
          {t('common.length', { count: contentLength })}
        </p>
        <button type="button" onClick={() => void handleCopy()} className={secondaryActionClassName}>
          {copied ? t('common.copied') : t('common.copy')}
        </button>
      </div>
    </article>
  )
}

function MetadataCard({
  label,
  value,
  breakAll = false,
}: {
  label: string
  value: string
  breakAll?: boolean
}) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-stone-50/90 p-3 dark:border-slate-800 dark:bg-slate-900/80">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500 dark:text-slate-400">
        {label}
      </p>
      <p className={`mt-2 text-sm font-medium text-stone-900 dark:text-slate-100 ${breakAll ? 'break-all' : ''}`}>
        {value}
      </p>
    </div>
  )
}

function MetadataItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.16em] opacity-75">{label}</dt>
      <dd className="mt-1 font-medium">{value}</dd>
    </div>
  )
}

function ContentGeneratorStatusBadge({ status }: { status: ContentGeneratorAssetStatus }) {
  const { t } = useTranslation()

  const statusClasses: Record<ContentGeneratorAssetStatus, string> = {
    pending:
      'border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-700/70 dark:bg-amber-950/45 dark:text-amber-200',
    running:
      'border-sky-200 bg-sky-100 text-sky-900 dark:border-sky-700/70 dark:bg-sky-950/45 dark:text-sky-200',
    ready:
      'border-emerald-200 bg-emerald-100 text-emerald-900 dark:border-emerald-700/70 dark:bg-emerald-950/45 dark:text-emerald-200',
    failed:
      'border-rose-200 bg-rose-100 text-rose-900 dark:border-rose-700/70 dark:bg-rose-950/45 dark:text-rose-200',
  }

  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${statusClasses[status]}`}
    >
      {resolveStatusLabel(status, t)}
    </span>
  )
}

function resolveStatusLabel(
  status: ContentGeneratorAssetStatus | null,
  t: (key: string, options?: Record<string, unknown>) => string,
) {
  if (!status) {
    return '-'
  }

  if (status === 'ready') {
    return t('sites.overview.contentGenerator.status.ready')
  }

  return t(`jobs.status.${status}`)
}
