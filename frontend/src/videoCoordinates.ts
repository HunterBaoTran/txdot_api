export interface DisplayBounds {
  x: number
  y: number
  width: number
  height: number
}

export function containedMediaBounds(
  containerWidth: number,
  containerHeight: number,
  mediaWidth: number,
  mediaHeight: number,
): DisplayBounds {
  if (mediaWidth <= 0 || mediaHeight <= 0) {
    return { x: 0, y: 0, width: containerWidth, height: containerHeight }
  }
  const scale = Math.min(containerWidth / mediaWidth, containerHeight / mediaHeight)
  const width = mediaWidth * scale
  const height = mediaHeight * scale
  return { x: (containerWidth - width) / 2, y: (containerHeight - height) / 2, width, height }
}

export function displayToNormalized(
  x: number,
  y: number,
  bounds: DisplayBounds,
): [number, number] | null {
  if (x < bounds.x || y < bounds.y || x > bounds.x + bounds.width || y > bounds.y + bounds.height) {
    return null
  }
  return [
    Math.min(1, Math.max(0, (x - bounds.x) / bounds.width)),
    Math.min(1, Math.max(0, (y - bounds.y) / bounds.height)),
  ]
}

export function normalizedToDisplay(
  point: [number, number],
  bounds: DisplayBounds,
): [number, number] {
  return [bounds.x + point[0] * bounds.width, bounds.y + point[1] * bounds.height]
}

export function movePolygonVertex(
  points: [number, number][],
  index: number,
  point: [number, number],
) {
  return points.map((current, item) => item === index ? point : current)
}
