import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { RefreshCwIcon, ChevronDownIcon } from 'lucide-react'
import { config } from '../config'

const API_BASE = config.apiBaseUrl

// Типы для PnL матчей
type PnLMatch = {
  _id: string
  currency: string
  open_lot_id: string
  close_tx_id?: string
  fiat_used: number
  matched_usdt: number
  lot_rate: number
  sell_rate_eff: number
  pnl_fiat: number
  pnl_usdt: number
  cost_usdt_of_fiat_in?: number
  stage?: number
  created_at: string
}

export function PnLMatches() {
  const [matches, setMatches] = useState<PnLMatch[]>([])
  const [loading, setLoading] = useState(false)
  const [expandedCurrency, setExpandedCurrency] = useState<string | null>(null)

  const fetchMatches = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/transactions/pnl-matches`)
      if (res.ok) {
        const data = await res.json()
        setMatches(data.matches || [])
      } else {
        toast.error('Не удалось загрузить PnL матчи')
      }
    } catch (error) {
      toast.error('Ошибка при загрузке PnL матчей')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMatches()
  }, [])

  // Группируем матчи по валюте
  const matchesByCurrency = matches.reduce((acc, match) => {
    if (!acc[match.currency]) {
      acc[match.currency] = []
    }
    acc[match.currency].push(match)
    return acc
  }, {} as Record<string, PnLMatch[]>)

  // Вычисляем итоги по валютам
  const currencySummary = Object.entries(matchesByCurrency).map(
    ([currency, currencyMatches]) => {
      const totalPnLFiat = currencyMatches.reduce(
        (sum, m) => sum + m.pnl_fiat,
        0
      )
      const totalPnLUsdt = currencyMatches.reduce(
        (sum, m) => sum + m.pnl_usdt,
        0
      )
      const totalFiatUsed = currencyMatches.reduce(
        (sum, m) => sum + m.fiat_used,
        0
      )
      const totalMatchedUsdt = currencyMatches.reduce(
        (sum, m) => sum + m.matched_usdt,
        0
      )

      // Считаем по этапам
      const stage1 = currencyMatches.filter((m) => !m.stage || m.stage === 1)
      const stage2 = currencyMatches.filter((m) => m.stage === 2)

      const stage1PnL = stage1.reduce((sum, m) => sum + m.pnl_usdt, 0)
      const stage2PnL = stage2.reduce((sum, m) => sum + m.pnl_usdt, 0)

      return {
        currency,
        matches: currencyMatches,
        totalPnLFiat,
        totalPnLUsdt,
        totalFiatUsed,
        totalMatchedUsdt,
        stage1,
        stage2,
        stage1PnL,
        stage2PnL,
      }
    }
  )

  const totalGlobalPnL = matches.reduce((sum, m) => sum + m.pnl_usdt, 0)

  if (matches.length === 0) {
    return (
      <div className="bg-white border rounded-lg p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">PnL Матчи (FIFO)</h2>
          <button
            onClick={fetchMatches}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            <RefreshCwIcon
              size={16}
              className={loading ? 'animate-spin' : ''}
            />
            Обновить
          </button>
        </div>
        <div className="text-center py-8 text-gray-500">
          PnL матчей пока нет. Создайте транзакции для отображения данных.
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 w-full">
      <div className="bg-white border rounded-lg p-6">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold">PnL Матчи (FIFO)</h2>
          <button
            onClick={fetchMatches}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            <RefreshCwIcon
              size={16}
              className={loading ? 'animate-spin' : ''}
            />
            Обновить
          </button>
        </div>

        {/* Общий итог */}
        <div className="bg-gradient-to-r from-green-50 to-blue-50 p-4 rounded-lg mb-6 border border-green-200">
          <div className="text-lg font-bold text-gray-800">
            Общая прибыль в USDT:
            <span
              className={`ml-2 ${
                totalGlobalPnL >= 0 ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {totalGlobalPnL.toFixed(4)} USDT
            </span>
          </div>
          <div className="text-sm text-gray-600 mt-1">
            Всего матчей: {matches.length}
          </div>
        </div>

        {/* По валютам */}
        <div className="space-y-3">
          {currencySummary.map((summary) => (
            <div
              key={summary.currency}
              className="border rounded-lg overflow-hidden"
            >
              <button
                onClick={() =>
                  setExpandedCurrency(
                    expandedCurrency === summary.currency
                      ? null
                      : summary.currency
                  )
                }
                className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="text-left">
                  <div className="font-semibold text-gray-800">
                    {summary.currency}
                  </div>
                  <div className="text-sm text-gray-600">
                    Матчей: {summary.matches.length} | Фиата:{' '}
                    {summary.totalFiatUsed.toFixed(2)} {summary.currency} | PnL:{' '}
                    <span
                      className={
                        summary.totalPnLUsdt >= 0
                          ? 'text-green-600'
                          : 'text-red-600'
                      }
                    >
                      {summary.totalPnLUsdt.toFixed(4)} USDT
                    </span>
                  </div>
                </div>
                <ChevronDownIcon
                  size={20}
                  className={`text-gray-600 transition-transform ${
                    expandedCurrency === summary.currency ? 'rotate-180' : ''
                  }`}
                />
              </button>

              {expandedCurrency === summary.currency && (
                <div className="p-4 bg-white border-t space-y-4">
                  {/* Этап 1 */}
                  {summary.stage1.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-semibold text-sm text-blue-700 bg-blue-50 px-3 py-2 rounded">
                        Этап 1: Живые лоты (из fiat_to_crypto)
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-gray-50 border-b">
                              <th className="px-3 py-2 text-left">Фиат</th>
                              <th className="px-3 py-2 text-right">
                                Использовано
                              </th>
                              <th className="px-3 py-2 text-right">USDT</th>
                              <th className="px-3 py-2 text-right">
                                Курс Лота
                              </th>
                              <th className="px-3 py-2 text-right">
                                Эфф. Курс
                              </th>
                              <th className="px-3 py-2 text-right">
                                PnL (USDT)
                              </th>
                              <th className="px-3 py-2 text-left">Дата</th>
                            </tr>
                          </thead>
                          <tbody>
                            {summary.stage1.map((match, idx) => (
                              <tr
                                key={idx}
                                className="border-b hover:bg-gray-50"
                              >
                                <td className="px-3 py-2">
                                  {summary.currency}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  {match.fiat_used.toFixed(2)}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  {match.matched_usdt.toFixed(4)}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  {match.lot_rate.toFixed(6)}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  {match.sell_rate_eff.toFixed(6)}
                                </td>
                                <td
                                  className={`px-3 py-2 text-right font-medium ${
                                    match.pnl_usdt >= 0
                                      ? 'text-green-600'
                                      : 'text-red-600'
                                  }`}
                                >
                                  {match.pnl_usdt.toFixed(4)}
                                </td>
                                <td className="px-3 py-2 text-xs text-gray-500">
                                  {new Date(match.created_at).toLocaleString(
                                    'ru-RU',
                                    {
                                      month: '2-digit',
                                      day: '2-digit',
                                      hour: '2-digit',
                                      minute: '2-digit',
                                    }
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="bg-blue-50 px-3 py-2 rounded text-xs">
                        <div className="font-semibold">
                          Итог Этапа 1:
                          <span
                            className={`ml-2 ${
                              summary.stage1PnL >= 0
                                ? 'text-green-600'
                                : 'text-red-600'
                            }`}
                          >
                            {summary.stage1PnL.toFixed(4)} USDT
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Этап 2 */}
                  {summary.stage2.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-semibold text-sm text-purple-700 bg-purple-50 px-3 py-2 rounded">
                        Этап 2: Обменные пункты (из fiat_to_fiat)
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-gray-50 border-b">
                              <th className="px-3 py-2 text-left">Фиат</th>
                              <th className="px-3 py-2 text-right">
                                Использовано
                              </th>
                              <th className="px-3 py-2 text-right">USDT</th>
                              <th className="px-3 py-2 text-right">Сб. USDT</th>
                              <th className="px-3 py-2 text-right">
                                Курс Лота
                              </th>
                              <th className="px-3 py-2 text-right">
                                Эфф. Курс
                              </th>
                              <th className="px-3 py-2 text-right">
                                PnL (USDT)
                              </th>
                              <th className="px-3 py-2 text-left">Дата</th>
                            </tr>
                          </thead>
                          <tbody>
                            {summary.stage2.map((match, idx) => (
                              <tr
                                key={idx}
                                className="border-b hover:bg-gray-50"
                              >
                                <td className="px-3 py-2">
                                  {summary.currency}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  {match.fiat_used.toFixed(2)}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  {match.matched_usdt.toFixed(4)}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  {match.cost_usdt_of_fiat_in?.toFixed(4) ||
                                    '-'}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  {match.lot_rate.toFixed(6)}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  {match.sell_rate_eff.toFixed(6)}
                                </td>
                                <td
                                  className={`px-3 py-2 text-right font-medium ${
                                    match.pnl_usdt >= 0
                                      ? 'text-green-600'
                                      : 'text-red-600'
                                  }`}
                                >
                                  {match.pnl_usdt.toFixed(4)}
                                </td>
                                <td className="px-3 py-2 text-xs text-gray-500">
                                  {new Date(match.created_at).toLocaleString(
                                    'ru-RU',
                                    {
                                      month: '2-digit',
                                      day: '2-digit',
                                      hour: '2-digit',
                                      minute: '2-digit',
                                    }
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="bg-purple-50 px-3 py-2 rounded text-xs">
                        <div className="font-semibold">
                          Итог Этапа 2:
                          <span
                            className={`ml-2 ${
                              summary.stage2PnL >= 0
                                ? 'text-green-600'
                                : 'text-red-600'
                            }`}
                          >
                            {summary.stage2PnL.toFixed(4)} USDT
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Только Этап 1 (без Этапа 2) */}
                  {summary.stage2.length === 0 && summary.stage1.length > 0 && (
                    <div className="bg-gray-50 px-3 py-2 rounded text-xs text-gray-600">
                      Этап 2 не использовался для этой валюты
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Легенда */}
        <div className="mt-6 pt-4 border-t">
          <h4 className="font-semibold text-sm mb-3">Легенда:</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <div className="flex items-start gap-2">
              <div className="w-3 h-3 bg-blue-200 border border-blue-400 rounded mt-1"></div>
              <div>
                <span className="font-medium">Этап 1 (Живые лоты):</span> фиат
                из fiat_to_crypto транзакций
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-3 h-3 bg-purple-200 border border-purple-400 rounded mt-1"></div>
              <div>
                <span className="font-medium">Этап 2 (Обменные пункты):</span>{' '}
                фиат из fiat_to_fiat транзакций (обмен через биржу)
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-3 h-3 bg-green-200 border border-green-400 rounded mt-1"></div>
              <div>
                <span className="font-medium">Сб. USDT:</span> себестоимость
                полученного фиата в USDT
              </div>
            </div>
            <div className="flex items-start gap-2">
              <div className="w-3 h-3 bg-orange-200 border border-orange-400 rounded mt-1"></div>
              <div>
                <span className="font-medium">PnL:</span> реализованная
                прибыль/убыток в USDT
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
