import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import DieStlPreview from './DieStlPreview'
import { formatLibraryName, formatTimestamp } from '../../lib/libraryDisplay'
import type {
  DieAssemblyRecord,
  DieRecord,
  DieTypeRecord,
  LibraryDbUserRecord,
  MaterialRecord,
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
  users: LibraryDbUserRecord[]
  currentUserId: number | null
  selectedMaterialId: number | null
  onSelectMaterialId: (nextId: number | null) => void
  isLoading: boolean
  error: string | null
}

export function LibraryMaterialsView({
  materials,
  users,
  currentUserId,
  selectedMaterialId,
  onSelectMaterialId,
  isLoading,
  error,
}: LibraryMaterialsViewProps) {
  const [textFilter, setTextFilter] = useState('')
  const [ownerFilters, setOwnerFilters] = useState<Set<OwnerFilterKey>>(new Set(DEFAULT_OWNER_FILTERS))
  const [selectedUserId, setSelectedUserId] = useSelectedUserState(users, currentUserId)

  const usersById = useMemo(() => {
    return new Map(users.map((entry) => [entry.user_id, entry]))
  }, [users])

  const normalizedFilter = textFilter.trim().toLowerCase()

  const filteredMaterials = useMemo(() => {
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

      const name = formatLibraryName(entry.name).toLowerCase()
      const haystack = `${entry.material_id} ${name} ${entry.source} ${entry.source_version} ${entry.file_name}`
      return haystack.includes(normalizedFilter)
    })
  }, [currentUserId, materials, normalizedFilter, ownerFilters, selectedUserId])

  const toggleOwnerFilter = (filterKey: OwnerFilterKey) => {
    setOwnerFilters((previous) => toggleFilter(previous, filterKey))
  }

  return (
    <div className="h-full min-h-0 flex flex-col bg-gray-50">
      <div className="ui-pane-header space-y-2">
        <div className="ui-pane-title">Materials</div>
        <input
          type="text"
          className="ui-input"
          value={textFilter}
          onChange={(event) => setTextFilter(event.target.value)}
          placeholder="Filter materials by id, name, source, or file..."
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
        {isLoading && <EmptyState message="Loading materials..." />}
        {!isLoading && filteredMaterials.length === 0 && <EmptyState message="No materials found for active filters." />}

        {!isLoading &&
          filteredMaterials.map((entry) => {
            const isSelected = selectedMaterialId === entry.material_id
            const propertiesText = JSON.stringify(entry.properties || {}, null, 2)

            return (
              <button
                key={entry.material_id}
                type="button"
                onClick={() => onSelectMaterialId(isSelected ? null : entry.material_id)}
                className={`ui-card ui-card-body w-full text-left space-y-2 ${
                  isSelected ? 'border-blue-600 bg-blue-50' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="font-semibold text-sm text-gray-900">{formatLibraryName(entry.name)}</div>
                  <div className="text-xs text-gray-500">ID: {entry.material_id}</div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-700">
                  <div>Owner: {getOwnerLabel(entry.owner_id, usersById)}</div>
                  <div>Source: {entry.source || '-'}</div>
                  <div>Source version: {entry.source_version || '-'}</div>
                  <div>File: {entry.file_name || '-'}</div>
                  <div>Created: {formatTimestamp(entry.created_at)}</div>
                  <div>Obsolete: {entry.is_obsolete ? 'Yes' : 'No'}</div>
                  <div>Obsolete at: {formatTimestamp(entry.obsolete_at)}</div>
                </div>
                {isSelected && (
                  <div className="rounded border border-gray-200 bg-white px-2 py-2">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
                      Properties
                    </div>
                    <pre className="overflow-x-auto text-[11px] leading-5 text-gray-700 whitespace-pre-wrap">
                      {propertiesText}
                    </pre>
                  </div>
                )}
              </button>
            )
          })}
      </div>
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
