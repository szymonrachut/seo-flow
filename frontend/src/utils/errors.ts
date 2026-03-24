import type { TFunction } from 'i18next'

import { ApiError, getApiBaseUrl } from '../api/client'

export function getUiErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError && error.status === 0 && error.detail === 'NETWORK_UNAVAILABLE') {
    return t('errors.networkUnavailable', { apiBaseUrl: getApiBaseUrl() })
  }

  if (error instanceof Error) {
    return error.message
  }

  return t('common.unknownError')
}
