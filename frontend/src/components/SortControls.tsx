import type { SortOrder } from '../types/api'

interface SortOption {
  label: string
  value: string
}

interface SortControlsProps {
  label?: string
  sortBy: string
  sortOrder: SortOrder
  options: SortOption[]
  onSortByChange: (sortBy: string) => void
  onSortOrderChange: (sortOrder: SortOrder) => void
}

export function SortControls({
  label = 'Sort',
  sortBy,
  sortOrder,
  options,
  onSortByChange,
  onSortOrderChange,
}: SortControlsProps) {
  return (
    <div className="flex flex-col gap-3 rounded-3xl border border-stone-300 bg-white/85 p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 className="text-base font-semibold text-stone-900">{label}</h2>
        <p className="mt-1 text-sm text-stone-600">Sorting is synchronized with the URL.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-2 text-sm text-stone-700">
          <span>By</span>
          <select
            value={sortBy}
            onChange={(event) => onSortByChange(event.target.value)}
            className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-sm"
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-stone-700">
          <span>Order</span>
          <select
            value={sortOrder}
            onChange={(event) => onSortOrderChange(event.target.value as SortOrder)}
            className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-sm"
          >
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </label>
      </div>
    </div>
  )
}
