import { type FormEvent, useState } from 'react'

import type { CrawlJobCreateInput } from '../../types/api'

interface CreateJobFormProps {
  onSubmit: (payload: CrawlJobCreateInput) => Promise<void>
  isPending: boolean
  errorMessage?: string | null
}

const defaultValues: CrawlJobCreateInput = {
  root_url: 'https://example.com',
  max_urls: 500,
  max_depth: 3,
  delay: 0.25,
}

export function CreateJobForm({ onSubmit, isPending, errorMessage }: CreateJobFormProps) {
  const [values, setValues] = useState<CrawlJobCreateInput>(defaultValues)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <section className="rounded-[28px] border border-stone-300 bg-white/90 p-5 shadow-sm">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-teal-700">New crawl job</p>
        <h2 className="mt-2 text-2xl font-semibold text-stone-950">Launch a local audit</h2>
        <p className="mt-2 text-sm text-stone-600">
          Keep frontend validation light. The backend still validates the payload.
        </p>
      </div>

      <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-stone-700">Root URL</span>
          <input
            required
            type="url"
            value={values.root_url}
            onChange={(event) => setValues((current) => ({ ...current, root_url: event.target.value }))}
            className="w-full rounded-2xl border border-stone-300 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200"
            placeholder="https://example.com"
          />
        </label>

        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-stone-700">Max URLs</span>
            <input
              min={1}
              type="number"
              value={values.max_urls}
              onChange={(event) =>
                setValues((current) => ({ ...current, max_urls: Number(event.target.value) || 1 }))
              }
              className="w-full rounded-2xl border border-stone-300 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-stone-700">Max depth</span>
            <input
              min={0}
              type="number"
              value={values.max_depth}
              onChange={(event) =>
                setValues((current) => ({ ...current, max_depth: Number(event.target.value) || 0 }))
              }
              className="w-full rounded-2xl border border-stone-300 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-stone-700">Delay</span>
            <input
              min={0}
              step={0.05}
              type="number"
              value={values.delay}
              onChange={(event) =>
                setValues((current) => ({ ...current, delay: Number(event.target.value) || 0 }))
              }
              className="w-full rounded-2xl border border-stone-300 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200"
            />
          </label>
        </div>

        {errorMessage ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-950">
            {errorMessage}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={isPending}
          className="inline-flex rounded-full bg-stone-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? 'Creating job...' : 'Create crawl job'}
        </button>
      </form>
    </section>
  )
}
