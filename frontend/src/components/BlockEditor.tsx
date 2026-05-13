import {
  useCallback,
  DragEvent,
  forwardRef,
  MouseEvent,
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
import { loadDocumentResumeState, saveDocumentResumeState } from '../lib/documentResumeState'
import { getBlockComponent, type BlockData, type SectionNumberingControl } from './blocks'
import DocumentInlineResults from './inlineResults/DocumentInlineResults'
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
  hoveredDocumentBlockId: string | null
  documentBlocks: BlockData[]
  activeDocumentBlockLabel: string | null
  selectedDocumentBlockIds: string[]
  selectedDocumentBlockLabel: string | null
  structureEditDisabled: boolean
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
  clearSelectedBlocks: () => void
  getActiveBlockId: () => string | null
  getBlocks: () => BlockData[]
  hasUnsavedChanges: () => boolean
}

interface BlockEditorProps {
  className?: string
  showPreprocessorResults?: boolean
  showPostprocessorResults?: boolean
  onMetaChange?: (meta: BlockEditorMeta) => void
}

const DOCUMENT_BLOCK_TYPE_ID = 'document'
const HEATING_SECTION_TYPE_ID = 'heating'
const DEFORMATION_SECTION_TYPE_ID = 'deformation'
const FURNACE_BLOCK_TYPE_ID = 'furnace'
const OPERATION_BLOCK_TYPE_ID = 'operation'
const OPERATION_PROPERTIES = 'operation_properties'
const EDITOR_BLOCK_DRAG_MIME = 'application/x-forgelab-editor-block-ids'
const INSERT_CONFIRMATION_DURATION_MS = 1100
const BLOCK_LAYOUT_TRANSITION = {
  duration: 0.38,
  ease: 'easeInOut' as const,
}
const OPERATION_TYPE_PROP_KEYS = [
  'operation_template_id',
  'operation_template_version',
  'operation_kind',
  'target',
  'template_snapshot',
  'operation_template',
  'title',
] as const
const OPERATION_TYPE_NAMESPACE_KEYS = [
  'operation_template_id',
  'operation_template_version',
  'operation_kind',
  'target',
  'template_snapshot',
] as const
const OPERATION_TEMPLATE_TO_DEFORMATION_FEED_KEY: Record<string, string> = {
  'operation.tail_flattening': 'tail_flattening',
  'operation.cogging': 'cogging',
  'operation.radial': 'radial',
  'operation.transversal': 'transversal',
}

type ShortcutShiftDirection = 'up' | 'down'
type ShortcutInsertPosition = 'above' | 'below'

interface ShortcutMoveUnit {
  ids: string[]
  startIndex: number
  endIndex: number
}

interface ShortcutMovePlan {
  blockIds: string[]
  previousBlockId: string | null
}

interface ShortcutMovePlanResult {
  plan: ShortcutMovePlan | null
  error?: string
}

interface ShortcutInsertPlan {
  blockTypeId: string
  previousBlockId: string | null
  props: Record<string, unknown>
}

interface ShortcutInsertPlanResult {
  plan: ShortcutInsertPlan | null
  error?: string
}

