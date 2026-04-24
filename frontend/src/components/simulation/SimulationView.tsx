import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { apiClient } from '../../lib/apiClient'
import type {
  DocumentWorkflowRecord,
  LibraryDbUserRecord,
  WorkflowDocumentStatusListResponse,
  WorkflowDocumentStatusRow,
  WorkflowPriorityUpdateRequest,
  WorkflowSimulationReorderRequest,
  WorkflowSimulationStatusListResponse,
  WorkflowSimulationStatusRow,
  WorkflowSolverPcStatusListResponse,
  WorkflowSolverPcStatusRow,
} from '../../types/api'
import Tooltip from '../ui/Tooltip'


interface SimulationViewProps {
  users: LibraryDbUserRecord[]
  currentUserId: number | null
}

type OwnerFilterMode = 'current' | 'all' | 'selected'

function PlayToolIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M6 4.75v10.5c0 .45.5.72.88.47l8-5.25a.56.56 0 0 0 0-.94l-8-5.25A.56.56 0 0 0 6 4.75Z"
        fill="currentColor"
      />
    </svg>
  )
}

function CurrentUserIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M10 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-5 6v-.75A4.25 4.25 0 0 1 9.25 11h1.5A4.25 4.25 0 0 1 15 15.25V16"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function AllUsersIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M6.5 9a2.25 2.25 0 1 0 0-4.5A2.25 2.25 0 0 0 6.5 9Zm7 0a1.9 1.9 0 1 0 0-3.8 1.9 1.9 0 0 0 0 3.8ZM3.75 15.5V15A3.5 3.5 0 0 1 7.25 11.5h.5A3.5 3.5 0 0 1 11.25 15v.5m1-.25A2.75 2.75 0 0 1 15 12.5h.25A2.75 2.75 0 0 1 18 15.25v.25"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function SelectedUserIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M10 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-5 6v-.75A4.25 4.25 0 0 1 9.25 11h1.5A4.25 4.25 0 0 1 15 15.25V16M14 5.5l1 1 2-2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function PauseIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M7 5.25v9.5M13 5.25v9.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  )
}

function ContinueIcon({ className }: { className?: string }) {
  return <PlayToolIcon className={className} />
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M15.5 9.5a5.5 5.5 0 1 1-1.1-3.3M15.5 4.5v3.2h-3.2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function DragHandleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <circle cx="7" cy="6" r="1.1" />
      <circle cx="13" cy="6" r="1.1" />
      <circle cx="7" cy="10" r="1.1" />
      <circle cx="13" cy="10" r="1.1" />
      <circle cx="7" cy="14" r="1.1" />
      <circle cx="13" cy="14" r="1.1" />
    </svg>
  )
}

function formatDateTime(value?: string | null): string {
  if (!value) {
    return '—'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return '—'
  }
  return parsed.toLocaleString()
}

function formatQueueText(queuePosition?: number | null): string {
  if (!queuePosition) {
    return '—'
  }
  return `#${queuePosition}`
}

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined) {
    return '—'
  }
  return `${value}%`
}

function formatDurationDays(value?: number | null): string {
  if (value === null || value === undefined) {
    return '—'
  }
  return `${value.toFixed(2)} d`
}

function resolveStatusMeta(state: string): { label: string; classes: string } {
  switch (state) {
    case 'running':
      return { label: 'Running', classes: 'bg-emerald-100 text-emerald-800 border-emerald-200' }
    case 'queued':
      return { label: 'Queued', classes: 'bg-sky-100 text-sky-800 border-sky-200' }
    case 'waiting_pre':
    case 'draft_waiting_pre':
      return { label: 'Waiting pre', classes: 'bg-amber-100 text-amber-800 border-amber-200' }
    case 'paused':
      return { label: 'Paused', classes: 'bg-orange-100 text-orange-800 border-orange-200' }
    case 'finished':
      return { label: 'Finished', classes: 'bg-slate-200 text-slate-700 border-slate-300' }
    case 'failed':
      return { label: 'Failed', classes: 'bg-rose-100 text-rose-800 border-rose-200' }
    case 'fixed':
      return { label: 'Fixed', classes: 'bg-indigo-100 text-indigo-800 border-indigo-200' }
    default:
      return { label: 'Draft', classes: 'bg-zinc-100 text-zinc-700 border-zinc-200' }
  }
}

