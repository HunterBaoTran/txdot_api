import { describe, expect, it } from 'vitest'
import { containedMediaBounds, displayToNormalized, movePolygonVertex, normalizedToDisplay } from './videoCoordinates'

describe('video coordinate mapping', () => {
  it('accounts for horizontal letterboxing', () => {
    const bounds = containedMediaBounds(1000, 500, 1000, 1000)
    expect(bounds).toEqual({ x: 250, y: 0, width: 500, height: 500 })
    expect(displayToNormalized(250, 0, bounds)).toEqual([0, 0])
    expect(displayToNormalized(750, 500, bounds)).toEqual([1, 1])
    expect(displayToNormalized(100, 250, bounds)).toBeNull()
  })

  it('round trips normalized polygon points after resize', () => {
    const bounds = containedMediaBounds(640, 360, 1920, 1080)
    const shown = normalizedToDisplay([0.25, 0.75], bounds)
    expect(displayToNormalized(shown[0], shown[1], bounds)).toEqual([0.25, 0.75])
  })

  it('moves only the selected polygon vertex', () => {
    expect(movePolygonVertex([[0.1, 0.1], [0.4, 0.1], [0.4, 0.4]], 0, [0.2, 0.2]))
      .toEqual([[0.2, 0.2], [0.4, 0.1], [0.4, 0.4]])
  })
})
