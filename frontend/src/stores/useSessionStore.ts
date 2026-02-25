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
        error: response.errorMessage || 'Login failed',
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
        error: response.errorMessage || 'Registration failed',
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
