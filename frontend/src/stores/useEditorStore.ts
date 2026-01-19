import { create } from 'zustand'
import { apiClient } from '../lib/apiClient'
import type { CommitRequest, CommitResponse } from '../types/api'
import { getDeviceId, generateUUID } from '../lib/utils'

type SaveStatus = 'saved' | 'saving' | 'error' | 'idle'

interface EditorState {
  content: unknown
  isDirty: boolean
  saveStatus: SaveStatus
  lastSavedRevNumber: number
  error: string | null

  setContent: (content: unknown) => void
  markDirty: () => void
  save: (docId: string) => Promise<boolean>
  setSaveStatus: (status: SaveStatus) => void
  setLastSavedRevNumber: (revNumber: number) => void
  reset: () => void
}

export const useEditorStore = create<EditorState>((set, get) => ({
  content: null,
  isDirty: false,
  saveStatus: 'idle',
  lastSavedRevNumber: 0,
  error: null,

  setContent: (content: unknown) => {
    set({ content })
  },

  markDirty: () => {
    set({ isDirty: true, saveStatus: 'idle' })
  },

  save: async (docId: string) => {
    // TODO: Implement proper operational transform commits
    // Backend expects specific operations (insert_block, update_text, etc.)
    // For now, save to localStorage as a fallback

    const state = get()

    if (!state.isDirty) {
      return true
    }

    // Save to localStorage for now
    try {
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
        error: 'Failed to save locally',
      })
      return false
    }
  },

  setSaveStatus: (status: SaveStatus) => {
    set({ saveStatus: status })
  },

  setLastSavedRevNumber: (revNumber: number) => {
    set({ lastSavedRevNumber: revNumber })
  },

  reset: () => {
    set({
      content: null,
      isDirty: false,
      saveStatus: 'idle',
      lastSavedRevNumber: 0,
      error: null,
    })
  },
}))
