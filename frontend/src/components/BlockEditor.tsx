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
import { motion } from 'framer-motion'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useBlockClipboardStore } from '../stores/useBlockClipboardStore'
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
  activeDocumentBlockId: string | null
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
  copyBlocksToClipboard: (blockIds: string[]) => Promise<boolean>
  cutBlocksToClipboard: (blockIds: string[]) => Promise<boolean>
  pasteClipboardClip: (clipId?: string, previousBlockId?: string | null) => Promise<boolean>
  makeBlockActive: (blockId: string | null) => void
  getActiveBlockId: () => string | null
  getBlocks: () => BlockData[]
  hasUnsavedChanges: () => boolean
}

interface BlockEditorProps {
  className?: string
  onMetaChange?: (meta: BlockEditorMeta) => void
  onBlocksChange?: (blocks: BlockData[]) => void
}

const DEFORMATION_BUNDLE_ORDER = ['24']
const DEFORMATION_BUNDLE_TYPES = new Set(DEFORMATION_BUNDLE_ORDER)
const DOCUMENT_HEADING_TYPE_ID = 'document_heading'
const FURNACE_SECTION_TYPE_ID = '10'
const DEFORMATION_SECTION_TYPE_ID = '24'
const CATALOG_BLOCK_DRAG_MIME = 'application/x-forgelab-block-type'
const EDITOR_BLOCK_DRAG_MIME = 'application/x-forgelab-editor-block-ids'
const INSERT_CONFIRMATION_DURATION_MS = 1100
const BLOCK_LAYOUT_TRANSITION = {
  duration: 0.38,
  ease: 'easeInOut' as const,
}

type DocumentVisualSection =
  | {
      kind: 'section'
      block: BlockData
      children: BlockData[]
    }
  | {
      kind: 'loose'
      key: string
      children: BlockData[]
    }

interface DocumentVisualLayout {
  heading: BlockData | null
  sections: DocumentVisualSection[]
}

function isTopLevelDocumentSection(block: BlockData): boolean {
  return block.block_type_id === FURNACE_SECTION_TYPE_ID || block.block_type_id === DEFORMATION_SECTION_TYPE_ID
}

function isDeformationSection(block: BlockData): boolean {
  return block.block_type_id === DEFORMATION_SECTION_TYPE_ID
}

function canActivateBlock(block: BlockData): boolean {
  return block.block_type_id !== DOCUMENT_HEADING_TYPE_ID
}

function canSelectBlock(block: BlockData): boolean {
  return block.block_type_id !== DOCUMENT_HEADING_TYPE_ID && !block.is_system
}

