import { MouseEvent, useEffect, useMemo } from 'react'
import { getBlockTypeLabel } from '../../lib/blockTypeMeta'
import { ClipboardClip, useBlockClipboardStore } from '../../stores/useBlockClipboardStore'
import type { BlockData } from '../../types/api'

interface ClipboardPaneProps {
  onPasteClip: (clipId: string) => void
}

function getOperationLibraryName(block: BlockData): string | null {
  const operationType = block.props?.operation_type
  if (!operationType || typeof operationType !== 'object') {
    return null
  }
  const libraryName = (operationType as { library_name?: unknown }).library_name
  return typeof libraryName === 'string' && libraryName.trim() ? libraryName : null
}

function getClipboardBlockName(block: BlockData): string {
  const title = block.props?.title
  if (typeof title === 'string' && title.trim()) {
    return title
  }
  return getOperationLibraryName(block) || getBlockTypeLabel(block.block_type_id)
}

function getClipHeading(clip: ClipboardClip): string {
  const firstBlockName = clip.blocks[0] ? getClipboardBlockName(clip.blocks[0]) : 'Empty clip'
  const suffix = clip.blocks.length > 1 ? ` +${clip.blocks.length - 1}` : ''
  return `${firstBlockName}${suffix}`
}

function stopContainerActivation(event: MouseEvent<HTMLElement>) {
  event.stopPropagation()
}

export default function ClipboardPane({ onPasteClip }: ClipboardPaneProps) {
  const clips = useBlockClipboardStore((state) => state.clips)
  const activeClipId = useBlockClipboardStore((state) => state.activeClipId)
  const selectedClipIds = useBlockClipboardStore((state) => state.selectedClipIds)
  const maxClips = useBlockClipboardStore((state) => state.maxClips)
  const setActiveClip = useBlockClipboardStore((state) => state.setActiveClip)
  const toggleSelectedClip = useBlockClipboardStore((state) => state.toggleSelectedClip)
  const removeClip = useBlockClipboardStore((state) => state.removeClip)
  const removeSelectedClips = useBlockClipboardStore((state) => state.removeSelectedClips)
  const removeAllClips = useBlockClipboardStore((state) => state.removeAllClips)
  const setMaxClips = useBlockClipboardStore((state) => state.setMaxClips)

  useEffect(() => {
    if (clips.length > 0 && !activeClipId) {
      setActiveClip(clips[0].id)
    }
  }, [activeClipId, clips, setActiveClip])

  const selectedCount = selectedClipIds.size
  const hasClips = clips.length > 0
  const topButtonLabel = selectedCount > 0 ? 'Remove selected' : 'Remove all'

  const clipRows = useMemo(() => {
    return clips.map((clip) => ({
      clip,
      heading: getClipHeading(clip),
      blockNames: clip.blocks.map((block) => getClipboardBlockName(block)),
    }))
  }, [clips])

  return (
    <div className="space-y-3">
      <div className="ui-card ui-card-body space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-sm font-semibold text-gray-900">Clipboard</div>
            <div className="text-xs text-gray-500">Frontend session only</div>
          </div>
          <label className="flex items-center gap-1 text-xs text-gray-600">
            Memory
            <input
              type="number"
              min={1}
              max={99}
              value={maxClips}
              onChange={(event) => setMaxClips(Number(event.target.value))}
              className="ui-input w-16"
            />
          </label>
        </div>

        <button
          type="button"
          onClick={selectedCount > 0 ? removeSelectedClips : removeAllClips}
          disabled={!hasClips}
          className={selectedCount > 0 ? 'ui-btn-danger w-full' : 'ui-btn w-full'}
        >
          {topButtonLabel}
        </button>
      </div>

      {!hasClips ? (
        <div className="ui-card ui-card-body text-sm text-gray-500">
          Copy or cut blocks from VisualEditor to create clipboard entries.
        </div>
      ) : (
        <div className="space-y-2">
          {clipRows.map(({ clip, heading, blockNames }) => {
            const isActive = clip.id === activeClipId
            const isSelected = selectedClipIds.has(clip.id)
            const createdAt = new Date(clip.createdAt).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })

            return (
              <div
                key={clip.id}
                onClick={() => setActiveClip(clip.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    setActiveClip(clip.id)
                  }
                }}
                role="button"
                tabIndex={0}
                aria-pressed={isActive}
                className={`w-full rounded border bg-white p-2 text-left shadow-sm transition-colors ${
                  isActive
                    ? 'border-blue-600 bg-blue-50 text-blue-950'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                <div className="mb-2 flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleSelectedClip(clip.id)}
                    onClick={stopContainerActivation}
                    className="h-3.5 w-3.5"
                    aria-label={`Select clipboard entry ${heading}`}
                  />
                  <span className="ui-badge shrink-0 uppercase">{clip.mode}</span>
                  <span className="min-w-0 flex-1 truncate text-sm font-semibold">{heading}</span>
                  <span className="shrink-0 text-xs text-gray-500">{createdAt}</span>
                  <button
                    type="button"
                    onClick={(event) => {
                      stopContainerActivation(event)
                      onPasteClip(clip.id)
                    }}
                    className="ui-btn-primary shrink-0"
                  >
                    Paste
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      stopContainerActivation(event)
                      removeClip(clip.id)
                    }}
                    className="ui-btn shrink-0"
                  >
                    Remove
                  </button>
                </div>

                <div className="mb-2 flex gap-1 overflow-hidden">
                  {blockNames.slice(0, 6).map((name, index) => (
                    <span
                      key={`${clip.id}-${index}`}
                      className="max-w-[92px] truncate rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-xs text-gray-700"
                    >
                      {name}
                    </span>
                  ))}
                  {blockNames.length > 6 ? (
                    <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-xs text-gray-500">
                      +{blockNames.length - 6}
                    </span>
                  ) : null}
                </div>

                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0 truncate text-xs text-gray-500">
                    {clip.blocks.length} block{clip.blocks.length === 1 ? '' : 's'}
                    {clip.sourceDocumentId ? ` from document ${clip.sourceDocumentId}` : ''}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
