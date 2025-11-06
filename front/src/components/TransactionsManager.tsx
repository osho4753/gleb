import React, { useState } from 'react'
import { toast } from 'sonner'
import { config } from '../config'

const API_BASE = config.apiBaseUrl

interface TransactionsManagerProps {
  onNavigateToHistory?: () => void
}

export function TransactionsManager({
  onNavigateToHistory,
}: TransactionsManagerProps) {
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    type: 'fiat_to_crypto',
    from_asset: 'USD',
    to_asset: 'BTC',
    amount_from: '',
    rate_used: '',
    fee_percent: '1',
    note: '',
  })
  const currencies = ['USD', 'USDT', 'EUR', 'CZK']

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.amount_from || !formData.rate_used) {
      toast.error('Заполните все обязательные поля')
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
        toast.success('Транзакция успешно создана')
        setFormData({
          ...formData,
          amount_from: '',
          rate_used: '',
        })
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось создать транзакцию')
      }
    } catch (error) {
      toast.error('Ошибка при создании транзакции')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 w-full max-w-full px-4 sm:px-6">
      {/* HEADER: Заголовок */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <h2 className="text-xl sm:text-2xl font-bold">Транзакции</h2>
      </div>

      {/* ФОРМА: Создание транзакции */}
      <div className="bg-gray-50 p-4 sm:p-6 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">Создать Транзакцию</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Тип Транзакции
            </label>
            <select
              value={formData.type}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  type: e.target.value,
                })
              }
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              <option value="fiat_to_crypto">Фиат в Крипто</option>
              <option value="crypto_to_fiat">Крипто в Фиат</option>
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Из Актива
              </label>
              <select
                value={formData.from_asset}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    from_asset: e.target.value,
                  })
                }
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              >
                {currencies.map((curr) => (
                  <option key={curr} value={curr}>
                    {curr}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">В Актив</label>
              <select
                value={formData.to_asset}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    to_asset: e.target.value,
                  })
                }
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              >
                {currencies.map((curr) => (
                  <option key={curr} value={curr}>
                    {curr}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                От (Сумма)
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
                placeholder="Введите сумму"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                Использованный Курс
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
                placeholder="Введите курс"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">
              Процент Комиссии
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
              placeholder="Введите % комиссии"
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Пометка</label>
            <textarea
              value={formData.note}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  note: e.target.value,
                })
              }
              placeholder="Введите пометку к транзакции (необязательно)"
              rows={3}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 font-medium"
          >
            {loading ? 'Создание...' : 'Создать Транзакцию'}
          </button>
        </form>
      </div>

      {/* Кнопка перехода к истории транзакций */}
      {onNavigateToHistory && (
        <div className="bg-gray-50 p-4 sm:p-6 rounded-lg">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold">История Транзакций</h3>
              <p className="text-sm text-gray-600">
                Просмотр, редактирование и управление всеми транзакциями
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
