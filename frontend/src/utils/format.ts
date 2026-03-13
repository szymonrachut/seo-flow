export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '—'
  }

  return new Intl.DateTimeFormat('pl-PL', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function formatNullable(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }
  return String(value)
}

export function formatResponseTime(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '—'
  }
  return `${value} ms`
}

export function formatBoolean(value: boolean) {
  return value ? 'Yes' : 'No'
}

export function truncateText(value: string | null | undefined, maxLength = 64) {
  if (!value) {
    return '—'
  }

  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}…` : value
}

export function prettyJson(value: unknown) {
  return JSON.stringify(value, null, 2)
}
