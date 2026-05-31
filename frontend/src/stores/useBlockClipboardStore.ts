import { create } from 'zustand'
import type { BlockData } from '../types/api'

export type ClipboardClipMode = 'copy' | 'cut'
export type BlocksPaneTab = 'actions' | 'clipboard'

export interface ClipboardClip {
  id: string
  mode: ClipboardClipMode
  sourceDocumentId: string | null
  createdAt: number
  blocks: BlockData[]
}

interface BlockClipboardState {
  clips: ClipboardClip[]
  activeClipId: string | null
  selectedClipIds: Set<string>
  maxClips: number
  activePaneTab: BlocksPaneTab
  addClip: (mode: ClipboardClipMode, blocks: BlockData[], sourceDocumentId?: string | null) => string | null
  setActiveClip: (clipId: string) => void
  toggleSelectedClip: (clipId: string) => void
  clearSelectedClips: () => void
  removeClip: (clipId: string) => void
  removeSelectedClips: () => void
  removeAllClips: () => void
  setMaxClips: (maxClips: number) => void
  setActivePaneTab: (tab: BlocksPaneTab) => void
}

const DEFAULT_MAX_CLIPS = 10
const MIN_MAX_CLIPS = 1
const MAX_MAX_CLIPS = 99

function createClipId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `clip-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function cloneBlocks(blocks: BlockData[]): BlockData[] {
  return JSON.parse(JSON.stringify(blocks || [])) as BlockData[]
}

function clampMaxClips(value: number): number {
  if (!Number.isFinite(value)) {
    return DEFAULT_MAX_CLIPS
  }
  return Math.min(MAX_MAX_CLIPS, Math.max(MIN_MAX_CLIPS, Math.floor(value)))
}

function normalizeActiveClipId(clips: ClipboardClip[], requestedActiveId: string | null): string | null {
  if (clips.length === 0) {
    return null
  }
  if (requestedActiveId && clips.some((clip) => clip.id === requestedActiveId)) {
    return requestedActiveId
  }
  return clips[0].id
}

function trimClips(clips: ClipboardClip[], maxClips: number): ClipboardClip[] {
  return clips.slice(0, clampMaxClips(maxClips))
}

export const useBlockClipboardStore = create<BlockClipboardState>((set) => ({
  clips: [],
  activeClipId: null,
  selectedClipIds: new Set<string>(),
  maxClips: DEFAULT_MAX_CLIPS,
  activePaneTab: 'actions',

  addClip: (mode, blocks, sourceDocumentId = null) => {
    if (blocks.length === 0) {
      return null
    }

    const clip: ClipboardClip = {
      id: createClipId(),
      mode,
      sourceDocumentId,
      createdAt: Date.now(),
      blocks: cloneBlocks(blocks),
    }

    set((state) => {
      const clips = trimClips([clip, ...state.clips], state.maxClips)
      return {
        clips,
        activeClipId: clip.id,
        selectedClipIds: new Set<string>(),
        activePaneTab: 'clipboard',
      }
    })

    return clip.id
  },

  setActiveClip: (clipId) => {
    set((state) => {
      if (!state.clips.some((clip) => clip.id === clipId)) {
        return state
      }
      return { activeClipId: clipId }
    })
  },

  toggleSelectedClip: (clipId) => {
    set((state) => {
      const selectedClipIds = new Set(state.selectedClipIds)
      if (selectedClipIds.has(clipId)) {
        selectedClipIds.delete(clipId)
      } else {
        selectedClipIds.add(clipId)
      }
      return { selectedClipIds }
    })
  },

  clearSelectedClips: () => set({ selectedClipIds: new Set<string>() }),

  removeClip: (clipId) => {
    set((state) => {
      const clips = state.clips.filter((clip) => clip.id !== clipId)
      const selectedClipIds = new Set(state.selectedClipIds)
      selectedClipIds.delete(clipId)
      return {
        clips,
        selectedClipIds,
        activeClipId: normalizeActiveClipId(clips, state.activeClipId === clipId ? null : state.activeClipId),
        activePaneTab: clips.length === 0 ? 'actions' : state.activePaneTab,
      }
    })
  },

  removeSelectedClips: () => {
    set((state) => {
      if (state.selectedClipIds.size === 0) {
        return state
      }
      const clips = state.clips.filter((clip) => !state.selectedClipIds.has(clip.id))
      return {
        clips,
        selectedClipIds: new Set<string>(),
        activeClipId: normalizeActiveClipId(clips, state.activeClipId),
        activePaneTab: clips.length === 0 ? 'actions' : state.activePaneTab,
      }
    })
  },

  removeAllClips: () => {
    set({
      clips: [],
      activeClipId: null,
      selectedClipIds: new Set<string>(),
      activePaneTab: 'actions',
    })
  },

  setMaxClips: (maxClips) => {
    set((state) => {
      const nextMaxClips = clampMaxClips(maxClips)
      const clips = trimClips(state.clips, nextMaxClips)
      const retainedIds = new Set(clips.map((clip) => clip.id))
      const selectedClipIds = new Set(
        Array.from(state.selectedClipIds).filter((clipId) => retainedIds.has(clipId))
      )
      return {
        maxClips: nextMaxClips,
        clips,
        selectedClipIds,
        activeClipId: normalizeActiveClipId(clips, state.activeClipId),
      }
    })
  },

  setActivePaneTab: (tab) => set({ activePaneTab: tab }),
}))
