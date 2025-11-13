import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { config } from '../config'
import { useAuth } from '../services/authService'
import {
  ExternalLinkIcon,
  CheckCircleIcon,
  XCircleIcon,
  LoaderIcon,
  InfoIcon,
  X,
} from 'lucide-react'

const API_BASE = config.apiBaseUrl

interface GoogleSheetsStatus {
  is_enabled: boolean
  spreadsheet_id?: string
  spreadsheet_url?: string
  connection_status: 'connected' | 'error' | 'not_configured'
  last_updated?: string
}

interface SetupInstructions {
  title: string
  steps: Array<{
    step: number
    title: string
    description: string
  }>
  service_email: string
  note: string
}

interface GoogleSheetsModalProps {
  isOpen: boolean
  onClose: () => void
}

export function GoogleSheetsModal({ isOpen, onClose }: GoogleSheetsModalProps) {
  const { authenticatedFetch } = useAuth()
  const [status, setStatus] = useState<GoogleSheetsStatus | null>(null)
  const [instructions, setInstructions] = useState<SetupInstructions | null>(
    null
  )
  const [loading, setLoading] = useState(false)
  const [spreadsheetUrl, setSpreadsheetUrl] = useState('')

  useEffect(() => {
    if (isOpen) {
      loadStatus()
      loadInstructions()
    }
  }, [isOpen])

  const loadStatus = async () => {
    try {
      const response = await authenticatedFetch(
        `${API_BASE}/google-sheets/status`
      )
      const data = await response.json()
      setStatus(data)
    } catch (error) {
      console.error('Failed to load Google Sheets status:', error)
      toast.error('Не удалось загрузить статус Google Таблиц')
    }
  }

  const loadInstructions = async () => {
    try {
      const response = await authenticatedFetch(
        `${API_BASE}/google-sheets/instructions`
      )
      const data = await response.json()
      setInstructions(data)
    } catch (error) {
      console.error('Failed to load instructions:', error)
    }
  }

  const handleEnable = async () => {
    if (!spreadsheetUrl.trim()) {
      toast.error('Введите ссылку на Google Таблицу')
      return
    }

    setLoading(true)
    try {
      const response = await authenticatedFetch(
        `${API_BASE}/google-sheets/enable`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            spreadsheet_url: spreadsheetUrl.trim(),
          }),
        }
      )

      if (response.ok) {
        await response.json()
        toast.success('Google Таблица успешно подключена!')
        setSpreadsheetUrl('')
        await loadStatus()
      } else {
        const error = await response.json()
        toast.error(
          `Ошибка подключения: ${error.detail || 'Неизвестная ошибка'}`
        )
      }
    } catch (error) {
      console.error('Failed to enable Google Sheets:', error)
      toast.error('Не удалось подключить Google Таблицу')
    } finally {
      setLoading(false)
    }
  }

  const handleDisable = async () => {
    setLoading(true)
    try {
      const response = await authenticatedFetch(
        `${API_BASE}/google-sheets/disable`,
        {
          method: 'POST',
        }
      )

      if (response.ok) {
        toast.success('Google Таблица временно отключена (настройки сохранены)')
        await loadStatus()
      } else {
        toast.error('Не удалось отключить Google Таблицу')
      }
    } catch (error) {
      console.error('Failed to disable Google Sheets:', error)
      toast.error('Ошибка при отключении')
    } finally {
      setLoading(false)
    }
  }

  const handleReEnable = async () => {
    setLoading(true)
    try {
      const response = await authenticatedFetch(
        `${API_BASE}/google-sheets/re-enable`,
        {
          method: 'POST',
        }
      )

      if (response.ok) {
        await response.json()
        toast.success('Google Таблица успешно включена и синхронизирована!')
        await loadStatus()
      } else {
        const error = await response.json()
        toast.error(`Ошибка включения: ${error.detail || 'Неизвестная ошибка'}`)
      }
    } catch (error) {
      console.error('Failed to re-enable Google Sheets:', error)
      toast.error('Не удалось включить Google Таблицу')
    } finally {
      setLoading(false)
    }
  }

  const handleDisconnect = async () => {
    if (
      !confirm('Вы уверены? Это полностью удалит настройки Google Таблицы.')
    ) {
      return
    }

    setLoading(true)
    try {
      const response = await authenticatedFetch(
        `${API_BASE}/google-sheets/disconnect`,
        {
          method: 'DELETE',
        }
      )

      if (response.ok) {
        toast.success('Google Таблица отсоединена')
        await loadStatus()
      } else {
        toast.error('Не удалось отсоединить Google Таблицу')
      }
    } catch (error) {
      console.error('Failed to disconnect Google Sheets:', error)
      toast.error('Ошибка при отсоединении')
    } finally {
      setLoading(false)
    }
  }

  const handleSyncAll = async () => {
    if (
      !confirm(
        'Синхронизировать все существующие данные с Google Таблицей? Это может занять некоторое время.'
      )
    ) {
      return
    }

    setLoading(true)
    try {
      const response = await authenticatedFetch(
        `${API_BASE}/google-sheets/sync-all`,
        {
          method: 'POST',
        }
      )

      if (response.ok) {
        const data = await response.json()
        toast.success(
          `Данные синхронизированы! Транзакций: ${data.synced_transactions}, валют кассы: ${data.synced_cash_assets}, валют прибыли: ${data.synced_profit_currencies}`
        )
      } else {
        const error = await response.json()
        toast.error(
          `Ошибка синхронизации: ${error.detail || 'Неизвестная ошибка'}`
        )
      }
    } catch (error) {
      console.error('Failed to sync all data:', error)
      toast.error('Ошибка при синхронизации данных')
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (connectionStatus: string) => {
    switch (connectionStatus) {
      case 'connected':
        return 'text-green-600'
      case 'error':
        return 'text-red-600'
      default:
        return 'text-gray-500'
    }
  }

  const getStatusIcon = (connectionStatus: string) => {
    switch (connectionStatus) {
      case 'connected':
        return <CheckCircleIcon className="h-5 w-5 text-green-600" />
      case 'error':
        return <XCircleIcon className="h-5 w-5 text-red-600" />
      default:
        return <XCircleIcon className="h-5 w-5 text-gray-500" />
    }
  }

  const getStatusText = (connectionStatus: string) => {
    switch (connectionStatus) {
      case 'connected':
        return 'Подключено'
      case 'error':
        return 'Ошибка соединения'
      default:
        return 'Не настроено'
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Заголовок модального окна */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold text-gray-900">
            Интеграция с Google Таблицами
          </h2>
          <div className="flex items-center space-x-4">
            {status && (
              <div className="flex items-center space-x-2">
                {getStatusIcon(status.connection_status)}
                <span
                  className={`text-sm font-medium ${getStatusColor(
                    status.connection_status
                  )}`}
                >
                  {getStatusText(status.connection_status)}
                </span>
              </div>
            )}
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="h-6 w-6" />
            </button>
          </div>
        </div>

        {/* Содержимое модального окна */}
        <div className="p-6">
          {!status ? (
            <div className="animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
              <div className="h-3 bg-gray-200 rounded w-1/2"></div>
            </div>
          ) : (
            <>
              {/* Текущий статус */}
              <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium text-gray-700">Статус:</span>
                    <span
                      className={`ml-2 ${
                        status.is_enabled ? 'text-green-600' : 'text-red-600'
                      }`}
                    >
                      {status.is_enabled ? 'Включено' : 'Выключено'}
                    </span>
                  </div>
                  {status.spreadsheet_url && (
                    <div>
                      <span className="font-medium text-gray-700">
                        Таблица:
                      </span>
                      <a
                        href={status.spreadsheet_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 text-blue-600 hover:text-blue-800 inline-flex items-center"
                      >
                        Открыть
                        <ExternalLinkIcon className="h-4 w-4 ml-1" />
                      </a>
                    </div>
                  )}
                </div>
              </div>

              {/* Управление */}
              <div className="space-y-4">
                {!status.is_enabled ? (
                  <>
                    {/* Состояние 3: Настроена но отключена */}
                    {status.spreadsheet_id ? (
                      <div className="space-y-4">
                        <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                          <p className="text-sm text-yellow-800 mb-3">
                            📋 Google Таблица была ранее настроена, но временно
                            отключена. Все настройки сохранены.
                          </p>
                        </div>

                        <button
                          onClick={handleReEnable}
                          disabled={loading}
                          className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium flex items-center justify-center"
                        >
                          {loading ? (
                            <LoaderIcon className="h-4 w-4 animate-spin mr-2" />
                          ) : (
                            <>
                              <svg
                                className="h-4 w-4 mr-2"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                                />
                              </svg>
                              Включить снова и синхронизировать
                            </>
                          )}
                        </button>
                      </div>
                    ) : (
                      /* Состояние 1: Не настроена - показываем инструкции сразу */
                      <div className="border rounded-lg p-4 bg-blue-50">
                        <h4 className="font-semibold mb-4 flex items-center">
                          <InfoIcon className="h-5 w-5 mr-2 text-blue-600" />
                          {instructions?.title ||
                            'Как подключить Google Таблицу'}
                        </h4>

                        {instructions && (
                          <div className="space-y-3 mb-4">
                            {instructions.steps.map((step) => (
                              <div key={step.step} className="flex">
                                <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-medium">
                                  {step.step}
                                </div>
                                <div className="ml-3">
                                  <h5 className="font-medium text-gray-900">
                                    {step.title}
                                  </h5>
                                  <p className="text-sm text-gray-600 mt-1">
                                    {step.description}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {instructions && (
                          <div className="bg-yellow-50 p-3 rounded mb-4">
                            <p className="text-sm text-yellow-800">
                              <strong>Email сервиса:</strong>
                              <code className="bg-yellow-100 px-2 py-1 ml-2 rounded text-xs break-all">
                                {instructions.service_email}
                              </code>
                            </p>
                          </div>
                        )}

                        {/* Форма подключения */}
                        <div className="space-y-3">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              Ссылка на Google Таблицу:
                            </label>
                            <input
                              type="url"
                              value={spreadsheetUrl}
                              onChange={(e) =>
                                setSpreadsheetUrl(e.target.value)
                              }
                              placeholder="https://docs.google.com/spreadsheets/d/..."
                              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            />
                          </div>

                          <button
                            onClick={handleEnable}
                            disabled={loading}
                            className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                          >
                            {loading ? (
                              <LoaderIcon className="h-4 w-4 animate-spin" />
                            ) : (
                              'Подключить Google Таблицу'
                            )}
                          </button>
                        </div>

                        {instructions && (
                          <div className="mt-4 p-3 bg-blue-100 rounded">
                            <p className="text-sm text-blue-800">
                              {instructions.note}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  /* Управление включенной интеграцией */
                  <div className="space-y-4">
                    <div className="flex flex-wrap gap-3">
                      <button
                        onClick={handleSyncAll}
                        disabled={loading}
                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center"
                      >
                        {loading ? (
                          <LoaderIcon className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                          <svg
                            className="h-4 w-4 mr-2"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                            />
                          </svg>
                        )}
                        Синхронизировать все данные
                      </button>
                      <button
                        onClick={handleDisable}
                        disabled={loading}
                        className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 transition-colors"
                      >
                        Отключить (настройки сохранятся)
                      </button>
                      <button
                        onClick={handleDisconnect}
                        disabled={loading}
                        className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
                      >
                        Отсоединить полностью
                      </button>
                    </div>

                    <div className="space-y-3">
                      <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                        <p className="text-sm text-green-800">
                          ✅ Google Таблица успешно подключена! Все новые
                          транзакции автоматически синхронизируются с вашей
                          таблицей.
                        </p>
                      </div>

                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                        <p className="text-sm text-blue-800">
                          💡 <strong>Существующие данные:</strong> При первом
                          подключении все ваши существующие транзакции и данные
                          кассы автоматически загружаются в таблицу. Если нужно
                          повторно синхронизировать данные, используйте кнопку
                          "Синхронизировать все данные".
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Футер модального окна */}
        <div className="border-t p-4 bg-gray-50 rounded-b-lg">
          <p className="text-xs text-gray-600 text-center">
            Интеграция позволяет автоматически синхронизировать все ваши
            транзакции с Google Таблицами для дополнительного учета и анализа.
          </p>
        </div>
      </div>
    </div>
  )
}
