import { useEffect, useMemo, useState } from 'react'

import { apiClient } from '../../lib/apiClient'
import type { BlockData, DocumentOperationListResponse, DocumentOperationRecord } from '../../types/api'

interface DocumentOperationsViewProps {
  documentId: string | null
  blocks: BlockData[]
  activeBlockId: string | null
  hoveredBlockId: string | null
  hasUnsavedChanges: boolean
  saveStatus: 'idle' | 'saving' | 'saved' | 'error'
}

interface TargetEntry {
  key: string
  value: string
}

const HEATING_BLOCK_TYPE_ID = 'heating'
const DEFORMATION_BLOCK_TYPE_ID = 'deformation'
const FURNACE_BLOCK_TYPE_ID = 'furnace'
const OPERATION_BLOCK_TYPE_ID = 'operation'

function isSectionBlock(block: BlockData): boolean {
  return block.block_type_id === HEATING_BLOCK_TYPE_ID || block.block_type_id === DEFORMATION_BLOCK_TYPE_ID
}

function getBlockTitle(block: BlockData | undefined): string {
  if (!block) {
    return ''
  }
  if (block.block_type_id === HEATING_BLOCK_TYPE_ID) {
    return 'Heating'
  }
  if (block.block_type_id === DEFORMATION_BLOCK_TYPE_ID) {
    return 'Deformation'
  }
  if (block.block_type_id === FURNACE_BLOCK_TYPE_ID) {
    return 'Furnace'
  }
  if (block.block_type_id === OPERATION_BLOCK_TYPE_ID) {
    const operationProperties = block.props?.operation_properties
    if (operationProperties && typeof operationProperties === 'object') {
      const props = operationProperties as Record<string, unknown>
      const template = props.template_snapshot
      if (template && typeof template === 'object') {
        const record = template as Record<string, unknown>
        const title = record.display_name || record.label || record.id
        if (title) {
          return String(title)
        }
      }
      if (props.operation_template_id) {
        return String(props.operation_template_id)
      }
    }
    return 'Operation'
  }
  return block.block_type_id
}

function relatedSourceBlockIds(blocks: BlockData[], blockId: string | null): Set<string> {
  if (!blockId) {
    return new Set()
  }

  const blockIndex = blocks.findIndex((block) => block.block_id === blockId)
  if (blockIndex < 0) {
    return new Set()
  }

  const block = blocks[blockIndex]
  if (block.block_type_id === OPERATION_BLOCK_TYPE_ID || block.block_type_id === FURNACE_BLOCK_TYPE_ID) {
    return new Set([block.block_id])
  }

  if (block.block_type_id !== HEATING_BLOCK_TYPE_ID && block.block_type_id !== DEFORMATION_BLOCK_TYPE_ID) {
    return new Set()
  }

  const childType = block.block_type_id === HEATING_BLOCK_TYPE_ID ? FURNACE_BLOCK_TYPE_ID : OPERATION_BLOCK_TYPE_ID
  const related = new Set<string>()
  for (let index = blockIndex + 1; index < blocks.length; index += 1) {
    const candidate = blocks[index]
    if (isSectionBlock(candidate)) {
      break
    }
    if (candidate.block_type_id === childType) {
      related.add(candidate.block_id)
    }
  }
  return related
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return ''
  }
  if (Array.isArray(value)) {
    return `[${value.map(formatValue).join(', ')}]`
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

function flattenTargetEntries(target: Record<string, unknown>, prefix = ''): TargetEntry[] {
  return Object.entries(target).flatMap(([key, value]) => {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (fullKey === 'parameters_calculation_mode') {
      return []
    }
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenTargetEntries(value as Record<string, unknown>, fullKey)
    }
    const formatted = formatValue(value)
    return formatted === '' ? [] : [{ key: fullKey, value: formatted }]
  })
}

function operationLabel(operation: DocumentOperationRecord): string {
  return operation.label_snapshot || operation.operation_template_id || operation.operation_kind || 'Operation'
}

function parseErrorText(operation: DocumentOperationRecord): string {
  return operation.parse_errors
    .map((entry) => {
      if (typeof entry.message === 'string') {
        return entry.message
      }
      if (typeof entry.error === 'string') {
        return entry.error
      }
      return JSON.stringify(entry)
    })
    .join('; ')
}

