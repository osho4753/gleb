import React, { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { RefreshCwIcon, TrashIcon } from 'lucide-react'
import { config } from '../config'

const API_BASE = config.apiBaseUrl

// Типы для транзакций и состояния (можно вынести в отдельный файл types.ts)
type Transaction = {
  _id: string
  type: 'fiat_to_crypto' | 'crypto_to_fiat'
  from_asset: string
  to_asset: string
  amount_from: number
  rate_used: number
  fee_percent: number
  note: string
  created_at: string
  modified_at?: string
  is_modified?: boolean
  amount_to_final: number
  profit: number
}

// ====================================================================
// Вспомогательный компонент для формы редактирования (неадаптированный, но функциональный)
// ====================================================================

function EditTransactionForm({
  transaction,
  onSave,
  onCancel,
}: {
  transaction: Transaction
  onSave: (id: string, data: any) => void
  onCancel: () => void
}) {
  const [formData, setFormData] = useState({
    type: transaction.type || 'fiat_to_crypto',
    from_asset: transaction.from_asset || 'USD',
    to_asset: transaction.to_asset || 'BTC',
    amount_from: transaction.amount_from?.toString() || '',
    rate_used: transaction.rate_used?.toString() || '',
    fee_percent: transaction.fee_percent?.toString() || '1',
    note: transaction.note || '',
    created_at: transaction.created_at
      ? new Date(transaction.created_at).toISOString().slice(0, 16)
      : '',
  })

  const currencies = ['USD', 'USDT', 'EUR', 'CZK', 'BTC', 'ETH', 'CRON']

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const updateData: any = {}

    // Сравниваем с исходными данными и добавляем только измененные поля
    if (formData.type !== transaction.type) updateData.type = formData.type
    if (formData.from_asset !== transaction.from_asset)
      updateData.from_asset = formData.from_asset
    if (formData.to_asset !== transaction.to_asset)
      updateData.to_asset = formData.to_asset
    if (parseFloat(formData.amount_from) !== transaction.amount_from)
      updateData.amount_from = parseFloat(formData.amount_from)
    if (parseFloat(formData.rate_used) !== transaction.rate_used)
      updateData.rate_used = parseFloat(formData.rate_used)
    if (parseFloat(formData.fee_percent) !== transaction.fee_percent)
      updateData.fee_percent = parseFloat(formData.fee_percent)
    if (formData.note !== (transaction.note || ''))
      updateData.note = formData.note
    if (
      formData.created_at !==
      new Date(transaction.created_at).toISOString().slice(0, 16)
    ) {
      updateData.created_at = new Date(formData.created_at).toISOString()
    }

    onSave(transaction._id, updateData)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium mb-2">Тип Транзакции</label>
        <select
          value={formData.type}
          onChange={(e) =>
            setFormData({
              ...formData,
              type: e.target.value as 'fiat_to_crypto' | 'crypto_to_fiat',
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
          <label className="block text-sm font-medium mb-2">Из Актива</label>
          <select
            value={formData.from_asset}
            onChange={(e) =>
              setFormData({ ...formData, from_asset: e.target.value })
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
              setFormData({ ...formData, to_asset: e.target.value })
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
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-2">От</label>
          <input
            type="number"
            step="0.01"
            value={formData.amount_from}
            onChange={(e) =>
              setFormData({ ...formData, amount_from: e.target.value })
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
              setFormData({ ...formData, rate_used: e.target.value })
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
            setFormData({ ...formData, fee_percent: e.target.value })
          }
          placeholder="Введите % комиссии"
          className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Дата и Время</label>
        <input
          type="datetime-local"
          value={formData.created_at}
          onChange={(e) =>
            setFormData({ ...formData, created_at: e.target.value })
          }
          className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Пометка</label>
        <textarea
          value={formData.note}
          onChange={(e) => setFormData({ ...formData, note: e.target.value })}
          placeholder="Введите пометку к транзакции (необязательно)"
          rows={2}
          className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        />
      </div>

      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 text-sm"
        >
          Отмена
        </button>
        <button
          type="submit"
          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 text-sm"
        >
          Сохранить Изменения
        </button>
      </div>
    </form>
  )
}

// ====================================================================
// Основной адаптированный компонент TransactionsManager
// ====================================================================

export function TransactionsManager() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(false)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editingTransaction, setEditingTransaction] =
    useState<Transaction | null>(null)

  // Пагинация и сортировка
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage, setItemsPerPage] = useState(10)
  const [sortBy, setSortBy] = useState('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [dateFilter, setDateFilter] = useState({ from: '', to: '' })
  const [currencyFilter, setCurrencyFilter] = useState('')
  const [formData, setFormData] = useState({
    type: 'fiat_to_crypto',
    from_asset: 'USD',
    to_asset: 'BTC',
    amount_from: '',
    rate_used: '',
    fee_percent: '1',
    note: '',
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
      toast.error('Не удалось загрузить транзакции')
    }
  }

  //... (остальные функции API - handleSubmit, handleResetTransactions, updateTransaction и т.д. - остаются без изменений)
  // Я оставляю их закомментированными здесь, чтобы не дублировать код, но в финальном компоненте они должны быть.

  // --------------------------------------------------------------------------------------------------------------------
  // --- НАЧАЛО: Функции, которые должны быть в финальном коде (оставлены как заглушки для краткости) ---
  // --------------------------------------------------------------------------------------------------------------------

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
        fetchTransactions()
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

  const handleResetTransactions = async () => {
    if (!confirm('Вы уверены, что хотите удалить все транзакции?')) return
    try {
      const res = await fetch(`${API_BASE}/transactions/reset`, {
        method: 'DELETE',
      })
      if (res.ok) {
        toast.success('Все транзакции успешно удалены')
        fetchTransactions()
      } else {
        toast.error('Не удалось удалить транзакции')
      }
    } catch (error) {
      toast.error('Ошибка при удалении транзакций')
    }
  }

  const handleEditTransaction = (tx: Transaction) => {
    setEditingTransaction(tx)
    setIsEditModalOpen(true)
  }

  const handleDeleteTransaction = async (transactionId: string) => {
    if (!confirm('Вы уверены, что хотите удалить эту транзакцию?')) return

    try {
      const res = await fetch(`${API_BASE}/transactions/${transactionId}`, {
        method: 'DELETE',
      })

      if (res.ok) {
        toast.success('Транзакция удалена')
        fetchTransactions()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось удалить транзакцию')
      }
    } catch (error) {
      toast.error('Ошибка при удалении транзакции')
    }
  }

  const updateTransaction = async (transactionId: string, updateData: any) => {
    try {
      const res = await fetch(`${API_BASE}/transactions/${transactionId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      })

      if (res.ok) {
        toast.success('Транзакция обновлена')
        setIsEditModalOpen(false)
        setEditingTransaction(null)
        fetchTransactions()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось обновить транзакцию')
      }
    } catch (error) {
      toast.error('Ошибка при обновлении транзакции')
    }
  }
  // --------------------------------------------------------------------------------------------------------------------
  // --- КОНЕЦ: Функции, которые должны быть в финальном коде ---
  // --------------------------------------------------------------------------------------------------------------------

  // Функции сортировки и фильтрации (оставляем без изменений)
  const sortTransactions = (transactions: Transaction[]) => {
    return [...transactions].sort((a, b) => {
      let aValue, bValue

      switch (sortBy) {
        case 'created_at':
          aValue = new Date(a.created_at).getTime()
          bValue = new Date(b.created_at).getTime()
          break
        case 'amount_from':
          aValue = a.amount_from || 0
          bValue = b.amount_from || 0
          break
        case 'amount_to_final':
          aValue = a.amount_to_final || 0
          bValue = b.amount_to_final || 0
          break
        case 'profit':
          aValue = a.profit || 0
          bValue = b.profit || 0
          break
        case 'from_asset':
          aValue = a.from_asset || ''
          bValue = b.from_asset || ''
          break
        case 'to_asset':
          aValue = a.to_asset || ''
          bValue = b.to_asset || ''
          break
        default:
          return 0
      }

      if (sortOrder === 'asc') {
        return aValue > bValue ? 1 : -1
      } else {
        return aValue < bValue ? 1 : -1
      }
    })
  }

  const filterTransactions = (transactions: Transaction[]) => {
    return transactions.filter((tx) => {
      // Фильтр по дате
      if (dateFilter.from || dateFilter.to) {
        const txDate = new Date(tx.created_at)
        if (dateFilter.from && txDate < new Date(dateFilter.from)) return false
        if (dateFilter.to && txDate > new Date(dateFilter.to + 'T23:59:59'))
          return false
      }

      // Фильтр по валюте
      if (
        currencyFilter &&
        tx.from_asset !== currencyFilter &&
        tx.to_asset !== currencyFilter
      ) {
        return false
      }

      return true
    })
  }

  const getFilteredAndSortedTransactions = () => {
    const filtered = filterTransactions(transactions)
    return sortTransactions(filtered)
  }

  const getPaginatedTransactions = () => {
    const sortedAndFiltered = getFilteredAndSortedTransactions()
    const startIndex = (currentPage - 1) * itemsPerPage
    const endIndex = startIndex + itemsPerPage
    return sortedAndFiltered.slice(startIndex, endIndex)
  }

  const getTotalPages = () => {
    const filteredTransactions = getFilteredAndSortedTransactions()
    return Math.ceil(filteredTransactions.length / itemsPerPage)
  }

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
  }

  useEffect(() => {
    fetchTransactions()
  }, [])

  // Сброс страницы при изменении фильтров
  useEffect(() => {
    setCurrentPage(1)
  }, [dateFilter, currencyFilter, sortBy, sortOrder])

  // ====================================================================
  // Компонент Карточки Транзакции для мобильных
  // ====================================================================

  const TransactionCard = ({ tx }: { tx: Transaction }) => {
    const typeLabel =
      tx.type === 'fiat_to_crypto' ? 'Фиат в Крипто' : 'Крипто в Фиат'
    const typeColor =
      tx.type === 'fiat_to_crypto'
        ? 'bg-blue-100 text-blue-700'
        : 'bg-green-100 text-green-700'
    const profitColor = tx.profit >= 0 ? 'text-green-600' : 'text-red-600'
    const formattedDate = new Date(tx.created_at).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })

    return (
      <div className="border border-gray-200 p-4 rounded-lg shadow-sm bg-white space-y-2 text-sm">
        <div className="flex justify-between items-start">
          <span
            className={`px-2 py-0.5 text-xs font-semibold rounded ${typeColor}`}
          >
            {typeLabel}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => handleEditTransaction(tx)}
              className="p-1 text-blue-500 hover:text-blue-600 rounded-full"
              title="Редактировать"
            >
              {/* Иконка карандаша */}
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="lucide lucide-pencil-icon lucide-pencil"
              >
                <path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z" />
                <path d="m15 5 4 4" />
              </svg>
            </button>
            <button
              onClick={() => handleDeleteTransaction(tx._id)}
              className="p-1 text-red-500 hover:text-red-600 rounded-full"
              title="Удалить"
            >
              {/* Иконка корзины */}
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
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
        </div>

        <div className="font-semibold text-lg">
          {tx.amount_from.toFixed(2)} {tx.from_asset} →{' '}
          {tx.amount_to_final.toFixed(2)} {tx.to_asset}
        </div>

        <div className="text-gray-600">
          <span className="font-medium">Прибыль:</span>{' '}
          <span className={profitColor + ' font-bold'}>
            {tx.profit.toFixed(2)}
          </span>
        </div>

        <div className="text-xs text-gray-500 pt-1 border-t mt-1 flex justify-between">
          <div>{formattedDate}</div>
          <div>Комиссия: {tx.fee_percent}%</div>
        </div>
        {tx.note && (
          <div className="text-xs text-gray-500 truncate" title={tx.note}>
            Пометка: {tx.note}
          </div>
        )}
      </div>
    )
  }

  // ====================================================================
  // Рендер компонента
  // ====================================================================

  return (
    <div className="space-y-6 w-full max-w-full px-4 sm:px-6">
      {/* HEADER: Адаптация заголовка и кнопок */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <h2 className="text-xl sm:text-2xl font-bold">Транзакции</h2>
        <div className="flex gap-2 w-full sm:w-auto">
          <button
            onClick={fetchTransactions}
            className="flex items-center justify-center gap-2 px-3 sm:px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm flex-1 sm:flex-none"
          >
            <RefreshCwIcon size={16} />
            <span className="hidden sm:inline">Обновить</span>
            <span className="sm:hidden">Обновить</span>
          </button>
          <button
            onClick={handleResetTransactions}
            className="flex items-center justify-center gap-2 px-3 sm:px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 text-sm flex-1 sm:flex-none"
          >
            <TrashIcon size={16} />
            <span className="hidden sm:inline">Удалить Все</span>
            <span className="sm:hidden">Удалить</span>
          </button>
        </div>
      </div>

      {/* ФОРМА: Адаптация формы */}
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
          {/* Адаптивная сетка для полей формы: 1 колонка на моб., 2 на десктопе */}
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

      {/* ИСТОРИЯ: Адаптация фильтров и таблицы */}
      <div>
        <h3 className="text-lg font-semibold mb-3">История Транзакций</h3>

        {/* Панель фильтров и сортировки */}
        <div className="bg-gray-50 p-4 rounded-lg mb-4 space-y-4">
          {/* Адаптивная сетка для фильтров: 1 колонка на моб., 4 на десктопе */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Фильтр по дате */}
            <div>
              <label className="block text-sm font-medium mb-1">От даты:</label>
              <input
                type="date"
                value={dateFilter.from}
                onChange={(e) =>
                  setDateFilter({ ...dateFilter, from: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">До даты:</label>
              <input
                type="date"
                value={dateFilter.to}
                onChange={(e) =>
                  setDateFilter({ ...dateFilter, to: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>

            {/* Фильтр по валюте */}
            <div>
              <label className="block text-sm font-medium mb-1">Валюта:</label>
              <select
                value={currencyFilter}
                onChange={(e) => setCurrencyFilter(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm"
              >
                <option value="">Все валюты</option>
                {currencies.map((curr) => (
                  <option key={curr} value={curr}>
                    {curr}
                  </option>
                ))}
              </select>
            </div>

            {/* Количество на странице */}
            <div>
              <label className="block text-sm font-medium mb-1">
                На странице:
              </label>
              <select
                value={itemsPerPage}
                onChange={(e) => {
                  setItemsPerPage(parseInt(e.target.value))
                  setCurrentPage(1)
                }}
                className="w-full px-3 py-2 border rounded-lg text-sm"
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
              </select>
            </div>
          </div>

          {/* Кнопки очистки фильтров и счетчик */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
            <button
              onClick={() => {
                setDateFilter({ from: '', to: '' })
                setCurrencyFilter('')
                setCurrentPage(1)
              }}
              className="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 w-full sm:w-auto"
            >
              Очистить фильтры
            </button>
            <div className="text-sm text-gray-600">
              Показано: {getPaginatedTransactions().length} из{' '}
              {getFilteredAndSortedTransactions().length} транзакций
            </div>
          </div>
        </div>

        {/* ========================================================= */}
        {/* Мобильный вид: Карточки (по умолчанию, скрыты на md+) */}
        {/* ========================================================= */}
        <div className="md:hidden space-y-3">
          {getPaginatedTransactions().length > 0 ? (
            getPaginatedTransactions().map((tx) => (
              <TransactionCard key={tx._id} tx={tx} />
            ))
          ) : (
            <div className="text-center py-6 text-gray-500">
              Транзакций пока нет
            </div>
          )}
        </div>

        {/* ========================================================= */}
        {/* Десктопный вид: Таблица (скрыта на моб.) */}
        {/* ========================================================= */}
        <div className="border rounded-lg overflow-hidden hidden md:block">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px]">
              {' '}
              {/* Добавил min-w для лучшего отображения скролла */}
              <thead className="bg-gray-50">
                <tr>
                  <th
                    className="px-4 py-3 text-left text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('created_at')}
                  >
                    Дата и Время{' '}
                    {sortBy === 'created_at' &&
                      (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                    Тип
                  </th>
                  <th
                    className="px-4 py-3 text-left text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('from_asset')}
                  >
                    От{' '}
                    {sortBy === 'from_asset' &&
                      (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    className="px-4 py-3 text-left text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('to_asset')}
                  >
                    К{' '}
                    {sortBy === 'to_asset' && (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    className="px-4 py-3 text-right text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('amount_from')}
                  >
                    От (Сумма){' '}
                    {sortBy === 'amount_from' &&
                      (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    className="px-4 py-3 text-right text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('amount_to_final')}
                  >
                    К (Сумма){' '}
                    {sortBy === 'amount_to_final' &&
                      (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                    Комиссия %
                  </th>
                  <th
                    className="px-4 py-3 text-right text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('profit')}
                  >
                    Прибыль{' '}
                    {sortBy === 'profit' && (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                    Пометка
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-medium text-gray-700">
                    Действия
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {getPaginatedTransactions().length > 0 ? (
                  getPaginatedTransactions().map((tx) => (
                    <tr key={tx._id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm">
                        {new Date(tx.created_at).toLocaleString('ru-RU')}
                        {tx.is_modified && (
                          <div className="text-xs text-orange-600">
                            Изменено:{' '}
                            {new Date(tx.modified_at!).toLocaleString('ru-RU')}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span
                          className={`px-2 py-1 text-xs rounded ${
                            tx.type === 'fiat_to_crypto'
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-green-100 text-green-700'
                          }`}
                        >
                          {tx.type === 'fiat_to_crypto'
                            ? 'Фиат в Крипто'
                            : 'Крипто в Фиат'}
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
                      <td className="px-4 py-3 text-sm max-w-xs">
                        <div className="truncate" title={tx.note || ''}>
                          {tx.note || '-'}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex gap-1 justify-center">
                          <button
                            onClick={() => handleEditTransaction(tx)}
                            className="p-1 text-blue-500 hover:text-blue-600 rounded-full"
                            title="Редактировать"
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              className="lucide lucide-pencil-icon lucide-pencil"
                            >
                              <path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z" />
                              <path d="m15 5 4 4" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleDeleteTransaction(tx._id)}
                            className="p-1 text-red-500 hover:text-red-600 rounded-full"
                            title="Удалить"
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
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
                      colSpan={10}
                      className="px-4 py-8 text-center text-gray-500"
                    >
                      Транзакций пока нет
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Пагинация (адаптирована) */}
        {getTotalPages() > 1 && (
          <div className="flex flex-wrap justify-between items-center mt-4 px-0 sm:px-4 gap-3">
            <div className="text-sm text-gray-600 w-full text-center sm:w-auto sm:text-left">
              Страница {currentPage} из {getTotalPages()}
            </div>
            <div className="flex flex-wrap justify-center gap-2 w-full sm:w-auto">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1}
                className="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                ← Назад
              </button>

              {/* Номера страниц */}
              {Array.from({ length: getTotalPages() }, (_, i) => i + 1)
                .filter((pageNum) => {
                  const maxPagesToShow = 5
                  if (getTotalPages() <= maxPagesToShow) return true
                  if (pageNum === 1 || pageNum === getTotalPages()) return true
                  if (
                    pageNum >=
                      currentPage - Math.floor((maxPagesToShow - 2) / 2) &&
                    pageNum <= currentPage + Math.ceil((maxPagesToShow - 2) / 2)
                  )
                    return true
                  return false
                })
                .map((pageNum) => (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={`px-3 py-1 text-sm rounded ${
                      currentPage === pageNum
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                  >
                    {pageNum}
                  </button>
                ))}

              <button
                onClick={() =>
                  setCurrentPage(Math.min(getTotalPages(), currentPage + 1))
                }
                disabled={currentPage === getTotalPages()}
                className="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Вперед →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Модальное окно редактирования (Адаптировано) */}
      {isEditModalOpen && editingTransaction && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          {' '}
          {/* Добавил p-4 для отступа на моб. */}
          <div className="bg-white p-6 rounded-lg max-w-lg w-full max-h-[95vh] overflow-y-auto">
            {' '}
            {/* max-w-lg и max-h-[95vh] для моб. */}
            <h3 className="text-lg font-semibold mb-4">
              Редактировать Транзакцию
            </h3>
            <EditTransactionForm
              transaction={editingTransaction}
              onSave={updateTransaction}
              onCancel={() => {
                setIsEditModalOpen(false)
                setEditingTransaction(null)
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
