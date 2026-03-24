import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

import i18n, { LANGUAGE_STORAGE_KEY, normalizeLanguage, type AppLanguage } from '../i18n'

interface RenderRouteOptions {
  path: string
  route: string
  extraRoutes?: ReactElement[]
  showLocation?: boolean
}

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

export function renderRoute(
  ui: ReactElement,
  { path, route, extraRoutes = [], showLocation = false }: RenderRouteOptions,
) {
  const queryClient = createTestQueryClient()
  const user = userEvent.setup()

  const result = render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path={path} element={<>{ui}{showLocation ? <LocationEcho /> : null}</>} />
            {extraRoutes}
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  )

  return {
    user,
    queryClient,
    ...result,
  }
}

export async function setTestLanguage(language: AppLanguage) {
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  await i18n.changeLanguage(language)
}

export async function syncTestLanguageFromStorage() {
  await i18n.changeLanguage(normalizeLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)))
}

export function jsonResponse(body: unknown, init?: ResponseInit) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: init?.status ?? 200,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    }),
  )
}

export function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void

  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })

  return { promise, resolve, reject }
}

function LocationEcho() {
  const location = useLocation()
  return <output data-testid="location-search">{location.search}</output>
}
