import { useEffect, useRef, useState } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { apiClient } from '../lib/apiClient'
import { getBlockComponent, BlockData } from './blocks'
import type {
  DocumentLineageResponse,
  EditSession,
  EditSessionListResponse,
  Operation,
} from '../types/api'

interface EditorSnapshot {
  name: string
  blocks: BlockData[]
}

export default function BlockEditor() {
  const [blocks, setBlocks] = useState<BlockData[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [nameSaveTimeout, setNameSaveTimeout] = useState<ReturnType<typeof setTimeout> | null>(null)
  const [lineage, setLineage] = useState<DocumentLineageResponse | null>(null)
  const [showLineage, setShowLineage] = useState(false)
  const [isLineageLoading, setIsLineageLoading] = useState(false)
  const [sessions, setSessions] = useState<EditSession[]>([])
  const [showSessions, setShowSessions] = useState(false)
  const [isSessionsLoading, setIsSessionsLoading] = useState(false)
  const [undoStack, setUndoStack] = useState<EditorSnapshot[]>([])
  const [redoStack, setRedoStack] = useState<EditorSnapshot[]>([])
  const activeSessionIdRef = useRef<string | null>(null)

  const { currentDoc, updateLocalDoc, updateDocument } = useDocumentsStore()

  const cloneSnapshot = (): EditorSnapshot => ({
    name,
    blocks: blocks.map((block) => ({
      ...block,
      props: { ...(block.props || {}) },
    })),
  })

  useEffect(() => {
    if (!currentDoc) {
      setBlocks([])
      setName('')
      setUndoStack([])
      setRedoStack([])
      setIsLoading(false)
      return
    }

    const loadBlocks = async () => {
      setIsLoading(true)
      try {
        const response = await apiClient.get<BlockData[]>(
          `/documents/${currentDoc.id}/blocks/root`
        )
        if (response.ok && response.data) {
          setBlocks(response.data)
        } else {
          setBlocks([])
        }
        setName(currentDoc.name || '')
        setUndoStack([])
        setRedoStack([])
      } finally {
        setIsLoading(false)
      }
    }

    loadBlocks()
  }, [currentDoc])

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

  const applySnapshot = async (snapshot: EditorSnapshot) => {
    if (!currentDoc) return
    setName(snapshot.name)
    setBlocks(snapshot.blocks)
    updateLocalDoc(String(currentDoc.id), { name: snapshot.name })

    const ops: Operation[] = snapshot.blocks.map((block) => ({
      op_type: 'update_props',
      data: {
        block_id: block.block_id,
        props: block.props,
      },
    }))

    await updateDocument(String(currentDoc.id), { name: snapshot.name })
    if (ops.length > 0) {
      await apiClient.post(`/documents/${currentDoc.id}/commit`, {
        body: { ops },
      })
    }
  }

  const handleUndo = async () => {
    if (undoStack.length === 0) return
    const target = undoStack[undoStack.length - 1]
    const current = cloneSnapshot()
    setUndoStack((prev) => prev.slice(0, -1))
    setRedoStack((prev) => [...prev, current])
    await applySnapshot(target)
  }

  const handleRedo = async () => {
    if (redoStack.length === 0) return
    const target = redoStack[redoStack.length - 1]
    const current = cloneSnapshot()
    setRedoStack((prev) => prev.slice(0, -1))
    setUndoStack((prev) => [...prev, current])
    await applySnapshot(target)
  }

  const handleBlockUpdate = async (blockId: string, props: Record<string, unknown>) => {
    if (!currentDoc) return
    const before = cloneSnapshot()
    setSaveStatus('saving')
    setSaveError(null)

    const operation: Operation = {
      op_type: 'update_props',
      data: {
        block_id: blockId,
        props,
      },
    }

    const response = await apiClient.post<{ success: boolean; message?: string }>(
      `/documents/${currentDoc.id}/commit`,
      {
        body: {
          ops: [operation],
        },
      }
    )

    if (response.ok && response.data?.success) {
      setBlocks((prev) =>
        prev.map((block) => (block.block_id === blockId ? { ...block, props } : block))
      )
      setUndoStack((prev) => [...prev, before])
      setRedoStack([])
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 1500)
      return
    }

    setSaveStatus('error')
    setSaveError(response.errorMessage || response.data?.message || 'Failed to save block')
  }

  const handleNameChange = (newName: string) => {
    const before = cloneSnapshot()
    setName(newName)
    if (!currentDoc) return

    updateLocalDoc(String(currentDoc.id), { name: newName })
    setUndoStack((prev) => [...prev, before])
    setRedoStack([])
    if (nameSaveTimeout) {
      clearTimeout(nameSaveTimeout)
    }

    const timeout = setTimeout(async () => {
      await updateDocument(String(currentDoc.id), { name: newName })
      setNameSaveTimeout(null)
    }, 700)

    setNameSaveTimeout(timeout)
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
          <input
            type="text"
            value={name}
            onChange={(event) => handleNameChange(event.target.value)}
            className="text-2xl font-bold border-none outline-none flex-1"
            placeholder="Untitled Document"
          />

          <div className="flex items-center gap-3">
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
              {saveStatus === 'idle' && <span className="text-gray-400">-</span>}
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

      <div className="flex-1 overflow-y-auto bg-gray-100">
        <div className="max-w-4xl mx-auto py-8 px-4 space-y-4">
          {blocks.length === 0 ? (
            <div className="text-center text-gray-500 py-12">No blocks found in this document.</div>
          ) : (
            blocks.map((block) => {
              const BlockComponent = getBlockComponent(block.block_type_id)

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
