import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { config } from '../config'

const API_BASE = config.apiBaseUrl
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
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!amount || isNaN(parseFloat(amount))) {
      toast.error('Введите корректную сумму')
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
        toast.success('Баланс кассы успешно обновлен')
        setAmount('')
        fetchCashStatus()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось обновить баланс кассы')
      }
    } catch (error) {
      toast.error('Ошибка при обновлении баланса кассы')
    } finally {
      setLoading(false)
    }
  }

  const handleEditBalance = (asset: string, currentAmount: number) => {
    const newAmount = prompt(
      `Введите новую сумму для ${asset}:`,
      currentAmount.toString()
    )
    if (newAmount === null) return

    const amount = parseFloat(newAmount)
    if (isNaN(amount)) {
      toast.error('Введите корректную сумму')
      return
    }

    updateBalance(asset, amount)
  }

  const updateBalance = async (asset: string, amount: number) => {
    try {
      const res = await fetch(`${API_BASE}/cash/${asset}?amount=${amount}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (res.ok) {
        toast.success(`Баланс ${asset} обновлен`)
        fetchCashStatus()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось обновить баланс')
      }
    } catch (error) {
      toast.error('Ошибка при обновлении баланса')
    }
  }

  const handleDeleteAsset = async (asset: string) => {
    if (!confirm(`Вы уверены, что хотите удалить ${asset} из кассы?`)) return

    try {
      const res = await fetch(`${API_BASE}/cash/${asset}`, {
        method: 'DELETE',
      })

      if (res.ok) {
        toast.success(`${asset} удален из кассы`)
        fetchCashStatus()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось удалить валюту')
      }
    } catch (error) {
      toast.error('Ошибка при удалении валюты')
    }
  }

  useEffect(() => {
    fetchCashStatus()
  }, [])
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Управление Кассой</h2>
      <div className="bg-gray-50 p-6 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">Установить Баланс Кассы</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Валюта</label>
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
            <label className="block text-sm font-medium mb-2">Сумма</label>
            <input
              type="number"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Введите сумму"
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? 'Сохранение...' : 'Сохранить Баланс'}
          </button>
        </form>
      </div>
      <div>
        <h3 className="text-lg font-semibold mb-3">Текущие Балансы</h3>
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                  Валюта
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                  Сумма
                </th>
                <th className="px-4 py-3 text-center text-sm font-medium text-gray-700">
                  Действия
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
                    <td className="px-4 py-3 text-center">
                      <div className="flex gap-2 justify-center">
                        <button
                          onClick={() => handleEditBalance(curr, Number(amt))}
                          className="px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="24"
                            height="24"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            className="lucide lucide-pencil-icon lucide-pencil"
                          >
                            <path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z" />
                            <path d="m15 5 4 4" />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleDeleteAsset(curr)}
                          className="px-3 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="24"
                            height="24"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            className="lucide lucide-trash2-icon lucide-trash-2"
                          >
                            <path d="M10 11v6" />
                            <path d="M14 11v6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                            <path d="M3 6h18" />
                            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-8 text-center text-gray-500"
                  >
                    Балансы не установлены
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
