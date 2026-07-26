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

export function initialAssistantFloatPosition(bounds: FloatBounds): FloatPosition {
  return clampAssistantFloatPosition({
    ...bounds,
    x: bounds.viewportWidth - bounds.panelWidth - 32,
    y: 112,
  })
}
