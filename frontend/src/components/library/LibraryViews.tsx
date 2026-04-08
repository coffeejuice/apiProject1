import { Fragment, useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'

import DieStlPreview from './DieStlPreview'
import { apiClient } from '../../lib/apiClient'
import { formatLibraryName, formatTimestamp } from '../../lib/libraryDisplay'
import type {
  DieAssemblyRecord,
  DieRecord,
  DieTypeRecord,
  LibraryDbUserRecord,
  MaterialClassificationAxisRecord,
  MaterialClassificationCatalogRecord,
  MaterialRecord,
  MaterialVisualAxisRecord,
  MaterialVisualDiagramRecord,
  MaterialVisualRecord,
  MaterialVisualSeriesRecord,
  PressModeRecord,
  PressRecord,
} from '../../types/api'

type OwnerFilterKey =
  | 'all'
  | 'builtIn'
  | 'builtInAndCurrentUser'
  | 'allUsers'
  | 'currentUser'
  | 'selectedUser'

const OWNER_FILTER_ITEMS: Array<{ id: OwnerFilterKey; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'builtIn', label: 'Build-in' },
  { id: 'builtInAndCurrentUser', label: 'Build-in and Current user' },
  { id: 'allUsers', label: 'All users' },
  { id: 'currentUser', label: 'Current user' },
  { id: 'selectedUser', label: 'Selected user' },
]

const DEFAULT_OWNER_FILTERS: Set<OwnerFilterKey> = new Set(['builtInAndCurrentUser'])

function toggleFilter<T>(current: Set<T>, value: T): Set<T> {
  if (current.has(value)) {
    if (current.size === 1) {
      return current
    }
    const next = new Set(current)
    next.delete(value)
    return next
  }

  const next = new Set(current)
  next.add(value)
  return next
}

function normalizeNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }

  return null
}

function buildUserLabel(user: LibraryDbUserRecord): string {
  if (user.full_name && user.full_name.trim().length > 0) {
    return user.full_name
  }
  return user.login
}

function getOwnerLabel(ownerUserId: number | null | undefined, usersById: Map<number, LibraryDbUserRecord>): string {
  if (ownerUserId === null || ownerUserId === undefined) {
    return 'Build-in'
  }

  const user = usersById.get(ownerUserId)
  if (!user) {
    return `User ${ownerUserId}`
  }

  return `${buildUserLabel(user)} (${user.login})`
}

function matchesOwnerFilter(
  ownerUserId: number | null | undefined,
  activeOwnerFilters: Set<OwnerFilterKey>,
  currentUserId: number | null,
  selectedUserId: number | null
): boolean {
  if (activeOwnerFilters.has('all')) {
    return true
  }

  const isBuiltInOwner = ownerUserId === null || ownerUserId === undefined || ownerUserId === 1
  let matches = false

  if (activeOwnerFilters.has('builtIn')) {
    matches = matches || isBuiltInOwner
  }

  if (activeOwnerFilters.has('builtInAndCurrentUser')) {
    matches =
      matches ||
      isBuiltInOwner ||
      (currentUserId !== null && ownerUserId === currentUserId)
  }

  if (activeOwnerFilters.has('allUsers')) {
    matches = matches || !isBuiltInOwner
  }

  if (activeOwnerFilters.has('currentUser')) {
    matches = matches || (currentUserId !== null && ownerUserId === currentUserId)
  }

  if (activeOwnerFilters.has('selectedUser')) {
    matches = matches || (selectedUserId !== null && ownerUserId === selectedUserId)
  }

  return matches
}

function useSelectedUserState(
  users: LibraryDbUserRecord[],
  currentUserId: number | null
): [number | null, (nextUserId: number) => void] {
  const [selectedUserId, setSelectedUserId] = useState<number | null>(currentUserId)

  useEffect(() => {
    if (users.length === 0) {
      setSelectedUserId(null)
      return
    }

    setSelectedUserId((previous) => {
      if (previous !== null && users.some((entry) => entry.user_id === previous)) {
        return previous
      }

      if (currentUserId !== null && users.some((entry) => entry.user_id === currentUserId)) {
        return currentUserId
      }

      return users[0].user_id
    })
  }, [currentUserId, users])

  const setSelected = (nextUserId: number) => {
    setSelectedUserId(nextUserId)
  }

  return [selectedUserId, setSelected]
}

