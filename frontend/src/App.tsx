import { useCallback, useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useSessionStore } from './stores/useSessionStore'
import { apiClient } from './lib/apiClient'
import type { SetupStatusResponse } from './types/api'
import LoginPage from './pages/LoginPage'
import AppPage from './pages/AppPage'
import SetupPage from './pages/SetupPage'

function App() {
  const { isAuthenticated, initialize, logout } = useSessionStore()
  const [setupStatus, setSetupStatus] = useState<SetupStatusResponse | null>(null)
  const [isSetupLoading, setIsSetupLoading] = useState(true)

  const refreshSetupStatus = useCallback(async () => {
    setIsSetupLoading(true)
    const response = await apiClient.get<SetupStatusResponse>('/setup/status')
    if (response.ok && response.data) {
      setSetupStatus(response.data)
    } else {
      setSetupStatus(null)
    }
    setIsSetupLoading(false)
  }, [])

  useEffect(() => {
    initialize()
    void refreshSetupStatus()

    // Set up global authentication error handler
    apiClient.setOnUnauthenticated(() => {
      logout()
      // The Navigate will happen automatically due to isAuthenticated changing
    })
  }, [initialize, logout, refreshSetupStatus])

  if (isSetupLoading) {
    return (
      <div className="ui-shell min-h-screen flex items-center justify-center text-sm text-gray-600">
        Checking setup status...
      </div>
    )
  }

  const needsSetup = setupStatus?.needs_seed ?? true

  return (
    <Routes>
      <Route
        path="/setup"
        element={(
          <SetupPage
            status={setupStatus}
            isStatusLoading={isSetupLoading}
            isAuthenticated={isAuthenticated}
            onRefreshStatus={refreshSetupStatus}
          />
        )}
      />
      <Route
        path="/login"
        element={!isAuthenticated ? <LoginPage /> : <Navigate to={needsSetup ? '/setup' : '/app'} />}
      />
      <Route
        path="/app/*"
        element={needsSetup ? <Navigate to="/setup" /> : (isAuthenticated ? <AppPage /> : <Navigate to="/login" />)}
      />
      <Route path="/" element={<Navigate to={needsSetup ? '/setup' : '/app'} />} />
    </Routes>
  )
}

export default App
