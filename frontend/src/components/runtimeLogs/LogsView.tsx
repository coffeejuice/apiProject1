import { useEffect, useMemo, useState } from 'react'

import { apiClient } from '../../lib/apiClient'
import type { LogClearResponse, LogEntry, LogServicesResponse, LogServiceSummary, LogTailResponse } from '../../types/api'

const LOG_SERVICES = ['api', 'pre', 'post', 'coordinator'] as const
const LOG_VIEW_STATE_KEY = 'forgelab-logs-view-state'
const LOG_SEVERITY_FILTERS = [
  { id: 'all', label: 'All records' },
  { id: 'warnings_errors', label: 'Warnings + errors' },
  { id: 'errors', label: 'Errors only' },
] as const

type LogServiceName = (typeof LOG_SERVICES)[number]
type LogSeverityFilter = (typeof LOG_SEVERITY_FILTERS)[number]['id']

export interface LogFocusRequest {
  service: LogServiceName
  query: string
  severityFilter?: LogSeverityFilter
  workerName?: string
  nonce: number
}

interface PersistedLogsViewState {
  selectedService?: string
  selectedWorker?: string
  lineCount?: number
  severityFilter?: LogSeverityFilter
  query?: string
}

interface LogsViewProps {
  focusRequest?: LogFocusRequest | null
}

