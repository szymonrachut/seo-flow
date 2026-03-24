import { type ReactNode, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { getCurrentLanguage, type AppLanguage, supportedLanguages } from '../i18n'
import { getStoredTheme, supportedThemes, type AppTheme, updateTheme } from '../theme'

interface AppHeaderProps {
  sectionTitle: string
}

const activeToggleClass =
  'border border-stone-950 bg-stone-950 !text-white shadow-sm hover:bg-stone-900 dark:border-teal-400 dark:bg-teal-400 dark:!text-slate-950 dark:hover:bg-teal-300'

const inactiveToggleClass =
  'text-stone-700 hover:bg-stone-100 dark:text-slate-200 dark:hover:bg-slate-800'

export function AppHeader({ sectionTitle }: AppHeaderProps) {
  const { t, i18n } = useTranslation()
  const activeLanguage = getCurrentLanguage()
  const [activeTheme, setActiveTheme] = useState<AppTheme>(() => getStoredTheme())

  useEffect(() => {
    updateTheme(activeTheme)
  }, [activeTheme])

  async function handleLanguageChange(language: AppLanguage) {
    if (language === activeLanguage) {
      return
    }

    await i18n.changeLanguage(language)
  }

  function handleThemeChange(theme: AppTheme) {
    if (theme === activeTheme) {
      return
    }

    setActiveTheme(theme)
  }

  return (
    <header className="sticky top-0 z-30 border-b border-stone-300/80 bg-[#f7f2ea]/92 backdrop-blur dark:border-slate-800 dark:bg-slate-950/92">
      <div className="flex w-full flex-col gap-4 px-4 py-4 sm:px-6 xl:flex-row xl:items-center xl:justify-between xl:px-8">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-teal-700 dark:text-teal-300">SEO Flow</p>
          <h1 className="mt-2 truncate text-2xl font-semibold tracking-tight text-stone-950 dark:text-slate-50">
            {sectionTitle}
          </h1>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <HeaderToggleGroup label={t('theme.label')}>
            {supportedThemes.map((theme) => {
              const labelKey = `theme.${theme}` as const
              const isActive = theme === activeTheme

              return (
                <button
                  key={theme}
                  type="button"
                  aria-label={t(labelKey)}
                  aria-pressed={isActive}
                  onClick={() => handleThemeChange(theme)}
                  className={`rounded-full px-3 py-1.5 text-sm font-semibold transition ${isActive ? activeToggleClass : inactiveToggleClass}`}
                >
                  {t(labelKey)}
                </button>
              )
            })}
          </HeaderToggleGroup>

          <HeaderToggleGroup label={t('language.label')}>
            {supportedLanguages.map((language) => {
              const isActive = language === activeLanguage
              const labelKey = language === 'en' ? 'language.english' : 'language.polish'
              const shortKey = `language.short.${language}` as const

              return (
                <button
                  key={language}
                  type="button"
                  aria-label={t(labelKey)}
                  aria-pressed={isActive}
                  onClick={() => void handleLanguageChange(language)}
                  className={`rounded-full px-3 py-1.5 text-sm font-semibold transition ${isActive ? activeToggleClass : inactiveToggleClass}`}
                >
                  {t(shortKey)}
                </button>
              )
            })}
          </HeaderToggleGroup>

          <div className="flex items-center gap-2">
            <IconButton ariaLabel={t('shell.actions.systemSettings')} disabled>
              <SettingsIcon />
            </IconButton>
            <IconButton ariaLabel={t('shell.actions.account')} disabled>
              <UserIcon />
            </IconButton>
          </div>
        </div>
      </div>
    </header>
  )
}

interface HeaderToggleGroupProps {
  label: string
  children: ReactNode
}

function HeaderToggleGroup({ label, children }: HeaderToggleGroupProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500 dark:text-slate-400">{label}</span>
      <div className="inline-flex rounded-full border border-stone-300 bg-white/80 p-1 shadow-sm dark:border-slate-700 dark:bg-slate-950/80">
        {children}
      </div>
    </div>
  )
}

interface IconButtonProps {
  ariaLabel: string
  children: ReactNode
  disabled?: boolean
}

function IconButton({ ariaLabel, children, disabled = false }: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      disabled={disabled}
      className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-stone-300 bg-white/85 text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/80 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900"
    >
      {children}
    </button>
  )
}

function SettingsIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.7">
      <path d="M12 3.75v2.5" strokeLinecap="round" />
      <path d="M12 17.75v2.5" strokeLinecap="round" />
      <path d="M3.75 12h2.5" strokeLinecap="round" />
      <path d="M17.75 12h2.5" strokeLinecap="round" />
      <path d="M6.2 6.2l1.8 1.8" strokeLinecap="round" />
      <path d="M16 16l1.8 1.8" strokeLinecap="round" />
      <path d="M6.2 17.8L8 16" strokeLinecap="round" />
      <path d="M16 8l1.8-1.8" strokeLinecap="round" />
      <circle cx="12" cy="12" r="3.6" />
    </svg>
  )
}

function UserIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.7">
      <circle cx="12" cy="8.25" r="3.25" />
      <path d="M5.5 19c1.1-3.05 3.53-4.75 6.5-4.75s5.4 1.7 6.5 4.75" strokeLinecap="round" />
    </svg>
  )
}
