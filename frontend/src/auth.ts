const ACCESS_CODE_STORAGE_KEY = 'tradepilot-shared-access-code'

export const ACCESS_CLEARED_EVENT = 'tradepilot:shared-access-cleared'

export function getSharedAccessCode(): string | null {
  return sessionStorage.getItem(ACCESS_CODE_STORAGE_KEY)
}

export function hasSharedAccessCode(): boolean {
  return Boolean(getSharedAccessCode())
}

export function saveSharedAccessCode(accessCode: string): void {
  sessionStorage.setItem(ACCESS_CODE_STORAGE_KEY, accessCode)
}

export function clearSharedAccessCode(): void {
  sessionStorage.removeItem(ACCESS_CODE_STORAGE_KEY)
  window.dispatchEvent(new Event(ACCESS_CLEARED_EVENT))
}
