import { DragEvent, MouseEvent, useEffect, useMemo, useState } from 'react'
import type { BlockData } from './blocks'
import { getBlockTypeIcon, getBlockTypeLabel } from '../lib/blockTypeMeta'
import { apiClient } from '../lib/apiClient'
import Tooltip from './ui/Tooltip'
import type { OperationBlockTypeRecord } from '../types/api'

type VisualEditorMode = 'viewer' | 'editor'
const VISUAL_BLOCK_DRAG_MIME = 'application/x-forgelab-visual-block-ids'

interface VisualEditorProps {
  blocks: BlockData[]
  isVisible: boolean
  hasUnsavedChanges: boolean
  activeDocumentBlockId: string | null
  onNavigate: (blockId: string) => void
  onInsertBlock: (blockTypeId: string, previousBlockId: string | null) => Promise<void>
  onMoveBlocks: (blockIds: string[], previousBlockId: string | null) => Promise<void>
  onCopyBlocks: (blockIds: string[], previousBlockId: string | null) => Promise<void>
  onDeleteBlocks: (blockIds: string[]) => Promise<void>
  hasActiveClipboardClip: boolean
  activeClipboardLabel?: string | null
  onCopyBlocksToClipboard: (blockIds: string[]) => Promise<boolean>
  onCutBlocksToClipboard: (blockIds: string[]) => Promise<boolean>
  onPasteActiveClipboard: () => Promise<boolean>
}

function getDropPayload(event: DragEvent<HTMLElement>): string[] {
  const payload = event.dataTransfer.getData(VISUAL_BLOCK_DRAG_MIME)
  if (!payload) {
    return []
  }

  try {
    const parsed = JSON.parse(payload)
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.filter((entry): entry is string => typeof entry === 'string')
  } catch {
    return []
  }
}

function hasVisualDragPayload(event: DragEvent<HTMLElement>): boolean {
  return Array.from(event.dataTransfer.types).includes(VISUAL_BLOCK_DRAG_MIME)
}

function getOperationLibraryName(block: BlockData): string | null {
  const operationType = block.props?.operation_type
  if (!operationType || typeof operationType !== 'object') {
    return null
  }
  const libraryName = (operationType as { library_name?: unknown }).library_name
  return typeof libraryName === 'string' && libraryName.trim() ? libraryName : null
}

function getBlockDisplayLabel(block: BlockData): string {
  return getOperationLibraryName(block) || getBlockTypeLabel(block.block_type_id)
}

function getBlockDisplayIcon(block: BlockData): string {
  return /^\d+$/.test(block.block_type_id) ? 'OP' : getBlockTypeIcon(block.block_type_id)
}

