import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { copyText } from '../utils/clipboard'

interface UrlActionsProps {
  url: string
  openLabel?: string
  copyLabel?: string
}

export function UrlActions({ url, openLabel = 'Open', copyLabel = 'Copy' }: UrlActionsProps) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const resolvedOpenLabel = openLabel === 'Open' ? t('common.open') : openLabel
  const resolvedCopyLabel = copyLabel === 'Copy' ? t('common.copy') : copyLabel

  useEffect(() => {
    if (!copied) {
      return undefined
    }

    const timeout = window.setTimeout(() => setCopied(false), 1400)
    return () => window.clearTimeout(timeout)
  }, [copied])

  async function handleCopy() {
    const copiedToClipboard = await copyText(url)
    if (!copiedToClipboard) {
      return
    }

    setCopied(true)
  }

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex rounded-full border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800"
      >
        {resolvedOpenLabel}
      </a>
      <button
        type="button"
        onClick={() => void handleCopy()}
        className="inline-flex rounded-full border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800"
      >
        {copied ? t('common.copied') : resolvedCopyLabel}
      </button>
    </div>
  )
}
