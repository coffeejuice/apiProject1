/**
 * Document Block Component
 * Displays document metadata in a table format mimicking a title page
 */

import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { BlockComponentProps } from './BlockRegistry'
import { getFieldMaxLength } from '../../lib/blockFieldLimits'
import { useLibraryStore } from '../../stores/useLibraryStore'
import type { MaterialRecord } from '../../types/api'
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

function formatMaterialBaseLabel(value: string): string {
  const normalized = value.trim()
  if (normalized.length <= 3) {
    return normalized.charAt(0).toUpperCase() + normalized.slice(1).toLowerCase()
  }
  return normalized
    .split(/[_\s.-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

function getMaterialBaseValues(material: MaterialRecord): string[] {
  const source = material.classifications.composition || []
  return source.map(String).filter((entry) => entry.trim().length > 0)
}

function isChineseDesignation(entry: MaterialRecord['designation_links'][number]): boolean {
  const country = (entry.country || '').trim().toLowerCase()
  const standard = (entry.standard || '').trim().toLowerCase()
  return (
    country === 'china' ||
    country === 'chinese' ||
    country === 'cn' ||
    country.includes('china') ||
    standard.startsWith('gb') ||
    standard.startsWith('gjb') ||
    standard.startsWith('yb')
  )
}

function getMaterialDisplayName(material: MaterialRecord): string {
  const seen = new Set<string>()
  const chineseDesignations = material.designation_links
    .filter(isChineseDesignation)
    .map((entry) => entry.designation.trim())
    .filter((designation) => {
      if (!designation) {
        return false
      }
      const key = designation.toLocaleLowerCase()
      if (seen.has(key)) {
        return false
      }
      seen.add(key)
      return true
    })

  return chineseDesignations.length > 0 ? chineseDesignations.join(' / ') : material.name
}

export default function DocumentBlock({
  block,
  baselineProps,
  onUpdate,
}: BlockComponentProps) {
  const materials = useLibraryStore((state) => state.materials)
  const [materialBaseFilter, setMaterialBaseFilter] = useState<string | null>(null)

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
  const materialBaseOptions = useMemo(() => {
    const seen = new Map<string, string>()
    materials.forEach((material) => {
      getMaterialBaseValues(material).forEach((base) => {
        const key = base.toLocaleLowerCase()
        if (!seen.has(key)) {
          seen.set(key, base)
        }
      })
    })
    return Array.from(seen.values()).sort((left, right) =>
      formatMaterialBaseLabel(left).localeCompare(formatMaterialBaseLabel(right))
    )
  }, [materials])
  const filteredMaterials = useMemo(() => {
    if (materialBaseFilter === null) {
      return materials
    }
    const selectedBaseKey = materialBaseFilter.toLocaleLowerCase()
    return materials.filter((material) =>
      getMaterialBaseValues(material).some((base) => base.toLocaleLowerCase() === selectedBaseKey)
    )
  }, [materialBaseFilter, materials])

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

  const renderMaterialField = () => {
    const currentValue = normalizeDocumentFieldValue(block.props, 'material_id')
    const selectedMaterial = materials.find((material) => String(material.material_id) === currentValue)
    const selectedMaterialIsVisible = filteredMaterials.some((material) => String(material.material_id) === currentValue)
    const isDirty = isFieldDirty('material_id')

    return (
      <div className="doc-material-control">
        <div className="doc-material-base-buttons" aria-label="Filter materials by composition base">
          {materialBaseOptions.map((base) => (
            <button
              key={base}
              type="button"
              onClick={() => setMaterialBaseFilter((current) => current === base ? null : base)}
              className={`doc-material-base-button ${materialBaseFilter === base ? 'doc-material-base-button-active' : ''}`}
              aria-pressed={materialBaseFilter === base}
            >
              {formatMaterialBaseLabel(base)}
            </button>
          ))}
        </div>
        <select
          value={currentValue}
          onChange={(event) => handleFieldChange('material_id', event.target.value)}
          className={`doc-select ${isDirty ? 'doc-field-dirty' : ''}`}
          aria-label="Select material"
        >
          <option value="">Select material...</option>
          {selectedMaterial && !selectedMaterialIsVisible ? (
            <option value={selectedMaterial.material_id}>
              {getMaterialDisplayName(selectedMaterial)}
            </option>
          ) : null}
          {!selectedMaterial && currentValue ? (
            <option value={currentValue}>Current material #{currentValue}</option>
          ) : null}
          {filteredMaterials.map((material) => (
            <option key={material.material_id} value={material.material_id}>
              {getMaterialDisplayName(material)}
            </option>
          ))}
        </select>
        {renderResetButton('material_id')}
      </div>
    )
  }

  const renderDocumentMetadata = () => {
    const version = block.props.version
    const editableLabel = typeof version?.is_editable === 'boolean'
      ? version.is_editable ? 'Yes' : 'No'
      : 'N/A'
    const createdAt = block.props.created_at
      ? new Date(block.props.created_at as string).toLocaleString()
      : 'N/A'
    const updatedAt = block.props.updated_at
      ? new Date(block.props.updated_at as string).toLocaleString()
      : 'N/A'

    return (
      <table className="doc-meta-table" aria-label="Document metadata">
        <thead>
          <tr>
            <th scope="col">Editable</th>
            <th scope="col">Operations</th>
            <th scope="col">Created</th>
            <th scope="col">Last Edited</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{editableLabel}</td>
            <td>{version?.operations_count ?? 0}</td>
            <td>{createdAt}</td>
            <td>{updatedAt}</td>
          </tr>
        </tbody>
      </table>
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

  const renderDocumentSection = (title: string, children: ReactNode) => (
    <section className="doc-document-section">
      <h2 className="doc-document-section-title">{title}</h2>
      <div className="doc-document-section-params">
        {children}
      </div>
    </section>
  )

  const renderProcessDataBlock = () => (
    renderDocumentSection(
      'Process data',
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
        </tbody>
      </table>
    )
  )

  const renderMergedSetupBlocks = () => (
    <>
      {renderDocumentSection(
        'Material',
        <table className="doc-table">
          <tbody>
            <tr className="doc-table-row">
              <td className="doc-label">Material:</td>
              <td className="doc-value">{renderMaterialField()}</td>
            </tr>
          </tbody>
        </table>
      )}

      {renderDocumentSection(
        'Input stock size',
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
      )}

      {renderDocumentSection(
        'Mesh',
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
      )}
    </>
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

      {renderDocumentMetadata()}

      <div className="doc-document-blocks">
        {renderProcessDataBlock()}
        {renderMergedSetupBlocks()}
      </div>
    </div>
  )
}