function getEditorBlockDragPayload(event: DragEvent<HTMLElement>): string[] {
  const payload = event.dataTransfer.getData(EDITOR_BLOCK_DRAG_MIME)
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

function hasDragMime(event: DragEvent<HTMLElement>, mimeType: string): boolean {
  return Array.from(event.dataTransfer.types).includes(mimeType)
}

function relinkOrderedBlocks(blocks: BlockData[]): BlockData[] {
  return blocks.map((block, index) => ({
    ...block,
    previous_block_id: index > 0 ? blocks[index - 1].block_id : null,
    next_block_id: index < blocks.length - 1 ? blocks[index + 1].block_id : null,
  }))
}

function normalizeMoveAnchor(blocks: BlockData[], movingIds: Set<string>, previousBlockId: string | null): string | null {
  if (previousBlockId === null || !movingIds.has(previousBlockId)) {
    return previousBlockId
  }

  let cursor = blocks.find((block) => block.block_id === previousBlockId)?.previous_block_id ?? null
  while (cursor && movingIds.has(cursor)) {
    cursor = blocks.find((block) => block.block_id === cursor)?.previous_block_id ?? null
  }
  return cursor
}

function reorderBlocksForMove(blocks: BlockData[], movingBlockIds: string[], previousBlockId: string | null): BlockData[] {
  const movingIds = new Set(movingBlockIds)
  const movingBlocks = blocks.filter((block) => movingIds.has(block.block_id))
  if (movingBlocks.length === 0) {
    return blocks
  }

  const remainingBlocks = blocks.filter((block) => !movingIds.has(block.block_id))
  const normalizedAnchor = normalizeMoveAnchor(blocks, movingIds, previousBlockId)
  const insertionIndex = normalizedAnchor === null
    ? 0
    : Math.max(0, remainingBlocks.findIndex((block) => block.block_id === normalizedAnchor) + 1)

  const reordered = [
    ...remainingBlocks.slice(0, insertionIndex),
    ...movingBlocks,
    ...remainingBlocks.slice(insertionIndex),
  ]

  return relinkOrderedBlocks(reordered)
}

function getOperationLibraryName(block: BlockData): string | null {
  const operationType = block.props?.operation_type
  if (!operationType || typeof operationType !== 'object') {
    return null
  }
  const libraryName = (operationType as { library_name?: unknown }).library_name
  return typeof libraryName === 'string' && libraryName.trim() ? libraryName : null
}

function getBlockDisplayName(block: BlockData): string {
  if (block.block_type_id === DOCUMENT_HEADING_TYPE_ID) {
    return 'Document'
  }
  if (block.block_type_id === FURNACE_SECTION_TYPE_ID) {
    return 'Furnace'
  }
  if (block.block_type_id === DEFORMATION_SECTION_TYPE_ID) {
    return 'Deformation'
  }
  return getOperationLibraryName(block) || `Block ${block.block_type_id}`
}

function getSectionDropTarget(section: DocumentVisualSection): string | null {
  if (section.kind === 'section') {
    return section.children[section.children.length - 1]?.block_id || section.block.block_id
  }
  return section.children[section.children.length - 1]?.block_id || null
}

function buildDocumentVisualLayout(blocks: BlockData[]): DocumentVisualLayout {
  const heading = blocks.find((block) => block.block_type_id === DOCUMENT_HEADING_TYPE_ID) || null
  const sections: DocumentVisualSection[] = []
  let activeDeformation: Extract<DocumentVisualSection, { kind: 'section' }> | null = null
  let looseSectionIndex = 0

  const appendLooseBlock = (block: BlockData) => {
    const lastSection = sections[sections.length - 1]
    if (lastSection?.kind === 'loose') {
      lastSection.children.push(block)
      return
    }
    sections.push({
      kind: 'loose',
      key: `loose-${looseSectionIndex}`,
      children: [block],
    })
    looseSectionIndex += 1
  }

  for (const block of blocks) {
    if (block.block_id === heading?.block_id) {
      continue
    }

    if (isTopLevelDocumentSection(block)) {
      const section: Extract<DocumentVisualSection, { kind: 'section' }> = {
        kind: 'section',
        block,
        children: [],
      }
      sections.push(section)
      activeDeformation = isDeformationSection(block) ? section : null
      continue
    }

    if (activeDeformation) {
      activeDeformation.children.push(block)
    } else {
      appendLooseBlock(block)
    }
  }

  return { heading, sections }
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

function preparePropsForStructureInsert(props: Record<string, unknown>): Record<string, unknown> {
  const clonedProps = cloneProps(props)
  delete clonedProps.title
  delete clonedProps.operation_type
  delete clonedProps.editable_fields
  delete clonedProps.field_limits
  return clonedProps
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
  const [activeDocumentBlockId, setActiveDocumentBlockId] = useState<string | null>(null)
  const [selectedDocumentBlockIds, setSelectedDocumentBlockIds] = useState<Set<string>>(new Set())
  const [dropPreviewPreviousBlockId, setDropPreviewPreviousBlockId] = useState<string | null | undefined>(undefined)
  const [confirmedInsertPreviousBlockId, setConfirmedInsertPreviousBlockId] = useState<string | null | undefined>(undefined)
  const [recentlyInsertedBlockIds, setRecentlyInsertedBlockIds] = useState<Set<string>>(new Set())
  const activeSessionIdRef = useRef<string | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const insertConfirmationTimeoutRef = useRef<number | null>(null)

  const { currentDoc, fetchDocument } = useDocumentsStore()
  const addClipboardClip = useBlockClipboardStore((state) => state.addClip)
  const activeClipboardClip = useBlockClipboardStore((state) =>
    state.clips.find((clip) => clip.id === state.activeClipId) ?? null
  )

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

  const documentVisualLayout = useMemo(
    () => buildDocumentVisualLayout(draftBlocks),
    [draftBlocks]
  )

  const activeDocumentBlock = useMemo(
    () => draftBlocks.find((block) => block.block_id === activeDocumentBlockId) || null,
    [activeDocumentBlockId, draftBlocks]
  )

  const selectedDocumentBlocksInOrder = useMemo(() => {
    return draftBlocks.filter((block) => selectedDocumentBlockIds.has(block.block_id))
  }, [draftBlocks, selectedDocumentBlockIds])

  const structureEditDisabled = hasUnsavedChanges

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

  const clearInsertConfirmation = useCallback(() => {
    if (insertConfirmationTimeoutRef.current !== null) {
      window.clearTimeout(insertConfirmationTimeoutRef.current)
      insertConfirmationTimeoutRef.current = null
    }
    setConfirmedInsertPreviousBlockId(undefined)
    setRecentlyInsertedBlockIds((previous) => (previous.size > 0 ? new Set() : previous))
  }, [])

  const markInsertedBlocks = useCallback(
    (blockIds: string[], previousBlockId: string | null) => {
      const filteredBlockIds = blockIds.filter((blockId) => typeof blockId === 'string' && blockId.length > 0)
      if (filteredBlockIds.length === 0) {
        clearInsertConfirmation()
        return
      }

      if (insertConfirmationTimeoutRef.current !== null) {
        window.clearTimeout(insertConfirmationTimeoutRef.current)
      }

      setConfirmedInsertPreviousBlockId(previousBlockId)
      setRecentlyInsertedBlockIds(new Set(filteredBlockIds))
      insertConfirmationTimeoutRef.current = window.setTimeout(() => {
        setConfirmedInsertPreviousBlockId(undefined)
        setRecentlyInsertedBlockIds(new Set())
        insertConfirmationTimeoutRef.current = null
      }, INSERT_CONFIRMATION_DURATION_MS)
    },
    [clearInsertConfirmation]
  )

  useEffect(() => {
    return () => {
      if (insertConfirmationTimeoutRef.current !== null) {
        window.clearTimeout(insertConfirmationTimeoutRef.current)
      }
    }
  }, [])

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
      setActiveDocumentBlockId(null)
      setSelectedDocumentBlockIds(new Set())
      setDropPreviewPreviousBlockId(undefined)
      clearInsertConfirmation()
      setIsLoading(false)
      return
    }

    setActiveDocumentBlockId(null)
    setSelectedDocumentBlockIds(new Set())
    setDropPreviewPreviousBlockId(undefined)
    clearInsertConfirmation()
    void loadEditorState(String(currentDoc.id), false)
  }, [clearInsertConfirmation, currentDoc?.id, loadEditorState])

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
    const blocksById = new Map(draftBlocks.map((block) => [block.block_id, block]))
    const activeBlock = activeDocumentBlockId ? blocksById.get(activeDocumentBlockId) : null
    if (activeDocumentBlockId && (!activeBlock || !canActivateBlock(activeBlock))) {
      setActiveDocumentBlockId(null)
    }

    setSelectedDocumentBlockIds((previous) => {
      const next = new Set<string>()
      previous.forEach((blockId) => {
        const block = blocksById.get(blockId)
        if (block && canSelectBlock(block)) {
          next.add(blockId)
        }
      })
      return next.size === previous.size ? previous : next
    })
  }, [activeDocumentBlockId, draftBlocks])

  useEffect(() => {
    if (!onMetaChange) {
      return
    }

    onMetaChange({
      isLoading,
      draftDocumentName,
      sourceDocumentId: currentDoc?.source_document_id ?? null,
      activeDocumentBlockId,
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
    activeDocumentBlockId,
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

    if (canActivateBlock(currentBlock)) {
      setActiveDocumentBlockId(blockId)
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

  const makeBlockActive = (blockId: string | null) => {
    if (blockId === null) {
      setActiveDocumentBlockId(null)
      return
    }

    const block = draftBlocks.find((entry) => entry.block_id === blockId)
    if (block && canActivateBlock(block)) {
      setActiveDocumentBlockId(blockId)
    }
  }

  const toggleSelectedDocumentBlock = (block: BlockData) => {
    if (!canSelectBlock(block)) {
      return
    }

    setSelectedDocumentBlockIds((previous) => {
      const next = new Set(previous)
      if (next.has(block.block_id)) {
        next.delete(block.block_id)
      } else {
        next.add(block.block_id)
      }
      return next
    })
  }

  const clearSelectedDocumentBlocks = () => {
    setSelectedDocumentBlockIds(new Set())
  }

  const getDefaultInsertAnchor = (): string | null => {
    if (activeDocumentBlockId) {
      return activeDocumentBlockId
    }
    return draftBlocks.length > 0 ? draftBlocks[draftBlocks.length - 1].block_id : null
  }

  const findDeformationBundleLeaderId = (block: BlockData): string | null => {
    if (!DEFORMATION_BUNDLE_TYPES.has(block.block_type_id)) {
      return null
    }

    const blockIndex = draftBlocks.findIndex((entry) => entry.block_id === block.block_id)
    const typeIndex = DEFORMATION_BUNDLE_ORDER.indexOf(block.block_type_id)
    if (blockIndex < 0 || typeIndex < 0) {
      return null
    }

    const leaderIndex = blockIndex - typeIndex
    const maybeBundle = draftBlocks.slice(leaderIndex, leaderIndex + DEFORMATION_BUNDLE_ORDER.length)
    const isBundle = DEFORMATION_BUNDLE_ORDER.every(
      (typeId, index) => maybeBundle[index]?.block_type_id === typeId,
    )
    return isBundle ? maybeBundle[0].block_id : null
  }

  const normalizeDeleteTargets = (blocks: BlockData[]): BlockData[] => {
    const seenIds = new Set<string>()
    const normalizedTargets: BlockData[] = []
    for (const block of blocks) {
      const targetId = findDeformationBundleLeaderId(block) || block.block_id
      if (seenIds.has(targetId)) {
        continue
      }
      const target = draftBlocks.find((entry) => entry.block_id === targetId)
      if (!target) {
        continue
      }
      seenIds.add(targetId)
      normalizedTargets.push(target)
    }
    return normalizedTargets
  }

  const handleInsertBlock = async (
    blockTypeId: string,
    previousBlockId?: string | null,
    props: Record<string, unknown> = {}
  ): Promise<boolean> => {
    if (!ensureStructureEditAllowed() || !currentDoc) {
      return false
    }

    clearInsertConfirmation()
    const insertAfterBlockId = previousBlockId === undefined ? getDefaultInsertAnchor() : previousBlockId

    const response = await apiClient.post<BlockData>(`/documents/${currentDoc.id}/blocks`, {
      body: {
        block_type_id: blockTypeId,
        props,
        previous_block_id: insertAfterBlockId,
      },
    })

    if (!response.ok) {
      setSaveStatus('error')
      setSaveError(withFallbackErrorMessage(response.errorMessage, 'Failed to insert block'))
      return false
    }

    await refreshEditor()
    if (response.data && canActivateBlock(response.data)) {
      setActiveDocumentBlockId(response.data.block_id)
    }
    if (response.data) {
      markInsertedBlocks([response.data.block_id], insertAfterBlockId)
    } else {
      clearInsertConfirmation()
    }
    setDropPreviewPreviousBlockId(undefined)
    setSaveStatus('idle')
    setSaveError(null)
    return true
  }

  const handleDeleteBlocks = async (blockIds: string[]): Promise<boolean> => {
    if (!ensureStructureEditAllowed()) {
      return false
    }

    clearInsertConfirmation()
    const targets = getOrderedBlocksByIds(blockIds).filter((block) => block.is_removable)
    if (targets.length === 0) {
      setSaveStatus('error')
      setSaveError('No removable blocks selected')
      return false
    }

    const normalizedTargets = normalizeDeleteTargets(targets)
    const deletedIds = new Set(normalizedTargets.map((block) => block.block_id))
    const responses = await Promise.all(
      normalizedTargets.map((block) => apiClient.delete(`/blocks/${block.block_id}`))
    )

    const failed = responses.find((response) => !response.ok)
    if (failed) {
      setSaveStatus('error')
      setSaveError(withFallbackErrorMessage(failed.errorMessage, 'Failed to delete selected blocks'))
      await refreshEditor()
      return false
    }

    await refreshEditor()
    setSelectedDocumentBlockIds((previous) => {
      const next = new Set(previous)
      deletedIds.forEach((blockId) => next.delete(blockId))
      return next
    })
    if (activeDocumentBlockId && deletedIds.has(activeDocumentBlockId)) {
      setActiveDocumentBlockId(null)
    }
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

    clearInsertConfirmation()
    const orderedMovableBlocks = getOrderedBlocksByIds(blockIds).filter(
      (block) => block.fixed_position === null
    )

    if (orderedMovableBlocks.length === 0) {
      setSaveStatus('error')
      setSaveError('No movable blocks selected')
      return false
    }

    const previousDraftBlocks = cloneBlocks(draftBlocks)
    const previousSavedBlocks = cloneBlocks(savedBlocks)
    const reorderedBlocks = reorderBlocksForMove(
      draftBlocks,
      orderedMovableBlocks.map((block) => block.block_id),
      previousBlockId
    )

    setDraftBlocks(reorderedBlocks)
    setSavedBlocks(cloneBlocks(reorderedBlocks))

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
        setDraftBlocks(previousDraftBlocks)
        setSavedBlocks(previousSavedBlocks)
        await refreshEditor({ preserveScroll: true })
        return false
      }

      pointer = block.block_id
    }

    setActiveDocumentBlockId(orderedMovableBlocks[orderedMovableBlocks.length - 1].block_id)
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

    clearInsertConfirmation()
    const orderedCopyableBlocks = getOrderedBlocksByIds(blockIds).filter(
      (block) => !block.is_system
    )

    if (orderedCopyableBlocks.length === 0) {
      setSaveStatus('error')
      setSaveError('No copyable blocks selected')
      return false
    }

    let pointer = previousBlockId
    let lastCopiedBlockId: string | null = null
    const copiedBlockIds: string[] = []
    for (const block of orderedCopyableBlocks) {
      const response = await apiClient.post<BlockData>(`/documents/${currentDoc.id}/blocks`, {
        body: {
          block_type_id: block.block_type_id,
          props: preparePropsForStructureInsert(block.props as Record<string, unknown>),
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
      lastCopiedBlockId = response.data.block_id
      copiedBlockIds.push(response.data.block_id)
    }

    await refreshEditor()
    if (lastCopiedBlockId) {
      setActiveDocumentBlockId(lastCopiedBlockId)
    }
    markInsertedBlocks(copiedBlockIds, previousBlockId)
    setSaveStatus('idle')
    setSaveError(null)
    return true
  }

  const handleCopyBlocksToClipboard = async (blockIds: string[]): Promise<boolean> => {
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

    addClipboardClip('copy', cloneBlocks(orderedCopyableBlocks), String(currentDoc.id))
    setSaveStatus('idle')
    setSaveError(null)
    return true
  }

  const handleCutBlocksToClipboard = async (blockIds: string[]): Promise<boolean> => {
    if (!ensureStructureEditAllowed() || !currentDoc) {
      return false
    }

    const orderedCuttableBlocks = getOrderedBlocksByIds(blockIds).filter(
      (block) => block.is_removable && !block.is_system
    )

    if (orderedCuttableBlocks.length === 0) {
      setSaveStatus('error')
      setSaveError('No removable blocks selected')
      return false
    }

    const normalizedTargets = normalizeDeleteTargets(orderedCuttableBlocks)
    const clipboardBlocks = cloneBlocks(normalizedTargets)
    const deleted = await handleDeleteBlocks(normalizedTargets.map((block) => block.block_id))
    if (!deleted) {
      return false
    }

    addClipboardClip('cut', clipboardBlocks, String(currentDoc.id))
    setSelectedDocumentBlockIds(new Set())
    return true
  }

  const handlePasteClipboardClip = async (
    clipId?: string,
    previousBlockId?: string | null
  ): Promise<boolean> => {
    if (!ensureStructureEditAllowed() || !currentDoc) {
      return false
    }

    clearInsertConfirmation()
    const insertAfterBlockId = previousBlockId === undefined ? activeDocumentBlockId : previousBlockId
    if (!insertAfterBlockId) {
      setSaveStatus('error')
      setSaveError('Make a block active before pasting')
      return false
    }

    const clipboardState = useBlockClipboardStore.getState()
    const targetClipId = clipId || clipboardState.activeClipId
    const targetClip = clipboardState.clips.find((clip) => clip.id === targetClipId)

    if (!targetClip) {
      setSaveStatus('error')
      setSaveError('Select a clipboard entry first')
      return false
    }

    const pasteableBlocks = targetClip.blocks.filter((block) => !block.is_system)
    if (pasteableBlocks.length === 0) {
      setSaveStatus('error')
      setSaveError('Selected clipboard entry has no pasteable blocks')
      return false
    }

    let pointer = insertAfterBlockId
    let lastPastedBlockId: string | null = null
    const pastedBlockIds: string[] = []
    for (const block of pasteableBlocks) {
      const response = await apiClient.post<BlockData>(`/documents/${currentDoc.id}/blocks`, {
        body: {
          block_type_id: block.block_type_id,
          props: preparePropsForStructureInsert(block.props as Record<string, unknown>),
          previous_block_id: pointer,
        },
      })

      if (!response.ok || !response.data) {
        setSaveStatus('error')
        setSaveError(
          withFallbackErrorMessage(response.errorMessage, `Failed to paste block ${block.block_id}`)
        )
        await refreshEditor()
        return false
      }

      pointer = response.data.block_id
      lastPastedBlockId = response.data.block_id
      pastedBlockIds.push(response.data.block_id)
    }

    await refreshEditor()
    if (lastPastedBlockId) {
      setActiveDocumentBlockId(lastPastedBlockId)
    }
    markInsertedBlocks(pastedBlockIds, insertAfterBlockId)
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
    copyBlocksToClipboard: handleCopyBlocksToClipboard,
    cutBlocksToClipboard: handleCutBlocksToClipboard,
    pasteClipboardClip: handlePasteClipboardClip,
    makeBlockActive,
    getActiveBlockId: () => activeDocumentBlockId,
    getBlocks: () => cloneBlocks(draftBlocks),
    hasUnsavedChanges: () => hasUnsavedChanges,
  }))

  const handleCopySelectedBlocksToClipboard = async () => {
    if (selectedDocumentBlocksInOrder.length === 0) {
      return
    }
    await handleCopyBlocksToClipboard(selectedDocumentBlocksInOrder.map((block) => block.block_id))
  }

  const handleCutSelectedBlocksToClipboard = async () => {
    if (selectedDocumentBlocksInOrder.length === 0) {
      return
    }
    await handleCutBlocksToClipboard(selectedDocumentBlocksInOrder.map((block) => block.block_id))
  }

  const handleRemoveSelectedBlocks = async () => {
    if (selectedDocumentBlocksInOrder.length === 0) {
      return
    }
    const removed = await handleDeleteBlocks(selectedDocumentBlocksInOrder.map((block) => block.block_id))
    if (removed) {
      setSelectedDocumentBlockIds(new Set())
    }
  }

  const handleRemoveSingleBlock = async (block: BlockData) => {
    await handleDeleteBlocks([block.block_id])
  }

  const handlePasteActiveClipboard = async () => {
    await handlePasteClipboardClip()
  }

  const handleDocumentBlockDragStart = (
    event: DragEvent<HTMLButtonElement>,
    block: BlockData
  ) => {
    if (structureEditDisabled || block.fixed_position !== null) {
      event.preventDefault()
      return
    }

    const payloadBlocks = selectedDocumentBlockIds.has(block.block_id)
      ? selectedDocumentBlocksInOrder.filter((entry) => entry.fixed_position === null)
      : [block]

    if (payloadBlocks.length === 0) {
      event.preventDefault()
      return
    }

    event.dataTransfer.setData(
      EDITOR_BLOCK_DRAG_MIME,
      JSON.stringify(payloadBlocks.map((entry) => entry.block_id))
    )
    event.dataTransfer.setData('text/plain', payloadBlocks.map((entry) => entry.block_id).join(','))
    event.dataTransfer.effectAllowed = 'copyMove'
  }

  const handleDropAtBlock = async (
    event: DragEvent<HTMLElement>,
    previousBlockId: string | null
  ) => {
    const blockType = event.dataTransfer.getData(CATALOG_BLOCK_DRAG_MIME)
    const editorBlockIds = getEditorBlockDragPayload(event)

    if (!blockType && editorBlockIds.length === 0) {
      return
    }

    event.preventDefault()
    event.stopPropagation()
    setDropPreviewPreviousBlockId(undefined)

    if (blockType) {
      await handleInsertBlock(blockType, previousBlockId)
      return
    }

    if (structureEditDisabled) {
      return
    }

    const isCopy = event.ctrlKey || event.metaKey || event.dataTransfer.dropEffect === 'copy'
    if (isCopy) {
      await handleCopyBlocks(editorBlockIds, previousBlockId)
    } else {
      await handleMoveBlocks(editorBlockIds, previousBlockId)
    }
  }

  const handleDropLineDragOver = (
    event: DragEvent<HTMLElement>,
    previousBlockId: string | null
  ) => {
    handleCanvasDragOver(event)
    if (event.defaultPrevented) {
      setDropPreviewPreviousBlockId(previousBlockId)
    }
  }

  const handleDropLineDrop = async (
    event: DragEvent<HTMLElement>,
    previousBlockId: string | null
  ) => {
    await handleDropAtBlock(event, previousBlockId)
    setDropPreviewPreviousBlockId(undefined)
  }

  const handleDropLineDragLeave = (event: DragEvent<HTMLElement>) => {
    const nextTarget = event.relatedTarget
    if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
      return
    }
    setDropPreviewPreviousBlockId(undefined)
  }

  const handleCanvasDragOver = (event: DragEvent<HTMLElement>) => {
    const hasCatalogBlock = hasDragMime(event, CATALOG_BLOCK_DRAG_MIME)
    const hasEditorBlocks = hasDragMime(event, EDITOR_BLOCK_DRAG_MIME)
    if (!hasCatalogBlock && !hasEditorBlocks) {
      return
    }
    event.preventDefault()
    event.dataTransfer.dropEffect = hasCatalogBlock || event.ctrlKey || event.metaKey ? 'copy' : 'move'
  }

  const handleCanvasDrop = async (event: DragEvent<HTMLDivElement>) => {
    const blockType = event.dataTransfer.getData(CATALOG_BLOCK_DRAG_MIME)
    const editorBlockIds = getEditorBlockDragPayload(event)
    if (!blockType && editorBlockIds.length === 0) {
      return
    }

    event.preventDefault()
    event.stopPropagation()
    const previousBlockId =
      draftBlocks.length > 0 ? draftBlocks[draftBlocks.length - 1].block_id : null
    await handleDropAtBlock(event, previousBlockId)
    setDropPreviewPreviousBlockId(undefined)
  }

  const handleEditorDragLeave = (event: DragEvent<HTMLDivElement>) => {
    const nextTarget = event.relatedTarget
    if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
      return
    }
    setDropPreviewPreviousBlockId(undefined)
  }

  const renderDropLine = (previousBlockId: string | null, key: string, className = '') => {
    const isPreviewActive =
      dropPreviewPreviousBlockId !== undefined && dropPreviewPreviousBlockId === previousBlockId
    const isConfirmed =
      !isPreviewActive &&
      confirmedInsertPreviousBlockId !== undefined &&
      confirmedInsertPreviousBlockId === previousBlockId
    const lineTone = isPreviewActive
      ? 'h-0.5 bg-blue-600 shadow-[0_0_0_2px_rgba(37,99,235,0.16)]'
      : isConfirmed
        ? 'h-0.5 bg-sky-500 shadow-[0_0_0_2px_rgba(14,165,233,0.14)]'
        : 'h-px bg-transparent'

    return (
      <div key={key} className={`relative h-0 ${className}`}>
        <div
          className="absolute inset-x-0 -top-3 z-20 h-6"
          onDragOver={(event) => handleDropLineDragOver(event, previousBlockId)}
          onDrop={(event) => {
            void handleDropLineDrop(event, previousBlockId)
          }}
          onDragLeave={handleDropLineDragLeave}
        >
          <div
            className={`pointer-events-none absolute left-0 right-0 top-1/2 -translate-y-1/2 rounded-full transition-all ${lineTone}`}
          />
          {isPreviewActive ? (
            <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 rounded-full border border-blue-300 bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700 shadow-sm">
              Insert here
            </div>
          ) : isConfirmed ? (
            <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 rounded-full border border-sky-300 bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700 shadow-sm">
              Inserted here
            </div>
          ) : null}
        </div>
      </div>
    )
  }

  const renderBlockCard = (block: BlockData, className = '') => {
    const BlockComponent = getBlockComponent(block.block_type_id)
    const baselineProps = savedBlocksById.get(block.block_id)?.props || {}
    const isActivatable = canActivateBlock(block)
    const isSelectable = canSelectBlock(block)
    const isActive = activeDocumentBlockId === block.block_id
    const isSelected = selectedDocumentBlockIds.has(block.block_id)
    const isRecentlyInserted = recentlyInsertedBlockIds.has(block.block_id)
    const blockName = getBlockDisplayName(block)
    const wrapperTone = [
      isActive
        ? 'ring-2 ring-blue-600 ring-offset-2 border-blue-500 bg-blue-50/40'
        : isSelected
          ? 'border-blue-300 bg-blue-50/25'
          : 'border-transparent',
      isRecentlyInserted ? 'border-sky-300 bg-sky-50/60 shadow-[0_0_0_4px_rgba(14,165,233,0.08)]' : '',
    ]
      .filter(Boolean)
      .join(' ')

    const maybeActivateFromInteraction = (target: EventTarget | null) => {
      if (!isActivatable) {
        return
      }
      if (target instanceof HTMLElement && target.closest('[data-block-action-silent="true"]')) {
        return
      }
      setActiveDocumentBlockId(block.block_id)
    }

    const blockContent = BlockComponent ? (
      <BlockComponent
        block={block}
        baselineProps={baselineProps}
        onUpdate={handleBlockUpdate}
        isReadOnly={false}
      />
    ) : (
      <div className="ui-card ui-card-body">
        <div className="text-red-600">Unknown block type: {block.block_type_id}</div>
        <pre className="text-xs text-gray-600 mt-2">
          {JSON.stringify(block, null, 2)}
        </pre>
      </div>
    )

    if (!isActivatable) {
      return (
        <div
          key={block.block_id}
          id={`block-${block.block_id}`}
          data-block-id={block.block_id}
          className={`scroll-mt-28 ${className}`}
        >
          {blockContent}
        </div>
      )
    }

    return (
      <motion.div
        layout="position"
        transition={BLOCK_LAYOUT_TRANSITION}
        key={block.block_id}
        id={`block-${block.block_id}`}
        data-block-id={block.block_id}
        className={`group scroll-mt-28 rounded-2xl border p-1 transition-[box-shadow,border-color,background-color] ${wrapperTone} ${className}`}
        onClickCapture={(event) => maybeActivateFromInteraction(event.target)}
        onFocusCapture={(event) => maybeActivateFromInteraction(event.target)}
        onDragOver={(event) => {
          handleDropLineDragOver(event, block.block_id)
          if (event.defaultPrevented) {
            event.stopPropagation()
          }
        }}
        onDrop={(event) => {
          void handleDropAtBlock(event, block.block_id)
        }}
      >
        <div className="mb-1 flex items-center justify-between gap-2 rounded-xl border border-gray-200 bg-white/85 px-2 py-1 shadow-sm">
          <div className="flex min-w-0 items-center gap-2">
            {isSelectable ? (
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => toggleSelectedDocumentBlock(block)}
                data-block-action-silent="true"
                className="h-3.5 w-3.5"
                aria-label={`Select ${blockName}`}
              />
            ) : null}

            <button
              type="button"
              draggable={!structureEditDisabled && block.fixed_position === null}
              onDragStart={(event) => handleDocumentBlockDragStart(event, block)}
              onDragEnd={() => setDropPreviewPreviousBlockId(undefined)}
              data-block-action-silent="true"
              disabled={structureEditDisabled || block.fixed_position !== null}
              className="ui-btn h-7 w-7 p-0 opacity-60 group-hover:opacity-100"
              aria-label={`Drag ${blockName}`}
            >
              ::
            </button>

            <button
              type="button"
              onClick={() => setActiveDocumentBlockId(block.block_id)}
              className="min-w-0 truncate text-left text-xs font-semibold text-slate-800"
            >
              {blockName}
            </button>

            {isActive ? (
              <span className="ui-badge border-blue-300 bg-blue-50 text-blue-700">Active</span>
            ) : null}
          </div>

          <div className="flex shrink-0 items-center gap-1">
            {block.is_removable ? (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation()
                  void handleRemoveSingleBlock(block)
                }}
                data-block-action-silent="true"
                disabled={structureEditDisabled}
                className="ui-btn-danger"
              >
                Remove
              </button>
            ) : null}
          </div>
        </div>

        {blockContent}
      </motion.div>
    )
  }

  const renderVisualSection = (section: DocumentVisualSection) => {
    const dropTarget = getSectionDropTarget(section)

    if (section.kind === 'loose') {
      return (
        <section
          key={section.key}
          className="rounded-2xl border border-dashed border-slate-300 bg-white/70 p-3 shadow-sm"
          onDragOver={(event) => handleDropLineDragOver(event, dropTarget)}
          onDrop={(event) => {
            void handleDropAtBlock(event, dropTarget)
          }}
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold text-slate-800">Unsectioned Operations</h2>
              <p className="text-xs text-slate-500">
                These blocks are outside Furnace and Deformation sections.
              </p>
            </div>
            <div className="ui-badge">{section.children.length} blocks</div>
          </div>
          <div className="space-y-3">
            {section.children.map((child, index) => {
              const previousBlockId = index === 0 ? child.previous_block_id : section.children[index - 1].block_id
              return (
                <div key={child.block_id}>
                  {renderDropLine(previousBlockId, `${section.key}-before-${child.block_id}`)}
                  {renderBlockCard(child)}
                </div>
              )
            })}
          </div>
        </section>
      )
    }

    const isDeformation = isDeformationSection(section.block)
    const sectionName = getBlockDisplayName(section.block)
    const sectionTone = isDeformation
      ? 'border-amber-300 bg-amber-50/70'
      : 'border-sky-300 bg-sky-50/70'
    const childRailTone = isDeformation ? 'border-amber-300' : 'border-sky-300'

    return (
      <section
        key={section.block.block_id}
        className={`rounded-2xl border p-3 shadow-sm ${sectionTone}`}
        onDragOver={(event) => handleDropLineDragOver(event, dropTarget)}
        onDrop={(event) => {
          void handleDropAtBlock(event, dropTarget)
        }}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900">{sectionName} Section</h2>
            <p className="text-xs text-slate-600">
              {isDeformation
                ? 'Operations below are visually grouped under this Deformation block.'
                : 'Furnace is a top-level section without child operation blocks.'}
            </p>
          </div>
          <div className="ui-badge">
            {isDeformation ? `${section.children.length} child blocks` : 'top level'}
          </div>
        </div>

        {renderBlockCard(section.block)}

        {isDeformation && section.children.length > 0 ? (
          <div className={`mt-4 ml-8 space-y-3 border-l-4 pl-8 ${childRailTone}`}>
            <div className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Deformation Operation Children
            </div>
            {section.children.map((child, index) => {
              const previousBlockId = index === 0 ? section.block.block_id : section.children[index - 1].block_id
              return (
                <div key={child.block_id}>
                  {renderDropLine(previousBlockId, `${section.block.block_id}-before-${child.block_id}`)}
                  {renderBlockCard(child)}
                </div>
              )
            })}
          </div>
        ) : null}
      </section>
    )
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

      <div className="border-b border-gray-200 bg-white px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <div className="ui-badge">
            Active:{' '}
            <span className="font-semibold">
              {activeDocumentBlock ? getBlockDisplayName(activeDocumentBlock) : 'none'}
            </span>
          </div>
          <div className="ui-badge">Selected: {selectedDocumentBlocksInOrder.length}</div>
          <button
            type="button"
            onClick={() => {
              void handleCopySelectedBlocksToClipboard()
            }}
            disabled={structureEditDisabled || selectedDocumentBlocksInOrder.length === 0}
            className="ui-btn"
          >
            Copy selected
          </button>
          <button
            type="button"
            onClick={() => {
              void handleCutSelectedBlocksToClipboard()
            }}
            disabled={structureEditDisabled || selectedDocumentBlocksInOrder.length === 0}
            className="ui-btn-danger"
          >
            Cut selected
          </button>
          <button
            type="button"
            onClick={() => {
              void handleRemoveSelectedBlocks()
            }}
            disabled={structureEditDisabled || selectedDocumentBlocksInOrder.length === 0}
            className="ui-btn-danger"
          >
            Remove selected
          </button>
          <button
            type="button"
            onClick={() => {
              void handlePasteActiveClipboard()
            }}
            disabled={structureEditDisabled || !activeClipboardClip || !activeDocumentBlockId}
            className="ui-btn-primary"
          >
            Paste after active
          </button>
          <button
            type="button"
            onClick={clearSelectedDocumentBlocks}
            disabled={selectedDocumentBlocksInOrder.length === 0}
            className="ui-btn"
          >
            Clear selection
          </button>
          {activeClipboardClip ? (
            <div className="min-w-0 max-w-[260px] truncate text-xs text-gray-500">
              Clipboard: {activeClipboardClip.blocks.length} block
              {activeClipboardClip.blocks.length === 1 ? '' : 's'}
            </div>
          ) : null}
        </div>
      </div>

      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto bg-gray-100"
        onDragOver={handleCanvasDragOver}
        onDragLeave={handleEditorDragLeave}
        onDrop={(event) => {
          void handleCanvasDrop(event)
        }}
      >
        <div className="max-w-6xl mx-auto py-5 px-4">
          {draftBlocks.length === 0 ? (
            <div className="text-center text-gray-500 py-8 text-sm">No blocks found in this document.</div>
          ) : (
            <div className="rounded-[28px] border border-slate-300 bg-gradient-to-br from-slate-50 via-white to-stone-100 p-3 shadow-sm sm:p-5">
              <div className="mb-4 flex items-center justify-between gap-3 px-1">
                <div>
                  <div className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">
                    Document Canvas
                  </div>
                  <div className="text-sm text-slate-600">
                    Title contains Material, Input Workpiece, and Mesh setup. Sections below stay flat in DB.
                  </div>
                </div>
                <div className="ui-badge">{draftBlocks.length} flat blocks</div>
              </div>

              <div
                className="space-y-4"
                onDragOver={handleCanvasDragOver}
                onDrop={(event) => {
                  void handleCanvasDrop(event)
                }}
              >
                {documentVisualLayout.heading ? (
                  <div>
                    {renderBlockCard(documentVisualLayout.heading)}
                    {renderDropLine(
                      documentVisualLayout.heading.block_id,
                      `${documentVisualLayout.heading.block_id}-after-heading`
                    )}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-red-300 bg-red-50 p-4 text-sm text-red-700">
                    Document title block is missing.
                  </div>
                )}

                <div className="space-y-4">
                  {documentVisualLayout.sections.length > 0 ? (
                    documentVisualLayout.sections.map((section) => {
                      const sectionKey = section.kind === 'section' ? section.block.block_id : section.key
                      return (
                        <div key={sectionKey}>
                          {renderVisualSection(section)}
                          {renderDropLine(getSectionDropTarget(section), `${sectionKey}-after-section`)}
                        </div>
                      )
                    })
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-300 bg-white/70 p-5 text-center text-sm text-slate-500">
                      Add Furnace or Deformation blocks to build the technological process.
                    </div>
                  )}
                </div>
              </div>
            </div>
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
