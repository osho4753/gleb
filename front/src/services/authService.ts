/**
 * Сервис аутентификации для многопользовательской системы
 */
import React from 'react'

const STORAGE_KEY = 'tenant_password'

export interface AuthState {
  isAuthenticated: boolean
  password: string | null
}

export interface TenantInfo {
  tenant_id: string
  name: string
  is_active: boolean
  created_at: string | null
}

class AuthService {
  private listeners: Set<(state: AuthState) => void> = new Set()
  private currentPassword: string | null = null

  constructor() {
    // Загружаем сохраненный пароль при инициализации
    this.currentPassword = localStorage.getItem(STORAGE_KEY)
  }

  /**
   * Получает текущее состояние аутентификации
   */
  getAuthState(): AuthState {
    return {
      isAuthenticated: this.currentPassword !== null,
      password: this.currentPassword,
    }
  }

  /**
   * Выполняет вход в систему
   */
  login(password: string): void {
    this.currentPassword = password
    localStorage.setItem(STORAGE_KEY, password)
    this.notifyListeners()
  }

  /**
   * Выполняет выход из системы
   */
  logout(): void {
    this.currentPassword = null
    localStorage.removeItem(STORAGE_KEY)
    this.notifyListeners()
  }

  /**
   * Получает заголовки для API запросов
   */
  getApiHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (this.currentPassword) {
      headers['X-Auth-Password'] = this.currentPassword
    }

    return headers
  }

  /**
   * Проверяет, является ли ответ ошибкой аутентификации
   */
  isAuthError(status: number): boolean {
    return status === 401 || status === 403
  }

  /**
   * Обрабатывает ошибку аутентификации
   */
  handleAuthError(): void {
    console.warn('Authentication error detected, logging out...')
    this.logout()
  }

  /**
   * Подписывается на изменения состояния аутентификации
   */
  subscribe(listener: (state: AuthState) => void): () => void {
    this.listeners.add(listener)

    // Возвращаем функцию отписки
    return () => {
      this.listeners.delete(listener)
    }
  }

  /**
   * Уведомляет всех слушателей об изменении состояния
   */
  private notifyListeners(): void {
    const state = this.getAuthState()
    this.listeners.forEach((listener) => listener(state))
  }

  /**
   * Выполняет аутентифицированный API запрос
   */
  async authenticatedFetch(
    url: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const headers = {
      ...this.getApiHeaders(),
      ...options.headers,
    }

    // Добавляем базовый URL если он не указан
    const apiBaseUrl =
      import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
    const fullUrl = url.startsWith('http') ? url : `${apiBaseUrl}${url}`

    const response = await fetch(fullUrl, {
      ...options,
      headers,
    })

    // Автоматически обрабатываем ошибки аутентификации
    if (this.isAuthError(response.status)) {
      this.handleAuthError()
      throw new Error('Authentication required')
    }

    return response
  }

  /**
   * Выполняет аутентифицированный JSON запрос
   */
  async authenticatedRequest<T>(
    url: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await this.authenticatedFetch(url, options)

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Получает информацию о текущем tenant
   */
  async getTenantInfo(): Promise<TenantInfo | null> {
    if (!this.currentPassword) {
      return null
    }

    try {
      const response = await this.authenticatedFetch('/tenant-info')

      if (response.ok) {
        return response.json()
      }

      return null
    } catch (error) {
      console.error('Failed to get tenant info:', error)
      return null
    }
  }

  /**
   * Проверяет валидность текущего пароля
   */
  async validateCurrentPassword(): Promise<boolean> {
    if (!this.currentPassword) {
      return false
    }

    try {
      const response = await this.authenticatedFetch('/transactions')

      return response.ok
    } catch (error) {
      console.error('Password validation failed:', error)
      return false
    }
  }
}

// Экспортируем синглтон
export const authService = new AuthService()

// React hook для использования в компонентах
export function useAuth() {
  const [authState, setAuthState] = React.useState<AuthState>(
    authService.getAuthState()
  )

  React.useEffect(() => {
    const unsubscribe = authService.subscribe(setAuthState)
    return unsubscribe
  }, [])

  // Создаем стабильные ссылки на методы
  const login = React.useCallback(
    (password: string) => authService.login(password),
    []
  )

  const logout = React.useCallback(() => authService.logout(), [])

  const authenticatedFetch = React.useCallback(
    (url: string, options?: RequestInit) =>
      authService.authenticatedFetch(url, options),
    []
  )

  const authenticatedRequest = React.useCallback(
    <T>(url: string, options?: RequestInit) =>
      authService.authenticatedRequest<T>(url, options),
    []
  )

  const getTenantInfo = React.useCallback(() => authService.getTenantInfo(), [])

  return {
    ...authState,
    login,
    logout,
    authenticatedFetch,
    authenticatedRequest,
    getTenantInfo,
  }
}
