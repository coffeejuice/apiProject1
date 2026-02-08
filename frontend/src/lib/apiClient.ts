import type { ApiResponse } from '../types/api'

type QueryParams = Record<string, string | number | boolean | null | undefined>

interface RequestOptions {
  params?: QueryParams
  body?: unknown
  headers?: Record<string, string>
}

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE'

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

    let body: string | undefined
    if (options?.body !== undefined) {
      if (!headers['Content-Type']) {
        headers['Content-Type'] = 'application/json'
      }
      body = JSON.stringify(options.body)
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
          (typeof dataObj.detail === 'string' && dataObj.detail) ||
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
    if (!url) {
      return ''
    }
    return url.replace(/\/+$/, '')
  }
}

const envBaseUrl = (
  import.meta as { env?: Record<string, string | undefined> }
).env?.VITE_API_BASE_URL

const defaultBaseUrl = envBaseUrl || 'http://127.0.0.1:8001'

export const apiClient = new ApiClient(defaultBaseUrl)
