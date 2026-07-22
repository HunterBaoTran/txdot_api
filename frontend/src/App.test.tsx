import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

class MockWebSocket {
  static OPEN = 1
  readyState = 1
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor() { setTimeout(() => this.onopen?.(), 0) }
  close() {}
}

describe('Veratex dashboard', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [] }))
    vi.stubGlobal('ResizeObserver', class { observe() {}; unobserve() {}; disconnect() {} })
  })

  it('renders the operational dashboard and deterministic source control', () => {
    render(<App />)
    expect(screen.getByText('Table intelligence, at a glance.')).toBeInTheDocument()
    expect(screen.getByText('Live annotated feed')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Camera' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Generated MP4 loop' })).toBeInTheDocument()
    expect(screen.getByText('Anonymous operational analytics only')).toBeInTheDocument()
  })
})
