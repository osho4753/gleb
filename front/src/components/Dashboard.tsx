import React, { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { RefreshCwIcon, TrashIcon } from 'lucide-react'
import { config } from '../config'

const API_BASE = config.apiBaseUrl
export function Dashboard() {
  const [cashStatus, setCashStatus] = useState<any>({})
  const [cashProfit, setCashProfit] = useState<any>({})
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
      toast.error('Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }
  const handleReset = async () => {
    if (!confirm('Are you sure you want to reset the cash?')) return
    try {
      const res = await fetch(`${API_BASE}/cash/reset`, {
        method: 'DELETE',
      })
      if (res.ok) {
        toast.success('Cash reset successfully')
        fetchData()
      } else {
        toast.error('Failed to reset cash')
      }
    } catch (error) {
      toast.error('Error resetting cash')
    }
  }
  useEffect(() => {
    fetchData()
  }, [])
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Dashboard Overview</h2>
        <div className="flex gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            <RefreshCwIcon size={16} />
            Refresh
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            <TrashIcon size={16} />
            Reset Cash
          </button>
        </div>
      </div>
      <div>
        <h3 className="text-xl font-semibold mb-3">Current Cash Status</h3>
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                  Currency
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {cashStatus.cash && Object.entries(cashStatus.cash).length > 0 ? (
                Object.entries(cashStatus.cash).map(([currency, amount]) => (
                  <tr key={currency} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium">
                      {currency}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {Number(amount).toFixed(2)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={2}
                    className="px-4 py-8 text-center text-gray-500"
                  >
                    No cash data available
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <div>
        <h3 className="text-xl font-semibold mb-3">Profit by Currency</h3>
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                  Currency
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                  Profit
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {cashProfit.cashflow_profit_by_currency &&
              Object.entries(cashProfit.cashflow_profit_by_currency).length >
                0 ? (
                Object.entries(cashProfit.cashflow_profit_by_currency).map(
                  ([currency, profit]) => (
                    <tr key={currency} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium">
                        {currency}
                      </td>
                      <td
                        className={`px-4 py-3 text-sm text-right font-medium ${
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
                    className="px-4 py-8 text-center text-gray-500"
                  >
                    No profit data available
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
