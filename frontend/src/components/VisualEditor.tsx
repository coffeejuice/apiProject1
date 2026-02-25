import { DragEvent, MouseEvent, useMemo, useState } from 'react'
import type { BlockData } from './blocks'
import { BLOCK_LIBRARY_TYPES, getBlockTypeIcon, getBlockTypeLabel } from '../lib/blockTypeMeta'

type VisualEditorMode = 'viewer' | 'editor'

interface VisualEditorProps {
  blocks: BlockData[]
  isVisible: boolean
  hasUnsavedChanges: boolean
  onNavigate: (blockId: string) => void
  onInsertBlock: (blockTypeId: string, previousBlockId: string | null) => Promise<void>
  onMoveBlocks: (blockIds: string[], previousBlockId: string | null) => Promise<void>
  onCopyBlocks: (blockIds: string[], previousBlockId: string | null) => Promise<void>
  onDeleteBlocks: (blockIds: string[]) => Promise<void>
}

function getDropPayload(event: DragEvent<HTMLElement>): string[] {
  const payload = event.dataTransfer.getData('application/x-technonotion-visual-block-ids')
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

export default function VisualEditor({
  blocks,
  isVisible,
  hasUnsavedChanges,
  onNavigate,
  onInsertBlock,
  onMoveBlocks,
  onCopyBlocks,
  onDeleteBlocks,
}: VisualEditorProps) {
  const [mode, setMode] = useState<VisualEditorMode>('viewer')
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set())
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [insertType, setInsertType] = useState<string>(BLOCK_LIBRARY_TYPES[0]?.id || 'paragraph')
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

    event.dataTransfer.setData('application/x-technonotion-visual-block-ids', JSON.stringify(payloadIds))
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
    const payloadIds = getDropPayload(event)
    if (payloadIds.length === 0) {
      return
    }
    event.preventDefault()
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

  const insertAfterCurrentSelection = async () => {
    if (structureEditDisabled) {
      return
    }

    const insertionPoint =
      selectedBlocksInOrder[selectedBlocksInOrder.length - 1]?.block_id ||
      blocks[blocks.length - 1]?.block_id ||
      null

    await runMutation(async () => {
      await onInsertBlock(insertType, insertionPoint)
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
          {hasUnsavedChanges && (
            <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
              Save or cancel draft changes before using VisualEditor structural actions.
            </div>
          )}

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
                disabled={structureEditDisabled}
              >
                {BLOCK_LIBRARY_TYPES.map((entry) => (
                  <option key={entry.id} value={entry.id}>
                    {entry.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  void insertAfterCurrentSelection()
                }}
                disabled={structureEditDisabled}
                className="ui-btn"
              >
                Insert after selection
              </button>
              <button
                type="button"
                onClick={() => {
                  void deleteCurrentSelection()
                }}
                disabled={structureEditDisabled || selectedBlocksInOrder.length === 0}
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
              <div
                className="w-4 h-8 rounded border border-dashed border-gray-300"
                onDragOver={handleDropOver}
                onDrop={(event) => {
                  void handleDropAt(event, null)
                }}
                title={mode === 'editor' ? 'Drop before first block' : undefined}
              />

              {visibleBlocks.map((block) => {
                const isSelected = selectedIds.has(block.block_id)

                return (
                  <div key={block.block_id} className="inline-flex items-center gap-2">
                    <button
                      type="button"
                      draggable={mode === 'editor' && !structureEditDisabled}
                      onDragStart={(event) => handleDragStart(event, block.block_id)}
                      onClick={(event) => handleBlockClick(event, block.block_id)}
                      className={`min-w-[64px] h-12 px-2 rounded border text-xs font-semibold flex flex-col items-center justify-center ${
                        isSelected
                          ? 'border-blue-600 bg-blue-50 text-blue-700'
                          : 'border-gray-300 bg-gray-50 text-gray-700 hover:bg-gray-100'
                      }`}
                      title={`${getBlockTypeLabel(block.block_type_id)} (${block.block_id})`}
                    >
                      <span>{getBlockTypeIcon(block.block_type_id)}</span>
                      <span className="text-xs truncate max-w-[52px]">
                        {getBlockTypeLabel(block.block_type_id)}
                      </span>
                    </button>

                    <div
                      className="w-4 h-8 rounded border border-dashed border-gray-300"
                      onDragOver={handleDropOver}
                      onDrop={(event) => {
                        void handleDropAt(event, block.block_id)
                      }}
                      title={mode === 'editor' ? 'Drop after this block' : undefined}
                    />
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