function resolveServerStatusMeta(state: string): { label: string; classes: string } {
  switch (state) {
    case 'busy':
      return { label: 'Busy', classes: 'bg-emerald-100 text-emerald-800 border-emerald-200' }
    case 'idle':
      return { label: 'Idle', classes: 'bg-sky-100 text-sky-800 border-sky-200' }
    default:
      return { label: 'Offline', classes: 'bg-zinc-100 text-zinc-700 border-zinc-200' }
  }
}

function StatusPill({ state }: { state: string }) {
  const meta = resolveStatusMeta(state)
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-2 py-1 text-xs font-semibold ${meta.classes}`}>
      <span className="h-2 w-2 rounded-full bg-current opacity-70" />
      {meta.label}
    </span>
  )
}

function ServerStatusPill({ state }: { state: string }) {
  const meta = resolveServerStatusMeta(state)
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-2 py-1 text-xs font-semibold ${meta.classes}`}>
      <span className="h-2 w-2 rounded-full bg-current opacity-70" />
      {meta.label}
    </span>
  )
}

function RunStopSwitch({
  active,
  disabled,
  onClick,
}: {
  active: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`relative inline-flex h-6 w-11 items-center rounded-full border transition ${
        active
          ? 'border-emerald-600 bg-emerald-500'
          : 'border-slate-300 bg-slate-300'
      } disabled:cursor-not-allowed disabled:opacity-50`}
      aria-label={active ? 'Stop automation' : 'Run automation'}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
          active ? 'translate-x-5' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

function OwnerFilterButton({
  active,
  label,
  onClick,
  children,
}: {
  active: boolean
  label: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Tooltip content={label}>
      <button
        type="button"
        onClick={onClick}
        aria-label={label}
        className={`ui-btn h-9 w-9 p-0 ${active ? 'border-blue-600 bg-blue-50 text-blue-700' : 'text-gray-700'}`}
      >
        {children}
      </button>
    </Tooltip>
  )
}

export default function SimulationView({ users, currentUserId }: SimulationViewProps) {
  const [documents, setDocuments] = useState<WorkflowDocumentStatusRow[]>([])
  const [simulations, setSimulations] = useState<WorkflowSimulationStatusRow[]>([])
  const [solverPcs, setSolverPcs] = useState<WorkflowSolverPcStatusRow[]>([])
  const [ownerFilterMode, setOwnerFilterMode] = useState<OwnerFilterMode>('current')
  const [selectedOwnerId, setSelectedOwnerId] = useState<number | null>(currentUserId)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastLoadedAt, setLastLoadedAt] = useState<string | null>(null)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [draggedSimulationId, setDraggedSimulationId] = useState<number | null>(null)

  useEffect(() => {
    if (currentUserId !== null && selectedOwnerId === null) {
      setSelectedOwnerId(currentUserId)
    }
  }, [currentUserId, selectedOwnerId])

  const loadData = async () => {
    setIsLoading(true)
    setError(null)

    const [documentsResponse, simulationsResponse, solverPcsResponse] = await Promise.all([
      apiClient.get<WorkflowDocumentStatusListResponse>('/workflow/documents'),
      apiClient.get<WorkflowSimulationStatusListResponse>('/workflow/simulations'),
      apiClient.get<WorkflowSolverPcStatusListResponse>('/workflow/solver-pcs'),
    ])

    if (!documentsResponse.ok || !simulationsResponse.ok || !solverPcsResponse.ok) {
      setError(
        documentsResponse.errorMessage ||
          simulationsResponse.errorMessage ||
          solverPcsResponse.errorMessage ||
          'Failed to load simulation dashboard.'
      )
    }

    setDocuments(documentsResponse.data?.documents || [])
    setSimulations(simulationsResponse.data?.simulations || [])
    setSolverPcs(solverPcsResponse.data?.solver_pcs || [])
    setLastLoadedAt(new Date().toISOString())
    setIsLoading(false)
  }

  useEffect(() => {
    void loadData()
  }, [])

  const effectiveOwnerId = ownerFilterMode === 'current'
    ? currentUserId
    : ownerFilterMode === 'selected'
      ? selectedOwnerId
      : null

  const filteredDocuments = useMemo(() => {
    if (ownerFilterMode === 'all' || effectiveOwnerId === null) {
      return documents
    }
    return documents.filter((entry) => entry.owner_user_id === effectiveOwnerId)
  }, [documents, effectiveOwnerId, ownerFilterMode])

  const filteredSimulations = useMemo(() => {
    if (ownerFilterMode === 'all' || effectiveOwnerId === null) {
      return simulations
    }
    return simulations.filter((entry) => entry.owner_user_id === effectiveOwnerId)
  }, [effectiveOwnerId, ownerFilterMode, simulations])

  const sortedUsers = useMemo(() => {
    return [...users].sort((left, right) => left.login.localeCompare(right.login))
  }, [users])

  const performDocumentAction = async (documentId: number, endpoint: string, body?: DocumentWorkflowRecord | Record<string, unknown>) => {
    setBusyKey(`document:${documentId}:${endpoint}`)
    const response = await apiClient.post<DocumentWorkflowRecord>(endpoint, body ? { body } : undefined)
    setBusyKey(null)
    if (!response.ok) {
      setError(response.errorMessage || 'Failed to update document workflow state.')
      return
    }
    await loadData()
  }

  const performVersionAction = async (
    documentVersionId: number,
    endpoint: string,
    method: 'POST' | 'PATCH' = 'POST',
    body?: WorkflowPriorityUpdateRequest,
  ) => {
    setBusyKey(`version:${documentVersionId}:${endpoint}`)
    const response = method === 'PATCH'
      ? await apiClient.patch<DocumentWorkflowRecord>(endpoint, body ? { body } : undefined)
      : await apiClient.post<DocumentWorkflowRecord>(endpoint, body ? { body } : undefined)
    setBusyKey(null)
    if (!response.ok) {
      setError(response.errorMessage || 'Failed to update simulation workflow state.')
      return
    }
    await loadData()
  }

  const handleDocumentRunToggle = async (row: WorkflowDocumentStatusRow) => {
    if (!row.document_fixed) {
      await performDocumentAction(row.document_id, `/documents/${row.document_id}/workflow/queue`)
      return
    }
    if (!row.document_version_id) {
      return
    }
    if (row.automation_active) {
      await performVersionAction(row.document_version_id, `/document-versions/${row.document_version_id}/workflow/cancel`)
      return
    }
    if (row.workflow_state === 'paused') {
      await performVersionAction(row.document_version_id, `/document-versions/${row.document_version_id}/workflow/resume`)
      return
    }
    await performVersionAction(row.document_version_id, `/document-versions/${row.document_version_id}/workflow/retry`)
  }

  const handleSimulationRunToggle = async (row: WorkflowSimulationStatusRow) => {
    if (row.automation_active) {
      await performVersionAction(row.document_version_id, `/document-versions/${row.document_version_id}/workflow/cancel`)
      return
    }
    if (row.workflow_state === 'paused') {
      await performVersionAction(row.document_version_id, `/document-versions/${row.document_version_id}/workflow/resume`)
      return
    }
    await performVersionAction(row.document_version_id, `/document-versions/${row.document_version_id}/workflow/retry`)
  }

  const handlePauseContinue = async (documentVersionId: number, workflowState: string) => {
    if (workflowState === 'paused') {
      await performVersionAction(documentVersionId, `/document-versions/${documentVersionId}/workflow/resume`)
      return
    }
    await performVersionAction(documentVersionId, `/document-versions/${documentVersionId}/workflow/pause`)
  }

  const reorderVisibleSubset = (
    allRows: WorkflowSimulationStatusRow[],
    visibleRows: WorkflowSimulationStatusRow[],
    draggedId: number,
    targetId: number,
  ): WorkflowSimulationStatusRow[] => {
    const visibleIds = visibleRows.map((entry) => entry.document_version_id)
    const draggedIndex = visibleIds.indexOf(draggedId)
    const targetIndex = visibleIds.indexOf(targetId)
    if (draggedIndex < 0 || targetIndex < 0 || draggedIndex === targetIndex) {
      return allRows
    }

    const nextVisible = [...visibleRows]
    const [draggedEntry] = nextVisible.splice(draggedIndex, 1)
    nextVisible.splice(targetIndex, 0, draggedEntry)

    const visibleIdSet = new Set(visibleIds)
    let replacementIndex = 0
    return allRows.map((entry) => {
      if (!visibleIdSet.has(entry.document_version_id)) {
        return entry
      }
      const replacement = nextVisible[replacementIndex]
      replacementIndex += 1
      return replacement
    })
  }

  const handleSimulationDrop = async (targetId: number) => {
    if (!draggedSimulationId || draggedSimulationId === targetId) {
      setDraggedSimulationId(null)
      return
    }

    const nextSimulations = reorderVisibleSubset(simulations, filteredSimulations, draggedSimulationId, targetId)
    setDraggedSimulationId(null)
    setSimulations(nextSimulations)
    setBusyKey(`reorder:${draggedSimulationId}`)

    const payload: WorkflowSimulationReorderRequest = {
      ordered_document_version_ids: nextSimulations.map((entry) => entry.document_version_id),
    }
    const response = await apiClient.patch<{ updated_document_version_ids: number[] }>('/workflow/simulations/reorder', {
      body: payload,
    })
    setBusyKey(null)
    if (!response.ok) {
      setError(response.errorMessage || 'Failed to reorder simulation queue.')
      await loadData()
      return
    }
    await loadData()
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-slate-100">
      <div className="ui-toolbar">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-700">
            <PlayToolIcon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="ui-toolbar-title">Simulation</div>
            <div className="ui-toolbar-meta">
              Queue controls, workflow state, and solver PC status.
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xs text-slate-500">Last refresh: {formatDateTime(lastLoadedAt)}</div>
          <button type="button" className="ui-btn gap-2" onClick={() => void loadData()} disabled={isLoading}>
            <RefreshIcon className="h-4 w-4" />
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
        <section className="ui-card">
          <div className="ui-card-body flex flex-wrap items-center gap-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Owner filter</div>
            <div className="flex items-center gap-2">
              <OwnerFilterButton
                active={ownerFilterMode === 'current'}
                label="Current user"
                onClick={() => setOwnerFilterMode('current')}
              >
                <CurrentUserIcon className="h-4 w-4" />
              </OwnerFilterButton>
              <OwnerFilterButton
                active={ownerFilterMode === 'all'}
                label="All users"
                onClick={() => setOwnerFilterMode('all')}
              >
                <AllUsersIcon className="h-4 w-4" />
              </OwnerFilterButton>
              <OwnerFilterButton
                active={ownerFilterMode === 'selected'}
                label="Selected user"
                onClick={() => setOwnerFilterMode('selected')}
              >
                <SelectedUserIcon className="h-4 w-4" />
              </OwnerFilterButton>
            </div>
            {ownerFilterMode === 'selected' ? (
              <select
                className="ui-select w-56"
                value={selectedOwnerId ?? ''}
                onChange={(event) => setSelectedOwnerId(event.target.value ? Number(event.target.value) : null)}
              >
                <option value="">Select user…</option>
                {sortedUsers.map((entry) => (
                  <option key={entry.user_id} value={entry.user_id}>
                    {entry.full_name ? `${entry.login} · ${entry.full_name}` : entry.login}
                  </option>
                ))}
              </select>
            ) : null}
            {error ? <div className="text-xs text-rose-700">{error}</div> : null}
          </div>
        </section>

        <section className="ui-card">
          <div className="ui-pane-header">
            <div className="ui-pane-title">Documents</div>
          </div>
          <div className="ui-card-body overflow-x-auto">
            <table className="min-w-full text-xs text-slate-700">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-3 py-2 font-semibold">Name</th>
                  <th className="px-3 py-2 font-semibold">Run / Stop</th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                  <th className="px-3 py-2 font-semibold">Queue</th>
                  <th className="px-3 py-2 font-semibold">Pause / Continue</th>
                  <th className="px-3 py-2 font-semibold">Owner</th>
                  <th className="px-3 py-2 font-semibold">Project</th>
                  <th className="px-3 py-2 font-semibold">Ops</th>
                  <th className="px-3 py-2 font-semibold">Progress</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocuments.map((row) => (
                  <tr key={row.document_id} className="border-b border-slate-100">
                    <td className="px-3 py-2 align-top">
                      <div className="font-semibold text-slate-900">{row.document_name}</div>
                      <div className="text-[11px] text-slate-500">
                        doc #{row.document_id}{row.document_version_id ? ` · ver #${row.document_version_id}` : ''}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <RunStopSwitch
                        active={row.automation_active}
                        disabled={busyKey !== null}
                        onClick={() => void handleDocumentRunToggle(row)}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill state={row.workflow_state} />
                    </td>
                    <td className="px-3 py-2">
                      <div className="ui-field-readonly w-16 justify-center">{formatQueueText(row.queue_position)}</div>
                    </td>
                    <td className="px-3 py-2">
                      {row.document_version_id && row.document_fixed ? (
                        <button
                          type="button"
                          className="ui-btn gap-2"
                          disabled={busyKey !== null}
                          onClick={() => void handlePauseContinue(row.document_version_id!, row.workflow_state)}
                        >
                          {row.workflow_state === 'paused' ? (
                            <ContinueIcon className="h-3.5 w-3.5" />
                          ) : (
                            <PauseIcon className="h-3.5 w-3.5" />
                          )}
                          {row.workflow_state === 'paused' ? 'Continue' : 'Pause'}
                        </button>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2">{row.owner_login}</td>
                    <td className="px-3 py-2">{row.project_name}</td>
                    <td className="px-3 py-2">{row.operations_count ?? '—'}</td>
                    <td className="px-3 py-2">{formatPercent(row.simulation_percent)}</td>
                  </tr>
                ))}
                {!isLoading && filteredDocuments.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-3 py-6 text-center text-slate-500">
                      No documents match the active owner filter.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="ui-card">
          <div className="ui-pane-header">
            <div className="ui-pane-title">Simulations</div>
          </div>
          <div className="ui-card-body overflow-x-auto">
            <table className="min-w-full text-xs text-slate-700">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-3 py-2 font-semibold">Name</th>
                  <th className="px-3 py-2 font-semibold">Run / Stop</th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                  <th className="px-3 py-2 font-semibold">Queue</th>
                  <th className="px-3 py-2 font-semibold">Pause / Continue</th>
                  <th className="px-3 py-2 font-semibold">Owner</th>
                  <th className="px-3 py-2 font-semibold">Server</th>
                  <th className="px-3 py-2 font-semibold">ETA</th>
                  <th className="px-3 py-2 font-semibold">Progress</th>
                </tr>
              </thead>
              <tbody>
                {filteredSimulations.map((row) => (
                  <tr
                    key={row.document_version_id}
                    draggable={busyKey === null}
                    onDragStart={() => setDraggedSimulationId(row.document_version_id)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => void handleSimulationDrop(row.document_version_id)}
                    className={`border-b border-slate-100 ${draggedSimulationId === row.document_version_id ? 'bg-blue-50' : ''}`}
                  >
                    <td className="px-3 py-2 align-top">
                      <div className="flex items-start gap-2">
                        <div className="mt-0.5 cursor-grab text-slate-400">
                          <DragHandleIcon className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="font-semibold text-slate-900">{row.document_name}</div>
                          <div className="text-[11px] text-slate-500">
                            {row.version_name} · sim #{row.document_version_id}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <RunStopSwitch
                        active={row.automation_active}
                        disabled={busyKey !== null}
                        onClick={() => void handleSimulationRunToggle(row)}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill state={row.workflow_state} />
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <div className="ui-field-readonly w-16 justify-center">{formatQueueText(row.queue_position)}</div>
                        <div className="text-[11px] text-slate-500">prio {row.simulation_priority ?? '—'}</div>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        className="ui-btn gap-2"
                        disabled={busyKey !== null}
                        onClick={() => void handlePauseContinue(row.document_version_id, row.workflow_state)}
                      >
                        {row.workflow_state === 'paused' ? (
                          <ContinueIcon className="h-3.5 w-3.5" />
                        ) : (
                          <PauseIcon className="h-3.5 w-3.5" />
                        )}
                        {row.workflow_state === 'paused' ? 'Continue' : 'Pause'}
                      </button>
                    </td>
                    <td className="px-3 py-2">{row.owner_login}</td>
                    <td className="px-3 py-2">{row.simulation_server_name || '—'}</td>
                    <td className="px-3 py-2">{formatDurationDays(row.simulation_expected_duration_days)}</td>
                    <td className="px-3 py-2">{formatPercent(row.simulation_percent)}</td>
                  </tr>
                ))}
                {!isLoading && filteredSimulations.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-3 py-6 text-center text-slate-500">
                      No simulations match the active owner filter.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="ui-card">
          <div className="ui-pane-header">
            <div className="ui-pane-title">Solver PCs</div>
          </div>
          <div className="ui-card-body overflow-x-auto">
            <table className="min-w-full text-xs text-slate-700">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-3 py-2 font-semibold">Name</th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                  <th className="px-3 py-2 font-semibold">Current simulation</th>
                  <th className="px-3 py-2 font-semibold">Host</th>
                  <th className="px-3 py-2 font-semibold">CPU</th>
                  <th className="px-3 py-2 font-semibold">RAM free</th>
                  <th className="px-3 py-2 font-semibold">Disk free</th>
                  <th className="px-3 py-2 font-semibold">Last update</th>
                </tr>
              </thead>
              <tbody>
                {solverPcs.map((row) => (
                  <tr key={row.server_id} className="border-b border-slate-100">
                    <td className="px-3 py-2">
                      <div className="font-semibold text-slate-900">{row.name}</div>
                      <div className="text-[11px] text-slate-500">server #{row.server_id}</div>
                    </td>
                    <td className="px-3 py-2">
                      <ServerStatusPill state={row.worker_state} />
                    </td>
                    <td className="px-3 py-2">
                      {row.document_name ? (
                        <div>
                          <div className="font-medium text-slate-800">{row.document_name}</div>
                          <div className="text-[11px] text-slate-500">{row.version_name || '—'}</div>
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div>{row.hostname}</div>
                      <div className="text-[11px] text-slate-500">{row.ip}</div>
                    </td>
                    <td className="px-3 py-2">
                      {row.cpu_count ?? '—'} / {row.max_threads_count ?? '—'}
                    </td>
                    <td className="px-3 py-2">{row.ram_free_size_gb?.toFixed(1) ?? '—'} GB</td>
                    <td className="px-3 py-2">{row.hdd_free_size_gb?.toFixed(1) ?? '—'} GB</td>
                    <td className="px-3 py-2">{formatDateTime(row.time_updated || row.time_started)}</td>
                  </tr>
                ))}
                {!isLoading && solverPcs.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-3 py-6 text-center text-slate-500">
                      No solver PCs registered.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  )
}
