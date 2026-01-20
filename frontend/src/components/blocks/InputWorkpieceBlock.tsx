/**
 * Input Workpiece Block Component
 * Displays and edits input workpiece parameters with dynamic geometry types
 */

import { useState, useEffect } from 'react'
import type { BlockComponentProps } from './BlockRegistry'

interface GeometryType {
  id: string
  name: string
  labels: string[]
  columns: string[]
}

export default function InputWorkpieceBlock({
  block,
  onUpdate,
  isReadOnly = false,
}: BlockComponentProps) {
  const [editedData, setEditedData] = useState<Record<string, any>>(block.props)
  const [isEditing, setIsEditing] = useState(false)

  useEffect(() => {
    setEditedData(block.props)
  }, [block.props])

  const handleFieldChange = (field: string, value: any) => {
    setEditedData((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleAttributeChange = (attrName: string, value: string) => {
    setEditedData((prev) => ({
      ...prev,
      attributes: {
        ...prev.attributes,
        [attrName]: value,
      },
    }))
  }

  const handleGeometryTypeChange = (newTypeId: string) => {
    // When geometry type changes, initialize attributes with empty values
    const selectedType = availableGeometryTypes.find((t) => t.id === newTypeId)
    const newAttributes: Record<string, string> = {}

    if (selectedType) {
      // Initialize all attributes for the selected geometry type with empty strings
      selectedType.columns.forEach((col) => {
        newAttributes[col] = ''
      })
    }

    setEditedData((prev) => ({
      ...prev,
      geometry_type_id: newTypeId,
      attributes: newAttributes,
    }))
  }

  const handleSave = () => {
    onUpdate(block.block_id, editedData)
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditedData(block.props)
    setIsEditing(false)
  }

  const availableGeometryTypes: GeometryType[] = block.props.available_geometry_types || []

  // Get the currently selected geometry type based on edit state
  const currentGeometryTypeId = isEditing
    ? editedData.geometry_type_id
    : block.props.geometry_type_id

  // Find the geometry definition for the current type
  const currentGeometry = currentGeometryTypeId
    ? availableGeometryTypes.find((g) => g.id === currentGeometryTypeId)
    : null

  const selectedGeometry = block.props.selected_geometry || null
  const title = block.props.title || 'Input Workpiece'

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-900">{title}</h2>
        {!isReadOnly && (
          <div className="flex gap-2">
            {!isEditing ? (
              <button
                onClick={() => setIsEditing(true)}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Edit
              </button>
            ) : (
              <>
                <button
                  onClick={handleCancel}
                  className="px-4 py-2 text-sm border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Save
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Fields Table */}
      <table className="w-full border-collapse">
        <tbody>
          {/* Geometry Type Selector */}
          <tr className="border-b">
            <td className="py-3 px-4 font-semibold bg-gray-50 w-1/2">Geometry Type:</td>
            <td className="py-3 px-4">
              {isEditing && !isReadOnly ? (
                <select
                  value={editedData.geometry_type_id ?? ''}
                  onChange={(e) => handleGeometryTypeChange(e.target.value)}
                  className="w-full px-2 py-1 border border-gray-300 rounded"
                >
                  <option value="">Select geometry type...</option>
                  {availableGeometryTypes.map((geom) => (
                    <option key={geom.id} value={geom.id}>
                      {geom.name}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-gray-900">
                  {selectedGeometry ? selectedGeometry.library_name : 'Not set'}
                </span>
              )}
            </td>
          </tr>

          {/* Dynamic Attributes based on selected geometry type */}
          {(isEditing ? currentGeometry : selectedGeometry) &&
            (isEditing ? currentGeometry : selectedGeometry).columns.map((colName: string, index: number) => {
              const geom = isEditing ? currentGeometry : selectedGeometry
              const label = geom.labels[index] || colName
              const currentValue = editedData.attributes?.[colName] ?? block.props.attributes?.[colName] ?? ''

              return (
                <tr key={colName} className="border-b">
                  <td className="py-3 px-4 font-semibold bg-gray-50">{label}</td>
                  <td className="py-3 px-4">
                    {isEditing && !isReadOnly ? (
                      <input
                        type="number"
                        step="0.001"
                        value={currentValue}
                        onChange={(e) => handleAttributeChange(colName, e.target.value)}
                        className="w-full px-2 py-1 border border-gray-300 rounded"
                        placeholder={`Enter ${label.toLowerCase()}`}
                      />
                    ) : (
                      <span className="text-gray-900">{currentValue || '-'}</span>
                    )}
                  </td>
                </tr>
              )
            })}

          {/* Weight */}
          <tr className="border-b">
            <td className="py-3 px-4 font-semibold bg-gray-50">Weight [kg]:</td>
            <td className="py-3 px-4">
              {isEditing && !isReadOnly ? (
                <input
                  type="number"
                  step="0.001"
                  min="0"
                  value={editedData.weight ?? block.props.weight ?? 0}
                  onChange={(e) => handleFieldChange('weight', parseFloat(e.target.value) || 0)}
                  className="w-full px-2 py-1 border border-gray-300 rounded"
                />
              ) : (
                <span className="text-gray-900">{block.props.weight ?? 0}</span>
              )}
            </td>
          </tr>

          {/* Elements across width */}
          <tr>
            <td className="py-3 px-4 font-semibold bg-gray-50">
              Elements across width [pcs]:
            </td>
            <td className="py-3 px-4">
              {isEditing && !isReadOnly ? (
                <input
                  type="number"
                  step="1"
                  min="0"
                  value={editedData.mesh_elements ?? block.props.mesh_elements ?? 0}
                  onChange={(e) => handleFieldChange('mesh_elements', parseInt(e.target.value) || 0)}
                  className="w-full px-2 py-1 border border-gray-300 rounded"
                />
              ) : (
                <span className="text-gray-900">{block.props.mesh_elements ?? 0}</span>
              )}
            </td>
          </tr>
        </tbody>
      </table>

      {/* System block indicator */}
      {block.is_system && (
        <div className="mt-4 text-xs text-gray-500 italic">
          * This is a required system block and cannot be removed
        </div>
      )}
    </div>
  )
}
