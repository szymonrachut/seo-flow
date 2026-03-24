import type { TFunction } from 'i18next'

import { normalizeLanguage } from '../../i18n'

const LEAD_TRANSLATION_KEYS: Record<string, string> = {
  'URL sits in the 4-15 position range with room to improve snippet or on-page signals':
    'opportunities.rationaleText.leads.quickWins',
  'URL has high impressions and low CTR with snippet issues':
    'opportunities.rationaleText.leads.highImpressionsLowCtr',
  'URL already gets traffic or impressions but still has technical issues':
    'opportunities.rationaleText.leads.trafficWithTechnicalIssues',
  'URL matters in search but quality signals remain weak':
    'opportunities.rationaleText.leads.importantButWeak',
  'URL has relatively low-effort fixes with meaningful search potential':
    'opportunities.rationaleText.leads.lowHangingFruit',
  'URL already has visibility but is exposed to a high-risk indexability or canonical problem':
    'opportunities.rationaleText.leads.highRiskPages',
  'URL shows demand but has weak internal linking support':
    'opportunities.rationaleText.leads.underlinked',
}

const ISSUE_TRANSLATION_KEYS: Record<string, string> = {
  'missing title': 'opportunities.rationaleText.issues.titleMissing',
  'title too short': 'opportunities.rationaleText.issues.titleTooShort',
  'title too long': 'opportunities.rationaleText.issues.titleTooLong',
  'missing meta description': 'opportunities.rationaleText.issues.metaDescriptionMissing',
  'meta description too short': 'opportunities.rationaleText.issues.metaDescriptionTooShort',
  'meta description too long': 'opportunities.rationaleText.issues.metaDescriptionTooLong',
  'missing H1': 'opportunities.rationaleText.issues.h1Missing',
  'multiple H1': 'opportunities.rationaleText.issues.multipleH1',
  'missing H2': 'opportunities.rationaleText.issues.h2Missing',
  'missing canonical': 'opportunities.rationaleText.issues.canonicalMissing',
  'canonical points to another URL': 'opportunities.rationaleText.issues.canonicalToOtherUrl',
  'canonical target is non-200': 'opportunities.rationaleText.issues.canonicalToNon200',
  'canonical target redirects': 'opportunities.rationaleText.issues.canonicalToRedirect',
  'page looks noindex-like': 'opportunities.rationaleText.issues.noindexLike',
  'page looks non-indexable': 'opportunities.rationaleText.issues.nonIndexableLike',
  'thin content': 'opportunities.rationaleText.issues.thinContent',
  'duplicate content': 'opportunities.rationaleText.issues.duplicateContent',
  'missing alt text': 'opportunities.rationaleText.issues.missingAltText',
  'oversized page': 'opportunities.rationaleText.issues.oversized',
}

export function localizeOpportunityRationale(
  rationale: string,
  language: string | null | undefined,
  t: TFunction,
) {
  if (!rationale || normalizeLanguage(language) !== 'pl') {
    return rationale
  }

  const trimmed = rationale.trim()

  const leadMatch = /^(.*?): (.*); issues: (.*?)(?:\.)?$/.exec(trimmed)
  if (leadMatch) {
    return t('opportunities.rationaleText.templates.leadWithIssues', {
      lead: translateLead(leadMatch[1], t),
      traffic: translateTrafficText(leadMatch[2], t),
      issues: translateIssueText(leadMatch[3], t),
    })
  }

  const trafficWithIssuesMatch = /^URL has (.+) with (.+?)(?:\.)?$/.exec(trimmed)
  if (trafficWithIssuesMatch) {
    return t('opportunities.rationaleText.templates.trafficWithIssues', {
      traffic: translateTrafficText(trafficWithIssuesMatch[1], t),
      issues: translateIssueText(trafficWithIssuesMatch[2], t),
    })
  }

  const trafficLimitedIssuesMatch = /^URL has (.+?) but limited actionable issues\.?$/.exec(trimmed)
  if (trafficLimitedIssuesMatch) {
    return t('opportunities.rationaleText.templates.trafficLimitedIssues', {
      traffic: translateTrafficText(trafficLimitedIssuesMatch[1], t),
    })
  }

  const issuesNoTrafficMatch = /^URL has (.+?) but no strong traffic signal in the selected GSC range\.?$/.exec(trimmed)
  if (issuesNoTrafficMatch) {
    return t('opportunities.rationaleText.templates.issuesNoTraffic', {
      issues: translateIssueText(issuesNoTrafficMatch[1], t),
    })
  }

  if (trimmed === 'URL has search demand but weak internal linking support.') {
    return t('opportunities.rationaleText.templates.weakInternalLinking')
  }

  if (trimmed === 'URL has low traffic and limited optimization pressure in the selected GSC range.') {
    return t('opportunities.rationaleText.templates.lowTrafficLowPressure')
  }

  return trimmed
}

function translateLead(lead: string, t: TFunction) {
  const key = LEAD_TRANSLATION_KEYS[lead]
  return key ? t(key) : lead
}

function translateTrafficText(text: string, t: TFunction) {
  const trimmed = text.trim()
  if (trimmed === 'no meaningful traffic signal') {
    return t('opportunities.rationaleText.tokens.noMeaningfulTrafficSignal')
  }

  return trimmed
    .replace(/\b(\d+)\s+impressions\b/g, (_, value: string) =>
      t('opportunities.rationaleText.metrics.impressions', { value }),
    )
    .replace(/\b(\d+)\s+clicks\b/g, (_, value: string) =>
      t('opportunities.rationaleText.metrics.clicks', { value }),
    )
    .replace(/\bCTR\s+([\d.]+%)\b/g, (_, value: string) =>
      t('opportunities.rationaleText.metrics.ctr', { value }),
    )
    .replace(/\bposition\s+([\d.]+)\b/g, (_, value: string) =>
      t('opportunities.rationaleText.metrics.position', { value }),
    )
    .replace(/\sand\s/g, ' i ')
}

function translateIssueText(text: string, t: TFunction) {
  const trimmed = text.trim()
  if (trimmed === 'limited issue depth') {
    return t('opportunities.rationaleText.tokens.limitedIssueDepth')
  }

  return trimmed
    .split(', ')
    .map((issue) => translateIssueLabel(issue, t))
    .join(', ')
}

function translateIssueLabel(issue: string, t: TFunction) {
  const trimmed = issue.trim()
  const key = ISSUE_TRANSLATION_KEYS[trimmed]
  if (key) {
    return t(key)
  }

  const internalLinksMatch = /^(\d+)\s+internal links$/.exec(trimmed)
  if (internalLinksMatch) {
    return t('opportunities.rationaleText.metrics.internalLinks', { value: internalLinksMatch[1] })
  }

  const linkingPagesMatch = /^(\d+)\s+linking pages$/.exec(trimmed)
  if (linkingPagesMatch) {
    return t('opportunities.rationaleText.metrics.linkingPages', { value: linkingPagesMatch[1] })
  }

  return trimmed
}
