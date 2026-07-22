import '@testing-library/jest-dom/vitest'

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = TestResizeObserver
globalThis.PointerEvent = MouseEvent as typeof PointerEvent
