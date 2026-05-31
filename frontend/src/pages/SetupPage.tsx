import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { apiClient } from '../lib/apiClient'
import type {
  ResetAdminPasswordRequest,
  ResetAdminPasswordResponse,
  SeedLibraryResponse,
  SeedRunSummary,
  SetupStatusResponse,
} from '../types/api'

interface SetupPageProps {
  status: SetupStatusResponse | null
  isStatusLoading: boolean
  isAuthenticated: boolean
  onRefreshStatus: () => Promise<void>
}

function getLastRunError(lastRun: SeedRunSummary | null | undefined): string | null {
  const error = lastRun?.details?.error
  return typeof error === 'string' && error.trim().length > 0 ? error : null
}

export default function SetupPage({
  status,
  isStatusLoading,
  isAuthenticated,
  onRefreshStatus,
}: SetupPageProps) {
  const [isSeeding, setIsSeeding] = useState(false)
  const [seedError, setSeedError] = useState<string | null>(null)
  const [seedSuccess, setSeedSuccess] = useState<string | null>(null)
  const [newAdminPassword, setNewAdminPassword] = useState('')
  const [confirmAdminPassword, setConfirmAdminPassword] = useState('')
  const [isResettingAdminPassword, setIsResettingAdminPassword] = useState(false)
  const [resetAdminPasswordError, setResetAdminPasswordError] = useState<string | null>(null)
  const [resetAdminPasswordSuccess, setResetAdminPasswordSuccess] = useState<string | null>(null)

  const canSeed = useMemo(() => {
    if (!status) {
      return false
    }
    if (status.can_seed_without_auth) {
      return true
    }
    return isAuthenticated
  }, [status, isAuthenticated])

  const lastRunError = useMemo(() => getLastRunError(status?.last_run), [status?.last_run])

  const handleSeed = async () => {
    setSeedError(null)
    setSeedSuccess(null)
    setIsSeeding(true)

    try {
      const response = await apiClient.post<SeedLibraryResponse>('/setup/seed-library')

      if (!response.ok || !response.data) {
        setSeedError(response.errorMessage || 'Failed to seed library')
        return
      }

      setSeedSuccess(`Seed completed (run #${response.data.run_id}).`)
      await onRefreshStatus()
    } finally {
      setIsSeeding(false)
    }
  }

  const handleResetAdminPassword = async () => {
    setResetAdminPasswordError(null)
    setResetAdminPasswordSuccess(null)

    if (!newAdminPassword || newAdminPassword.length < 8) {
      setResetAdminPasswordError('Password must be at least 8 characters.')
      return
    }
    if (newAdminPassword !== confirmAdminPassword) {
      setResetAdminPasswordError('Password confirmation does not match.')
      return
    }

    setIsResettingAdminPassword(true)
    const response = await apiClient.post<ResetAdminPasswordResponse>('/setup/reset-admin-password', {
      body: {
        new_password: newAdminPassword,
      } satisfies ResetAdminPasswordRequest,
    })
    setIsResettingAdminPassword(false)

    if (!response.ok || !response.data) {
      setResetAdminPasswordError(response.errorMessage || 'Failed to reset admin password.')
      return
    }

    setResetAdminPasswordSuccess(`Password updated for user '${response.data.login}'.`)
    setNewAdminPassword('')
    setConfirmAdminPassword('')
  }

  return (
    <div className="ui-shell min-h-screen p-4">
      <div className="max-w-3xl mx-auto space-y-3">
        <div className="ui-card ui-card-body">
          <h1 className="text-sm font-semibold text-gray-900">Setup & Seeding</h1>
          <p className="text-xs text-gray-600 mt-1">
            Use this page on first launch, or run seeding again as an administrator.
          </p>
        </div>

        <div className="ui-card ui-card-body space-y-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="ui-btn"
              onClick={() => void onRefreshStatus()}
              disabled={isStatusLoading}
            >
              {isStatusLoading ? 'Refreshing...' : 'Refresh Status'}
            </button>
            <button
              type="button"
              className="ui-btn-primary"
              onClick={handleSeed}
              disabled={!canSeed || isSeeding || isStatusLoading}
            >
              {isSeeding ? 'Seeding...' : 'Run Library Seed'}
            </button>
            <Link className="ui-btn" to="/app">
              Open App
            </Link>
            {!isAuthenticated && (
              <Link className="ui-btn" to="/login">
                Login
              </Link>
            )}
          </div>

          {!canSeed && (
            <div className="text-xs text-amber-700 border border-amber-300 bg-amber-50 rounded p-2">
              Administrator login is required to seed this environment.
            </div>
          )}

          {seedError && (
            <div className="text-xs text-red-700 border border-red-300 bg-red-50 rounded p-2">
              {seedError}
            </div>
          )}
          {seedSuccess && (
            <div className="text-xs text-green-700 border border-green-300 bg-green-50 rounded p-2">
              {seedSuccess}
            </div>
          )}
        </div>

        <div className="ui-card ui-card-body">
          <div className="text-xs text-gray-700 space-y-1">
            <div>Needs seed: {status?.needs_seed ? 'yes' : 'no'}</div>
            <div>Can seed without auth: {status?.can_seed_without_auth ? 'yes' : 'no'}</div>
            <div>Config file exists: {status?.file_exists ? 'yes' : 'no'}</div>
            <div>Config hash: {status?.file_hash || 'n/a'}</div>
          </div>
        </div>

        {status?.last_run && (
          <div className="ui-card ui-card-body space-y-2">
            <h2 className="text-xs font-semibold text-gray-900">Last Seed Run</h2>
            <div className="text-xs text-gray-700 space-y-1">
              <div>Run ID: {status.last_run.id}</div>
              <div>Status: {status.last_run.status}</div>
              <div>Started: {status.last_run.started_at || 'n/a'}</div>
              <div>Finished: {status.last_run.finished_at || 'n/a'}</div>
            </div>
            {status.last_run.status === 'failed' && lastRunError && (
              <div className="text-xs text-red-700 border border-red-300 bg-red-50 rounded p-2 whitespace-pre-line">
                {lastRunError}
              </div>
            )}
          </div>
        )}

        <div className="ui-card ui-card-body">
          <h2 className="text-xs font-semibold text-gray-900 mb-2">Table Counts</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
            {Object.entries(status?.counts || {}).map(([tableName, count]) => (
              <div key={tableName} className="ui-badge flex items-center justify-between">
                <span>{tableName}</span>
                <span>{count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="ui-card ui-card-body space-y-3">
          <h2 className="text-xs font-semibold text-gray-900">Admin Password</h2>
          <p className="text-xs text-gray-600">
            Reset password for account <span className="font-semibold">admin</span>.
          </p>

          {!isAuthenticated && (
            <div className="text-xs text-amber-700 border border-amber-300 bg-amber-50 rounded p-2">
              Login as administrator to reset admin password.
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input
              type="password"
              className="ui-input"
              placeholder="New admin password"
              value={newAdminPassword}
              onChange={(e) => setNewAdminPassword(e.target.value)}
              disabled={!isAuthenticated || isResettingAdminPassword}
            />
            <input
              type="password"
              className="ui-input"
              placeholder="Confirm new password"
              value={confirmAdminPassword}
              onChange={(e) => setConfirmAdminPassword(e.target.value)}
              disabled={!isAuthenticated || isResettingAdminPassword}
            />
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="ui-btn-secondary"
              disabled={!isAuthenticated || isResettingAdminPassword}
              onClick={handleResetAdminPassword}
            >
              {isResettingAdminPassword ? 'Updating...' : 'Reset Admin Password'}
            </button>
          </div>

          {resetAdminPasswordError && (
            <div className="text-xs text-red-700 border border-red-300 bg-red-50 rounded p-2">
              {resetAdminPasswordError}
            </div>
          )}
          {resetAdminPasswordSuccess && (
            <div className="text-xs text-green-700 border border-green-300 bg-green-50 rounded p-2">
              {resetAdminPasswordSuccess}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
