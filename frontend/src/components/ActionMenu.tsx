import { Link } from 'react-router-dom'

export interface ActionMenuItem {
  key: string
  label: string
  to?: string
  href?: string
  onClick?: () => void
  disabled?: boolean
}

interface ActionMenuProps {
  label: string
  items: ActionMenuItem[]
}

const triggerClassName =
  'list-none rounded-full border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-900'

const itemClassName =
  'flex w-full items-center rounded-2xl px-3 py-2 text-left text-sm text-stone-700 transition hover:bg-stone-100 dark:text-slate-200 dark:hover:bg-slate-900'

function renderItem(item: ActionMenuItem) {
  if (item.to) {
    return (
      <Link key={item.key} to={item.to} className={itemClassName}>
        {item.label}
      </Link>
    )
  }

  if (item.href) {
    return (
      <a key={item.key} href={item.href} className={itemClassName}>
        {item.label}
      </a>
    )
  }

  return (
    <button
      key={item.key}
      type="button"
      onClick={item.onClick}
      disabled={item.disabled}
      className={itemClassName}
    >
      {item.label}
    </button>
  )
}

export function ActionMenu({ label, items }: ActionMenuProps) {
  if (items.length === 0) {
    return null
  }

  return (
    <details className="group relative">
      <summary className={triggerClassName}>
        <span>{label}</span>
        <span aria-hidden="true" className="ml-2 text-xs text-stone-500 dark:text-slate-400">
          v
        </span>
      </summary>
      <div className="absolute right-0 z-20 mt-2 min-w-60 rounded-3xl border border-stone-300 bg-white/95 p-2 shadow-lg dark:border-slate-700 dark:bg-slate-950/95">
        <div className="grid gap-1">{items.map((item) => renderItem(item))}</div>
      </div>
    </details>
  )
}
