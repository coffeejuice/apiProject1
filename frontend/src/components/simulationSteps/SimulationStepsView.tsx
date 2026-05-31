import { useEffect, useMemo, useState } from 'react'

import { apiClient } from '../../lib/apiClient'
import type {
  DocumentPreprocessQueueResponse,
  DocumentSimulationStepListResponse,
  DocumentSimulationStepRecord,
  DocumentSimulationStepSurfaceResponse,
  LogRelatedResponse,
  RelatedLogRecord,
  SimulationStepDiagnosticsRecord,
  SimulationStepRecord,
  SimulationStepStatusRecord,
  SimulationStepSurfaceMesh,
} from '../../types/api'
import type { BlockData } from '../blocks/BlockRegistry'
import SurfaceMeshThreeView, { type SurfaceMeshLayer } from './SurfaceMeshThreeView'

interface SimulationStepsViewProps {
  documentId: string | null
  isStepListVisible?: boolean
  activeBlockId?: string | null
  hoveredBlockId?: string | null
  onOpenPreLogs?: (query: string) => void
  onOpenSourceBlock?: (blockId: string) => void
}

const DOCUMENT_BLOCK_TYPE_ID = 'document'
const HEATING_BLOCK_TYPE_ID = 'heating'
const DEFORMATION_BLOCK_TYPE_ID = 'deformation'
const FURNACE_BLOCK_TYPE_ID = 'furnace'
const OPERATION_BLOCK_TYPE_ID = 'operation'

interface StepVisualSection {
  block: BlockData
  children: BlockData[]
}

type StepListItem =
  | { kind: 'section'; block: BlockData; title: string; number: string | null; relatedBlockIds: string[] }
  | { kind: 'source'; block: BlockData; title: string; number: string | null; relatedBlockIds: string[] }
  | { kind: 'step'; step: SimulationStepViewRecord }

type SimulationStepViewRecord = SimulationStepRecord & {
  simulation_step: SimulationStepRecord
  diagnostics: SimulationStepDiagnosticsRecord
  simulation_step_status?: SimulationStepStatusRecord | null
}

function toStepViewRecord(record: DocumentSimulationStepRecord): SimulationStepViewRecord {
  const simulationStep = record.simulation_step
  const normalizedStep: SimulationStepRecord = {
    ...simulationStep,
    pre_input: simulationStep.pre_input || simulationStep.control_parameters || {},
    pre_output: simulationStep.pre_output || simulationStep.step_specific_parameters || {},
    calculations: simulationStep.calculations || simulationStep.metrics || {},
  }
  const simulationStepStatus = record.simulation_step_status || null
  return {
    ...normalizedStep,
    simulation_step: normalizedStep,
    diagnostics: record.diagnostics || {
      response_sources: {},
      related_log_query: {},
      api_messages: [],
    },
    simulation_step_status: simulationStepStatus,
  }
}

export type MeshViewMode = 'overlay' | 'side_by_side'
type StepIssueSeverity = 'info' | 'warning' | 'error' | 'blocked'
type StepIssueKind = 'pre' | 'artifact' | 'status' | 'readiness' | 'diagnostic'

interface StepIssue {
  severity: StepIssueSeverity
  kind: StepIssueKind
  title: string
  message: string
  sourceBlockId?: string | null
  raw?: unknown
}

interface StepIssueSummary {
  preErrors: number
  missingArtifacts: number
  warnings: number
  blocked: number
}

type Vector3 = [number, number, number]

interface GeometryBasis {
  origin?: Vector3
  ox?: Vector3
  oy?: Vector3
  oz?: Vector3
}

interface GeometryMarker {
  point?: Vector3
  label?: string
}

export interface GeometrySummary {
  shape?: string
  width?: number
  height?: number
  length?: number
  diameter?: number
  volume?: number
  area?: number
  outline: Array<[number, number]>
  basis?: GeometryBasis | null
  topMarker?: GeometryMarker | null
}

type GeometryKind = 'initial' | 'final'

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M15.8 7.4a6.2 6.2 0 0 0-11.4-1M4.2 3.4v3.2h3.2M4.2 12.6a6.2 6.2 0 0 0 11.4 1M15.8 16.6v-3.2h-3.2"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/\.?0+$/, '')
  }
  if (typeof value === 'boolean') {
    return value ? 'yes' : 'no'
  }
  return String(value)
}

const GEOMETRY_VIEW_FONT_FAMILY = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace"
const GEOMETRY_VIEW_TITLE_CLASS = 'font-mono text-[10px] font-semibold leading-tight text-[rgba(55,53,47,0.78)]'
const GEOMETRY_VIEW_NOTE_CLASS = 'font-mono text-[10px] leading-tight text-[rgba(55,53,47,0.48)]'
const METRIC_TABLE_CHAR_WIDTH_PX = 6
const METRIC_TABLE_CELL_PADDING_X_PX = 8
const METRIC_TABLE_MIN_COLUMN_WIDTH_PX = 30
const METRIC_TABLE_WRAPPER_PADDING_X_PX = 10

type MetricFormat = 'default' | 'length' | 'area' | 'volume' | 'log_strain' | 'percent'

interface ComparisonMetric {
  label: string
  initial: unknown
  final: unknown
  format?: MetricFormat
}

function formatMetricValue(value: unknown, format: MetricFormat = 'default'): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  const numericValue = toNumber(value)
  if (numericValue === undefined) {
    return formatValue(value)
  }
  if (format === 'length') {
    return numericValue.toFixed(0)
  }
  if (format === 'area' || format === 'volume') {
    return numericValue.toFixed(0)
  }
  if (format === 'log_strain') {
    return numericValue.toFixed(3)
  }
  if (format === 'percent') {
    return numericValue.toFixed(1)
  }
  return formatValue(numericValue)
}

function inferMetricFormatFromPath(path: string): MetricFormat | undefined {
  const normalized = path.toLowerCase()
  const parts = normalized.split('.')
  const key = parts[parts.length - 1] || normalized
  if (
    key.includes('area') ||
    key.endsWith('_mm2') ||
    normalized.includes('cross_section_area')
  ) {
    return 'area'
  }
  if (
    key.includes('volume') ||
    key.endsWith('_mm3')
  ) {
    return 'volume'
  }
  if (
    key.includes('relative_deformation_percent') ||
    key.includes('relative_deformation_pct') ||
    key.endsWith('_percent') ||
    key.endsWith('_pct')
  ) {
    return 'percent'
  }
  if (
    key.includes('strain') ||
    key.includes('logarithmic_deformation') ||
    key.includes('true_deformation')
  ) {
    return 'log_strain'
  }
  if (
    key.endsWith('_mm') ||
    key.includes('length') ||
    key.includes('height') ||
    key.includes('width') ||
    key.includes('diameter') ||
    key.includes('radius') ||
    key.includes('stroke') ||
    key.includes('feed') ||
    key.includes('size')
  ) {
    return 'length'
  }
  return undefined
}

function metricColumnWidthPx(metric: ComparisonMetric): number {
  const maxLength = Math.max(
    metric.label.length,
    formatMetricValue(metric.initial, metric.format).length,
    formatMetricValue(metric.final, metric.format).length,
  )
  return Math.max(
    METRIC_TABLE_MIN_COLUMN_WIDTH_PX,
    maxLength * METRIC_TABLE_CHAR_WIDTH_PX + METRIC_TABLE_CELL_PADDING_X_PX + 2,
  )
}

function metricTableWidthPx(metrics: ComparisonMetric[]): number {
  return Math.ceil(metrics.reduce((sum, metric) => sum + metricColumnWidthPx(metric), 1))
}

function metricTableOverlayWidthPx(metrics: ComparisonMetric[]): number {
  return metricTableWidthPx(metrics) + METRIC_TABLE_WRAPPER_PADDING_X_PX
}

