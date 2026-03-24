import { render, screen } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import { describe, expect, test } from 'vitest'

import i18n from '../i18n'
import { DataTable } from './DataTable'

describe('DataTable', () => {
  test('keeps headers and cells nowrap by default and supports per-column minWidth', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <DataTable
          columns={[
            {
              key: 'title',
              header: 'Title',
              sortKey: 'title',
              minWidth: 320,
              cell: (row: { title: string }) => row.title,
            },
            {
              key: 'status',
              header: 'Status',
              minWidth: 90,
              cell: (row: { status: string }) => row.status,
            },
          ]}
          rows={[{ id: 1, title: 'Alpha', status: '200' }]}
          rowKey={(row) => row.id}
          sortBy="title"
          sortOrder="asc"
          onSortChange={() => {}}
        />
      </I18nextProvider>,
    )

    const table = screen.getByRole('table')
    expect(table.parentElement).toHaveClass('overflow-x-auto')

    const titleHeader = screen.getByText('Title').closest('th')
    const titleCell = screen.getByText('Alpha').closest('td')
    const statusCell = screen.getByText('200').closest('td')

    expect(titleHeader).toHaveClass('whitespace-nowrap')
    expect(titleHeader).toHaveStyle({ minWidth: '320px' })
    expect(titleCell).toHaveClass('whitespace-nowrap')
    expect(titleCell).toHaveStyle({ minWidth: '320px' })
    expect(statusCell).toHaveStyle({ minWidth: '90px' })
  })
})
