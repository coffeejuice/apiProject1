/**
 * Document Heading Block Component
 * Displays document metadata in a table format mimicking a title page
 */

import type { BlockComponentProps } from './BlockRegistry'
import { getFieldMaxLength } from '../../lib/blockFieldLimits'

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

  const isFieldDirty = (field: string) =>
    normalizeComparable(block.props?.[field]) !== normalizeComparable(baselineProps?.[field])

  const resetField = (field: string) => {
    const fallbackValue = field === 'name' ? 'Untitled Document' : ''
    handleFieldChange(field, baselineProps?.[field] ?? fallbackValue)
  }

  const renderResetButton = (field: string) => {
    if (isReadOnly || !isFieldDirty(field)) {
      return null
    }

    return (
      <button
        type="button"
        onClick={() => resetField(field)}
        className="h-8 w-8 flex-shrink-0 border border-red-300 rounded text-red-700 bg-red-50 hover:bg-red-100"
        title="Revert this parameter"
      >
        ↺
      </button>
    )
  }

  const renderTextField = (field: string, placeholder = '') => {
    const currentValue = normalizeComparable(block.props?.[field])
    const maxLength = getFieldMaxLength(block, field)
    const isDirty = isFieldDirty(field)

    if (isReadOnly) {
      return <span className="text-gray-900">{currentValue}</span>
    }

    return (
      <div className="w-full">
        <div className="flex items-start gap-2">
          <input
            type="text"
            value={currentValue}
            onChange={(event) => handleFieldChange(field, event.target.value)}
            className={`w-full px-2 py-1 border rounded ${
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
      return <span className="text-gray-900 whitespace-pre-wrap">{currentValue}</span>
    }

    return (
      <div className="w-full">
        <div className="flex items-start gap-2">
          <textarea
            value={currentValue}
            onChange={(event) => handleFieldChange(field, event.target.value)}
            className={`w-full px-2 py-1 border rounded ${
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

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm">
      <div className="text-center mb-6">
        {isReadOnly ? (
          <h1 className="text-3xl font-bold text-gray-900">
            {normalizeComparable(block.props?.name) || 'Untitled Document'}
          </h1>
        ) : (
          <div className="flex items-start gap-2">
            <input
              type="text"
              value={normalizeComparable(block.props?.name)}
              onChange={(event) => handleFieldChange('name', event.target.value)}
              className={`w-full text-center text-3xl font-bold text-gray-900 px-2 py-1 border rounded ${
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
            <td className="py-2 px-4 font-semibold bg-gray-50 w-1/3">Heat No:</td>
            <td className="py-2 px-4">{renderTextField('heat_no')}</td>
          </tr>
          <tr className="border-b">
            <td className="py-2 px-4 font-semibold bg-gray-50">Finished Size:</td>
            <td className="py-2 px-4">{renderTextField('finished_size')}</td>
          </tr>
          <tr className="border-b">
            <td className="py-2 px-4 font-semibold bg-gray-50">Stock Size:</td>
            <td className="py-2 px-4">{renderTextField('stock_size')}</td>
          </tr>
          <tr className="border-b">
            <td className="py-2 px-4 font-semibold bg-gray-50">Stock Weight [kg]:</td>
            <td className="py-2 px-4">{renderTextField('stock_weight')}</td>
          </tr>
          <tr className="border-b">
            <td className="py-2 px-4 font-semibold bg-gray-50">Remarks:</td>
            <td className="py-2 px-4">{renderTextareaField('remarks', 3)}</td>
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
                {block.props.updated_at
                  ? new Date(block.props.updated_at as string).toLocaleString()
                  : 'N/A'}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

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
