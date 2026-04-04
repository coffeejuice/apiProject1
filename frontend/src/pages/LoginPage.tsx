import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useSessionStore } from '../stores/useSessionStore'

export default function LoginPage() {
  const [loginUsername, setLoginUsername] = useState('demo_user')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('password123')
  const [showPassword, setShowPassword] = useState(false)
  const [isRegisterMode, setIsRegisterMode] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [customBaseUrl, setCustomBaseUrl] = useState('')

  const { login, register, isLoading, error, baseUrl, setBaseUrl } = useSessionStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (isRegisterMode) {
      await register({ login: loginUsername, email, password })
    } else {
      await login({ login: loginUsername, password })
    }
  }

  const handleSaveSettings = () => {
    if (customBaseUrl.trim()) {
      setBaseUrl(customBaseUrl.trim())
    }
    setShowSettings(false)
  }

  return (
    <div className="ui-shell min-h-screen flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="ui-card p-4">
          <div className="text-center mb-4">
            <h1 className="text-sm font-semibold text-gray-900">ForgeLab</h1>
            <p className="text-sm text-gray-600 mt-1">
              {isRegisterMode ? 'Create your account' : 'Sign in to your account'}
            </p>
          </div>

          {error && (
            <div className="mb-3 p-2 min-h-[72px] max-h-40 overflow-y-auto bg-red-50 border border-red-200 rounded text-red-700 text-xs whitespace-pre-line">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="login"
                className="block text-xs font-semibold text-gray-700 mb-1"
              >
                Username
              </label>
              <input
                id="login"
                type="text"
                value={loginUsername}
                onChange={(e) => setLoginUsername(e.target.value)}
                className="ui-input"
                required
                disabled={isLoading}
              />
            </div>

            {isRegisterMode && (
              <div>
                <label
                  htmlFor="email"
                  className="block text-xs font-semibold text-gray-700 mb-1"
                >
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="ui-input"
                  required
                  disabled={isLoading}
                />
              </div>
            )}

            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold text-gray-700 mb-1"
              >
                Password
              </label>
              <div className="flex items-center gap-2">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="ui-input flex-1"
                  required
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="ui-btn min-w-[58px]"
                  disabled={isLoading}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="ui-btn-primary w-full"
            >
              {isLoading
                ? (isRegisterMode ? 'Creating account...' : 'Signing in...')
                : (isRegisterMode ? 'Register' : 'Sign in')}
            </button>
          </form>

          <div className="mt-4 text-center">
            <button
              onClick={() => setIsRegisterMode(!isRegisterMode)}
              className="ui-btn"
            >
              {isRegisterMode
                ? 'Already have an account? Sign in'
                : "Don't have an account? Register"}
            </button>
          </div>

          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setCustomBaseUrl(baseUrl)
                  setShowSettings(!showSettings)
                }}
                className="ui-btn"
              >
                API Settings
              </button>
              <Link to="/setup" className="ui-btn">
                Setup
              </Link>
            </div>

            {showSettings && (
              <div className="ui-card ui-card-body mt-3">
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  API Base URL
                </label>
                <input
                  type="text"
                  value={customBaseUrl}
                  onChange={(e) => setCustomBaseUrl(e.target.value)}
                  className="ui-input mb-2"
                  placeholder="http://127.0.0.1:8001"
                />
                <div className="text-xs text-gray-500 mb-3">
                  Current: {baseUrl}
                </div>
                <button
                  onClick={handleSaveSettings}
                  className="ui-btn w-full"
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
