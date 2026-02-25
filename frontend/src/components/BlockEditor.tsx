import {
  useCallback,
  DragEvent,
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { apiClient } from '../lib/apiClient'
import { applyFieldLengthLimits } from '../lib/blockFieldLimits'
import { getBlockComponent, BlockData } from './blocks'
import type {
  DocumentLineageResponse,
  EditSession,
  EditSessionListResponse,
  Operation,
} from '../types/api'

interface EditorSnapshot {
  blocks: BlockData[]
}

export type EditorSaveStatus = 'idle' | 'saving' | 'saved' | 'error'

export interface BlockEditorMeta {
  isLoading: boolean
  draftDocumentName: string
  sourceDocumentId: number | null
  saveStatus: EditorSaveStatus
  saveError: string | null
  hasUnsavedChanges: boolean
  changedBlocksCount: number
  canUndo: boolean
  canRedo: boolean
  isLineageLoading: boolean
  isSessionsLoading: boolean
}

export interface RefreshEditorOptions {
  preserveScroll?: boolean
  refreshDocument?: boolean
}

export interface BlockEditorHandle {
  saveChanges: () => Promise<boolean>
  cancelChanges: () => Promise<boolean>
  undo: () => void
  redo: () => void
  showLineage: () => Promise<void>
  showSessions: () => Promise<void>
  refresh: (options?: RefreshEditorOptions) => Promise<void>
  scrollToBlock: (blockId: string) => void
  insertBlock: (
    blockTypeId: string,
    previousBlockId?: string | null,
    props?: Record<string, unknown>
  ) => Promise<boolean>
  deleteBlocks: (blockIds: string[]) => Promise<boolean>
  moveBlocks: (blockIds: string[], previousBlockId: string | null) => Promise<boolean>
  copyBlocks: (blockIds: string[], previousBlockId: string | null) => Promise<boolean>
  getBlocks: () => BlockData[]
  hasUnsavedChanges: () => boolean
}

interface BlockEditorProps {
  className?: string
  onMetaChange?: (meta: BlockEditorMeta) => void
  onBlocksChange?: (blocks: BlockData[]) => void
}

function cloneProps(props: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(props || {}))
}

function cloneBlocks(blocks: BlockData[]): BlockData[] {
  return blocks.map((block) => ({
    ...block,
    props: cloneProps((block.props || {}) as Record<string, unknown>),
  }))
}

function deepEqual(left: unknown, right: unknown): boolean {
  if (left === right) {
    return true
  }

  if (left === null || right === null || left === undefined || right === undefined) {
    return false
  }

  if (typeof left !== typeof right) {
    return false
  }

  if (Array.isArray(left) && Array.isArray(right)) {
    if (left.length !== right.length) {
      return false
    }
    for (let index = 0; index < left.length; index += 1) {
      if (!deepEqual(left[index], right[index])) {
        return false
      }
    }
    return true
  }

  if (Array.isArray(left) || Array.isArray(right)) {
    return false
  }

  if (typeof left === 'object' && typeof right === 'object') {
    const leftRecord = left as Record<string, unknown>
    const rightRecord = right as Record<string, unknown>
    const leftKeys = Object.keys(leftRecord)
    const rightKeys = Object.keys(rightRecord)

    if (leftKeys.length !== rightKeys.length) {
      return false
    }

    for (const key of leftKeys) {
      if (!Object.prototype.hasOwnProperty.call(rightRecord, key)) {
        return false
      }
      if (!deepEqual(leftRecord[key], rightRecord[key])) {
        return false
      }
    }
    return true
  }

  return false
}

function withFallbackErrorMessage(message: string | undefined, fallback: string): string {
  if (!message) {
    return fallback
  }
  return message
}

