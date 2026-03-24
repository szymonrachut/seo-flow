import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { CrawlJobCreateInput } from '../../types/api'

interface CreateJobFormProps {
  onSubmit: (payload: CrawlJobCreateInput) => Promise<void>
  isPending: boolean
  errorMessage?: string | null
  initialValues?: Partial<CrawlJobCreateInput>
}

const defaultValues: CrawlJobCreateInput = {
  root_url: 'https://example.com',
  max_urls: 500,
  max_depth: 10,
  delay: 0.25,
  render_mode: 'auto',
  render_timeout_ms: 8000,
  max_rendered_pages_per_job: 25,
}

export function CreateJobForm({ onSubmit, isPending, errorMessage, initialValues }: CreateJobFormProps) {
  const { t } = useTranslation()
  const [values, setValues] = useState<CrawlJobCreateInput>({ ...defaultValues, ...initialValues })

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <section className="rounded-[28px] border border-stone-300 bg-white/90 p-5 shadow-sm">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-teal-700">{t('jobs.form.eyebrow')}</p>
        <h2 className="mt-2 text-2xl font-semibold text-stone-950">{t('jobs.form.title')}</h2>
        <p className="mt-2 text-sm text-stone-600">{t('jobs.form.description')}</p>
      </div>

      <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-stone-700">{t('jobs.form.rootUrl')}</span>
          <input
            required
            type="url"
            value={values.root_url}
            onChange={(event) => setValues((current) => ({ ...current, root_url: event.target.value }))}
            className="w-full rounded-2xl border border-stone-300 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200"
            placeholder={t('jobs.form.rootUrlPlaceholder')}
          />
        </label>

        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-stone-700">{t('jobs.form.maxUrls')}</span>
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
            <span className="mb-1.5 block text-sm font-medium text-stone-700">{t('jobs.form.maxDepth')}</span>
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
            <span className="mb-1.5 block text-sm font-medium text-stone-700">{t('jobs.form.delay')}</span>
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

        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-stone-700">{t('jobs.form.renderMode')}</span>
            <select
              value={values.render_mode}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  render_mode: event.target.value as CrawlJobCreateInput['render_mode'],
                }))
              }
              className="w-full rounded-2xl border border-stone-300 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200"
            >
              <option value="never">{t('jobs.form.renderModeNever')}</option>
              <option value="auto">{t('jobs.form.renderModeAuto')}</option>
              <option value="always">{t('jobs.form.renderModeAlways')}</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-stone-700">{t('jobs.form.renderTimeout')}</span>
            <input
              min={1000}
              max={60000}
              step={1000}
              type="number"
              value={values.render_timeout_ms}
              onChange={(event) =>
                setValues((current) => ({ ...current, render_timeout_ms: Number(event.target.value) || 1000 }))
              }
              className="w-full rounded-2xl border border-stone-300 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-stone-700">{t('jobs.form.renderLimit')}</span>
            <input
              min={1}
              type="number"
              value={values.max_rendered_pages_per_job}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  max_rendered_pages_per_job: Number(event.target.value) || 1,
                }))
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
          {isPending ? t('jobs.form.submitting') : t('jobs.form.submit')}
        </button>
      </form>
    </section>
  )
}
