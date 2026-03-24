export const THEME_STORAGE_KEY = 'seo-crawler-ui-theme'
export const DEFAULT_THEME = 'light'

export type AppTheme = 'light' | 'dark'

export const supportedThemes: AppTheme[] = ['light', 'dark']

export function normalizeTheme(theme: string | null | undefined): AppTheme {
  return theme === 'dark' ? 'dark' : 'light'
}

function getPreferredTheme(): AppTheme {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return DEFAULT_THEME
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function getStoredTheme(): AppTheme {
  if (typeof window === 'undefined') {
    return DEFAULT_THEME
  }

  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)

  return storedTheme ? normalizeTheme(storedTheme) : getPreferredTheme()
}

export function persistTheme(theme: AppTheme) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(THEME_STORAGE_KEY, normalizeTheme(theme))
}

export function applyTheme(theme: AppTheme) {
  if (typeof document === 'undefined') {
    return
  }

  const normalizedTheme = normalizeTheme(theme)
  document.documentElement.classList.toggle('dark', normalizedTheme === 'dark')
  document.documentElement.dataset.theme = normalizedTheme
}

export function syncThemeFromStorage() {
  const theme = getStoredTheme()
  applyTheme(theme)
  return theme
}

export function updateTheme(theme: AppTheme) {
  const normalizedTheme = normalizeTheme(theme)
  persistTheme(normalizedTheme)
  applyTheme(normalizedTheme)
  return normalizedTheme
}
