import { type ReactNode, useEffect } from 'react'

interface DetailModalProps {
  titleId: string
  title: string
  closeLabel: string
  onClose: () => void
  eyebrow?: string
  subtitle?: ReactNode
  children: ReactNode
  className?: string
}

export function DetailModal({
  titleId,
  title,
  closeLabel,
  onClose,
  eyebrow,
  subtitle,
  children,
  className = '',
}: DetailModalProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-stone-950/55 px-4 py-6 sm:px-6 sm:py-10"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`w-full max-w-4xl rounded-[32px] border border-stone-300 bg-white p-5 shadow-2xl dark:border-slate-700 dark:bg-slate-900 sm:p-6 ${className}`.trim()}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-stone-200 pb-4 dark:border-slate-700">
          <div className="min-w-0 space-y-2">
            {eyebrow ? <p className="text-xs uppercase tracking-[0.22em] text-teal-700 dark:text-teal-300">{eyebrow}</p> : null}
            <h2 id={titleId} className="text-lg font-semibold text-stone-950 whitespace-normal break-words dark:text-slate-50">
              {title}
            </h2>
            {subtitle ? <div className="text-sm text-stone-600 whitespace-normal break-words dark:text-slate-300">{subtitle}</div> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-stone-300 text-lg font-semibold leading-none text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-600 dark:text-slate-200 dark:hover:border-slate-500 dark:hover:bg-slate-800"
            aria-label={closeLabel}
          >
            x
          </button>
        </div>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  )
}