export default function VisualEditor({
  blocks,
  isVisible,
  hasUnsavedChanges,
  activeDocumentBlockId,
  onNavigate,
  onInsertBlock,
  onMoveBlocks,
  onCopyBlocks,
  onDeleteBlocks,
  hasActiveClipboardClip,
  activeClipboardLabel,
  onCopyBlocksToClipboard,
  onCutBlocksToClipboard,
  onPasteActiveClipboard,
}: VisualEditorProps) {
  const [mode, setMode] = useState<VisualEditorMode>('viewer')
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set())
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [insertType, setInsertType] = useState<string>('')
  const [operationTypes, setOperationTypes] = useState<OperationBlockTypeRecord[]>([])
  const [operationTypesLoading, setOperationTypesLoading] = useState(false)
  const [operationTypesError, setOperationTypesError] = useState<string | null>(null)
  const [isMutating, setIsMutating] = useState(false)

  const uniqueTypes = useMemo(() => {
    const known = new Set<string>()
    blocks.forEach((block) => known.add(block.block_type_id))
    return Array.from(known)
  }, [blocks])

  const visibleBlocks = useMemo(() => {
    if (mode === 'editor') {
      return blocks
    }
    return blocks.filter((block) => !hiddenTypes.has(block.block_type_id))
  }, [blocks, hiddenTypes, mode])

  const selectedBlocksInOrder = useMemo(() => {
    return blocks.filter((block) => selectedIds.has(block.block_id))
  }, [blocks, selectedIds])

  const structureEditDisabled = hasUnsavedChanges || isMutating
  const insertDisabled =
    structureEditDisabled || !insertType || operationTypes.length === 0 || !activeDocumentBlockId
  const selectionActionDisabled = structureEditDisabled || selectedBlocksInOrder.length === 0

  useEffect(() => {
    if (!isVisible) {
      return
    }

    let isActive = true
    setOperationTypesLoading(true)
    setOperationTypesError(null)

    const loadOperationTypes = async () => {
      const response = await apiClient.get<OperationBlockTypeRecord[]>(
        '/library/db/document-block-types',
        {
          params: {
            insertable_only: true,
          },
        }
      )

      if (!isActive) {
        return
      }

      if (response.ok && response.data) {
        const loadedOperationTypes = response.data
        setOperationTypes(loadedOperationTypes)
        setInsertType((current) =>
          current || (loadedOperationTypes.length > 0 ? String(loadedOperationTypes[0].type_id) : '')
        )
      } else {
        setOperationTypesError(response.errorMessage || 'Failed to load operation block types')
      }
      setOperationTypesLoading(false)
    }

    void loadOperationTypes()

    return () => {
      isActive = false
    }
  }, [isVisible])

  const runMutation = async (task: () => Promise<void>) => {
    setIsMutating(true)
    try {
      await task()
    } finally {
      setIsMutating(false)
    }
  }

  const handleBlockClick = (event: MouseEvent<HTMLButtonElement>, blockId: string) => {
    if (mode === 'viewer') {
      onNavigate(blockId)
      return
    }

    if (event.metaKey || event.ctrlKey) {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        if (next.has(blockId)) {
          next.delete(blockId)
        } else {
          next.add(blockId)
        }
        return next
      })
      return
    }

    setSelectedIds(new Set([blockId]))
    onNavigate(blockId)
  }

  const handleDragStart = (event: DragEvent<HTMLButtonElement>, blockId: string) => {
    if (mode !== 'editor' || structureEditDisabled) {
      return
    }

    const payloadIds = selectedIds.has(blockId) ? selectedBlocksInOrder.map((block) => block.block_id) : [blockId]
    if (payloadIds.length === 0) {
      return
    }

    event.dataTransfer.setData(VISUAL_BLOCK_DRAG_MIME, JSON.stringify(payloadIds))
    event.dataTransfer.setData('text/plain', payloadIds.join(','))
    event.dataTransfer.effectAllowed = 'copyMove'
  }

  const handleDropAt = async (event: DragEvent<HTMLDivElement>, previousBlockId: string | null) => {
    const payloadIds = getDropPayload(event)
    if (payloadIds.length === 0) {
      return
    }

    event.preventDefault()

    if (structureEditDisabled) {
      return
    }

    const isCopy = event.ctrlKey || event.metaKey || event.dataTransfer.dropEffect === 'copy'

    await runMutation(async () => {
      if (isCopy) {
        await onCopyBlocks(payloadIds, previousBlockId)
      } else {
        await onMoveBlocks(payloadIds, previousBlockId)
      }
    })

    setSelectedIds(new Set())
  }

  const handleDropOver = (event: DragEvent<HTMLDivElement>) => {
    if (!hasVisualDragPayload(event)) {
      return
    }
    event.preventDefault()
    event.dataTransfer.dropEffect = event.ctrlKey || event.metaKey ? 'copy' : 'move'
  }

  const toggleTypeVisibility = (blockTypeId: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev)
      if (next.has(blockTypeId)) {
        next.delete(blockTypeId)
      } else {
        next.add(blockTypeId)
      }
      return next
    })
  }

  const insertAfterActiveBlock = async () => {
    if (insertDisabled || !activeDocumentBlockId) {
      return
    }

    await runMutation(async () => {
      await onInsertBlock(insertType, activeDocumentBlockId)
    })
  }

  const deleteCurrentSelection = async () => {
    if (structureEditDisabled || selectedBlocksInOrder.length === 0) {
      return
    }

    await runMutation(async () => {
      await onDeleteBlocks(selectedBlocksInOrder.map((block) => block.block_id))
    })
    setSelectedIds(new Set())
  }

  const copyCurrentSelectionToClipboard = async () => {
    if (selectionActionDisabled) {
      return
    }

    await runMutation(async () => {
      await onCopyBlocksToClipboard(selectedBlocksInOrder.map((block) => block.block_id))
    })
  }

  const cutCurrentSelectionToClipboard = async () => {
    if (selectionActionDisabled) {
      return
    }

    let didCut = false
    await runMutation(async () => {
      didCut = await onCutBlocksToClipboard(selectedBlocksInOrder.map((block) => block.block_id))
    })
    if (didCut) {
      setSelectedIds(new Set())
    }
  }

  const pasteActiveClipboardAfterActiveBlock = async () => {
    if (structureEditDisabled || !hasActiveClipboardClip || !activeDocumentBlockId) {
      return
    }

    await runMutation(async () => {
      await onPasteActiveClipboard()
    })
  }

  if (!isVisible) {
    return null
  }

  return (
    <section className="border-b border-gray-200 bg-white flex-shrink-0">
      <div className="ui-pane-header flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="ui-pane-title">VisualEditor</div>
          <button
            type="button"
            onClick={() => setMode((prev) => (prev === 'viewer' ? 'editor' : 'viewer'))}
            className="ui-btn rounded-full"
          >
            Edit: {mode === 'editor' ? 'ON' : 'OFF'}
          </button>
          <div className="text-xs text-gray-500">
            {blocks.length} blocks
            {mode === 'editor' && selectedIds.size > 0 ? ` | ${selectedIds.size} selected` : ''}
          </div>
        </div>
      </div>

      <div className="px-4 pb-3 space-y-3">
          {mode === 'viewer' && uniqueTypes.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
                {uniqueTypes.map((blockTypeId) => {
                  const isHidden = hiddenTypes.has(blockTypeId)
                return (
                  <button
                    key={blockTypeId}
                    type="button"
                    onClick={() => toggleTypeVisibility(blockTypeId)}
                    className={`ui-btn ${
                      isHidden
                        ? 'border-gray-300 text-gray-500 bg-gray-50'
                        : 'border-blue-300 text-blue-700 bg-blue-50'
                    }`}
                  >
                    {isHidden ? 'Show' : 'Hide'} {getBlockTypeLabel(blockTypeId)}
                  </button>
                )
              })}
              <button
                type="button"
                onClick={() => setHiddenTypes(new Set())}
                className="ui-btn"
              >
                Show all
              </button>
            </div>
          )}

          {mode === 'editor' && (
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={insertType}
                onChange={(event) => setInsertType(event.target.value)}
                className="ui-select w-auto"
                disabled={structureEditDisabled || operationTypes.length === 0}
              >
                {operationTypes.map((entry) => (
                  <option key={entry.type_id} value={String(entry.type_id)}>
                    {entry.library_name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  void insertAfterActiveBlock()
                }}
                disabled={insertDisabled}
                className="ui-btn"
              >
                Insert after active
              </button>
              {operationTypesLoading && (
                <span className="text-xs text-gray-500">Loading operations...</span>
              )}
              {operationTypesError && (
                <span className="text-xs text-red-700">{operationTypesError}</span>
              )}
              <button
                type="button"
                onClick={() => {
                  void copyCurrentSelectionToClipboard()
                }}
                disabled={selectionActionDisabled}
                className="ui-btn"
              >
                Copy
              </button>
              <button
                type="button"
                onClick={() => {
                  void cutCurrentSelectionToClipboard()
                }}
                disabled={selectionActionDisabled}
                className="ui-btn-danger"
              >
                Cut
              </button>
              <button
                type="button"
                onClick={() => {
                  void pasteActiveClipboardAfterActiveBlock()
                }}
                disabled={structureEditDisabled || !hasActiveClipboardClip || !activeDocumentBlockId}
                className="ui-btn-primary"
              >
                Paste active
              </button>
              {activeClipboardLabel && (
                <span className="max-w-[160px] truncate text-xs text-gray-500">
                  {activeClipboardLabel}
                </span>
              )}
              <button
                type="button"
                onClick={() => {
                  void deleteCurrentSelection()
                }}
                disabled={selectionActionDisabled}
                className="ui-btn-danger"
              >
                Delete selected
              </button>
              <button
                type="button"
                onClick={() => setSelectedIds(new Set())}
                disabled={selectedIds.size === 0}
                className="ui-btn"
              >
                Clear selection
              </button>
            </div>
          )}

          <div className="overflow-x-auto">
            <div className="inline-flex items-center gap-2 min-w-full pb-1">
              <Tooltip content={mode === 'editor' ? 'Drop before first block' : null}>
                <div
                  className="w-4 h-8 rounded border border-dashed border-gray-300"
                  onDragOver={handleDropOver}
                  onDrop={(event) => {
                    void handleDropAt(event, null)
                  }}
                  aria-label={mode === 'editor' ? 'Drop before first block' : undefined}
                />
              </Tooltip>

              {visibleBlocks.map((block) => {
                const isSelected = selectedIds.has(block.block_id)
                const isActive = activeDocumentBlockId === block.block_id

                return (
                  <div key={block.block_id} className="inline-flex items-center gap-2">
                    <Tooltip content={`${getBlockDisplayLabel(block)} (${block.block_id})`}>
                      <button
                        type="button"
                        draggable={mode === 'editor' && !structureEditDisabled}
                        onDragStart={(event) => handleDragStart(event, block.block_id)}
                        onClick={(event) => handleBlockClick(event, block.block_id)}
                        className={`min-w-[64px] h-12 px-2 rounded border text-xs font-semibold flex flex-col items-center justify-center ${
                          isActive
                            ? 'border-blue-700 bg-blue-100 text-blue-900 ring-2 ring-blue-600 ring-offset-1'
                            : isSelected
                            ? 'border-blue-600 bg-blue-50 text-blue-700'
                            : 'border-gray-300 bg-gray-50 text-gray-700 hover:bg-gray-100'
                        }`}
                        aria-label={`${getBlockDisplayLabel(block)} (${block.block_id})`}
                      >
                        <span>{getBlockDisplayIcon(block)}</span>
                        <span className="text-xs truncate max-w-[52px]">
                          {getBlockDisplayLabel(block)}
                        </span>
                      </button>
                    </Tooltip>

                    <Tooltip content={mode === 'editor' ? 'Drop after this block' : null}>
                      <div
                        className="w-4 h-8 rounded border border-dashed border-gray-300"
                        onDragOver={handleDropOver}
                        onDrop={(event) => {
                          void handleDropAt(event, block.block_id)
                        }}
                        aria-label={mode === 'editor' ? 'Drop after this block' : undefined}
                      />
                    </Tooltip>
                  </div>
                )
              })}

              {visibleBlocks.length === 0 && (
                <div className="text-xs text-gray-500 py-2">No blocks to display in current mode.</div>
              )}
            </div>
          </div>

          {mode === 'editor' && (
            <div className="text-sm text-gray-500">
              Drag selected block icons to reorder. Hold Ctrl (or Cmd) while dropping to copy instead of move.
            </div>
          )}
      </div>
    </section>
  )
}
