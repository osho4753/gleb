import React, { useEffect, useState } from 'react'
import { toast } from 'sonner'
const API_BASE = 'http://127.0.0.1:8000'
export function CashManager() {
  const [currency, setCurrency] = useState('USD')
  const [amount, setAmount] = useState('')
  const [cashStatus, setCashStatus] = useState<any>({})
  const [loading, setLoading] = useState(false)
  const currencies = ['USD', 'USDT', 'EUR', 'CZK', 'BTC', 'ETH', 'CRON']
  const fetchCashStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/cash/status`)
      if (res.ok) {
        const data = await res.json()
        setCashStatus(data)
      }
    } catch (error) {
      console.error('Failed to fetch cash status')
    }
  }
  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!amount || isNaN(amount)) {
      toast.error('Please enter a valid amount')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/cash/set`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          asset: currency,
          amount: parseFloat(amount),
        }),
      })
      if (res.ok) {
        toast.success('Cash balance updated successfully')
        setAmount('')
        fetchCashStatus()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Failed to update cash balance')
      }
    } catch (error) {
      toast.error('Error updating cash balance')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    fetchCashStatus()
  }, [])
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Cash Management</h2>
      <div className="bg-gray-50 p-6 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">Set Cash Balance</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Currency</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {currencies.map((curr) => (
                <option key={curr} value={curr}>
                  {curr}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Amount</label>
            <input
              type="number"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Enter amount"
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? 'Saving...' : 'Save Balance'}
          </button>
        </form>
      </div>
      <div>
        <h3 className="text-lg font-semibold mb-3">Current Balances</h3>
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
                Object.entries(cashStatus.cash).map(([curr, amt]) => (
                  <tr key={curr} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium">{curr}</td>
                    <td className="px-4 py-3 text-sm text-right">
                      {Number(amt).toFixed(2)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={2}
                    className="px-4 py-8 text-center text-gray-500"
                  >
                    No balances set
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