interface SectionInsertMenuState {
  blockId: string
  position: ShortcutInsertPosition
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

interface RenderBlockCardOptions {
  renderVariant?: string
  showToolbar?: boolean
  elementId?: string | null
  keySuffix?: string
  dropPreviousBlockId?: string | null
  sectionNumberingControl?: SectionNumberingControl
  deformationFeedKeys?: string[]
}

function coercePositiveInteger(value: unknown, fallback: number): number {
  const parsed = Number.parseInt(String(value ?? ''), 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function isTopLevelDocumentSection(block: BlockData): boolean {
  return block.block_type_id === HEATING_SECTION_TYPE_ID || block.block_type_id === DEFORMATION_SECTION_TYPE_ID
}

function isDeformationSection(block: BlockData): boolean {
  return block.block_type_id === DEFORMATION_SECTION_TYPE_ID
}

function isHeatingSection(block: BlockData): boolean {
  return block.block_type_id === HEATING_SECTION_TYPE_ID
}

function isOperationBlock(block: BlockData): boolean {
  return block.block_type_id === OPERATION_BLOCK_TYPE_ID
}

function isFurnaceBlock(block: BlockData): boolean {
  return block.block_type_id === FURNACE_BLOCK_TYPE_ID
}

function canActivateBlock(block: BlockData): boolean {
  return block.block_type_id !== DOCUMENT_BLOCK_TYPE_ID
}

function canSelectBlock(block: BlockData): boolean {
  return block.block_type_id !== DOCUMENT_BLOCK_TYPE_ID && !block.is_system
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

function buildOperationMoveUnits(blocks: BlockData[]): ShortcutMoveUnit[] {
  return blocks.reduce<ShortcutMoveUnit[]>((units, block, index) => {
    if (isOperationBlock(block)) {
      units.push({
        ids: [block.block_id],
        startIndex: index,
        endIndex: index,
      })
    }
    return units
  }, [])
}

function buildFurnaceMoveUnits(blocks: BlockData[]): ShortcutMoveUnit[] {
  return blocks.reduce<ShortcutMoveUnit[]>((units, block, index) => {
    if (isFurnaceBlock(block)) {
      units.push({
        ids: [block.block_id],
        startIndex: index,
        endIndex: index,
      })
    }
    return units
  }, [])
}

function buildSectionMoveUnits(blocks: BlockData[]): ShortcutMoveUnit[] {
  const units: ShortcutMoveUnit[] = []
  let index = 0

  while (index < blocks.length) {
    const block = blocks[index]

    if (!isTopLevelDocumentSection(block)) {
      index += 1
      continue
    }

    const ids = [block.block_id]
    let endIndex = index

    if (isDeformationSection(block) || isHeatingSection(block)) {
      let childIndex = index + 1
      while (
        childIndex < blocks.length &&
        blocks[childIndex].block_type_id !== DOCUMENT_BLOCK_TYPE_ID &&
        !isTopLevelDocumentSection(blocks[childIndex])
      ) {
        ids.push(blocks[childIndex].block_id)
        endIndex = childIndex
        childIndex += 1
      }
    }

    units.push({
      ids,
      startIndex: index,
      endIndex,
    })
    index = endIndex + 1
  }

  return units
}

function getAnchorBeforeBlockAfterRemoving(
  blocks: BlockData[],
  movingIds: Set<string>,
  nextBlockId: string | null
): string | null {
  const remainingBlocks = blocks.filter((block) => !movingIds.has(block.block_id))
  if (nextBlockId === null) {
    return remainingBlocks[remainingBlocks.length - 1]?.block_id ?? null
  }

  const nextIndex = remainingBlocks.findIndex((block) => block.block_id === nextBlockId)
  if (nextIndex < 0) {
    return remainingBlocks[remainingBlocks.length - 1]?.block_id ?? null
  }
  return nextIndex > 0 ? remainingBlocks[nextIndex - 1].block_id : null
}

function areIndexesContiguous(indexes: number[]): boolean {
  return indexes.every((index, arrayIndex) => arrayIndex === 0 || index === indexes[arrayIndex - 1] + 1)
}

function buildShortcutMovePlanFromUnits(
  blocks: BlockData[],
  units: ShortcutMoveUnit[],
  targetUnitIndexes: number[],
  direction: ShortcutShiftDirection
): ShortcutMovePlan | null {
  const sortedUnitIndexes = Array.from(new Set(targetUnitIndexes)).sort((left, right) => left - right)
  if (sortedUnitIndexes.length === 0) {
    return null
  }

  const movingIds = new Set(
    sortedUnitIndexes.flatMap((unitIndex) => units[unitIndex]?.ids ?? [])
  )
  if (movingIds.size === 0) {
    return null
  }

  const blockIds = blocks
    .filter((block) => movingIds.has(block.block_id))
    .map((block) => block.block_id)
  const firstUnitIndex = sortedUnitIndexes[0]
  const lastUnitIndex = sortedUnitIndexes[sortedUnitIndexes.length - 1]
  const firstUnit = units[firstUnitIndex]
  const lastUnit = units[lastUnitIndex]

  if (!firstUnit || !lastUnit) {
    return null
  }

  if (!areIndexesContiguous(sortedUnitIndexes)) {
    if (direction === 'up') {
      return {
        blockIds,
        previousBlockId: blocks[firstUnit.startIndex].previous_block_id,
      }
    }

    return {
      blockIds,
      previousBlockId: getAnchorBeforeBlockAfterRemoving(
        blocks,
        movingIds,
        blocks[lastUnit.endIndex].next_block_id
      ),
    }
  }

  if (direction === 'up') {
    if (firstUnitIndex === 0) {
      return null
    }
    const previousUnit = units[firstUnitIndex - 1]
    return {
      blockIds,
      previousBlockId: blocks[previousUnit.startIndex].previous_block_id,
    }
  }

  if (lastUnitIndex >= units.length - 1) {
    return null
  }
  const nextUnit = units[lastUnitIndex + 1]
  return {
    blockIds,
    previousBlockId: blocks[nextUnit.endIndex].block_id,
  }
}

function getOperationLibraryName(block: BlockData): string | null {
  const title = block.props?.title
  if (typeof title === 'string' && title.trim()) {
    return title
  }
  const template = block.props?.operation_template || block.props?.template_snapshot
  if (template && typeof template === 'object') {
    const label = (template as { display_name?: unknown; label?: unknown }).display_name ||
      (template as { label?: unknown }).label
    if (typeof label === 'string' && label.trim()) {
      return label
    }
  }
  return null
}

function getBlockDisplayName(block: BlockData): string {
  if (block.block_type_id === DOCUMENT_BLOCK_TYPE_ID) {
    return 'Document'
  }
  if (block.block_type_id === HEATING_SECTION_TYPE_ID) {
    return 'Heating'
  }
  if (block.block_type_id === FURNACE_BLOCK_TYPE_ID) {
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
  const heading = blocks.find((block) => block.block_type_id === DOCUMENT_BLOCK_TYPE_ID) || null
  const sections: DocumentVisualSection[] = []
  let activeSection: Extract<DocumentVisualSection, { kind: 'section' }> | null = null
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
      activeSection = section
      continue
    }

    if (
      activeSection &&
      ((isDeformationSection(activeSection.block) && isOperationBlock(block)) ||
        (isHeatingSection(activeSection.block) && isFurnaceBlock(block)))
    ) {
      activeSection.children.push(block)
    } else {
      appendLooseBlock(block)
    }
  }

  return { heading, sections }
}

function buildSectionNumbers(
  sections: DocumentVisualSection[],
  startNumber: number
): Map<string, string> {
  const numbersByBlockId = new Map<string, string>()
  let sectionIndex = 0
  let currentNumber = startNumber

  while (sectionIndex < sections.length) {
    const section = sections[sectionIndex]
    if (section.kind !== 'section') {
      sectionIndex += 1
      continue
    }

    const nextSection = sections[sectionIndex + 1]
    if (
      isHeatingSection(section.block) &&
      nextSection?.kind === 'section' &&
      isDeformationSection(nextSection.block)
    ) {
      numbersByBlockId.set(section.block.block_id, `${currentNumber}.1`)
      numbersByBlockId.set(nextSection.block.block_id, `${currentNumber}.2`)
      currentNumber += 1
      sectionIndex += 2
      continue
    }

    numbersByBlockId.set(section.block.block_id, `${currentNumber}.`)
    currentNumber += 1
    sectionIndex += 1
  }

  return numbersByBlockId
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
  delete clonedProps.operation_template
  delete clonedProps.operation_type
  delete clonedProps.operation_templates
  delete clonedProps.operation_type_selector
  delete clonedProps.operation_block_parsing_rules
  delete clonedProps.parameters_calculation_mode_selector
  delete clonedProps.editable_fields
  delete clonedProps.field_limits
  return clonedProps
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function getOperationTemplateIdFromProps(props: Record<string, unknown> | undefined): string {
  const rawProps = props || {}
  const operationProperties = asRecord(rawProps[OPERATION_PROPERTIES])
  const value = rawProps.operation_template_id ?? operationProperties.operation_template_id
  return value === null || value === undefined ? '' : String(value)
}

function getDeformationFeedKeysFromChildren(children: BlockData[]): string[] {
  const keys = new Set<string>()
  children.forEach((child) => {
    if (child.block_type_id !== OPERATION_BLOCK_TYPE_ID) {
      return
    }
    const templateId = getOperationTemplateIdFromProps(child.props)
    const feedKey = OPERATION_TEMPLATE_TO_DEFORMATION_FEED_KEY[templateId]
    if (feedKey) {
      keys.add(feedKey)
    }
  })
  return Array.from(keys)
}

function hasUnsavedOperationTypeChange(
  draftProps: Record<string, unknown>,
  baselineProps: Record<string, unknown>
): boolean {
  return getOperationTemplateIdFromProps(draftProps) !== getOperationTemplateIdFromProps(baselineProps)
}

function restoreOperationTypeProps(
  draftProps: Record<string, unknown>,
  baselineProps: Record<string, unknown>
): Record<string, unknown> {
  const nextProps = cloneProps(draftProps)

  OPERATION_TYPE_PROP_KEYS.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(baselineProps, key)) {
      nextProps[key] = cloneProps({ value: baselineProps[key] }).value
    } else {
      delete nextProps[key]
    }
  })

  const draftOperationProperties = asRecord(draftProps[OPERATION_PROPERTIES])
  const baselineOperationProperties = asRecord(baselineProps[OPERATION_PROPERTIES])
  if (
    Object.keys(draftOperationProperties).length > 0 ||
    Object.keys(baselineOperationProperties).length > 0
  ) {
    const nextOperationProperties = cloneProps(draftOperationProperties)
    OPERATION_TYPE_NAMESPACE_KEYS.forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(baselineOperationProperties, key)) {
        nextOperationProperties[key] = cloneProps({ value: baselineOperationProperties[key] }).value
      } else {
        delete nextOperationProperties[key]
      }
    })
    nextProps[OPERATION_PROPERTIES] = nextOperationProperties
  }

  return nextProps
}

function isInteractiveShortcutTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false
  }
  if (target.isContentEditable) {
    return true
  }

  return Boolean(
    target.closest(
      [
        'input',
        'textarea',
        'select',
        'button',
        '[role="combobox"]',
        '[role="listbox"]',
        '[role="menu"]',
        '[role="textbox"]',
      ].join(',')
    )
  )
}

const BlockEditor = forwardRef<BlockEditorHandle, BlockEditorProps>(function BlockEditor(
  {
    className,
    showPreprocessorResults = false,
    showPostprocessorResults = false,
    onMetaChange,
  },
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
  const [hoveredDocumentBlockId, setHoveredDocumentBlockId] = useState<string | null>(null)
  const [selectedDocumentBlockIds, setSelectedDocumentBlockIds] = useState<Set<string>>(new Set())
  const [dropPreviewPreviousBlockId, setDropPreviewPreviousBlockId] = useState<string | null | undefined>(undefined)
  const [confirmedInsertPreviousBlockId, setConfirmedInsertPreviousBlockId] = useState<string | null | undefined>(undefined)
  const [recentlyInsertedBlockIds, setRecentlyInsertedBlockIds] = useState<Set<string>>(new Set())
  const [sectionInsertMenu, setSectionInsertMenu] = useState<SectionInsertMenuState | null>(null)
  const activeSessionIdRef = useRef<string | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const insertConfirmationTimeoutRef = useRef<number | null>(null)
  const previousActiveDocumentBlockIdRef = useRef<string | null>(null)
  const restoredDocumentIdRef = useRef<string | null>(null)
  const scrollPersistFrameRef = useRef<number | null>(null)
  const latestScrollTopRef = useRef(0)

  const { currentDoc, fetchDocument } = useDocumentsStore()
  const addClipboardClip = useBlockClipboardStore((state) => state.addClip)

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
    const headingBlock = draftBlocks.find((block) => block.block_type_id === DOCUMENT_BLOCK_TYPE_ID)
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

  const sectionNumbersByBlockId = useMemo(() => {
    const sectionNumberingStart = coercePositiveInteger(
      documentVisualLayout.heading?.props?.section_numbering_start,
      2
    )
    return buildSectionNumbers(documentVisualLayout.sections, sectionNumberingStart)
  }, [documentVisualLayout.heading?.props?.section_numbering_start, documentVisualLayout.sections])

  const firstTopLevelSectionBlockId = useMemo(() => {
    return documentVisualLayout.sections.find((section) => section.kind === 'section')?.block.block_id || null
  }, [documentVisualLayout.sections])

  const activeDocumentBlock = useMemo(
    () => draftBlocks.find((block) => block.block_id === activeDocumentBlockId) || null,
    [activeDocumentBlockId, draftBlocks]
  )

  const selectedDocumentBlocksInOrder = useMemo(() => {
    return draftBlocks.filter((block) => selectedDocumentBlockIds.has(block.block_id))
  }, [draftBlocks, selectedDocumentBlockIds])

  const inlineResultContextBlockId = useMemo(() => {
    if (!showPreprocessorResults && !showPostprocessorResults) {
      return null
    }
    if (selectedDocumentBlocksInOrder.length === 1) {
      return selectedDocumentBlocksInOrder[0].block_id
    }
    if (selectedDocumentBlocksInOrder.length === 0) {
      return activeDocumentBlockId
    }
    return null
  }, [
    activeDocumentBlockId,
    selectedDocumentBlocksInOrder,
    showPostprocessorResults,
    showPreprocessorResults,
  ])

  const activeDocumentBlockLabel = activeDocumentBlock ? getBlockDisplayName(activeDocumentBlock) : null
  const selectedDocumentBlockLabel = selectedDocumentBlocksInOrder.length === 1
    ? getBlockDisplayName(selectedDocumentBlocksInOrder[0])
    : null

  const structureEditDisabled = hasUnsavedChanges

  const persistResumeForCurrentDocument = useCallback(
    (patch: Partial<{ scrollTop: number; selectedBlockIds: string[] }> = {}) => {
      if (!currentDoc?.id) {
        return
      }

      saveDocumentResumeState({
        projectId: String(currentDoc.project_id),
        documentId: currentDoc.id,
        ...patch,
      })
    },
    [currentDoc?.id, currentDoc?.project_id]
  )

  const persistSelectedBlockIds = useCallback(
    (blockIds: Iterable<string>) => {
      persistResumeForCurrentDocument({ selectedBlockIds: Array.from(blockIds) })
    },
    [persistResumeForCurrentDocument]
  )

  const restoreScrollTop = useCallback((scrollTop: number) => {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (scrollContainerRef.current) {
          scrollContainerRef.current.scrollTop = scrollTop
        }
      })
    })
  }, [])

  const loadEditorState = useCallback(
    async (
      docId: string,
      refreshDocument: boolean,
      options?: { showLoading?: boolean; preserveScroll?: boolean }
    ) => {
      const showLoading = options?.showLoading ?? true
      const preserveScroll = options?.preserveScroll ?? false
      const scrollTopBefore = preserveScroll ? scrollContainerRef.current?.scrollTop ?? null : null
      const resumeState = loadDocumentResumeState()
      const shouldRestoreResume =
        resumeState?.documentId === docId && restoredDocumentIdRef.current !== docId

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
        setHoveredDocumentBlockId(null)

        if (shouldRestoreResume && resumeState) {
          const blocksById = new Map(loadedBlocks.map((block) => [block.block_id, block]))
          const selectedBlockIds = resumeState.selectedBlockIds.filter((blockId) => {
            const block = blocksById.get(blockId)
            return Boolean(block && canSelectBlock(block))
          })
          setSelectedDocumentBlockIds(new Set(selectedBlockIds))
          restoredDocumentIdRef.current = docId
          restoreScrollTop(resumeState.scrollTop)
        } else if (scrollTopBefore !== null) {
          restoreScrollTop(scrollTopBefore)
        }
      } finally {
        if (showLoading) {
          setIsLoading(false)
        }
      }
    },
    [fetchDocument, restoreScrollTop]
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
      if (scrollPersistFrameRef.current !== null) {
        window.cancelAnimationFrame(scrollPersistFrameRef.current)
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
      setSectionInsertMenu(null)
      clearInsertConfirmation()
      setIsLoading(false)
      return
    }

    setActiveDocumentBlockId(null)
    setSelectedDocumentBlockIds(new Set())
    setDropPreviewPreviousBlockId(undefined)
    restoredDocumentIdRef.current = null
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
    const previousActiveBlockId = previousActiveDocumentBlockIdRef.current
    if (previousActiveBlockId && previousActiveBlockId !== activeDocumentBlockId) {
      const baselineBlock = savedBlocksById.get(previousActiveBlockId)
      if (baselineBlock?.block_type_id === OPERATION_BLOCK_TYPE_ID) {
        setDraftBlocks((previousBlocks) => {
          let changed = false
          const nextBlocks = previousBlocks.map((block) => {
            if (block.block_id !== previousActiveBlockId || block.block_type_id !== OPERATION_BLOCK_TYPE_ID) {
              return block
            }

            if (!hasUnsavedOperationTypeChange(
              block.props as Record<string, unknown>,
              baselineBlock.props as Record<string, unknown>
            )) {
              return block
            }

            changed = true
            return {
              ...block,
              props: restoreOperationTypeProps(
                block.props as Record<string, unknown>,
                baselineBlock.props as Record<string, unknown>
              ),
            }
          })
          return changed ? nextBlocks : previousBlocks
        })
      }
    }

    previousActiveDocumentBlockIdRef.current = activeDocumentBlockId
  }, [activeDocumentBlockId, savedBlocksById])

  useEffect(() => {
    if (!onMetaChange) {
      return
    }

    onMetaChange({
      isLoading,
      draftDocumentName,
      sourceDocumentId: currentDoc?.source_document_id ?? null,
      activeDocumentBlockId,
      hoveredDocumentBlockId,
      documentBlocks: cloneBlocks(draftBlocks),
      activeDocumentBlockLabel,
      selectedDocumentBlockIds: selectedDocumentBlocksInOrder.map((block) => block.block_id),
      selectedDocumentBlockLabel,
      structureEditDisabled,
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
    hoveredDocumentBlockId,
    activeDocumentBlockLabel,
    draftBlocks,
    draftDocumentName,
    hasUnsavedChanges,
    isLineageLoading,
    isLoading,
    isSessionsLoading,
    onMetaChange,
    redoStack.length,
    saveError,
    saveStatus,
    selectedDocumentBlockLabel,
    selectedDocumentBlocksInOrder,
    structureEditDisabled,
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

  const buildSectionNumberingControl = (): SectionNumberingControl | undefined => {
    const heading = documentVisualLayout.heading
    if (!heading) {
      return undefined
    }

    const baselineHeadingProps = savedBlocksById.get(heading.block_id)?.props || {}
    const currentValue = String(heading.props?.section_numbering_start ?? 2)
    const baselineValue = String(baselineHeadingProps.section_numbering_start ?? 2)

    return {
      value: currentValue,
      isDirty: currentValue !== baselineValue,
      onChange: (value: string) => {
        handleBlockUpdate(heading.block_id, {
          ...(heading.props || {}),
          section_numbering_start: value,
        })
      },
      onReset: () => {
        handleBlockUpdate(heading.block_id, {
          ...(heading.props || {}),
          section_numbering_start: baselineHeadingProps.section_numbering_start ?? 2,
        })
      },
    }
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

  const ensureStructureEditAllowed = async (): Promise<boolean> => {
    if (!currentDoc) {
      setSaveStatus('error')
      setSaveError('Select a document first')
      return false
    }

    if (hasUnsavedChanges) {
      return handleSaveChanges()
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
      persistSelectedBlockIds(next)
      return next
    })
  }

  const clearSelectedDocumentBlocks = () => {
    setSelectedDocumentBlockIds(new Set())
    persistSelectedBlockIds([])
  }

  const handleEditorScroll = () => {
    if (!currentDoc?.id || !scrollContainerRef.current) {
      return
    }

    latestScrollTopRef.current = scrollContainerRef.current.scrollTop
    if (scrollPersistFrameRef.current !== null) {
      return
    }

    scrollPersistFrameRef.current = window.requestAnimationFrame(() => {
      scrollPersistFrameRef.current = null
      persistResumeForCurrentDocument({ scrollTop: latestScrollTopRef.current })
    })
  }

  const getDefaultInsertAnchor = (): string | null => {
    if (activeDocumentBlockId) {
      return activeDocumentBlockId
    }
    return draftBlocks.length > 0 ? draftBlocks[draftBlocks.length - 1].block_id : null
  }

  const normalizeDeleteTargets = (blocks: BlockData[]): BlockData[] => {
    const seenIds = new Set<string>()
    const normalizedTargets: BlockData[] = []
    for (const block of blocks) {
      if (seenIds.has(block.block_id)) {
        continue
      }
      seenIds.add(block.block_id)
      normalizedTargets.push(block)
    }
    return normalizedTargets
  }

  const handleInsertBlock = async (
    blockTypeId: string,
    previousBlockId?: string | null,
    props: Record<string, unknown> = {}
  ): Promise<boolean> => {
    if (!(await ensureStructureEditAllowed()) || !currentDoc) {
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
    if (!(await ensureStructureEditAllowed())) {
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
      persistSelectedBlockIds(next)
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
    if (!(await ensureStructureEditAllowed())) {
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
    if (!(await ensureStructureEditAllowed()) || !currentDoc) {
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
    if (!(await ensureStructureEditAllowed()) || !currentDoc) {
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
    if (!(await ensureStructureEditAllowed()) || !currentDoc) {
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
    clearSelectedDocumentBlocks()
    return true
  }

  const handlePasteClipboardClip = async (
    clipId?: string,
    previousBlockId?: string | null
  ): Promise<boolean> => {
    if (!(await ensureStructureEditAllowed()) || !currentDoc) {
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

  const buildShortcutMovePlan = useCallback(
    (direction: ShortcutShiftDirection): ShortcutMovePlanResult => {
      const selectedBlocks = selectedDocumentBlocksInOrder.filter(
        (block) => block.fixed_position === null
      )

      if (selectedDocumentBlocksInOrder.length > 0) {
        if (selectedBlocks.length === 0) {
          return { plan: null, error: 'No movable selected blocks' }
        }

        const allOperations = selectedBlocks.every(isOperationBlock)
        const allFurnaces = selectedBlocks.every(isFurnaceBlock)
        const allSections = selectedBlocks.every(isTopLevelDocumentSection)

        if (allOperations) {
          const units = buildOperationMoveUnits(draftBlocks)
          const unitIndexes = selectedBlocks
            .map((block) => units.findIndex((unit) => unit.ids.includes(block.block_id)))
            .filter((index) => index >= 0)
          return {
            plan: buildShortcutMovePlanFromUnits(draftBlocks, units, unitIndexes, direction),
          }
        }

        if (allFurnaces) {
          const units = buildFurnaceMoveUnits(draftBlocks)
          const unitIndexes = selectedBlocks
            .map((block) => units.findIndex((unit) => unit.ids.includes(block.block_id)))
            .filter((index) => index >= 0)
          return {
            plan: buildShortcutMovePlanFromUnits(draftBlocks, units, unitIndexes, direction),
          }
        }

        if (allSections) {
          const units = buildSectionMoveUnits(draftBlocks)
          const unitIndexes = selectedBlocks
            .map((block) => units.findIndex((unit) => unit.ids[0] === block.block_id))
            .filter((index) => index >= 0)
          return {
            plan: buildShortcutMovePlanFromUnits(draftBlocks, units, unitIndexes, direction),
          }
        }

        return {
          plan: null,
          error: 'Select operation blocks, furnace blocks, or top-level sections before shifting',
        }
      }

      if (!activeDocumentBlock || activeDocumentBlock.fixed_position !== null) {
        return { plan: null }
      }

      if (isOperationBlock(activeDocumentBlock)) {
        const units = buildOperationMoveUnits(draftBlocks)
        const unitIndex = units.findIndex((unit) => unit.ids.includes(activeDocumentBlock.block_id))
        return {
          plan: buildShortcutMovePlanFromUnits(draftBlocks, units, [unitIndex], direction),
        }
      }

      if (isFurnaceBlock(activeDocumentBlock)) {
        const units = buildFurnaceMoveUnits(draftBlocks)
        const unitIndex = units.findIndex((unit) => unit.ids.includes(activeDocumentBlock.block_id))
        return {
          plan: buildShortcutMovePlanFromUnits(draftBlocks, units, [unitIndex], direction),
        }
      }

      if (isTopLevelDocumentSection(activeDocumentBlock)) {
        const units = buildSectionMoveUnits(draftBlocks)
        const unitIndex = units.findIndex((unit) => unit.ids[0] === activeDocumentBlock.block_id)
        return {
          plan: buildShortcutMovePlanFromUnits(draftBlocks, units, [unitIndex], direction),
        }
      }

      return { plan: null, error: 'This block type cannot be shifted with the keyboard shortcut' }
    },
    [activeDocumentBlock, draftBlocks, selectedDocumentBlocksInOrder]
  )

  const handleShortcutShift = useCallback(
    async (direction: ShortcutShiftDirection): Promise<void> => {
      const { plan, error } = buildShortcutMovePlan(direction)
      if (error) {
        setSaveStatus('error')
        setSaveError(error)
        return
      }
      if (!plan) {
        return
      }

      await handleMoveBlocks(plan.blockIds, plan.previousBlockId)
    },
    [buildShortcutMovePlan, handleMoveBlocks]
  )

  const buildShortcutInsertPlan = useCallback(
    (
      position: ShortcutInsertPosition,
      targetBlock = activeDocumentBlock,
      options: { ignoreSelection?: boolean } = {}
    ): ShortcutInsertPlanResult => {
      if (!options.ignoreSelection && selectedDocumentBlocksInOrder.length > 0) {
        return { plan: null, error: 'Clear block selection before inserting by shortcut' }
      }
      if (!targetBlock || targetBlock.block_type_id === DOCUMENT_BLOCK_TYPE_ID) {
        return { plan: null }
      }

      const blockTypeId = targetBlock.block_type_id
      let previousBlockId = position === 'above'
        ? targetBlock.previous_block_id
        : targetBlock.block_id

      if (position === 'below' && isTopLevelDocumentSection(targetBlock)) {
        const sectionUnit = buildSectionMoveUnits(draftBlocks).find(
          (unit) => unit.ids[0] === targetBlock.block_id
        )
        previousBlockId = sectionUnit
          ? draftBlocks[sectionUnit.endIndex].block_id
          : targetBlock.block_id
      }

      return {
        plan: {
          blockTypeId,
          previousBlockId,
          props: {},
        },
      }
    },
    [activeDocumentBlock, draftBlocks, selectedDocumentBlocksInOrder.length]
  )

  const handleShortcutInsert = useCallback(
    async (position: ShortcutInsertPosition): Promise<void> => {
      const { plan, error } = buildShortcutInsertPlan(position)
      if (error) {
        setSaveStatus('error')
        setSaveError(error)
        return
      }
      if (!plan) {
        return
      }

      await handleInsertBlock(plan.blockTypeId, plan.previousBlockId, plan.props)
    },
    [buildShortcutInsertPlan, handleInsertBlock]
  )

  const handleInlineInsert = async (
    block: BlockData,
    position: ShortcutInsertPosition
  ): Promise<void> => {
    const { plan, error } = buildShortcutInsertPlan(position, block, { ignoreSelection: true })
    if (error) {
      setSaveStatus('error')
      setSaveError(error)
      return
    }
    if (!plan) {
      return
    }

    await handleInsertBlock(plan.blockTypeId, plan.previousBlockId, plan.props)
  }

  const getTopLevelSectionInsertAnchor = (
    block: BlockData,
    position: ShortcutInsertPosition
  ): string | null => {
    if (position === 'above') {
      return block.previous_block_id
    }
    const sectionUnit = buildSectionMoveUnits(draftBlocks).find(
      (unit) => unit.ids[0] === block.block_id
    )
    return sectionUnit ? draftBlocks[sectionUnit.endIndex].block_id : block.block_id
  }

  const handleInlineTopLevelSectionInsert = async (
    anchorBlock: BlockData,
    blockTypeId: typeof HEATING_SECTION_TYPE_ID | typeof DEFORMATION_SECTION_TYPE_ID,
    position: ShortcutInsertPosition
  ): Promise<void> => {
    setSectionInsertMenu(null)
    await handleInsertBlock(blockTypeId, getTopLevelSectionInsertAnchor(anchorBlock, position), {})
  }

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        event.isComposing ||
        !event.shiftKey ||
        event.ctrlKey ||
        event.metaKey ||
        isInteractiveShortcutTarget(event.target)
      ) {
        return
      }

      if (event.key === 'Enter') {
        event.preventDefault()
        void handleShortcutInsert(event.altKey ? 'above' : 'below')
        return
      }

      if (!event.altKey) {
        return
      }
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') {
        return
      }

      event.preventDefault()
      void handleShortcutShift(event.key === 'ArrowUp' ? 'up' : 'down')
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleShortcutInsert, handleShortcutShift])

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
    clearSelectedBlocks: clearSelectedDocumentBlocks,
    getActiveBlockId: () => activeDocumentBlockId,
    getBlocks: () => cloneBlocks(draftBlocks),
    hasUnsavedChanges: () => hasUnsavedChanges,
  }))

  const handleDocumentBlockDragStart = (
    event: DragEvent<HTMLButtonElement>,
    block: BlockData
  ) => {
    if (block.fixed_position !== null) {
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
    const editorBlockIds = getEditorBlockDragPayload(event)

    if (editorBlockIds.length === 0) {
      return
    }

    event.preventDefault()
    event.stopPropagation()
    setDropPreviewPreviousBlockId(undefined)

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
    const hasEditorBlocks = hasDragMime(event, EDITOR_BLOCK_DRAG_MIME)
    if (!hasEditorBlocks) {
      return
    }
    event.preventDefault()
    event.dataTransfer.dropEffect = event.ctrlKey || event.metaKey ? 'copy' : 'move'
  }

  const handleCanvasDrop = async (event: DragEvent<HTMLDivElement>) => {
    const editorBlockIds = getEditorBlockDragPayload(event)
    if (editorBlockIds.length === 0) {
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
      ? 'h-0.5 bg-[rgba(47,111,159,0.8)] shadow-[0_0_0_2px_rgba(47,111,159,0.12)]'
      : isConfirmed
        ? 'h-0.5 bg-[rgba(47,111,159,0.56)] shadow-[0_0_0_2px_rgba(47,111,159,0.1)]'
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
            <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 rounded border border-[rgba(47,111,159,0.2)] bg-white px-2 py-0.5 text-[11px] font-medium text-[rgba(47,111,159,0.95)] shadow-sm">
              Insert here
            </div>
          ) : isConfirmed ? (
            <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 rounded border border-[rgba(47,111,159,0.16)] bg-white px-2 py-0.5 text-[11px] font-medium text-[rgba(47,111,159,0.78)] shadow-sm">
              Inserted here
            </div>
          ) : null}
        </div>
      </div>
    )
  }

  const handleDocumentCanvasClick = (target: EventTarget | null) => {
    if (!(target instanceof HTMLElement)) {
      return
    }
    if (target.closest('[data-document-activatable-block="true"]')) {
      return
    }
    setSectionInsertMenu(null)
    setActiveDocumentBlockId(null)
  }

  const renderInlineResultsForBlock = (block: BlockData) => {
    if (inlineResultContextBlockId !== block.block_id) {
      return null
    }
    if (!showPreprocessorResults && !showPostprocessorResults) {
      return null
    }
    return (
      <DocumentInlineResults
        documentId={currentDoc?.id ?? null}
        blocks={draftBlocks}
        contextBlockId={block.block_id}
        showPreprocessor={showPreprocessorResults}
        showPostprocessor={showPostprocessorResults}
        hasUnsavedChanges={hasUnsavedChanges}
      />
    )
  }

  const renderBlockCard = (
    block: BlockData,
    className = '',
    sectionNumber: string | null = null,
    options: RenderBlockCardOptions = {}
  ) => {
    const BlockComponent = getBlockComponent(block.block_type_id)
    const baselineProps = savedBlocksById.get(block.block_id)?.props || {}
    const isActivatable = canActivateBlock(block)
    const isSelectable = canSelectBlock(block)
    const isActive = activeDocumentBlockId === block.block_id
    const isSelected = selectedDocumentBlockIds.has(block.block_id)
    const isRecentlyInserted = recentlyInsertedBlockIds.has(block.block_id)
    const activeSectionInsertMenu = sectionInsertMenu?.blockId === block.block_id ? sectionInsertMenu : null
    const blockName = getBlockDisplayName(block)
    const elementId = options.elementId === undefined ? `block-${block.block_id}` : options.elementId
    const showToolbar = options.showToolbar ?? true
    const reactKey = options.keySuffix ? `${block.block_id}-${options.keySuffix}` : block.block_id
    const dropPreviousBlockId = options.dropPreviousBlockId === undefined ? block.block_id : options.dropPreviousBlockId
    const wrapperTone = [
      isSelected ? 'doc-block-selected' : '',
      isActive ? 'doc-block-active' : '',
      isRecentlyInserted ? 'doc-block-recent' : '',
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
      setSectionInsertMenu(null)
      setActiveDocumentBlockId(block.block_id)
    }

    const handleInlineInsertButtonClick = (event: MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation()
      const position = event.shiftKey ? 'above' : 'below'
      if (isTopLevelDocumentSection(block)) {
        setSectionInsertMenu({ blockId: block.block_id, position })
        return
      }
      void handleInlineInsert(block, position)
    }

    const blockContent = BlockComponent ? (
      <BlockComponent
        block={block}
        baselineProps={baselineProps}
        isActive={isActive}
        saveStatus={saveStatus}
        sectionNumber={sectionNumber}
        sectionNumberingControl={options.sectionNumberingControl}
        renderVariant={options.renderVariant}
        deformationFeedKeys={options.deformationFeedKeys}
        onUpdate={handleBlockUpdate}
      />
    ) : (
      <div className="doc-content">
        <div className="text-red-600">Unknown block type: {block.block_type_id}</div>
        <pre className="text-xs text-gray-600 mt-2">
          {JSON.stringify(block, null, 2)}
        </pre>
      </div>
    )

    if (!isActivatable) {
      return (
        <div
          key={reactKey}
          id={elementId || undefined}
          data-block-id={block.block_id}
          className={`doc-block-wrapper scroll-mt-28 ${className}`}
        >
          {blockContent}
        </div>
      )
    }

    return (
      <motion.div
        layout="position"
        transition={BLOCK_LAYOUT_TRANSITION}
        key={reactKey}
        id={elementId || undefined}
        data-block-id={block.block_id}
        data-document-activatable-block="true"
        className={`doc-block-wrapper group scroll-mt-28 ${wrapperTone} ${className}`}
        onMouseEnter={() => setHoveredDocumentBlockId(block.block_id)}
        onMouseLeave={() => {
          setHoveredDocumentBlockId((current) => current === block.block_id ? null : current)
        }}
        onClickCapture={(event) => maybeActivateFromInteraction(event.target)}
        onFocusCapture={(event) => maybeActivateFromInteraction(event.target)}
        onDragOver={(event) => {
          handleDropLineDragOver(event, dropPreviousBlockId)
          if (event.defaultPrevented) {
            event.stopPropagation()
          }
        }}
        onDrop={(event) => {
          void handleDropAtBlock(event, dropPreviousBlockId)
        }}
      >
        {showToolbar ? (
          <div className="doc-block-toolbar">
            <div className="flex min-w-0 items-center gap-2">
              {isSelectable ? (
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleSelectedDocumentBlock(block)}
                  data-block-action-silent="true"
                  className="h-3.5 w-3.5 accent-stone-700"
                  aria-label={`Select ${blockName}`}
                />
              ) : null}

              <button
                type="button"
                onClick={handleInlineInsertButtonClick}
                data-block-action-silent="true"
                disabled={false}
                className="doc-block-control disabled:cursor-not-allowed"
                aria-label={
                  isTopLevelDocumentSection(block)
                    ? `Choose section type to insert near ${blockName}. Shift-click inserts above.`
                    : `Insert ${blockName} below. Shift-click to insert above.`
                }
                title={
                  isTopLevelDocumentSection(block)
                    ? `Choose section type to insert below. Shift-click chooses above.`
                    : `Insert ${blockName} below. Shift-click inserts above.`
                }
              >
                ＋
              </button>

              {activeSectionInsertMenu ? (
                <div
                  className="doc-inline-insert-menu"
                  data-block-action-silent="true"
                  onClick={(event) => event.stopPropagation()}
                >
                  <button
                    type="button"
                    onClick={() => {
                      void handleInlineTopLevelSectionInsert(
                        block,
                        HEATING_SECTION_TYPE_ID,
                        activeSectionInsertMenu.position
                      )
                    }}
                  >
                    Heating
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void handleInlineTopLevelSectionInsert(
                        block,
                        DEFORMATION_SECTION_TYPE_ID,
                        activeSectionInsertMenu.position
                      )
                    }}
                  >
                    Deformation
                  </button>
                </div>
              ) : null}

              <button
                type="button"
                draggable={block.fixed_position === null}
                onDragStart={(event) => handleDocumentBlockDragStart(event, block)}
                onDragEnd={() => setDropPreviewPreviousBlockId(undefined)}
                data-block-action-silent="true"
                disabled={block.fixed_position !== null}
                className="doc-block-control cursor-grab disabled:cursor-not-allowed"
                aria-label={`Drag ${blockName}`}
              >
                ⋮⋮
              </button>
            </div>
          </div>
        ) : null}

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
          className="doc-loose-section"
          onDragOver={(event) => handleDropLineDragOver(event, dropTarget)}
          onDrop={(event) => {
            void handleDropAtBlock(event, dropTarget)
          }}
        >
          <h2 className="doc-subtitle">Unsectioned Operations</h2>
          <div className="doc-page-body">
            {section.children.map((child, index) => {
              const previousBlockId = index === 0 ? child.previous_block_id : section.children[index - 1].block_id
              return (
                <div key={child.block_id}>
                  {renderDropLine(previousBlockId, `${section.key}-before-${child.block_id}`)}
                  {renderBlockCard(child)}
                  {renderInlineResultsForBlock(child)}
                </div>
              )
            })}
          </div>
        </section>
      )
    }

    if (isDeformationSection(section.block)) {
      const sectionNumber = sectionNumbersByBlockId.get(section.block.block_id) || null
      const sectionNumberingControl = section.block.block_id === firstTopLevelSectionBlockId
        ? buildSectionNumberingControl()
        : undefined
      return (
        <section
          key={section.block.block_id}
          className="doc-section doc-deformation-section"
          onDragOver={(event) => handleDropLineDragOver(event, dropTarget)}
          onDrop={(event) => {
            void handleDropAtBlock(event, dropTarget)
          }}
        >
          {renderBlockCard(section.block, 'doc-deformation-header-block', sectionNumber, {
            renderVariant: 'deformation-header',
            keySuffix: 'header',
            sectionNumberingControl,
          })}

          {renderBlockCard(section.block, 'doc-deformation-dies-block', null, {
            renderVariant: 'deformation-dies',
            showToolbar: false,
            elementId: null,
            keySuffix: 'dies',
            dropPreviousBlockId: section.block.block_id,
          })}

          {section.children.length > 0 ? (
            <div className="doc-children">
              {section.children.map((child, index) => {
                const previousBlockId = index === 0 ? section.block.block_id : section.children[index - 1].block_id
                const childNumber = isOperationBlock(child) ? `${index + 1}.` : null
                return (
                  <div key={child.block_id}>
                    {renderDropLine(previousBlockId, `${section.block.block_id}-before-${child.block_id}`)}
                    {renderBlockCard(child, '', childNumber)}
                    {renderInlineResultsForBlock(child)}
                  </div>
                )
              })}
            </div>
          ) : null}

          {renderBlockCard(section.block, 'doc-deformation-parameters-footer', null, {
            renderVariant: 'deformation-parameters',
            showToolbar: false,
            elementId: null,
            keySuffix: 'parameters',
            dropPreviousBlockId: dropTarget,
            deformationFeedKeys: getDeformationFeedKeysFromChildren(section.children),
          })}

          {renderInlineResultsForBlock(section.block)}
        </section>
      )
    }

    return (
      <section
        key={section.block.block_id}
        className="doc-section"
        onDragOver={(event) => handleDropLineDragOver(event, dropTarget)}
        onDrop={(event) => {
          void handleDropAtBlock(event, dropTarget)
        }}
      >
        {renderBlockCard(section.block, '', sectionNumbersByBlockId.get(section.block.block_id) || null, {
          sectionNumberingControl: section.block.block_id === firstTopLevelSectionBlockId
            ? buildSectionNumberingControl()
            : undefined,
        })}

        {section.children.length > 0 ? (
          <div className="doc-children">
            {section.children.map((child, index) => {
              const previousBlockId = index === 0 ? section.block.block_id : section.children[index - 1].block_id
              const childNumber = isDeformationSection(section.block) && isOperationBlock(child)
                ? `${index + 1}.`
                : null
                return (
                  <div key={child.block_id}>
                    {renderDropLine(previousBlockId, `${section.block.block_id}-before-${child.block_id}`)}
                    {renderBlockCard(child, '', childNumber)}
                    {renderInlineResultsForBlock(child)}
                  </div>
                )
              })}
            </div>
          ) : null}

        {renderInlineResultsForBlock(section.block)}
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

      <div
        ref={scrollContainerRef}
        className="doc-editor-shell flex-1 overflow-y-auto"
        onScroll={handleEditorScroll}
        onDragOver={handleCanvasDragOver}
        onDragLeave={handleEditorDragLeave}
        onDrop={(event) => {
          void handleCanvasDrop(event)
        }}
      >
        <div className="mx-auto px-4 pt-8 pb-[75vh]">
          {draftBlocks.length === 0 ? (
            <div className="text-center text-gray-500 py-8 text-sm">No blocks found in this document.</div>
          ) : (
            <div
              className="doc-page"
              onClick={(event) => handleDocumentCanvasClick(event.target)}
            >
              <div
                className="doc-page-body"
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
                  <div className="doc-readonly text-red-700">
                    Document title block is missing.
                  </div>
                )}

                <div className="doc-page-body">
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
                    <div className="doc-readonly py-6 text-center">
                      Add Heating or Deformation blocks to build the technological process.
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
