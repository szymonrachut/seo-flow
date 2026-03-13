import type { ReactNode } from 'react'

export interface DataTableColumn<T> {
  key: string
  header: string
  className?: string
  cell: (row: T) => ReactNode
}

interface DataTableProps<T> {
  columns: Array<DataTableColumn<T>>
  rows: T[]
  rowKey: (row: T) => string | number
}

export function DataTable<T>({ columns, rows, rowKey }: DataTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-3xl border border-stone-300 bg-white/85 shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-stone-200 text-left text-sm">
          <thead className="bg-stone-100/80 text-xs uppercase tracking-[0.18em] text-stone-500">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={`px-4 py-3 font-semibold ${column.className ?? ''}`}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-200/80 text-stone-700">
            {rows.map((row) => (
              <tr key={rowKey(row)} className="align-top hover:bg-teal-50/40">
                {columns.map((column) => (
                  <td key={column.key} className={`px-4 py-3 ${column.className ?? ''}`}>
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
