import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { RefreshCwIcon } from 'lucide-react'
import { config } from '../config'

const API_BASE = config.apiBaseUrl

interface FiatLot {
  _id: string
  currency: string
  remaining: number
  rate: number
  tx_id: string | null
  created_at: string
  meta: {
    source: string
    fee_percent: number
  }
}

interface ProfitSummary {
  currency: string
  realized_profit: {
    fiat: number
    usdt: number
  }
  remaining_lots: {
    count: number
    total_value: number
  }
  transactions: {
    buy_count: number
    sell_count: number
  }
}

export function FiatLotsManager() {
  const [lots, setLots] = useState<FiatLot[]>([])
  const [selectedCurrency, setSelectedCurrency] = useState<string>('CZK')
  const [profitSummary, setProfitSummary] = useState<ProfitSummary | null>(null)
  const [loading, setLoading] = useState(false)

  const currencies = ['CZK', 'USD', 'EUR']

  useEffect(() => {
    fetchLotsByCurrency(selectedCurrency)
    fetchProfitSummary(selectedCurrency)
  }, [selectedCurrency])

  const fetchLotsByCurrency = async (currency: string) => {
    try {
      setLoading(true)
      const response = await fetch(
        `${API_BASE}/transactions/fiat-lots/${currency}`
      )
      if (!response.ok) throw new Error('Failed to fetch fiat lots')

      const data = await response.json()
      setLots(data.lots || [])
    } catch (error) {
      console.error('Error fetching fiat lots:', error)
      toast.error('Ошибка загрузки фиатных лотов')
    } finally {
      setLoading(false)
    }
  }

  const fetchProfitSummary = async (currency: string) => {
    try {
      const response = await fetch(
        `${API_BASE}/transactions/profit-summary/${currency}`
      )
      if (!response.ok) throw new Error('Failed to fetch profit summary')

      const data = await response.json()
      setProfitSummary(data)
    } catch (error) {
      console.error('Error fetching profit summary:', error)
      toast.error('Ошибка загрузки сводки прибыли')
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('ru-RU')
  }

  const formatNumber = (num: number, decimals = 2) => {
    return num.toLocaleString('ru-RU', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h2 className="text-xl font-semibold text-gray-900">
          Фиатные лоты и прибыль
        </h2>

        <div className="flex gap-2">
          <button
            onClick={() => {
              fetchLotsByCurrency(selectedCurrency)
              fetchProfitSummary(selectedCurrency)
            }}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 text-sm"
          >
            <RefreshCwIcon
              size={16}
              className={loading ? 'animate-spin' : ''}
            />
            Обновить
          </button>

          {currencies.map((currency) => (
            <button
              key={currency}
              onClick={() => setSelectedCurrency(currency)}
              className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                selectedCurrency === currency
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {currency}
            </button>
          ))}
        </div>
      </div>

      {/* Сводка прибыли */}
      {profitSummary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-green-50 p-4 rounded-lg border border-green-200">
            <h3 className="text-sm font-medium text-green-800 mb-1">
              Реализованная прибыль
            </h3>
            <div className="text-lg font-semibold text-green-900">
              {formatNumber(profitSummary.realized_profit.fiat)}{' '}
              {selectedCurrency}
            </div>
            <div className="text-xs text-green-700">
              ≈ {formatNumber(profitSummary.realized_profit.usdt, 4)} USDT
            </div>
          </div>

          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
            <h3 className="text-sm font-medium text-blue-800 mb-1">
              Остатки лотов
            </h3>
            <div className="text-lg font-semibold text-blue-900">
              {formatNumber(profitSummary.remaining_lots.total_value)}{' '}
              {selectedCurrency}
            </div>
            <div className="text-xs text-blue-700">
              {profitSummary.remaining_lots.count} лотов
            </div>
          </div>

          <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
            <h3 className="text-sm font-medium text-purple-800 mb-1">
              Транзакции
            </h3>
            <div className="text-lg font-semibold text-purple-900">
              {profitSummary.transactions.buy_count +
                profitSummary.transactions.sell_count}
            </div>
            <div className="text-xs text-purple-700">
              {profitSummary.transactions.buy_count} покупок,{' '}
              {profitSummary.transactions.sell_count} продаж
            </div>
          </div>
        </div>
      )}

      {/* Таблица лотов */}
      <div className="bg-white rounded-lg border">
        <div className="px-4 py-3 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-lg font-medium text-gray-900">
            Активные лоты {selectedCurrency}
          </h3>
          {loading && <div className="text-sm text-gray-500">Загрузка...</div>}
        </div>

        {lots.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            Нет активных лотов для {selectedCurrency}
          </div>
        ) : (
          <div className="overflow-x-auto">
            {/* Мобильная версия - карточки */}
            <div className="block sm:hidden">
              {lots.map((lot) => (
                <div
                  key={lot._id}
                  className="p-4 border-b border-gray-100 last:border-b-0"
                >
                  <div className="space-y-2">
                    <div className="flex justify-between items-start">
                      <span className="font-medium text-gray-900">
                        {formatNumber(lot.remaining)} {lot.currency}
                      </span>
                      <span className="text-sm text-gray-500">
                        {formatDate(lot.created_at)}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Курс:</span>
                      <span className="font-medium">
                        {formatNumber(lot.rate, 5)} {lot.currency}/USDT
                      </span>
                    </div>
                    {lot.meta.fee_percent > 0 && (
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600">Комиссия:</span>
                        <span>{lot.meta.fee_percent}%</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Десктопная версия - таблица */}
            <table className="hidden sm:table min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Остаток
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Курс ({selectedCurrency}/USDT)
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Комиссия
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Создан
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {lots.map((lot) => (
                  <tr key={lot._id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {formatNumber(lot.remaining)} {lot.currency}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatNumber(lot.rate, 5)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {lot.meta.fee_percent}%
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(lot.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
