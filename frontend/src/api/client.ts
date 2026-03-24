const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const apiBaseUrl = rawApiBaseUrl.replace(/\/+$/, '')
const LANGUAGE_STORAGE_KEY = 'seo-crawler-ui-language'

function normalizeLanguage(language: string | null | undefined): 'en' | 'pl' {
  if (language?.toLowerCase().startsWith('pl')) {
    return 'pl'
  }

  return 'en'
}

function getUiLanguage(): 'en' | 'pl' {
  if (typeof window === 'undefined') {
    return 'en'
  }

  return normalizeLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY))
}

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

export function getApiBaseUrl(): string {
  return apiBaseUrl
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {})
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (!headers.has('X-UI-Language')) {
    headers.set('X-UI-Language', getUiLanguage())
  }

  let response: Response

  try {
    response = await fetch(buildApiUrl(path), {
      ...init,
      headers,
    })
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError(0, 'NETWORK_UNAVAILABLE')
    }

    throw error
  }

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
