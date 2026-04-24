/**
 * Input Workpiece Block Component
 * Displays and edits input workpiece parameters with dynamic geometry types
 */

import type { BlockComponentProps } from './BlockRegistry'
import Tooltip from '../ui/Tooltip'

interface GeometryType {
  id: string
  name: string
  labels: string[]
  columns: string[]
}

function normalizeComparable(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

export default function InputWorkpieceBlock({
  block,
  baselineProps,
  onUpdate,
  isReadOnly = false,
}: BlockComponentProps) {
  const handleFieldChange = (field: string, value: unknown) => {
    onUpdate(block.block_id, {
      ...(block.props || {}),
      [field]: value,
    })
  }

  const handleAttributeChange = (attrName: string, value: string) => {
    onUpdate(block.block_id, {
      ...(block.props || {}),
      attributes: {
        ...(block.props?.attributes || {}),
        [attrName]: value,
      },
    })
  }

  const handleGeometryTypeChange = (newTypeId: string) => {
    const selectedType = availableGeometryTypes.find((t) => t.id === newTypeId)
    const newAttributes: Record<string, string> = {}

    if (selectedType) {
      selectedType.columns.forEach((col) => {
        newAttributes[col] = ''
      })
    }

    onUpdate(block.block_id, {
      ...(block.props || {}),
      geometry_type_id: newTypeId,
      attributes: newAttributes,
    })
  }

  const resetField = (field: string) => {
    handleFieldChange(field, baselineProps?.[field] ?? '')
  }

  const resetGeometryType = () => {
    onUpdate(block.block_id, {
      ...(block.props || {}),
      geometry_type_id: baselineProps?.geometry_type_id ?? '',
      attributes: {
        ...(baselineProps?.attributes || {}),
      },
    })
  }

  const resetAttribute = (attrName: string) => {
    const baselineValue = baselineProps?.attributes?.[attrName] ?? ''
    handleAttributeChange(attrName, normalizeComparable(baselineValue))
  }

  const availableGeometryTypes: GeometryType[] = block.props.available_geometry_types || []

  const currentGeometryTypeId = normalizeComparable(block.props.geometry_type_id)
  const currentGeometry = currentGeometryTypeId
    ? availableGeometryTypes.find((g) => g.id === currentGeometryTypeId)
    : null

  const selectedGeometry = currentGeometry || block.props.selected_geometry || null
  const title = block.props.title || 'Input Workpiece'

  const isFieldDirty = (field: string) =>
    normalizeComparable(block.props?.[field]) !== normalizeComparable(baselineProps?.[field])

  const isAttributeDirty = (attrName: string) =>
    normalizeComparable(block.props?.attributes?.[attrName]) !==
    normalizeComparable(baselineProps?.attributes?.[attrName])

  const renderResetButton = (onClick: () => void, dirty: boolean) => {
    if (isReadOnly || !dirty) {
      return null
    }

    return (
      <Tooltip content="Revert this parameter">
        <button
          type="button"
          onClick={onClick}
          className="ui-btn-danger h-8 w-8 p-0 flex-shrink-0"
          aria-label="Revert this parameter"
        >
          ↺
        </button>
      </Tooltip>
    )
  }

  return (
    <div className="ui-card ui-card-body text-sm">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-gray-900">{title}</h2>
      </div>

      <table className="w-full border-collapse">
        <tbody>
          <tr className="border-b">
            <td className="py-1 px-2 font-semibold bg-gray-50 w-1/2">Geometry Type:</td>
            <td className="py-1 px-2">
              {isReadOnly ? (
                <div className="ui-field-readonly">
                  {selectedGeometry ? selectedGeometry.library_name : 'Not set'}
                </div>
              ) : (
                <div className="flex items-start gap-2">
                  <select
                    value={normalizeComparable(block.props.geometry_type_id)}
                    onChange={(event) => handleGeometryTypeChange(event.target.value)}
                    className={`ui-select ${
                      isFieldDirty('geometry_type_id')
                        ? 'border-red-300 bg-red-50'
                        : 'border-gray-300'
                    }`}
                  >
                    <option value="">Select geometry type...</option>
                    {availableGeometryTypes.map((geom) => (
                      <option key={geom.id} value={geom.id}>
                        {geom.name}
                      </option>
                    ))}
                  </select>
                  {renderResetButton(
                    resetGeometryType,
                    isFieldDirty('geometry_type_id')
                  )}
                </div>
              )}
            </td>
          </tr>

          {selectedGeometry &&
            selectedGeometry.columns.map((colName: string, index: number) => {
              const label = selectedGeometry.labels[index] || colName
              const currentValue = normalizeComparable(block.props.attributes?.[colName])
              const dirty = isAttributeDirty(colName)

              return (
                <tr key={colName} className="border-b">
                  <td className="py-1 px-2 font-semibold bg-gray-50">{label}</td>
                  <td className="py-1 px-2">
                    {isReadOnly ? (
                      <div className="ui-field-readonly">{currentValue || '-'}</div>
                    ) : (
                      <div className="flex items-start gap-2">
                        <input
                          type="number"
                          step="0.001"
                          value={currentValue}
                          onChange={(event) => handleAttributeChange(colName, event.target.value)}
                          className={`ui-input ${
                            dirty ? 'border-red-300 bg-red-50' : 'border-gray-300'
                          }`}
                          placeholder={`Enter ${label.toLowerCase()}`}
                        />
                        {renderResetButton(() => resetAttribute(colName), dirty)}
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}

          <tr className="border-b">
            <td className="py-1 px-2 font-semibold bg-gray-50">Weight [kg]:</td>
            <td className="py-1 px-2">
              {isReadOnly ? (
                <div className="ui-field-readonly">{block.props.weight ?? 0}</div>
              ) : (
                <div className="flex items-start gap-2">
                  <input
                    type="number"
                    step="0.001"
                    min="0"
                    value={normalizeComparable(block.props.weight)}
                    onChange={(event) => handleFieldChange('weight', event.target.value)}
                    className={`ui-input ${
                      isFieldDirty('weight') ? 'border-red-300 bg-red-50' : 'border-gray-300'
                    }`}
                  />
                  {renderResetButton(() => resetField('weight'), isFieldDirty('weight'))}
                </div>
              )}
            </td>
          </tr>

        </tbody>
      </table>

      {block.is_system && (
        <div className="mt-3 text-xs text-gray-500 italic">
          * This is a required system block and cannot be removed
        </div>
      )}
    </div>
  )
}
