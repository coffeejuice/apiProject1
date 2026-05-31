import { create } from 'zustand'
import { apiClient } from '../lib/apiClient'
import type { User, LoginRequest, LoginResponse, RegisterRequest } from '../types/api'
import { extractField } from '../lib/utils'

interface SessionState {
  token: string | null
  user: User | null
  baseUrl: string
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  setBaseUrl: (url: string) => void
  login: (credentials: LoginRequest) => Promise<boolean>
  register: (data: RegisterRequest) => Promise<boolean>
  logout: () => void
  fetchMe: () => Promise<boolean>
  initialize: () => void
}

const TOKEN_KEY = 'forgelab-token'
const BASE_URL_KEY = 'forgelab-base-url'
const DEFAULT_BASE_URL = 'http://127.0.0.1:8001'

function buildAuthErrorMessage(
  mode: 'login' | 'register',
  errorMessage: string | undefined,
  status: number
): string {
  const message = (errorMessage || '').trim()

  if (!message) {
    if (status === 0) {
      return 'Cannot reach API server. Check API Settings and server connection.'
    }

    return mode === 'register'
      ? 'Registration failed. Check input fields and try again.'
      : 'Login failed. Check credentials and try again.'
  }

  const normalized = message.toLowerCase()

  if (mode === 'register') {
    if (normalized.includes('login already registered')) {
      return 'Username is already registered.\nUse a different username or sign in to the existing account.'
    }

    if (normalized.includes('email already registered')) {
      return 'Email is already registered.\nUse a different email or sign in to the existing account.'
    }

    if (status === 422) {
      return `Registration validation failed:\n${message}`
    }
  }

  if (mode === 'login' && normalized.includes('incorrect username or password')) {
    return 'Incorrect username or password.'
  }

  return message
}

export const useSessionStore = create<SessionState>((set, get) => ({
  token: null,
  user: null,
  baseUrl: DEFAULT_BASE_URL,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  setBaseUrl: (url: string) => {
    apiClient.setBaseUrl(url)
    const normalizedBaseUrl = apiClient.getBaseUrl()
    localStorage.setItem(BASE_URL_KEY, normalizedBaseUrl)
    set({ baseUrl: normalizedBaseUrl })
  },

  login: async (credentials: LoginRequest) => {
    set({ isLoading: true, error: null })

    const response = await apiClient.post<LoginResponse>('/auth/login', {
      body: credentials,
    })

    if (!response.ok) {
      set({
        isLoading: false,
        error: buildAuthErrorMessage('login', response.errorMessage, response.status),
      })
      return false
    }

    // Extract token from response (tolerant)
    const token = extractField<string>(
      response.data as Record<string, unknown>,
      'access_token',
      'token',
      'accessToken'
    )

    if (!token) {
      set({ isLoading: false, error: 'No token received from server' })
      return false
    }

    // Save token
    localStorage.setItem(TOKEN_KEY, token)
    apiClient.setToken(token)
    set({ token, isAuthenticated: true })

    // Fetch user info
    const success = await get().fetchMe()
    set({ isLoading: false })
    return success
  },

  register: async (data: RegisterRequest) => {
    set({ isLoading: true, error: null })

    const response = await apiClient.post<User>('/auth/register', {
      body: data,
    })

    if (!response.ok) {
      set({
        isLoading: false,
        error: buildAuthErrorMessage('register', response.errorMessage, response.status),
      })
      return false
    }

    // After successful registration, automatically log in
    set({ isLoading: false })
    return get().login({ login: data.login, password: data.password })
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY)
    apiClient.setToken(null)
    set({
      token: null,
      user: null,
      isAuthenticated: false,
      error: null,
    })
  },

  fetchMe: async () => {
    const response = await apiClient.get<User>('/auth/me')

    if (!response.ok) {
      set({ error: response.errorMessage || 'Failed to fetch user info' })
      return false
    }

    set({ user: response.data || null, error: null })
    return true
  },

  initialize: () => {
    // Load base URL
    const savedBaseUrl = localStorage.getItem(BASE_URL_KEY)
    if (savedBaseUrl) {
      apiClient.setBaseUrl(savedBaseUrl)
      const normalizedBaseUrl = apiClient.getBaseUrl()
      if (normalizedBaseUrl !== savedBaseUrl) {
        localStorage.setItem(BASE_URL_KEY, normalizedBaseUrl)
      }
      set({ baseUrl: normalizedBaseUrl })
    } else {
      apiClient.setBaseUrl(DEFAULT_BASE_URL)
      set({ baseUrl: apiClient.getBaseUrl() })
    }

    // Load token
    const savedToken = localStorage.getItem(TOKEN_KEY)
    if (savedToken) {
      apiClient.setToken(savedToken)
      set({ token: savedToken, isAuthenticated: true })

      // Fetch user info in background
      get().fetchMe()
    }
  },
}))
