/**
 * Document Block Component
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

function normalizeDocumentFieldValue(props: Record<string, unknown> | undefined, field: string): string {
  return normalizeComparable(props?.[field] ?? (field === 'section_numbering_start' ? 2 : ''))
}

export default function DocumentBlock({
  block,
  baselineProps,
  onUpdate,
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
    normalizeDocumentFieldValue(block.props, field) !== normalizeDocumentFieldValue(baselineProps, field)

  const isAttributeDirty = (field: string) =>
    normalizeComparable(block.props?.attributes?.[field]) !==
    normalizeComparable(baselineProps?.attributes?.[field])

  const resetField = (field: string) => {
    const fallbackValue = field === 'name'
      ? 'Untitled Document'
      : field === 'section_numbering_start'
        ? 2
        : ''
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
    if (!isFieldDirty(field)) {
      return null
    }

    return (
      <Tooltip content="Revert this parameter">
        <button
          type="button"
          onClick={() => resetField(field)}
          className="doc-reset"
          aria-label="Revert this parameter"
        >
          ↺
        </button>
      </Tooltip>
    )
  }

  const renderTextField = (field: string, placeholder = '') => {
    const currentValue = normalizeDocumentFieldValue(block.props, field)
    const maxLength = getFieldMaxLength(block, field)
    const isDirty = isFieldDirty(field)

    return (
      <div className="w-full">
        <div className="doc-field-row">
          <input
            type="text"
            value={currentValue}
            onChange={(event) => handleFieldChange(field, event.target.value)}
            className={`doc-field ${isDirty ? 'doc-field-dirty' : ''}`}
            maxLength={maxLength || undefined}
            placeholder={placeholder}
          />
          {renderResetButton(field)}
        </div>
      </div>
    )
  }

  const renderTextareaField = (field: string, rows: number) => {
    const currentValue = normalizeDocumentFieldValue(block.props, field)
    const maxLength = getFieldMaxLength(block, field)
    const isDirty = isFieldDirty(field)

    return (
      <div className="w-full">
        <div className="doc-field-row">
          <textarea
            value={currentValue}
            onChange={(event) => handleFieldChange(field, event.target.value)}
            className={`doc-textarea ${isDirty ? 'doc-field-dirty' : ''}`}
            rows={rows}
            maxLength={maxLength || undefined}
          />
          {renderResetButton(field)}
        </div>
      </div>
    )
  }

  const renderNumericField = (field: string, placeholder = '') => {
    const currentValue = normalizeDocumentFieldValue(block.props, field)
    const isDirty = isFieldDirty(field)

    return (
      <div className="doc-field-row">
        <input
          type="number"
          step="0.001"
          min="0"
          value={currentValue}
          onChange={(event) => handleFieldChange(field, event.target.value)}
          className={`doc-field ${isDirty ? 'doc-field-dirty' : ''}`}
          placeholder={placeholder}
        />
        {renderResetButton(field)}
      </div>
    )
  }

  const renderIntegerField = (field: string, placeholder = '') => {
    const currentValue = normalizeDocumentFieldValue(block.props, field)
    const isDirty = isFieldDirty(field)

    return (
      <div className="doc-field-row">
        <input
          type="number"
          step="1"
          min="1"
          value={currentValue}
          onChange={(event) => handleFieldChange(field, event.target.value)}
          className={`doc-field ${isDirty ? 'doc-field-dirty' : ''}`}
          placeholder={placeholder}
        />
        {renderResetButton(field)}
      </div>
    )
  }

  const renderAttributeField = (field: string, label: string) => {
    const currentValue = normalizeComparable(block.props?.attributes?.[field])
    const isDirty = isAttributeDirty(field)

    return (
      <div className="doc-field-row">
        <input
          type="number"
          step="0.001"
          value={currentValue}
          onChange={(event) => handleAttributeChange(field, event.target.value)}
          className={`doc-field ${isDirty ? 'doc-field-dirty' : ''}`}
          placeholder={`Enter ${label.toLowerCase()}`}
        />
        {!isDirty ? null : (
          <Tooltip content="Revert this parameter">
            <button
              type="button"
              onClick={() => resetAttribute(field)}
              className="doc-reset"
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
    <div className="mt-4 grid gap-2">
      <section className="doc-section">
        <h2 className="doc-subtitle">Material</h2>
        <table className="doc-table">
          <tbody>
            <tr className="doc-table-row">
              <td className="doc-label">Material:</td>
              <td className="doc-value">{renderTextField('material_id')}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="doc-section">
        <h2 className="doc-subtitle">
          {normalizeComparable(block.props.billet_geometry_title) || 'Billet'}
        </h2>

        <table className="doc-table">
          <tbody>
            <tr className="doc-table-row">
              <td className="doc-label">Geometry Type:</td>
              <td className="doc-value">
                <div className="doc-field-row">
                  <select
                    value={currentGeometryTypeId}
                    onChange={(event) => handleGeometryTypeChange(event.target.value)}
                    className={`doc-select ${
                      isFieldDirty('geometry_type_id') ? 'doc-field-dirty' : ''
                    }`}
                  >
                    <option value="">Select geometry type...</option>
                    {availableGeometryTypes.map((geometry) => (
                      <option key={geometry.id} value={geometry.id}>
                        {geometry.name}
                      </option>
                    ))}
                  </select>
                  {!isFieldDirty('geometry_type_id') ? null : (
                    <Tooltip content="Revert this parameter">
                      <button
                        type="button"
                        onClick={resetGeometryType}
                        className="doc-reset"
                        aria-label="Revert this parameter"
                      >
                        ↺
                      </button>
                    </Tooltip>
                  )}
                </div>
              </td>
            </tr>

            {selectedGeometry?.columns?.map((column: string, index: number) => {
              const label = selectedGeometry.labels?.[index] || column
              return (
                <tr key={column} className="doc-table-row">
                  <td className="doc-label">{label}</td>
                  <td className="doc-value">{renderAttributeField(column, label)}</td>
                </tr>
              )
            })}

            <tr className="doc-table-row">
              <td className="doc-label">Weight [kg]:</td>
              <td className="doc-value">{renderNumericField('weight')}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="doc-section">
        <h2 className="doc-subtitle">Mesh</h2>
        <table className="doc-table">
          <tbody>
            <tr className="doc-table-row">
              <td className="doc-label">
                Elements across width [pcs]:
              </td>
              <td className="doc-value">{renderNumericField('mesh_elements')}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="doc-section">
        <h2 className="doc-subtitle">Numbering</h2>
        <table className="doc-table">
          <tbody>
            <tr className="doc-table-row">
              <td className="doc-label">Section numbering starts at:</td>
              <td className="doc-value">{renderIntegerField('section_numbering_start')}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  )

  return (
    <div className="doc-content">
      <div className="mb-3 text-center">
        <div className="doc-field-row">
          <input
            type="text"
            value={normalizeComparable(block.props?.name)}
            onChange={(event) => handleFieldChange('name', event.target.value)}
            className={`doc-field doc-title-main ${
              isFieldDirty('name') ? 'doc-field-dirty' : ''
            }`}
            maxLength={getFieldMaxLength(block, 'name')}
            placeholder="Document Title"
          />
          {renderResetButton('name')}
        </div>
      </div>

      <table className="doc-table">
        <tbody>
          <tr className="doc-table-row">
            <td className="doc-label">Heat No:</td>
            <td className="doc-value">{renderTextField('heat_no')}</td>
          </tr>
          <tr className="doc-table-row">
            <td className="doc-label">Finished Size:</td>
            <td className="doc-value">{renderTextField('finished_size')}</td>
          </tr>
          <tr className="doc-table-row">
            <td className="doc-label">Remarks:</td>
            <td className="doc-value">{renderTextareaField('remarks', 3)}</td>
          </tr>
          <tr className="doc-table-row">
            <td className="doc-label">Created At:</td>
            <td className="doc-value">
              <span className="doc-readonly">
                {block.props.created_at
                  ? new Date(block.props.created_at).toLocaleString()
                  : 'N/A'}
              </span>
            </td>
          </tr>
          <tr className="doc-table-row">
            <td className="doc-label">Last Edited:</td>
            <td className="doc-value">
              <span className="doc-readonly">
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
        <section className="doc-section">
          <h3 className="doc-subtitle">Version Information</h3>
          <table className="doc-table">
            <tbody>
              <tr className="doc-table-row">
                <td className="doc-label">Version Name:</td>
                <td className="doc-value">{block.props.version.name || 'N/A'}</td>
              </tr>
              <tr className="doc-table-row">
                <td className="doc-label">Editable:</td>
                <td className="doc-value">
                  {block.props.version.is_editable ? 'Yes' : 'No'}
                </td>
              </tr>
              <tr className="doc-table-row">
                <td className="doc-label">Operations Count:</td>
                <td className="doc-value">{block.props.version.operations_count ?? 0}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
