import { useState, useEffect } from 'react'
import { useAuth } from '../services/authService'
import { config } from '../config'

const API_BASE = config.apiBaseUrl

interface GoogleSheetsIconProps {
  onOpenModal: () => void
}

export function GoogleSheetsIcon({ onOpenModal }: GoogleSheetsIconProps) {
  const { authenticatedFetch } = useAuth()
  const [isEnabled, setIsEnabled] = useState<boolean | null>(null)
  const [showTooltip, setShowTooltip] = useState(false)
  const [showWelcomeNotification, setShowWelcomeNotification] = useState(false)
  const [hasCheckedStatus, setHasCheckedStatus] = useState(false)

  // Проверяем статус при загрузке компонента (для welcome уведомления)
  const checkStatusOnLoad = async () => {
    if (hasCheckedStatus) return

    try {
      const response = await authenticatedFetch(
        `${API_BASE}/google-sheets/status`
      )
      const data = await response.json()
      setIsEnabled(data.is_enabled)
      setHasCheckedStatus(true)

      // Показываем welcome уведомление если Google Sheets не подключен
      if (!data.is_enabled && !data.spreadsheet_id) {
        setTimeout(() => {
          setShowWelcomeNotification(true)
          // Автоматически скрываем через 8 секунд
          setTimeout(() => {
            setShowWelcomeNotification(false)
          }, 8000)
        }, 2000) // Показываем через 2 секунды после загрузки
      }
    } catch (error) {
      console.error('Failed to check Google Sheets status:', error)
      setIsEnabled(false)
      setHasCheckedStatus(true)
    }
  }

  // Проверяем статус при наведении (lazy loading)
  const checkStatus = async () => {
    if (isEnabled !== null) return // уже загружено

    try {
      const response = await authenticatedFetch(
        `${API_BASE}/google-sheets/status`
      )
      const data = await response.json()
      setIsEnabled(data.is_enabled)
    } catch (error) {
      console.error('Failed to check Google Sheets status:', error)
      setIsEnabled(false)
    }
  }

  // Проверяем статус при первой загрузке
  useEffect(() => {
    checkStatusOnLoad()
  }, [])

  return (
    <div className="relative">
      <button
        onClick={onOpenModal}
        onMouseEnter={() => {
          setShowTooltip(true)
          checkStatus()
        }}
        onMouseLeave={() => setShowTooltip(false)}
        className="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors relative group"
        title="Google Таблицы"
      >
        {/* Excel/Sheets Icon */}
        <svg
          className="w-5 h-5"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill={isEnabled ? '#10b981' : 'none'}
            className={isEnabled ? 'text-green-500' : 'text-current'}
          />
          <polyline
            points="14,2 14,8 20,8"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <line
            x1="16"
            y1="13"
            x2="8"
            y2="13"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <line
            x1="16"
            y1="17"
            x2="8"
            y2="17"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <polyline
            points="10,9 9,9 8,9"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>

        {/* Индикатор состояния */}
        {isEnabled !== null && (
          <div
            className={`absolute -top-1 -right-1 w-3 h-3 rounded-full border-2 border-white ${
              isEnabled ? 'bg-green-500' : 'bg-gray-400'
            }`}
          />
        )}
      </button>

      {/* Welcome Notification */}
      {showWelcomeNotification && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-gradient-to-r from-blue-500 to-blue-600 text-white text-sm rounded-lg p-4 shadow-xl z-50">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center">
              <svg
                className="w-5 h-5 mr-2 text-yellow-300"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="font-semibold">Новая возможность!</span>
            </div>
            <button
              onClick={() => setShowWelcomeNotification(false)}
              className="text-blue-200 hover:text-white transition-colors"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>
          <p className="text-blue-100 leading-relaxed mb-3">
            🚀 Подключите <strong>Google Таблицы</strong> для автоматической
            синхронизации всех ваших транзакций и удобного ведения учёта!
          </p>
          <button
            onClick={() => {
              setShowWelcomeNotification(false)
              onOpenModal()
            }}
            className="w-full bg-white text-blue-600 font-semibold py-2 px-4 rounded-md hover:bg-blue-50 transition-colors"
          >
            Подключить сейчас
          </button>
          {/* Стрелка */}
          <div className="absolute top-0 right-6 transform -translate-y-1 w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-blue-500" />
        </div>
      )}

      {/* Tooltip */}
      {showTooltip && !showWelcomeNotification && (
        <div className="absolute right-0 top-full mt-2 w-64 bg-gray-900 text-white text-xs rounded-lg p-3 shadow-lg z-50">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold">Google Таблицы</span>
            {isEnabled !== null && (
              <span
                className={`px-2 py-1 text-xs rounded-full ${
                  isEnabled
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-600 text-gray-200'
                }`}
              >
                {isEnabled ? 'Включено' : 'Выключено'}
              </span>
            )}
          </div>
          <p className="text-gray-300 leading-relaxed">
            {isEnabled
              ? 'Ваши транзакции автоматически синхронизируются с Google Таблицей. Нажмите для управления настройками.'
              : 'Подключите Google Таблицу для автоматической синхронизации транзакций и ведения учёта.'}
          </p>
          {/* Стрелка tooltip */}
          <div className="absolute top-0 right-4 transform -translate-y-1 w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-gray-900" />
        </div>
      )}
    </div>
  )
}
