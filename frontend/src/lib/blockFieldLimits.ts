export type FieldLimits = Record<string, number>

interface BlockWithFieldLimits {
  field_limits?: FieldLimits
}

function applyLimitAtPath(target: unknown, pathSegments: string[], maxLength: number): boolean {
  if (!target || typeof target !== 'object' || pathSegments.length === 0) {
    return false
  }

  const [segment, ...rest] = pathSegments

  if (segment === '*') {
    let changed = false

    if (Array.isArray(target)) {
      for (const entry of target) {
        changed = applyLimitAtPath(entry, rest, maxLength) || changed
      }
      return changed
    }

    const record = target as Record<string, unknown>
    for (const key of Object.keys(record)) {
      changed = applyLimitAtPath(record[key], rest, maxLength) || changed
    }
    return changed
  }

  const record = target as Record<string, unknown>
  if (!Object.prototype.hasOwnProperty.call(record, segment)) {
    return false
  }

  if (rest.length === 0) {
    const value = record[segment]
    if (typeof value === 'string' && value.length > maxLength) {
      record[segment] = value.slice(0, maxLength)
      return true
    }
    return false
  }

  return applyLimitAtPath(record[segment], rest, maxLength)
}

export function getFieldMaxLength(
  block: BlockWithFieldLimits,
  fieldPath: string
): number | undefined {
  const value = block.field_limits?.[fieldPath]
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    return undefined
  }
  return Math.floor(value)
}

export function applyFieldLengthLimits(
  props: Record<string, any>,
  fieldLimits?: FieldLimits
): Record<string, any> {
  if (!fieldLimits || Object.keys(fieldLimits).length === 0) {
    return props
  }

  const constrainedProps = JSON.parse(JSON.stringify(props || {})) as Record<string, any>
  let changed = false

  for (const [fieldPath, rawLimit] of Object.entries(fieldLimits)) {
    const limit = Number(rawLimit)
    if (!fieldPath || !Number.isFinite(limit) || limit <= 0) {
      continue
    }

    changed =
      applyLimitAtPath(constrainedProps, fieldPath.split('.'), Math.floor(limit)) || changed
  }

  return changed ? constrainedProps : props
}
