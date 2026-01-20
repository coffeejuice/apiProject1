/**
 * Process Heading Block Component
 * Displays process metadata in a table format mimicking a title page
 */

import { useState, useEffect } from 'react'
import type { BlockComponentProps } from './BlockRegistry'

export default function ProcessHeadingBlock({
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

  const handleSave = () => {
    onUpdate(block.block_id, editedData)
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditedData(block.props)
    setIsEditing(false)
  }

  // Field length limits (must match backend validation) - all fields are strings
  const fieldLimits: Record<string, number> = {
    title: 1024,
    heat_no: 511,
    finished_size: 511,
    stock_size: 511,
    stock_weight: 511,
    remarks: 4095,
  }

  const renderField = (label: string, field: string, value: any) => {
    if (isEditing && !isReadOnly) {
      const currentValue = editedData[field] ?? value ?? ''
      const maxLength = fieldLimits[field]
      const isOverLimit = maxLength && currentValue.length > maxLength

      return (
        <div className="w-full">
          <input
            type="text"
            value={currentValue}
            onChange={(e) => handleFieldChange(field, e.target.value)}
            className={`w-full px-2 py-1 border rounded ${
              isOverLimit ? 'border-red-500 bg-red-50' : 'border-gray-300'
            }`}
            maxLength={maxLength || undefined}
          />
          {maxLength && (
            <div
              className={`text-xs mt-1 ${
                isOverLimit ? 'text-red-600' : 'text-gray-500'
              }`}
            >
              {currentValue.length} / {maxLength} characters
            </div>
          )}
        </div>
      )
    }
    return <span className="text-gray-900">{value ?? ''}</span>
  }

  const renderNumberField = (label: string, field: string, value: any) => {
    if (isEditing && !isReadOnly) {
      return (
        <input
          type="number"
          step="0.01"
          value={editedData[field] ?? value ?? 0}
          onChange={(e) => handleFieldChange(field, parseFloat(e.target.value) || 0)}
          className="w-full px-2 py-1 border border-gray-300 rounded"
        />
      )
    }
    return <span className="text-gray-900">{value ?? 0}</span>
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm">
      {/* Title Header */}
      <div className="text-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">
          {isEditing && !isReadOnly ? (
            <input
              type="text"
              value={editedData.title ?? block.props.title ?? ''}
              onChange={(e) => handleFieldChange('title', e.target.value)}
              className="w-full text-center px-2 py-1 border border-gray-300 rounded"
              placeholder="Process Title"
            />
          ) : (
            block.props.title || 'Untitled Process'
          )}
        </h1>
        <div className="text-sm text-gray-500 mt-2">
          Revision: {block.props.current_rev_number ?? 0}
        </div>
      </div>

      {/* Edit/Save Controls */}
      {!isReadOnly && (
        <div className="flex justify-end gap-2 mb-4">
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

      {/* Process Information Table */}
      <table className="w-full border-collapse">
        <tbody>
          <tr className="border-b">
            <td className="py-2 px-4 font-semibold bg-gray-50 w-1/3">Heat No:</td>
            <td className="py-2 px-4">{renderField('Heat No', 'heat_no', block.props.heat_no)}</td>
          </tr>
          <tr className="border-b">
            <td className="py-2 px-4 font-semibold bg-gray-50">Finished Size:</td>
            <td className="py-2 px-4">
              {renderField('Finished Size', 'finished_size', block.props.finished_size)}
            </td>
          </tr>
          <tr className="border-b">
            <td className="py-2 px-4 font-semibold bg-gray-50">Stock Size:</td>
            <td className="py-2 px-4">
              {renderField('Stock Size', 'stock_size', block.props.stock_size)}
            </td>
          </tr>
          <tr className="border-b">
            <td className="py-2 px-4 font-semibold bg-gray-50">Stock Weight [kg]:</td>
            <td className="py-2 px-4">
              {renderNumberField('Stock Weight', 'stock_weight', block.props.stock_weight)}
            </td>
          </tr>
          <tr className="border-b">
            <td className="py-2 px-4 font-semibold bg-gray-50">Remarks:</td>
            <td className="py-2 px-4">
              {isEditing && !isReadOnly ? (
                <textarea
                  value={editedData.remarks ?? block.props.remarks ?? ''}
                  onChange={(e) => handleFieldChange('remarks', e.target.value)}
                  className="w-full px-2 py-1 border border-gray-300 rounded"
                  rows={3}
                />
              ) : (
                <span className="text-gray-900 whitespace-pre-wrap">{block.props.remarks ?? ''}</span>
              )}
            </td>
          </tr>
          <tr>
            <td className="py-2 px-4 font-semibold bg-gray-50">Created At:</td>
            <td className="py-2 px-4">
              <span className="text-gray-600 text-sm">
                {block.props.created_at
                  ? new Date(block.props.created_at).toLocaleString()
                  : 'N/A'}
              </span>
            </td>
          </tr>
          <tr>
            <td className="py-2 px-4 font-semibold bg-gray-50">Last Edited:</td>
            <td className="py-2 px-4">
              <span className="text-gray-600 text-sm">
                {block.props.last_edit_at
                  ? new Date(block.props.last_edit_at).toLocaleString()
                  : 'N/A'}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      {/* Version Info (if exists) */}
      {block.props.version && (
        <div className="mt-6 pt-6 border-t">
          <h3 className="text-lg font-semibold mb-3">Version Information</h3>
          <table className="w-full border-collapse">
            <tbody>
              <tr className="border-b">
                <td className="py-2 px-4 font-semibold bg-gray-50 w-1/3">Version Name:</td>
                <td className="py-2 px-4">{block.props.version.name || 'N/A'}</td>
              </tr>
              <tr className="border-b">
                <td className="py-2 px-4 font-semibold bg-gray-50">Editable:</td>
                <td className="py-2 px-4">
                  {block.props.version.is_editable ? 'Yes' : 'No'}
                </td>
              </tr>
              <tr>
                <td className="py-2 px-4 font-semibold bg-gray-50">Operations Count:</td>
                <td className="py-2 px-4">{block.props.version.operations_count ?? 0}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
