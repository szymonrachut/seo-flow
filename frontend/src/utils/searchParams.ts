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

export function parseFloatParam(value: string | null, fallback: number): number
export function parseFloatParam(value: string | null, fallback: undefined): number | undefined
export function parseFloatParam(value: string | null, fallback: number | undefined) {
  if (value === null || value.trim() === '') {
    return fallback
  }

  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return fallback
  }

  return parsed
}

export function parseCsvParam<T extends string>(
  value: string | null,
  allowedValues?: readonly T[],
): Set<T> {
  if (!value) {
    return new Set<T>()
  }

  const allowed = allowedValues ? new Set<string>(allowedValues) : null

  return new Set(
    value
      .split(',')
      .map((item) => item.trim())
      .filter((item): item is T => item.length > 0 && (allowed === null || allowed.has(item))),
  )
}

export function serializeCsvParam<T extends string>(values: Iterable<T>) {
  const serialized = Array.from(new Set(values))
  return serialized.length > 0 ? serialized.join(',') : undefined
}

export function toggleCsvParamValue<T extends string>(current: Iterable<T>, value: T) {
  const next = new Set(current)
  if (next.has(value)) {
    next.delete(value)
  } else {
    next.add(value)
  }
  return next
}
