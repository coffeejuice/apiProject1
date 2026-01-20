import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useSessionStore } from './stores/useSessionStore'
import { apiClient } from './lib/apiClient'
import LoginPage from './pages/LoginPage'
import AppPage from './pages/AppPage'

function App() {
  const { isAuthenticated, initialize, logout } = useSessionStore()

  useEffect(() => {
    initialize()

    // Set up global authentication error handler
    apiClient.setOnUnauthenticated(() => {
      logout()
      // The Navigate will happen automatically due to isAuthenticated changing
    })
  }, [initialize, logout])

  return (
    <Routes>
      <Route
        path="/login"
        element={!isAuthenticated ? <LoginPage /> : <Navigate to="/app" />}
      />
      <Route
        path="/app/*"
        element={isAuthenticated ? <AppPage /> : <Navigate to="/login" />}
      />
      <Route path="/" element={<Navigate to="/app" />} />
    </Routes>
  )
}

export default App