function loadPersistedState(): PersistedLogsViewState {
  try {
    const rawValue = window.sessionStorage.getItem(LOG_VIEW_STATE_KEY)
    if (!rawValue) {
      return {}
    }
    const parsed = JSON.parse(rawValue)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function persistState(state: PersistedLogsViewState) {
  try {
    window.sessionStorage.setItem(LOG_VIEW_STATE_KEY, JSON.stringify(state))
  } catch {
    // Session persistence is a convenience only.
  }
}

function formatTime(value: string | undefined): string {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

function levelClass(level: string | undefined): string {
  switch ((level || '').toUpperCase()) {
    case 'ERROR':
    case 'CRITICAL':
      return 'bg-red-50 text-red-700 border-red-200'
    case 'WARNING':
      return 'bg-amber-50 text-amber-700 border-amber-200'
    case 'DEBUG':
      return 'bg-slate-50 text-slate-500 border-slate-200'
    default:
      return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  }
}

function entryDetails(entry: LogEntry): string {
  const hidden = new Set([
    'timestamp',
    'level',
    'service',
    'worker_name',
    'hostname',
    'pid',
    'logger',
    'module',
    'function',
    'line',
    'message',
    'exception',
    'raw',
  ])
  const details = Object.entries(entry).filter(([key]) => !hidden.has(key))
  if (details.length === 0) {
    return ''
  }
  return JSON.stringify(Object.fromEntries(details), null, 2)
}

function serviceByName(services: LogServiceSummary[], service: string): LogServiceSummary | undefined {
  return services.find((entry) => entry.service === service)
}

function isLogServiceName(value: unknown): value is LogServiceName {
  return typeof value === 'string' && LOG_SERVICES.includes(value as LogServiceName)
}

function isSeverityFilter(value: unknown): value is LogSeverityFilter {
  return typeof value === 'string' && LOG_SEVERITY_FILTERS.some((filter) => filter.id === value)
}

function isErrorLevel(level: string | undefined): boolean {
  const normalized = (level || '').toUpperCase()
  return normalized === 'ERROR' || normalized === 'CRITICAL'
}

function isWarningOrErrorLevel(level: string | undefined): boolean {
  const normalized = (level || '').toUpperCase()
  return normalized === 'WARNING' || normalized === 'ERROR' || normalized === 'CRITICAL'
}

function matchesSeverityFilter(entry: LogEntry, filter: LogSeverityFilter): boolean {
  if (filter === 'errors') {
    return isErrorLevel(entry.level)
  }
  if (filter === 'warnings_errors') {
    return isWarningOrErrorLevel(entry.level)
  }
  return true
}

function workerNamesForService(services: LogServiceSummary[], service: string): string[] {
  const workers = serviceByName(services, service)?.workers.map((worker) => worker.worker_name) || []
  return workers.length > 0 ? workers : [service]
}

export default function LogsView({ focusRequest = null }: LogsViewProps) {
  const persistedState = useMemo(loadPersistedState, [])
  const [services, setServices] = useState<LogServiceSummary[]>([])
  const [logsRoot, setLogsRoot] = useState('')
  const [selectedService, setSelectedService] = useState<string>(() => (
    isLogServiceName(persistedState.selectedService) ? persistedState.selectedService : 'api'
  ))
  const [selectedWorker, setSelectedWorker] = useState<string>(() => persistedState.selectedWorker || 'api')
  const [lineCount, setLineCount] = useState(() => {
    const persistedLineCount = Number(persistedState.lineCount)
    return Number.isFinite(persistedLineCount) && persistedLineCount >= 1 ? Math.min(persistedLineCount, 2000) : 300
  })
  const [severityFilter, setSeverityFilter] = useState<LogSeverityFilter>(() => (
    isSeverityFilter(persistedState.severityFilter) ? persistedState.severityFilter : 'all'
  ))
  const [query, setQuery] = useState(() => persistedState.query || '')
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [filePath, setFilePath] = useState('')
  const [missing, setMissing] = useState(false)
  const [isLoadingServices, setIsLoadingServices] = useState(false)
  const [isLoadingTail, setIsLoadingTail] = useState(false)
  const [isClearing, setIsClearing] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedServiceSummary = useMemo(
    () => serviceByName(services, selectedService),
    [selectedService, services]
  )

  const workerNames = useMemo(() => {
    return workerNamesForService(services, selectedService)
  }, [selectedService, services])

  const visibleEntries = useMemo(() => {
    return entries.filter((entry) => matchesSeverityFilter(entry, severityFilter))
  }, [entries, severityFilter])

  const loadServices = async () => {
    setIsLoadingServices(true)
    setError(null)
    const response = await apiClient.get<LogServicesResponse>('/logs/services')
    setIsLoadingServices(false)
    if (!response.ok || !response.data) {
      setError(response.errorMessage || 'Failed to load log services.')
      return
    }
    setServices(response.data.services || [])
    setLogsRoot(response.data.logs_root || '')
  }

  const loadTail = async (overrides: {
    service?: string
    worker?: string
    lines?: number
    query?: string
  } = {}) => {
    const service = overrides.service || selectedService
    const worker = overrides.worker || selectedWorker
    const lines = overrides.lines || lineCount
    const searchQuery = overrides.query ?? query
    setIsLoadingTail(true)
    setError(null)
    const response = await apiClient.get<LogTailResponse>(`/logs/${service}/tail`, {
      params: {
        worker_name: worker,
        lines,
        q: searchQuery.trim() || undefined,
      },
    })
    setIsLoadingTail(false)
    if (!response.ok || !response.data) {
      setEntries([])
      setError(response.errorMessage || 'Failed to load log file.')
      return
    }
    setEntries(response.data.entries || [])
    setFilePath(response.data.file_path || '')
    setMissing(Boolean(response.data.missing))
  }

  const clearSelectedLogFile = async () => {
    const confirmed = window.confirm(`Clear log file for ${selectedService}/${selectedWorker}?`)
    if (!confirmed) {
      return
    }
    setIsClearing(true)
    setError(null)
    const response = await apiClient.delete<LogClearResponse>(`/logs/${selectedService}`, {
      params: {
        worker_name: selectedWorker,
      },
    })
    setIsClearing(false)
    if (!response.ok || !response.data?.cleared) {
      setError(response.errorMessage || 'Failed to clear log file.')
      return
    }
    setEntries([])
    setMissing(false)
    setFilePath(response.data.file_path || filePath)
    await loadServices()
    await loadTail()
  }

  useEffect(() => {
    void loadServices()
  }, [])

  useEffect(() => {
    persistState({
      selectedService,
      selectedWorker,
      lineCount,
      severityFilter,
      query,
    })
  }, [lineCount, query, selectedService, selectedWorker, severityFilter])

  useEffect(() => {
    const workers = selectedServiceSummary?.workers || []
    if (workers.length > 0 && !workers.some((worker) => worker.worker_name === selectedWorker)) {
      setSelectedWorker(workers[0].worker_name)
      return
    }
    if (workers.length === 0 && selectedWorker !== selectedService) {
      setSelectedWorker(selectedService)
    }
  }, [selectedService, selectedServiceSummary?.workers, selectedWorker])

  useEffect(() => {
    void loadTail()
  }, [selectedService, selectedWorker])

  useEffect(() => {
    if (!focusRequest) {
      return
    }
    const nextService = focusRequest.service
    const nextWorkers = workerNamesForService(services, nextService)
    const nextWorker = focusRequest.workerName && nextWorkers.includes(focusRequest.workerName)
      ? focusRequest.workerName
      : nextWorkers[0] || nextService
    const nextLineCount = Math.max(lineCount, 1000)
    const nextSeverityFilter = focusRequest.severityFilter || 'warnings_errors'
    setSelectedService(nextService)
    setSelectedWorker(nextWorker)
    setQuery(focusRequest.query)
    setSeverityFilter(nextSeverityFilter)
    setLineCount(nextLineCount)
    void loadTail({
      service: nextService,
      worker: nextWorker,
      lines: nextLineCount,
      query: focusRequest.query,
    })
  }, [focusRequest?.nonce])

  useEffect(() => {
    if (!autoRefresh) {
      return undefined
    }
    const intervalId = window.setInterval(() => {
      void loadServices()
      void loadTail()
    }, 5000)
    return () => window.clearInterval(intervalId)
  }, [autoRefresh, selectedService, selectedWorker, lineCount, query])

  return (
    <section className="flex h-full min-h-0 flex-col bg-[#fbfbfa]">
      <div className="border-b border-[rgba(55,53,47,0.09)] bg-[#fbfbfa] px-5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[15px] font-semibold text-[rgba(55,53,47,0.88)]">Logs</h1>
            <div className="mt-0.5 text-[11px] text-[rgba(55,53,47,0.48)]">
              API, Pre, Post, and Coordinator local files. Solver logs are excluded.
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="ui-btn" onClick={() => void loadServices()} disabled={isLoadingServices}>
              Reload files
            </button>
            <button type="button" className="ui-btn-primary" onClick={() => void loadTail()} disabled={isLoadingTail}>
              Refresh
            </button>
            <button
              type="button"
              className="ui-btn"
              onClick={() => void clearSelectedLogFile()}
              disabled={isClearing || isLoadingTail}
              title="Clear log file of selected service/worker"
            >
              {isClearing ? 'Clearing...' : 'Clear log file'}
            </button>
            <label className="flex items-center gap-1.5 text-[12px] text-[rgba(55,53,47,0.68)]">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(event) => setAutoRefresh(event.target.checked)}
              />
              Auto
            </label>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-full border border-[rgba(55,53,47,0.12)] bg-white p-0.5">
            {LOG_SERVICES.map((service) => (
              <button
                key={service}
                type="button"
                onClick={() => setSelectedService(service)}
                className={`rounded-full px-3 py-1 text-[12px] transition ${
                  selectedService === service
                    ? 'bg-[rgba(55,53,47,0.88)] text-white'
                    : 'text-[rgba(55,53,47,0.62)] hover:bg-[rgba(55,53,47,0.06)]'
                }`}
              >
                {service}
              </button>
            ))}
          </div>

          <select
            value={selectedWorker}
            onChange={(event) => setSelectedWorker(event.target.value)}
            className="ui-input h-8 w-44"
          >
            {workerNames.map((worker) => (
              <option key={worker} value={worker}>
                {worker}
              </option>
            ))}
          </select>

          <div className="inline-flex rounded-full border border-[rgba(55,53,47,0.12)] bg-white p-0.5">
            {LOG_SEVERITY_FILTERS.map((filter) => (
              <button
                key={filter.id}
                type="button"
                onClick={() => setSeverityFilter(filter.id)}
                className={`rounded-full px-2.5 py-1 text-[11px] transition ${
                  severityFilter === filter.id
                    ? 'bg-[rgba(55,53,47,0.82)] text-white'
                    : 'text-[rgba(55,53,47,0.62)] hover:bg-[rgba(55,53,47,0.06)]'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <input
            type="number"
            min={1}
            max={2000}
            value={lineCount}
            onChange={(event) => setLineCount(Number(event.target.value) || 300)}
            className="ui-input h-8 w-24"
            aria-label="Log lines"
          />

          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                void loadTail()
              }
            }}
            placeholder="Filter text..."
            className="ui-input h-8 min-w-52 flex-1"
          />
          <button type="button" className="ui-btn h-8" onClick={() => void loadTail()} disabled={isLoadingTail}>
            Search
          </button>
          {query ? (
            <button
              type="button"
              className="ui-btn h-8"
              onClick={() => {
                setQuery('')
                void loadTail({ query: '' })
              }}
              disabled={isLoadingTail}
            >
              Clear search
            </button>
          ) : null}
        </div>

        <div className="mt-2 truncate text-[11px] text-[rgba(55,53,47,0.45)]">
          Root: {logsRoot || '—'} · File: {filePath || '—'} · Showing {visibleEntries.length} / {entries.length} loaded records
        </div>
      </div>

      {error ? (
        <div className="mx-5 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {missing ? (
        <div className="mx-5 mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Log file does not exist yet. Start the selected process and refresh.
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-auto px-5 py-3">
        <div className="overflow-hidden rounded-lg border border-[rgba(55,53,47,0.10)] bg-white">
          <table className="min-w-full border-collapse text-left text-[12px]">
            <thead className="sticky top-0 bg-[#f5f4f1] text-[rgba(55,53,47,0.58)]">
              <tr>
                <th className="w-44 border-b border-[rgba(55,53,47,0.10)] px-2 py-1.5 font-medium">Time</th>
                <th className="w-24 border-b border-[rgba(55,53,47,0.10)] px-2 py-1.5 font-medium">Level</th>
                <th className="w-52 border-b border-[rgba(55,53,47,0.10)] px-2 py-1.5 font-medium">Logger</th>
                <th className="border-b border-[rgba(55,53,47,0.10)] px-2 py-1.5 font-medium">Message</th>
              </tr>
            </thead>
            <tbody>
              {visibleEntries.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-[rgba(55,53,47,0.45)]">
                    No log lines to show.
                  </td>
                </tr>
              ) : (
                visibleEntries.map((entry, index) => {
                  const details = entryDetails(entry)
                  return (
                    <tr key={`${entry.timestamp || 'line'}-${index}`} className="border-b border-[rgba(55,53,47,0.06)] align-top">
                      <td className="px-2 py-1.5 font-mono text-[11px] text-[rgba(55,53,47,0.52)]">
                        {formatTime(entry.timestamp)}
                      </td>
                      <td className="px-2 py-1.5">
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${levelClass(entry.level)}`}>
                          {entry.level || 'LOG'}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 font-mono text-[11px] text-[rgba(55,53,47,0.58)]">
                        <div>{entry.logger || '—'}</div>
                        <div className="text-[10px] text-[rgba(55,53,47,0.38)]">
                          {entry.function ? `${entry.function}:${entry.line ?? ''}` : ''}
                        </div>
                      </td>
                      <td className="px-2 py-1.5 text-[rgba(55,53,47,0.82)]">
                        <div className="whitespace-pre-wrap break-words">{entry.message || ''}</div>
                        {entry.exception ? (
                          <pre className="mt-1 whitespace-pre-wrap rounded bg-red-50 px-2 py-1 text-[11px] text-red-700">
                            {String(entry.exception)}
                          </pre>
                        ) : null}
                        {details ? (
                          <pre className="mt-1 whitespace-pre-wrap rounded bg-[#f8f8f7] px-2 py-1 text-[11px] text-[rgba(55,53,47,0.58)]">
                            {details}
                          </pre>
                        ) : null}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
