import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach } from 'vitest'

import i18n, { DEFAULT_LANGUAGE, LANGUAGE_STORAGE_KEY } from '../i18n'
import { DEFAULT_THEME, THEME_STORAGE_KEY, applyTheme } from '../theme'

beforeEach(async () => {
  window.localStorage.removeItem(LANGUAGE_STORAGE_KEY)
  window.localStorage.removeItem(THEME_STORAGE_KEY)
  applyTheme(DEFAULT_THEME)
  await i18n.changeLanguage(DEFAULT_LANGUAGE)
})

afterEach(async () => {
  window.localStorage.removeItem(LANGUAGE_STORAGE_KEY)
  window.localStorage.removeItem(THEME_STORAGE_KEY)
  applyTheme(DEFAULT_THEME)
  await i18n.changeLanguage(DEFAULT_LANGUAGE)
})
