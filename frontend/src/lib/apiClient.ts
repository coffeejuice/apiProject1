import type { ApiResponse } from '../types/api'

type QueryParams = Record<string, string | number | boolean | null | undefined>

interface RequestOptions {
  params?: QueryParams
  body?: unknown
  headers?: Record<string, string>
}

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE'

const LOOPBACK_DEFAULT_BASE_URL = 'http://127.0.0.1:8001'
const LOOPBACK_HOSTNAMES = new Set(['127.0.0.1', 'localhost', '::1'])
const viteEnv = (
  import.meta as { env?: Record<string, string | boolean | undefined> }
).env
const isDevMode = viteEnv?.DEV === true || viteEnv?.MODE === 'development'

function normalizeApiBaseUrl(url: string): string {
  if (!url) {
    return ''
  }

  const trimmed = url.trim().replace(/\/+$/, '')
  if (!trimmed) {
    return ''
  }

  if (!isDevMode) {
    return trimmed
  }

  try {
    const parsed = new URL(trimmed)
    if (LOOPBACK_HOSTNAMES.has(parsed.hostname.toLowerCase())) {
      return parsed.origin
    }
  } catch {
    return LOOPBACK_DEFAULT_BASE_URL
  }

  return LOOPBACK_DEFAULT_BASE_URL
}

function formatErrorDetail(detail: unknown): string | undefined {
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    const lines = detail
      .map((entry) => {
        if (!entry || typeof entry !== 'object') {
          return String(entry)
        }

        const record = entry as Record<string, unknown>
        const message =
          (typeof record.msg === 'string' && record.msg) ||
          (typeof record.message === 'string' && record.message) ||
          (typeof record.error === 'string' && record.error) ||
          ''

        const location = Array.isArray(record.loc)
          ? record.loc
              .filter((token): token is string | number => typeof token === 'string' || typeof token === 'number')
              .map(String)
              .filter((token) => token !== 'body' && token !== 'query' && token !== 'path')
              .join('.')
          : ''

        if (location && message) {
          return `${location}: ${message}`
        }

        if (message) {
          return message
        }

        return JSON.stringify(record)
      })
      .filter((line) => line && line.trim().length > 0)

    return lines.length > 0 ? lines.join('\n') : undefined
  }

  if (detail && typeof detail === 'object') {
    const record = detail as Record<string, unknown>
    return (
      (typeof record.message === 'string' && record.message) ||
      (typeof record.error === 'string' && record.error) ||
      JSON.stringify(record)
    )
  }

  return undefined
}

class ApiClient {
  private baseUrl: string
  private token: string | null = null
  private onUnauthenticated: (() => void) | null = null

  constructor(baseUrl: string) {
    this.baseUrl = this.normalizeBaseUrl(baseUrl)
  }

  setBaseUrl(url: string): void {
    this.baseUrl = this.normalizeBaseUrl(url)
  }

  getBaseUrl(): string {
    return this.baseUrl
  }

  setToken(token: string | null): void {
    this.token = token
  }

  getToken(): string | null {
    return this.token
  }

  setOnUnauthenticated(callback: (() => void) | null): void {
    this.onUnauthenticated = callback
  }

  async get<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return this.request<T>('GET', path, options)
  }

  async post<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return this.request<T>('POST', path, options)
  }

  async patch<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return this.request<T>('PATCH', path, options)
  }

  async delete<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return this.request<T>('DELETE', path, options)
  }

  private async request<T>(
    method: HttpMethod,
    path: string,
    options?: RequestOptions
  ): Promise<ApiResponse<T>> {
    const url = this.buildUrl(path, options?.params)
    const headers: Record<string, string> = {
      ...(options?.headers || {}),
    }

    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`
    }

    let body: BodyInit | undefined
    if (options?.body !== undefined) {
      if (typeof FormData !== 'undefined' && options.body instanceof FormData) {
        body = options.body
      } else {
        if (!headers['Content-Type']) {
          headers['Content-Type'] = 'application/json'
        }
        body = JSON.stringify(options.body)
      }
    }

    try {
      const response = await fetch(url, {
        method,
        headers,
        body,
      })

      if (response.status === 401 && this.onUnauthenticated) {
        this.onUnauthenticated()
      }

      const parsed = await this.parseResponse(response)
      return parsed as ApiResponse<T>
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Network error'
      return {
        ok: false,
        status: 0,
        errorMessage: message,
      }
    }
  }

  private async parseResponse(response: Response): Promise<ApiResponse<unknown>> {
    const status = response.status
    let data: unknown = undefined
    let errorMessage: string | undefined = undefined
    let errorCode: string | undefined = undefined

    const text = await response.text()
    if (text) {
      try {
        data = JSON.parse(text)
      } catch {
        data = text
      }
    }

    if (!response.ok) {
      if (typeof data === 'string') {
        errorMessage = data
      } else if (data && typeof data === 'object') {
        const dataObj = data as Record<string, unknown>
        errorMessage =
          formatErrorDetail(dataObj.detail) ||
          (typeof dataObj.message === 'string' && dataObj.message) ||
          (typeof dataObj.error === 'string' && dataObj.error) ||
          undefined
        errorCode =
          (typeof dataObj.code === 'string' && dataObj.code) ||
          (typeof dataObj.error_code === 'string' && dataObj.error_code) ||
          undefined
      }
    }

    return {
      ok: response.ok,
      status,
      data: response.ok ? data : undefined,
      errorMessage,
      errorCode,
    }
  }

  private buildUrl(path: string, params?: QueryParams): string {
    const baseUrl = this.baseUrl || ''
    const url = new URL(path, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`)

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value === undefined || value === null) {
          return
        }
        url.searchParams.append(key, String(value))
      })
    }

    return url.toString()
  }

  private normalizeBaseUrl(url: string): string {
    return normalizeApiBaseUrl(url)
  }
}

const envBaseUrl = (viteEnv?.VITE_API_BASE_URL as string | undefined) || ''

const defaultBaseUrl = normalizeApiBaseUrl(envBaseUrl || LOOPBACK_DEFAULT_BASE_URL)

export const apiClient = new ApiClient(defaultBaseUrl)
