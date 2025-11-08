import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { RefreshCwIcon, TrashIcon } from 'lucide-react'
import { config } from '../config'

const API_BASE = config.apiBaseUrl
type CashStatus = {
  cash?: Record<string, number>
}
type CashProfit = {
  cashflow_profit_by_currency?: Record<string, number>
  profits_by_currency?: Record<string, number>
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

export function Dashboard() {
  const [cashStatus, setCashStatus] = useState<CashStatus>({})
  const [cashProfit, setCashProfit] = useState<CashProfit>({})
  const [realizedProfit, setRealizedProfit] = useState<CashProfit>({})
  const [profitSummaries, setProfitSummaries] = useState<
    Record<string, ProfitSummary>
  >({})
  const [loading, setLoading] = useState(false)
  const fetchData = async () => {
    setLoading(true)
    try {
      const [statusRes, cashflowRes, realizedRes] = await Promise.all([
        fetch(`${API_BASE}/cash/status`),
        fetch(`${API_BASE}/cash/cashflow_profit`),
        fetch(`${API_BASE}/cash/profit`),
      ])

      if (statusRes.ok) {
        const statusData = await statusRes.json()
        setCashStatus(statusData)
      }

      if (cashflowRes.ok) {
        const cashflowData = await cashflowRes.json()
        setCashProfit(cashflowData)
      }

      if (realizedRes.ok) {
        const realizedData = await realizedRes.json()
        setRealizedProfit(realizedData)
      }

      // Получаем данные по фиатным лотам для всех валют
      const currencies = ['CZK', 'USD', 'EUR']
      const summariesData: Record<string, ProfitSummary> = {}

      for (const currency of currencies) {
        try {
          const summaryRes = await fetch(
            `${API_BASE}/transactions/profit-summary/${currency}`
          )
          if (summaryRes.ok) {
            summariesData[currency] = await summaryRes.json()
          }
        } catch (error) {
          console.error(`Failed to fetch summary for ${currency}:`, error)
        }
      }
      setProfitSummaries(summariesData)
    } catch (error) {
      toast.error('Не удалось загрузить данные')
    } finally {
      setLoading(false)
    }
  }
  const handleReset = async () => {
    if (!confirm('Вы уверены, что хотите сбросить кассу?')) return
    try {
      const res = await fetch(`${API_BASE}/reset-all`, {
        method: 'DELETE',
      })
      if (res.ok) {
        toast.success('Касса успешно сброшена')
        fetchData()
      } else {
        toast.error('Не удалось сбросить кассу')
      }
    } catch (error) {
      toast.error('Ошибка при сбросе кассы')
    }
  }

  const handleResetAllData = async () => {
    if (
      !confirm(
        'Вы уверены, что хотите сбросить ВСЕ данные (касса, транзакции, лоты, PnL матчи)?'
      )
    )
      return
    try {
      const res = await fetch(`${API_BASE}/reset-all-data`, {
        method: 'DELETE',
      })
      if (res.ok) {
        toast.success('Все данные успешно сброшены')
        fetchData()
      } else {
        toast.error('Не удалось сбросить данные')
      }
    } catch (error) {
      toast.error('Ошибка при сбросе данных')
    }
  }
  useEffect(() => {
    fetchData()
  }, [])
  return (
    <div className="space-y-6 w-full max-w-full px-4 sm:px-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h2 className="text-xl sm:text-2xl font-bold">Обзор Системы</h2>
        <div className="flex flex-wrap gap-2 w-full sm:w-auto">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center justify-center gap-1.5 px-3 sm:px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 text-sm sm:text-base flex-1 sm:flex-none min-h-[40px]"
          >
            <RefreshCwIcon
              size={16}
              className={loading ? 'animate-spin' : ''}
            />
            <span>Обновить</span>
          </button>
          <button
            onClick={handleReset}
            className="flex items-center justify-center gap-1.5 px-3 sm:px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 text-sm sm:text-base flex-1 sm:flex-none min-h-[40px]"
          >
            <TrashIcon size={16} />
            <span className="hidden sm:inline">Сбросить Кассу</span>
            <span className="sm:hidden">Касса</span>
          </button>
          <button
            onClick={handleResetAllData}
            className="flex items-center justify-center gap-1.5 px-3 sm:px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm sm:text-base flex-1 sm:flex-none min-h-[40px]"
          >
            <TrashIcon size={16} />
            <span className="hidden sm:inline">Сбросить Всё</span>
            <span className="sm:hidden">Всё</span>
          </button>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="w-full">
          <h3 className="text-lg sm:text-xl font-semibold mb-3">
            Текущее Состояние Кассы
          </h3>
          <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 sm:px-4 py-3 text-left text-xs sm:text-sm font-medium text-gray-700">
                      Валюта
                    </th>
                    <th className="px-3 sm:px-4 py-3 text-right text-xs sm:text-sm font-medium text-gray-700">
                      Кол-во
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {cashStatus.cash &&
                  Object.entries(cashStatus.cash).length > 0 ? (
                    Object.entries(cashStatus.cash).map(
                      ([currency, amount]) => (
                        <tr key={currency} className="hover:bg-gray-50">
                          <td className="px-3 sm:px-4 py-2.5 sm:py-3 text-xs sm:text-sm font-medium">
                            {currency}
                          </td>
                          <td className="px-3 sm:px-4 py-2.5 sm:py-3 text-xs sm:text-sm text-right">
                            {Number(amount).toFixed(2)}
                          </td>
                        </tr>
                      )
                    )
                  ) : (
                    <tr>
                      <td
                        colSpan={2}
                        className="px-3 sm:px-4 py-6 sm:py-8 text-center text-xs sm:text-sm text-gray-500"
                      >
                        Нет данных о кассе
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Реализованная Прибыль */}
        <div className="w-full">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-3">
            <h3 className="text-lg sm:text-xl font-semibold">
              Реализованная Прибыль
            </h3>
          </div>

          <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 sm:px-4 py-3 text-left text-xs sm:text-sm font-medium text-gray-700">
                      Валюта
                    </th>
                    <th className="px-3 sm:px-4 py-3 text-right text-xs sm:text-sm font-medium text-gray-700">
                      Прибыль
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {realizedProfit.profits_by_currency &&
                  Object.entries(realizedProfit.profits_by_currency).length >
                    0 ? (
                    Object.entries(realizedProfit.profits_by_currency).map(
                      ([currency, profit]) =>
                        currency !== '' && (
                          <tr key={currency} className="hover:bg-gray-50">
                            <td className="px-3 sm:px-4 py-2.5 sm:py-3 text-xs sm:text-sm font-medium">
                              {currency}
                            </td>
                            <td
                              className={`px-3 sm:px-4 py-2.5 sm:py-3 text-xs sm:text-sm text-right font-medium ${
                                Number(profit) >= 0
                                  ? 'text-green-600'
                                  : 'text-red-600'
                              }`}
                            >
                              {Number(profit).toFixed(2)}
                            </td>
                          </tr>
                        )
                    )
                  ) : (
                    <tr>
                      <td
                        colSpan={2}
                        className="px-3 sm:px-4 py-6 sm:py-8 text-center text-xs sm:text-sm text-gray-500"
                      >
                        Нет данных о реализованной прибыли
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Новая секция - Сводка по фиатным лотам */}
      {Object.keys(profitSummaries).length > 0 && (
        <div className="mt-8">
          <h3 className="text-lg sm:text-xl font-semibold mb-4">
            Сводка по фиатным лотам
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {Object.entries(profitSummaries).map(([currency, summary]) => (
              <div
                key={currency}
                className="border rounded-lg bg-white shadow-sm p-4"
              >
                <h4 className="font-semibold text-lg mb-3 text-center">
                  {currency}
                </h4>

                <div className="space-y-3">
                  <div className="bg-green-50 p-3 rounded border border-green-200">
                    <div className="text-sm text-green-800 font-medium">
                      Реализованная прибыль
                    </div>
                    <div className="text-lg font-semibold text-green-900">
                      {summary.realized_profit.fiat.toFixed(2)} {currency}
                    </div>
                    <div className="text-xs text-green-700">
                      ≈ {summary.realized_profit.usdt.toFixed(4)} USDT
                    </div>
                  </div>

                  <div className="bg-blue-50 p-3 rounded border border-blue-200">
                    <div className="text-sm text-blue-800 font-medium">
                      Остатки лотов
                    </div>
                    <div className="text-lg font-semibold text-blue-900">
                      {summary.remaining_lots.total_value.toFixed(2)} {currency}
                    </div>
                    <div className="text-xs text-blue-700">
                      {summary.remaining_lots.count} активных лотов
                    </div>
                  </div>

                  <div className="bg-purple-50 p-3 rounded border border-purple-200">
                    <div className="text-sm text-purple-800 font-medium">
                      Транзакции
                    </div>
                    <div className="text-lg font-semibold text-purple-900">
                      {summary.transactions.buy_count +
                        summary.transactions.sell_count}
                    </div>
                    <div className="text-xs text-purple-700">
                      {summary.transactions.buy_count} покупок,{' '}
                      {summary.transactions.sell_count} продаж
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
