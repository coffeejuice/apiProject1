/**
 * Document Heading Block Component
 * Displays document metadata in a table format mimicking a title page
 */

import type { BlockComponentProps } from './BlockRegistry'
import { getFieldMaxLength } from '../../lib/blockFieldLimits'
import Tooltip from '../ui/Tooltip'

interface GeometryType {
  id: string
  name: string
  labels: string[]
  columns: string[]
  library_name?: string
}

function normalizeComparable(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

export default function DocumentHeadingBlock({
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

  const availableGeometryTypes: GeometryType[] = block.props.available_geometry_types || []
  const currentGeometryTypeId = normalizeComparable(block.props.geometry_type_id)
  const currentGeometry = currentGeometryTypeId
    ? availableGeometryTypes.find((geometry) => geometry.id === currentGeometryTypeId)
    : null
  const selectedGeometry = currentGeometry || block.props.selected_geometry || null

  const handleGeometryTypeChange = (newTypeId: string) => {
    const selectedType = availableGeometryTypes.find((geometry) => geometry.id === newTypeId)
    const newAttributes: Record<string, string> = {}

    if (selectedType) {
      selectedType.columns.forEach((column) => {
        newAttributes[column] = ''
      })
    }

    onUpdate(block.block_id, {
      ...(block.props || {}),
      geometry_type_id: newTypeId,
      attributes: newAttributes,
    })
  }

  const isFieldDirty = (field: string) =>
    normalizeComparable(block.props?.[field]) !== normalizeComparable(baselineProps?.[field])

  const isAttributeDirty = (field: string) =>
    normalizeComparable(block.props?.attributes?.[field]) !==
    normalizeComparable(baselineProps?.attributes?.[field])

  const resetField = (field: string) => {
    const fallbackValue = field === 'name' ? 'Untitled Document' : ''
    handleFieldChange(field, baselineProps?.[field] ?? fallbackValue)
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

  const resetAttribute = (field: string) => {
    handleAttributeChange(field, normalizeComparable(baselineProps?.attributes?.[field]))
  }

  const renderResetButton = (field: string) => {
    if (isReadOnly || !isFieldDirty(field)) {
      return null
    }

    return (
      <Tooltip content="Revert this parameter">
        <button
          type="button"
          onClick={() => resetField(field)}
          className="ui-btn-danger h-8 w-8 p-0 flex-shrink-0"
          aria-label="Revert this parameter"
        >
          ↺
        </button>
      </Tooltip>
    )
  }

  const renderTextField = (field: string, placeholder = '') => {
    const currentValue = normalizeComparable(block.props?.[field])
    const maxLength = getFieldMaxLength(block, field)
    const isDirty = isFieldDirty(field)

    if (isReadOnly) {
      return <div className="ui-field-readonly">{currentValue || '-'}</div>
    }

    return (
      <div className="w-full">
        <div className="flex items-start gap-2">
          <input
            type="text"
            value={currentValue}
            onChange={(event) => handleFieldChange(field, event.target.value)}
            className={`ui-input ${
              isDirty ? 'border-red-300 bg-red-50' : 'border-gray-300'
            }`}
            maxLength={maxLength || undefined}
            placeholder={placeholder}
          />
          {renderResetButton(field)}
        </div>
      </div>
    )
  }

  const renderTextareaField = (field: string, rows: number) => {
    const currentValue = normalizeComparable(block.props?.[field])
    const maxLength = getFieldMaxLength(block, field)
    const isDirty = isFieldDirty(field)

    if (isReadOnly) {
      return (
        <div className="ui-field-readonly ui-field-readonly-multiline">
          {currentValue || '-'}
        </div>
      )
    }

    return (
      <div className="w-full">
        <div className="flex items-start gap-2">
          <textarea
            value={currentValue}
            onChange={(event) => handleFieldChange(field, event.target.value)}
            className={`ui-textarea ${
              isDirty ? 'border-red-300 bg-red-50' : 'border-gray-300'
            }`}
            rows={rows}
            maxLength={maxLength || undefined}
          />
          {renderResetButton(field)}
        </div>
      </div>
    )
  }

  const renderNumericField = (field: string, placeholder = '') => {
    const currentValue = normalizeComparable(block.props?.[field])
    const isDirty = isFieldDirty(field)

    if (isReadOnly) {
      return <div className="ui-field-readonly">{currentValue || '-'}</div>
    }

    return (
      <div className="flex items-start gap-2">
        <input
          type="number"
          step="0.001"
          min="0"
          value={currentValue}
          onChange={(event) => handleFieldChange(field, event.target.value)}
          className={`ui-input ${isDirty ? 'border-red-300 bg-red-50' : 'border-gray-300'}`}
          placeholder={placeholder}
        />
        {renderResetButton(field)}
      </div>
    )
  }

  const renderAttributeField = (field: string, label: string) => {
    const currentValue = normalizeComparable(block.props?.attributes?.[field])
    const isDirty = isAttributeDirty(field)

    if (isReadOnly) {
      return <div className="ui-field-readonly">{currentValue || '-'}</div>
    }

    return (
      <div className="flex items-start gap-2">
        <input
          type="number"
          step="0.001"
          value={currentValue}
          onChange={(event) => handleAttributeChange(field, event.target.value)}
          className={`ui-input ${isDirty ? 'border-red-300 bg-red-50' : 'border-gray-300'}`}
          placeholder={`Enter ${label.toLowerCase()}`}
        />
        {isReadOnly || !isDirty ? null : (
          <Tooltip content="Revert this parameter">
            <button
              type="button"
              onClick={() => resetAttribute(field)}
              className="ui-btn-danger h-8 w-8 p-0 flex-shrink-0"
              aria-label="Revert this parameter"
            >
              ↺
            </button>
          </Tooltip>
        )}
      </div>
    )
  }

  const renderMergedSetupBlocks = () => (
    <div className="mt-3 grid gap-3 border-t pt-3">
      <div className="ui-card ui-card-body text-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-gray-900">Material</h2>
        </div>
        <table className="w-full border-collapse">
          <tbody>
            <tr>
              <td className="py-1 px-2 font-semibold bg-gray-50 w-1/2">Material:</td>
              <td className="py-1 px-2">{renderTextField('material_id')}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="ui-card ui-card-body text-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-gray-900">
            {normalizeComparable(block.props.input_workpiece_title) || 'Input Workpiece'}
          </h2>
        </div>

        <table className="w-full border-collapse">
          <tbody>
            <tr className="border-b">
              <td className="py-1 px-2 font-semibold bg-gray-50 w-1/2">Geometry Type:</td>
              <td className="py-1 px-2">
                {isReadOnly ? (
                  <div className="ui-field-readonly">
                    {selectedGeometry ? selectedGeometry.library_name || selectedGeometry.name : 'Not set'}
                  </div>
                ) : (
                  <div className="flex items-start gap-2">
                    <select
                      value={currentGeometryTypeId}
                      onChange={(event) => handleGeometryTypeChange(event.target.value)}
                      className={`ui-select ${
                        isFieldDirty('geometry_type_id')
                          ? 'border-red-300 bg-red-50'
                          : 'border-gray-300'
                      }`}
                    >
                      <option value="">Select geometry type...</option>
                      {availableGeometryTypes.map((geometry) => (
                        <option key={geometry.id} value={geometry.id}>
                          {geometry.name}
                        </option>
                      ))}
                    </select>
                    {isReadOnly || !isFieldDirty('geometry_type_id') ? null : (
                      <Tooltip content="Revert this parameter">
                        <button
                          type="button"
                          onClick={resetGeometryType}
                          className="ui-btn-danger h-8 w-8 p-0 flex-shrink-0"
                          aria-label="Revert this parameter"
                        >
                          ↺
                        </button>
                      </Tooltip>
                    )}
                  </div>
                )}
              </td>
            </tr>

            {selectedGeometry?.columns?.map((column: string, index: number) => {
              const label = selectedGeometry.labels?.[index] || column
              return (
                <tr key={column} className="border-b">
                  <td className="py-1 px-2 font-semibold bg-gray-50">{label}</td>
                  <td className="py-1 px-2">{renderAttributeField(column, label)}</td>
                </tr>
              )
            })}

            <tr>
              <td className="py-1 px-2 font-semibold bg-gray-50">Weight [kg]:</td>
              <td className="py-1 px-2">{renderNumericField('weight')}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="ui-card ui-card-body text-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-gray-900">Mesh</h2>
        </div>
        <table className="w-full border-collapse">
          <tbody>
            <tr>
              <td className="py-1 px-2 font-semibold bg-gray-50 w-1/2">
                Elements across width [pcs]:
              </td>
              <td className="py-1 px-2">{renderNumericField('mesh_elements')}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )

  return (
    <div className="ui-card ui-card-body text-sm">
      <div className="text-center mb-3">
        {isReadOnly ? (
          <h1 className="text-sm font-bold text-gray-900">
            {normalizeComparable(block.props?.name) || 'Untitled Document'}
          </h1>
        ) : (
          <div className="flex items-start gap-2">
            <input
              type="text"
              value={normalizeComparable(block.props?.name)}
              onChange={(event) => handleFieldChange('name', event.target.value)}
              className={`ui-input text-center text-sm font-bold text-gray-900 ${
                isFieldDirty('name') ? 'border-red-300 bg-red-50' : 'border-gray-300'
              }`}
              maxLength={getFieldMaxLength(block, 'name')}
              placeholder="Document Title"
            />
            {renderResetButton('name')}
          </div>
        )}
      </div>

      <table className="w-full border-collapse">
        <tbody>
          <tr className="border-b">
            <td className="py-1 px-2 font-semibold bg-gray-50 w-1/3">Heat No:</td>
            <td className="py-1 px-2">{renderTextField('heat_no')}</td>
          </tr>
          <tr className="border-b">
            <td className="py-1 px-2 font-semibold bg-gray-50">Finished Size:</td>
            <td className="py-1 px-2">{renderTextField('finished_size')}</td>
          </tr>
          <tr className="border-b">
            <td className="py-1 px-2 font-semibold bg-gray-50">Remarks:</td>
            <td className="py-1 px-2">{renderTextareaField('remarks', 3)}</td>
          </tr>
          <tr>
            <td className="py-1 px-2 font-semibold bg-gray-50">Created At:</td>
            <td className="py-1 px-2">
              <span className="text-gray-600 text-xs">
                {block.props.created_at
                  ? new Date(block.props.created_at).toLocaleString()
                  : 'N/A'}
              </span>
            </td>
          </tr>
          <tr>
            <td className="py-1 px-2 font-semibold bg-gray-50">Last Edited:</td>
            <td className="py-1 px-2">
              <span className="text-gray-600 text-xs">
                {block.props.updated_at
                  ? new Date(block.props.updated_at as string).toLocaleString()
                  : 'N/A'}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      {renderMergedSetupBlocks()}

      {block.props.version && (
        <div className="mt-3 pt-3 border-t">
          <h3 className="text-sm font-semibold mb-2">Version Information</h3>
          <table className="w-full border-collapse">
            <tbody>
              <tr className="border-b">
                <td className="py-1 px-2 font-semibold bg-gray-50 w-1/3">Version Name:</td>
                <td className="py-1 px-2">{block.props.version.name || 'N/A'}</td>
              </tr>
              <tr className="border-b">
                <td className="py-1 px-2 font-semibold bg-gray-50">Editable:</td>
                <td className="py-1 px-2">
                  {block.props.version.is_editable ? 'Yes' : 'No'}
                </td>
              </tr>
              <tr>
                <td className="py-1 px-2 font-semibold bg-gray-50">Operations Count:</td>
                <td className="py-1 px-2">{block.props.version.operations_count ?? 0}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
