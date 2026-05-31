const LOCALIZED_NAME_KEYS = ['EN', 'RU', 'ZH_HANS']

export function formatLibraryName(value: unknown): string {
  if (typeof value === 'string') {
    return value
  }

  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>

    for (const key of LOCALIZED_NAME_KEYS) {
      const entry = record[key]
      if (typeof entry === 'string' && entry.trim().length > 0) {
        return entry
      }
    }

    for (const entry of Object.values(record)) {
      if (typeof entry === 'string' && entry.trim().length > 0) {
        return entry
      }
    }
  }

  if (value === null || value === undefined) {
    return ''
  }

  return String(value)
}

export function formatTimestamp(value?: string | null): string {
  if (!value) {
    return '-'
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return parsed.toLocaleString()
}