function MetricComparisonTable({ metrics }: { metrics: ComparisonMetric[] }) {
  const columnWidths = metrics.map(metricColumnWidthPx)
  const tableWidth = metricTableWidthPx(metrics)

  return (
    <table
      className="table-fixed border-collapse font-mono text-[10px] leading-[12px] text-[rgba(55,53,47,0.68)]"
      style={{ width: tableWidth }}
    >
      <colgroup>
        {columnWidths.map((width, index) => (
          <col key={`${metrics[index]?.label ?? 'metric'}-${index}`} style={{ width }} />
        ))}
      </colgroup>
      <thead>
        <tr>
          {metrics.map((metric) => (
            <th
              key={metric.label}
              className="whitespace-nowrap border border-[rgba(55,53,47,0.16)] bg-white/70 px-[4px] py-[2px] text-center font-semibold text-[rgba(55,53,47,0.78)]"
            >
              {metric.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        <tr>
          {metrics.map((metric) => (
            <td
              key={metric.label}
              className="whitespace-nowrap border border-[rgba(55,53,47,0.14)] bg-white/45 px-[4px] py-[2px] text-right tabular-nums text-slate-700"
            >
              {formatMetricValue(metric.initial, metric.format)}
            </td>
          ))}
        </tr>
        <tr>
          {metrics.map((metric) => (
            <td
              key={metric.label}
              className="whitespace-nowrap border border-[rgba(55,53,47,0.14)] bg-white/45 px-[4px] py-[2px] text-right tabular-nums text-emerald-700"
            >
              {formatMetricValue(metric.final, metric.format)}
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  )
}

interface ScalarMetricRow {
  label: string
  value: unknown
  format?: MetricFormat
}

function scalarMetricTableWidthPx(rows: ScalarMetricRow[]): number {
  const labelLength = Math.max(1, ...rows.map((row) => row.label.length))
  const valueLength = Math.max(1, ...rows.map((row) => formatMetricValue(row.value, row.format).length))
  const labelWidth = Math.max(28, labelLength * METRIC_TABLE_CHAR_WIDTH_PX + METRIC_TABLE_CELL_PADDING_X_PX + 2)
  const valueWidth = Math.max(42, valueLength * METRIC_TABLE_CHAR_WIDTH_PX + METRIC_TABLE_CELL_PADDING_X_PX + 2)
  return Math.ceil(labelWidth + valueWidth + 1)
}

function scalarMetricTableOverlayWidthPx(rows: ScalarMetricRow[]): number {
  return scalarMetricTableWidthPx(rows) + METRIC_TABLE_WRAPPER_PADDING_X_PX
}

function scalarMetricTableOverlayHeightPx(rows: ScalarMetricRow[]): number {
  return rows.length * 17 + 10
}

function ScalarMetricTable({ rows }: { rows: ScalarMetricRow[] }) {
  const labelLength = Math.max(1, ...rows.map((row) => row.label.length))
  const valueLength = Math.max(1, ...rows.map((row) => formatMetricValue(row.value, row.format).length))
  const labelWidth = Math.max(28, labelLength * METRIC_TABLE_CHAR_WIDTH_PX + METRIC_TABLE_CELL_PADDING_X_PX + 2)
  const valueWidth = Math.max(42, valueLength * METRIC_TABLE_CHAR_WIDTH_PX + METRIC_TABLE_CELL_PADDING_X_PX + 2)

  return (
    <table
      className="table-fixed border-collapse font-mono text-[10px] leading-[12px] text-[rgba(55,53,47,0.68)]"
      style={{ width: labelWidth + valueWidth + 1 }}
    >
      <colgroup>
        <col style={{ width: labelWidth }} />
        <col style={{ width: valueWidth }} />
      </colgroup>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <th className="whitespace-nowrap border border-[rgba(55,53,47,0.16)] bg-white/70 px-[4px] py-[2px] text-center font-semibold text-[rgba(55,53,47,0.78)]">
              {row.label}
            </th>
            <td className="whitespace-nowrap border border-[rgba(55,53,47,0.14)] bg-white/45 px-[4px] py-[2px] text-right tabular-nums text-[rgba(55,53,47,0.72)]">
              {formatMetricValue(row.value, row.format)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return '-'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

function jsonCount(value: unknown): number {
  if (!value || typeof value !== 'object') {
    return 0
  }
  if (Array.isArray(value)) {
    return value.length
  }
  return Object.keys(value).length
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function blockDisplayName(block: BlockData): string {
  if (block.block_type_id === DOCUMENT_BLOCK_TYPE_ID) {
    return 'Document'
  }
  if (block.block_type_id === HEATING_BLOCK_TYPE_ID) {
    return 'Heating'
  }
  if (block.block_type_id === DEFORMATION_BLOCK_TYPE_ID) {
    return 'Deformation'
  }
  if (block.block_type_id === FURNACE_BLOCK_TYPE_ID) {
    return 'Furnace'
  }

  const props = block.props || {}
  const title = props.title
  if (typeof title === 'string' && title.trim()) {
    return title.trim()
  }
  const template = props.operation_template || props.template_snapshot
  if (template && typeof template === 'object') {
    const templateRecord = template as { display_name?: unknown; label?: unknown }
    const label = templateRecord.display_name || templateRecord.label
    if (typeof label === 'string' && label.trim()) {
      return label.trim()
    }
  }
  const operationProperties = asRecord(props.operation_properties)
  const templateId = props.operation_template_id || operationProperties.operation_template_id
  if (typeof templateId === 'string' && templateId.trim()) {
    return templateId.replace(/^operation\./, '').replace(/[._-]+/g, ' ')
  }
  return 'Operation'
}

function sectionNumberingStart(blocks: BlockData[]): number {
  const documentBlock = blocks.find((block) => block.block_type_id === DOCUMENT_BLOCK_TYPE_ID)
  const props = documentBlock?.props || {}
  const documentProperties = asRecord(props.document_properties)
  const rawValue = props.section_numbering_start ?? documentProperties.section_numbering_start
  const value = typeof rawValue === 'number' ? rawValue : Number(rawValue)
  return Number.isInteger(value) && value > 0 ? value : 2
}

function isTopLevelSection(block: BlockData): boolean {
  return block.block_type_id === HEATING_BLOCK_TYPE_ID || block.block_type_id === DEFORMATION_BLOCK_TYPE_ID
}

function isValidSectionChild(section: BlockData, child: BlockData): boolean {
  return (
    (section.block_type_id === HEATING_BLOCK_TYPE_ID && child.block_type_id === FURNACE_BLOCK_TYPE_ID) ||
    (section.block_type_id === DEFORMATION_BLOCK_TYPE_ID && child.block_type_id === OPERATION_BLOCK_TYPE_ID)
  )
}

function relatedSourceBlockIds(blocks: BlockData[], blockId: string | null | undefined): Set<string> {
  if (!blockId) {
    return new Set()
  }

  const blockIndex = blocks.findIndex((block) => block.block_id === blockId)
  if (blockIndex < 0) {
    return new Set()
  }

  const block = blocks[blockIndex]
  if (block.block_type_id === OPERATION_BLOCK_TYPE_ID || block.block_type_id === FURNACE_BLOCK_TYPE_ID) {
    return new Set([block.block_id])
  }

  if (!isTopLevelSection(block)) {
    return new Set()
  }

  const childType = block.block_type_id === HEATING_BLOCK_TYPE_ID ? FURNACE_BLOCK_TYPE_ID : OPERATION_BLOCK_TYPE_ID
  const related = new Set<string>()
  for (let index = blockIndex + 1; index < blocks.length; index += 1) {
    const candidate = blocks[index]
    if (isTopLevelSection(candidate)) {
      break
    }
    if (candidate.block_type_id === childType) {
      related.add(candidate.block_id)
    }
  }
  return related
}

function buildVisualSections(blocks: BlockData[]): StepVisualSection[] {
  const sections: StepVisualSection[] = []
  let activeSection: StepVisualSection | null = null

  for (const block of blocks) {
    if (block.block_type_id === DOCUMENT_BLOCK_TYPE_ID) {
      continue
    }

    if (isTopLevelSection(block)) {
      activeSection = { block, children: [] }
      sections.push(activeSection)
      continue
    }

    if (activeSection && isValidSectionChild(activeSection.block, block)) {
      activeSection.children.push(block)
    }
  }

  return sections
}

function buildSectionNumbers(sections: StepVisualSection[], startNumber: number): Map<string, string> {
  const numbersByBlockId = new Map<string, string>()
  let index = 0
  let currentNumber = startNumber

  while (index < sections.length) {
    const section = sections[index]
    const nextSection = sections[index + 1]
    if (
      section.block.block_type_id === HEATING_BLOCK_TYPE_ID &&
      nextSection?.block.block_type_id === DEFORMATION_BLOCK_TYPE_ID
    ) {
      numbersByBlockId.set(section.block.block_id, `${currentNumber}.1`)
      numbersByBlockId.set(nextSection.block.block_id, `${currentNumber}.2`)
      currentNumber += 1
      index += 2
      continue
    }

    numbersByBlockId.set(section.block.block_id, `${currentNumber}.`)
    currentNumber += 1
    index += 1
  }

  return numbersByBlockId
}

function flattenUserParameters(
  value: unknown,
  prefix = '',
  output: string[] = [],
  limit = 5
): string[] {
  if (output.length >= limit || value === null || value === undefined || value === '') {
    return output
  }

  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    output.push(`${prefix}: ${formatValue(value)}`)
    return output
  }

  if (Array.isArray(value)) {
    output.push(`${prefix}: ${value.length} rows`)
    return output
  }

  if (typeof value === 'object') {
    for (const [key, childValue] of Object.entries(value as Record<string, unknown>)) {
      if (output.length >= limit) {
        break
      }
      const nextPrefix = prefix ? `${prefix}.${key}` : key
      flattenUserParameters(childValue, nextPrefix, output, limit)
    }
  }

  return output
}

function preOutputChips(step: SimulationStepViewRecord): string[] {
  const calculations = asRecord(step.calculations)
  const preOutput = asRecord(step.pre_output)
  const chips = [
    ...flattenUserParameters(calculations, '', [], 3),
    ...flattenUserParameters(preOutput, '', [], 2),
  ]
  return chips.length > 0 ? chips : ['no Pre variables']
}

function statusClass(status: string | undefined): string {
  switch ((status || '').toLowerCase()) {
    case 'failed':
    case 'parse error':
      return 'border-red-200 bg-red-50 text-red-700'
    case 'running':
      return 'border-blue-200 bg-blue-50 text-blue-700'
    case 'finished':
    case 'compiled':
    case 'success':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700'
    case 'queued':
    case 'pending':
      return 'border-amber-200 bg-amber-50 text-amber-700'
    case 'not ready':
      return 'border-slate-200 bg-slate-50 text-slate-500'
    default:
      return 'border-slate-200 bg-slate-50 text-slate-600'
  }
}

function toNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

function parseVector3(value: unknown): Vector3 | undefined {
  if (!Array.isArray(value) || value.length < 3) {
    return undefined
  }
  const x = toNumber(value[0])
  const y = toNumber(value[1])
  const z = toNumber(value[2])
  return x !== undefined && y !== undefined && z !== undefined ? [x, y, z] : undefined
}

function parseGeometryBasis(value: unknown): GeometryBasis | null {
  const record = asRecord(value)
  const ox = parseVector3(record.ox ?? record.x ?? record.Ox)
  const oy = parseVector3(record.oy ?? record.y ?? record.Oy)
  const oz = parseVector3(record.oz ?? record.z ?? record.Oz)
  const origin = parseVector3(record.origin)
  if (!origin && !ox && !oy && !oz) {
    return null
  }
  return { origin, ox, oy, oz }
}

function parseGeometryMarker(value: unknown): GeometryMarker | null {
  const record = asRecord(value)
  const point = parseVector3(record.point ?? record.position)
  const label = typeof record.label === 'string' ? record.label : undefined
  if (!point && !label) {
    return null
  }
  return { point, label }
}

function parseOutline(value: unknown): Array<[number, number]> {
  if (!Array.isArray(value)) {
    return []
  }
  const points: Array<[number, number]> = []
  for (const item of value) {
    if (!Array.isArray(item) || item.length < 2) {
      continue
    }
    const x = toNumber(item[0])
    const y = toNumber(item[1])
    if (x !== undefined && y !== undefined) {
      points.push([x, y])
    }
  }
  return points
}

export function summarizeGeometry(raw: Record<string, unknown> | null | undefined): GeometrySummary | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  return {
    shape: typeof raw.shape === 'string' ? raw.shape : undefined,
    width: toNumber(raw.width_mm),
    height: toNumber(raw.height_mm),
    length: toNumber(raw.length_mm),
    diameter: toNumber(raw.equivalent_diameter_mm),
    volume: toNumber(raw.volume_mm3),
    area: toNumber(raw.cross_section_area_mm2),
    outline: parseOutline(raw.cross_section_outline),
    basis: parseGeometryBasis(raw.basis),
    topMarker: parseGeometryMarker(raw.top_marker),
  }
}

function ellipseOutline(width: number, height: number, segments = 72): Array<[number, number]> {
  return Array.from({ length: segments }, (_, index) => {
    const angle = (index / segments) * Math.PI * 2
    return [Math.cos(angle) * width * 0.5, Math.sin(angle) * height * 0.5]
  })
}

function rectangleOutline(width: number, height: number): Array<[number, number]> {
  const halfWidth = width * 0.5
  const halfHeight = height * 0.5
  return [
    [-halfWidth, -halfHeight],
    [halfWidth, -halfHeight],
    [halfWidth, halfHeight],
    [-halfWidth, halfHeight],
  ]
}

function crossSectionOutline(geometry: GeometrySummary | null): Array<[number, number]> {
  if (!geometry) {
    return []
  }
  if (geometry.outline.length >= 3) {
    return geometry.outline
  }
  const width = geometry.width || geometry.diameter
  const height = geometry.height || geometry.diameter
  if (!width || !height) {
    return []
  }
  const shape = (geometry.shape || '').toLowerCase()
  const isRound =
    shape.includes('round') ||
    shape.includes('circle') ||
    shape.includes('cyl') ||
    (geometry.diameter !== undefined && geometry.width === undefined && geometry.height === undefined)
  return isRound ? ellipseOutline(width, height) : rectangleOutline(width, height)
}

interface PlanarProjector {
  project: (point: [number, number]) => [number, number]
}

function createPlanarProjector(
  outlines: Array<Array<[number, number]>>,
  width: number,
  height: number,
  padding = 18
): PlanarProjector | null {
  const points = outlines.flat()
  if (points.length === 0) {
    return null
  }
  const xs = points.map(([x]) => x)
  const ys = points.map(([, y]) => y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const spanX = Math.max(maxX - minX, 1)
  const spanY = Math.max(maxY - minY, 1)
  const availableWidth = Math.max(width - padding * 2, 1)
  const availableHeight = Math.max(height - padding * 2, 1)
  const scale = Math.min(availableWidth / spanX, availableHeight / spanY)
  const drawnWidth = spanX * scale
  const drawnHeight = spanY * scale
  const offsetX = (width - drawnWidth) * 0.5 - minX * scale
  const offsetY = (height - drawnHeight) * 0.5 + maxY * scale

  return {
    project: ([x, y]) => [offsetX + x * scale, offsetY - y * scale],
  }
}

function outlinePath(points: Array<[number, number]>, projector: PlanarProjector | null): string {
  if (points.length === 0 || !projector) {
    return ''
  }
  return points
    .map((point, index) => {
      const [px, py] = projector.project(point)
      return `${index === 0 ? 'M' : 'L'} ${px.toFixed(2)} ${py.toFixed(2)}`
    })
    .join(' ') + ' Z'
}

function geometryValue(geometry: GeometrySummary | null, key: 'width' | 'height' | 'length' | 'area'): number | undefined {
  if (!geometry) {
    return undefined
  }
  if (key === 'width') {
    return geometry.width ?? geometry.diameter
  }
  if (key === 'height') {
    return geometry.height ?? geometry.diameter
  }
  return geometry[key]
}

function metricValue(metrics: Record<string, unknown> | undefined, keys: string[]): number | undefined {
  for (const key of keys) {
    const value = toNumber(metrics?.[key])
    if (value !== undefined) {
      return value
    }
  }
  return undefined
}

export function Geometry2DPreview({
  initial,
  final,
  metrics,
}: {
  initial: GeometrySummary | null
  final: GeometrySummary | null
  metrics: Record<string, unknown>
}) {
  const width = 440
  const height = 280
  const initialOutline = crossSectionOutline(initial)
  const finalOutline = crossSectionOutline(final)
  const projector = createPlanarProjector([initialOutline, finalOutline], width, height, 24)
  const initialPath = outlinePath(initialOutline, projector)
  const finalPath = outlinePath(finalOutline, projector)
  const comparisonMetrics: ComparisonMetric[] = [
    { label: 'H', initial: geometryValue(initial, 'height'), final: geometryValue(final, 'height'), format: 'length' },
    { label: 'W', initial: geometryValue(initial, 'width'), final: geometryValue(final, 'width'), format: 'length' },
    { label: 'L', initial: geometryValue(initial, 'length'), final: geometryValue(final, 'length'), format: 'length' },
    { label: 'A', initial: geometryValue(initial, 'area'), final: geometryValue(final, 'area'), format: 'area' },
  ]
  const comparisonTableWidth = metricTableOverlayWidthPx(comparisonMetrics)
  const allStrainRows: ScalarMetricRow[] = [
    { label: 'eH', value: metricValue(metrics, ['strain_height']), format: 'log_strain' },
    { label: 'eW', value: metricValue(metrics, ['strain_width']), format: 'log_strain' },
    { label: 'eL', value: metricValue(metrics, ['strain_length']), format: 'log_strain' },
    { label: 'def', value: metricValue(metrics, ['relative_deformation_percent', 'relative_deformation_pct']), format: 'percent' },
  ]
  const strainRows = allStrainRows.filter((row) => row.value !== undefined)
  const hasStrainRows = strainRows.length > 0
  const strainTableWidth = hasStrainRows ? scalarMetricTableOverlayWidthPx(strainRows) : 0
  const strainTableHeight = hasStrainRows ? scalarMetricTableOverlayHeightPx(strainRows) : 0

  return (
    <div className="rounded-xl border border-[rgba(55,53,47,0.10)] bg-white p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className={GEOMETRY_VIEW_TITLE_CLASS}>2D cross-section</div>
        <div className={`${GEOMETRY_VIEW_NOTE_CLASS} flex items-center gap-2`}>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-slate-400" /> Initial</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Final</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-[280px] w-full rounded-lg bg-[#faf9f7]">
        <rect x="0" y="0" width={width} height={height} fill="#faf9f7" />
        <path d={`M 18 ${height - 18} H ${width - 18} M 18 18 V ${height - 18}`} stroke="rgba(55,53,47,0.18)" strokeWidth="1" />
        {initialPath ? <path d={initialPath} fill="rgba(100,116,139,0.13)" stroke="rgb(100,116,139)" strokeWidth="2" /> : null}
        {finalPath ? <path d={finalPath} fill="rgba(16,185,129,0.14)" stroke="rgb(16,185,129)" strokeWidth="2.4" /> : null}
        {initialPath || finalPath ? (
          <foreignObject x="14" y="14" width={comparisonTableWidth} height="62">
            <div className="rounded-lg border border-[rgba(55,53,47,0.10)] bg-white/85 p-1 font-mono text-[10px] leading-tight text-[rgba(55,53,47,0.68)] shadow-sm backdrop-blur">
              <MetricComparisonTable metrics={comparisonMetrics} />
            </div>
          </foreignObject>
        ) : null}
        {hasStrainRows ? (
          <foreignObject x={width - strainTableWidth - 14} y={height - strainTableHeight - 14} width={strainTableWidth} height={strainTableHeight}>
            <div className="rounded-lg border border-[rgba(55,53,47,0.10)] bg-white/85 p-1 font-mono text-[10px] leading-tight text-[rgba(55,53,47,0.68)] shadow-sm backdrop-blur">
              <ScalarMetricTable rows={strainRows} />
            </div>
          </foreignObject>
        ) : null}
        {!initialPath && !finalPath ? (
          <text x={width / 2} y={height / 2} textAnchor="middle" fill="rgba(55,53,47,0.45)" fontSize="10" fontFamily={GEOMETRY_VIEW_FONT_FAMILY}>
            No cross-section outline
          </text>
        ) : null}
      </svg>
    </div>
  )
}

function geometryStatsMetrics({
  initialGeometry,
  finalGeometry,
  initialSurface,
  finalSurface,
}: {
  initialGeometry: GeometrySummary | null
  finalGeometry: GeometrySummary | null
  initialSurface?: SimulationStepSurfaceMesh | null
  finalSurface?: SimulationStepSurfaceMesh | null
}): ComparisonMetric[] {
  return [
    { label: 'S', initial: initialSurface?.surface_area_mm2, final: finalSurface?.surface_area_mm2, format: 'area' },
    {
      label: 'V',
      initial: initialSurface?.volume_mm3 ?? initialGeometry?.volume,
      final: finalSurface?.volume_mm3 ?? finalGeometry?.volume,
      format: 'volume',
    },
    { label: 'L', initial: initialGeometry?.length, final: finalGeometry?.length, format: 'length' },
    {
      label: 'H',
      initial: initialGeometry?.height ?? initialGeometry?.diameter,
      final: finalGeometry?.height ?? finalGeometry?.diameter,
      format: 'length',
    },
    {
      label: 'W',
      initial: initialGeometry?.width ?? initialGeometry?.diameter,
      final: finalGeometry?.width ?? finalGeometry?.diameter,
      format: 'length',
    },
  ]
}

function GeometryStatsTable({ rows }: { rows: ComparisonMetric[] }) {
  return (
    <div className="rounded-lg border border-[rgba(55,53,47,0.10)] bg-white/85 p-1 font-mono text-[10px] leading-tight text-[rgba(55,53,47,0.68)] shadow-sm backdrop-blur">
      <MetricComparisonTable metrics={rows} />
    </div>
  )
}

function BasisStatus({ initial, final }: { initial: GeometrySummary | null; final: GeometrySummary | null }) {
  const hasInitialBasis = Boolean(initial?.basis?.ox || initial?.basis?.oy || initial?.basis?.oz)
  const hasFinalBasis = Boolean(final?.basis?.ox || final?.basis?.oy || final?.basis?.oz)
  const hasInitialMarker = Boolean(initial?.topMarker?.point || initial?.topMarker?.label)
  const hasFinalMarker = Boolean(final?.topMarker?.point || final?.topMarker?.label)
  if (hasInitialBasis || hasFinalBasis || hasInitialMarker || hasFinalMarker) {
    return (
      <div className="rounded-lg border border-[rgba(55,53,47,0.10)] bg-white/85 px-2 py-1.5 font-mono text-[10px] leading-tight text-[rgba(55,53,47,0.66)] shadow-sm backdrop-blur">
        <div className="font-semibold">Basis metadata</div>
        <div>Initial: {hasInitialBasis ? 'basis' : 'no basis'} / {hasInitialMarker ? 'top marker' : 'no marker'}</div>
        <div>Final: {hasFinalBasis ? 'basis' : 'no basis'} / {hasFinalMarker ? 'top marker' : 'no marker'}</div>
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50/90 px-2 py-1.5 font-mono text-[10px] leading-tight text-amber-800 shadow-sm backdrop-blur">
      Basis/top-marker metadata is not emitted by Pre yet. Rotation animation stays disabled.
    </div>
  )
}

export function Geometry3DPreview({
  geometry,
  kind,
  surface,
  isSurfaceLoading,
}: {
  geometry: GeometrySummary | null
  kind: GeometryKind
  surface?: SimulationStepSurfaceMesh | null
  isSurfaceLoading?: boolean
}) {
  const color = kind === 'initial' ? '#64748b' : '#10b981'
  const layers = useMemo<SurfaceMeshLayer[]>(
    () => surface
      ? [{
          key: kind,
          surface,
          color,
          opacity: 0.32,
          edgeOpacity: 0.14,
          sharpEdgeOpacity: 0.9,
        }]
      : [],
    [color, kind, surface]
  )

  return (
    <div className="rounded-xl border border-[rgba(55,53,47,0.10)] bg-white p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className={GEOMETRY_VIEW_TITLE_CLASS}>
          3D {kind} geometry
        </div>
        <div className={GEOMETRY_VIEW_NOTE_CLASS}>
          {isSurfaceLoading ? 'loading surface mesh...' : surface ? `${surface.face_count ?? 0} faces` : 'no surface mesh'}
        </div>
      </div>
      <SurfaceMeshThreeView
        layers={layers}
        isLoading={isSurfaceLoading}
        emptyMessage="Surface mesh is unavailable"
        className="h-[220px] w-full"
      />
      <div className="mt-2 grid grid-cols-2 gap-1 font-mono text-[10px] leading-tight text-[rgba(55,53,47,0.58)]">
        <div>Width: {formatMetricValue(geometry?.width || geometry?.diameter, 'length')}</div>
        <div>Height: {formatMetricValue(geometry?.height || geometry?.diameter, 'length')}</div>
        <div>Length: {formatMetricValue(geometry?.length, 'length')}</div>
        <div>Volume: {formatMetricValue(surface?.volume_mm3 ?? geometry?.volume, 'volume')}</div>
        <div>Area: {formatMetricValue(surface?.surface_area_mm2, 'area')}</div>
        <div>Basis: {geometry?.basis ? 'yes' : 'missing'}</div>
      </div>
    </div>
  )
}

export function Geometry3DOverlayPreview({
  initialGeometry,
  finalGeometry,
  initialSurface,
  finalSurface,
  isSurfaceLoading,
}: {
  initialGeometry: GeometrySummary | null
  finalGeometry: GeometrySummary | null
  initialSurface?: SimulationStepSurfaceMesh | null
  finalSurface?: SimulationStepSurfaceMesh | null
  isSurfaceLoading?: boolean
}) {
  const layers = useMemo<SurfaceMeshLayer[]>(
    () => [
      {
        key: 'initial',
        surface: initialSurface,
        color: '#64748b',
        opacity: 0.22,
        edgeOpacity: 0.10,
        sharpEdgeOpacity: 0.52,
      },
      {
        key: 'final',
        surface: finalSurface,
        color: '#10b981',
        opacity: 0.34,
        edgeOpacity: 0.12,
        sharpEdgeOpacity: 0.92,
      },
    ].filter((layer) => layer.surface),
    [initialSurface, finalSurface]
  )
  const statsRows = geometryStatsMetrics({
    initialGeometry,
    finalGeometry,
    initialSurface,
    finalSurface,
  })
  const statsTableWidth = metricTableOverlayWidthPx(statsRows)

  return (
    <div className="rounded-xl border border-[rgba(55,53,47,0.10)] bg-white p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className={GEOMETRY_VIEW_TITLE_CLASS}>3D initial/final overlay</div>
        <div className={`${GEOMETRY_VIEW_NOTE_CLASS} flex items-center gap-2`}>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-slate-400" /> Initial</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Final</span>
        </div>
      </div>
      <div className="relative h-[300px] w-full overflow-hidden rounded-lg bg-[#faf9f7]">
        <SurfaceMeshThreeView
          layers={layers}
          isLoading={isSurfaceLoading}
          emptyMessage="Surface meshes are unavailable"
          className="h-full w-full"
        />
        <div className="pointer-events-none absolute left-3 top-3" style={{ width: statsTableWidth }}>
          <GeometryStatsTable rows={statsRows} />
        </div>
        <div className="pointer-events-none absolute bottom-3 right-3 w-[200px]">
          <BasisStatus initial={initialGeometry} final={finalGeometry} />
        </div>
      </div>
    </div>
  )
}

export function StepGeometryPreviewGrid({
  step,
  surfaceMesh,
  isSurfaceLoading,
  meshViewMode = 'overlay',
}: {
  step: SimulationStepViewRecord
  surfaceMesh?: DocumentSimulationStepSurfaceResponse | null
  isSurfaceLoading?: boolean
  meshViewMode?: MeshViewMode
}) {
  const initialGeometry = summarizeGeometry(step.initial_geometry)
  const finalGeometry = summarizeGeometry(step.final_geometry)
  const selectedSurfaceMesh =
    surfaceMesh?.document_operation_id === step.document_operation_id ? surfaceMesh : null

  return (
    <div className="grid grid-cols-2 gap-3">
      <Geometry2DPreview initial={initialGeometry} final={finalGeometry} metrics={step.calculations} />
      <div className="min-w-0">
        {meshViewMode === 'overlay' ? (
          <Geometry3DOverlayPreview
            initialGeometry={initialGeometry}
            finalGeometry={finalGeometry}
            initialSurface={selectedSurfaceMesh?.initial}
            finalSurface={selectedSurfaceMesh?.final}
            isSurfaceLoading={isSurfaceLoading}
          />
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <Geometry3DPreview
              geometry={initialGeometry}
              kind="initial"
              surface={selectedSurfaceMesh?.initial}
              isSurfaceLoading={isSurfaceLoading}
            />
            <Geometry3DPreview
              geometry={finalGeometry}
              kind="final"
              surface={selectedSurfaceMesh?.final}
              isSurfaceLoading={isSurfaceLoading}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function compactJson(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'string') {
    return value
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

interface VariableEntry {
  key: string
  value: string
}

const HIDDEN_METRIC_KEYS = new Set([
  'initial_surface_area_mm2',
  'final_surface_area_mm2',
  'strain_height',
  'strain_width',
  'strain_length',
  'relative_deformation_percent',
  'relative_deformation_pct',
  'surface_artifacts',
])

const HIDDEN_GEOMETRY_KEYS = new Set([
  'cross_section_outline',
  'width_mm',
  'height_mm',
  'length_mm',
  'equivalent_diameter_mm',
  'volume_mm3',
  'cross_section_area_mm2',
  'parameters_json',
  'basis',
  'top_marker',
])

function geometryMetadata(raw: Record<string, unknown> | null | undefined): Record<string, unknown> {
  const record = asRecord(raw)
  return {
    type_id: record.type_id,
    shape: record.shape,
    orientation_metadata_status: record.orientation_metadata_status,
    parameters: record.parameters,
  }
}

function shouldHideVariable(path: string, value: unknown, hiddenTopLevelKeys: Set<string>): boolean {
  const parts = path.split('.')
  const topLevelKey = parts[0]
  const lastKey = parts[parts.length - 1]
  if (hiddenTopLevelKeys.has(topLevelKey) || hiddenTopLevelKeys.has(lastKey)) {
    return true
  }

  const normalized = path.toLowerCase()
  if (
    normalized.includes('cross_section_outline') ||
    normalized.includes('vertices') ||
    normalized.includes('faces') ||
    normalized.includes('stl') ||
    normalized.includes('artifact')
  ) {
    return true
  }

  return Array.isArray(value) && (
    normalized.includes('outline') ||
    normalized.includes('mesh') ||
    normalized.includes('surface')
  )
}

function formatVariableTableValue(value: unknown, path: string): string {
  const metricFormat = inferMetricFormatFromPath(path)
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '[]'
    }
    if (value.every((item) => item === null || ['string', 'number', 'boolean'].includes(typeof item))) {
      return `[${value.map((item) => metricFormat ? formatMetricValue(item, metricFormat) : formatValue(item)).join(', ')}]`
    }
    return `${value.length} rows`
  }
  if (value && typeof value === 'object') {
    return compactJson(value)
  }
  return metricFormat ? formatMetricValue(value, metricFormat) : formatValue(value)
}

function flattenVariableEntries(
  value: unknown,
  options: {
    prefix?: string
    hiddenTopLevelKeys?: Set<string>
    output?: VariableEntry[]
  } = {}
): VariableEntry[] {
  const prefix = options.prefix || ''
  const hiddenTopLevelKeys = options.hiddenTopLevelKeys || new Set<string>()
  const output = options.output || []
  if (value === null || value === undefined || value === '') {
    return output
  }
  if (shouldHideVariable(prefix, value, hiddenTopLevelKeys)) {
    return output
  }

  if (Array.isArray(value)) {
    output.push({ key: prefix || 'value', value: formatVariableTableValue(value, prefix || 'value') })
    return output
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0 && prefix) {
      output.push({ key: prefix, value: '{}' })
      return output
    }
    for (const [key, childValue] of entries) {
      const nextPrefix = prefix ? `${prefix}.${key}` : key
      flattenVariableEntries(childValue, {
        prefix: nextPrefix,
        hiddenTopLevelKeys,
        output,
      })
    }
    return output
  }

  output.push({ key: prefix || 'value', value: formatVariableTableValue(value, prefix || 'value') })
  return output
}

function VariableGroupPanel({
  title,
  value,
  hiddenTopLevelKeys = new Set<string>(),
}: {
  title: string
  value: unknown
  hiddenTopLevelKeys?: Set<string>
}) {
  const entries = flattenVariableEntries(value, { hiddenTopLevelKeys })
  return (
    <section className="rounded-xl border border-[rgba(55,53,47,0.10)] bg-white">
      <div className="border-b border-[rgba(55,53,47,0.07)] px-3 py-1.5 text-[12px] font-semibold text-[rgba(55,53,47,0.78)]">
        {title}
      </div>
      {entries.length > 0 ? (
        <div>
          <table className="w-full border-collapse text-[11px] leading-tight">
            <tbody>
              {entries.map((entry) => (
                <tr key={`${entry.key}-${entry.value}`} className="border-b border-[rgba(55,53,47,0.055)] last:border-b-0">
                  <th className="w-[42%] px-2 py-1 text-right align-top font-medium text-[rgba(55,53,47,0.48)]">
                    <span className="block break-words" title={entry.key}>{entry.key}</span>
                  </th>
                  <td className="px-2 py-1 align-top font-mono text-[rgba(55,53,47,0.72)]">
                    <span className="block break-words" title={entry.value}>{entry.value}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-3 py-3 text-[11px] text-[rgba(55,53,47,0.42)]">No extra variables.</div>
      )}
    </section>
  )
}

function stepStatus(step: SimulationStepViewRecord): string {
  const calculationStatus = typeof step.calculations?.preprocessor_status === 'string'
    ? step.calculations.preprocessor_status
    : undefined
  if (step.simulation_step_status?.status?.toLowerCase() === 'failed') {
    return step.simulation_step_status.status
  }
  if (step.preprocess_ready && !step.initial_geometry && !step.final_geometry) {
    return calculationStatus || step.simulation_step_status?.status || 'pending'
  }
  return calculationStatus || step.simulation_step_status?.status || (step.preprocess_ready ? 'ready' : 'not ready')
}

function stepStateDescription(step: SimulationStepViewRecord): string {
  const status = stepStatus(step).toLowerCase()
  if (status === 'failed') {
    return 'Pre or runtime execution failed on this row. Use the simulation_step_status, diagnostics, and related log query for troubleshooting.'
  }
  if (!step.preprocess_ready) {
    return 'This sibling simulation step exists, but its source document operation is not ready for Pre compilation.'
  }
  if (status === 'queued' || status === 'pending') {
    return 'Pre output is queued or pending. Run or wait for the Pre worker before using this row for Solver input.'
  }
  if (!step.initial_geometry && !step.final_geometry) {
    return 'Pre output is not available for this row yet. Queue Pre regeneration after saving document changes.'
  }
  return 'Pre output is available for this row.'
}

function stepError(step: SimulationStepViewRecord): string | null {
  if (step.simulation_step_status?.last_error) {
    return step.simulation_step_status.last_error
  }
  if (typeof step.calculations?.preprocessor_error === 'string') {
    return step.calculations.preprocessor_error
  }
  if (step.simulation_step_status?.error_payload && jsonCount(step.simulation_step_status.error_payload) > 0) {
    return JSON.stringify(step.simulation_step_status.error_payload)
  }
  return null
}

function issueMessage(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return ''
  }
  if (typeof value === 'string') {
    return value
  }
  const record = asRecord(value)
  const message = record.message || record.error || record.warning || record.detail
  if (typeof message === 'string') {
    return message
  }
  return compactJson(value)
}

function artifactIssueMessages(step: SimulationStepViewRecord): string[] {
  const messages: string[] = []
  const addMessage = (value: unknown) => {
    const message = issueMessage(value)
    if (message && !messages.includes(message)) {
      messages.push(message)
    }
  }

  addMessage(step.calculations?.legacy_surface_artifact_error)
  addMessage(step.calculations?.surface_artifact_error)

  const surfaceArtifacts = asRecord(step.calculations?.surface_artifacts)
  addMessage(surfaceArtifacts.artifact_storage_error)
  const artifacts = asRecord(surfaceArtifacts.artifacts)
  Object.values(artifacts).forEach((artifact) => {
    const writeErrors = asRecord(artifact).write_errors
    if (Array.isArray(writeErrors)) {
      writeErrors.forEach(addMessage)
    }
  })

  return messages
}

function stepIssues(step: SimulationStepViewRecord, activeSurfaceError?: string | null): StepIssue[] {
  const issues: StepIssue[] = []
  const sourceBlockId = step.source_block_id

  const preprocessorError = typeof step.calculations?.preprocessor_error === 'string'
    ? step.calculations.preprocessor_error
    : null
  if (preprocessorError) {
    issues.push({
      severity: 'error',
      kind: 'pre',
      title: 'Preprocessor failed',
      message: preprocessorError,
      sourceBlockId,
      raw: {
        document_operation_id: step.document_operation_id,
        operation_template_id: step.operation_template_id,
        preprocessor_error: preprocessorError,
      },
    })
  }

  if (step.simulation_step_status?.status?.toLowerCase() === 'failed') {
    issues.push({
      severity: 'error',
      kind: 'status',
      title: 'Step failed',
      message: step.simulation_step_status.last_error || 'The runtime status for this step is failed.',
      sourceBlockId,
      raw: step.simulation_step_status,
    })
  }

  if (!step.preprocess_ready) {
    issues.push({
      severity: 'blocked',
      kind: 'readiness',
      title: 'Preprocessor is blocked',
      message: 'This operation row is not ready for Pre compilation. Fix source input before retrying.',
      sourceBlockId,
      raw: { preprocess_ready: step.preprocess_ready },
    })
  }

  artifactIssueMessages(step).forEach((message) => {
    issues.push({
      severity: 'warning',
      kind: 'artifact',
      title: 'Surface artifact problem',
      message,
      sourceBlockId,
      raw: message,
    })
  })

  if (activeSurfaceError) {
    issues.push({
      severity: 'warning',
      kind: 'artifact',
      title: 'Surface preview unavailable',
      message: activeSurfaceError,
      sourceBlockId,
      raw: activeSurfaceError,
    })
  }

  if (issues.length === 0 && stepStatus(step).toLowerCase() !== 'compiled') {
    issues.push({
      severity: 'info',
      kind: 'status',
      title: 'Pre output status',
      message: stepStateDescription(step),
      sourceBlockId,
      raw: { status: stepStatus(step) },
    })
  }

  const apiMessages = Array.isArray(step.diagnostics?.api_messages) ? step.diagnostics.api_messages : []
  apiMessages.forEach((messageItem) => {
    const record = asRecord(messageItem)
    const severityValue = typeof record.severity === 'string' ? record.severity.toLowerCase() : 'info'
    const severity: StepIssueSeverity = severityValue === 'error'
      ? 'error'
      : severityValue === 'warning'
        ? 'warning'
        : 'info'
    issues.push({
      severity,
      kind: 'diagnostic',
      title: 'API diagnostic',
      message: issueMessage(messageItem),
      sourceBlockId,
      raw: messageItem,
    })
  })

  return issues
}

function summarizeStepIssues(steps: SimulationStepViewRecord[]): StepIssueSummary {
  return steps.reduce<StepIssueSummary>((summary, step) => {
    const issues = stepIssues(step)
    if (issues.some((issue) => (issue.kind === 'pre' || issue.kind === 'status') && issue.severity === 'error')) {
      summary.preErrors += 1
    }
    if (issues.some((issue) => issue.kind === 'artifact')) {
      summary.missingArtifacts += 1
    }
    summary.warnings += issues.filter((issue) => issue.severity === 'warning').length
    summary.blocked += issues.filter((issue) => issue.severity === 'blocked').length
    return summary
  }, {
    preErrors: 0,
    missingArtifacts: 0,
    warnings: 0,
    blocked: 0,
  })
}

function preLogSearchQuery(step: SimulationStepViewRecord): string {
  const relatedLogQuery = asRecord(step.diagnostics?.related_log_query)
  const searchTerms = Array.isArray(relatedLogQuery.search_terms)
    ? relatedLogQuery.search_terms
        .filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    : []
  if (searchTerms.length > 0) {
    return searchTerms.join(' ')
  }
  const queryParts = Object.entries(relatedLogQuery)
    .filter(([key, value]) => (
      key !== 'service'
      && key !== 'search_terms'
      && value !== null
      && value !== undefined
      && value !== ''
    ))
    .map(([key, value]) => `${key}=${value}`)
  if (queryParts.length > 0) {
    return queryParts.join(' ')
  }
  if (step.document_operation_id) {
    return `document_operation_id=${step.document_operation_id}`
  }
  if (step.source_block_id) {
    return String(step.source_block_id)
  }
  return step.operation_template_id || ''
}

function issueSeverityClass(severity: StepIssueSeverity): string {
  if (severity === 'error') {
    return 'border-red-200 bg-red-50 text-red-800'
  }
  if (severity === 'blocked') {
    return 'border-orange-200 bg-orange-50 text-orange-800'
  }
  if (severity === 'warning') {
    return 'border-amber-200 bg-amber-50 text-amber-800'
  }
  return 'border-sky-200 bg-sky-50 text-sky-800'
}

function issueBadgeClass(severity: StepIssueSeverity): string {
  if (severity === 'error') {
    return 'border-red-200 bg-white text-red-700'
  }
  if (severity === 'blocked') {
    return 'border-orange-200 bg-white text-orange-700'
  }
  if (severity === 'warning') {
    return 'border-amber-200 bg-white text-amber-700'
  }
  return 'border-sky-200 bg-white text-sky-700'
}

function issueSummaryTotal(summary: StepIssueSummary): number {
  return summary.preErrors + summary.missingArtifacts + summary.warnings + summary.blocked
}

function StepIssueStrip({
  issues,
  preLogQuery,
  onOpenPreLogs,
  onOpenSourceBlock,
}: {
  issues: StepIssue[]
  preLogQuery: string
  onOpenPreLogs?: (query: string) => void
  onOpenSourceBlock?: (blockId: string) => void
}) {
  if (issues.length === 0) {
    return null
  }

  const primaryIssue = issues[0]
  const sourceBlockId = issues.find((issue) => issue.sourceBlockId)?.sourceBlockId || null
  const rawDiagnostics = issues
    .map((issue) => issue.raw)
    .filter((value) => value !== null && value !== undefined && value !== '')

  return (
    <section className={`rounded-xl border px-3 py-2 text-[12px] ${issueSeverityClass(primaryIssue.severity)}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.04em] ${issueBadgeClass(primaryIssue.severity)}`}>
              {primaryIssue.severity}
            </span>
            <span className="font-semibold">{primaryIssue.title}</span>
            {issues.length > 1 ? (
              <span className="text-[11px] opacity-75">+{issues.length - 1} more</span>
            ) : null}
          </div>
          <div className="mt-1 break-words leading-snug">{primaryIssue.message}</div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {sourceBlockId && onOpenSourceBlock ? (
            <button type="button" className="ui-btn h-8 bg-white" onClick={() => onOpenSourceBlock(sourceBlockId)}>
              Go to source block
            </button>
          ) : null}
          {preLogQuery && onOpenPreLogs ? (
            <button type="button" className="ui-btn h-8 bg-white" onClick={() => onOpenPreLogs(preLogQuery)}>
              Open Pre logs
            </button>
          ) : null}
        </div>
      </div>
      {issues.length > 1 ? (
        <div className="mt-2 grid gap-1">
          {issues.slice(1).map((issue, index) => (
            <div key={`${issue.kind}-${issue.severity}-${index}`} className="rounded-md bg-white/60 px-2 py-1">
              <span className="font-semibold">{issue.title}:</span> {issue.message}
            </div>
          ))}
        </div>
      ) : null}
      {rawDiagnostics.length > 0 ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-[11px] font-semibold opacity-75">Raw diagnostics</summary>
          <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-white/70 px-2 py-1 text-[11px] text-[rgba(55,53,47,0.72)]">
            {JSON.stringify(rawDiagnostics, null, 2)}
          </pre>
        </details>
      ) : null}
    </section>
  )
}

function logLevelClass(level: string | undefined): string {
  switch ((level || '').toUpperCase()) {
    case 'ERROR':
    case 'CRITICAL':
      return 'border-red-200 bg-red-50 text-red-700'
    case 'WARNING':
      return 'border-amber-200 bg-amber-50 text-amber-700'
    case 'DEBUG':
      return 'border-slate-200 bg-slate-50 text-slate-500'
    default:
      return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  }
}

function logEntrySource(record: RelatedLogRecord): string {
  const entry = record.entry || {}
  const logger = typeof entry.logger === 'string' && entry.logger ? entry.logger : record.worker_name
  const fn = typeof entry.function === 'string' && entry.function ? entry.function : ''
  const line = typeof entry.line === 'number' || typeof entry.line === 'string' ? String(entry.line) : ''
  return fn ? `${logger} · ${fn}${line ? `:${line}` : ''}` : logger
}

function logEntryMessage(record: RelatedLogRecord): string {
  const message = record.entry?.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }
  try {
    return JSON.stringify(record.entry)
  } catch {
    return String(record.entry)
  }
}

function RelatedPreLogsPanel({
  response,
  isLoading,
  error,
  preLogQuery,
  onOpenPreLogs,
}: {
  response: LogRelatedResponse | null
  isLoading: boolean
  error: string | null
  preLogQuery: string
  onOpenPreLogs?: (query: string) => void
}) {
  const entries = response?.entries || []
  return (
    <section className="rounded-xl border border-[rgba(55,53,47,0.10)] bg-white">
      <div className="flex items-center justify-between gap-2 border-b border-[rgba(55,53,47,0.07)] px-3 py-1.5">
        <div>
          <div className="text-[12px] font-semibold text-[rgba(55,53,47,0.78)]">Related Pre log records</div>
          <div className="mt-0.5 text-[10px] text-[rgba(55,53,47,0.42)]">
            {isLoading
              ? 'Loading...'
              : `${entries.length} records · workers ${(response?.searched_workers || []).join(', ') || 'pre'}`}
          </div>
        </div>
        {preLogQuery && onOpenPreLogs ? (
          <button type="button" className="ui-btn h-7 text-[11px]" onClick={() => onOpenPreLogs(preLogQuery)}>
            Open logs
          </button>
        ) : null}
      </div>
      {error ? (
        <div className="px-3 py-2 text-[11px] text-red-700">{error}</div>
      ) : entries.length > 0 ? (
        <div className="overflow-hidden">
          <table className="w-full border-collapse text-[11px] leading-tight">
            <tbody>
              {entries.map((record, index) => (
                <tr
                  key={`${record.worker_name}-${record.entry.timestamp || index}-${index}`}
                  className="border-b border-[rgba(55,53,47,0.055)] last:border-b-0 align-top"
                >
                  <td className="w-[92px] px-2 py-1 font-mono text-[10px] text-[rgba(55,53,47,0.42)]">
                    {formatDate(typeof record.entry.timestamp === 'string' ? record.entry.timestamp : undefined)}
                  </td>
                  <td className="w-[72px] px-1 py-1">
                    <span className={`inline-flex rounded-full border px-1.5 py-0.5 text-[9px] font-semibold ${logLevelClass(record.entry.level)}`}>
                      {record.entry.level || 'LOG'}
                    </span>
                  </td>
                  <td className="px-2 py-1">
                    <div className="font-medium text-[rgba(55,53,47,0.72)]">{logEntrySource(record)}</div>
                    <div className="mt-0.5 break-words text-[rgba(55,53,47,0.78)]">{logEntryMessage(record)}</div>
                    {record.match_reasons.length > 0 ? (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {record.match_reasons.map((reason) => (
                          <span
                            key={reason}
                            className="rounded bg-[#f5f4f1] px-1.5 py-0.5 font-mono text-[9px] text-[rgba(55,53,47,0.50)]"
                          >
                            {reason}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-3 py-3 text-[11px] text-[rgba(55,53,47,0.42)]">
          No matching Pre log records in the recent log tail.
        </div>
      )}
    </section>
  )
}

function operationTitle(step: SimulationStepViewRecord): string {
  return step.operation_label_snapshot || step.operation_template_id || step.operation_kind
}

function hasAnyRelatedBlock(blockIds: string[], highlightBlockIds: Set<string>): boolean {
  return blockIds.some((blockId) => highlightBlockIds.has(blockId))
}

function stepSummaryTableValue(step: SimulationStepViewRecord): Record<string, unknown> {
  return {
    title: `Step ${step.execution_order}: ${operationTitle(step)}`,
    status: stepStatus(step),
    state: stepStateDescription(step),
    document_operation_id: step.document_operation_id,
    operation_template_id: step.operation_template_id || '-',
    source_block_id: step.source_block_id || '-',
    updated_at: formatDate(step.updated_at),
  }
}

function StepListPanel({
  items,
  selectedStep,
  isLoading,
  isQueueingPre,
  visibleRowsCount,
  totalRowsCount,
  isFiltered,
  issueSummary,
  onSelectStep,
  onRefresh,
  highlightedBlockIds,
  onHoverBlockIds,
}: {
  items: StepListItem[]
  selectedStep: SimulationStepViewRecord | null
  isLoading: boolean
  isQueueingPre: boolean
  visibleRowsCount: number
  totalRowsCount: number
  isFiltered: boolean
  issueSummary: StepIssueSummary
  onSelectStep: (stepId: number) => void
  onRefresh: () => void
  highlightedBlockIds: Set<string>
  onHoverBlockIds: (blockIds: string[]) => void
}) {
  return (
    <aside className="flex h-full min-h-0 flex-col overflow-hidden border-r border-[rgba(55,53,47,0.08)] bg-white">
      <div className="border-b border-[rgba(55,53,47,0.08)] bg-[#f5f4f1] px-2.5 py-2">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold text-[rgba(55,53,47,0.72)]">Steps</div>
            <div className="mt-0.5 truncate text-[9px] text-[rgba(55,53,47,0.44)]">
              {visibleRowsCount}{isFiltered ? ` / ${totalRowsCount}` : ''} rows
            </div>
          </div>
          <button
            type="button"
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[rgba(55,53,47,0.12)] bg-white text-[rgba(55,53,47,0.66)] shadow-sm transition hover:bg-[rgba(55,53,47,0.04)] disabled:cursor-not-allowed disabled:opacity-50"
            onClick={onRefresh}
            disabled={isLoading || isQueueingPre}
            aria-label="Queue preprocessor refresh"
            title="Queue Pre without regenerating operations"
          >
            <RefreshIcon className={`h-4 w-4 ${isLoading || isQueueingPre ? 'animate-spin' : ''}`} />
          </button>
        </div>
        {issueSummaryTotal(issueSummary) > 0 ? (
          <div className="mt-2 grid grid-cols-2 gap-1 text-[9px]">
            {issueSummary.preErrors > 0 ? (
              <span className="rounded border border-red-200 bg-red-50 px-1 py-0.5 text-red-700">Pre {issueSummary.preErrors}</span>
            ) : null}
            {issueSummary.missingArtifacts > 0 ? (
              <span className="rounded border border-amber-200 bg-amber-50 px-1 py-0.5 text-amber-700">Artifacts {issueSummary.missingArtifacts}</span>
            ) : null}
            {issueSummary.warnings > 0 ? (
              <span className="rounded border border-amber-200 bg-amber-50 px-1 py-0.5 text-amber-700">Warnings {issueSummary.warnings}</span>
            ) : null}
            {issueSummary.blocked > 0 ? (
              <span className="rounded border border-orange-200 bg-orange-50 px-1 py-0.5 text-orange-700">Blocked {issueSummary.blocked}</span>
            ) : null}
          </div>
        ) : (
          <div className="mt-2 rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[9px] text-emerald-700">
            No document issues
          </div>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-1.5 py-2">
        <div className="space-y-1">
          {items.map((item, index) => {
            if (item.kind === 'section') {
              const isRelated = hasAnyRelatedBlock(item.relatedBlockIds, highlightedBlockIds)
              return (
                <div
                  key={`section-${item.block.block_id}-${index}`}
                  onMouseEnter={() => onHoverBlockIds(item.relatedBlockIds)}
                  onMouseLeave={() => onHoverBlockIds([])}
                  className={`rounded-md border px-2 py-1.5 text-[10px] font-semibold transition ${
                    isRelated
                      ? 'border-amber-200 bg-amber-50 text-amber-800'
                      : 'border-transparent bg-[rgba(55,53,47,0.065)] text-[rgba(55,53,47,0.78)]'
                  }`}
                >
                  <span className="font-mono text-[rgba(55,53,47,0.48)]">{item.number}</span>{' '}
                  {item.title}
                </div>
              )
            }

            if (item.kind === 'source') {
              const isRelated = hasAnyRelatedBlock(item.relatedBlockIds, highlightedBlockIds)
              return (
                <div
                  key={`source-${item.block.block_id}-${index}`}
                  onMouseEnter={() => onHoverBlockIds(item.relatedBlockIds)}
                  onMouseLeave={() => onHoverBlockIds([])}
                  className={`ml-2 rounded-md border px-2 py-1 text-[10px] font-medium transition ${
                    isRelated
                      ? 'border-amber-200 bg-amber-50 text-amber-800'
                      : 'border-transparent bg-[#faf9f7] text-[rgba(55,53,47,0.62)]'
                  }`}
                >
                  <span className="font-mono text-[rgba(55,53,47,0.40)]">{item.number}</span>{' '}
                  {item.title}
                </div>
              )
            }

            const { step } = item
            const isSelected = selectedStep?.document_operation_id === step.document_operation_id
            const isRelated = step.source_block_id ? highlightedBlockIds.has(step.source_block_id) : false
            const status = stepStatus(step)
            const errorMessage = stepError(step)
            const chips = preOutputChips(step)

            return (
              <button
                key={`step-${step.document_operation_id}`}
                type="button"
                onClick={() => onSelectStep(step.document_operation_id)}
                onMouseEnter={() => onHoverBlockIds(step.source_block_id ? [step.source_block_id] : [])}
                onMouseLeave={() => onHoverBlockIds([])}
                className={`ml-4 block w-[calc(100%-1rem)] rounded-md border px-2 py-1.5 text-left transition hover:bg-[rgba(55,53,47,0.035)] ${
                  isSelected
                    ? 'border-[rgba(55,53,47,0.30)] bg-[rgba(55,53,47,0.07)]'
                    : isRelated
                      ? 'border-amber-200 bg-amber-50/70'
                    : 'border-transparent bg-white'
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="font-mono text-[10px] font-semibold text-[rgba(55,53,47,0.64)]">
                    {step.execution_order}
                  </span>
                  <span className={`max-w-[78px] truncate rounded-full border px-1.5 py-0.5 text-[9px] font-semibold ${statusClass(status)}`}>
                    {status}
                  </span>
                </div>
                <div className="mt-1 truncate text-[10px] font-semibold text-[rgba(55,53,47,0.84)]">
                  {operationTitle(step)}
                </div>
                <div className="mt-1 space-y-0.5">
                  {chips.slice(0, 4).map((chip) => (
                    <div
                      key={chip}
                      className="truncate rounded bg-[#f5f4f1] px-1.5 py-0.5 font-mono text-[9px] text-[rgba(55,53,47,0.54)]"
                      title={chip}
                    >
                      {chip}
                    </div>
                  ))}
                </div>
                {errorMessage ? (
                  <div className="mt-1 truncate text-[9px] text-red-600" title={errorMessage}>
                    {errorMessage}
                  </div>
                ) : null}
              </button>
            )
          })}
        </div>
        {!isLoading && items.length === 0 ? (
          <div className="px-2 py-8 text-center text-[11px] text-[rgba(55,53,47,0.45)]">
            No simulation steps yet.
          </div>
        ) : null}
        {isLoading ? (
          <div className="px-2 py-8 text-center text-[11px] text-[rgba(55,53,47,0.45)]">
            Loading...
          </div>
        ) : null}
      </div>
    </aside>
  )
}

function buildStepListItems(blocks: BlockData[], steps: SimulationStepViewRecord[]): StepListItem[] {
  if (blocks.length === 0) {
    return steps.map((step) => ({ kind: 'step', step }))
  }

  const usedStepIds = new Set<number>()
  const stepsByBlockId = new Map<string, SimulationStepViewRecord[]>()
  steps.forEach((step) => {
    if (!step.source_block_id) {
      return
    }
    const list = stepsByBlockId.get(step.source_block_id) || []
    list.push(step)
    stepsByBlockId.set(step.source_block_id, list)
  })

  const items: StepListItem[] = []
  const documentBlock = blocks.find((block) => block.block_type_id === DOCUMENT_BLOCK_TYPE_ID)
  if (documentBlock) {
    const documentSteps = stepsByBlockId.get(documentBlock.block_id) || []
    documentSteps.forEach((step) => {
      items.push({ kind: 'step', step })
      usedStepIds.add(step.document_operation_id)
    })
  }

  const sections = buildVisualSections(blocks)
  const sectionNumbers = buildSectionNumbers(sections, sectionNumberingStart(blocks))
  sections.forEach((section) => {
    const sectionRelatedBlockIds = [
      section.block.block_id,
      ...section.children.map((child) => child.block_id),
    ]
    items.push({
      kind: 'section',
      block: section.block,
      title: blockDisplayName(section.block),
      number: sectionNumbers.get(section.block.block_id) || null,
      relatedBlockIds: sectionRelatedBlockIds,
    })

    const sectionSteps = stepsByBlockId.get(section.block.block_id) || []
    sectionSteps.forEach((step) => {
      items.push({ kind: 'step', step })
      usedStepIds.add(step.document_operation_id)
    })

    section.children.forEach((child, childIndex) => {
      const childNumber = child.block_type_id === OPERATION_BLOCK_TYPE_ID || child.block_type_id === FURNACE_BLOCK_TYPE_ID
        ? `${childIndex + 1}.`
        : null
      items.push({
        kind: 'source',
        block: child,
        title: blockDisplayName(child),
        number: childNumber,
        relatedBlockIds: [child.block_id],
      })
      const childSteps = stepsByBlockId.get(child.block_id) || []
      childSteps.forEach((step) => {
        items.push({ kind: 'step', step })
        usedStepIds.add(step.document_operation_id)
      })
    })
  })

  steps.forEach((step) => {
    if (!usedStepIds.has(step.document_operation_id)) {
      items.push({ kind: 'step', step })
    }
  })

  return items
}

export default function SimulationStepsView({
  documentId,
  isStepListVisible = true,
  activeBlockId = null,
  hoveredBlockId = null,
  onOpenPreLogs,
  onOpenSourceBlock,
}: SimulationStepsViewProps) {
  const [steps, setSteps] = useState<SimulationStepViewRecord[]>([])
  const [blocks, setBlocks] = useState<BlockData[]>([])
  const [selectedStepId, setSelectedStepId] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isQueueingPre, setIsQueueingPre] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [surfaceMesh, setSurfaceMesh] = useState<DocumentSimulationStepSurfaceResponse | null>(null)
  const [isSurfaceLoading, setIsSurfaceLoading] = useState(false)
  const [surfaceError, setSurfaceError] = useState<string | null>(null)
  const [relatedPreLogs, setRelatedPreLogs] = useState<LogRelatedResponse | null>(null)
  const [isRelatedPreLogsLoading, setIsRelatedPreLogsLoading] = useState(false)
  const [relatedPreLogsError, setRelatedPreLogsError] = useState<string | null>(null)
  const [hoveredBlockIds, setHoveredBlockIds] = useState<string[]>([])
  const [meshViewMode, setMeshViewMode] = useState<MeshViewMode>('overlay')

  const activeSourceBlockIds = useMemo(
    () => relatedSourceBlockIds(blocks, activeBlockId),
    [activeBlockId, blocks]
  )
  const hoveredSourceBlockIds = useMemo(
    () => relatedSourceBlockIds(blocks, hoveredBlockId),
    [blocks, hoveredBlockId]
  )
  const visibleSteps = steps

  const selectedStep = useMemo(() => {
    if (visibleSteps.length === 0) {
      return null
    }
    return visibleSteps.find((step) => step.document_operation_id === selectedStepId) || visibleSteps[0]
  }, [selectedStepId, visibleSteps])
  const selectedStepIssues = useMemo(
    () => selectedStep ? stepIssues(selectedStep, surfaceError) : [],
    [selectedStep, surfaceError]
  )
  const selectedStepPreLogQuery = useMemo(
    () => selectedStep ? preLogSearchQuery(selectedStep) : '',
    [selectedStep]
  )
  const documentIssueSummary = useMemo(
    () => summarizeStepIssues(steps),
    [steps]
  )

  const stepListItems = useMemo(() => buildStepListItems(blocks, visibleSteps), [blocks, visibleSteps])
  const highlightedBlockIds = useMemo(() => {
    const blockIds = new Set<string>()
    activeSourceBlockIds.forEach((blockId) => blockIds.add(blockId))
    hoveredSourceBlockIds.forEach((blockId) => blockIds.add(blockId))
    if (selectedStep?.source_block_id) {
      blockIds.add(selectedStep.source_block_id)
    }
    hoveredBlockIds.forEach((blockId) => blockIds.add(blockId))
    return blockIds
  }, [activeSourceBlockIds, hoveredBlockIds, hoveredSourceBlockIds, selectedStep?.source_block_id])

  const loadSteps = async () => {
    if (!documentId) {
      setSteps([])
      setBlocks([])
      setSelectedStepId(null)
      setError(null)
      setNotice(null)
      return
    }
    setIsLoading(true)
    setError(null)
    const [response, blocksResponse] = await Promise.all([
      apiClient.get<DocumentSimulationStepListResponse>(`/documents/${documentId}/simulation-steps`),
      apiClient.get<BlockData[]>(`/documents/${documentId}/blocks/root`),
    ])
    setBlocks(blocksResponse.ok && blocksResponse.data ? blocksResponse.data : [])
    if (!response.ok || !response.data) {
      setSteps([])
      setSelectedStepId(null)
      setError(response.errorMessage || 'Failed to load simulation steps.')
      setIsLoading(false)
      return
    }
    const nextSteps = (response.data.steps || []).map(toStepViewRecord)
    setSteps(nextSteps)
    setSelectedStepId((previous) => {
      if (previous && nextSteps.some((step) => step.document_operation_id === previous)) {
        return previous
      }
      return nextSteps[0]?.document_operation_id ?? null
    })
    setIsLoading(false)
  }

  const queuePreprocess = async () => {
    if (!documentId || isQueueingPre) {
      return
    }

    setIsQueueingPre(true)
    setError(null)
    setNotice(null)

    const response = await apiClient.post<DocumentPreprocessQueueResponse>(
      `/documents/${documentId}/simulation-steps/preprocess`
    )
    if (!response.ok || !response.data) {
      setError(response.errorMessage || 'Failed to start preprocessor.')
      setIsQueueingPre(false)
      return
    }

    setNotice(`${response.data.message} Operations: ${response.data.operations_count}.`)
    await loadSteps()
    setIsQueueingPre(false)

    window.setTimeout(() => {
      void loadSteps()
    }, 1200)
  }

  useEffect(() => {
    void loadSteps()
  }, [documentId])

  useEffect(() => {
    if (!documentId || !selectedStep) {
      setSurfaceMesh(null)
      setSurfaceError(null)
      setIsSurfaceLoading(false)
      return
    }

    let isCancelled = false
    setSurfaceMesh(null)
    setSurfaceError(null)
    setIsSurfaceLoading(true)

    apiClient
      .get<DocumentSimulationStepSurfaceResponse>(
        `/documents/${documentId}/simulation-steps/${selectedStep.document_operation_id}/surface`,
        { params: { max_outline_points: 128 } }
      )
      .then((response) => {
        if (isCancelled) {
          return
        }
        if (!response.ok || !response.data) {
          setSurfaceError(response.errorMessage || 'Failed to load surface mesh.')
          return
        }
        setSurfaceMesh(response.data)
      })
      .finally(() => {
        if (!isCancelled) {
          setIsSurfaceLoading(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [documentId, selectedStep?.document_operation_id])

  useEffect(() => {
    if (!selectedStep) {
      setRelatedPreLogs(null)
      setRelatedPreLogsError(null)
      setIsRelatedPreLogsLoading(false)
      return
    }

    let isCancelled = false
    setRelatedPreLogs(null)
    setRelatedPreLogsError(null)
    setIsRelatedPreLogsLoading(true)

    apiClient
      .get<LogRelatedResponse>('/logs/pre/related', {
        params: {
          document_operation_id: selectedStep.document_operation_id,
          document_version_id: selectedStep.document_version_id,
          execution_order: selectedStep.execution_order,
          operation_template_id: selectedStep.operation_template_id || undefined,
          source_block_id: selectedStep.source_block_id || undefined,
          lines: 3000,
          limit: 12,
        },
      })
      .then((response) => {
        if (isCancelled) {
          return
        }
        if (!response.ok || !response.data) {
          setRelatedPreLogsError(response.errorMessage || 'Failed to load related Pre logs.')
          return
        }
        setRelatedPreLogs(response.data)
      })
      .finally(() => {
        if (!isCancelled) {
          setIsRelatedPreLogsLoading(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [selectedStep?.document_operation_id])

  if (!documentId) {
    return (
      <section className="flex h-full min-h-0 items-center justify-center bg-[#fbfbfa] text-sm text-[rgba(55,53,47,0.55)]">
        Select one document to inspect simulation steps.
      </section>
    )
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-[#fbfbfa]">
      {error ? (
        <div className="mx-5 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="mx-5 mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {notice}
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {isStepListVisible ? (
          <div className="w-[230px] shrink-0 min-h-0">
            <StepListPanel
              items={stepListItems}
              selectedStep={selectedStep}
              isLoading={isLoading}
              isQueueingPre={isQueueingPre}
              visibleRowsCount={visibleSteps.length}
              totalRowsCount={steps.length}
              isFiltered={false}
              issueSummary={documentIssueSummary}
              onSelectStep={setSelectedStepId}
              onRefresh={() => void queuePreprocess()}
              highlightedBlockIds={highlightedBlockIds}
              onHoverBlockIds={setHoveredBlockIds}
            />
          </div>
        ) : null}

        <div className="min-h-0 flex-1 overflow-auto p-4">
          {selectedStep ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="text-[12px] font-semibold text-[rgba(55,53,47,0.68)]">Geometry inspection</div>
                <div className="inline-flex rounded-full border border-[rgba(55,53,47,0.12)] bg-white p-0.5 text-[10px]">
                  <button
                    type="button"
                    onClick={() => setMeshViewMode('overlay')}
                    className={`rounded-full px-2.5 py-1 font-semibold ${
                      meshViewMode === 'overlay'
                        ? 'bg-[rgba(55,53,47,0.88)] text-white'
                        : 'text-[rgba(55,53,47,0.58)] hover:bg-[rgba(55,53,47,0.06)]'
                    }`}
                  >
                    Overlay
                  </button>
                  <button
                    type="button"
                    onClick={() => setMeshViewMode('side_by_side')}
                    className={`rounded-full px-2.5 py-1 font-semibold ${
                      meshViewMode === 'side_by_side'
                        ? 'bg-[rgba(55,53,47,0.88)] text-white'
                        : 'text-[rgba(55,53,47,0.58)] hover:bg-[rgba(55,53,47,0.06)]'
                    }`}
                  >
                    Side by side
                  </button>
                </div>
              </div>

              <StepGeometryPreviewGrid
                step={selectedStep}
                surfaceMesh={surfaceMesh}
                isSurfaceLoading={isSurfaceLoading}
                meshViewMode={meshViewMode}
              />

              <StepIssueStrip
                issues={selectedStepIssues}
                preLogQuery={selectedStepPreLogQuery}
                onOpenPreLogs={onOpenPreLogs}
                onOpenSourceBlock={onOpenSourceBlock}
              />

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-3">
                  <VariableGroupPanel title="simulation_steps.pre_input" value={selectedStep.pre_input} />
                  <VariableGroupPanel title="simulation_steps.pre_output" value={selectedStep.pre_output} />
                  <VariableGroupPanel
                    title="simulation_steps.calculations"
                    value={selectedStep.calculations}
                    hiddenTopLevelKeys={HIDDEN_METRIC_KEYS}
                  />
                </div>

                <div className="space-y-3">
                  <VariableGroupPanel title="Step summary" value={stepSummaryTableValue(selectedStep)} />
                  <VariableGroupPanel
                    title="Geometry metadata"
                    value={{
                      initial: geometryMetadata(selectedStep.initial_geometry),
                      final: geometryMetadata(selectedStep.final_geometry),
                    }}
                    hiddenTopLevelKeys={HIDDEN_GEOMETRY_KEYS}
                  />
                  <VariableGroupPanel title="simulation_step_status" value={selectedStep.simulation_step_status} />
                  <VariableGroupPanel title="Diagnostics / API response" value={selectedStep.diagnostics} />
                  <RelatedPreLogsPanel
                    response={relatedPreLogs}
                    isLoading={isRelatedPreLogsLoading}
                    error={relatedPreLogsError}
                    preLogQuery={selectedStepPreLogQuery}
                    onOpenPreLogs={onOpenPreLogs}
                  />
                  <VariableGroupPanel
                    title="simulation_steps typed columns"
                    value={{
                      document_operation_id: selectedStep.document_operation_id,
                      document_version_id: selectedStep.document_version_id,
                      execution_order: selectedStep.execution_order,
                      source_block_id: selectedStep.source_block_id,
                      operation_template_id: selectedStep.operation_template_id,
                      operation_kind: selectedStep.operation_kind,
                      operation_label_snapshot: selectedStep.operation_label_snapshot,
                      block_name_snapshot: selectedStep.block_name_snapshot,
                      library_name_snapshot: selectedStep.library_name_snapshot,
                      material_version_id: selectedStep.material_version_id,
                      press_id: selectedStep.press_id,
                      press_mode_id: selectedStep.press_mode_id,
                      die_assembly_id: selectedStep.die_assembly_id,
                      top_die_id: selectedStep.top_die_id,
                      bottom_die_id: selectedStep.bottom_die_id,
                      left_die_id: selectedStep.left_die_id,
                      right_die_id: selectedStep.right_die_id,
                      accumulated_time_start_seconds: selectedStep.accumulated_time_start_seconds,
                      duration_seconds: selectedStep.duration_seconds,
                      accumulated_time_stop_seconds: selectedStep.accumulated_time_stop_seconds,
                      created_at: selectedStep.created_at,
                      updated_at: selectedStep.updated_at,
                    }}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center rounded-xl border border-[rgba(55,53,47,0.10)] bg-white text-sm text-[rgba(55,53,47,0.45)]">
              Select a simulation step row.
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
