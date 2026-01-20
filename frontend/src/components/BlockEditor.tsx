/**
 * Block-based Document Editor
 * Replaces TipTap with custom block rendering system
 */

import { useEffect, useState } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { apiClient } from '../lib/apiClient'
import { getBlockComponent, BlockData } from './blocks'
import type { Operation } from '../types/api'
import { generateUUID } from '../lib/utils'

export default function BlockEditor() {
  const [blocks, setBlocks] = useState<BlockData[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [titleSaveTimeout, setTitleSaveTimeout] = useState<NodeJS.Timeout | null>(null)

  const { currentDoc, updateLocalDoc, updateDocument } = useDocumentsStore()

  // Load blocks when document changes
  useEffect(() => {
    if (!currentDoc) {
      setBlocks([])
      setTitle('')
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
          console.error('Failed to load blocks:', response.errorMessage)
          setBlocks([])
        }
        setTitle(currentDoc.title || '')
      } catch (error) {
        console.error('Failed to load blocks:', error)
        setBlocks([])
      } finally {
        setIsLoading(false)
      }
    }

    loadBlocks()
  }, [currentDoc])

  const handleBlockUpdate = async (blockId: string, props: Record<string, any>) => {
    if (!currentDoc) return

    setSaveStatus('saving')

    try {
      // Create update_props operation
      const operation: Operation = {
        op_type: 'update_props',
        data: {
          block_id: blockId,
          props,
        },
      }

      console.log('Saving block update:', { blockId, props })

      // Commit to backend
      const response = await apiClient.post<{
        success: boolean
        new_rev_number?: number
        conflicts?: any[]
      }>(`/documents/${currentDoc.id}/commit`, {
        body: {
          device_id: getDeviceId(),
          base_rev_number: currentDoc.rev_number || 0,
          client_batch_id: generateUUID(),
          ops: [operation],
        },
      })

      console.log('Commit response:', response)

      if (response.ok && response.data?.success) {
        // Update local block state
        setBlocks((prevBlocks) =>
          prevBlocks.map((block) =>
            block.block_id === blockId ? { ...block, props } : block
          )
        )

        // Update the document's revision number for next save
        if (response.data.new_rev_number && currentDoc) {
          updateLocalDoc(currentDoc.id, { rev_number: response.data.new_rev_number })
        }

        setSaveStatus('saved')
        setSaveError(null)
        setTimeout(() => setSaveStatus('idle'), 2000)
      } else if (response.ok && response.data?.conflicts) {
        // Handle conflicts
        const conflictMsg = `Conflict detected: ${response.data.conflicts.length} field(s) changed by another user. ${JSON.stringify(response.data.conflicts)}`
        console.error('Save conflicts:', response.data.conflicts)
        setSaveStatus('error')
        setSaveError(conflictMsg)
      } else {
        const errorMsg = response.errorMessage || 'Failed to save block'
        console.error('Failed to save block:', response.data || errorMsg)
        setSaveStatus('error')
        setSaveError(errorMsg)
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      console.error('Error saving block:', error)
      setSaveStatus('error')
      setSaveError(errorMsg)
    }
  }

  const handleTitleChange = (newTitle: string) => {
    setTitle(newTitle)
    if (currentDoc) {
      updateLocalDoc(currentDoc.id, { title: newTitle })

      // Clear any pending save
      if (titleSaveTimeout) {
        clearTimeout(titleSaveTimeout)
      }

      // Debounce backend update
      const timeoutId = setTimeout(async () => {
        await updateDocument(currentDoc.id, { title: newTitle })
        setTitleSaveTimeout(null)
      }, 1000)

      setTitleSaveTimeout(timeoutId)
    }
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
      {/* Header */}
      <div className="border-b border-gray-200 bg-white p-4 flex-shrink-0">
        <div className="flex items-center justify-between mb-2">
          <input
            type="text"
            value={title}
            onChange={(e) => handleTitleChange(e.target.value)}
            className="text-2xl font-bold border-none outline-none flex-1"
            placeholder="Untitled Document"
          />

          <div className="flex items-center gap-4">
            {/* Save Status */}
            <div className="text-sm">
              {saveStatus === 'saving' && (
                <span className="text-blue-600">Saving...</span>
              )}
              {saveStatus === 'saved' && (
                <span className="text-green-600">Saved</span>
              )}
              {saveStatus === 'error' && (
                <span
                  className="text-red-600 cursor-help"
                  title={saveError || 'Error saving'}
                >
                  Error saving
                </span>
              )}
              {saveStatus === 'idle' && <span className="text-gray-400">-</span>}
            </div>
          </div>
        </div>

        {/* Error Message Banner */}
        {saveError && saveStatus === 'error' && (
          <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded text-sm">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <span className="font-semibold text-red-800">Save Error:</span>
                <span className="text-red-700 ml-2">{saveError}</span>
              </div>
              <button
                onClick={() => setSaveError(null)}
                className="text-red-600 hover:text-red-800 ml-2"
                title="Dismiss"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        <div className="text-xs text-gray-500">
          Revision: {currentDoc.rev_number || 0}
        </div>
      </div>

      {/* Editor Content */}
      <div className="flex-1 overflow-y-auto bg-gray-100">
        <div className="max-w-4xl mx-auto py-8 px-4 space-y-4">
          {blocks.length === 0 ? (
            <div className="text-center text-gray-500 py-12">
              No blocks found. This document might be using the old format.
            </div>
          ) : (
            blocks.map((block) => {
              const BlockComponent = getBlockComponent(block.block_type)

              if (!BlockComponent) {
                return (
                  <div key={block.block_id} className="bg-white p-4 rounded shadow">
                    <div className="text-red-600">
                      Unknown block type: {block.block_type}
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
    </div>
  )
}

/**
 * Get or create a persistent device ID
 */
function getDeviceId(): string {
  let deviceId = localStorage.getItem('device_id')
  if (!deviceId) {
    deviceId = generateUUID()
    localStorage.setItem('device_id', deviceId)
  }
  return deviceId
}