function OwnerFilters({
  activeOwnerFilters,
  onToggleOwnerFilter,
  users,
  selectedUserId,
  onSelectedUserChange,
}: {
  activeOwnerFilters: Set<OwnerFilterKey>
  onToggleOwnerFilter: (filterKey: OwnerFilterKey) => void
  users: LibraryDbUserRecord[]
  selectedUserId: number | null
  onSelectedUserChange: (nextUserId: number) => void
}) {
  return (
    <div className="space-y-1">
      <div className="text-xs font-semibold text-gray-700">Owner filter</div>
      <div className="flex flex-wrap items-center gap-2">
        {OWNER_FILTER_ITEMS.map((entry) => {
          const isActive = activeOwnerFilters.has(entry.id)

          if (entry.id === 'selectedUser') {
            const isSelectedUserActive = activeOwnerFilters.has('selectedUser')
            return (
              <div key={entry.id} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onToggleOwnerFilter(entry.id)}
                  className={`ui-btn ${isActive ? 'border-blue-600 bg-blue-50 text-blue-700' : ''}`}
                >
                  {entry.label}
                </button>
                <select
                  className="ui-select w-48"
                  value={selectedUserId ?? ''}
                  onChange={(event) => onSelectedUserChange(Number(event.target.value))}
                  disabled={!isSelectedUserActive || users.length === 0}
                >
                  {users.map((user) => (
                    <option key={user.user_id} value={user.user_id}>
                      {buildUserLabel(user)}
                    </option>
                  ))}
                </select>
              </div>
            )
          }

          return (
            <button
              key={entry.id}
              type="button"
              onClick={() => onToggleOwnerFilter(entry.id)}
              className={`ui-btn ${isActive ? 'border-blue-600 bg-blue-50 text-blue-700' : ''}`}
            >
              {entry.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function MaterialClassificationFilters({
  axes,
  selectedFilters,
  onToggleValue,
  onClear,
}: {
  axes: MaterialClassificationAxisRecord[]
  selectedFilters: MaterialClassificationFilterState
  onToggleValue: (axisKey: string, valueKey: string) => void
  onClear: () => void
}) {
  if (axes.length === 0) {
    return null
  }

  const hasActiveFilters = hasActiveMaterialClassificationFilters(selectedFilters)

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold text-gray-700">Classification filter</div>
        <button
          type="button"
          onClick={onClear}
          className="text-[11px] font-medium text-slate-500 transition hover:text-slate-700 disabled:cursor-default disabled:text-slate-300"
          disabled={!hasActiveFilters}
        >
          Clear
        </button>
      </div>
      <div className="space-y-2">
        {axes.map((axis) => (
          <div key={axis.axis_id} className="space-y-1.5">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              {formatLibraryName(axis.name)}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {axis.values.map((value) => {
                const isActive = (selectedFilters[axis.key] ?? []).includes(value.key)
                return (
                  <button
                    key={value.value_id}
                    type="button"
                    onClick={() => onToggleValue(axis.key, value.key)}
                    className={`rounded-full border px-2.5 py-1 text-[11px] transition ${
                      isActive
                        ? 'border-sky-400 bg-sky-50 text-sky-700'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-800'
                    }`}
                  >
                    {formatLibraryName(value.name)}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

interface PowerLimitPoint {
  id: number | null
  force: number | null
  speed: number | null
}

interface CurveStyle {
  color: string
  symbol: 'circle' | 'square' | 'triangle' | 'diamond' | 'cross'
}

const CURVE_STYLES: CurveStyle[] = [
  { color: '#2563eb', symbol: 'circle' },
  { color: '#dc2626', symbol: 'square' },
  { color: '#059669', symbol: 'triangle' },
  { color: '#7c3aed', symbol: 'diamond' },
  { color: '#d97706', symbol: 'cross' },
  { color: '#db2777', symbol: 'circle' },
  { color: '#0f766e', symbol: 'square' },
  { color: '#7f1d1d', symbol: 'triangle' },
]

function getCurveStyle(index: number): CurveStyle {
  return CURVE_STYLES[index % CURVE_STYLES.length]
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) {
    return ''
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false'
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

function compareSortValues(left: unknown, right: unknown): number {
  const leftNumber = normalizeNumber(left)
  const rightNumber = normalizeNumber(right)

  if (leftNumber !== null && rightNumber !== null) {
    return leftNumber - rightNumber
  }

  const leftText = formatCellValue(left).toLowerCase()
  const rightText = formatCellValue(right).toLowerCase()
  if (leftText < rightText) {
    return -1
  }
  if (leftText > rightText) {
    return 1
  }
  return 0
}

function DiagramSymbol({
  symbol,
  x,
  y,
  color,
}: {
  symbol: CurveStyle['symbol']
  x: number
  y: number
  color: string
}) {
  if (symbol === 'square') {
    return <rect x={x - 3} y={y - 3} width={6} height={6} fill={color} />
  }
  if (symbol === 'triangle') {
    return <polygon points={`${x},${y - 4} ${x - 4},${y + 3} ${x + 4},${y + 3}`} fill={color} />
  }
  if (symbol === 'diamond') {
    return <polygon points={`${x},${y - 4} ${x - 4},${y} ${x},${y + 4} ${x + 4},${y}`} fill={color} />
  }
  if (symbol === 'cross') {
    return (
      <g stroke={color} strokeWidth={1.5}>
        <line x1={x - 3} y1={y - 3} x2={x + 3} y2={y + 3} />
        <line x1={x + 3} y1={y - 3} x2={x - 3} y2={y + 3} />
      </g>
    )
  }
  return <circle cx={x} cy={y} r={3} fill={color} />
}

function EmptyState({ message }: { message: string }) {
  return <div className="text-sm text-gray-500 py-4">{message}</div>
}

type MaterialVisualLoadState =
  | { status: 'loading' }
  | { status: 'loaded'; data: MaterialVisualRecord }
  | { status: 'error'; errorMessage: string }

const MATERIAL_CHART_COLORS = ['#2563eb', '#059669', '#dc2626', '#d97706']

function formatMaterialAxisLabel(axis: MaterialVisualAxisRecord): string {
  if (axis.unit && axis.unit.trim().length > 0) {
    return `${axis.label}, ${axis.unit}`
  }
  return axis.label
}

function formatMaterialChartValue(value: number): string {
  const absoluteValue = Math.abs(value)
  if (absoluteValue >= 1000) {
    return value.toFixed(0)
  }
  if (absoluteValue >= 100) {
    return value.toFixed(1)
  }
  if (absoluteValue >= 1) {
    return value.toFixed(2)
  }
  if (absoluteValue >= 0.01) {
    return value.toFixed(3)
  }
  return value.toExponential(1).replace('e', 'E')
}

function extractMaterialDiagramControlSummaries(
  controls: Record<string, unknown> | null | undefined
): Array<{ key: string; label: string; value: string }> {
  if (!controls) {
    return []
  }

  return Object.entries(controls).flatMap(([key, control]) => {
    if (!control || typeof control !== 'object') {
      return []
    }

    const record = control as Record<string, unknown>
    const label = typeof record.label === 'string' ? record.label : null
    const defaultValue = record.default
    if (!label || defaultValue === undefined || defaultValue === null) {
      return []
    }

    const numericValue = normalizeNumber(defaultValue)
    const formattedValue =
      numericValue !== null
        ? formatMaterialChartValue(numericValue)
        : typeof defaultValue === 'string'
          ? defaultValue
          : String(defaultValue)

    return [{ key, label, value: formattedValue }]
  })
}

interface MaterialChartBounds {
  minX: number
  maxX: number
  minY: number
  maxY: number
}

type MaterialChartScaleMode = 'auto' | 'manual'
type MaterialChartAxisKey = 'x' | 'y'
type MaterialChartAxisEdge = 'min' | 'max'

interface MaterialChartEditingState {
  axis: MaterialChartAxisKey
  edge: MaterialChartAxisEdge
  value: string
}

function buildMaterialChartBounds(points: Array<{ x: number; y: number }>): MaterialChartBounds {
  if (points.length === 0) {
    return {
      minX: 0,
      maxX: 1,
      minY: 0,
      maxY: 1,
    }
  }

  const rawMinX = Math.min(...points.map((entry) => entry.x))
  const rawMaxX = Math.max(...points.map((entry) => entry.x))
  const rawMinY = Math.min(...points.map((entry) => entry.y))
  const rawMaxY = Math.max(...points.map((entry) => entry.y))

  const rangeX = rawMaxX - rawMinX
  const rangeY = rawMaxY - rawMinY

  return {
    minX: rangeX === 0 ? rawMinX - 1 : rawMinX - rangeX * 0.05,
    maxX: rangeX === 0 ? rawMaxX + 1 : rawMaxX + rangeX * 0.05,
    minY: rangeY === 0 ? rawMinY - 1 : rawMinY - rangeY * 0.08,
    maxY: rangeY === 0 ? rawMaxY + 1 : rawMaxY + rangeY * 0.08,
  }
}

function buildMaterialChartTicks(min: number, max: number, count: number): number[] {
  const ticks: number[] = []
  for (let index = 0; index <= count; index += 1) {
    const ratio = index / count
    ticks.push(min + (max - min) * ratio)
  }

  if (min < 0 && max > 0) {
    ticks.push(0)
  }

  const deduped = Array.from(new Set(ticks.map((entry) => Number(entry.toFixed(6)))))
  deduped.sort((left, right) => left - right)
  return deduped
}

function validateMaterialChartBounds(bounds: MaterialChartBounds): string | null {
  if (!Number.isFinite(bounds.minX) || !Number.isFinite(bounds.maxX) || !Number.isFinite(bounds.minY) || !Number.isFinite(bounds.maxY)) {
    return 'Scale values must be finite numbers.'
  }

  if (bounds.minX >= bounds.maxX) {
    return 'X scale min must be less than max.'
  }

  if (bounds.minY >= bounds.maxY) {
    return 'Y scale min must be less than max.'
  }

  return null
}

function useMaterialChartScale(points: Array<{ x: number; y: number }>) {
  const autoBounds = useMemo(() => buildMaterialChartBounds(points), [points])
  const [scaleMode, setScaleMode] = useState<MaterialChartScaleMode>('auto')
  const [manualBounds, setManualBounds] = useState<MaterialChartBounds | null>(null)
  const [editingState, setEditingState] = useState<MaterialChartEditingState | null>(null)
  const [scaleError, setScaleError] = useState<string | null>(null)

  const activeBounds = scaleMode === 'manual' && manualBounds ? manualBounds : autoBounds

  const setAutoScale = useCallback(() => {
    setScaleMode('auto')
    setEditingState(null)
    setScaleError(null)
  }, [])

  const setManualScale = useCallback(() => {
    setScaleMode('manual')
    setManualBounds((previous) => previous ?? autoBounds)
    setScaleError(null)
  }, [autoBounds])

  const resetManualScale = useCallback(() => {
    setScaleMode('manual')
    setManualBounds(autoBounds)
    setEditingState(null)
    setScaleError(null)
  }, [autoBounds])

  const startEditingTick = useCallback((axis: MaterialChartAxisKey, edge: MaterialChartAxisEdge) => {
    if (scaleMode !== 'manual') {
      return
    }

    const currentValue =
      axis === 'x'
        ? edge === 'min'
          ? activeBounds.minX
          : activeBounds.maxX
        : edge === 'min'
          ? activeBounds.minY
          : activeBounds.maxY

    setEditingState({
      axis,
      edge,
      value: String(currentValue),
    })
    setScaleError(null)
  }, [activeBounds, scaleMode])

  const updateEditingValue = useCallback((value: string) => {
    setEditingState((previous) => {
      if (!previous) {
        return previous
      }

      return {
        ...previous,
        value,
      }
    })
  }, [])

  const cancelEditingTick = useCallback(() => {
    setEditingState(null)
    setScaleError(null)
  }, [])

  const submitEditingTick = useCallback(() => {
    if (!editingState) {
      return
    }

    const parsedValue = Number(editingState.value.trim())
    if (!Number.isFinite(parsedValue)) {
      setScaleError('Scale value must be a number.')
      return
    }

    const nextBounds = {
      ...(scaleMode === 'manual' && manualBounds ? manualBounds : autoBounds),
    }

    if (editingState.axis === 'x') {
      if (editingState.edge === 'min') {
        nextBounds.minX = parsedValue
      } else {
        nextBounds.maxX = parsedValue
      }
    } else if (editingState.edge === 'min') {
      nextBounds.minY = parsedValue
    } else {
      nextBounds.maxY = parsedValue
    }

    const validationError = validateMaterialChartBounds(nextBounds)
    if (validationError) {
      setScaleError(validationError)
      return
    }

    setManualBounds(nextBounds)
    setScaleMode('manual')
    setEditingState(null)
    setScaleError(null)
  }, [autoBounds, editingState, manualBounds, scaleMode])

  return {
    scaleMode,
    scaleError,
    activeBounds,
    editingState,
    setAutoScale,
    setManualScale,
    resetManualScale,
    startEditingTick,
    updateEditingValue,
    cancelEditingTick,
    submitEditingTick,
  }
}

function MaterialChartScaleToolbar({
  scaleMode,
  onSetAuto,
  onSetManual,
  onReset,
}: {
  scaleMode: MaterialChartScaleMode
  onSetAuto: () => void
  onSetManual: () => void
  onReset: () => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="text-[11px] uppercase tracking-[0.14em] text-slate-400">Scale</div>
      <button
        type="button"
        onClick={onSetAuto}
        className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition ${
          scaleMode === 'auto'
            ? 'border-sky-300 bg-sky-50 text-sky-700'
            : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
        }`}
      >
        Auto
      </button>
      <button
        type="button"
        onClick={onSetManual}
        className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition ${
          scaleMode === 'manual'
            ? 'border-sky-300 bg-sky-50 text-sky-700'
            : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
        }`}
      >
        Manual
      </button>
      <button
        type="button"
        onClick={onReset}
        className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 transition hover:border-slate-300"
      >
        Reset
      </button>
    </div>
  )
}

function EditableMaterialAxisTick({
  x,
  y,
  formattedValue,
  textAnchor,
  baseClassName,
  editable,
  editing,
  editValue,
  onEditValueChange,
  onStartEdit,
  onSubmit,
  onCancel,
}: {
  x: number
  y: number
  formattedValue: string
  textAnchor: 'middle' | 'end'
  baseClassName: string
  editable: boolean
  editing: boolean
  editValue: string
  onEditValueChange: (value: string) => void
  onStartEdit: () => void
  onSubmit: () => void
  onCancel: () => void
}) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [isHovered, setIsHovered] = useState(false)
  const textWidth = Math.max(24, formattedValue.length * 6.2)
  const iconSize = editable ? 8 : 0
  const iconGap = editable ? 5 : 0
  const hoverChipHeight = 20
  const hoverChipY = y - 13
  const hoverAccentClasses = editable && isHovered ? 'fill-sky-800 font-medium' : baseClassName

  useEffect(() => {
    if (!editing || !inputRef.current) {
      return
    }

    inputRef.current.focus()
    inputRef.current.select()
  }, [editing])

  if (editing) {
    const width = 78
    const height = 24
    const foreignX = textAnchor === 'middle' ? x - width / 2 : x - width
    const foreignY = y - 12

    return (
      <foreignObject x={foreignX} y={foreignY} width={width} height={height}>
        <div className="h-full w-full">
          <input
            ref={inputRef}
            value={editValue}
            onChange={(event) => onEditValueChange(event.target.value)}
            onBlur={onSubmit}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                onSubmit()
              }
              if (event.key === 'Escape') {
                event.preventDefault()
                onCancel()
              }
            }}
            className="h-full w-full rounded border border-sky-300 bg-white px-1.5 text-[11px] text-slate-700 shadow-sm outline-none"
          />
        </div>
      </foreignObject>
    )
  }

  const pillX =
    textAnchor === 'middle'
      ? x - textWidth / 2 - 8
      : x - textWidth - 16 - iconSize - iconGap
  const pillWidth = textWidth + 16 + iconSize + iconGap
  const iconCenterX =
    textAnchor === 'middle'
      ? pillX + pillWidth - 8 - iconSize / 2
      : pillX + 8 + iconSize / 2

  return (
    <g
      onMouseEnter={editable ? () => setIsHovered(true) : undefined}
      onMouseLeave={editable ? () => setIsHovered(false) : undefined}
      onClick={editable ? onStartEdit : undefined}
      className={editable ? 'cursor-pointer' : undefined}
    >
      {editable ? (
        <>
          <rect
            x={pillX}
            y={hoverChipY}
            width={pillWidth}
            height={hoverChipHeight}
            rx={10}
            ry={10}
            fill={isHovered ? '#e0f2fe' : 'transparent'}
            stroke={isHovered ? '#38bdf8' : 'transparent'}
            strokeWidth={1.2}
          />
          <path
            d={`M ${iconCenterX - 2.8} ${y + 4.1} L ${iconCenterX - 1.9} ${y + 0.7} L ${iconCenterX + 1.7} ${y - 2.9} L ${iconCenterX + 3.5} ${y - 1.1} L ${iconCenterX - 0.1} ${y + 2.5} Z M ${iconCenterX + 2.1} ${y - 3.5} L ${iconCenterX + 3.2} ${y - 4.6} L ${iconCenterX + 4.6} ${y - 3.2} L ${iconCenterX + 3.5} ${y - 1.9} Z`}
            fill={isHovered ? '#0369a1' : 'transparent'}
            opacity={isHovered ? 1 : 0}
            pointerEvents="none"
          />
        </>
      ) : null}
      <text
        x={x}
        y={y}
        textAnchor={textAnchor}
        className={`${hoverAccentClasses} text-[11px] transition-colors`}
        pointerEvents="none"
      >
        {formattedValue}
      </text>
    </g>
  )
}

export function MaterialDiagramCard({ diagram }: { diagram: MaterialVisualDiagramRecord }) {
  const controlSummaries = useMemo(() => {
    return extractMaterialDiagramControlSummaries(diagram.controls)
  }, [diagram.controls])

  const series = useMemo(() => {
    return diagram.series
      .map((entry, index) => ({
        ...entry,
        color: MATERIAL_CHART_COLORS[index % MATERIAL_CHART_COLORS.length],
        points: entry.points.filter(
          (point) => Number.isFinite(point.x) && Number.isFinite(point.y)
        ),
      }))
      .filter((entry) => entry.points.length > 0)
  }, [diagram.series])

  const allPoints = useMemo(() => {
    return series.flatMap((entry) => entry.points)
  }, [series])
  const {
    scaleMode,
    scaleError,
    activeBounds,
    editingState,
    setAutoScale,
    setManualScale,
    resetManualScale,
    startEditingTick,
    updateEditingValue,
    cancelEditingTick,
    submitEditingTick,
  } = useMaterialChartScale(allPoints)

  if (series.length === 0 || allPoints.length === 0) {
    return (
      <div className="rounded border border-gray-200 bg-white px-3 py-3">
        <div className="text-xs font-semibold text-gray-700">{diagram.title}</div>
        <div className="text-xs text-gray-500 mt-2">No diagram data available.</div>
      </div>
    )
  }

  const width = 420
  const height = 260
  const leftPadding = 52
  const rightPadding = 16
  const topPadding = 18
  const bottomPadding = 40
  const plotWidth = width - leftPadding - rightPadding
  const plotHeight = height - topPadding - bottomPadding
  const clipPathId = `material-diagram-clip-${useId().replace(/:/g, '')}`

  const { minX, maxX, minY, maxY } = activeBounds

  const scaleX = (value: number) => {
    if (maxX === minX) {
      return leftPadding + plotWidth / 2
    }
    return leftPadding + ((value - minX) / (maxX - minX)) * plotWidth
  }

  const scaleY = (value: number) => {
    if (maxY === minY) {
      return topPadding + plotHeight / 2
    }
    return height - bottomPadding - ((value - minY) / (maxY - minY)) * plotHeight
  }
  const xTickValues = buildMaterialChartTicks(minX, maxX, 4)
  const yTickValues = buildMaterialChartTicks(minY, maxY, 4)

  return (
    <div className="rounded border border-gray-200 bg-white px-3 py-3 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="text-xs font-semibold text-gray-700">{diagram.title}</div>
          {scaleError ? <div className="text-[11px] text-rose-600">{scaleError}</div> : null}
        </div>
        <div className="flex flex-col items-end gap-2">
          <MaterialChartScaleToolbar
            scaleMode={scaleMode}
            onSetAuto={setAutoScale}
            onSetManual={setManualScale}
            onReset={resetManualScale}
          />
          {series.length > 1 && (
            <div className="flex flex-wrap items-center justify-end gap-2">
              {series.map((entry) => (
                <div key={entry.key} className="flex items-center gap-1 text-[11px] text-gray-600">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                  <span>{entry.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {controlSummaries.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {controlSummaries.map((entry) => (
            <div
              key={entry.key}
              className="rounded border border-gray-200 bg-gray-50 px-2 py-1 text-[11px] text-gray-600"
            >
              {entry.label}: {entry.value}
            </div>
          ))}
        </div>
      )}

      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-56 border border-gray-200 rounded bg-white">
        <defs>
          <clipPath id={clipPathId}>
            <rect x={leftPadding} y={topPadding} width={plotWidth} height={plotHeight} />
          </clipPath>
        </defs>

        {xTickValues.map((xValue, index) => {
          const x = scaleX(xValue)
          const isZero = Math.abs(xValue) < 1e-9
          const edge = index === 0 ? 'min' : index === xTickValues.length - 1 ? 'max' : null
          const isEditable = scaleMode === 'manual' && edge !== null
          const isEditing = editingState?.axis === 'x' && editingState.edge === edge

          return (
            <g key={`material-x-grid-${diagram.key}-${xValue}`}>
              <line
                x1={x}
                y1={topPadding}
                x2={x}
                y2={height - bottomPadding}
                stroke={isZero ? '#9ca3af' : '#e5e7eb'}
                strokeWidth={isZero ? 1.2 : 1}
              />
              <EditableMaterialAxisTick
                x={x}
                y={height - bottomPadding + 16}
                formattedValue={formatMaterialChartValue(xValue)}
                textAnchor="middle"
                baseClassName="fill-gray-600"
                editable={isEditable}
                editing={Boolean(isEditing)}
                editValue={isEditing ? editingState?.value ?? '' : ''}
                onEditValueChange={updateEditingValue}
                onStartEdit={() => {
                  if (edge) {
                    startEditingTick('x', edge)
                  }
                }}
                onSubmit={submitEditingTick}
                onCancel={cancelEditingTick}
              />
            </g>
          )
        })}

        {yTickValues.map((yValue, index) => {
          const y = scaleY(yValue)
          const isZero = Math.abs(yValue) < 1e-9
          const edge = index === 0 ? 'min' : index === yTickValues.length - 1 ? 'max' : null
          const isEditable = scaleMode === 'manual' && edge !== null
          const isEditing = editingState?.axis === 'y' && editingState.edge === edge

          return (
            <g key={`material-y-grid-${diagram.key}-${yValue}`}>
              <line
                x1={leftPadding}
                y1={y}
                x2={width - rightPadding}
                y2={y}
                stroke={isZero ? '#9ca3af' : '#e5e7eb'}
                strokeWidth={isZero ? 1.2 : 1}
              />
              <EditableMaterialAxisTick
                x={leftPadding - 8}
                y={y + 3}
                formattedValue={formatMaterialChartValue(yValue)}
                textAnchor="end"
                baseClassName="fill-gray-600"
                editable={isEditable}
                editing={Boolean(isEditing)}
                editValue={isEditing ? editingState?.value ?? '' : ''}
                onEditValueChange={updateEditingValue}
                onStartEdit={() => {
                  if (edge) {
                    startEditingTick('y', edge)
                  }
                }}
                onSubmit={submitEditingTick}
                onCancel={cancelEditingTick}
              />
            </g>
          )
        })}

        <line
          x1={leftPadding}
          y1={height - bottomPadding}
          x2={width - rightPadding}
          y2={height - bottomPadding}
          stroke="#6b7280"
          strokeWidth={1.2}
        />
        <line
          x1={leftPadding}
          y1={topPadding}
          x2={leftPadding}
          y2={height - bottomPadding}
          stroke="#6b7280"
          strokeWidth={1.2}
        />

        <g clipPath={`url(#${clipPathId})`}>
          {series.map((entry) => {
            const polylinePoints = entry.points
              .map((point) => `${scaleX(point.x)},${scaleY(point.y)}`)
              .join(' ')

            return (
              <g key={entry.key}>
                <polyline
                  fill="none"
                  stroke={entry.color}
                  strokeWidth={2.2}
                  points={polylinePoints}
                />
                {entry.points.map((point, pointIndex) => {
                  const x = scaleX(point.x)
                  const y = scaleY(point.y)
                  return <circle key={`${entry.key}-${pointIndex}`} cx={x} cy={y} r={2.5} fill={entry.color} />
                })}
              </g>
            )
          })}
        </g>

        <text
          x={leftPadding + (width - leftPadding - rightPadding) / 2}
          y={height - 10}
          textAnchor="middle"
          className="fill-gray-700 text-[12px]"
        >
          {formatMaterialAxisLabel(diagram.x_axis)}
        </text>
        <text
          x={18}
          y={topPadding + (height - topPadding - bottomPadding) / 2}
          textAnchor="middle"
          transform={`rotate(-90 18 ${topPadding + (height - topPadding - bottomPadding) / 2})`}
          className="fill-gray-700 text-[12px]"
        >
          {formatMaterialAxisLabel(diagram.y_axis)}
        </text>
      </svg>
    </div>
  )
}

export interface LibraryDiesViewProps {
  dies: DieRecord[]
  dieTypes: DieTypeRecord[]
  users: LibraryDbUserRecord[]
  currentUserId: number | null
  selectedDieId: number | null
  onSelectDieId: (nextId: number | null) => void
  isLoading: boolean
  error: string | null
}

export function LibraryDiesView({
  dies,
  dieTypes,
  users,
  currentUserId,
  selectedDieId,
  onSelectDieId,
  isLoading,
  error,
}: LibraryDiesViewProps) {
  const [textFilter, setTextFilter] = useState('')
  const [selectedTypeFilters, setSelectedTypeFilters] = useState<Set<string>>(new Set(['all']))
  const [ownerFilters, setOwnerFilters] = useState<Set<OwnerFilterKey>>(new Set(DEFAULT_OWNER_FILTERS))
  const [selectedUserId, setSelectedUserId] = useSelectedUserState(users, currentUserId)

  const usersById = useMemo(() => {
    return new Map(users.map((entry) => [entry.user_id, entry]))
  }, [users])

  const dieTypesById = useMemo(() => {
    return new Map(dieTypes.map((entry) => [entry.id, formatLibraryName(entry.name)]))
  }, [dieTypes])

  const normalizedFilter = textFilter.trim().toLowerCase()

  const filteredDies = useMemo(() => {
    return dies.filter((entry) => {
      const typeMatch =
        selectedTypeFilters.has('all') || selectedTypeFilters.has(String(entry.die_type_id))
      if (!typeMatch) {
        return false
      }

      const ownerMatch = matchesOwnerFilter(
        entry.owner_user_id,
        ownerFilters,
        currentUserId,
        selectedUserId
      )
      if (!ownerMatch) {
        return false
      }

      if (!normalizedFilter) {
        return true
      }

      const name = formatLibraryName(entry.name).toLowerCase()
      const inventory = (entry.inventory_number || '').toLowerCase()
      const haystack = `${entry.id} ${name} ${inventory}`
      return haystack.includes(normalizedFilter)
    })
  }, [currentUserId, dies, normalizedFilter, ownerFilters, selectedTypeFilters, selectedUserId])

  const toggleTypeFilter = (filterId: string) => {
    setSelectedTypeFilters((previous) => toggleFilter(previous, filterId))
  }

  const toggleOwnerFilter = (filterKey: OwnerFilterKey) => {
    setOwnerFilters((previous) => toggleFilter(previous, filterKey))
  }

  return (
    <div className="h-full min-h-0 flex flex-col bg-gray-50">
      <div className="ui-pane-header space-y-2">
        <div className="ui-pane-title">Dies</div>
        <input
          type="text"
          className="ui-input"
          value={textFilter}
          onChange={(event) => setTextFilter(event.target.value)}
          placeholder="Filter dies by id, name, inventory..."
        />
        <div className="space-y-1">
          <div className="text-xs font-semibold text-gray-700">Type filter</div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => toggleTypeFilter('all')}
              className={`ui-btn ${selectedTypeFilters.has('all') ? 'border-blue-600 bg-blue-50 text-blue-700' : ''}`}
            >
              All types
            </button>
            {dieTypes.map((entry) => {
              const key = String(entry.id)
              const isActive = selectedTypeFilters.has(key)
              return (
                <button
                  key={entry.id}
                  type="button"
                  onClick={() => toggleTypeFilter(key)}
                  className={`ui-btn ${isActive ? 'border-blue-600 bg-blue-50 text-blue-700' : ''}`}
                >
                  {formatLibraryName(entry.name)}
                </button>
              )
            })}
          </div>
        </div>

        <OwnerFilters
          activeOwnerFilters={ownerFilters}
          onToggleOwnerFilter={toggleOwnerFilter}
          users={users}
          selectedUserId={selectedUserId}
          onSelectedUserChange={setSelectedUserId}
        />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
        {error && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</div>}
        {isLoading && <EmptyState message="Loading dies..." />}
        {!isLoading && filteredDies.length === 0 && <EmptyState message="No dies found for active filters." />}

        {!isLoading &&
          filteredDies.map((entry) => {
            const isSelected = selectedDieId === entry.id
            const dieTypeName = dieTypesById.get(entry.die_type_id) || `Type ${entry.die_type_id}`

            return (
              <div
                key={entry.id}
                onClick={() => onSelectDieId(isSelected ? null : entry.id)}
                onKeyDown={(event) => {
                  if (event.target !== event.currentTarget) {
                    return
                  }
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onSelectDieId(isSelected ? null : entry.id)
                  }
                }}
                role="button"
                tabIndex={0}
                className={`ui-card ui-card-body w-full text-left space-y-2 ${
                  isSelected ? 'border-blue-600 bg-blue-50' : ''
                }`}
              >
                <div className="font-semibold text-sm text-gray-900">{formatLibraryName(entry.name)}</div>
                <div className="flex items-start gap-3">
                  <div className="w-48 sm:w-56 aspect-square shrink-0">
                    <DieStlPreview
                      className="h-full w-full"
                      stlFileUrl={entry.stl_file_url}
                      stlFileExists={entry.stl_file_exists}
                    />
                  </div>
                  <div className="flex-1 min-w-0 space-y-1 text-xs text-gray-700">
                    <div>ID: {entry.id}</div>
                    <div>Type: {dieTypeName}</div>
                    <div>Owner: {getOwnerLabel(entry.owner_user_id, usersById)}</div>
                    <div>Inventory: {entry.inventory_number || '-'}</div>
                    <div>Template: {entry.die_template_file_name || '-'}</div>
                    <div>Created: {formatTimestamp(entry.created_at)}</div>
                    <div>Obsolete: {entry.is_obsolete ? 'Yes' : 'No'}</div>
                  </div>
                </div>
              </div>
            )
          })}
      </div>
    </div>
  )
}

export interface LibraryDieAssembliesViewProps {
  dieAssemblies: DieAssemblyRecord[]
  users: LibraryDbUserRecord[]
  currentUserId: number | null
  selectedDieAssemblyId: number | null
  onSelectDieAssemblyId: (nextId: number | null) => void
  isLoading: boolean
  error: string | null
}

export function LibraryDieAssembliesView({
  dieAssemblies,
  users,
  currentUserId,
  selectedDieAssemblyId,
  onSelectDieAssemblyId,
  isLoading,
  error,
}: LibraryDieAssembliesViewProps) {
  const [textFilter, setTextFilter] = useState('')
  const [ownerFilters, setOwnerFilters] = useState<Set<OwnerFilterKey>>(new Set(DEFAULT_OWNER_FILTERS))
  const [selectedUserId, setSelectedUserId] = useSelectedUserState(users, currentUserId)

  const usersById = useMemo(() => {
    return new Map(users.map((entry) => [entry.user_id, entry]))
  }, [users])

  const normalizedFilter = textFilter.trim().toLowerCase()

  const filteredAssemblies = useMemo(() => {
    return dieAssemblies.filter((entry) => {
      const ownerMatch = matchesOwnerFilter(
        entry.owner_user_id,
        ownerFilters,
        currentUserId,
        selectedUserId
      )
      if (!ownerMatch) {
        return false
      }

      if (!normalizedFilter) {
        return true
      }

      const name = formatLibraryName(entry.name).toLowerCase()
      const haystack = `${entry.id} ${name}`
      return haystack.includes(normalizedFilter)
    })
  }, [currentUserId, dieAssemblies, normalizedFilter, ownerFilters, selectedUserId])

  const toggleOwnerFilter = (filterKey: OwnerFilterKey) => {
    setOwnerFilters((previous) => toggleFilter(previous, filterKey))
  }

  return (
    <div className="h-full min-h-0 flex flex-col bg-gray-50">
      <div className="ui-pane-header space-y-2">
        <div className="ui-pane-title">Die Assemblies</div>
        <input
          type="text"
          className="ui-input"
          value={textFilter}
          onChange={(event) => setTextFilter(event.target.value)}
          placeholder="Filter die assemblies by id or name..."
        />

        <OwnerFilters
          activeOwnerFilters={ownerFilters}
          onToggleOwnerFilter={toggleOwnerFilter}
          users={users}
          selectedUserId={selectedUserId}
          onSelectedUserChange={setSelectedUserId}
        />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
        {error && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</div>}
        {isLoading && <EmptyState message="Loading die assemblies..." />}
        {!isLoading && filteredAssemblies.length === 0 && <EmptyState message="No die assemblies found for active filters." />}

        {!isLoading &&
          filteredAssemblies.map((entry) => {
            const isSelected = selectedDieAssemblyId === entry.id

            return (
              <button
                key={entry.id}
                type="button"
                onClick={() => onSelectDieAssemblyId(isSelected ? null : entry.id)}
                className={`ui-card ui-card-body w-full text-left space-y-2 ${
                  isSelected ? 'border-blue-600 bg-blue-50' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="font-semibold text-sm text-gray-900">{formatLibraryName(entry.name)}</div>
                  <div className="text-xs text-gray-500">ID: {entry.id}</div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-700">
                  <div>Owner: {getOwnerLabel(entry.owner_user_id, usersById)}</div>
                  <div>Obsolete: {entry.is_obsolete ? 'Yes' : 'No'}</div>
                  <div>Top die: {entry.top_die_id ?? '-'}</div>
                  <div>Bottom die: {entry.bottom_die_id ?? '-'}</div>
                  <div>Left die: {entry.left_die_id ?? '-'}</div>
                  <div>Right die: {entry.right_die_id ?? '-'}</div>
                  <div>Created: {formatTimestamp(entry.created_at)}</div>
                </div>
              </button>
            )
          })}
      </div>
    </div>
  )
}

export interface LibraryMaterialsViewProps {
  materials: MaterialRecord[]
  materialClassificationCatalog: MaterialClassificationCatalogRecord | null
  users: LibraryDbUserRecord[]
  currentUserId: number | null
  selectedMaterialId: number | null
  onSelectMaterialId: (nextId: number | null) => void
  isMaterialListVisible: boolean
  isLoading: boolean
  error: string | null
}

interface DashboardMaterialSeries {
  materialId: number
  materialName: string
  color: string
  points: Array<{ x: number; y: number }>
}

interface DashboardMaterialDiagram {
  key: string
  title: string
  kind: string
  x_axis: MaterialVisualAxisRecord
  y_axis: MaterialVisualAxisRecord
  controls?: Record<string, unknown> | null
  series: DashboardMaterialSeries[]
}

const DASHBOARD_MATERIAL_COLORS = [
  '#2563eb',
  '#dc2626',
  '#059669',
  '#d97706',
  '#7c3aed',
  '#0f766e',
  '#db2777',
  '#4338ca',
  '#b45309',
  '#be123c',
  '#0f766e',
  '#1d4ed8',
]

function buildMaterialSearchText(entry: MaterialRecord): string {
  const name = formatLibraryName(entry.name).toLowerCase()
  return `${entry.material_id} ${name} ${entry.deform_file_name || ''} ${entry.note || ''}`.toLowerCase()
}

function filterMaterialsForLibrary(
  materials: MaterialRecord[],
  normalizedFilter: string,
  ownerFilters: Set<OwnerFilterKey>,
  currentUserId: number | null,
  selectedUserId: number | null
): MaterialRecord[] {
  return materials.filter((entry) => {
    const ownerMatch = matchesOwnerFilter(
      entry.owner_id,
      ownerFilters,
      currentUserId,
      selectedUserId
    )
    if (!ownerMatch) {
      return false
    }

    if (!normalizedFilter) {
      return true
    }

    return buildMaterialSearchText(entry).includes(normalizedFilter)
  })
}

type MaterialClassificationFilterState = Record<string, string[]>

function getMaterialClassificationHierarchyLevel(
  axis: Pick<MaterialClassificationAxisRecord, 'hierarchy_level'> | null | undefined
): number {
  const level = axis?.hierarchy_level
  return level === 1 || level === 2 || level === 3 ? level : 3
}

function sortMaterialClassificationAxes(
  axes: MaterialClassificationAxisRecord[]
): MaterialClassificationAxisRecord[] {
  return [...axes].sort((left, right) => {
    return (
      getMaterialClassificationHierarchyLevel(left) - getMaterialClassificationHierarchyLevel(right) ||
      left.sort_order - right.sort_order ||
      formatLibraryName(left.name).localeCompare(formatLibraryName(right.name)) ||
      left.axis_id - right.axis_id
    )
  })
}

function buildMaterialClassificationAxisByKey(
  catalog: MaterialClassificationCatalogRecord | null
): Map<string, MaterialClassificationAxisRecord> {
  const axisByKey = new Map<string, MaterialClassificationAxisRecord>()
  ;(catalog?.axes ?? []).forEach((axis) => {
    axisByKey.set(axis.key, axis)
  })
  return axisByKey
}

function hasActiveMaterialClassificationFilters(filters: MaterialClassificationFilterState): boolean {
  return Object.values(filters).some((values) => values.length > 0)
}

function areMaterialClassificationFilterStatesEqual(
  left: MaterialClassificationFilterState,
  right: MaterialClassificationFilterState
): boolean {
  const leftKeys = Object.keys(left)
  const rightKeys = Object.keys(right)
  if (leftKeys.length !== rightKeys.length) {
    return false
  }

  return leftKeys.every((axisKey) => {
    const leftValues = left[axisKey] ?? []
    const rightValues = right[axisKey] ?? []
    if (leftValues.length !== rightValues.length) {
      return false
    }
    return leftValues.every((value, index) => value === rightValues[index])
  })
}

function toggleMaterialClassificationFilterValue(
  current: MaterialClassificationFilterState,
  axisKey: string,
  valueKey: string
): MaterialClassificationFilterState {
  const currentValues = current[axisKey] ?? []
  const nextValues = currentValues.includes(valueKey)
    ? currentValues.filter((entry) => entry !== valueKey)
    : [...currentValues, valueKey]

  if (nextValues.length === 0) {
    const { [axisKey]: _removed, ...rest } = current
    return rest
  }

  return {
    ...current,
    [axisKey]: nextValues,
  }
}

function matchesMaterialClassificationFilters(
  material: MaterialRecord,
  filters: MaterialClassificationFilterState,
  axisByKey?: Map<string, MaterialClassificationAxisRecord>,
  maxHierarchyLevel?: number
): boolean {
  if (!hasActiveMaterialClassificationFilters(filters)) {
    return true
  }

  return Object.entries(filters).every(([axisKey, selectedValues]) => {
    if (selectedValues.length === 0) {
      return true
    }
    if (maxHierarchyLevel !== undefined) {
      const axisLevel = getMaterialClassificationHierarchyLevel(axisByKey?.get(axisKey))
      if (axisLevel > maxHierarchyLevel) {
        return true
      }
    }
    const materialValues = material.classifications[axisKey] ?? []
    return selectedValues.some((valueKey) => materialValues.includes(valueKey))
  })
}

function buildMaterialClassificationFilterAxes(
  catalog: MaterialClassificationCatalogRecord | null,
  materials: MaterialRecord[],
  selectedFilters: MaterialClassificationFilterState
): MaterialClassificationAxisRecord[] {
  const axes = sortMaterialClassificationAxes(
    (catalog?.axes ?? [])
      .filter((axis) => axis.is_filter_visible && !axis.is_obsolete)
      .map((axis) => ({
        ...axis,
        values: axis.values.filter((value) => !value.is_obsolete),
      }))
  )
  const axisByKey = new Map(axes.map((axis) => [axis.key, axis]))

  return axes.map((axis) => {
    const parentHierarchyLevel = getMaterialClassificationHierarchyLevel(axis) - 1
    const scopedMaterials =
      parentHierarchyLevel <= 0
        ? materials
        : materials.filter((material) =>
            matchesMaterialClassificationFilters(
              material,
              selectedFilters,
              axisByKey,
              parentHierarchyLevel
            )
          )
    const availableValueKeys = new Set<string>()
    scopedMaterials.forEach((material) => {
      ;(material.classifications[axis.key] ?? []).forEach((valueKey) => {
        availableValueKeys.add(valueKey)
      })
    })

    return {
      ...axis,
      values: axis.values
        .filter((value) => availableValueKeys.has(value.key))
        .sort((left, right) => left.sort_order - right.sort_order || left.value_id - right.value_id),
    }
  })
}

function pruneMaterialClassificationFilters(
  filters: MaterialClassificationFilterState,
  axes: MaterialClassificationAxisRecord[]
): MaterialClassificationFilterState {
  const allowedValuesByAxis = new Map(
    axes.map((axis) => [axis.key, new Set(axis.values.map((value) => value.key))])
  )
  const next: MaterialClassificationFilterState = {}

  Object.entries(filters).forEach(([axisKey, values]) => {
    const allowedValues = allowedValuesByAxis.get(axisKey)
    if (!allowedValues) {
      return
    }
    const nextValues = values.filter((value) => allowedValues.has(value))
    if (nextValues.length > 0) {
      next[axisKey] = nextValues
    }
  })

  return next
}

interface MaterialClassificationComparisonValue {
  key: string
  label: string
  state: 'selected' | 'other'
}

interface MaterialClassificationComparisonRow {
  axisKey: string
  axisLabel: string
  values: MaterialClassificationComparisonValue[]
}

function buildMaterialClassificationBranchFilters(
  material: MaterialRecord,
  axes: MaterialClassificationAxisRecord[],
  maxHierarchyLevel: number
): MaterialClassificationFilterState {
  const next: MaterialClassificationFilterState = {}

  axes.forEach((axis) => {
    if (getMaterialClassificationHierarchyLevel(axis) > maxHierarchyLevel) {
      return
    }
    const values = material.classifications[axis.key] ?? []
    if (values.length > 0) {
      next[axis.key] = values
    }
  })

  return next
}

function buildMaterialClassificationComparisonRows(
  material: MaterialRecord,
  visibleMaterials: MaterialRecord[],
  catalog: MaterialClassificationCatalogRecord | null
): MaterialClassificationComparisonRow[] {
  const formatFallbackAxisLabel = (axisKey: string) =>
    axisKey.split('_').map((token) => token.charAt(0).toUpperCase() + token.slice(1)).join(' ')
  const axes = sortMaterialClassificationAxes((catalog?.axes ?? []).filter((axis) => !axis.is_obsolete))
  const axisByKey = new Map(axes.map((axis) => [axis.key, axis]))

  return axes.flatMap((axis) => {
    const hierarchyLevel = getMaterialClassificationHierarchyLevel(axis)
    const branchFilters = buildMaterialClassificationBranchFilters(material, axes, hierarchyLevel - 1)
    const scopedMaterials =
      hierarchyLevel <= 1
        ? visibleMaterials
        : visibleMaterials.filter((entry) =>
            matchesMaterialClassificationFilters(
              entry,
              branchFilters,
              axisByKey,
              hierarchyLevel - 1
            )
          )
    const visibleValues = new Set<string>()
    scopedMaterials.forEach((entry) => {
      ;(entry.classifications[axis.key] ?? []).forEach((valueKey) => {
        visibleValues.add(valueKey)
      })
    })

    if (visibleValues.size === 0) {
      return []
    }

    const axisKey = axis.key
    const selectedValues = new Set(material.classifications[axisKey] ?? [])
    const orderedValueKeys: string[] = []

    axis.values
      .filter((entry) => !entry.is_obsolete && visibleValues.has(entry.key))
      .sort((left, right) => left.sort_order - right.sort_order || left.value_id - right.value_id)
      .forEach((entry) => {
        orderedValueKeys.push(entry.key)
      })

    Array.from(visibleValues)
      .filter((valueKey) => !orderedValueKeys.includes(valueKey))
      .sort((left, right) => left.localeCompare(right))
      .forEach((valueKey) => {
        orderedValueKeys.push(valueKey)
      })

    const values = orderedValueKeys.map((valueKey) => {
      const value = axis?.values.find((entry) => entry.key === valueKey)
      const state: MaterialClassificationComparisonValue['state'] = selectedValues.has(valueKey)
        ? 'selected'
        : 'other'
      return {
        key: valueKey,
        label: value ? formatLibraryName(value.name) : valueKey,
        state,
      }
    })

    return {
      axisKey,
      axisLabel: formatLibraryName(axis.name) || formatFallbackAxisLabel(axisKey),
      values,
    }
  })
}

function useMaterialVisualStore() {
  const [materialVisualStates, setMaterialVisualStates] = useState<Record<number, MaterialVisualLoadState>>({})
  const materialVisualStatesRef = useRef<Record<number, MaterialVisualLoadState>>({})

  useEffect(() => {
    materialVisualStatesRef.current = materialVisualStates
  }, [materialVisualStates])

  const fetchMaterialVisuals = useCallback(async (materialId: number, options?: { force?: boolean }) => {
    const force = options?.force ?? false
    const currentState = materialVisualStatesRef.current[materialId]
    if (!force && (currentState?.status === 'loading' || currentState?.status === 'loaded')) {
      return
    }

    const loadingState: MaterialVisualLoadState = { status: 'loading' }
    materialVisualStatesRef.current = {
      ...materialVisualStatesRef.current,
      [materialId]: loadingState,
    }
    setMaterialVisualStates((previous) => ({
      ...previous,
      [materialId]: loadingState,
    }))

    const response = await apiClient.get<MaterialVisualRecord>(`/library/db/materials/${materialId}/visuals`)

    const nextState: MaterialVisualLoadState =
      response.ok && response.data
        ? {
            status: 'loaded',
            data: response.data,
          }
        : {
            status: 'error',
            errorMessage: response.errorMessage || 'Failed to load material diagrams.',
          }

    materialVisualStatesRef.current = {
      ...materialVisualStatesRef.current,
      [materialId]: nextState,
    }
    setMaterialVisualStates((previous) => ({
      ...previous,
      [materialId]: nextState,
    }))
  }, [])

  return {
    materialVisualStates,
    fetchMaterialVisuals,
  }
}

function extractPrimaryMaterialSeries(diagram: MaterialVisualDiagramRecord): MaterialVisualSeriesRecord | null {
  for (const entry of diagram.series) {
    const points = entry.points.filter(
      (point) => Number.isFinite(point.x) && Number.isFinite(point.y)
    )
    if (points.length > 0) {
      return {
        ...entry,
        points,
      }
    }
  }

  return null
}

function getDashboardMaterialColor(index: number): string {
  if (index >= 0 && index < DASHBOARD_MATERIAL_COLORS.length) {
    return DASHBOARD_MATERIAL_COLORS[index]
  }

  const hue = (index * 41) % 360
  return `hsl(${hue} 70% 42%)`
}

const MATERIAL_CHEMISTRY_ELEMENT_ORDER = [
  'Ni',
  'Cr',
  'Fe',
  'Nb',
  'Nb+Ta',
  'Ta',
  'Mo',
  'Ti',
  'Al',
  'Co',
  'Cu',
  'Mn',
  'Si',
  'C',
  'P',
  'S',
  'B',
  'O',
  'N',
  'H',
]

function parseMaterialChemistryLimitSortValue(limit: string | null | undefined): {
  category: number
  numericValue: number | null
} {
  const normalized = (limit ?? '').trim()
  if (!normalized) {
    return {
      category: 2,
      numericValue: null,
    }
  }

  if (normalized.toLowerCase() === 'bal') {
    return {
      category: 3,
      numericValue: null,
    }
  }

  if (normalized.includes('-')) {
    const parts = normalized
      .split('-')
      .map((entry) => Number(entry.trim()))
      .filter((entry) => Number.isFinite(entry))
    return {
      category: 0,
      numericValue: parts.length > 0 ? Math.max(...parts) : null,
    }
  }

  if (normalized.startsWith('<') || normalized.startsWith('>')) {
    const parsedValue = Number(normalized.slice(1).trim())
    return {
      category: 1,
      numericValue: Number.isFinite(parsedValue) ? parsedValue : null,
    }
  }

  const parsedValue = Number(normalized)
  return {
    category: Number.isFinite(parsedValue) ? 0 : 2,
    numericValue: Number.isFinite(parsedValue) ? parsedValue : null,
  }
}

function sortMaterialChemistryElements(
  elements: Iterable<string>,
  referenceChemistryLimits?: Record<string, string>
): string[] {
  const preferredOrder = new Map(MATERIAL_CHEMISTRY_ELEMENT_ORDER.map((value, index) => [value, index]))

  return Array.from(new Set(elements)).sort((left, right) => {
    const leftSortValue = parseMaterialChemistryLimitSortValue(referenceChemistryLimits?.[left])
    const rightSortValue = parseMaterialChemistryLimitSortValue(referenceChemistryLimits?.[right])

    if (leftSortValue.category !== rightSortValue.category) {
      return leftSortValue.category - rightSortValue.category
    }

    if (leftSortValue.numericValue !== null || rightSortValue.numericValue !== null) {
      return (rightSortValue.numericValue ?? Number.NEGATIVE_INFINITY) - (leftSortValue.numericValue ?? Number.NEGATIVE_INFINITY)
    }

    const leftRank = preferredOrder.get(left)
    const rightRank = preferredOrder.get(right)

    if (leftRank !== undefined || rightRank !== undefined) {
      return (leftRank ?? Number.MAX_SAFE_INTEGER) - (rightRank ?? Number.MAX_SAFE_INTEGER)
    }

    return left.localeCompare(right)
  })
}

function buildDashboardMaterialDiagrams(
  materials: MaterialRecord[],
  materialVisualStates: Record<number, MaterialVisualLoadState>
): DashboardMaterialDiagram[] {
  const materialIndexById = new Map(materials.map((entry, index) => [entry.material_id, index]))
  const groupedDiagrams = new Map<string, DashboardMaterialDiagram>()

  for (const material of materials) {
    const state = materialVisualStates[material.material_id]
    if (!state || state.status !== 'loaded') {
      continue
    }

    const materialName = formatLibraryName(material.name)
    const materialIndex = materialIndexById.get(material.material_id) ?? 0

    for (const diagram of state.data.diagrams) {
      const primarySeries = extractPrimaryMaterialSeries(diagram)
      if (!primarySeries) {
        continue
      }

      let group = groupedDiagrams.get(diagram.key)
      if (!group) {
        group = {
          key: diagram.key,
          title: diagram.title,
          kind: diagram.kind,
          x_axis: diagram.x_axis,
          y_axis: diagram.y_axis,
          controls: diagram.controls,
          series: [],
        }
        groupedDiagrams.set(diagram.key, group)
      }

      group.series.push({
        materialId: material.material_id,
        materialName,
        color: getDashboardMaterialColor(materialIndex),
        points: primarySeries.points,
      })
    }
  }

  return Array.from(groupedDiagrams.values()).map((entry) => ({
    ...entry,
    series: [...entry.series].sort((left, right) => {
      return (materialIndexById.get(left.materialId) ?? 0) - (materialIndexById.get(right.materialId) ?? 0)
    }),
  }))
}

function sortMaterialIdsByVisibleOrder(
  ids: Iterable<number>,
  materials: MaterialRecord[]
): number[] {
  const visibleOrder = new Map(materials.map((entry, index) => [entry.material_id, index]))
  return Array.from(new Set(ids))
    .filter((id) => visibleOrder.has(id))
    .sort((left, right) => (visibleOrder.get(left) ?? 0) - (visibleOrder.get(right) ?? 0))
}

function MaterialDashboardDiagramCard({
  diagram,
  selectedMaterialIds,
  totalMaterialCount,
}: {
  diagram: DashboardMaterialDiagram
  selectedMaterialIds: number[]
  totalMaterialCount: number
}) {
  const selectedMaterialIdSet = useMemo(() => new Set(selectedMaterialIds), [selectedMaterialIds])
  const controlSummaries = useMemo(() => {
    return extractMaterialDiagramControlSummaries(diagram.controls)
  }, [diagram.controls])

  const allPoints = useMemo(() => {
    return diagram.series.flatMap((entry) => entry.points)
  }, [diagram.series])
  const hasActiveSelection = selectedMaterialIdSet.size > 0
  const {
    scaleMode,
    scaleError,
    activeBounds,
    editingState,
    setAutoScale,
    setManualScale,
    resetManualScale,
    startEditingTick,
    updateEditingValue,
    cancelEditingTick,
    submitEditingTick,
  } = useMaterialChartScale(allPoints)

  if (diagram.series.length === 0 || allPoints.length === 0) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white/95 px-4 py-4 shadow-sm">
        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{diagram.title}</div>
        <div className="mt-2 text-sm text-slate-500">No comparable diagram data is available.</div>
      </div>
    )
  }

  const width = 460
  const height = 280
  const leftPadding = 54
  const rightPadding = 18
  const topPadding = 18
  const bottomPadding = 42
  const plotWidth = width - leftPadding - rightPadding
  const plotHeight = height - topPadding - bottomPadding
  const clipPathId = `material-dashboard-clip-${useId().replace(/:/g, '')}`

  const { minX, maxX, minY, maxY } = activeBounds

  const scaleX = (value: number) => {
    if (maxX === minX) {
      return leftPadding + plotWidth / 2
    }
    return leftPadding + ((value - minX) / (maxX - minX)) * plotWidth
  }

  const scaleY = (value: number) => {
    if (maxY === minY) {
      return topPadding + plotHeight / 2
    }
    return height - bottomPadding - ((value - minY) / (maxY - minY)) * plotHeight
  }
  const xTickValues = buildMaterialChartTicks(minX, maxX, 4)
  const yTickValues = buildMaterialChartTicks(minY, maxY, 4)
  const orderedSeries = [...diagram.series].sort((left, right) => {
    const leftSelected = selectedMaterialIdSet.has(left.materialId) ? 1 : 0
    const rightSelected = selectedMaterialIdSet.has(right.materialId) ? 1 : 0
    return leftSelected - rightSelected
  })

  return (
    <div className="rounded-3xl border border-slate-200 bg-white/95 px-4 py-4 shadow-sm backdrop-blur space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{diagram.title}</div>
          <div className="mt-1 text-sm text-slate-600">
            {diagram.series.length} of {totalMaterialCount} materials plotted
          </div>
          {scaleError ? <div className="mt-1 text-[11px] text-rose-600">{scaleError}</div> : null}
        </div>
        <MaterialChartScaleToolbar
          scaleMode={scaleMode}
          onSetAuto={setAutoScale}
          onSetManual={setManualScale}
          onReset={resetManualScale}
        />
      </div>

      {controlSummaries.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {controlSummaries.map((entry) => (
            <div
              key={entry.key}
              className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-600"
            >
              {entry.label}: {entry.value}
            </div>
          ))}
        </div>
      )}

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-60 w-full rounded-2xl border border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)]"
      >
        <defs>
          <clipPath id={clipPathId}>
            <rect x={leftPadding} y={topPadding} width={plotWidth} height={plotHeight} />
          </clipPath>
        </defs>

        {xTickValues.map((xValue, index) => {
          const x = scaleX(xValue)
          const isZero = Math.abs(xValue) < 1e-9
          const edge = index === 0 ? 'min' : index === xTickValues.length - 1 ? 'max' : null
          const isEditable = scaleMode === 'manual' && edge !== null
          const isEditing = editingState?.axis === 'x' && editingState.edge === edge

          return (
            <g key={`dashboard-x-grid-${diagram.key}-${xValue}`}>
              <line
                x1={x}
                y1={topPadding}
                x2={x}
                y2={height - bottomPadding}
                stroke={isZero ? '#94a3b8' : '#e2e8f0'}
                strokeWidth={isZero ? 1.25 : 1}
              />
              <EditableMaterialAxisTick
                x={x}
                y={height - bottomPadding + 18}
                formattedValue={formatMaterialChartValue(xValue)}
                textAnchor="middle"
                baseClassName="fill-slate-500"
                editable={isEditable}
                editing={Boolean(isEditing)}
                editValue={isEditing ? editingState?.value ?? '' : ''}
                onEditValueChange={updateEditingValue}
                onStartEdit={() => {
                  if (edge) {
                    startEditingTick('x', edge)
                  }
                }}
                onSubmit={submitEditingTick}
                onCancel={cancelEditingTick}
              />
            </g>
          )
        })}

        {yTickValues.map((yValue, index) => {
          const y = scaleY(yValue)
          const isZero = Math.abs(yValue) < 1e-9
          const edge = index === 0 ? 'min' : index === yTickValues.length - 1 ? 'max' : null
          const isEditable = scaleMode === 'manual' && edge !== null
          const isEditing = editingState?.axis === 'y' && editingState.edge === edge

          return (
            <g key={`dashboard-y-grid-${diagram.key}-${yValue}`}>
              <line
                x1={leftPadding}
                y1={y}
                x2={width - rightPadding}
                y2={y}
                stroke={isZero ? '#94a3b8' : '#e2e8f0'}
                strokeWidth={isZero ? 1.25 : 1}
              />
              <EditableMaterialAxisTick
                x={leftPadding - 8}
                y={y + 3}
                formattedValue={formatMaterialChartValue(yValue)}
                textAnchor="end"
                baseClassName="fill-slate-500"
                editable={isEditable}
                editing={Boolean(isEditing)}
                editValue={isEditing ? editingState?.value ?? '' : ''}
                onEditValueChange={updateEditingValue}
                onStartEdit={() => {
                  if (edge) {
                    startEditingTick('y', edge)
                  }
                }}
                onSubmit={submitEditingTick}
                onCancel={cancelEditingTick}
              />
            </g>
          )
        })}

        <line
          x1={leftPadding}
          y1={height - bottomPadding}
          x2={width - rightPadding}
          y2={height - bottomPadding}
          stroke="#64748b"
          strokeWidth={1.2}
        />
        <line
          x1={leftPadding}
          y1={topPadding}
          x2={leftPadding}
          y2={height - bottomPadding}
          stroke="#64748b"
          strokeWidth={1.2}
        />

        <g clipPath={`url(#${clipPathId})`}>
          {orderedSeries.map((entry) => {
            const isSelected = selectedMaterialIdSet.has(entry.materialId)
            const polylinePoints = entry.points
              .map((point) => `${scaleX(point.x)},${scaleY(point.y)}`)
              .join(' ')

            return (
              <g key={`${diagram.key}-${entry.materialId}`}>
                <polyline
                  fill="none"
                  stroke={hasActiveSelection ? (isSelected ? entry.color : '#94a3b8') : entry.color}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeOpacity={hasActiveSelection ? (isSelected ? 1 : 0.24) : 0.82}
                  strokeWidth={hasActiveSelection ? (isSelected ? 3.1 : 1.2) : 1.7}
                  points={polylinePoints}
                />
                {entry.points.map((point, pointIndex) => {
                  if (!hasActiveSelection || !isSelected) {
                    return null
                  }

                  const x = scaleX(point.x)
                  const y = scaleY(point.y)
                  return (
                    <circle key={`${entry.materialId}-${pointIndex}`} cx={x} cy={y} r={2.6} fill={entry.color} />
                  )
                })}
              </g>
            )
          })}
        </g>

        <text
          x={leftPadding + (width - leftPadding - rightPadding) / 2}
          y={height - 10}
          textAnchor="middle"
          className="fill-slate-700 text-[12px]"
        >
          {formatMaterialAxisLabel(diagram.x_axis)}
        </text>
        <text
          x={18}
          y={topPadding + (height - topPadding - bottomPadding) / 2}
          textAnchor="middle"
          transform={`rotate(-90 18 ${topPadding + (height - topPadding - bottomPadding) / 2})`}
          className="fill-slate-700 text-[12px]"
        >
          {formatMaterialAxisLabel(diagram.y_axis)}
        </text>
      </svg>
    </div>
  )
}

export function LibraryMaterialsView({
  materials,
  materialClassificationCatalog,
  users,
  currentUserId,
  selectedMaterialId,
  onSelectMaterialId,
  isMaterialListVisible,
  isLoading,
  error,
}: LibraryMaterialsViewProps) {
  const [textFilter, setTextFilter] = useState('')
  const [ownerFilters, setOwnerFilters] = useState<Set<OwnerFilterKey>>(new Set(DEFAULT_OWNER_FILTERS))
  const [classificationFilters, setClassificationFilters] = useState<MaterialClassificationFilterState>({})
  const [selectedUserId, setSelectedUserId] = useSelectedUserState(users, currentUserId)
  const { materialVisualStates, fetchMaterialVisuals } = useMaterialVisualStore()
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<number[]>(() => {
    return selectedMaterialId !== null ? [selectedMaterialId] : []
  })
  const [selectionAnchorMaterialId, setSelectionAnchorMaterialId] = useState<number | null>(selectedMaterialId)

  const usersById = useMemo(() => {
    return new Map(users.map((entry) => [entry.user_id, entry]))
  }, [users])

  const normalizedFilter = textFilter.trim().toLowerCase()

  const ownerAndTextFilteredMaterials = useMemo(() => {
    return filterMaterialsForLibrary(
      materials,
      normalizedFilter,
      ownerFilters,
      currentUserId,
      selectedUserId
    )
  }, [currentUserId, materials, normalizedFilter, ownerFilters, selectedUserId])

  const classificationAxisByKey = useMemo(() => {
    return buildMaterialClassificationAxisByKey(materialClassificationCatalog)
  }, [materialClassificationCatalog])

  const classificationFilterAxes = useMemo(() => {
    return buildMaterialClassificationFilterAxes(
      materialClassificationCatalog,
      ownerAndTextFilteredMaterials,
      classificationFilters
    )
  }, [classificationFilters, materialClassificationCatalog, ownerAndTextFilteredMaterials])

  const effectiveClassificationFilters = useMemo(() => {
    return pruneMaterialClassificationFilters(classificationFilters, classificationFilterAxes)
  }, [classificationFilterAxes, classificationFilters])

  useEffect(() => {
    if (areMaterialClassificationFilterStatesEqual(classificationFilters, effectiveClassificationFilters)) {
      return
    }
    setClassificationFilters(effectiveClassificationFilters)
  }, [classificationFilters, effectiveClassificationFilters])

  const filteredMaterials = useMemo(() => {
    return ownerAndTextFilteredMaterials.filter((entry) =>
      matchesMaterialClassificationFilters(
        entry,
        effectiveClassificationFilters,
        classificationAxisByKey
      )
    )
  }, [classificationAxisByKey, effectiveClassificationFilters, ownerAndTextFilteredMaterials])

  useEffect(() => {
    const visibleIds = new Set(filteredMaterials.map((entry) => entry.material_id))

    setSelectedMaterialIds((previous) => {
      const next = previous.filter((id) => visibleIds.has(id))
      if (next.length === previous.length) {
        return previous
      }

      const nextPrimary =
        selectedMaterialId !== null && next.includes(selectedMaterialId)
          ? selectedMaterialId
          : next[next.length - 1] ?? null

      if (nextPrimary !== selectedMaterialId) {
        onSelectMaterialId(nextPrimary)
      }

      return next
    })

    setSelectionAnchorMaterialId((previous) => {
      if (previous !== null && visibleIds.has(previous)) {
        return previous
      }
      return null
    })
  }, [filteredMaterials, onSelectMaterialId, selectedMaterialId])

  useEffect(() => {
    if (
      selectedMaterialId !== null &&
      filteredMaterials.some((entry) => entry.material_id === selectedMaterialId)
    ) {
      setSelectedMaterialIds((previous) => {
        if (previous.length > 0 || previous.includes(selectedMaterialId)) {
          return previous
        }
        return [selectedMaterialId]
      })

      setSelectionAnchorMaterialId((previous) => previous ?? selectedMaterialId)
    }
  }, [filteredMaterials, selectedMaterialId])

  useEffect(() => {
    if (isLoading) {
      return
    }

    filteredMaterials.forEach((entry) => {
      const currentState = materialVisualStates[entry.material_id]
      if (!currentState) {
        void fetchMaterialVisuals(entry.material_id)
      }
    })
  }, [fetchMaterialVisuals, filteredMaterials, isLoading, materialVisualStates])

  const toggleOwnerFilter = (filterKey: OwnerFilterKey) => {
    setOwnerFilters((previous) => toggleFilter(previous, filterKey))
  }

  const toggleClassificationFilterValue = (axisKey: string, valueKey: string) => {
    setClassificationFilters((previous) =>
      toggleMaterialClassificationFilterValue(previous, axisKey, valueKey)
    )
  }

  const clearClassificationFilters = () => {
    setClassificationFilters({})
  }

  const activeMaterialId = useMemo(() => {
    if (selectedMaterialId !== null && selectedMaterialIds.includes(selectedMaterialId)) {
      return selectedMaterialId
    }
    return selectedMaterialIds[selectedMaterialIds.length - 1] ?? null
  }, [selectedMaterialId, selectedMaterialIds])

  const diagramMaterials = useMemo(() => {
    return filteredMaterials
  }, [filteredMaterials])

  const selectedMaterialIdSet = useMemo(() => {
    return new Set(selectedMaterialIds)
  }, [selectedMaterialIds])

  const selectedMaterials = useMemo(() => {
    return diagramMaterials.filter((entry) => selectedMaterialIdSet.has(entry.material_id))
  }, [diagramMaterials, selectedMaterialIdSet])
  const highlightedMaterialIds = useMemo(() => {
    return selectedMaterials.map((entry) => entry.material_id)
  }, [selectedMaterials])

  const selectedMaterial = useMemo(() => {
    return diagramMaterials.find((entry) => entry.material_id === activeMaterialId) ?? null
  }, [activeMaterialId, diagramMaterials])

  const dashboardDiagrams = useMemo(() => {
    return buildDashboardMaterialDiagrams(diagramMaterials, materialVisualStates)
  }, [diagramMaterials, materialVisualStates])
  const materialColorById = useMemo(() => {
    return new Map(
      diagramMaterials.map((entry, index) => [entry.material_id, getDashboardMaterialColor(index)])
    )
  }, [diagramMaterials])

  const loadingCount = diagramMaterials.filter((entry) => materialVisualStates[entry.material_id]?.status === 'loading').length
  const errorCount = diagramMaterials.filter((entry) => materialVisualStates[entry.material_id]?.status === 'error').length

  const selectedMaterialState =
    selectedMaterial !== null ? materialVisualStates[selectedMaterial.material_id] : undefined
  const selectedMaterialClassificationRows = useMemo(() => {
    if (selectedMaterial === null) {
      return []
    }
    return buildMaterialClassificationComparisonRows(
      selectedMaterial,
      diagramMaterials,
      materialClassificationCatalog
    )
  }, [diagramMaterials, materialClassificationCatalog, selectedMaterial])
  const selectedMaterialChemistryColumns = useMemo(() => {
    if (selectedMaterial === null) {
      return []
    }

    const referenceChemistryLimits =
      selectedMaterial.designation_links.find(
        (entry) => Object.keys(entry.chemistry_limits ?? {}).length > 0
      )?.chemistry_limits ?? {}

    return sortMaterialChemistryElements(
      selectedMaterial.designation_links.flatMap((entry) => Object.keys(entry.chemistry_limits ?? {})),
      referenceChemistryLimits
    )
  }, [selectedMaterial])

  const summaryMaterials = selectedMaterials.length > 0 ? selectedMaterials : diagramMaterials
  const showSingleMaterialDetails = selectedMaterials.length === 1 && selectedMaterial !== null

  const handleMaterialCardClick = (event: React.MouseEvent<HTMLButtonElement>, materialId: number) => {
    const visibleIds = filteredMaterials.map((entry) => entry.material_id)
    const clickedIndex = visibleIds.indexOf(materialId)
    if (clickedIndex === -1) {
      return
    }

    const isToggleSelection = event.ctrlKey || event.metaKey
    const currentIds = selectedMaterialIds
    const currentSet = new Set(currentIds)

    if (event.shiftKey) {
      const anchorId = selectionAnchorMaterialId ?? activeMaterialId ?? materialId
      const anchorIndex = visibleIds.indexOf(anchorId)
      const safeAnchorIndex = anchorIndex === -1 ? clickedIndex : anchorIndex
      const rangeIds = visibleIds.slice(
        Math.min(safeAnchorIndex, clickedIndex),
        Math.max(safeAnchorIndex, clickedIndex) + 1
      )
      const nextIds = isToggleSelection
        ? sortMaterialIdsByVisibleOrder([...currentIds, ...rangeIds], filteredMaterials)
        : rangeIds

      setSelectedMaterialIds(nextIds)
      setSelectionAnchorMaterialId(anchorId)
      onSelectMaterialId(materialId)
      return
    }

    if (isToggleSelection) {
      const nextIds = currentSet.has(materialId)
        ? currentIds.filter((id) => id !== materialId)
        : sortMaterialIdsByVisibleOrder([...currentIds, materialId], filteredMaterials)

      const nextPrimary =
        nextIds.length === 0
          ? null
          : currentSet.has(materialId)
            ? materialId === activeMaterialId
              ? nextIds[nextIds.length - 1] ?? null
              : activeMaterialId
            : materialId

      setSelectedMaterialIds(nextIds)
      setSelectionAnchorMaterialId(materialId)
      onSelectMaterialId(nextPrimary)
      return
    }

    if (currentIds.length === 1 && currentIds[0] === materialId) {
      setSelectedMaterialIds([])
      setSelectionAnchorMaterialId(materialId)
      onSelectMaterialId(null)
      return
    }

    setSelectedMaterialIds([materialId])
    setSelectionAnchorMaterialId(materialId)
    onSelectMaterialId(materialId)
  }

  return (
    <div className="h-full min-h-0 flex overflow-hidden bg-[linear-gradient(180deg,#f8fafc_0%,#eef2ff_42%,#f8fafc_100%)]">
      {isMaterialListVisible ? (
        <aside className="h-full min-h-0 w-80 shrink-0 border-r border-slate-200 bg-white/70">
          <div className="h-full min-h-0 overflow-y-auto px-4 py-4 space-y-4">
            <input
              type="text"
              className="ui-input"
              value={textFilter}
              onChange={(event) => setTextFilter(event.target.value)}
              placeholder="Filter materials by id, name, note, or DEFORM file..."
            />

            <OwnerFilters
              activeOwnerFilters={ownerFilters}
              onToggleOwnerFilter={toggleOwnerFilter}
              users={users}
              selectedUserId={selectedUserId}
              onSelectedUserChange={setSelectedUserId}
            />

            <MaterialClassificationFilters
              axes={classificationFilterAxes}
              selectedFilters={effectiveClassificationFilters}
              onToggleValue={toggleClassificationFilterValue}
              onClear={clearClassificationFilters}
            />

            <div className="flex flex-wrap items-center gap-2">
              <button type="button" className="ui-btn-primary" onClick={() => undefined}>
                New material
              </button>
              <button
                type="button"
                className="ui-btn"
                disabled={selectedMaterialIds.length !== 1}
                onClick={() => undefined}
              >
                Clone selected material
              </button>
              <button
                type="button"
                className="ui-btn-danger"
                disabled={selectedMaterialIds.length === 0}
                onClick={() => undefined}
              >
                Delete selected material
              </button>
              <div className="ui-badge">
                Selected: {selectedMaterialIds.length}
              </div>
            </div>

            {error && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</div>}
            {isLoading && <EmptyState message="Loading materials..." />}
            {!isLoading && filteredMaterials.length === 0 && <EmptyState message="No materials found for active filters." />}

            {!isLoading &&
              filteredMaterials.map((entry) => {
                const isSelected = selectedMaterialIdSet.has(entry.material_id)
                const loadState = materialVisualStates[entry.material_id]

                return (
                  <button
                    key={entry.material_id}
                    type="button"
                    onClick={(event) => handleMaterialCardClick(event, entry.material_id)}
                    className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                      isSelected
                        ? 'border-sky-300 bg-sky-50 shadow-sm'
                        : 'border-slate-200 bg-white/85 hover:border-slate-300 hover:bg-white'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className="inline-block h-3 w-1.5 rounded-full"
                        style={{
                          backgroundColor: materialColorById.get(entry.material_id) || '#2563eb',
                        }}
                      />
                      <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">
                        {formatLibraryName(entry.name)}
                      </span>
                      <span
                        className={`h-2.5 w-2.5 rounded-full ${
                          loadState?.status === 'loaded'
                            ? 'bg-emerald-500'
                            : loadState?.status === 'error'
                              ? 'bg-rose-500'
                              : loadState?.status === 'loading'
                                ? 'bg-amber-400'
                                : 'bg-slate-300'
                        }`}
                      />
                    </div>
                  </button>
                )
              })}
          </div>
        </aside>
      ) : null}

      <section className="flex-1 min-w-0 min-h-0 flex flex-col">
        <div className="shrink-0 border-b border-slate-200 bg-white/75 px-5 py-4 backdrop-blur">
              <div className="text-sm leading-6 text-slate-700">
            <span className="font-medium text-slate-900">
              {selectedMaterials.length > 0
                ? `DEFORM materials. Selected ${selectedMaterials.length} of ${diagramMaterials.length} materials: `
                : `DEFORM materials. Select a material to highlight it. Now all ${diagramMaterials.length} materials highlighted: `}
            </span>
            {summaryMaterials.map((entry, index) => (
              <span key={entry.material_id} className="inline">
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: materialColorById.get(entry.material_id) || '#2563eb' }}
                  />
                  <span>{formatLibraryName(entry.name)}</span>
                </span>
                {index < summaryMaterials.length - 1 ? <span className="text-slate-400">, </span> : null}
              </span>
            ))}
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {showSingleMaterialDetails ? (
            <div className="border-b border-slate-200 bg-white/45 px-5 py-5">
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Materials
              </div>
              <div className="mt-2 text-2xl font-semibold text-slate-900">
                {formatLibraryName(selectedMaterial.name)}
              </div>
              <div className="mt-2 text-sm text-slate-600">
                Charts below compare only parsed content from the DEFORM source file referenced by{' '}
                <code className="rounded bg-slate-100 px-1 py-0.5 text-[12px] text-slate-700">materials.deform_file_name</code>.
              </div>
              <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(340px,1.1fr)]">
                <div className="grid grid-cols-[minmax(0,150px)_1fr] gap-x-5 gap-y-2 text-sm text-slate-700">
                  <div className="font-medium text-slate-500">Active</div>
                  <div>{formatLibraryName(selectedMaterial.name)}</div>

                  <div className="font-medium text-slate-500">ID</div>
                  <div>{selectedMaterial.material_id}</div>

                  <div className="font-medium text-slate-500">DEFORM file</div>
                  <div className="break-all">{selectedMaterial.deform_file_name || '-'}</div>

                  <div className="font-medium text-slate-500">Owner</div>
                  <div>{getOwnerLabel(selectedMaterial.owner_id, usersById)}</div>

                  <div className="font-medium text-slate-500">Tests</div>
                  <div>{selectedMaterial.test_records_count}</div>

                  <div className="font-medium text-slate-500">Diagrams</div>
                  <div>
                    {selectedMaterialState?.status === 'loaded'
                      ? selectedMaterialState.data.diagrams.length
                      : selectedMaterialState?.status === 'error'
                        ? 'Load error'
                        : 'Loading'}
                  </div>

                  <div className="font-medium text-slate-500">Note</div>
                  <div>{selectedMaterial.note || '-'}</div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3">
                  <div className="overflow-x-auto">
                    <table className="w-full table-auto border-separate border-spacing-0 text-sm text-slate-700">
                      <thead>
                        <tr className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                          <th className="w-px whitespace-nowrap border-b border-slate-100 pb-2 pr-4 text-left font-semibold">
                            Designation
                          </th>
                          <th className="w-px whitespace-nowrap border-b border-slate-100 pb-2 pr-4 text-left font-semibold">
                            Standard
                          </th>
                          <th className="w-px whitespace-nowrap border-b border-slate-100 pb-2 pr-4 text-left font-semibold">
                            Country
                          </th>
                          {selectedMaterialChemistryColumns.map((element) => (
                            <th
                              key={element}
                              className="w-px whitespace-nowrap border-b border-slate-100 pb-2 px-3 text-center font-semibold"
                            >
                              <span className="normal-case tracking-normal">{element}</span>
                            </th>
                          ))}
                          <th className="border-b border-slate-100 pb-2 text-left font-semibold" />
                        </tr>
                      </thead>
                      <tbody>
                        {selectedMaterial.designation_links.length > 0 ? (
                          selectedMaterial.designation_links.map((entry) => (
                            <tr
                              key={`${entry.designation}-${entry.standard ?? 'none'}-${entry.country ?? 'none'}`}
                              className="align-top"
                            >
                              <td
                                className={`whitespace-nowrap border-b border-slate-100 py-2 pr-4 ${
                                  entry.is_main_designation ? 'font-semibold text-slate-900' : ''
                                }`}
                              >
                                {entry.designation}
                              </td>
                              <td
                                className={`whitespace-nowrap border-b border-slate-100 py-2 pr-4 ${
                                  entry.standard ? 'text-slate-700' : 'text-slate-400'
                                }`}
                              >
                                {entry.standard || 'Unlinked'}
                              </td>
                              <td
                                className={`whitespace-nowrap border-b border-slate-100 py-2 pr-4 ${
                                  entry.country ? 'text-slate-700' : 'text-slate-400'
                                }`}
                              >
                                {entry.country || '-'}
                              </td>
                              {selectedMaterialChemistryColumns.map((element) => {
                                const chemistryLimit = entry.chemistry_limits?.[element]
                                return (
                                  <td
                                    key={`${entry.designation}-${element}`}
                                    className={`whitespace-nowrap border-b border-slate-100 py-2 px-3 text-center ${
                                      chemistryLimit ? 'text-slate-700' : 'text-slate-300'
                                    }`}
                                  >
                                    {chemistryLimit || '—'}
                                  </td>
                                )
                              })}
                              <td className="border-b border-slate-100 py-2" />
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td
                              colSpan={selectedMaterialChemistryColumns.length + 4}
                              className="whitespace-nowrap border-b border-slate-100 py-2 pr-4 text-slate-500"
                            >
                              No designations linked.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div className="mt-4 rounded-2xl border border-slate-200 bg-white/80 px-4 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Classification
                </div>
                <div className="mt-1 text-[11px] text-slate-500">
                  Selected material values are highlighted. Other values present in the current material set are muted.
                </div>
                <div className="mt-3 grid grid-cols-[minmax(0,180px)_1fr] gap-x-5 gap-y-3 text-sm text-slate-700">
                  {selectedMaterialClassificationRows.length > 0 ? (
                    selectedMaterialClassificationRows.map((entry) => (
                      <Fragment key={entry.axisKey}>
                        <div className="pt-1 font-medium text-slate-500">
                          {entry.axisLabel}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {entry.values.map((value) => (
                            <span
                              key={`${entry.axisKey}-${value.key}`}
                              className={`rounded-full border px-2.5 py-1 text-[11px] ${
                                value.state === 'selected'
                                  ? 'border-sky-300 bg-sky-50 text-sky-700'
                                  : 'border-slate-200 bg-slate-100/80 text-slate-400'
                              }`}
                            >
                              {value.label}
                            </span>
                          ))}
                        </div>
                      </Fragment>
                    ))
                  ) : (
                    <div className="col-span-2 text-slate-500">No classification values assigned.</div>
                  )}
                </div>
              </div>

              {errorCount > 0 && (
                <div className="mt-4 text-xs text-rose-700">
                  {errorCount} material{errorCount === 1 ? '' : 's'} failed to load diagrams.
                </div>
              )}
            </div>
          ) : errorCount > 0 ? (
            <div className="border-b border-slate-200 bg-white/45 px-5 py-3 text-xs text-rose-700">
              {errorCount} material{errorCount === 1 ? '' : 's'} failed to load diagrams.
            </div>
          ) : null}

          <div className="p-4">
            {isLoading ? (
              <EmptyState message="Loading material diagrams..." />
            ) : diagramMaterials.length === 0 ? (
              <EmptyState message="No materials found for active filters." />
            ) : dashboardDiagrams.length === 0 ? (
              <div className="rounded-3xl border border-dashed border-slate-300 bg-white/80 px-6 py-12 text-center text-sm text-slate-500">
                {loadingCount > 0
                  ? 'Loading material diagrams...'
                  : errorCount === diagramMaterials.length
                    ? 'No material charts could be created because diagram loading failed for all visible materials.'
                    : 'No comparable diagrams are available for the visible material set.'}
              </div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {dashboardDiagrams.map((diagram) => (
                  <MaterialDashboardDiagramCard
                    key={diagram.key}
                    diagram={diagram}
                    selectedMaterialIds={highlightedMaterialIds}
                    totalMaterialCount={diagramMaterials.length}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

function extractPowerLimitPoints(mode: PressModeRecord): PowerLimitPoint[] {
  const raw = mode.properties?.power_limit
  if (!Array.isArray(raw)) {
    return []
  }

  return raw.map((entry) => {
    if (!entry || typeof entry !== 'object') {
      return { id: null, force: null, speed: null }
    }

    const row = entry as Record<string, unknown>
    return {
      id: normalizeNumber(row.id),
      force: normalizeNumber(row.force),
      speed: normalizeNumber(row.speed),
    }
  })
}

function extractModePropertiesWithoutPowerLimit(mode: PressModeRecord): Record<string, unknown> {
  const source = mode.properties || {}
  const next: Record<string, unknown> = {}

  Object.entries(source).forEach(([key, value]) => {
    if (key === 'power_limit') {
      return
    }
    next[key] = value
  })

  return next
}

interface PressModeRow {
  mode: PressModeRecord
  modeName: string
  powerLimitPoints: PowerLimitPoint[]
  propertiesWithoutPowerLimit: Record<string, unknown>
  style: CurveStyle
}

interface PressModeColumn {
  key: string
  label: string
  getValue: (row: PressModeRow) => unknown
}

function PowerLimitDiagram({
  rows,
  selectedModeId,
  onSelectMode,
}: {
  rows: PressModeRow[]
  selectedModeId: number | null
  onSelectMode: (modeId: number) => void
}) {
  const width = 620
  const height = 300
  const leftPadding = 64
  const rightPadding = 20
  const topPadding = 18
  const bottomPadding = 50
  const xTicks = 6
  const yTicks = 6

  const curves = rows
    .map((row) => ({
      row,
      points: row.powerLimitPoints
        .map((point, index) => ({
          x: point.force ?? 0,
          y: point.speed ?? index,
        }))
        .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y)),
    }))
    .filter((curve) => curve.points.length > 0)

  if (curves.length === 0) {
    return <div className="text-xs text-gray-500 py-2">No power_limit data for diagram.</div>
  }

  const minX = Math.min(...curves.flatMap((curve) => curve.points.map((point) => point.x)))
  const maxX = Math.max(...curves.flatMap((curve) => curve.points.map((point) => point.x)))
  const minY = Math.min(...curves.flatMap((curve) => curve.points.map((point) => point.y)))
  const maxY = Math.max(...curves.flatMap((curve) => curve.points.map((point) => point.y)))
  const hasNegativeX = minX < 0
  const hasNegativeY = minY < 0

  const rangeX = maxX - minX
  const rangeY = maxY - minY
  const paddedMinXBase = rangeX === 0 ? minX - 1 : minX - rangeX * 0.05
  const paddedMaxXBase = rangeX === 0 ? maxX + 1 : maxX + rangeX * 0.05
  const paddedMinYBase = rangeY === 0 ? minY - 1 : minY - rangeY * 0.05
  const paddedMaxYBase = rangeY === 0 ? maxY + 1 : maxY + rangeY * 0.05
  const paddedMinX = hasNegativeX ? paddedMinXBase : 0
  const paddedMaxX = Math.max(paddedMaxXBase, 0)
  const paddedMinY = hasNegativeY ? paddedMinYBase : 0
  const paddedMaxY = Math.max(paddedMaxYBase, 0)

  const scaleX = (value: number) => {
    if (paddedMaxX === paddedMinX) {
      return leftPadding + (width - leftPadding - rightPadding) / 2
    }
    return leftPadding + ((value - paddedMinX) / (paddedMaxX - paddedMinX)) * (width - leftPadding - rightPadding)
  }

  const scaleY = (value: number) => {
    if (paddedMaxY === paddedMinY) {
      return topPadding + (height - topPadding - bottomPadding) / 2
    }
    return height - bottomPadding - ((value - paddedMinY) / (paddedMaxY - paddedMinY)) * (height - topPadding - bottomPadding)
  }

  const formatTick = (value: number) => {
    if (Math.abs(value) >= 1000) {
      return value.toFixed(0)
    }
    if (Math.abs(value) >= 10) {
      return value.toFixed(1)
    }
    return value.toFixed(2)
  }

  const buildTicks = (min: number, max: number, count: number): number[] => {
    const ticks: number[] = []
    for (let index = 0; index <= count; index += 1) {
      const ratio = index / count
      ticks.push(min + (max - min) * ratio)
    }

    ticks.push(0)
    const deduped = Array.from(new Set(ticks.map((entry) => Number(entry.toFixed(6)))))
    deduped.sort((left, right) => left - right)
    return deduped
  }

  const xTickValues = buildTicks(paddedMinX, paddedMaxX, xTicks)
  const yTickValues = buildTicks(paddedMinY, paddedMaxY, yTicks)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-72 border border-gray-200 rounded bg-white">
      {xTickValues.map((xValue) => {
        const x = scaleX(xValue)
        const isZero = Math.abs(xValue) < 1e-9
        return (
          <g key={`x-grid-${xValue}`}>
            <line
              x1={x}
              y1={topPadding}
              x2={x}
              y2={height - bottomPadding}
              stroke={isZero ? '#9ca3af' : '#e5e7eb'}
              strokeWidth={isZero ? 1.3 : 1}
            />
            <text x={x} y={height - bottomPadding + 16} textAnchor="middle" className="fill-gray-600 text-[11px]">
              {formatTick(xValue)}
            </text>
          </g>
        )
      })}

      {yTickValues.map((yValue) => {
        const y = scaleY(yValue)
        const isZero = Math.abs(yValue) < 1e-9
        return (
          <g key={`y-grid-${yValue}`}>
            <line
              x1={leftPadding}
              y1={y}
              x2={width - rightPadding}
              y2={y}
              stroke={isZero ? '#9ca3af' : '#e5e7eb'}
              strokeWidth={isZero ? 1.3 : 1}
            />
            <text x={leftPadding - 8} y={y + 3} textAnchor="end" className="fill-gray-600 text-[11px]">
              {formatTick(yValue)}
            </text>
          </g>
        )
      })}

      <line
        x1={leftPadding}
        y1={height - bottomPadding}
        x2={width - rightPadding}
        y2={height - bottomPadding}
        stroke="#6b7280"
        strokeWidth={1.2}
      />
      <line
        x1={leftPadding}
        y1={topPadding}
        x2={leftPadding}
        y2={height - bottomPadding}
        stroke="#6b7280"
        strokeWidth={1.2}
      />

      {curves.map((curve) => {
        const isSelected = selectedModeId === curve.row.mode.id
        const points = curve.points.map((point) => `${scaleX(point.x)},${scaleY(point.y)}`).join(' ')
        return (
          <g key={curve.row.mode.id}>
            <polyline
              fill="none"
              stroke={curve.row.style.color}
              strokeWidth={isSelected ? 3.2 : 1.8}
              points={points}
              onClick={() => onSelectMode(curve.row.mode.id)}
              className="cursor-pointer"
            />
            {curve.points.map((point, pointIndex) => {
              const x = scaleX(point.x)
              const y = scaleY(point.y)
              return (
                <g
                  key={`${curve.row.mode.id}-${pointIndex}`}
                  onClick={() => onSelectMode(curve.row.mode.id)}
                  className="cursor-pointer"
                >
                  <DiagramSymbol symbol={curve.row.style.symbol} x={x} y={y} color={curve.row.style.color} />
                </g>
              )
            })}
          </g>
        )
      })}

      <text
        x={leftPadding + (width - leftPadding - rightPadding) / 2}
        y={height - 10}
        textAnchor="middle"
        className="fill-gray-700 text-[12px]"
      >
        Force, MN
      </text>
      <text
        x={18}
        y={topPadding + (height - topPadding - bottomPadding) / 2}
        textAnchor="middle"
        transform={`rotate(-90 18 ${topPadding + (height - topPadding - bottomPadding) / 2})`}
        className="fill-gray-700 text-[12px]"
      >
        Speed, mm/s
      </text>
    </svg>
  )
}

function PressCard({
  press,
  modes,
  usersById,
  isSelected,
  onToggleSelection,
  onRegisterPressModesTableContainer,
  onPressModesTableScroll,
}: {
  press: PressRecord
  modes: PressModeRecord[]
  usersById: Map<number, LibraryDbUserRecord>
  isSelected: boolean
  onToggleSelection: () => void
  onRegisterPressModesTableContainer: (pressId: number, element: HTMLDivElement | null) => void
  onPressModesTableScroll: (sourcePressId: number, nextScrollLeft: number) => void
}) {
  const [selectedModeId, setSelectedModeId] = useState<number | null>(null)
  const [sortBy, setSortBy] = useState<string>('id')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')

  const modeRows = useMemo<PressModeRow[]>(() => {
    return modes.map((mode, index) => ({
      mode,
      modeName: formatLibraryName(mode.name),
      powerLimitPoints: extractPowerLimitPoints(mode),
      propertiesWithoutPowerLimit: extractModePropertiesWithoutPowerLimit(mode),
      style: getCurveStyle(index),
    }))
  }, [modes])

  const defaultModeId = useMemo(() => {
    if (modeRows.length === 0) {
      return null
    }

    const byId = [...modeRows].sort((left, right) => left.mode.id - right.mode.id)
    const defaultRow = byId.find((row) => row.mode.is_default_press_mode)
    return defaultRow?.mode.id ?? byId[0].mode.id
  }, [modeRows])

  useEffect(() => {
    const availableModeIds = new Set(modeRows.map((row) => row.mode.id))

    setSelectedModeId((previous) => {
      if (previous !== null && availableModeIds.has(previous)) {
        return previous
      }
      return defaultModeId
    })
  }, [defaultModeId, modeRows])

  const propertyColumnKeys = useMemo(() => {
    const keys = new Set<string>()
    modeRows.forEach((row) => {
      Object.keys(row.propertiesWithoutPowerLimit).forEach((key) => keys.add(key))
    })
    return Array.from(keys).sort((left, right) => left.localeCompare(right))
  }, [modeRows])

  const columns = useMemo<PressModeColumn[]>(() => {
    const baseColumns: PressModeColumn[] = [
      { key: 'id', label: 'id', getValue: (row) => row.mode.id },
      { key: 'press_id', label: 'press_id', getValue: (row) => row.mode.press_id },
      { key: 'owner_user_id', label: 'owner_user_id', getValue: (row) => row.mode.owner_user_id },
      { key: 'name', label: 'name', getValue: (row) => row.modeName },
      {
        key: 'is_default_press_mode',
        label: 'is_default_press_mode',
        getValue: (row) => row.mode.is_default_press_mode,
      },
      { key: 'is_obsolete', label: 'is_obsolete', getValue: (row) => row.mode.is_obsolete },
      { key: 'created_at', label: 'created_at', getValue: (row) => row.mode.created_at },
      { key: 'obsolete_at', label: 'obsolete_at', getValue: (row) => row.mode.obsolete_at },
    ]

    const propertyColumns = propertyColumnKeys.map<PressModeColumn>((key) => ({
      key: `property:${key}`,
      label: key,
      getValue: (row) => row.propertiesWithoutPowerLimit[key],
    }))

    return [...baseColumns, ...propertyColumns]
  }, [propertyColumnKeys])

  const sortedRows = useMemo(() => {
    const targetColumn = columns.find((column) => column.key === sortBy) || columns[0]
    if (!targetColumn) {
      return modeRows
    }

    return [...modeRows].sort((left, right) => {
      const comparison = compareSortValues(targetColumn.getValue(left), targetColumn.getValue(right))
      return sortDirection === 'asc' ? comparison : -comparison
    })
  }, [columns, modeRows, sortBy, sortDirection])

  const singleSelectedRow = useMemo(() => {
    if (selectedModeId === null) {
      return null
    }
    return sortedRows.find((row) => row.mode.id === selectedModeId) || null
  }, [selectedModeId, sortedRows])

  const powerLimitRowsCount = Math.max(singleSelectedRow?.powerLimitPoints.length || 0, 6)

  const handleSortByColumn = (columnKey: string) => {
    if (sortBy === columnKey) {
      setSortDirection((previous) => (previous === 'asc' ? 'desc' : 'asc'))
      return
    }

    setSortBy(columnKey)
    setSortDirection('asc')
  }

  return (
    <div className={`ui-card ui-card-body space-y-3 ${isSelected ? 'border-blue-600 bg-blue-50' : ''}`}>
      <button type="button" onClick={onToggleSelection} className="w-full text-left space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="font-semibold text-sm text-gray-900">{formatLibraryName(press.name)}</div>
          <div className="text-xs text-gray-500">ID: {press.id}</div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-700">
          <div>Owner: {getOwnerLabel(press.owner_user_id, usersById)}</div>
          <div>Obsolete: {press.is_obsolete ? 'Yes' : 'No'}</div>
          <div>Created: {formatTimestamp(press.created_at)}</div>
          <div>Press modes: {modes.length}</div>
        </div>
      </button>

      {modes.length === 0 && <div className="text-xs text-gray-500">No related press modes.</div>}

      {modes.length > 0 && (
        <div className="space-y-3">
          <div className="overflow-x-auto">
            <div className="min-w-[980px] grid grid-cols-2 gap-3">
              <div className="border border-gray-200 rounded bg-white p-2 space-y-2">
                <div className="text-xs font-semibold text-gray-700">Power Limit Diagram</div>
                <PowerLimitDiagram
                  rows={sortedRows}
                  selectedModeId={selectedModeId}
                  onSelectMode={setSelectedModeId}
                />
              </div>

              <div className="border border-gray-200 rounded bg-white p-2 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-semibold text-gray-700">Power Limit Table</div>
                    <div className="text-xs text-gray-500">
                    {singleSelectedRow ? `Mode ${singleSelectedRow.mode.id}` : ''}
                  </div>
                </div>
                <table className="w-full text-xs border border-gray-200 rounded">
                  <thead className="bg-gray-50 text-gray-600">
                    <tr>
                      <th className="px-2 py-1 text-left border-b border-gray-200">Point ID</th>
                      <th className="px-2 py-1 text-left border-b border-gray-200">Force, MN</th>
                      <th className="px-2 py-1 text-left border-b border-gray-200">Speed, mm/s</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from({ length: powerLimitRowsCount }).map((_, index) => {
                      const point = singleSelectedRow?.powerLimitPoints[index]
                      return (
                        <tr key={index} className="border-b border-gray-100 last:border-b-0">
                          <td className="px-2 py-1">{point?.id ?? ''}</td>
                          <td className="px-2 py-1">{point?.force ?? ''}</td>
                          <td className="px-2 py-1">{point?.speed ?? ''}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="border border-gray-200 rounded bg-white">
            <div className="text-xs font-semibold text-gray-700 px-2 py-2 border-b border-gray-200">
              Press Modes Table
            </div>
            <div
              ref={(element) => onRegisterPressModesTableContainer(press.id, element)}
              className="overflow-x-auto"
              onScroll={(event) => onPressModesTableScroll(press.id, event.currentTarget.scrollLeft)}
            >
              <table className="min-w-[1200px] w-full text-xs">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="sticky left-0 z-10 bg-gray-50 px-2 py-1 text-left border-b border-r border-gray-200">
                      Legend
                    </th>
                    {columns.map((column) => {
                      const isActiveSort = sortBy === column.key
                      return (
                        <th key={column.key} className="px-2 py-1 text-left border-b border-gray-200 whitespace-nowrap">
                          <button
                            type="button"
                            className="font-semibold text-gray-600 hover:text-gray-900"
                            onClick={() => handleSortByColumn(column.key)}
                          >
                            {column.label}
                            {isActiveSort ? ` ${sortDirection === 'asc' ? '▲' : '▼'}` : ''}
                          </button>
                        </th>
                      )
                    })}
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row) => {
                    const isModeSelected = selectedModeId === row.mode.id
                    return (
                      <tr
                        key={row.mode.id}
                        className={`border-b border-gray-100 cursor-pointer ${
                          isModeSelected ? 'bg-blue-50' : 'hover:bg-gray-50'
                        }`}
                        onClick={() => setSelectedModeId(row.mode.id)}
                      >
                        <td className="sticky left-0 z-10 bg-inherit px-2 py-1 border-r border-gray-200 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                              <DiagramSymbol
                                symbol={row.style.symbol}
                                x={7}
                                y={7}
                                color={row.style.color}
                              />
                            </svg>
                            <span>{row.mode.id}</span>
                          </div>
                        </td>
                        {columns.map((column) => (
                          <td key={column.key} className="px-2 py-1 whitespace-nowrap">
                            {formatCellValue(column.getValue(row))}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export interface LibraryPressesViewProps {
  presses: PressRecord[]
  pressModes: PressModeRecord[]
  users: LibraryDbUserRecord[]
  currentUserId: number | null
  selectedPressId: number | null
  onSelectPressId: (nextId: number | null) => void
  isLoading: boolean
  error: string | null
}

export function LibraryPressesView({
  presses,
  pressModes,
  users,
  currentUserId,
  selectedPressId,
  onSelectPressId,
  isLoading,
  error,
}: LibraryPressesViewProps) {
  const [textFilter, setTextFilter] = useState('')
  const [ownerFilters, setOwnerFilters] = useState<Set<OwnerFilterKey>>(new Set(DEFAULT_OWNER_FILTERS))
  const [selectedUserId, setSelectedUserId] = useSelectedUserState(users, currentUserId)
  const pressModesTableContainersRef = useRef<Map<number, HTMLDivElement>>(new Map())
  const isSyncingPressModesTablesRef = useRef(false)

  const usersById = useMemo(() => {
    return new Map(users.map((entry) => [entry.user_id, entry]))
  }, [users])

  const modesByPressId = useMemo(() => {
    const grouped = new Map<number, PressModeRecord[]>()

    pressModes.forEach((mode) => {
      if (mode.press_id === null || mode.press_id === undefined) {
        return
      }
      const existing = grouped.get(mode.press_id) || []
      existing.push(mode)
      grouped.set(mode.press_id, existing)
    })

    return grouped
  }, [pressModes])

  const normalizedFilter = textFilter.trim().toLowerCase()

  const filteredPresses = useMemo(() => {
    return presses.filter((entry) => {
      const ownerMatch = matchesOwnerFilter(
        entry.owner_user_id,
        ownerFilters,
        currentUserId,
        selectedUserId
      )
      if (!ownerMatch) {
        return false
      }

      if (!normalizedFilter) {
        return true
      }

      const name = formatLibraryName(entry.name).toLowerCase()
      const haystack = `${entry.id} ${name}`
      return haystack.includes(normalizedFilter)
    })
  }, [currentUserId, normalizedFilter, ownerFilters, presses, selectedUserId])

  const toggleOwnerFilter = (filterKey: OwnerFilterKey) => {
    setOwnerFilters((previous) => toggleFilter(previous, filterKey))
  }

  const registerPressModesTableContainer = useCallback((pressId: number, element: HTMLDivElement | null) => {
    if (element) {
      pressModesTableContainersRef.current.set(pressId, element)
      return
    }
    pressModesTableContainersRef.current.delete(pressId)
  }, [])

  const syncPressModesTableScroll = useCallback((sourcePressId: number, nextScrollLeft: number) => {
    if (isSyncingPressModesTablesRef.current) {
      return
    }

    isSyncingPressModesTablesRef.current = true
    pressModesTableContainersRef.current.forEach((container, pressId) => {
      if (pressId === sourcePressId) {
        return
      }
      if (Math.abs(container.scrollLeft - nextScrollLeft) > 1) {
        container.scrollLeft = nextScrollLeft
      }
    })

    requestAnimationFrame(() => {
      isSyncingPressModesTablesRef.current = false
    })
  }, [])

  return (
    <div className="h-full min-h-0 flex flex-col bg-gray-50">
      <div className="ui-pane-header space-y-2">
        <div className="ui-pane-title">Presses</div>
        <input
          type="text"
          className="ui-input"
          value={textFilter}
          onChange={(event) => setTextFilter(event.target.value)}
          placeholder="Filter presses by id or name..."
        />

        <OwnerFilters
          activeOwnerFilters={ownerFilters}
          onToggleOwnerFilter={toggleOwnerFilter}
          users={users}
          selectedUserId={selectedUserId}
          onSelectedUserChange={setSelectedUserId}
        />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
        {error && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</div>}
        {isLoading && <EmptyState message="Loading presses..." />}
        {!isLoading && filteredPresses.length === 0 && <EmptyState message="No presses found for active filters." />}

        {!isLoading &&
          filteredPresses.map((press) => {
            const isSelected = selectedPressId === press.id
            const modes = modesByPressId.get(press.id) || []
            return (
              <PressCard
                key={press.id}
                press={press}
                modes={modes}
                usersById={usersById}
                isSelected={isSelected}
                onToggleSelection={() => onSelectPressId(isSelected ? null : press.id)}
                onRegisterPressModesTableContainer={registerPressModesTableContainer}
                onPressModesTableScroll={syncPressModesTableScroll}
              />
            )
          })}
      </div>
    </div>
  )
}
