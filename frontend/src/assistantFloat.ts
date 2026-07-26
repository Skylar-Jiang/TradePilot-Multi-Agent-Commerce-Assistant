type FloatPosition = {
  x: number
  y: number
}

type FloatBounds = {
  viewportWidth: number
  viewportHeight: number
  panelWidth: number
  panelHeight: number
}

const MIN_X = 24
const MIN_Y = 96
const MIN_WIDTH = 340
const MIN_HEIGHT = 420
const clamp = (value: number, minimum: number, maximum: number) => Math.min(Math.max(value, minimum), maximum)

export function clampAssistantFloatPosition(position: FloatPosition & FloatBounds): FloatPosition {
  const maxX = Math.max(MIN_X, position.viewportWidth - position.panelWidth - MIN_X)
  const maxY = Math.max(
    MIN_Y,
    Math.min(position.viewportHeight - position.panelHeight - MIN_X, Math.floor(position.viewportHeight * 0.45)),
  )

  return {
    x: clamp(position.x, MIN_X, maxX),
    y: clamp(position.y, MIN_Y, maxY),
  }
}

export function draggedAssistantFloatPosition({
  pointerX,
  pointerY,
  grabOffsetX,
  grabOffsetY,
  ...bounds
}: {
  pointerX: number
  pointerY: number
  grabOffsetX: number
  grabOffsetY: number
} & FloatBounds): FloatPosition {
  return clampAssistantFloatPosition({
    ...bounds,
    x: pointerX - grabOffsetX,
    y: pointerY - grabOffsetY,
  })
}

export function initialAssistantFloatPosition(bounds: FloatBounds): FloatPosition {
  return clampAssistantFloatPosition({
    ...bounds,
    x: bounds.viewportWidth - bounds.panelWidth - 32,
    y: 112,
  })
}

export function resizedAssistantFloatSize({
  pointerX,
  pointerY,
  startPointerX,
  startPointerY,
  startWidth,
  startHeight,
  panelX,
  panelY,
  viewportWidth,
  viewportHeight,
}: {
  pointerX: number
  pointerY: number
  startPointerX: number
  startPointerY: number
  startWidth: number
  startHeight: number
  panelX: number
  panelY: number
  viewportWidth: number
  viewportHeight: number
}) {
  const maxWidth = Math.max(1, viewportWidth - panelX - MIN_X)
  const maxHeight = Math.max(1, viewportHeight - panelY - MIN_X)

  return {
    width: clamp(startWidth + pointerX - startPointerX, Math.min(MIN_WIDTH, maxWidth), maxWidth),
    height: clamp(startHeight + pointerY - startPointerY, Math.min(MIN_HEIGHT, maxHeight), maxHeight),
  }
}
