type QueryPrimitive = string | number | boolean | undefined

export function buildQueryString<T extends object>(params: T) {
  const searchParams = new URLSearchParams()

  Object.entries(params as Record<string, QueryPrimitive>).forEach(([key, value]) => {
    if (value === undefined || value === '') {
      return
    }
    searchParams.set(key, String(value))
  })

  return searchParams.toString()
}

export function mergeSearchParams(
  current: URLSearchParams,
  updates: Record<string, QueryPrimitive>,
) {
  const next = new URLSearchParams(current)

  Object.entries(updates).forEach(([key, value]) => {
    if (value === undefined || value === '') {
      next.delete(key)
    } else {
      next.set(key, String(value))
    }
  })

  return next
}

export function parseIntegerParam(value: string | null, fallback: number): number
export function parseIntegerParam(value: string | null, fallback: undefined): number | undefined
export function parseIntegerParam(value: string | null, fallback: number | undefined) {
  if (value === null || value.trim() === '') {
    return fallback
  }

  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return fallback
  }

  return parsed
}
