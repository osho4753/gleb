import React, { useState, useEffect } from 'react'
import { toast } from 'sonner'
import config from '../config'
import { useAuth } from '../services/authService'

interface LoginScreenProps {
  onLoginSuccess: (password: string) => void
}

export function LoginScreen({ onLoginSuccess }: LoginScreenProps) {
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
    const { authenticatedFetch } = useAuth()
  const [showDemo, setShowDemo] = useState(false)

  // Проверяем, есть ли сохраненный пароль при загрузке
  useEffect(() => {
    const savedPassword = localStorage.getItem('tenant_password')
    if (savedPassword) {
      // Автоматически пробуем войти с сохраненным паролем
      verifyPassword(savedPassword)
    }
  }, [])

  const verifyPassword = async (testPassword: string) => {
    setLoading(true)

    try {
      // Тестируем пароль, делая запрос к API
      const response = await authenticatedFetch(`${config.apiBaseUrl}/transactions`, {
        headers: {
          'X-Auth-Password': testPassword,
        },
      })

      if (response.status === 200) {
        // Пароль верный, сохраняем и входим
        localStorage.setItem('tenant_password', testPassword)
        onLoginSuccess(testPassword)
        toast.success('Вход выполнен успешно!')
      } else if (response.status === 401) {
        // Неверный пароль
        localStorage.removeItem('tenant_password')
        toast.error('Неверный пароль доступа')
      } else {
        // Другая ошибка
        toast.error('Ошибка подключения к серверу')
      }
    } catch (error) {
      console.error('Login error:', error)
      toast.error('Не удается подключиться к серверу')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!password.trim()) {
      toast.error('Введите пароль')
      return
    }

    verifyPassword(password)
  }

  const handleDemoLogin = (demoPassword: string, orgName: string) => {
    setPassword(demoPassword)
    toast.info(`Пробуем войти как "${orgName}"...`)
    verifyPassword(demoPassword)
  }

  const handleLogout = () => {
    localStorage.removeItem('tenant_password')
    setPassword('')
    toast.info('Выход выполнен')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="max-w-md w-full space-y-8">
        {/* Логотип и заголовок */}
        <div className="text-center">
          <div className="mx-auto h-20 w-20 bg-indigo-600 rounded-full flex items-center justify-center mb-4">
            <svg
              className="h-12 w-12 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
          </div>
          <h2 className="text-3xl font-bold text-gray-900">Панель Обменника</h2>
          <p className="mt-2 text-gray-600">
            Введите пароль доступа к вашей организации
          </p>
        </div>

        {/* Форма входа */}
        <div className="bg-white p-8 rounded-xl shadow-lg">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                Пароль доступа
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                placeholder="Введите пароль..."
                disabled={loading}
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 text-white py-3 px-4 rounded-lg hover:bg-indigo-700 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {loading ? (
                <>
                  <svg
                    className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  Проверяем...
                </>
              ) : (
                'Войти'
              )}
            </button>
          </form>

          {/* Демо кнопки */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-gray-500">Демо доступ:</span>
              <button
                onClick={() => setShowDemo(!showDemo)}
                className="text-sm text-indigo-600 hover:text-indigo-800"
              >
                {showDemo ? 'Скрыть' : 'Показать'}
              </button>
            </div>

            {showDemo && (
              <div className="space-y-2">
                <button
                  onClick={() =>
                    handleDemoLogin('admin123', 'Дефолтная организация')
                  }
                  className="w-full text-left px-3 py-2 text-sm bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                  disabled={loading}
                >
                  🏢 admin123 - Дефолтная организация
                </button>
                <button
                  onClick={() =>
                    handleDemoLogin('test123', 'Тестовая организация')
                  }
                  className="w-full text-left px-3 py-2 text-sm bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                  disabled={loading}
                >
                  🧪 test123 - Тестовая организация
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Информация */}
        <div className="text-center text-sm text-gray-500">
          <p>Каждая организация имеет изолированные данные</p>
          <p>Обратитесь к администратору для получения пароля</p>
        </div>

        {/* Кнопка выхода (если есть сохраненный пароль) */}
        {localStorage.getItem('tenant_password') && (
          <div className="text-center">
            <button
              onClick={handleLogout}
              className="text-sm text-gray-500 hover:text-gray-700 underline"
            >
              Выйти из текущей организации
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
