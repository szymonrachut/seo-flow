import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './en.json'
import pl from './pl.json'

export const LANGUAGE_STORAGE_KEY = 'seo-crawler-ui-language'
export const DEFAULT_LANGUAGE = 'en'

export type AppLanguage = 'en' | 'pl'

export const supportedLanguages: AppLanguage[] = ['en', 'pl']

const resources = {
  en: {
    translation: en,
  },
  pl: {
    translation: pl,
  },
} as const

export const intlLocales: Record<AppLanguage, string> = {
  en: 'en-US',
  pl: 'pl-PL',
}

export function normalizeLanguage(language: string | null | undefined): AppLanguage {
  if (language?.toLowerCase().startsWith('pl')) {
    return 'pl'
  }

  return 'en'
}

export function getStoredLanguage(): AppLanguage {
  if (typeof window === 'undefined') {
    return DEFAULT_LANGUAGE
  }

  return normalizeLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY))
}

export function persistLanguage(language: string) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, normalizeLanguage(language))
}

export function getCurrentLanguage(): AppLanguage {
  return normalizeLanguage(i18n.resolvedLanguage ?? i18n.language)
}

export async function syncLanguageFromStorage() {
  const nextLanguage = getStoredLanguage()

  if (getCurrentLanguage() !== nextLanguage) {
    await i18n.changeLanguage(nextLanguage)
  }

  return nextLanguage
}

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    resources,
    lng: getStoredLanguage(),
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: supportedLanguages,
    interpolation: {
      escapeValue: false,
    },
    returnNull: false,
    react: {
      useSuspense: false,
    },
    initImmediate: false,
  })
}

function applyLanguageSideEffects(language: string) {
  const normalized = normalizeLanguage(language)
  persistLanguage(normalized)

  if (typeof document !== 'undefined') {
    document.documentElement.lang = normalized
  }
}

applyLanguageSideEffects(getCurrentLanguage())
i18n.on('languageChanged', applyLanguageSideEffects)

export default i18n
