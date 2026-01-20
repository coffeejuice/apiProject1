import { create } from 'zustand'
import { apiClient } from '../lib/apiClient'
import type { CommitRequest, CommitResponse } from '../types/api'
import { getDeviceId, generateUUID } from '../lib/utils'
import { contentToBlocks, generateOperations, type TrackedBlock } from '../lib/blockManager'

type SaveStatus = 'saved' | 'saving' | 'error' | 'idle'

interface EditorState {
  content: unknown
  isDirty: boolean
  saveStatus: SaveStatus
  lastSavedRevNumber: number
  error: string | null
  trackedBlocks: TrackedBlock[]

  setContent: (content: unknown) => void
  markDirty: () => void
  save: (docId: string) => Promise<boolean>
  setSaveStatus: (status: SaveStatus) => void
  setLastSavedRevNumber: (revNumber: number) => void
  loadBlocksFromBackend: (docId: string) => Promise<void>
  reset: () => void
}

export const useEditorStore = create<EditorState>((set, get) => ({
  content: null,
  isDirty: false,
  saveStatus: 'idle',
  lastSavedRevNumber: 0,
  error: null,
  trackedBlocks: [],

  setContent: (content: unknown) => {
    set({ content })
  },

  markDirty: () => {
    set({ isDirty: true, saveStatus: 'idle' })
  },

  save: async (docId: string) => {
    const state = get()

    if (!state.isDirty) {
      return true
    }

    set({ saveStatus: 'saving' })

    try {
      // Convert current content to blocks
      const newBlocks = contentToBlocks(state.content)

      // Generate operations by diffing
      const ops = generateOperations(state.trackedBlocks, newBlocks)

      // If there are operations, send them to backend
      if (ops.length > 0) {
        const commitRequest: CommitRequest = {
          device_id: getDeviceId(),
          base_rev_number: state.lastSavedRevNumber,
          client_batch_id: generateUUID(),
          ops,
        }

        const response = await apiClient.post<CommitResponse>(
          `/documents/${docId}/commit`,
          { body: commitRequest }
        )

        if (!response.ok) {
          throw new Error(response.errorMessage || 'Failed to commit changes')
        }

        if (!response.data?.success) {
          throw new Error('Commit failed on server')
        }

        // Update revision number
        set({ lastSavedRevNumber: response.data.new_rev_number })
      }

      // Update tracked blocks to new state
      set({ trackedBlocks: newBlocks })

      // Save to localStorage as backup
      localStorage.setItem(`doc_${docId}_content`, JSON.stringify(state.content))

      set({
        isDirty: false,
        saveStatus: 'saved',
        error: null,
      })

      return true
    } catch (error) {
      set({
        saveStatus: 'error',
        error: error instanceof Error ? error.message : 'Failed to save',
      })

      // Fallback to localStorage
      try {
        localStorage.setItem(`doc_${docId}_content`, JSON.stringify(state.content))
      } catch {}

      return false
    }
  },

  setSaveStatus: (status: SaveStatus) => {
    set({ saveStatus: status })
  },

  setLastSavedRevNumber: (revNumber: number) => {
    set({ lastSavedRevNumber: revNumber })
  },

  loadBlocksFromBackend: async (docId: string) => {
    try {
      // Fetch blocks from backend
      const response = await apiClient.get<any>(`/documents/${docId}/blocks/root`)

      if (response.ok && response.data) {
        const blocks = Array.isArray(response.data) ? response.data : []

        // Convert backend blocks to tracked blocks
        const trackedBlocks: TrackedBlock[] = blocks.map((block: any) => ({
          blockId: block.block_id,
          blockType: block.block_type,
          text: block.text || '',
          props: block.props || {},
          orderKey: block.order_key,
        }))

        set({ trackedBlocks })
      }
    } catch (error) {
      console.error('Failed to load blocks from backend:', error)
      // Don't fail - we can start with empty blocks
      set({ trackedBlocks: [] })
    }
  },

  reset: () => {
    set({
      content: null,
      isDirty: false,
      saveStatus: 'idle',
      lastSavedRevNumber: 0,
      error: null,
      trackedBlocks: [],
    })
  },
}))
