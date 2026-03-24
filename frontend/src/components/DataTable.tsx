import type { CSSProperties, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { SortOrder } from '../types/api'

export interface DataTableColumn<T> {
  key: string
  header: string
  sortKey?: string
  cell: (row: T) => ReactNode
  minWidth?: number | string
  headerClassName?: string
  cellClassName?: string
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  rows: T[]
  rowKey: (row: T) => string | number
  sortBy?: string
  sortOrder?: SortOrder
  onSortChange?: (sortBy: string, sortOrder: SortOrder) => void
  stickyHeader?: boolean
}

function getNextSortOrder(isActive: boolean, sortOrder: SortOrder | undefined): SortOrder {
  if (!isActive) {
    return 'asc'
  }

  return sortOrder === 'asc' ? 'desc' : 'asc'
}

function resolveMinWidth(minWidth: DataTableColumn<unknown>['minWidth']): CSSProperties | undefined {
  if (minWidth === undefined) {
    return undefined
  }

  return {
    minWidth: typeof minWidth === 'number' ? `${minWidth}px` : minWidth,
  }
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  sortBy,
  sortOrder,
  onSortChange,
  stickyHeader = true,
}: DataTableProps<T>) {
  const { t } = useTranslation()

  return (
    <div className="w-full overflow-x-auto rounded-[28px] border border-stone-300 bg-white/90 shadow-sm dark:border-slate-800 dark:bg-slate-950/85">
      <table className="w-max min-w-full table-auto border-collapse">
        <thead>
          <tr className="bg-stone-100/90 dark:bg-slate-900/90">
            {columns.map((column) => {
              const isSortable = Boolean(column.sortKey && onSortChange)
              const isActive = isSortable && column.sortKey === sortBy
              const nextSortOrder = getNextSortOrder(isActive, sortOrder)
              const ariaSort = isActive ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'
              const minWidthStyle = resolveMinWidth(column.minWidth)

              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={ariaSort}
                  style={minWidthStyle}
                  className={`border-b border-stone-200 px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.18em] whitespace-nowrap break-normal text-stone-600 dark:border-slate-800 dark:text-slate-300 ${stickyHeader ? 'sticky top-0 z-10 bg-stone-100/95 backdrop-blur dark:bg-slate-900/95' : ''} ${column.headerClassName ?? ''}`}
                >
                  {isSortable && column.sortKey ? (
                    <button
                      type="button"
                      onClick={() => onSortChange?.(column.sortKey!, nextSortOrder)}
                      className="group inline-flex items-center gap-2 whitespace-nowrap text-left text-inherit"
                      aria-label={t('common.sortBy', { column: column.header })}
                    >
                      <span
                        className={`border-b border-dotted transition ${
                          isActive
                            ? 'border-stone-800 text-stone-950 dark:border-teal-300 dark:text-teal-200'
                            : 'border-stone-400 text-stone-700 group-hover:border-stone-600 group-hover:text-stone-900 dark:border-slate-600 dark:text-slate-300 dark:group-hover:border-slate-400 dark:group-hover:text-slate-100'
                        }`}
                      >
                        {column.header}
                      </span>
                      <span
                        aria-hidden="true"
                        className={`text-sm leading-none transition ${
                          isActive ? 'text-stone-950 dark:text-teal-200' : 'text-stone-400 group-hover:text-stone-700 dark:text-slate-500 dark:group-hover:text-slate-200'
                        }`}
                      >
                        {isActive ? (sortOrder === 'asc' ? '^' : 'v') : '+'}
                      </span>
                    </button>
                  ) : (
                    <span>{column.header}</span>
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-stone-200/70 align-top last:border-b-0 dark:border-slate-800/80">
              {columns.map((column) => {
                const minWidthStyle = resolveMinWidth(column.minWidth)

                return (
                  <td
                    key={column.key}
                    style={minWidthStyle}
                    className={`px-4 py-4 text-sm whitespace-nowrap break-normal text-stone-700 dark:text-slate-200 ${column.cellClassName ?? ''}`}
                  >
                    {column.cell(row)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
