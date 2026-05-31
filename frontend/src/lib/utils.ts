export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }

  // Fallback for older environments
  const bytes = new Uint8Array(16)
  for (let i = 0; i < bytes.length; i += 1) {
    bytes[i] = Math.floor(Math.random() * 256)
  }

  // RFC4122 version 4
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80

  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'))
  return (
    `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-` +
    `${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-` +
    `${hex.slice(10, 16).join('')}`
  )
}

export function getDeviceId(): string {
  const storageKey = 'device_id'
  let deviceId = localStorage.getItem(storageKey)
  if (!deviceId) {
    deviceId = generateUUID()
    localStorage.setItem(storageKey, deviceId)
  }
  return deviceId
}

export function extractField<T>(
  data: Record<string, unknown> | undefined,
  ...keys: string[]
): T | undefined {
  if (!data) {
    return undefined
  }

  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(data, key)) {
      const value = data[key]
      if (value !== undefined && value !== null) {
        return value as T
      }
    }
  }

  return undefined
}