export default function DocumentOperationsView({
  documentId,
  blocks,
  activeBlockId,
  hoveredBlockId,
  hasUnsavedChanges,
  saveStatus,
}: DocumentOperationsViewProps) {
  const [operations, setOperations] = useState<DocumentOperationRecord[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const blocksById = useMemo(
    () => new Map(blocks.map((block) => [block.block_id, block])),
    [blocks]
  )

  const activeBlock = activeBlockId ? blocksById.get(activeBlockId) : undefined
  const activeSourceIds = useMemo(() => {
    return relatedSourceBlockIds(blocks, activeBlockId)
  }, [activeBlockId, blocks])

  const hoveredSourceIds = useMemo(
    () => relatedSourceBlockIds(blocks, hoveredBlockId),
    [blocks, hoveredBlockId]
  )

  const isFocused = activeSourceIds.size > 0
  const visibleOperations = useMemo(() => {
    if (!isFocused) {
      return operations
    }
    return operations.filter((operation) => activeSourceIds.has(operation.source_block_id))
  }, [activeSourceIds, isFocused, operations])

  useEffect(() => {
    if (!documentId) {
      setOperations([])
      setError(null)
      return
    }

    let cancelled = false
    const loadOperations = async () => {
      setIsLoading(true)
      setError(null)
      const response = await apiClient.get<DocumentOperationListResponse>(`/documents/${documentId}/operations`)
      if (cancelled) {
        return
      }
      if (!response.ok || !response.data) {
        setOperations([])
        setError(response.errorMessage || 'Failed to load document operations')
      } else {
        setOperations(response.data.operations || [])
      }
      setIsLoading(false)
    }

    void loadOperations()
    return () => {
      cancelled = true
    }
  }, [documentId, saveStatus])

  if (!documentId) {
    return (
      <aside className="operations-panel">
        <div className="operations-panel-empty">Select one document to inspect operations.</div>
      </aside>
    )
  }

  const focusTitle = isFocused ? getBlockTitle(activeBlock) : null

  return (
    <aside className="operations-panel">
      <div className="operations-panel-header">
        <div>
          <div className="operations-title">Document operations</div>
          <div className="operations-subtitle">
            {isFocused ? `Focused: ${focusTitle}` : 'All saved materialized records'}
          </div>
        </div>
        <div className="ui-badge">{visibleOperations.length} rows</div>
      </div>

      {hasUnsavedChanges ? (
        <div className="operations-warning">
          Operations are generated from saved document state. Save to update this table.
        </div>
      ) : null}

      {error ? (
        <div className="operations-error">{error}</div>
      ) : null}

      <div className="operations-table-wrap">
        <table className="operations-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Type</th>
              <th>Target parameters</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {visibleOperations.map((operation) => {
              const isHighlighted =
                hoveredSourceIds.has(operation.source_block_id) ||
                activeSourceIds.has(operation.source_block_id)
              const targetEntries = flattenTargetEntries(operation.target || {})
              const errorText = parseErrorText(operation)
              return (
                <tr
                  key={operation.document_operation_id}
                  className={[
                    isHighlighted ? 'operations-row-highlighted' : '',
                    operation.parse_status !== 'valid' ? 'operations-row-error' : '',
                  ].filter(Boolean).join(' ')}
                >
                  <td className="operations-order">{operation.operation_order}</td>
                  <td>
                    <div className="operations-type-pill">{operationLabel(operation)}</div>
                  </td>
                  <td>
                    {targetEntries.length > 0 ? (
                      <div className="operations-params">
                        {targetEntries.map((entry) => (
                          <span key={`${operation.document_operation_id}-${entry.key}`} className="operations-param-chip">
                            <span className="operations-param-key">{entry.key}</span>
                            <span className="operations-param-value">{entry.value}</span>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="operations-muted">No target parameters</span>
                    )}
                  </td>
                  <td>
                    <span
                      className={operation.parse_status === 'valid' ? 'operations-status-valid' : 'operations-status-error'}
                      title={errorText || operation.parse_status}
                    >
                      {operation.parse_status}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {!isLoading && visibleOperations.length === 0 ? (
          <div className="operations-panel-empty">
            {isFocused ? 'No saved operations for the active block.' : 'No document operations generated yet.'}
          </div>
        ) : null}

        {isLoading ? (
          <div className="operations-panel-empty">Loading operations...</div>
        ) : null}
      </div>
    </aside>
  )
}
