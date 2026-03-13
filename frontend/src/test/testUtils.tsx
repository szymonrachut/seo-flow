import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

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
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path={path} element={<>{ui}{showLocation ? <LocationEcho /> : null}</>} />
          {extraRoutes}
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )

  return {
    user,
    queryClient,
    ...result,
  }
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
