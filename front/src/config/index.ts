// API configuration
export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'https://gleb.onrender.com',
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
}

export default config
