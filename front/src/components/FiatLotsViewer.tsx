import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { ChevronDownIcon, RefreshCwIcon } from 'lucide-react'
import { config } from '../config'
import { useAuth } from '../services/authService'
import { useCashDesk } from '../services/cashDeskService'

const API_BASE = config.apiBaseUrl

interface FiatLot {
  _id: string
  currency: string
  remaining: number
  rate: number
  tx_id: string | null
  created_at: string
  meta?: any
}

interface FiatLotsViewerProps {
  onNavigateToHistory?: () => void
}

export function FiatLotsViewer({ onNavigateToHistory }: FiatLotsViewerProps) {
  const [lots, setLots] = useState<FiatLot[]>([])
  const [loading, setLoading] = useState(false)
  const [showOnlyActive, setShowOnlyActive] = useState(true)
  const { authenticatedFetch } = useAuth()
  const { selectedCashDesk } = useCashDesk()
  const [expandedCurrency, setExpandedCurrency] = useState<string | null>(null)

  const currencies = ['USD', 'EUR', 'CZK']

  const fetchLots = async () => {
    setLoading(true)
    try {
      for (const currency of currencies) {
        const url = new URL(`${API_BASE}/transactions/fiat-lots/${currency}`)
        if (selectedCashDesk?._id) {
          url.searchParams.set('cash_desk_id', selectedCashDesk._id)
        }
        const res = await authenticatedFetch(url.toString())
        if (res.ok) {
          const data = await res.json()
          setLots((prev) => {
            // Удаляем старые лоты этой валюты и добавляем новые
            const filtered = prev.filter((lot) => lot.currency !== currency)
            return [...filtered, ...data.lots]
          })
        }
      }
      toast.success('Лоты загружены')
    } catch (error) {
      toast.error('Ошибка при загрузке лотов')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLots()
  }, [selectedCashDesk])

  // Группируем лоты по валютам
  const lotsByCurrency = currencies.reduce((acc, currency) => {
    acc[currency] = lots.filter((lot) => lot.currency === currency)
    return acc
  }, {} as Record<string, FiatLot[]>)

  // Фильтруем по активности
  const getDisplayLots = (currencyLots: FiatLot[]) => {
    return showOnlyActive
      ? currencyLots.filter((lot) => lot.remaining > 0)
      : currencyLots
  }

  return (
    <div className="space-y-6 w-full max-w-full px-4 sm:px-6">
      {/* Заголовок */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <h2 className="text-xl sm:text-2xl font-bold">Фиатные Лоты</h2>
        <button
          onClick={fetchLots}
          disabled={loading}
          className="flex items-center justify-center gap-2 px-3 sm:px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm disabled:opacity-50 flex-1 sm:flex-none"
        >
          <RefreshCwIcon size={16} className={loading ? 'animate-spin' : ''} />
          <span>Обновить</span>
        </button>
      </div>

      {/* Фильтр активные/все */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={showOnlyActive}
            onChange={(e) => setShowOnlyActive(e.target.checked)}
            className="w-4 h-4 text-blue-500 rounded focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-sm font-medium text-gray-700">
            Активные лоты
          </span>
        </label>
      </div>

      {/* Лоты по валютам */}
      <div className="space-y-4">
        {currencies.map((currency) => {
          const currencyLots = lotsByCurrency[currency]
          const displayLots = getDisplayLots(currencyLots)
          const totalRemaining = currencyLots
            .filter((lot) => lot.remaining > 0)
            .reduce((sum, lot) => sum + lot.remaining, 0)

          return (
            <div
              key={currency}
              className="border rounded-lg overflow-hidden bg-white"
            >
              {/* Заголовок валюты */}
              <button
                onClick={() =>
                  setExpandedCurrency(
                    expandedCurrency === currency ? null : currency
                  )
                }
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors border-b"
              >
                <div className="flex items-center gap-3 text-left">
                  <span className="font-bold text-lg text-gray-800 w-16">
                    {currency}
                  </span>
                  <div className="text-sm">
                    <div className="text-gray-600">
                      Лотов: {displayLots.length}
                      {!showOnlyActive && currencyLots.length > 0 && (
                        <span className="text-gray-400">
                          {' '}
                          / {currencyLots.length}
                        </span>
                      )}
                    </div>
                    <div className="text-green-600 font-semibold">
                      Активно: {totalRemaining.toFixed(2)} {currency}
                    </div>
                  </div>
                </div>
                <ChevronDownIcon
                  size={20}
                  className={`text-gray-600 transition-transform ${
                    expandedCurrency === currency ? 'rotate-180' : ''
                  }`}
                />
              </button>

              {/* Таблица лотов */}
              {expandedCurrency === currency && displayLots.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[600px] text-sm">
                    <thead className="bg-gray-50 border-b">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">
                          ID
                        </th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">
                          Remaining
                        </th>
                        <th className="px-4 py-3 text-right font-semibold text-gray-700">
                          Rate
                        </th>
                        <th className="px-4 py-3 text-center font-semibold text-gray-700">
                          Статус
                        </th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">
                          Источник
                        </th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">
                          Дата создания
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {displayLots.map((lot) => {
                        const isActive = lot.remaining > 0
                        const source = lot.meta?.source || 'unknown'
                        const createdAt = new Date(
                          lot.created_at
                        ).toLocaleString('ru-RU')

                        return (
                          <tr
                            key={lot._id}
                            className={isActive ? 'bg-white' : 'bg-gray-50'}
                          >
                            <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                              {lot._id.slice(0, 8)}...
                            </td>
                            <td className="px-4 py-3 text-right font-semibold">
                              {lot.remaining > 0 ? (
                                <span className="text-green-600">
                                  {lot.remaining.toFixed(2)}
                                </span>
                              ) : (
                                <span className="text-gray-400 line-through">
                                  0.00
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-right text-gray-700">
                              {lot.rate.toFixed(6)}
                            </td>
                            <td className="px-4 py-3 text-center">
                              {isActive ? (
                                <span className="inline-block px-2 py-1 bg-green-100 text-green-700 text-xs font-semibold rounded">
                                  Активен
                                </span>
                              ) : (
                                <span className="inline-block px-2 py-1 bg-gray-200 text-gray-600 text-xs font-semibold rounded">
                                  Исчерпан
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              {source === 'fiat_to_crypto' ? (
                                <span className="inline-block px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
                                  Фиат→Крипто
                                </span>
                              ) : source === 'fiat_to_fiat' ? (
                                <span className="inline-block px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded">
                                  Фиат↔Фиат
                                </span>
                              ) : (
                                <span className="text-gray-500 text-xs">
                                  {source}
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-xs text-gray-600">
                              {createdAt}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Пусто */}
              {expandedCurrency === currency && displayLots.length === 0 && (
                <div className="px-4 py-6 text-center text-gray-500">
                  {showOnlyActive
                    ? `Нет активных лотов ${currency}`
                    : `Нет лотов ${currency}`}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Статистика */}
      <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
        <h3 className="font-semibold text-blue-900 mb-3">Статистика</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
          {currencies.map((currency) => {
            const currencyLots = lotsByCurrency[currency]
            const activeLots = currencyLots.filter((lot) => lot.remaining > 0)
            const totalRemaining = activeLots.reduce(
              (sum, lot) => sum + lot.remaining,
              0
            )

            return (
              <div
                key={currency}
                className="bg-white p-3 rounded border border-blue-100"
              >
                <div className="font-semibold text-gray-800">{currency}</div>
                <div className="text-xs text-gray-600 mt-1">
                  Активных лотов:{' '}
                  <span className="font-semibold">{activeLots.length}</span>
                </div>
                <div className="text-xs text-green-600 font-semibold mt-1">
                  Всего: {totalRemaining.toFixed(2)}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Кнопка перехода к истории */}
      {onNavigateToHistory && (
        <div className="bg-gray-50 p-4 sm:p-6 rounded-lg">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold">История Транзакций</h3>
              <p className="text-sm text-gray-600">
                Просмотр и управление всеми транзакциями
              </p>
            </div>
            <button
              onClick={onNavigateToHistory}
              className="w-full sm:w-auto px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 font-medium text-sm"
            >
              Посмотреть Историю
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
