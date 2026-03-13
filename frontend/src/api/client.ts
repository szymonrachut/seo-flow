const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const apiBaseUrl = rawApiBaseUrl.replace(/\/+$/, '')

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${apiBaseUrl}${normalizedPath}`
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {})
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers,
  })
  const contentType = response.headers.get('content-type') ?? ''

  if (!response.ok) {
    let detail = `HTTP ${response.status}`

    if (contentType.includes('application/json')) {
      const payload = (await response.json()) as { detail?: string }
      detail = payload.detail ?? detail
    } else {
      const text = await response.text()
      if (text) {
        detail = text
      }
    }

    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }

  return (await response.text()) as T
}
