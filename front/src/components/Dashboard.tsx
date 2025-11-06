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
}
export function Dashboard() {
  const [cashStatus, setCashStatus] = useState<CashStatus>({})
  const [cashProfit, setCashProfit] = useState<CashProfit>({})
  const [loading, setLoading] = useState(false)
  const fetchData = async () => {
    setLoading(true)
    try {
      const [statusRes, profitRes] = await Promise.all([
        fetch(`${API_BASE}/cash/status`),
        fetch(`${API_BASE}/cash/cashflow_profit`),
      ])
      if (statusRes.ok) {
        const statusData = await statusRes.json()
        setCashStatus(statusData)
      }
      if (profitRes.ok) {
        const profitData = await profitRes.json()
        setCashProfit(profitData)
      }
    } catch (error) {
      toast.error('Не удалось загрузить данные')
    } finally {
      setLoading(false)
    }
  }
  const handleReset = async () => {
    if (!confirm('Вы уверены, что хотите сбросить кассу?')) return
    try {
      const res = await fetch(`${API_BASE}/cash/reset`, {
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
            <span>Сбросить Кассу</span>
          </button>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                      Количество
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
        <div className="w-full">
          <h3 className="text-lg sm:text-xl font-semibold mb-3">
            Прибыль по Валютам
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
                      Прибыль
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {cashProfit.cashflow_profit_by_currency &&
                  Object.entries(cashProfit.cashflow_profit_by_currency)
                    .length > 0 ? (
                    Object.entries(cashProfit.cashflow_profit_by_currency).map(
                      ([currency, profit]) => (
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
                        Нет данных о прибыли
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
