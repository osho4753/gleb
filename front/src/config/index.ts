import { authService } from '../services/authService'

// API configuration
export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'https://gleb.onrender.com',
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
}

// Аутентифицированный fetch для использования в компонентах
export const authenticatedFetch =
  authService.authenticatedFetch.bind(authService)

// Аутентифицированный JSON запрос
export const authenticatedRequest =
  authService.authenticatedRequest.bind(authService)

export default config
