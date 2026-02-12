/**
 * Input Workpiece Block Component
 * Displays and edits input workpiece parameters with dynamic geometry types
 */

import type { BlockComponentProps } from './BlockRegistry'

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
      <button
        type="button"
        onClick={onClick}
        className="h-8 w-8 flex-shrink-0 border border-red-300 rounded text-red-700 bg-red-50 hover:bg-red-100"
        title="Revert this parameter"
      >
        ↺
      </button>
    )
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-900">{title}</h2>
      </div>

      <table className="w-full border-collapse">
        <tbody>
          <tr className="border-b">
            <td className="py-3 px-4 font-semibold bg-gray-50 w-1/2">Geometry Type:</td>
            <td className="py-3 px-4">
              {isReadOnly ? (
                <span className="text-gray-900">
                  {selectedGeometry ? selectedGeometry.library_name : 'Not set'}
                </span>
              ) : (
                <div className="flex items-start gap-2">
                  <select
                    value={normalizeComparable(block.props.geometry_type_id)}
                    onChange={(event) => handleGeometryTypeChange(event.target.value)}
                    className={`w-full px-2 py-1 border rounded ${
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
                  <td className="py-3 px-4 font-semibold bg-gray-50">{label}</td>
                  <td className="py-3 px-4">
                    {isReadOnly ? (
                      <span className="text-gray-900">{currentValue || '-'}</span>
                    ) : (
                      <div className="flex items-start gap-2">
                        <input
                          type="number"
                          step="0.001"
                          value={currentValue}
                          onChange={(event) => handleAttributeChange(colName, event.target.value)}
                          className={`w-full px-2 py-1 border rounded ${
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
            <td className="py-3 px-4 font-semibold bg-gray-50">Weight [kg]:</td>
            <td className="py-3 px-4">
              {isReadOnly ? (
                <span className="text-gray-900">{block.props.weight ?? 0}</span>
              ) : (
                <div className="flex items-start gap-2">
                  <input
                    type="number"
                    step="0.001"
                    min="0"
                    value={normalizeComparable(block.props.weight)}
                    onChange={(event) => handleFieldChange('weight', event.target.value)}
                    className={`w-full px-2 py-1 border rounded ${
                      isFieldDirty('weight') ? 'border-red-300 bg-red-50' : 'border-gray-300'
                    }`}
                  />
                  {renderResetButton(() => resetField('weight'), isFieldDirty('weight'))}
                </div>
              )}
            </td>
          </tr>

          <tr>
            <td className="py-3 px-4 font-semibold bg-gray-50">
              Elements across width [pcs]:
            </td>
            <td className="py-3 px-4">
              {isReadOnly ? (
                <span className="text-gray-900">{block.props.mesh_elements ?? 0}</span>
              ) : (
                <div className="flex items-start gap-2">
                  <input
                    type="number"
                    step="1"
                    min="0"
                    value={normalizeComparable(block.props.mesh_elements)}
                    onChange={(event) => handleFieldChange('mesh_elements', event.target.value)}
                    className={`w-full px-2 py-1 border rounded ${
                      isFieldDirty('mesh_elements')
                        ? 'border-red-300 bg-red-50'
                        : 'border-gray-300'
                    }`}
                  />
                  {renderResetButton(
                    () => resetField('mesh_elements'),
                    isFieldDirty('mesh_elements')
                  )}
                </div>
              )}
            </td>
          </tr>
        </tbody>
      </table>

      {block.is_system && (
        <div className="mt-4 text-xs text-gray-500 italic">
          * This is a required system block and cannot be removed
        </div>
      )}
    </div>
  )
}
