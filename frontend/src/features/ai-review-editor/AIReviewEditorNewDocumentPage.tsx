import { startTransition, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { DataViewHeader } from '../../components/DataViewHeader'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getUiErrorMessage } from '../../utils/errors'
import { useSiteWorkspaceContext } from '../sites/context'
import {
  buildSiteAiReviewEditorDocumentPath,
  buildSiteAiReviewEditorDocumentsPath,
} from '../sites/routes'
import { useCreateSiteAiReviewDocumentMutation } from './api'

const surfaceClass =
  'rounded-[32px] border border-stone-300 bg-white/85 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950/80'
const fieldLabelClass = 'grid gap-1 text-sm text-stone-700 dark:text-slate-300'
const fieldControlClass =
  'rounded-2xl border border-stone-300 bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-teal-400 dark:focus:ring-teal-500/30'
const secondaryActionClass =
  'inline-flex rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-400 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-100 dark:hover:border-slate-600 dark:hover:bg-slate-900'
const primaryActionClass =
  'inline-flex rounded-full bg-stone-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-teal-400 dark:text-slate-950 dark:hover:bg-teal-300'

export function AIReviewEditorNewDocumentPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { site, activeCrawlId, baselineCrawlId } = useSiteWorkspaceContext()
  const createDocumentMutation = useCreateSiteAiReviewDocumentMutation(site.id)

  const [title, setTitle] = useState('')
  const [documentType, setDocumentType] = useState('article')
  const [sourceContent, setSourceContent] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  useDocumentTitle(t('documentTitle.aiReviewEditorNewDocument', { domain: site.domain }))

  const documentsPath = buildSiteAiReviewEditorDocumentsPath(site.id, {
    activeCrawlId,
    baselineCrawlId,
  })

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)

    const normalizedTitle = title.trim()
    const normalizedDocumentType = documentType.trim()
    const normalizedSourceContent = sourceContent.trim()

    if (!normalizedTitle || !normalizedDocumentType || !normalizedSourceContent) {
      setFormError(t('aiReviewEditor.create.validation.required'))
      return
    }

    try {
      const document = await createDocumentMutation.mutateAsync({
        title: normalizedTitle,
        document_type: normalizedDocumentType,
        source_format: 'html',
        source_content: normalizedSourceContent,
      })

      startTransition(() => {
        navigate(
          buildSiteAiReviewEditorDocumentPath(document.site_id, document.id, {
            activeCrawlId,
            baselineCrawlId,
          }),
        )
      })
    } catch (error) {
      setFormError(getUiErrorMessage(error, t))
    }
  }

  return (
    <div className="space-y-6">
      <DataViewHeader
        eyebrow={t('aiReviewEditor.header.eyebrow')}
        title={t('aiReviewEditor.create.title')}
        description={t('aiReviewEditor.create.description')}
        contextChips={[
          { label: t('aiReviewEditor.documents.context.site'), value: site.domain },
          {
            label: t('aiReviewEditor.documents.context.activeCrawl'),
            value: activeCrawlId ? `#${activeCrawlId}` : t('aiReviewEditor.common.none'),
          },
          {
            label: t('aiReviewEditor.documents.context.baseline'),
            value: baselineCrawlId ? `#${baselineCrawlId}` : t('aiReviewEditor.common.none'),
          },
          {
            label: t('aiReviewEditor.create.fields.sourceFormat'),
            value: 'html',
          },
        ]}
        operations={[
          {
            key: 'documents',
            label: t('aiReviewEditor.actions.openDocuments'),
            to: documentsPath,
          },
        ]}
      />

      {formError ? (
        <section className="rounded-3xl border border-rose-200 bg-rose-50/90 p-4 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          {formError}
        </section>
      ) : null}

      <section className={surfaceClass}>
        <form className="space-y-5" onSubmit={handleSubmit}>
          <div className="grid gap-5 lg:grid-cols-2">
            <label className={fieldLabelClass}>
              <span>{t('aiReviewEditor.create.fields.title')}</span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={t('aiReviewEditor.create.placeholders.title')}
                className={fieldControlClass}
                maxLength={255}
              />
            </label>

            <label className={fieldLabelClass}>
              <span>{t('aiReviewEditor.create.fields.documentType')}</span>
              <input
                value={documentType}
                onChange={(event) => setDocumentType(event.target.value)}
                placeholder={t('aiReviewEditor.create.placeholders.documentType')}
                className={fieldControlClass}
                maxLength={64}
              />
            </label>
          </div>

          <label className={fieldLabelClass}>
            <span>{t('aiReviewEditor.create.fields.sourceContent')}</span>
            <textarea
              value={sourceContent}
              onChange={(event) => setSourceContent(event.target.value)}
              placeholder={t('aiReviewEditor.create.placeholders.sourceContent')}
              className={`${fieldControlClass} min-h-[320px] resize-y`}
            />
          </label>

          <div className="rounded-3xl border border-stone-200 bg-stone-50/90 p-4 text-sm text-stone-700 dark:border-slate-800 dark:bg-slate-900/85 dark:text-slate-200">
            <p className="font-semibold text-stone-900 dark:text-slate-100">
              {t('aiReviewEditor.create.htmlOnlyTitle')}
            </p>
            <p className="mt-1">{t('aiReviewEditor.create.htmlOnlyDescription')}</p>
            <p className="mt-3">{t('aiReviewEditor.create.nextStepHint')}</p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={createDocumentMutation.isPending} className={primaryActionClass}>
              {createDocumentMutation.isPending
                ? t('aiReviewEditor.actions.creatingDocument')
                : t('aiReviewEditor.actions.createDocument')}
            </button>
            <Link to={documentsPath} className={secondaryActionClass}>
              {t('aiReviewEditor.actions.openDocuments')}
            </Link>
          </div>
        </form>
      </section>
    </div>
  )
}
