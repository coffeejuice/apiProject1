import { type ReactNode, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { BlockComponentProps } from './BlockRegistry'
import Tooltip from '../ui/Tooltip'
import { formatLibraryName } from '../../lib/libraryDisplay'
import { useLibraryStore } from '../../stores/useLibraryStore'

interface OperationTemplateField {
  path: string
  type?: string
  label?: string
  unit?: string | null
  default?: unknown
  options?: Array<{ value?: unknown; label?: unknown }>
}

interface SelectorNode {
  id: string
  label?: string
  value?: unknown
  template_id?: string
  children?: SelectorNode[]
}

interface OperationTypeSelector {
  tree?: SelectorNode[]
}

interface ParametersCalculationModeSelector {
  target_path?: string
  default?: unknown
  tree?: SelectorNode[]
}

interface OperationTemplate {
  id?: string
  version?: number
  label?: string
  display_name?: string
  category?: string
  operation_kind?: string
  compiler_handler?: string
  insertable?: boolean
  materialize?: boolean
  input_method?: string
  input_schema?: OperationTemplateField[]
  target_schema?: OperationTemplateField[]
}

interface RoundingTableRow {
  size?: string
  feed?: string
  angle?: string
  rotations_per_feed?: string
  speed?: string
}

type FurnaceProgramRowType = 'hold' | 'heat' | 'unload'

interface FurnaceProgramRow {
  type?: FurnaceProgramRowType
  duration_min?: string
  temperature_c?: string
}

interface FurnaceProgramSegment {
  row: FurnaceProgramRow
  type: FurnaceProgramRowType
  startX: number
  endX: number
  startY: number
  endY: number
  startTemp: number
  endTemp: number
  temperatureLabel?: string
  durationLabel?: string
}

interface FurnaceProgramMark {
  x: number
  y: number
  temperatureLabel?: string
}

interface FurnaceProgramDiagram {
  width: number
  height: number
  axisY: number
  yAxisX: number
  segments: FurnaceProgramSegment[]
  marks: FurnaceProgramMark[]
}

const HEATING_BLOCK_TYPE_ID = 'heating'
const FURNACE_BLOCK_TYPE_ID = 'furnace'
const DEFORMATION_PROPERTIES = 'deformation_properties'
const FURNACE_PROPERTIES = 'furnace_properties'
const OPERATION_PROPERTIES = 'operation_properties'
const STANDARD_RIGHT_ARROW = '→'
const RIGHT_ARROW_SYMBOLS = [
  '→', '↠', '↣', '↦', '↪', '↬', '⇀', '⇁', '⇉', '⇛', '⇝', '⇢',
  '⇨', '⇒', '⇾', '➔', '➙', '➜', '➝', '➞', '➟', '➠', '➡',
  '➢', '➣', '➤', '➥', '➦', '➧', '➨', '➩', '➪', '➫', '➬',
  '➭', '➮', '➯', '➱', '➲', '➳', '➵', '➸', '➺', '➻', '➼',
  '➽', '➾', '⟶', '⟴', '⟹', '⟼', '⟾', '⟿', '⤀', '⤏', '⤐',
  '⤳', '⥤', '⭢', '⮕',
]
const ROUNDING_TABLE_PATH = `${OPERATION_PROPERTIES}.rounding_table`
const ROUNDING_TABLE_COLUMNS: Array<{ key: keyof RoundingTableRow; label: string; minChars: number }> = [
  { key: 'size', label: 'Size', minChars: 4 },
  { key: 'feed', label: 'Feed, mm', minChars: 8 },
  { key: 'angle', label: 'Angle, °', minChars: 8 },
  { key: 'rotations_per_feed', label: 'Rotations\nper Feed', minChars: 9 },
  { key: 'speed', label: 'Speed, mm/s', minChars: 11 },
]
const DEFORMATION_SPEED_FIELDS: Array<{ field: string; label: string }> = [
  { field: 'speed_upsetting', label: 'Upsetting' },
  { field: 'speed_prolongation', label: 'Prolongation' },
]
const FEED_DIRECTION_OPTIONS: Array<{ id: number; icon: string; label: string }> = [
  { id: 2, icon: '→', label: 'Feed from left to right' },
  { id: 3, icon: '←', label: 'Feed from right to left' },
  { id: 4, icon: '↔', label: 'Alternating feed direction' },
]
const FEED_DIRECTION_DEFAULT_ID = 2
const DIE_SELECTION_MODE_PAIR = 'pair'
const DIE_SELECTION_MODE_SEPARATE = 'separate'
const DEFORMATION_FEED_ROWS: Array<{ key: string; label: string }> = [
  { key: 'tail_flattening', label: 'Tail Flattening' },
  { key: 'cogging', label: 'Cogging' },
  { key: 'radial', label: 'Radial Cogging' },
  { key: 'transversal', label: 'Transverse Cogging' },
]
const FURNACE_PROGRAM_PATH = `${FURNACE_PROPERTIES}.temperature_program`
const FURNACE_PROGRAM_TYPES: Array<{ type: FurnaceProgramRowType; icon: string; label: string }> = [
  { type: 'hold', icon: '--', label: 'Hold at specified temperature' },
  { type: 'heat', icon: '/', label: 'Wait for furnace to heat up to set temperature' },
  { type: 'unload', icon: '\\', label: 'Unload billet' },
]
const FURNACE_PROGRAM_AXIS_Y = 178
const FURNACE_PROGRAM_CHART_TOP = 34
const FURNACE_PROGRAM_CHART_BOTTOM = 124
const FURNACE_PROGRAM_LEFT = 34
const FURNACE_PROGRAM_MIN_LINE_LENGTH = 86
const FURNACE_PROGRAM_HEIGHT = 208
type DieIconFamily = 'flat' | 'v' | 'rounding' | 'gfm' | 'knife'
type DieIconMode = 'assembly' | 'top' | 'bottom'
type DiePopoverTarget = { kind: 'type' | 'name'; key: string } | null
const DIE_ICON_PATHS: Record<DieIconFamily, Partial<Record<DieIconMode, string[]>>> = {
  flat: {
    assembly: ['M18 32 H110 V58 H18 Z', 'M18 74 H110 V100 H18 Z'],
    top: ['M18 51 H110 V77 H18 Z'],
    bottom: ['M18 51 H110 V77 H18 Z'],
  },
  v: {
    assembly: ['M18 30 H110 V58 H84 L64 40 L44 58 H18 Z', 'M18 70 H44 L64 90 L84 70 H110 V100 H18 Z'],
    top: ['M18 43 H110 V71 H84 L64 53 L44 71 H18 Z'],
    bottom: ['M18 57 H44 L64 77 L84 57 H110 V87 H18 Z'],
  },
  rounding: {
    assembly: [
      'M18 30 H110 V58 H86 C82 43 72 36 64 36 C56 36 46 43 42 58 H18 Z',
      'M18 98 H110 V70 H86 C82 85 72 92 64 92 C56 92 46 85 42 70 H18 Z',
    ],
    top: ['M18 43 H110 V71 H86 C82 56 72 49 64 49 C56 49 46 56 42 71 H18 Z'],
    bottom: ['M18 85 H110 V57 H86 C82 72 72 79 64 79 C56 79 46 72 42 57 H18 Z'],
  },
  gfm: {
    assembly: [
      'M50 14 H78 L74 42 L64 54 L54 42 Z',
      'M50 114 H78 L74 86 L64 74 L54 86 Z',
      'M14 50 L42 54 L54 64 L42 74 L14 78 Z',
      'M114 50 L86 54 L74 64 L86 74 L114 78 Z',
    ],
  },
  knife: {
    assembly: ['M18 20 H110 V50 H18 Z', 'M64 70 L76 92 V118 H52 V92 Z'],
    bottom: ['M64 22 L79 54 V106 H49 V54 Z'],
  },
}

function maxVisualLineLength(value: string): number {
  return Math.max(...value.split('\n').map((line) => line.length))
}

function normalizeValue(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

function normalizeFeedDirectionId(value: unknown): string {
  const normalized = normalizeValue(value || FEED_DIRECTION_DEFAULT_ID)
  return FEED_DIRECTION_OPTIONS.some((option) => String(option.id) === normalized)
    ? normalized
    : String(FEED_DIRECTION_DEFAULT_ID)
}

function normalizeOptionalNumberId(value: unknown): number | null {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const parsed = Number(value)
  return Number.isInteger(parsed) ? parsed : null
}

function dieTypeLooksFlat(name: unknown): boolean {
  return formatLibraryName(name).toLowerCase().includes('flat')
}

function classificationMatchesType(classificationPath: string | null | undefined, dieTypeName: string): boolean {
  const normalizedPath = normalizeValue(classificationPath).toLowerCase()
  const normalizedName = dieTypeName.toLowerCase()
  if (!normalizedPath || !normalizedName) {
    return false
  }
  if (normalizedName.includes('flat')) {
    return normalizedPath.includes('flat')
  }
  if (normalizedName.includes('v')) {
    return normalizedPath.includes('vdie') || normalizedPath.includes('v-die') || normalizedPath.includes('v_die')
  }
  if (normalizedName.includes('round')) {
    return normalizedPath.includes('round')
  }
  if (normalizedName.includes('gfm')) {
    return normalizedPath.includes('gfm')
  }
  return normalizedPath.includes(normalizedName.replace(/\s+/g, '.'))
}

function formatLibraryNameOrFallback(name: unknown, fallback: string): string {
  const formatted = formatLibraryName(name)
  return formatted || fallback
}

function dieIconFamily(name: unknown): DieIconFamily {
  const normalized = formatLibraryName(name).toLowerCase()
  if (normalized.includes('knife') || normalized.includes('cut')) {
    return 'knife'
  }
  if (normalized.includes('gfm')) {
    return 'gfm'
  }
  if (normalized.includes('round')) {
    return 'rounding'
  }
  if (normalized.includes('v')) {
    return 'v'
  }
  return 'flat'
}

function dieIconPaths(name: unknown, mode: DieIconMode): string[] {
  const family = dieIconFamily(name)
  return DIE_ICON_PATHS[family][mode] || DIE_ICON_PATHS[family].assembly || DIE_ICON_PATHS.flat.assembly || []
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const RIGHT_ARROW_PATTERN = new RegExp(`-->|->|${RIGHT_ARROW_SYMBOLS.map(escapeRegExp).join('|')}`, 'g')

function normalizeRightArrows(value: string): string {
  return value.replace(RIGHT_ARROW_PATTERN, STANDARD_RIGHT_ARROW)
}

function normalizeRightArrowsWithSelection(
  value: string,
  selectionStart: number,
  selectionEnd: number,
): { value: string; selectionStart: number; selectionEnd: number } {
  return {
    value: normalizeRightArrows(value),
    selectionStart: normalizeRightArrows(value.slice(0, selectionStart)).length,
    selectionEnd: normalizeRightArrows(value.slice(0, selectionEnd)).length,
  }
}

function emptyRoundingRow(): RoundingTableRow {
  return {
    size: '',
    feed: '',
    angle: '',
    rotations_per_feed: '',
    speed: '',
  }
}

function normalizeRoundingRows(value: unknown): RoundingTableRow[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .filter((entry): entry is Record<string, unknown> => Boolean(entry && typeof entry === 'object'))
    .map((entry) => ({
      size: normalizeValue(entry.size),
      feed: normalizeValue(entry.feed),
      angle: normalizeValue(entry.angle),
      rotations_per_feed: normalizeValue(entry.rotations_per_feed),
      speed: normalizeValue(entry.speed),
    }))
}

function rowsForDisplay(rows: RoundingTableRow[]): RoundingTableRow[] {
  return rows.length > 0 ? rows : [emptyRoundingRow()]
}

function emptyFurnaceProgramRow(temperature = ''): FurnaceProgramRow {
  return {
    type: 'hold',
    duration_min: '',
    temperature_c: temperature,
  }
}

function normalizeFurnaceProgramRows(value: unknown): FurnaceProgramRow[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .filter((entry): entry is Record<string, unknown> => Boolean(entry && typeof entry === 'object'))
    .map((entry) => {
      const rawType = normalizeValue(entry.type)
      const type: FurnaceProgramRowType =
        rawType === 'heat' || rawType === 'unload' || rawType === 'hold' ? rawType : 'hold'
      return {
        type,
        duration_min: type === 'hold' ? normalizeValue(entry.duration_min) : '',
        temperature_c: type === 'hold' ? normalizeValue(entry.temperature_c) : '',
      }
    })
}

function furnaceRowsForDisplay(rows: FurnaceProgramRow[], fallbackTemperature = ''): FurnaceProgramRow[] {
  return rows.length > 0 ? rows : [emptyFurnaceProgramRow(fallbackTemperature)]
}

function parseFiniteNumber(value: unknown): number | null {
  const parsed = Number.parseFloat(normalizeValue(value))
  return Number.isFinite(parsed) ? parsed : null
}

function lastHoldTemperature(rows: FurnaceProgramRow[]): string {
  for (let index = rows.length - 1; index >= 0; index -= 1) {
    const row = rows[index]
    if ((row.type ?? 'hold') === 'hold' && normalizeValue(row.temperature_c).trim()) {
      return normalizeValue(row.temperature_c).trim()
    }
  }
  return ''
}

function nextHoldTemperature(rows: FurnaceProgramRow[], startIndex: number): number | null {
  for (let index = startIndex; index < rows.length; index += 1) {
    const row = rows[index]
    if ((row.type ?? 'hold') === 'hold') {
      const temperature = parseFiniteNumber(row.temperature_c)
      if (temperature !== null) {
        return temperature
      }
    }
  }
  return null
}

function firstHoldTemperature(rows: FurnaceProgramRow[]): number | null {
  return nextHoldTemperature(rows, 0)
}

function formatTemperatureLabel(value: unknown): string {
  const text = normalizeValue(value).trim()
  return text ? `${text} C` : ''
}

function buildFurnaceProgramDiagram(rows: FurnaceProgramRow[]): FurnaceProgramDiagram {
  const displayRows = furnaceRowsForDisplay(rows)
  const rawSegments: Array<Omit<FurnaceProgramSegment, 'startY' | 'endY'>> = []
  const fallbackTemperature = firstHoldTemperature(displayRows) ?? 1000
  let currentTemperature = fallbackTemperature
  let x = FURNACE_PROGRAM_LEFT

  displayRows.forEach((row, rowIndex) => {
    const type = row.type ?? 'hold'
    const durationText = normalizeValue(row.duration_min).trim()
    const temperatureText = normalizeValue(row.temperature_c).trim()
    const duration = parseFiniteNumber(durationText)
    const labelWidth = durationText ? `${durationText} min`.length * 7 + 28 : 0
    const holdLength = Math.max(
      FURNACE_PROGRAM_MIN_LINE_LENGTH,
      labelWidth,
      duration !== null ? Math.min(260, duration * 1.2) : 0,
    )
    const length = type === 'hold' ? holdLength : FURNACE_PROGRAM_MIN_LINE_LENGTH

    let startTemp = currentTemperature
    let endTemp = currentTemperature
    if (type === 'hold') {
      endTemp = parseFiniteNumber(temperatureText) ?? currentTemperature
      startTemp = endTemp
      currentTemperature = endTemp
    } else if (type === 'heat') {
      endTemp = nextHoldTemperature(displayRows, rowIndex + 1) ?? currentTemperature
      startTemp = currentTemperature
      if (startTemp === endTemp) {
        startTemp = endTemp - 45
      }
      currentTemperature = endTemp
    } else {
      startTemp = currentTemperature
      const nextTemperature = nextHoldTemperature(displayRows, rowIndex + 1)
      const drop = Math.max(35, Math.abs((nextTemperature ?? startTemp) - startTemp) * 0.45)
      endTemp = startTemp - drop
      currentTemperature = endTemp
    }

    rawSegments.push({
      row,
      type,
      startX: x,
      endX: x + length,
      startTemp,
      endTemp,
      temperatureLabel: type === 'hold' ? formatTemperatureLabel(temperatureText) : type === 'heat' ? formatTemperatureLabel(endTemp) : '',
      durationLabel: type === 'hold' && durationText ? `${durationText} min` : '',
    })
    x += length
  })

  const temperatureValues = rawSegments.flatMap((segment) => [segment.startTemp, segment.endTemp])
  const minTemperature = Math.min(...temperatureValues)
  const maxTemperature = Math.max(...temperatureValues)
  const range = Math.max(1, maxTemperature - minTemperature)
  const paddedMin = minTemperature - Math.max(20, range * 0.16)
  const paddedMax = maxTemperature + Math.max(20, range * 0.16)
  const paddedRange = Math.max(1, paddedMax - paddedMin)
  const yForTemperature = (temperature: number) =>
    FURNACE_PROGRAM_CHART_BOTTOM -
    ((temperature - paddedMin) / paddedRange) * (FURNACE_PROGRAM_CHART_BOTTOM - FURNACE_PROGRAM_CHART_TOP)

  const segments = rawSegments.map((segment) => ({
    ...segment,
    startY: yForTemperature(segment.startTemp),
    endY: yForTemperature(segment.endTemp),
  }))
  const marks: FurnaceProgramMark[] = []
  segments.forEach((segment) => {
    marks.push({
      x: segment.startX,
      y: segment.startY,
      temperatureLabel: segment.type === 'hold' ? segment.temperatureLabel : undefined,
    })
    marks.push({
      x: segment.endX,
      y: segment.endY,
      temperatureLabel: segment.type === 'hold' || segment.type === 'heat' ? segment.temperatureLabel : undefined,
    })
  })
  const mergedMarks: FurnaceProgramMark[] = []
  marks.forEach((mark) => {
    const existing = mergedMarks.find(
      (candidate) => Math.abs(candidate.x - mark.x) < 0.5 && Math.abs(candidate.y - mark.y) < 0.5,
    )
    if (existing) {
      existing.temperatureLabel = existing.temperatureLabel || mark.temperatureLabel
    } else {
      mergedMarks.push({ ...mark })
    }
  })

  return {
    width: Math.max(360, x + 28),
    height: FURNACE_PROGRAM_HEIGHT,
    axisY: FURNACE_PROGRAM_AXIS_Y,
    yAxisX: FURNACE_PROGRAM_LEFT,
    segments,
    marks: mergedMarks,
  }
}

function stringifyJson(value: unknown): string {
  return JSON.stringify(value ?? null)
}

function asSelectorNodes(value: unknown): SelectorNode[] {
  return Array.isArray(value) ? value.filter((entry): entry is SelectorNode => Boolean(entry && typeof entry === 'object')) : []
}

function getOperationTemplate(props: Record<string, unknown> | undefined): OperationTemplate {
  const current = props?.operation_template
  if (current && typeof current === 'object') {
    return current as OperationTemplate
  }
  const snapshot = props?.template_snapshot
  return snapshot && typeof snapshot === 'object' ? snapshot as OperationTemplate : {}
}

function getAvailableTemplates(props: Record<string, unknown> | undefined): OperationTemplate[] {
  const templates = props?.operation_templates
  return Array.isArray(templates)
    ? templates.filter((entry): entry is OperationTemplate => Boolean(entry && typeof entry === 'object'))
    : []
}

function getNestedValue(source: Record<string, unknown>, dottedPath: string): unknown {
  const parts = dottedPath.split('.').filter(Boolean)
  let cursor: unknown = source
  for (const part of parts) {
    if (!cursor || typeof cursor !== 'object' || !(part in cursor)) {
      return undefined
    }
    cursor = (cursor as Record<string, unknown>)[part]
  }
  return cursor
}

function getOperationTemplateId(props: Record<string, unknown> | undefined): string {
  const rawProps = props || {}
  const operationProperties = rawProps[OPERATION_PROPERTIES]
  const namespaced =
    operationProperties && typeof operationProperties === 'object'
      ? (operationProperties as Record<string, unknown>).operation_template_id
      : undefined
  return normalizeValue(rawProps.operation_template_id ?? namespaced)
}

function isConcreteOperationTemplateId(templateId: string): boolean {
  return Boolean(templateId && templateId !== 'operation.empty')
}

function setNestedValue(source: Record<string, unknown>, dottedPath: string, value: unknown): Record<string, unknown> {
  const parts = dottedPath.split('.').filter(Boolean)
  if (parts.length === 0) {
    return { ...source }
  }

  const result = JSON.parse(JSON.stringify(source || {})) as Record<string, unknown>
  let cursor = result
  parts.slice(0, -1).forEach((part) => {
    const existing = cursor[part]
    if (!existing || typeof existing !== 'object' || Array.isArray(existing)) {
      cursor[part] = {}
    }
    cursor = cursor[part] as Record<string, unknown>
  })
  cursor[parts[parts.length - 1]] = value
  return result
}

function setTargetDefault(target: Record<string, unknown>, path: string, value: unknown) {
  if (!path.startsWith('target.')) {
    return
  }
  const nested = setNestedValue({ target }, path, value)
  const nextTarget = nested.target
  if (nextTarget && typeof nextTarget === 'object') {
    Object.assign(target, nextTarget)
  }
}

function findPathByTemplateId(nodes: SelectorNode[], templateId: string): SelectorNode[] {
  for (const node of nodes) {
    if (node.template_id === templateId) {
      return [node]
    }
    const childPath = findPathByTemplateId(asSelectorNodes(node.children), templateId)
    if (childPath.length > 0) {
      return [node, ...childPath]
    }
  }
  return []
}

function findPathByValue(nodes: SelectorNode[], value: string): SelectorNode[] {
  for (const node of nodes) {
    if (normalizeValue(node.value) === value) {
      return [node]
    }
    const childPath = findPathByValue(asSelectorNodes(node.children), value)
    if (childPath.length > 0) {
      return [node, ...childPath]
    }
  }
  return []
}

function findFirstLeafValue(node: SelectorNode): unknown {
  const children = asSelectorNodes(node.children)
  if (children.length === 0) {
    return node.value
  }
  return findFirstLeafValue(children[0])
}

function getColumns(tree: SelectorNode[], path: SelectorNode[]): SelectorNode[][] {
  const columns: SelectorNode[][] = [tree]
  for (const node of path) {
    const children = asSelectorNodes(node.children)
    if (children.length > 0) {
      columns.push(children)
    }
  }
  return columns
}

function buildTargetDefaults(
  template: OperationTemplate,
  calculationSelector: ParametersCalculationModeSelector,
  previousTarget: unknown
): Record<string, unknown> {
  const target: Record<string, unknown> = {}
  const calculationPath = calculationSelector.target_path || 'target.parameters_calculation_mode'
  const previousCalculationMode =
    previousTarget && typeof previousTarget === 'object'
      ? (previousTarget as Record<string, unknown>).parameters_calculation_mode
      : undefined
  setTargetDefault(target, calculationPath, previousCalculationMode ?? calculationSelector.default ?? 'manual')

  for (const field of template.target_schema || []) {
    if (field.path === calculationPath) {
      continue
    }
    setTargetDefault(target, field.path, field.default ?? '')
  }
  return target
}

function renderResetButton(onClick: () => void, isDirty: boolean) {
  if (!isDirty) {
    return null
  }

  return (
    <Tooltip content="Revert this parameter">
      <button
        type="button"
        onClick={onClick}
        className="doc-reset"
        aria-label="Revert this parameter"
      >
        ↺
      </button>
    </Tooltip>
  )
}

export default function OperationBlock({
  block,
  baselineProps,
  isActive,
  saveStatus,
  sectionNumber,
  sectionNumberingControl,
  renderVariant,
  deformationFeedKeys,
  onUpdate,
}: BlockComponentProps) {
  const dies = useLibraryStore((state) => state.dies)
  const dieAssemblies = useLibraryStore((state) => state.dieAssemblies)
  const dieTypes = useLibraryStore((state) => state.dieTypes)
  const libraryHasLoaded = useLibraryStore((state) => state.hasLoaded)
  const libraryIsLoading = useLibraryStore((state) => state.isLoading)
  const fetchLibrary = useLibraryStore((state) => state.fetchAll)
  const props = block.props || {}
  const operationTextPath = `${OPERATION_PROPERTIES}.operation_text`
  const operationTextValue = normalizeValue(getNestedValue(props, operationTextPath) ?? props.operation_text)
  const roundingRows = normalizeRoundingRows(getNestedValue(props, ROUNDING_TABLE_PATH) ?? props.rounding_table)
  const baselineRoundingRows = normalizeRoundingRows(
    getNestedValue(baselineProps || {}, ROUNDING_TABLE_PATH) ?? baselineProps?.rounding_table
  )
  const template = getOperationTemplate(props)
  const availableTemplates = getAvailableTemplates(props)
  const targetSchema = template.target_schema || []
  const currentTemplateId = getOperationTemplateId(props)
  const baselineTemplateId = getOperationTemplateId(baselineProps)
  const hasSelectedOperationType = isConcreteOperationTemplateId(currentTemplateId)
  const hasSavedOperationType = isConcreteOperationTemplateId(baselineTemplateId)
  const hasUnsavedOperationTypeChange = currentTemplateId !== baselineTemplateId
  const [operationPathIds, setOperationPathIds] = useState<string[]>([])
  const [isOperationSelectorOpen, setIsOperationSelectorOpen] = useState(false)
  const [furnaceProgramView, setFurnaceProgramView] = useState<'diagram' | 'table'>('diagram')
  const [openDiePopover, setOpenDiePopover] = useState<DiePopoverTarget>(null)
  const operationTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const operationTextSelectionRef = useRef<{ start: number; end: number } | null>(null)
  const diePickerRootRef = useRef<HTMLDivElement | null>(null)
  const operationTypeSelector = (props.operation_type_selector || {}) as OperationTypeSelector
  const calculationSelector = (props.parameters_calculation_mode_selector || {}) as ParametersCalculationModeSelector
  const operationTree = asSelectorNodes(operationTypeSelector.tree)
  const calculationTree = asSelectorNodes(calculationSelector.tree)
  const calculationPath = calculationSelector.target_path || 'target.parameters_calculation_mode'

  const operationPath = useMemo(() => {
    if (operationPathIds.length > 0) {
      let currentColumn = operationTree
      const path: SelectorNode[] = []
      for (const id of operationPathIds) {
        const node = currentColumn.find((entry) => entry.id === id)
        if (!node) {
          break
        }
        path.push(node)
        currentColumn = asSelectorNodes(node.children)
      }
      return path
    }
    return hasSelectedOperationType ? findPathByTemplateId(operationTree, currentTemplateId) : []
  }, [currentTemplateId, hasSelectedOperationType, operationPathIds, operationTree])
  const savedOperationPath = useMemo(
    () => hasSavedOperationType ? findPathByTemplateId(operationTree, baselineTemplateId) : [],
    [baselineTemplateId, hasSavedOperationType, operationTree]
  )

  const calculationValue = normalizeValue(getNestedValue(props, calculationPath) ?? calculationSelector.default ?? 'manual')
  const calculationPathNodes = useMemo(
    () => findPathByValue(calculationTree, calculationValue),
    [calculationTree, calculationValue]
  )
  const calculationModeDefault = normalizeValue(calculationSelector.default ?? 'manual')
  const calculationModeNode =
    calculationPathNodes.length > 0 ? calculationPathNodes[calculationPathNodes.length - 1] : undefined
  const calculationModeLabel = normalizeValue(
    calculationModeNode?.label ?? calculationModeNode?.value ?? calculationValue
  )
  const titleCalculationMode =
    calculationValue && calculationValue !== calculationModeDefault
      ? calculationValue === 'optimization'
        ? 'OPT'
        : calculationModeLabel.toUpperCase()
      : ''

  const operationTitle = hasSelectedOperationType
    ? template.display_name || template.label || currentTemplateId
    : 'Empty operation'
  const shouldShowOperationTypeSelector =
    !hasSavedOperationType || isOperationSelectorOpen || hasUnsavedOperationTypeChange
  const usesRoundingTable = template.input_method === 'rounding_table' || currentTemplateId === 'operation.rounding'

  useEffect(() => {
    setOperationPathIds([])
  }, [currentTemplateId])

  useEffect(() => {
    if (!isActive && hasSavedOperationType) {
      setIsOperationSelectorOpen(false)
    }
  }, [hasSavedOperationType, isActive])

  useEffect(() => {
    if (saveStatus === 'saved' && hasSavedOperationType) {
      setIsOperationSelectorOpen(false)
    }
  }, [hasSavedOperationType, saveStatus])

  useEffect(() => {
    if (block.block_type_id !== 'deformation' || libraryHasLoaded || libraryIsLoading) {
      return
    }
    void fetchLibrary()
  }, [block.block_type_id, fetchLibrary, libraryHasLoaded, libraryIsLoading])

  useEffect(() => {
    if (!openDiePopover) {
      return undefined
    }

    const handlePointerDown = (event: PointerEvent) => {
      const root = diePickerRootRef.current
      if (root && event.target instanceof Node && root.contains(event.target)) {
        return
      }
      setOpenDiePopover(null)
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpenDiePopover(null)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [openDiePopover])

  useLayoutEffect(() => {
    const selection = operationTextSelectionRef.current
    const textarea = operationTextareaRef.current
    if (!selection || !textarea || document.activeElement !== textarea) {
      return
    }

    const start = Math.min(selection.start, operationTextValue.length)
    const end = Math.min(selection.end, operationTextValue.length)
    textarea.setSelectionRange(start, end)
    operationTextSelectionRef.current = null
  }, [operationTextValue])

  const updatePath = (path: string, value: unknown) => {
    onUpdate(block.block_id, setNestedValue(props, path, value))
  }

  const updatePaths = (updates: Array<[string, unknown]>) => {
    let nextProps = props
    updates.forEach(([path, value]) => {
      nextProps = setNestedValue(nextProps, path, value)
    })
    onUpdate(block.block_id, nextProps)
  }

  const resetPath = (path: string) => {
    updatePath(path, getNestedValue(baselineProps || {}, path) ?? '')
  }

  const isPathDirty = (path: string) =>
    normalizeValue(getNestedValue(props, path)) !== normalizeValue(getNestedValue(baselineProps || {}, path))

  const renderSectionNumberingControl = () => {
    if (!sectionNumberingControl) {
      return null
    }

    return (
      <div className="doc-section-numbering-control" data-block-action-silent="true">
        <span>Start numbering:</span>
        <input
          type="number"
          min="1"
          step="1"
          value={sectionNumberingControl.value}
          onChange={(event) => sectionNumberingControl.onChange(event.target.value)}
          className={`doc-section-numbering-input ${
            sectionNumberingControl.isDirty ? 'doc-field-dirty' : ''
          }`}
          aria-label="Start section numbering at"
        />
        {sectionNumberingControl.isDirty ? (
          <Tooltip content="Revert section numbering start">
            <button
              type="button"
              onClick={sectionNumberingControl.onReset}
              className="doc-reset"
              aria-label="Revert section numbering start"
            >
              ↺
            </button>
          </Tooltip>
        ) : null}
      </div>
    )
  }

  if (block.block_type_id === 'deformation') {
    if (renderVariant === 'deformation-header') {
      return (
        <div className="doc-content doc-deformation-header-content">
          <div className="doc-section-title-row">
            <h2 className="doc-title doc-title-parent">
              {sectionNumber ? `${sectionNumber} ` : ''}
              Deformation
            </h2>
            {renderSectionNumberingControl()}
          </div>
        </div>
      )
    }

    const renderDeformationVariableField = (field: string, label: string, unit: string) => {
      const path = `${DEFORMATION_PROPERTIES}.deformation_variables.${field}`
      const value = normalizeValue(getNestedValue(props, path))
      const dirty = isPathDirty(path)

      return (
        <tr key={field} className="doc-table-row">
          <td className="doc-label">
            {label}
            <span className="ml-1 doc-muted">[{unit}]</span>
          </td>
          <td className="doc-value">
            <div className="doc-field-row">
              <input
                type="number"
                value={value}
                onChange={(event) => updatePath(path, event.target.value)}
                className={`doc-field ${dirty ? 'doc-field-dirty' : ''}`}
                step="0.001"
                placeholder={label}
              />
              {renderResetButton(() => resetPath(path), dirty)}
            </div>
          </td>
        </tr>
      )
    }

    const renderDeformationSpeedRow = ({ field, label }: { field: string; label: string }) => {
      const path = `${DEFORMATION_PROPERTIES}.${field}`
      const value = normalizeValue(getNestedValue(props, path))
      const dirty = isPathDirty(path)

      return (
        <tr key={field}>
          <td className="doc-deformation-speed-label">{label}</td>
          <td className="doc-deformation-speed-value">
            <div className="doc-field-row">
              <input
                type="number"
                value={value}
                onChange={(event) => updatePath(path, event.target.value)}
                className={`doc-field ${dirty ? 'doc-field-dirty' : ''}`}
                step="0.001"
                min="0"
                placeholder="Speed"
              />
              {renderResetButton(() => resetPath(path), dirty)}
            </div>
          </td>
        </tr>
      )
    }

    const renderDeformationFeedRow = ({ key, label }: { key: string; label: string }) => {
      const directionPath = `${DEFORMATION_PROPERTIES}.feed_settings.${key}.feed_direction_id`
      const directionValue = normalizeFeedDirectionId(getNestedValue(props, directionPath))
      const baselineDirectionValue = normalizeFeedDirectionId(getNestedValue(baselineProps || {}, directionPath))
      const directionDirty = directionValue !== baselineDirectionValue
      const feedFields = [
        { key: 'feed_first', placeholder: 'First' },
        { key: 'feed_middle', placeholder: 'Middle' },
        { key: 'feed_last', placeholder: 'Last' },
      ]

      return (
        <tr key={key}>
          <td className="doc-deformation-feed-label">{label}</td>
          <td className="doc-deformation-feed-direction">
            <div className="doc-feed-direction-group" role="radiogroup" aria-label={`${label} feed direction`}>
              {FEED_DIRECTION_OPTIONS.map((option) => {
                const isSelected = directionValue === String(option.id)
                return (
                  <button
                    key={option.id}
                    type="button"
                    className={[
                      'doc-feed-direction-button',
                      isSelected ? 'doc-feed-direction-button-active' : '',
                      directionDirty && isSelected ? 'doc-feed-direction-button-dirty' : '',
                    ].filter(Boolean).join(' ')}
                    aria-label={option.label}
                    aria-checked={isSelected}
                    role="radio"
                    onClick={() => updatePath(directionPath, option.id)}
                  >
                    {option.icon}
                  </button>
                )
              })}
            </div>
          </td>
          {feedFields.map((field) => {
            const feedPath = `${DEFORMATION_PROPERTIES}.feed_settings.${key}.${field.key}`
            const feedValue = normalizeValue(getNestedValue(props, feedPath))
            const feedDirty = isPathDirty(feedPath)
            return (
              <td key={field.key} className="doc-deformation-feed-value">
                <div className="doc-field-row">
                  <input
                    type="number"
                    value={feedValue}
                    onChange={(event) => updatePath(feedPath, event.target.value)}
                    className={`doc-field ${feedDirty ? 'doc-field-dirty' : ''}`}
                    step="0.001"
                    min="0"
                    placeholder={field.placeholder}
                  />
                  {renderResetButton(() => resetPath(feedPath), feedDirty)}
                </div>
              </td>
            )
          })}
        </tr>
      )
    }

    const visibleDeformationFeedRows = renderVariant === 'deformation-parameters'
      ? DEFORMATION_FEED_ROWS.filter((row) => deformationFeedKeys?.includes(row.key))
      : DEFORMATION_FEED_ROWS

    const renderDeformationParameterPanel = (title: string, content: ReactNode) => (
      <div className="doc-deformation-parameter-panel">
        <div className="doc-title-row doc-deformation-parameter-title-row">
          <h2 className="doc-title doc-title-child">{title}</h2>
        </div>
        <div className="doc-title-tabbed-content">{content}</div>
      </div>
    )

    const renderDieSelectorBlock = () => {
      const dieTypePath = `${DEFORMATION_PROPERTIES}.die_type_id`
      const topDieTypePath = `${DEFORMATION_PROPERTIES}.top_die_type_id`
      const bottomDieTypePath = `${DEFORMATION_PROPERTIES}.bottom_die_type_id`
      const modePath = `${DEFORMATION_PROPERTIES}.die_selection_mode`
      const assemblyPath = `${DEFORMATION_PROPERTIES}.die_assembly_id`
      const topDiePath = `${DEFORMATION_PROPERTIES}.top_die_id`
      const bottomDiePath = `${DEFORMATION_PROPERTIES}.bottom_die_id`

      const fallbackDieTypeId = dieTypes.find((entry) => dieTypeLooksFlat(entry.name))?.id ?? dieTypes[0]?.id ?? null
      const pairDieTypeId = normalizeOptionalNumberId(getNestedValue(props, dieTypePath)) ?? fallbackDieTypeId
      const topDieTypeId = normalizeOptionalNumberId(getNestedValue(props, topDieTypePath)) ?? pairDieTypeId
      const bottomDieTypeId = normalizeOptionalNumberId(getNestedValue(props, bottomDieTypePath)) ?? pairDieTypeId
      const pairDieType = dieTypes.find((entry) => entry.id === pairDieTypeId)
      const topDieType = dieTypes.find((entry) => entry.id === topDieTypeId)
      const bottomDieType = dieTypes.find((entry) => entry.id === bottomDieTypeId)
      const pairDieTypeName = formatLibraryName(pairDieType?.name)
      const topDieTypeName = formatLibraryName(topDieType?.name)
      const bottomDieTypeName = formatLibraryName(bottomDieType?.name)
      const selectionMode =
        normalizeValue(getNestedValue(props, modePath)) === DIE_SELECTION_MODE_SEPARATE
          ? DIE_SELECTION_MODE_SEPARATE
          : DIE_SELECTION_MODE_PAIR

      const diesById = new Map(dies.map((entry) => [entry.id, entry]))
      const filterDiesByType = (dieTypeId: number | null) => dies
        .filter((entry) => !entry.is_obsolete)
        .filter((entry) => dieTypeId === null || entry.die_type_id === dieTypeId)
      const sideDies = (side: 'top' | 'bottom', dieTypeId: number | null) => {
        const filteredDies = filterDiesByType(dieTypeId)
        const sideSpecific = filteredDies.filter((entry) =>
          normalizeValue(entry.classification_path).toLowerCase().includes(side)
        )
        return sideSpecific.length > 0 ? sideSpecific : filteredDies
      }
      const filteredAssemblies = dieAssemblies
        .filter((entry) => !entry.is_obsolete)
        .filter((entry) => {
          if (pairDieTypeId === null) {
            return true
          }
          const linkedDieIds = [entry.top_die_id, entry.bottom_die_id, entry.left_die_id, entry.right_die_id]
            .filter((value): value is number => typeof value === 'number')
          const linkedTypeMatch = linkedDieIds.some((dieId) => diesById.get(dieId)?.die_type_id === pairDieTypeId)
          return linkedTypeMatch || classificationMatchesType(entry.classification_path, pairDieTypeName)
        })
      const assemblyValue = normalizeValue(getNestedValue(props, assemblyPath))
      const topDieValue = normalizeValue(getNestedValue(props, topDiePath))
      const bottomDieValue = normalizeValue(getNestedValue(props, bottomDiePath))
      const selectedAssemblyName = assemblyValue
        ? formatLibraryNameOrFallback(dieAssemblies.find((entry) => String(entry.id) === assemblyValue)?.name, `#${assemblyValue}`)
        : 'None'
      const selectedTopDieName = topDieValue
        ? formatLibraryNameOrFallback(dies.find((entry) => String(entry.id) === topDieValue)?.name, `#${topDieValue}`)
        : 'None'
      const selectedBottomDieName = bottomDieValue
        ? formatLibraryNameOrFallback(dies.find((entry) => String(entry.id) === bottomDieValue)?.name, `#${bottomDieValue}`)
        : 'None'

      const setDieType = (typePath: string, selectPath: string, dieTypeId: number) => {
        updatePaths([
          [typePath, dieTypeId],
          [selectPath, ''],
        ])
        setOpenDiePopover(null)
      }
      const setMode = (mode: typeof DIE_SELECTION_MODE_PAIR | typeof DIE_SELECTION_MODE_SEPARATE) => {
        updatePath(modePath, mode)
        setOpenDiePopover(null)
      }
      const setSelectValue = (path: string, value: string) => {
        updatePath(path, value ? Number(value) : '')
        setOpenDiePopover(null)
      }

      const isDiePopoverOpen = (kind: 'type' | 'name', key: string) =>
        openDiePopover?.kind === kind && openDiePopover.key === key
      const toggleDiePopover = (kind: 'type' | 'name', key: string) => {
        setOpenDiePopover((current) =>
          current?.kind === kind && current.key === key ? null : { kind, key }
        )
      }

      const renderDieIcon = (name: unknown, mode: DieIconMode) => (
        <svg
          viewBox="0 0 128 128"
          aria-hidden="true"
          className="doc-die-icon"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {dieIconPaths(name, mode).map((pathData) => (
            <path key={pathData} d={pathData} />
          ))}
        </svg>
      )

      const renderDieTypePopover = (
        iconMode: DieIconMode,
        selectedDieTypeId: number | null,
        typePath: string,
        selectPath: string,
      ) => (
        <div className="doc-die-popover doc-die-type-popover" role="menu">
          {dieTypes.length > 0 ? (
            <div className="doc-die-type-palette">
              {dieTypes.map((entry) => {
                const selected = entry.id === selectedDieTypeId
                const dirty = selected && isPathDirty(typePath)
                const label = formatLibraryName(entry.name)
                return (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => setDieType(typePath, selectPath, entry.id)}
                    title={label}
                    aria-label={label}
                    aria-pressed={selected}
                    className={[
                      'doc-die-popover-option',
                      'doc-die-type-option',
                      selected ? 'doc-die-popover-option-selected' : '',
                      dirty ? 'doc-die-popover-option-dirty' : '',
                    ].filter(Boolean).join(' ')}
                  >
                    {renderDieIcon(entry.name, iconMode)}
                  </button>
                )
              })}
            </div>
          ) : (
            <span className="doc-muted">{libraryIsLoading ? 'Loading die types...' : 'Die types are not loaded.'}</span>
          )}
        </div>
      )

      const renderDieNamePopover = (
        selectPath: string,
        selectValue: string,
        options: Array<{ id: number; name: unknown }>,
      ) => (
        <div className="doc-die-popover doc-die-name-popover" role="listbox">
          <div className="doc-die-name-list">
            <button
              type="button"
              onClick={() => setSelectValue(selectPath, '')}
              aria-selected={!selectValue}
              className={[
                'doc-die-popover-option',
                'doc-die-name-option',
                !selectValue ? 'doc-die-popover-option-selected' : '',
              ].filter(Boolean).join(' ')}
            >
              None
            </button>
            {options.map((entry) => {
              const selected = String(entry.id) === selectValue
              return (
                <button
                  key={entry.id}
                  type="button"
                  onClick={() => setSelectValue(selectPath, String(entry.id))}
                  aria-selected={selected}
                  className={[
                    'doc-die-popover-option',
                    'doc-die-name-option',
                    selected ? 'doc-die-popover-option-selected' : '',
                  ].filter(Boolean).join(' ')}
                >
                  {formatLibraryName(entry.name)}
                </button>
              )
            })}
          </div>
        </div>
      )

      const renderDieSelectionLine = ({
        label,
        summaryPrefix,
        iconMode,
        selectedDieType,
        selectedDieTypeId,
        selectedDieTypeName,
        dieTypePath,
        selectPath,
        selectValue,
        selectedName,
        options,
      }: {
        label?: string
        summaryPrefix: string
        iconMode: DieIconMode
        selectedDieType?: { id: number; name: unknown }
        selectedDieTypeId: number | null
        selectedDieTypeName: string
        dieTypePath: string
        selectPath: string
        selectValue: string
        selectedName: string
        options: Array<{ id: number; name: unknown }>
      }) => {
        const typeOpen = isDiePopoverOpen('type', dieTypePath)
        const nameOpen = isDiePopoverOpen('name', selectPath)
        return (
          <div className="doc-die-selector-line">
            <div className="doc-die-inline-row">
              <span className="doc-die-inline-control" data-block-action-silent="true">
                <button
                  type="button"
                  onClick={() => toggleDiePopover('type', dieTypePath)}
                  aria-label={label ? `${label} die type` : 'Die assembly type'}
                  aria-expanded={typeOpen}
                  title={selectedDieTypeName || 'Die type'}
                  className={[
                    'doc-die-inline-button',
                    'doc-die-type-trigger',
                    typeOpen ? 'doc-die-inline-button-open' : '',
                    isPathDirty(dieTypePath) ? 'doc-die-inline-button-dirty' : '',
                  ].filter(Boolean).join(' ')}
                >
                  {renderDieIcon(selectedDieType?.name, iconMode)}
                </button>
                {typeOpen ? renderDieTypePopover(iconMode, selectedDieTypeId, dieTypePath, selectPath) : null}
              </span>
              <span className="doc-die-static-text">
                {summaryPrefix} {selectedDieTypeName || 'Flat'}
              </span>
              <span className="doc-die-inline-control doc-die-name-control" data-block-action-silent="true">
                <button
                  type="button"
                  onClick={() => toggleDiePopover('name', selectPath)}
                  aria-label={label ? `${label} die` : 'Die assembly'}
                  aria-expanded={nameOpen}
                  title={selectedName}
                  className={[
                    'doc-die-inline-button',
                    'doc-die-name-trigger',
                    nameOpen ? 'doc-die-inline-button-open' : '',
                    isPathDirty(selectPath) ? 'doc-die-inline-button-dirty' : '',
                  ].filter(Boolean).join(' ')}
                >
                  {selectedName}
                </button>
                {nameOpen ? renderDieNamePopover(selectPath, selectValue, options) : null}
              </span>
            </div>
          </div>
        )
      }

      return (
        <div className="doc-deformation-dies-panel" ref={diePickerRootRef}>
          <div className="doc-title-row doc-die-title-row">
            <h2 className="doc-title doc-title-child">Dies</h2>
            <div className="doc-title-mode-controls doc-die-mode-controls doc-segmented-control" aria-label="Die selection mode">
              <button
                type="button"
                onClick={() => setMode(DIE_SELECTION_MODE_PAIR)}
                className={[
                  'doc-segmented-button',
                  selectionMode === DIE_SELECTION_MODE_PAIR ? 'doc-segmented-button-active' : '',
                  selectionMode === DIE_SELECTION_MODE_PAIR && isPathDirty(modePath) ? 'doc-segmented-button-dirty' : '',
                ].filter(Boolean).join(' ')}
              >
                Pair
              </button>
              <button
                type="button"
                onClick={() => setMode(DIE_SELECTION_MODE_SEPARATE)}
                className={[
                  'doc-segmented-button',
                  selectionMode === DIE_SELECTION_MODE_SEPARATE ? 'doc-segmented-button-active' : '',
                  selectionMode === DIE_SELECTION_MODE_SEPARATE && isPathDirty(modePath) ? 'doc-segmented-button-dirty' : '',
                ].filter(Boolean).join(' ')}
              >
                Separate
              </button>
            </div>
          </div>

          <div className="doc-title-tabbed-content">
            {selectionMode === DIE_SELECTION_MODE_PAIR ? (
              renderDieSelectionLine({
                summaryPrefix: 'Pair of',
                iconMode: 'assembly',
                selectedDieType: pairDieType,
                selectedDieTypeId: pairDieTypeId,
                selectedDieTypeName: pairDieTypeName,
                dieTypePath,
                selectPath: assemblyPath,
                selectValue: assemblyValue,
                selectedName: selectedAssemblyName,
                options: filteredAssemblies,
              })
            ) : (
              <div className="doc-die-selector-lines">
                {renderDieSelectionLine({
                  label: 'Top',
                  summaryPrefix: 'Top',
                  iconMode: 'top',
                  selectedDieType: topDieType,
                  selectedDieTypeId: topDieTypeId,
                  selectedDieTypeName: topDieTypeName,
                  dieTypePath: topDieTypePath,
                  selectPath: topDiePath,
                  selectValue: topDieValue,
                  selectedName: selectedTopDieName,
                  options: sideDies('top', topDieTypeId),
                })}
                {renderDieSelectionLine({
                  label: 'Bottom',
                  summaryPrefix: 'Bottom',
                  iconMode: 'bottom',
                  selectedDieType: bottomDieType,
                  selectedDieTypeId: bottomDieTypeId,
                  selectedDieTypeName: bottomDieTypeName,
                  dieTypePath: bottomDieTypePath,
                  selectPath: bottomDiePath,
                  selectValue: bottomDieValue,
                  selectedName: selectedBottomDieName,
                  options: sideDies('bottom', bottomDieTypeId),
                })}
              </div>
            )}
          </div>
        </div>
      )
    }

    if (renderVariant === 'deformation-dies') {
      return (
        <div className="doc-content">
          {renderDieSelectorBlock()}
        </div>
      )
    }

    return (
      <div className="doc-content">
        {renderVariant === 'deformation-parameters' ? null : (
          <div className="doc-section-title-row">
            <h2 className="doc-title doc-title-parent">
              {sectionNumber ? `${sectionNumber} ` : ''}
              Deformation
            </h2>
            {renderSectionNumberingControl()}
          </div>
        )}
        <div className={renderVariant === 'deformation-parameters' ? 'doc-deformation-parameter-panels' : undefined}>
          {renderDeformationParameterPanel(
            'Speed',
            <table className="doc-operation-table doc-deformation-speed-table">
              <thead>
                <tr>
                  <th aria-label="Operation family" />
                  <th>Speed, mm/s</th>
                </tr>
              </thead>
              <tbody>
                {DEFORMATION_SPEED_FIELDS.map(renderDeformationSpeedRow)}
              </tbody>
            </table>,
          )}
          {visibleDeformationFeedRows.length > 0 ? renderDeformationParameterPanel(
            'Feed',
            <table className="doc-operation-table doc-deformation-feed-table">
              <thead>
                <tr>
                  <th>Operation</th>
                  <th>Direction</th>
                  <th>First, mm</th>
                  <th>Middle, mm</th>
                  <th>Last, mm</th>
                </tr>
              </thead>
              <tbody>
                {visibleDeformationFeedRows.map(renderDeformationFeedRow)}
              </tbody>
            </table>,
          ) : null}
          {renderDeformationParameterPanel(
            'Other parameters',
            <table className="doc-table doc-deformation-other-parameters-table">
              <tbody>
                {renderDeformationVariableField('tail_chamfering_stroke', 'Tail chamfering stroke', 'mm')}
                {renderDeformationVariableField('tail_flattening_stroke', 'Tail flattening stroke', 'mm')}
              </tbody>
            </table>,
          )}
        </div>
      </div>
    )
  }

  if (block.block_type_id === HEATING_BLOCK_TYPE_ID) {
    return (
      <div className="doc-content">
        <div className="doc-section-title-row">
          <h2 className="doc-title doc-title-parent">
            {sectionNumber ? `${sectionNumber} ` : ''}
            Heating
          </h2>
          {renderSectionNumberingControl()}
        </div>
      </div>
    )
  }

  if (block.block_type_id === FURNACE_BLOCK_TYPE_ID) {
    const furnaceRows = normalizeFurnaceProgramRows(getNestedValue(props, FURNACE_PROGRAM_PATH) ?? props.temperature_program)
    const baselineFurnaceRows = normalizeFurnaceProgramRows(
      getNestedValue(baselineProps || {}, FURNACE_PROGRAM_PATH) ?? baselineProps?.temperature_program
    )
    const legacyTemperatureValue = normalizeValue(getNestedValue(props, `${FURNACE_PROPERTIES}.temperature`) ?? props.temperature)
    const baselineLegacyTemperatureValue = normalizeValue(
      getNestedValue(baselineProps || {}, `${FURNACE_PROPERTIES}.temperature`) ?? baselineProps?.temperature
    )
    const displayRows = furnaceRowsForDisplay(furnaceRows, legacyTemperatureValue)
    const baselineDisplayRows = furnaceRowsForDisplay(baselineFurnaceRows, baselineLegacyTemperatureValue)
    const programDirty = stringifyJson(displayRows) !== stringifyJson(baselineDisplayRows)

    const updateFurnaceProgramRows = (nextRows: FurnaceProgramRow[]) => {
      const normalizedRows = furnaceRowsForDisplay(nextRows)
      const compatibilityTemperature = lastHoldTemperature(normalizedRows)
      const nextPropsWithRows = setNestedValue(props, FURNACE_PROGRAM_PATH, normalizedRows)
      const nextPropsWithTemperature = setNestedValue(
        nextPropsWithRows,
        `${FURNACE_PROPERTIES}.temperature`,
        compatibilityTemperature,
      )
      onUpdate(block.block_id, {
        ...nextPropsWithTemperature,
        temperature_program: normalizedRows,
        temperature: compatibilityTemperature,
      })
    }

    const updateProgramCell = (rowIndex: number, key: keyof FurnaceProgramRow, value: string) => {
      const nextRows = displayRows.map((row) => ({ ...row }))
      nextRows[rowIndex] = {
        ...nextRows[rowIndex],
        [key]: value,
      }
      updateFurnaceProgramRows(nextRows)
    }

    const updateProgramType = (rowIndex: number, type: FurnaceProgramRowType) => {
      const nextRows = displayRows.map((row) => ({ ...row }))
      nextRows[rowIndex] = {
        type,
        duration_min: type === 'hold' ? normalizeValue(nextRows[rowIndex]?.duration_min) : '',
        temperature_c: type === 'hold' ? normalizeValue(nextRows[rowIndex]?.temperature_c) : '',
      }
      updateFurnaceProgramRows(nextRows)
    }

    const insertProgramRow = (rowIndex: number, offset: 0 | 1) => {
      const nextRows = displayRows.map((row) => ({ ...row }))
      nextRows.splice(rowIndex + offset, 0, emptyFurnaceProgramRow())
      updateFurnaceProgramRows(nextRows)
    }

    const removeProgramRow = (rowIndex: number) => {
      const nextRows = displayRows.filter((_, index) => index !== rowIndex)
      updateFurnaceProgramRows(nextRows.length > 0 ? nextRows : [emptyFurnaceProgramRow()])
    }

    const diagram = buildFurnaceProgramDiagram(displayRows)

    const renderFurnaceDiagram = () => (
      <div className="doc-furnace-diagram-wrap">
        <svg
          className="doc-furnace-diagram"
          width={diagram.width}
          height={diagram.height}
          viewBox={`0 0 ${diagram.width} ${diagram.height}`}
          role="img"
          aria-label="Furnace temperature program diagram"
        >
          <line className="doc-furnace-axis" x1={diagram.yAxisX} y1={diagram.axisY} x2={diagram.width - 12} y2={diagram.axisY} />
          <line className="doc-furnace-axis" x1={diagram.yAxisX} y1={diagram.axisY} x2={diagram.yAxisX} y2={FURNACE_PROGRAM_CHART_TOP - 12} />
          {diagram.marks.map((mark, markIndex) => (
            <line
              key={`guide-${markIndex}`}
              className="doc-furnace-guide"
              x1={mark.x}
              y1={mark.y}
              x2={mark.x}
              y2={diagram.axisY}
            />
          ))}
          {diagram.segments.map((segment, segmentIndex) => (
            <line
              key={`segment-${segmentIndex}`}
              className={`doc-furnace-line doc-furnace-line-${segment.type}`}
              x1={segment.startX}
              y1={segment.startY}
              x2={segment.endX}
              y2={segment.endY}
            />
          ))}
          {diagram.marks.map((mark, markIndex) => (
            <circle key={`mark-${markIndex}`} className="doc-furnace-mark" cx={mark.x} cy={mark.y} r="5.8" />
          ))}
          {diagram.marks.map((mark, markIndex) => (
            mark.temperatureLabel ? (
              <text key={`temp-${markIndex}`} className="doc-furnace-temp-label" x={mark.x} y={mark.y - 12}>
                {mark.temperatureLabel}
              </text>
            ) : null
          ))}
          {diagram.segments.map((segment, segmentIndex) => (
            segment.durationLabel ? (
              <text
                key={`duration-${segmentIndex}`}
                className="doc-furnace-duration-label"
                x={(segment.startX + segment.endX) / 2}
                y={diagram.axisY - 26}
              >
                {segment.durationLabel}
              </text>
            ) : null
          ))}
        </svg>
      </div>
    )

    const renderFurnaceTable = () => (
      <div className="doc-field-row">
        <div className="doc-operation-table-wrap">
          <table className="doc-operation-table doc-furnace-program-table">
            <colgroup>
              <col className="doc-operation-pass-col" />
              <col className="doc-furnace-type-col" />
              <col className="doc-furnace-duration-col" />
              <col className="doc-furnace-temperature-col" />
              <col className="doc-operation-actions-col" />
            </colgroup>
            <thead>
              <tr>
                <th>Number</th>
                <th>Type</th>
                <th>Duration, min</th>
                <th>Temperature, C</th>
                <th className="doc-operation-actions-header" aria-label="Row actions" />
              </tr>
            </thead>
            <tbody>
              {displayRows.map((row, rowIndex) => {
                const rowType = row.type ?? 'hold'
                const baselineRow = baselineDisplayRows[rowIndex] ?? emptyFurnaceProgramRow()
                const typeDirty = rowType !== (baselineRow.type ?? 'hold')
                const durationDirty = normalizeValue(row.duration_min) !== normalizeValue(baselineRow.duration_min)
                const temperatureDirty = normalizeValue(row.temperature_c) !== normalizeValue(baselineRow.temperature_c)
                return (
                  <tr key={rowIndex}>
                    <td className="doc-operation-pass">{rowIndex + 1}</td>
                    <td>
                      <div className="doc-furnace-type-buttons">
                        {FURNACE_PROGRAM_TYPES.map((entry) => (
                          <button
                            key={entry.type}
                            type="button"
                            onClick={() => updateProgramType(rowIndex, entry.type)}
                            className={[
                              'doc-furnace-type-button',
                              rowType === entry.type ? 'doc-furnace-type-button-active' : '',
                              rowType === entry.type && typeDirty ? 'doc-furnace-type-button-dirty' : '',
                            ].filter(Boolean).join(' ')}
                            aria-label={entry.label}
                            title={entry.label}
                          >
                            {entry.icon}
                          </button>
                        ))}
                      </div>
                    </td>
                    <td>
                      {rowType === 'hold' ? (
                        <input
                          type="text"
                          value={normalizeValue(row.duration_min)}
                          onChange={(event) => updateProgramCell(rowIndex, 'duration_min', event.target.value)}
                          className={`doc-field ${durationDirty ? 'doc-field-dirty' : ''}`}
                        />
                      ) : (
                        <div className="doc-furnace-readonly-cell">
                          {rowType === 'heat' ? 'Heat up' : 'Unload billet'}
                        </div>
                      )}
                    </td>
                    <td>
                      {rowType === 'hold' ? (
                        <input
                          type="text"
                          value={normalizeValue(row.temperature_c)}
                          onChange={(event) => updateProgramCell(rowIndex, 'temperature_c', event.target.value)}
                          className={`doc-field ${temperatureDirty ? 'doc-field-dirty' : ''}`}
                        />
                      ) : (
                        <div className="doc-furnace-readonly-cell" aria-label="No direct temperature value" />
                      )}
                    </td>
                    <td className="doc-operation-actions-cell">
                      <div className="doc-table-actions">
                        <button type="button" onClick={() => insertProgramRow(rowIndex, 0)} aria-label="Insert row above">
                          ↑+
                        </button>
                        <button type="button" onClick={() => insertProgramRow(rowIndex, 1)} aria-label="Insert row below">
                          ↓+
                        </button>
                        <button type="button" onClick={() => removeProgramRow(rowIndex)} aria-label="Remove row">
                          ×
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {renderResetButton(() => updateFurnaceProgramRows(baselineDisplayRows), programDirty)}
      </div>
    )

    return (
      <div className="doc-content">
        <div className="doc-title-row">
          <h2 className="doc-title doc-title-child">
            {sectionNumber ? `${sectionNumber} ` : ''}
            Furnace
          </h2>
          <div className="doc-title-mode-controls doc-furnace-switch doc-segmented-control" aria-label="Furnace program display mode">
            <button
              type="button"
              onClick={() => setFurnaceProgramView('diagram')}
              className={[
                'doc-segmented-button',
                furnaceProgramView === 'diagram' ? 'doc-segmented-button-active' : '',
              ].filter(Boolean).join(' ')}
            >
              Diagram
            </button>
            <button
              type="button"
              onClick={() => setFurnaceProgramView('table')}
              className={[
                'doc-segmented-button',
                furnaceProgramView === 'table' ? 'doc-segmented-button-active' : '',
              ].filter(Boolean).join(' ')}
            >
              Table
            </button>
          </div>
        </div>
        <section className="doc-section doc-furnace-program-section">
          {furnaceProgramView === 'diagram' ? renderFurnaceDiagram() : renderFurnaceTable()}
        </section>
      </div>
    )
  }

  const selectOperationTemplate = (templateId: string) => {
    const nextTemplate = availableTemplates.find((entry) => entry.id === templateId)
    if (!nextTemplate) {
      return
    }

    const nextTarget = buildTargetDefaults(nextTemplate, calculationSelector, props.target)
    const nextRoundingTable =
      nextTemplate.input_method === 'rounding_table' && roundingRows.length === 0
        ? [emptyRoundingRow()]
        : roundingRows
    onUpdate(block.block_id, {
      ...props,
      operation_template_id: nextTemplate.id,
      operation_template_version: nextTemplate.version,
      operation_kind: nextTemplate.operation_kind,
      rounding_table: nextRoundingTable,
      target: nextTarget,
      template_snapshot: nextTemplate,
      operation_template: nextTemplate,
      title: nextTemplate.display_name || nextTemplate.label || nextTemplate.id,
    })
    setOperationPathIds(findPathByTemplateId(operationTree, templateId).map((node) => node.id))
  }

  const renderSelectorRow = (
    columns: SelectorNode[][],
    selectedPathIds: string[],
    onSelect: (node: SelectorNode, depth: number) => void,
    wrap = false,
    isDirty = false,
    savedPathIds: string[] = [],
    compact = false
  ) => (
    <div
      className={
        compact
          ? `doc-segmented-control ${wrap ? 'flex-wrap' : ''}`
          : `flex items-center gap-1 pb-1 ${wrap ? 'flex-wrap' : 'overflow-x-auto'}`
      }
    >
      {columns.map((column, depth) => (
        <div key={`row-${depth}`} className={`flex items-center ${compact ? 'gap-0' : 'gap-1'} ${wrap ? 'flex-wrap' : 'shrink-0'}`}>
          {depth > 0 ? <span className="doc-muted px-1">/</span> : null}
          {column.map((node) => {
            const selected = selectedPathIds[depth] === node.id
            const saved = savedPathIds[depth] === node.id
            return (
              <button
                key={node.id}
                type="button"
                onClick={() => onSelect(node, depth)}
                className={[
                  compact ? 'doc-segmented-button' : 'doc-selector-button',
                  !compact && saved && !selected ? 'doc-selector-button-saved' : '',
                  selected ? (compact ? 'doc-segmented-button-active' : 'doc-selector-button-selected') : '',
                  selected && isDirty ? (compact ? 'doc-segmented-button-dirty' : 'doc-selector-button-dirty') : '',
                ].filter(Boolean).join(' ')}
              >
                {node.label || node.id}
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )

  const renderOperationTypeArea = () => {
    return (
      <section className="doc-section mt-0">
        {operationTree.length === 0 ? (
          <div className="doc-readonly">Operation type selector is not defined.</div>
        ) : (
          renderSelectorRow(
            getColumns(operationTree, operationPath),
            operationPath.map((node) => node.id),
            (node, depth) => {
              const children = asSelectorNodes(node.children)
              setOperationPathIds([...operationPath.slice(0, depth).map((entry) => entry.id), node.id])
              if (children.length === 0 && node.template_id) {
                selectOperationTemplate(node.template_id)
              }
            },
            true,
            hasUnsavedOperationTypeChange,
            savedOperationPath.map((node) => node.id)
          )
        )}
      </section>
    )
  }

  const renderCalculationModeSelector = () => {
    if (calculationTree.length === 0) {
      return null
    }

    return (
      <div
        className="doc-title-mode-controls"
        onClick={(event) => event.stopPropagation()}
        onDoubleClick={(event) => event.stopPropagation()}
      >
        {renderSelectorRow(
          getColumns(calculationTree, calculationPathNodes),
          calculationPathNodes.map((node) => node.id),
          (node) => {
            const value = asSelectorNodes(node.children).length > 0 ? findFirstLeafValue(node) : node.value
            updatePath(calculationPath, value ?? calculationSelector.default ?? 'manual')
          },
          false,
          isPathDirty(calculationPath),
          [],
          true
        )}
      </div>
    )
  }

  const renderOperationTextArea = () => {
    const dirty =
      operationTextValue !== normalizeValue(getNestedValue(baselineProps || {}, operationTextPath) ?? baselineProps?.operation_text)
    const rowCount = Math.max(1, operationTextValue.split(/\r\n|\r|\n/).length)

    return (
      <section className="doc-section">
        <div className="doc-field-row">
          <textarea
            ref={operationTextareaRef}
            value={operationTextValue}
            onChange={(event) => {
              const normalized = normalizeRightArrowsWithSelection(
                event.target.value,
                event.target.selectionStart,
                event.target.selectionEnd,
              )
              operationTextSelectionRef.current = {
                start: normalized.selectionStart,
                end: normalized.selectionEnd,
              }
              updatePath(operationTextPath, normalized.value)
            }}
            className={`doc-textarea ${dirty ? 'doc-field-dirty' : ''}`}
            placeholder={`Use ${STANDARD_RIGHT_ARROW} between operations. Line breaks and spacing are visual only.`}
            rows={rowCount}
          />
          {renderResetButton(
            () => updatePath(operationTextPath, getNestedValue(baselineProps || {}, operationTextPath) ?? baselineProps?.operation_text ?? ''),
            dirty
          )}
        </div>
      </section>
    )
  }

  const renderRoundingTable = () => {
    const displayRows = rowsForDisplay(roundingRows)
    const baselineDisplayRows = rowsForDisplay(baselineRoundingRows)
    const columnWidths = ROUNDING_TABLE_COLUMNS.map((column) =>
      Math.max(
        column.minChars,
        maxVisualLineLength(column.label) + 1,
        Math.max(1, ...displayRows.map((row) => normalizeValue(row[column.key]).length)) + 2,
      )
    )
    const dirty = stringifyJson(roundingRows) !== stringifyJson(baselineRoundingRows)

    const updateRows = (nextRows: RoundingTableRow[]) => {
      updatePath(ROUNDING_TABLE_PATH, rowsForDisplay(nextRows))
    }

    const updateCell = (rowIndex: number, key: keyof RoundingTableRow, value: string) => {
      const nextRows = displayRows.map((row) => ({ ...row }))
      nextRows[rowIndex] = {
        ...nextRows[rowIndex],
        [key]: value,
      }
      updateRows(nextRows)
    }

    const insertRow = (rowIndex: number, offset: 0 | 1) => {
      const nextRows = displayRows.map((row) => ({ ...row }))
      nextRows.splice(rowIndex + offset, 0, emptyRoundingRow())
      updateRows(nextRows)
    }

    const removeRow = (rowIndex: number) => {
      const nextRows = displayRows.filter((_, index) => index !== rowIndex)
      updateRows(nextRows.length > 0 ? nextRows : [emptyRoundingRow()])
    }

    return (
      <section className="doc-section">
        <div className="doc-field-row">
          <div className="doc-operation-table-wrap">
            <table className="doc-operation-table">
              <colgroup>
                <col className="doc-operation-pass-col" />
                {ROUNDING_TABLE_COLUMNS.map((column, columnIndex) => (
                  <col key={column.key} style={{ width: `${columnWidths[columnIndex]}ch` }} />
                ))}
                <col className="doc-operation-actions-col" />
              </colgroup>
              <thead>
                <tr>
                  <th>Pass</th>
                  {ROUNDING_TABLE_COLUMNS.map((column) => (
                    <th key={column.key}>{column.label}</th>
                  ))}
                  <th className="doc-operation-actions-header" aria-label="Row actions" />
                </tr>
              </thead>
              <tbody>
                {displayRows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    <td className="doc-operation-pass">{rowIndex + 1}</td>
                    {ROUNDING_TABLE_COLUMNS.map((column) => (
                      <td key={column.key}>
                        <input
                          type="text"
                          value={normalizeValue(row[column.key])}
                          onChange={(event) => updateCell(rowIndex, column.key, event.target.value)}
                          className={`doc-field ${
                            normalizeValue(row[column.key]) !== normalizeValue(baselineDisplayRows[rowIndex]?.[column.key])
                              ? 'doc-field-dirty'
                              : ''
                          }`}
                        />
                      </td>
                    ))}
                    <td className="doc-operation-actions-cell">
                      <div className="doc-table-actions">
                        <button type="button" onClick={() => insertRow(rowIndex, 0)} aria-label="Insert row above">
                          ↑+
                        </button>
                        <button type="button" onClick={() => insertRow(rowIndex, 1)} aria-label="Insert row below">
                          ↓+
                        </button>
                        <button type="button" onClick={() => removeRow(rowIndex)} aria-label="Remove row">
                          ×
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {renderResetButton(() => updatePath(ROUNDING_TABLE_PATH, baselineRoundingRows), dirty)}
        </div>
      </section>
    )
  }

  const renderTemplateField = (field: OperationTemplateField) => {
    const path = field.path
    if (path === calculationPath) {
      return null
    }
    const label = field.label || path
    const currentValue = normalizeValue(getNestedValue(props, path))
    const dirty = isPathDirty(path)
    const options = field.options || []
    const inputType = field.type === 'decimal' || field.type === 'integer' ? 'number' : 'text'

    return (
      <tr key={path} className="doc-table-row">
        <td className="doc-label">
          {label}
          {field.unit ? <span className="ml-1 doc-muted">[{field.unit}]</span> : null}
        </td>
        <td className="doc-value">
          <div className="doc-field-row">
            {options.length > 0 ? (
              <select
                value={currentValue}
                onChange={(event) => updatePath(path, event.target.value)}
                className={`doc-select ${dirty ? 'doc-field-dirty' : ''}`}
              >
                {options.map((option) => (
                  <option key={normalizeValue(option.value)} value={normalizeValue(option.value)}>
                    {normalizeValue(option.label || option.value)}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={inputType}
                value={currentValue}
                onChange={(event) => updatePath(path, event.target.value)}
                className={`doc-field ${dirty ? 'doc-field-dirty' : ''}`}
                placeholder={label}
                step={field.type === 'integer' ? 1 : undefined}
              />
            )}
            {renderResetButton(() => resetPath(path), dirty)}
          </div>
        </td>
      </tr>
    )
  }

  const renderedTemplateFields = targetSchema.map(renderTemplateField).filter(Boolean)

  return (
    <div className="doc-content">
      <div className="doc-title-row">
        <h2
          className="doc-title doc-title-child cursor-pointer select-none"
          onDoubleClick={(event) => {
            event.stopPropagation()
            setIsOperationSelectorOpen(true)
          }}
        >
          {sectionNumber ? `${sectionNumber} ` : ''}
          {operationTitle}
          {titleCalculationMode ? (
            <span className="doc-title-mode-label">{titleCalculationMode}</span>
          ) : null}
        </h2>
        {renderCalculationModeSelector()}
      </div>

      <div className="doc-title-tabbed-content">
        {shouldShowOperationTypeSelector ? renderOperationTypeArea() : null}
        {hasSelectedOperationType ? (usesRoundingTable ? renderRoundingTable() : renderOperationTextArea()) : null}

        {hasSelectedOperationType && renderedTemplateFields.length > 0 ? (
          <section className="doc-section">
            <table className="doc-table">
              <tbody>{renderedTemplateFields}</tbody>
            </table>
          </section>
        ) : null}
      </div>
    </div>
  )
}
