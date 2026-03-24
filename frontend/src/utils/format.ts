import i18n, { intlLocales, normalizeLanguage } from '../i18n'

interface CrawlSnapshotLike {
  created_at?: string | null
  started_at?: string | null
  root_url?: string | null
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  return new Intl.DateTimeFormat(intlLocales[normalizeLanguage(i18n.resolvedLanguage ?? i18n.language)], {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function resolveCrawlDateTime(value: CrawlSnapshotLike | null | undefined) {
  return value?.started_at ?? value?.created_at ?? null
}

export function formatCrawlDateTime(value: CrawlSnapshotLike | null | undefined) {
  return formatDateTime(resolveCrawlDateTime(value))
}

export function formatCrawlOptionLabel(value: CrawlSnapshotLike | null | undefined, fallbackRootUrl?: string | null) {
  const crawlDateTime = resolveCrawlDateTime(value)
  const rootUrl = value?.root_url ?? fallbackRootUrl ?? null

  if (!crawlDateTime) {
    return rootUrl ?? '-'
  }

  const formattedDateTime = formatDateTime(crawlDateTime)
  return rootUrl ? `${formattedDateTime} - ${rootUrl}` : formattedDateTime
}

export function formatNullable(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }

  return String(value)
}

export function formatResponseTime(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }

  return `${value} ms`
}

export function formatBytes(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }

  if (value < 1024) {
    return `${value} B`
  }

  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`
  }

  return `${(value / (1024 * 1024)).toFixed(2)} MB`
}

export function formatBoolean(value: boolean) {
  return value ? i18n.t('common.yes') : i18n.t('common.no')
}

export function formatPercent(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) {
    return '-'
  }

  return `${(value * 100).toFixed(digits)}%`
}

export function formatPosition(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }

  return value.toFixed(1)
}

export function truncateText(value: string | null | undefined, maxLength = 64) {
  if (!value) {
    return '-'
  }

  return value.length > maxLength ? `${value.slice(0, maxLength - 3)}...` : value
}

export function prettyJson(value: unknown) {
  return JSON.stringify(value, null, 2)
}

export function formatLength(value: string | null | undefined) {
  if (!value) {
    return '0'
  }

  return String(value.trim().length)
}
