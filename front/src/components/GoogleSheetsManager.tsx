import React, { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { config } from '../config'
import { useAuth } from '../services/authService'
import { useCashDesk } from '../services/cashDeskService'

const API_BASE = config.apiBaseUrl

interface GoogleSheetsStatus {
  is_enabled: boolean
  spreadsheet_id?: string
  spreadsheet_url?: string
  connection_status: string
  last_updated?: string
}

export function GoogleSheetsManager() {
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<GoogleSheetsStatus | null>(null)
  const [spreadsheetUrl, setSpreadsheetUrl] = useState('')
  const { authenticatedFetch } = useAuth()
  const { cashDesks, selectedCashDesk, selectedCashDeskId } = useCashDesk()

  // Загрузка статуса Google Sheets
  const loadStatus = async () => {
    try {
      const res = await authenticatedFetch(`${API_BASE}/google-sheets/status`)
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      }
    } catch (error) {
      console.error('Error loading Google Sheets status:', error)
    }
  }

  // Подключение Google Sheets
  const enableGoogleSheets = async () => {
    if (!spreadsheetUrl.trim()) {
      toast.error('Введите ссылку на Google Таблицу')
      return
    }

    setLoading(true)
    try {
      const res = await authenticatedFetch(`${API_BASE}/google-sheets/enable`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          spreadsheet_url: spreadsheetUrl.trim(),
        }),
      })

      if (res.ok) {
        toast.success('Google Sheets успешно подключены!')
        setSpreadsheetUrl('')
        loadStatus()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось подключить Google Sheets')
      }
    } catch (error) {
      toast.error('Ошибка при подключении Google Sheets')
    } finally {
      setLoading(false)
    }
  }

  // Отключение Google Sheets
  const disableGoogleSheets = async () => {
    if (!confirm('Вы уверены что хотите отключить Google Sheets?')) {
      return
    }

    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/google-sheets/disable`,
        {
          method: 'POST',
        }
      )

      if (res.ok) {
        toast.success('Google Sheets отключены')
        loadStatus()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось отключить Google Sheets')
      }
    } catch (error) {
      toast.error('Ошибка при отключении Google Sheets')
    } finally {
      setLoading(false)
    }
  }

  // Синхронизация конкретной кассы
  const syncCashDesk = async (cashDeskId: string, cashDeskName: string) => {
    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/google-sheets/sync-cash-desk/${cashDeskId}`,
        {
          method: 'POST',
        }
      )

      if (res.ok) {
        const result = await res.json()
        toast.success(
          `Касса "${cashDeskName}" синхронизирована! Транзакций: ${result.transactions_count}`
        )
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось синхронизировать кассу')
      }
    } catch (error) {
      toast.error('Ошибка при синхронизации кассы')
    } finally {
      setLoading(false)
    }
  }

  // Синхронизация агрегированного отчета
  const syncAggregateReport = async () => {
    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/google-sheets/sync-aggregate-report`,
        {
          method: 'POST',
        }
      )

      if (res.ok) {
        const result = await res.json()
        toast.success(
          `Агрегированный отчет создан! Касс: ${result.cash_desks_count}, транзакций: ${result.total_transactions}`
        )
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось создать агрегированный отчет')
      }
    } catch (error) {
      toast.error('Ошибка при создании отчета')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  if (!status) {
    return (
      <div className="p-4 text-center text-gray-500">
        Загрузка статуса Google Sheets...
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Google Sheets интеграция</h2>
        <div
          className={`px-3 py-1 rounded-full text-sm font-medium ${
            status.is_enabled
              ? 'bg-green-100 text-green-800'
              : 'bg-gray-100 text-gray-800'
          }`}
        >
          {status.is_enabled ? '✅ Подключено' : '❌ Не подключено'}
        </div>
      </div>

      {/* Статус подключения */}
      {status.is_enabled ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h3 className="font-semibold text-green-800 mb-2">
            Подключено к Google Sheets
          </h3>
          {status.spreadsheet_url && (
            <p className="text-sm text-green-700 mb-3">
              <a
                href={status.spreadsheet_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline font-medium"
              >
                🔗 Открыть таблицу
              </a>
            </p>
          )}

          <div className="flex gap-2">
            <button
              onClick={disableGoogleSheets}
              disabled={loading}
              className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 font-medium"
            >
              Отключить
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-800 mb-4">
            Подключить Google Sheets
          </h3>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Ссылка на Google Таблицу
              </label>
              <input
                type="url"
                value={spreadsheetUrl}
                onChange={(e) => setSpreadsheetUrl(e.target.value)}
                placeholder="https://docs.google.com/spreadsheets/d/..."
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <button
              onClick={enableGoogleSheets}
              disabled={loading}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 font-medium"
            >
              {loading ? 'Подключение...' : 'Подключить'}
            </button>
          </div>
        </div>
      )}

      {/* Синхронизация касс (только если подключено) */}
      {status.is_enabled && (
        <div className="bg-white border border-gray-200 rounded-lg">
          <div className="p-4 border-b">
            <h3 className="text-lg font-semibold">
              Синхронизация данных (Фаза 2)
            </h3>
            <p className="text-sm text-gray-600">
              Каждая касса создает отдельные листы в таблице
            </p>
          </div>

          <div className="p-4 space-y-4">
            {/* Агрегированный отчет */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-semibold text-blue-800 mb-2">
                📊 Общий отчет по всем кассам
              </h4>
              <p className="text-blue-700 text-sm mb-3">
                Создает лист "Общий_Отчет" с данными по всем кассам и сводной
                информацией
              </p>
              <button
                onClick={syncAggregateReport}
                disabled={loading || cashDesks.length === 0}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 font-medium"
              >
                Создать общий отчет
              </button>
            </div>

            {/* Отдельные кассы */}
            <div className="space-y-3">
              <h4 className="font-semibold">🏪 Синхронизация отдельных касс</h4>

              {cashDesks.length === 0 ? (
                <p className="text-gray-500 text-sm">
                  У вас пока нет касс. Создайте кассы в разделе "Управление
                  кассами".
                </p>
              ) : (
                <div className="space-y-2">
                  {cashDesks.map((desk) => (
                    <div
                      key={desk._id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div>
                        <span className="font-medium">{desk.name}</span>
                        <span className="text-sm text-gray-500 ml-2">
                          (создаст листы "Транзакции_{desk.name}" и "Касса_
                          {desk.name}")
                        </span>
                      </div>
                      <button
                        onClick={() => syncCashDesk(desk._id, desk.name)}
                        disabled={loading}
                        className="px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50 font-medium text-sm"
                      >
                        Синхронизировать
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Текущая касса - быстрая синхронизация */}
            {selectedCashDesk && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <h4 className="font-semibold text-yellow-800 mb-2">
                  ⚡ Быстрая синхронизация
                </h4>
                <p className="text-yellow-700 text-sm mb-3">
                  Синхронизировать текущую выбранную кассу:{' '}
                  <strong>{selectedCashDesk.name}</strong>
                </p>
                <button
                  onClick={() =>
                    syncCashDesk(selectedCashDeskId!, selectedCashDesk.name)
                  }
                  disabled={loading}
                  className="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 disabled:opacity-50 font-medium"
                >
                  Синхронизировать "{selectedCashDesk.name}"
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Информация о новой структуре */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-800 mb-2">
          💡 Новая структура Google Sheets (Фаза 2)
        </h4>
        <div className="text-blue-700 text-sm space-y-2">
          <p>
            <strong>Для каждой кассы создаются отдельные листы:</strong>
          </p>
          <ul className="list-disc list-inside space-y-1 ml-4">
            <li>
              <code>"Транзакции_[Название_Кассы]"</code> - все транзакции этой
              кассы
            </li>
            <li>
              <code>"Касса_[Название_Кассы]"</code> - баланс и прибыль этой
              кассы
            </li>
          </ul>
          <p className="mt-3">
            <strong>Агрегированный отчет:</strong>
          </p>
          <ul className="list-disc list-inside space-y-1 ml-4">
            <li>
              <code>"Общий_Отчет"</code> - сводка по всем кассам + все
              транзакции с указанием кассы
            </li>
          </ul>
          <p className="mt-3 text-blue-600">
            🎯 <strong>Преимущества:</strong> Каждый филиал может видеть только
            свои данные, а руководство - общую картину по всем кассам.
          </p>
        </div>
      </div>
    </div>
  )
}

export default GoogleSheetsManager
