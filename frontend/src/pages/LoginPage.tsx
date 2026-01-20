import { useState } from 'react'
import { useSessionStore } from '../stores/useSessionStore'

export default function LoginPage() {
  const [loginUsername, setLoginUsername] = useState('demo_user')
  const [password, setPassword] = useState('password123')
  const [showSettings, setShowSettings] = useState(false)
  const [customBaseUrl, setCustomBaseUrl] = useState('')

  const { login, isLoading, error, baseUrl, setBaseUrl } = useSessionStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await login({ login: loginUsername, password })
  }

  const handleSaveSettings = () => {
    if (customBaseUrl.trim()) {
      setBaseUrl(customBaseUrl.trim())
    }
    setShowSettings(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-lg shadow-xl p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Techno-Notion</h1>
            <p className="text-gray-600 mt-2">Sign in to your account</p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="login"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Username
              </label>
              <input
                id="login"
                type="text"
                value={loginUsername}
                onChange={(e) => setLoginUsername(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
                disabled={isLoading}
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
                disabled={isLoading}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-200">
            <button
              onClick={() => {
                setCustomBaseUrl(baseUrl)
                setShowSettings(!showSettings)
              }}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              ⚙️ API Settings
            </button>

            {showSettings && (
              <div className="mt-4 p-4 bg-gray-50 rounded border border-gray-200">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  API Base URL
                </label>
                <input
                  type="text"
                  value={customBaseUrl}
                  onChange={(e) => setCustomBaseUrl(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mb-2"
                  placeholder="http://127.0.0.1:8001"
                />
                <div className="text-xs text-gray-500 mb-3">
                  Current: {baseUrl}
                </div>
                <button
                  onClick={handleSaveSettings}
                  className="w-full bg-gray-600 text-white py-2 px-4 rounded-md hover:bg-gray-700 text-sm"
                >
                  Save Settings
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