const BlockEditor = forwardRef<BlockEditorHandle, BlockEditorProps>(function BlockEditor(
  { className, onMetaChange, onBlocksChange },
  ref
) {
  const [savedBlocks, setSavedBlocks] = useState<BlockData[]>([])
  const [draftBlocks, setDraftBlocks] = useState<BlockData[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [saveStatus, setSaveStatus] = useState<EditorSaveStatus>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [lineage, setLineage] = useState<DocumentLineageResponse | null>(null)
  const [showLineage, setShowLineage] = useState(false)
  const [isLineageLoading, setIsLineageLoading] = useState(false)
  const [sessions, setSessions] = useState<EditSession[]>([])
  const [showSessions, setShowSessions] = useState(false)
  const [isSessionsLoading, setIsSessionsLoading] = useState(false)
  const [undoStack, setUndoStack] = useState<EditorSnapshot[]>([])
  const [redoStack, setRedoStack] = useState<EditorSnapshot[]>([])
  const activeSessionIdRef = useRef<string | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)

  const { currentDoc, fetchDocument } = useDocumentsStore()

  const cloneSnapshot = (): EditorSnapshot => ({
    blocks: cloneBlocks(draftBlocks),
  })

  const savedBlocksById = useMemo(
    () => new Map(savedBlocks.map((block) => [block.block_id, block])),
    [savedBlocks]
  )

  const changedBlocks = useMemo(() => {
    return draftBlocks.filter((block) => {
      const savedBlock = savedBlocksById.get(block.block_id)
      if (!savedBlock) {
        return true
      }
      return !deepEqual(savedBlock.props, block.props)
    })
  }, [draftBlocks, savedBlocksById])

  const hasUnsavedChanges = changedBlocks.length > 0

  const draftDocumentName = useMemo(() => {
    const headingBlock = draftBlocks.find((block) => block.block_type_id === 'document_heading')
    const headingName = headingBlock?.props?.name
    if (typeof headingName === 'string' && headingName.trim().length > 0) {
      return headingName
    }
    return currentDoc?.name || ''
  }, [draftBlocks, currentDoc?.name])

  const loadEditorState = useCallback(
    async (
      docId: string,
      refreshDocument: boolean,
      options?: { showLoading?: boolean; preserveScroll?: boolean }
    ) => {
      const showLoading = options?.showLoading ?? true
      const preserveScroll = options?.preserveScroll ?? false
      const scrollTopBefore = preserveScroll ? scrollContainerRef.current?.scrollTop ?? null : null

      if (showLoading) {
        setIsLoading(true)
      }

      try {
        const [response] = await Promise.all([
          apiClient.get<BlockData[]>(`/documents/${docId}/blocks/root`),
          refreshDocument ? fetchDocument(docId) : Promise.resolve(null),
        ])

        const loadedBlocks = response.ok && response.data ? cloneBlocks(response.data) : []
        setSavedBlocks(loadedBlocks)
        setDraftBlocks(cloneBlocks(loadedBlocks))
        setUndoStack([])
        setRedoStack([])

        if (scrollTopBefore !== null) {
          requestAnimationFrame(() => {
            if (scrollContainerRef.current) {
              scrollContainerRef.current.scrollTop = scrollTopBefore
            }
          })
        }
      } finally {
        if (showLoading) {
          setIsLoading(false)
        }
      }
    },
    [fetchDocument]
  )

  const currentDocId = currentDoc?.id

  useEffect(() => {
    if (!currentDoc?.id) {
      setSavedBlocks([])
      setDraftBlocks([])
      setSaveStatus('idle')
      setSaveError(null)
      setShowLineage(false)
      setShowSessions(false)
      setLineage(null)
      setSessions([])
      activeSessionIdRef.current = null
      setUndoStack([])
      setRedoStack([])
      setIsLoading(false)
      return
    }

    void loadEditorState(String(currentDoc.id), false)
  }, [currentDoc?.id, loadEditorState])

  useEffect(() => {
    if (!currentDocId) {
      return
    }

    let active = true
    const docId = currentDocId

    const startSession = async () => {
      const response = await apiClient.post<EditSession>(`/documents/${docId}/sessions/start`, {
        body: {},
      })
      if (active && response.ok && response.data) {
        activeSessionIdRef.current = response.data.session_id
      }
    }

    void startSession()

    return () => {
      active = false
      const sessionId = activeSessionIdRef.current
      if (sessionId) {
        activeSessionIdRef.current = null
        void apiClient.post(`/documents/${docId}/sessions/${sessionId}/end`, {
          body: {},
        })
      }
    }
  }, [currentDocId])

  useEffect(() => {
    if (!onBlocksChange) {
      return
    }
    onBlocksChange(cloneBlocks(draftBlocks))
  }, [draftBlocks, onBlocksChange])

  useEffect(() => {
    if (!onMetaChange) {
      return
    }

    onMetaChange({
      isLoading,
      draftDocumentName,
      sourceDocumentId: currentDoc?.source_document_id ?? null,
      saveStatus,
      saveError,
      hasUnsavedChanges,
      changedBlocksCount: changedBlocks.length,
      canUndo: undoStack.length > 0,
      canRedo: redoStack.length > 0,
      isLineageLoading,
      isSessionsLoading,
    })
  }, [
    changedBlocks.length,
    currentDoc?.source_document_id,
    draftDocumentName,
    hasUnsavedChanges,
    isLineageLoading,
    isLoading,
    isSessionsLoading,
    onMetaChange,
    redoStack.length,
    saveError,
    saveStatus,
    undoStack.length,
  ])

  const handleUndo = () => {
    if (undoStack.length === 0) return
    const target = undoStack[undoStack.length - 1]
    const current = cloneSnapshot()
    setUndoStack((prev) => prev.slice(0, -1))
    setRedoStack((prev) => [...prev, current])
    setDraftBlocks(cloneBlocks(target.blocks))
  }

  const handleRedo = () => {
    if (redoStack.length === 0) return
    const target = redoStack[redoStack.length - 1]
    const current = cloneSnapshot()
    setRedoStack((prev) => prev.slice(0, -1))
    setUndoStack((prev) => [...prev, current])
    setDraftBlocks(cloneBlocks(target.blocks))
  }

  const handleBlockUpdate = (blockId: string, props: Record<string, unknown>) => {
    const currentBlock = draftBlocks.find((block) => block.block_id === blockId)
    if (!currentBlock) {
      return
    }

    const constrainedProps = applyFieldLengthLimits(
      props,
      currentBlock.field_limits
    ) as Record<string, unknown>

    if (deepEqual(currentBlock.props, constrainedProps)) {
      return
    }

    const before = cloneSnapshot()

    setDraftBlocks((prev) =>
      prev.map((block) =>
        block.block_id === blockId
          ? { ...block, props: cloneProps(constrainedProps) }
          : block
      )
    )
    setUndoStack((prev) => [...prev, before])
    setRedoStack([])
    setSaveStatus('idle')
    setSaveError(null)
  }

  const handleSaveChanges = async (): Promise<boolean> => {
    if (!currentDoc || changedBlocks.length === 0) {
      return false
    }

    setSaveStatus('saving')
    setSaveError(null)

    const ops: Operation[] = changedBlocks.map((block) => ({
      op_type: 'update_props',
      data: {
        block_id: block.block_id,
        props: block.props,
      },
    }))

    const response = await apiClient.post<{ success: boolean; message?: string }>(
      `/documents/${currentDoc.id}/commit`,
      {
        body: { ops },
      }
    )

    if (!response.ok || !response.data?.success) {
      setSaveStatus('error')
      setSaveError(response.errorMessage || response.data?.message || 'Failed to save changes')
      return false
    }

    await loadEditorState(String(currentDoc.id), true, {
      showLoading: false,
      preserveScroll: true,
    })
    setSaveStatus('saved')
    setTimeout(() => setSaveStatus('idle'), 1500)
    return true
  }

  const handleCancelChanges = async (): Promise<boolean> => {
    if (!currentDoc || !hasUnsavedChanges) {
      return false
    }

    setSaveError(null)
    await loadEditorState(String(currentDoc.id), true, {
      showLoading: false,
      preserveScroll: true,
    })
    setSaveStatus('idle')
    return true
  }

  const handleShowLineage = async () => {
    if (!currentDoc) return
    setIsLineageLoading(true)
    const response = await apiClient.get<DocumentLineageResponse>(
      `/documents/${currentDoc.id}/lineage`
    )
    if (response.ok && response.data) {
      setLineage(response.data)
      setShowLineage(true)
    } else {
      setSaveStatus('error')
      setSaveError(response.errorMessage || 'Failed to load lineage')
    }
    setIsLineageLoading(false)
  }

  const handleShowSessions = async () => {
    if (!currentDoc) return
    setIsSessionsLoading(true)
    const response = await apiClient.get<EditSessionListResponse>(
      `/documents/${currentDoc.id}/sessions`
    )
    if (response.ok && response.data) {
      setSessions(response.data.sessions || [])
      setShowSessions(true)
    } else {
      setSaveStatus('error')
      setSaveError(response.errorMessage || 'Failed to load sessions')
    }
    setIsSessionsLoading(false)
  }

  const refreshEditor = async (options?: RefreshEditorOptions) => {
    if (!currentDoc?.id) {
      return
    }

    await loadEditorState(String(currentDoc.id), options?.refreshDocument ?? false, {
      showLoading: false,
      preserveScroll: options?.preserveScroll ?? false,
    })
  }

  const scrollToBlock = (blockId: string) => {
    const element = document.getElementById(`block-${blockId}`)
    if (!element) {
      return
    }
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const ensureStructureEditAllowed = (): boolean => {
    if (!currentDoc) {
      setSaveStatus('error')
      setSaveError('Select a document first')
      return false
    }

    if (hasUnsavedChanges) {
      setSaveStatus('error')
      setSaveError('Save or cancel unsaved changes before modifying block structure')
      return false
    }

    return true
  }

  const getOrderedBlocksByIds = (blockIds: string[]): BlockData[] => {
    const idSet = new Set(blockIds)
    return draftBlocks.filter((block) => idSet.has(block.block_id))
  }

  const handleInsertBlock = async (
    blockTypeId: string,
    previousBlockId: string | null = null,
    props: Record<string, unknown> = {}
  ): Promise<boolean> => {
    if (!ensureStructureEditAllowed() || !currentDoc) {
      return false
    }

    const response = await apiClient.post<BlockData>(`/documents/${currentDoc.id}/blocks`, {
      body: {
        block_type_id: blockTypeId,
        props,
        previous_block_id: previousBlockId,
      },
    })

    if (!response.ok) {
      setSaveStatus('error')
      setSaveError(withFallbackErrorMessage(response.errorMessage, 'Failed to insert block'))
      return false
    }

    await refreshEditor()
    setSaveStatus('idle')
    setSaveError(null)
    return true
  }

  const handleDeleteBlocks = async (blockIds: string[]): Promise<boolean> => {
    if (!ensureStructureEditAllowed()) {
      return false
    }

    const targets = getOrderedBlocksByIds(blockIds).filter((block) => block.is_removable)
    if (targets.length === 0) {
      setSaveStatus('error')
      setSaveError('No removable blocks selected')
      return false
    }

    const responses = await Promise.all(
      targets.map((block) => apiClient.delete(`/blocks/${block.block_id}`))
    )

    const failed = responses.find((response) => !response.ok)
    if (failed) {
      setSaveStatus('error')
      setSaveError(withFallbackErrorMessage(failed.errorMessage, 'Failed to delete selected blocks'))
      await refreshEditor()
      return false
    }

    await refreshEditor()
    setSaveStatus('idle')
    setSaveError(null)
    return true
  }

  const handleMoveBlocks = async (
    blockIds: string[],
    previousBlockId: string | null
  ): Promise<boolean> => {
    if (!ensureStructureEditAllowed()) {
      return false
    }

    const orderedMovableBlocks = getOrderedBlocksByIds(blockIds).filter(
      (block) => block.fixed_position === null
    )

    if (orderedMovableBlocks.length === 0) {
      setSaveStatus('error')
      setSaveError('No movable blocks selected')
      return false
    }

    let pointer = previousBlockId
    for (const block of orderedMovableBlocks) {
      const targetPreviousId = pointer === block.block_id ? block.previous_block_id : pointer

      const response = await apiClient.post(`/blocks/${block.block_id}/move`, {
        body: {
          previous_block_id: targetPreviousId,
        },
      })

      if (!response.ok) {
        setSaveStatus('error')
        setSaveError(
          withFallbackErrorMessage(response.errorMessage, `Failed to move block ${block.block_id}`)
        )
        await refreshEditor()
        return false
      }

      pointer = block.block_id
    }

    await refreshEditor()
    setSaveStatus('idle')
    setSaveError(null)
    return true
  }

  const handleCopyBlocks = async (
    blockIds: string[],
    previousBlockId: string | null
  ): Promise<boolean> => {
    if (!ensureStructureEditAllowed() || !currentDoc) {
      return false
    }

    const orderedCopyableBlocks = getOrderedBlocksByIds(blockIds).filter(
      (block) => !block.is_system
    )

    if (orderedCopyableBlocks.length === 0) {
      setSaveStatus('error')
      setSaveError('No copyable blocks selected')
      return false
    }

    let pointer = previousBlockId
    for (const block of orderedCopyableBlocks) {
      const response = await apiClient.post<BlockData>(`/documents/${currentDoc.id}/blocks`, {
        body: {
          block_type_id: block.block_type_id,
          props: cloneProps(block.props as Record<string, unknown>),
          previous_block_id: pointer,
        },
      })

      if (!response.ok || !response.data) {
        setSaveStatus('error')
        setSaveError(
          withFallbackErrorMessage(response.errorMessage, `Failed to copy block ${block.block_id}`)
        )
        await refreshEditor()
        return false
      }

      pointer = response.data.block_id
    }

    await refreshEditor()
    setSaveStatus('idle')
    setSaveError(null)
    return true
  }

  useImperativeHandle(ref, () => ({
    saveChanges: handleSaveChanges,
    cancelChanges: handleCancelChanges,
    undo: handleUndo,
    redo: handleRedo,
    showLineage: handleShowLineage,
    showSessions: handleShowSessions,
    refresh: refreshEditor,
    scrollToBlock,
    insertBlock: handleInsertBlock,
    deleteBlocks: handleDeleteBlocks,
    moveBlocks: handleMoveBlocks,
    copyBlocks: handleCopyBlocks,
    getBlocks: () => cloneBlocks(draftBlocks),
    hasUnsavedChanges: () => hasUnsavedChanges,
  }))

  const handleCanvasDragOver = (event: DragEvent<HTMLDivElement>) => {
    const blockType = event.dataTransfer.getData('application/x-forgelab-block-type')
    if (!blockType) {
      return
    }
    event.preventDefault()
  }

  const handleCanvasDrop = async (event: DragEvent<HTMLDivElement>) => {
    const blockType = event.dataTransfer.getData('application/x-forgelab-block-type')
    if (!blockType) {
      return
    }

    event.preventDefault()
    const previousBlockId =
      draftBlocks.length > 0 ? draftBlocks[draftBlocks.length - 1].block_id : null
    await handleInsertBlock(blockType, previousBlockId)
  }

  if (!currentDoc) {
    return (
      <div className={`flex items-center justify-center h-full text-gray-500 ${className || ''}`}>
        Select a document to start editing
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center h-full ${className || ''}`}>
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div className={`flex flex-col h-full min-h-0 ${className || ''}`}>
      {saveError && saveStatus === 'error' && (
        <div className="mx-4 mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          {saveError}
        </div>
      )}

      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto bg-gray-100"
        onDragOver={handleCanvasDragOver}
        onDrop={(event) => {
          void handleCanvasDrop(event)
        }}
      >
        <div className="max-w-4xl mx-auto py-4 px-4 space-y-3">
          {draftBlocks.length === 0 ? (
            <div className="text-center text-gray-500 py-8 text-sm">No blocks found in this document.</div>
          ) : (
            draftBlocks.map((block) => {
              const BlockComponent = getBlockComponent(block.block_type_id)
              const baselineProps = savedBlocksById.get(block.block_id)?.props || {}

              if (!BlockComponent) {
                return (
                  <div
                    key={block.block_id}
                    id={`block-${block.block_id}`}
                    data-block-id={block.block_id}
                    className="ui-card ui-card-body"
                  >
                    <div className="text-red-600">Unknown block type: {block.block_type_id}</div>
                    <pre className="text-xs text-gray-600 mt-2">
                      {JSON.stringify(block, null, 2)}
                    </pre>
                  </div>
                )
              }

              return (
                <div
                  key={block.block_id}
                  id={`block-${block.block_id}`}
                  data-block-id={block.block_id}
                  className="scroll-mt-28"
                >
                  <BlockComponent
                    block={block}
                    baselineProps={baselineProps}
                    onUpdate={handleBlockUpdate}
                    isReadOnly={false}
                  />
                </div>
              )
            })
          )}
        </div>
      </div>

      {showLineage && lineage && (
        <div className="ui-modal-overlay">
          <div className="ui-modal w-full max-w-3xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold">Document Lineage</h2>
              <button
                type="button"
                onClick={() => setShowLineage(false)}
                className="ui-btn"
              >
                Close
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-sm font-semibold mb-2">Ancestors</h3>
                {lineage.ancestors.length === 0 ? (
                  <p className="text-sm text-gray-500">No ancestors</p>
                ) : (
                  <ul className="space-y-2">
                    {lineage.ancestors.map((node) => (
                      <li key={`ancestor-${node.document_id}`} className="ui-card ui-card-body text-sm">
                        <div className="font-medium text-sm">{node.name}</div>
                        <div className="text-xs text-gray-500">ID: {node.document_id}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <h3 className="text-sm font-semibold mb-2">Descendants</h3>
                {lineage.descendants.length === 0 ? (
                  <p className="text-sm text-gray-500">No descendants</p>
                ) : (
                  <ul className="space-y-2">
                    {lineage.descendants.map((node) => (
                      <li key={`descendant-${node.document_id}`} className="ui-card ui-card-body text-sm">
                        <div className="font-medium text-sm">{node.name}</div>
                        <div className="text-xs text-gray-500">ID: {node.document_id}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {showSessions && (
        <div className="ui-modal-overlay">
          <div className="ui-modal w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold">Edit Sessions</h2>
              <button
                type="button"
                onClick={() => setShowSessions(false)}
                className="ui-btn"
              >
                Close
              </button>
            </div>
            {sessions.length === 0 ? (
              <p className="text-sm text-gray-500">No sessions found.</p>
            ) : (
              <ul className="space-y-2">
                {sessions.map((session) => (
                  <li key={session.session_id} className="ui-card ui-card-body text-sm">
                    <div className="text-sm">Editor user: {session.editor_user_id}</div>
                    <div className="text-sm">Start: {new Date(session.started_at).toLocaleString()}</div>
                    <div>
                      End:{' '}
                      {session.ended_at
                        ? new Date(session.ended_at).toLocaleString()
                        : 'Active / not ended'}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
})

export default BlockEditor
