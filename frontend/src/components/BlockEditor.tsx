import { useEffect, useMemo, useRef, useState } from 'react'
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

function cloneProps(props: Record<string, any>): Record<string, any> {
  return JSON.parse(JSON.stringify(props || {}))
}

function cloneBlocks(blocks: BlockData[]): BlockData[] {
  return blocks.map((block) => ({
    ...block,
    props: cloneProps((block.props || {}) as Record<string, any>),
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

export default function BlockEditor() {
  const [savedBlocks, setSavedBlocks] = useState<BlockData[]>([])
  const [draftBlocks, setDraftBlocks] = useState<BlockData[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
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

  const loadEditorState = async (
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

      return
    } finally {
      if (showLoading) {
        setIsLoading(false)
      }
    }
  }

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
  }, [currentDoc?.id])

  useEffect(() => {
    if (!currentDoc) {
      return
    }

    let active = true
    const docId = currentDoc.id

    const startSession = async () => {
      const response = await apiClient.post<EditSession>(`/documents/${docId}/sessions/start`, {
        body: {},
      })
      if (active && response.ok && response.data) {
        activeSessionIdRef.current = response.data.session_id
      }
    }

    startSession()

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
  }, [currentDoc?.id])

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

  const handleBlockUpdate = (blockId: string, props: Record<string, any>) => {
    const currentBlock = draftBlocks.find((block) => block.block_id === blockId)
    if (!currentBlock) {
      return
    }

    const constrainedProps = applyFieldLengthLimits(props, currentBlock.field_limits)

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

  const handleSaveChanges = async () => {
    if (!currentDoc || changedBlocks.length === 0) {
      return
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
      return
    }

    await loadEditorState(String(currentDoc.id), true, {
      showLoading: false,
      preserveScroll: true,
    })
    setSaveStatus('saved')
    setTimeout(() => setSaveStatus('idle'), 1500)
  }

  const handleCancelChanges = async () => {
    if (!currentDoc || !hasUnsavedChanges) {
      return
    }

    setSaveError(null)
    await loadEditorState(String(currentDoc.id), true, {
      showLoading: false,
      preserveScroll: true,
    })
    setSaveStatus('idle')
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

  if (!currentDoc) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        Select a document to start editing
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-gray-200 bg-white p-4 flex-shrink-0">
        <div className="flex items-center justify-between mb-2 gap-4">
          <div className="text-2xl font-bold flex-1 truncate">
            {draftDocumentName || 'Untitled Document'}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleSaveChanges}
              disabled={!hasUnsavedChanges || saveStatus === 'saving'}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              Save
            </button>

            <button
              type="button"
              onClick={handleCancelChanges}
              disabled={!hasUnsavedChanges || saveStatus === 'saving'}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleUndo}
              disabled={undoStack.length === 0}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
            >
              Undo
            </button>

            <button
              type="button"
              onClick={handleRedo}
              disabled={redoStack.length === 0}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
            >
              Redo
            </button>

            <button
              type="button"
              onClick={handleShowLineage}
              disabled={isLineageLoading}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
            >
              {isLineageLoading ? 'Loading...' : 'Lineage'}
            </button>

            <button
              type="button"
              onClick={handleShowSessions}
              disabled={isSessionsLoading}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
            >
              {isSessionsLoading ? 'Loading...' : 'Sessions'}
            </button>

            <div className="text-sm">
              {saveStatus === 'saving' && <span className="text-blue-600">Saving...</span>}
              {saveStatus === 'saved' && <span className="text-green-600">Saved</span>}
              {saveStatus === 'error' && (
                <span className="text-red-600 cursor-help" title={saveError || 'Error'}>
                  Error saving
                </span>
              )}
              {saveStatus === 'idle' && (
                <span className={hasUnsavedChanges ? 'text-amber-600' : 'text-gray-400'}>
                  {hasUnsavedChanges ? `${changedBlocks.length} unsaved` : '-'}
                </span>
              )}
            </div>
          </div>
        </div>

        {saveError && saveStatus === 'error' && (
          <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            {saveError}
          </div>
        )}

        <div className="text-xs text-gray-500">
          Source document: {currentDoc.source_document_id ?? 'None'}
        </div>
      </div>

      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto bg-gray-100">
        <div className="max-w-4xl mx-auto py-8 px-4 space-y-4">
          {draftBlocks.length === 0 ? (
            <div className="text-center text-gray-500 py-12">No blocks found in this document.</div>
          ) : (
            draftBlocks.map((block) => {
              const BlockComponent = getBlockComponent(block.block_type_id)
              const baselineProps = savedBlocksById.get(block.block_id)?.props || {}

              if (!BlockComponent) {
                return (
                  <div key={block.block_id} className="bg-white p-4 rounded shadow">
                    <div className="text-red-600">
                      Unknown block type: {block.block_type_id}
                    </div>
                    <pre className="text-xs text-gray-600 mt-2">
                      {JSON.stringify(block, null, 2)}
                    </pre>
                  </div>
                )
              }

              return (
                <BlockComponent
                  key={block.block_id}
                  block={block}
                  baselineProps={baselineProps}
                  onUpdate={handleBlockUpdate}
                  isReadOnly={false}
                />
              )
            })
          )}
        </div>
      </div>

      {showLineage && lineage && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-3xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">Document Lineage</h2>
              <button
                type="button"
                onClick={() => setShowLineage(false)}
                className="text-gray-500 hover:text-gray-800"
              >
                Close
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="font-semibold mb-2">Ancestors</h3>
                {lineage.ancestors.length === 0 ? (
                  <p className="text-sm text-gray-500">No ancestors</p>
                ) : (
                  <ul className="space-y-2">
                    {lineage.ancestors.map((node) => (
                      <li key={`ancestor-${node.document_id}`} className="text-sm border rounded p-2">
                        <div className="font-medium">{node.name}</div>
                        <div className="text-gray-500">ID: {node.document_id}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <h3 className="font-semibold mb-2">Descendants</h3>
                {lineage.descendants.length === 0 ? (
                  <p className="text-sm text-gray-500">No descendants</p>
                ) : (
                  <ul className="space-y-2">
                    {lineage.descendants.map((node) => (
                      <li key={`descendant-${node.document_id}`} className="text-sm border rounded p-2">
                        <div className="font-medium">{node.name}</div>
                        <div className="text-gray-500">ID: {node.document_id}</div>
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
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">Edit Sessions</h2>
              <button
                type="button"
                onClick={() => setShowSessions(false)}
                className="text-gray-500 hover:text-gray-800"
              >
                Close
              </button>
            </div>
            {sessions.length === 0 ? (
              <p className="text-sm text-gray-500">No sessions found.</p>
            ) : (
              <ul className="space-y-2">
                {sessions.map((session) => (
                  <li key={session.session_id} className="border rounded p-3 text-sm">
                    <div>Editor user: {session.editor_user_id}</div>
                    <div>Start: {new Date(session.started_at).toLocaleString()}</div>
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
}
