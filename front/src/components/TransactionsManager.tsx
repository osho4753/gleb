import React, { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { RefreshCwIcon, TrashIcon } from 'lucide-react'
import { config } from '../config'

const API_BASE = config.apiBaseUrl
export function TransactionsManager() {
  const [transactions, setTransactions] = useState<any>([])
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    type: 'fiat_to_crypto',
    from_asset: 'USD',
    to_asset: 'BTC',
    amount_from: '',
    rate_used: '',
    fee_percent: '1',
  })
  const currencies = ['USD', 'USDT', 'EUR', 'CZK', 'BTC', 'ETH', 'CRON']
  const fetchTransactions = async () => {
    try {
      const res = await fetch(`${API_BASE}/transactions`)
      if (res.ok) {
        const data = await res.json()
        setTransactions(data)
      }
    } catch (error) {
      console.error('Failed to fetch transactions')
    }
  }
  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.amount_from || !formData.rate_used) {
      toast.error('Please fill in all required fields')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/transactions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...formData,
          amount_from: parseFloat(formData.amount_from),
          rate_used: parseFloat(formData.rate_used),
          fee_percent: parseFloat(formData.fee_percent),
        }),
      })
      if (res.ok) {
        toast.success('Transaction created successfully')
        setFormData({
          ...formData,
          amount_from: '',
          rate_used: '',
        })
        fetchTransactions()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Failed to create transaction')
      }
    } catch (error) {
      toast.error('Error creating transaction')
    } finally {
      setLoading(false)
    }
  }

  const handleResetTransactions = async () => {
    if (!confirm('Are you sure you want to delete all transactions?')) return
    try {
      const res = await fetch(`${API_BASE}/transactions/reset`, {
        method: 'DELETE',
      })
      if (res.ok) {
        toast.success('All transactions deleted successfully')
        fetchTransactions()
      } else {
        toast.error('Failed to delete transactions')
      }
    } catch (error) {
      toast.error('Error deleting transactions')
    }
  }

  useEffect(() => {
    fetchTransactions()
  }, [])
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Transactions</h2>
        <div className="flex gap-2">
          <button
            onClick={fetchTransactions}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            <RefreshCwIcon size={16} />
            Refresh
          </button>
          <button
            onClick={handleResetTransactions}
            className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            <TrashIcon size={16} />
            Delete All
          </button>
        </div>
      </div>
      <div className="bg-gray-50 p-6 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">Create Transaction</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Transaction Type
            </label>
            <select
              value={formData.type}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  type: e.target.value,
                })
              }
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="fiat_to_crypto">Fiat to Crypto</option>
              <option value="crypto_to_fiat">Crypto to Fiat</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                From Asset
              </label>
              <select
                value={formData.from_asset}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    from_asset: e.target.value,
                  })
                }
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
              <label className="block text-sm font-medium mb-2">To Asset</label>
              <select
                value={formData.to_asset}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    to_asset: e.target.value,
                  })
                }
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {currencies.map((curr) => (
                  <option key={curr} value={curr}>
                    {curr}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Amount From
              </label>
              <input
                type="number"
                step="0.01"
                value={formData.amount_from}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    amount_from: e.target.value,
                  })
                }
                placeholder="Enter amount"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                Rate Used
              </label>
              <input
                type="number"
                step="0.00000001"
                value={formData.rate_used}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    rate_used: e.target.value,
                  })
                }
                placeholder="Enter rate"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">
              Fee Percent
            </label>
            <input
              type="number"
              step="0.1"
              value={formData.fee_percent}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  fee_percent: e.target.value,
                })
              }
              placeholder="Enter fee %"
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? 'Creating...' : 'Create Transaction'}
          </button>
        </form>
      </div>
      <div>
        <h3 className="text-lg font-semibold mb-3">Transaction History</h3>
        <div className="border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                    Date & Time
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                    From
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                    To
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                    Amount From
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                    Amount To
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                    Fee %
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                    Profit
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {transactions.length > 0 ? (
                  transactions.map((tx: any, index: any) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm">
                        {new Date(tx.created_at).toLocaleString('ru-RU')}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span className="px-2 py-1 text-xs rounded bg-blue-100 text-blue-700">
                          {tx.type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-medium">
                        {tx.from_asset}
                      </td>
                      <td className="px-4 py-3 text-sm font-medium">
                        {tx.to_asset}
                      </td>
                      <td className="px-4 py-3 text-sm text-right">
                        {tx.amount_from?.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-sm text-right">
                        {tx.amount_to_final?.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-sm text-right">
                        {tx.fee_percent}%
                      </td>
                      <td
                        className={`px-4 py-3 text-sm text-right font-medium ${
                          tx.profit >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}
                      >
                        {tx.profit?.toFixed(2)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-8 text-center text-gray-500"
                    >
                      No transactions yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
