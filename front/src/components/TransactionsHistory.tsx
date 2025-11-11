import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  RefreshCwIcon,
  EditIcon,
  TrashIcon,
  ChevronDownIcon,
  DownloadIcon,
} from 'lucide-react'
import { config } from '../config'
import { evaluate } from 'mathjs'

const API_BASE = config.apiBaseUrl

// Типы для транзакций
type Transaction = {
  _id: string
  type:
    | 'fiat_to_crypto'
    | 'crypto_to_fiat'
    | 'fiat_to_fiat'
    | 'deposit'
    | 'withdrawal'
  from_asset: string
  to_asset: string
  amount_from: number
  rate_used: number
  rate_for_gleb_pnl?: number
  fee_percent: number
  note: string
  created_at: string
  modified_at?: string
  is_modified?: boolean
  amount_to_final: number
  amount_to_clean?: number
  profit: number
  profit_currency: string
  cost_usdt_of_fiat_in?: number
  rate_usdt_of_fiat_in?: number
}

// Компонент для редактирования транзакции
function EditTransactionModal({
  transaction,
  isOpen,
  onClose,
  onSave,
}: {
  transaction: Transaction | null
  isOpen: boolean
  onClose: () => void
  onSave: (id: string, data: any) => void
}) {
  const [formData, setFormData] = useState({
    type: 'fiat_to_crypto' as
      | 'fiat_to_crypto'
      | 'crypto_to_fiat'
      | 'fiat_to_fiat'
      | 'deposit'
      | 'withdrawal',
    from_asset: 'USD',
    to_asset: 'BTC',
    amount_from: '',
    rate_used: '',
    fee_percent: '1',
    note: '',
    created_at: '',
  })

  const currencies = ['USD', 'USDT', 'EUR', 'CZK']

  useEffect(() => {
    if (transaction) {
      setFormData({
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
    }
  }, [transaction])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!transaction) return

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

  if (!isOpen || !transaction) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white p-6 rounded-lg max-w-lg w-full max-h-[95vh] overflow-y-auto">
        <h3 className="text-lg font-semibold mb-4">Редактировать Транзакцию</h3>

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
                  type: e.target.value as
                    | 'fiat_to_crypto'
                    | 'crypto_to_fiat'
                    | 'fiat_to_fiat'
                    | 'deposit'
                    | 'withdrawal',
                })
              }
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              <option value="fiat_to_crypto">Фиат в Крипто</option>
              <option value="crypto_to_fiat">Крипто в Фиат</option>
              <option value="fiat_to_fiat">Фиат в Фиат</option>
              <option value="deposit">Пополнение</option>
              <option value="withdrawal">Вычет</option>
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
              <label className="block text-sm font-medium mb-2">Сумма От</label>
              <input
                type="number"
                step="0.01"
                value={formData.amount_from}
                onChange={(e) =>
                  setFormData({ ...formData, amount_from: e.target.value })
                }
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
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Дата и Время
            </label>
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
              onChange={(e) =>
                setFormData({ ...formData, note: e.target.value })
              }
              rows={2}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
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
      </div>
    </div>
  )
}

export function TransactionsHistory() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(false)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editingTransaction, setEditingTransaction] =
    useState<Transaction | null>(null)

  // Состояние для калькулятора
  const [calculatorInput, setCalculatorInput] = useState('')
  const [calculatorOpen, setCalculatorOpen] = useState(false)
  const [calculatorResult, setCalculatorResult] = useState<string | null>(null)

  // Состояние для меню экспорта
  const [exportMenuOpen, setExportMenuOpen] = useState(false)

  // Пагинация и сортировка
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage, setItemsPerPage] = useState(10)
  const [sortBy, setSortBy] = useState('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [dateFilter, setDateFilter] = useState({ from: '', to: '' })
  const [currencyFilter, setCurrencyFilter] = useState('')

  const currencies = ['USD', 'USDT', 'EUR', 'CZK']

  const fetchTransactions = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/transactions`)
      if (res.ok) {
        const data = await res.json()
        setTransactions(data)
      } else {
        toast.error('Не удалось загрузить транзакции')
      }
    } catch (error) {
      toast.error('Ошибка при загрузке транзакций')
    } finally {
      setLoading(false)
    }
  }

  const updateTransaction = async (transactionId: string, updateData: any) => {
    try {
      console.log('Updating transaction:', {
        id: transactionId,
        apiBase: API_BASE,
        url: `${API_BASE}/transactions/${transactionId}`,
        data: updateData,
      })

      if (!transactionId || transactionId.length < 10) {
        throw new Error('Invalid transaction ID')
      }

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

  const handleDeleteTransaction = async (transactionId: string) => {
    if (!confirm('Вы уверены, что хотите удалить эту транзакцию?')) return

    try {
      console.log('Deleting transaction:', {
        id: transactionId,
        apiBase: API_BASE,
        url: `${API_BASE}/transactions/${transactionId}`,
      })

      if (!transactionId || transactionId.length < 10) {
        throw new Error('Invalid transaction ID')
      }

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

  const handleResetTransactions = async () => {
    if (
      !confirm(
        'Вы уверены, что хотите удалить ВСЕ транзакции? Это действие нельзя отменить!'
      )
    )
      return
    if (
      !confirm(
        'Последнее предупреждение! Все транзакции будут безвозвратно удалены. Продолжить?'
      )
    )
      return

    try {
      const res = await fetch(`${API_BASE}/reset-all-transactions`, {
        method: 'DELETE',
      })

      if (res.ok) {
        toast.success('Все транзакции удалены')
        fetchTransactions()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось удалить все транзакции')
      }
    } catch (error) {
      toast.error('Ошибка при удалении всех транзакций')
    }
  }

  // Функции сортировки и фильтрации
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
        case 'rate_used':
          aValue = a.rate_used || 0
          bValue = b.rate_used || 0
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

  const handleEditTransaction = (tx: Transaction) => {
    setEditingTransaction(tx)
    setIsEditModalOpen(true)
  }

  // Функция для расчета выражения
  const handleCalculatorInput = (value: string) => {
    setCalculatorInput(value)
    if (!value.trim()) {
      setCalculatorResult(null)
      return
    }
    try {
      const result = evaluate(value)
      setCalculatorResult(
        typeof result === 'number' ? result.toString() : JSON.stringify(result)
      )
    } catch (error) {
      setCalculatorResult(null)
    }
  }

  // Функция экспорта в CSV
  const handleExportCSV = async (simple = false) => {
    try {
      const endpoint = simple
        ? `${API_BASE}/transactions/export/csv/simple`
        : `${API_BASE}/transactions/export/csv`

      console.log('Экспорт CSV:', { endpoint, simple, API_BASE })
      toast.info('Загрузка CSV файла...')

      const response = await fetch(endpoint)

      console.log('Ответ сервера:', {
        status: response.status,
        ok: response.ok,
        headers: response.headers,
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('Ошибка ответа:', errorText)
        throw new Error(`Ошибка при экспорте: ${response.status}`)
      }

      const blob = await response.blob()
      console.log('Blob получен:', { size: blob.size, type: blob.type })

      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `transactions_${simple ? 'simple_' : ''}${Date.now()}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)

      toast.success('CSV файл загружен успешно!')
    } catch (error) {
      console.error('Ошибка при экспорте:', error)
      toast.error(
        `Ошибка при экспорте в CSV: ${
          error instanceof Error ? error.message : 'Неизвестная ошибка'
        }`
      )
    }
  }

  // Компонент карточки транзакции для мобильных устройств
  const TransactionCard = ({ tx }: { tx: Transaction }) => {
    const typeLabel =
      tx.type === 'fiat_to_crypto'
        ? 'Фиат в Крипто'
        : tx.type === 'crypto_to_fiat'
        ? 'Крипто в Фиат'
        : tx.type === 'fiat_to_fiat'
        ? 'Фиат в Фиат'
        : tx.type === 'deposit'
        ? 'Пополнение'
        : 'Вычет'
    const typeColor =
      tx.type === 'fiat_to_crypto'
        ? 'bg-blue-100 text-blue-700'
        : tx.type === 'crypto_to_fiat'
        ? 'bg-orange-100 text-orange-700'
        : tx.type === 'fiat_to_fiat'
        ? 'bg-purple-100 text-purple-700'
        : tx.type === 'deposit'
        ? 'bg-green-100 text-green-700'
        : 'bg-red-100 text-red-700'
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
          {tx.is_modified && (
            <span className="px-1 py-0.5 text-xs rounded bg-orange-100 text-orange-600">
              изм.
            </span>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => handleEditTransaction(tx)}
              className="p-1 text-blue-500 hover:text-blue-600 rounded-full"
              title="Редактировать"
            >
              <EditIcon size={16} />
            </button>
            <button
              onClick={() => handleDeleteTransaction(tx._id)}
              className="p-1 text-red-500 hover:text-red-600 rounded-full"
              title="Удалить"
            >
              <TrashIcon size={16} />
            </button>
          </div>
        </div>

        <div className="font-semibold text-lg">
          {tx.type === 'deposit'
            ? `+${tx.amount_from.toFixed(2)} ${tx.from_asset}`
            : tx.type === 'withdrawal'
            ? `${tx.amount_from.toFixed(2)} ${tx.from_asset}`
            : `${tx.amount_from.toFixed(2)} ${
                tx.from_asset
              } → ${tx.amount_to_final.toFixed(2)} ${tx.to_asset}`}
        </div>

        {tx.type !== 'deposit' && tx.type !== 'withdrawal' && (
          <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
            <div>
              <span className="font-medium">Курс:</span> {tx.rate_used}
            </div>
            <div>
              <span className="font-medium">Комиссия:</span>{' '}
              {tx.type === 'fiat_to_crypto'
                ? `-${tx.fee_percent}%`
                : tx.type === 'fiat_to_fiat'
                ? 'нет'
                : `+${tx.fee_percent}%`}
            </div>
            {tx.rate_for_gleb_pnl && (
              <>
                <div>
                  <span className="font-medium">Эфф. курс:</span>{' '}
                  {tx.rate_for_gleb_pnl?.toFixed(4)}
                </div>
                <div></div>
              </>
            )}
            {tx.cost_usdt_of_fiat_in && (
              <>
                <div>
                  <span className="font-medium">Сб.USDT:</span>{' '}
                  {tx.cost_usdt_of_fiat_in?.toFixed(2)}
                </div>
                <div>
                  <span className="font-medium">Курс USDT:</span>{' '}
                  {tx.rate_usdt_of_fiat_in?.toFixed(4)}
                </div>
              </>
            )}
          </div>
        )}

        {tx.type !== 'deposit' && tx.type !== 'withdrawal' && (
          <div className="text-gray-600">
            <span className="font-medium">Прибыль:</span>{' '}
            <span className={profitColor + ' font-bold'}>
              {tx.profit.toFixed(2)} {tx.profit_currency}
            </span>
          </div>
        )}

        {tx.note && (
          <div className="text-xs text-gray-500 truncate" title={tx.note}>
            <span className="font-medium">Пометка:</span> {tx.note}
          </div>
        )}

        <div className="text-xs text-gray-500 pt-1 border-t mt-1 flex justify-between">
          <div>{formattedDate}</div>
          {tx.is_modified && (
            <div className="text-orange-600">
              Изм: {new Date(tx.modified_at!).toLocaleString('ru-RU')}
            </div>
          )}
        </div>
      </div>
    )
  }

  useEffect(() => {
    fetchTransactions()
  }, [])

  // Закрытие меню экспорта при клике вне его
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      if (exportMenuOpen && !target.closest('.export-menu-container')) {
        setExportMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [exportMenuOpen])

  // Сброс страницы при изменении фильтров
  useEffect(() => {
    setCurrentPage(1)
  }, [dateFilter, currencyFilter, sortBy, sortOrder])

  return (
    <div className="space-y-6 w-full max-w-full px-4 sm:px-6">
      {/* Заголовок */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <h2 className="text-xl sm:text-2xl font-bold">История Транзакций</h2>
        <div className="flex gap-2 w-full sm:w-auto flex-wrap">
          <button
            onClick={fetchTransactions}
            disabled={loading}
            className="flex items-center justify-center gap-2 px-3 sm:px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm disabled:opacity-50 flex-1 sm:flex-none"
          >
            <RefreshCwIcon
              size={16}
              className={loading ? 'animate-spin' : ''}
            />
            <span className="hidden sm:inline">Обновить</span>
            <span className="sm:hidden">Обновить</span>
          </button>

          {/* Меню экспорта */}
          <div className="relative flex-1 sm:flex-none export-menu-container">
            <button
              onClick={() => setExportMenuOpen(!exportMenuOpen)}
              className="w-full flex items-center justify-center gap-2 px-3 sm:px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 text-sm"
            >
              <DownloadIcon size={16} />
              <span className="hidden sm:inline">Экспорт</span>
              <span className="sm:hidden">CSV</span>
              <ChevronDownIcon
                size={14}
                className={`transition-transform ${
                  exportMenuOpen ? 'rotate-180' : ''
                }`}
              />
            </button>

            {exportMenuOpen && (
              <div className="absolute right-0 mt-1 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-10">
                <button
                  onClick={() => {
                    handleExportCSV(true)
                    setExportMenuOpen(false)
                  }}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 rounded-t-lg flex items-center gap-2"
                >
                  <DownloadIcon size={14} />
                  Простой CSV
                </button>
                <button
                  onClick={() => {
                    handleExportCSV(false)
                    setExportMenuOpen(false)
                  }}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 rounded-b-lg flex items-center gap-2"
                >
                  <DownloadIcon size={14} />
                  Полный CSV
                </button>
              </div>
            )}
          </div>

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

      {/* Панель фильтров */}
      <div className="bg-gray-50 p-4 rounded-lg space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
      <div className="bg-white border rounded-lg">
        <button
          onClick={() => setCalculatorOpen(!calculatorOpen)}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
        >
          <span className="font-medium text-gray-700">Быстрый Калькулятор</span>
          <ChevronDownIcon
            size={20}
            className={`text-gray-600 transition-transform ${
              calculatorOpen ? 'rotate-180' : ''
            }`}
          />
        </button>

        {calculatorOpen && (
          <div className="border-t p-3 sm:p-4 space-y-3 bg-gray-50">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-2">
                Введите выражение (например: 1000 * 1.05 + 50)
              </label>
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
                <input
                  type="text"
                  value={calculatorInput}
                  onChange={(e) => handleCalculatorInput(e.target.value)}
                  placeholder="Например: 100 + 50 * 2 - (25 / 5)"
                  className="flex-1 px-3 sm:px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-xs sm:text-sm"
                />
                {calculatorResult && (
                  <div className="flex items-center gap-2 font-bold bg-white p-2 rounded-lg border border-blue-200 w-full sm:w-auto">
                    <span className="text-gray-600 text-xs sm:text-sm">=</span>
                    <span className="text-blue-600 text-sm sm:text-lg flex-1 sm:flex-none text-right sm:min-w-[80px] sm:text-right">
                      {calculatorResult}
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-gray-100 p-2 rounded text-xs text-gray-600 space-y-1">
              <div className="font-medium text-gray-700 mb-1">Операции:</div>
              <div className="text-xs sm:text-xs">
                + (плюс), - (минус), * (умножить), / (делить), ^ или **
                (степень)
              </div>
              <div className="font-medium text-gray-700 mt-2 mb-1">
                Функции:
              </div>
              <div className="text-xs sm:text-xs">
                sqrt(), sin(), cos(), tan(), abs(), log(), ln() и др.
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Мобильный вид: Карточки (показываются только на маленьких экранах) */}
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

      {/* Десктопный вид: Таблица (скрывается на маленьких экранах) */}
      <div className="border rounded-lg overflow-hidden bg-white hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px]">
            <thead className="bg-gray-50">
              <tr>
                <th
                  className="px-4 py-3 text-left text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('created_at')}
                >
                  Дата и Время{' '}
                  {sortBy === 'created_at' && (sortOrder === 'asc' ? '↑' : '↓')}
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                  Тип
                </th>
                <th
                  className="px-4 py-3 text-left text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('from_asset')}
                >
                  От{' '}
                  {sortBy === 'from_asset' && (sortOrder === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  className="px-4 py-3 text-left text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('to_asset')}
                >
                  К {sortBy === 'to_asset' && (sortOrder === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  className="px-4 py-3 text-right text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('amount_from')}
                >
                  Сумма От{' '}
                  {sortBy === 'amount_from' &&
                    (sortOrder === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  className="px-4 py-3 text-right text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('amount_to_final')}
                >
                  Сумма К{' '}
                  {sortBy === 'amount_to_final' &&
                    (sortOrder === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  className="px-4 py-3 text-right text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('rate_used')}
                >
                  Курс{' '}
                  {sortBy === 'rate_used' && (sortOrder === 'asc' ? '↑' : '↓')}
                </th>
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                  Эфф. курс
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
                <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                  Сб. USDT
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
                            : tx.type === 'crypto_to_fiat'
                            ? 'bg-orange-100 text-orange-700'
                            : tx.type === 'fiat_to_fiat'
                            ? 'bg-purple-100 text-purple-700'
                            : tx.type === 'deposit'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-red-100 text-red-700'
                        }`}
                      >
                        {tx.type === 'fiat_to_crypto'
                          ? 'Фиат в Крипто'
                          : tx.type === 'crypto_to_fiat'
                          ? 'Крипто в Фиат'
                          : tx.type === 'fiat_to_fiat'
                          ? 'Фиат в Фиат'
                          : tx.type === 'deposit'
                          ? 'Пополнение'
                          : 'Вычет'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm font-medium">
                      {tx.from_asset}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium">
                      {tx.type === 'deposit' || tx.type === 'withdrawal'
                        ? '-'
                        : tx.to_asset}
                    </td>
                    <td className="px-4 py-3 text-sm text-right ">
                      {tx.type === 'withdrawal'
                        ? `${tx.amount_from.toFixed(2)} ${tx.from_asset}`
                        : tx.type === 'fiat_to_fiat'
                        ? `-${tx.amount_from?.toFixed(2)} ${tx.from_asset}`
                        : `+${tx.amount_from?.toFixed(2)} ${tx.from_asset}`}
                    </td>
                    <td className="px-4 py-3 text-sm text-right ">
                      {tx.type === 'deposit' || tx.type === 'withdrawal'
                        ? '-'
                        : tx.type === 'fiat_to_fiat'
                        ? `+${tx.amount_to_final?.toFixed(2)} ${tx.to_asset}`
                        : `-${tx.amount_to_final?.toFixed(2)} ${tx.to_asset}`}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {tx.type === 'deposit' || tx.type === 'withdrawal'
                        ? '-'
                        : tx.rate_used}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {tx.type === 'deposit' || tx.type === 'withdrawal'
                        ? '-'
                        : tx.rate_for_gleb_pnl?.toFixed(4) || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {tx.type === 'deposit' || tx.type === 'withdrawal'
                        ? '-'
                        : tx.type === 'fiat_to_crypto'
                        ? tx.fee_percent === 0
                          ? '0%'
                          : `-${tx.fee_percent}%`
                        : tx.type === 'fiat_to_fiat'
                        ? 'нет'
                        : tx.fee_percent === 0
                        ? '0%'
                        : `+${tx.fee_percent}%`}
                    </td>
                    <td
                      className={`px-4 py-3 text-sm text-right font-medium ${
                        tx.type === 'deposit' || tx.type === 'withdrawal'
                          ? 'text-gray-500'
                          : tx.profit >= 0
                          ? 'text-green-600'
                          : 'text-red-600'
                      }`}
                    >
                      {tx.type === 'deposit' || tx.type === 'withdrawal'
                        ? '-'
                        : tx.profit?.toFixed(2)}{' '}
                      {tx.profit_currency}
                    </td>
                    <td className="px-4 py-3 text-sm text-right">
                      {tx.cost_usdt_of_fiat_in
                        ? tx.cost_usdt_of_fiat_in.toFixed(2)
                        : '-'}
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
                          <EditIcon size={16} />
                        </button>
                        <button
                          onClick={() => handleDeleteTransaction(tx._id)}
                          className="p-1 text-red-500 hover:text-red-600 rounded-full"
                          title="Удалить"
                        >
                          <TrashIcon size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={12}
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

      {/* Пагинация */}
      {getTotalPages() > 1 && (
        <div className="flex flex-col sm:flex-row justify-between items-center mt-4 gap-3">
          <div className="text-xs sm:text-sm text-gray-600 order-2 sm:order-1">
            Страница {currentPage} из {getTotalPages()}
          </div>
          <div className="flex flex-wrap justify-center gap-1 sm:gap-2 order-1 sm:order-2">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="px-2 sm:px-3 py-2 text-xs sm:text-sm bg-gray-500 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed min-w-[60px] sm:min-w-auto"
            >
              ← Назад
            </button>

            {(() => {
              const totalPages = getTotalPages()
              console.log('Pagination debug:', {
                totalPages,
                currentPage,
                filteredLength: getFilteredAndSortedTransactions().length,
              })

              if (totalPages <= 5) {
                // Показываем все страницы если их 5 или меньше
                const allPages = Array.from(
                  { length: totalPages },
                  (_, i) => i + 1
                )
                console.log('All pages:', allPages)
                return allPages.map((pageNum) => (
                  <button
                    key={`page-${pageNum}`}
                    onClick={() => setCurrentPage(pageNum)}
                    className={`px-2 sm:px-3 py-2 text-xs sm:text-sm rounded min-w-[40px] sm:min-w-auto ${
                      currentPage === pageNum
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                  >
                    {pageNum}
                  </button>
                ))
              }

              // Для большого количества страниц показываем 5 страниц вокруг текущей
              let startPage = Math.max(1, currentPage - 2)
              let endPage = Math.min(totalPages, startPage + 4)

              // Корректируем если не хватает страниц в конце
              if (endPage - startPage < 4) {
                startPage = Math.max(1, endPage - 4)
              }

              const pageNumbers = []
              for (let i = startPage; i <= endPage; i++) {
                pageNumbers.push(i)
              }

              console.log('Page numbers:', { startPage, endPage, pageNumbers })

              return pageNumbers.map((pageNum) => (
                <button
                  key={`page-${pageNum}`}
                  onClick={() => setCurrentPage(pageNum)}
                  className={`px-2 sm:px-3 py-2 text-xs sm:text-sm rounded min-w-[40px] sm:min-w-auto ${
                    currentPage === pageNum
                      ? 'bg-blue-500 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {pageNum}
                </button>
              ))
            })()}

            <button
              onClick={() =>
                setCurrentPage(Math.min(getTotalPages(), currentPage + 1))
              }
              disabled={currentPage === getTotalPages()}
              className="px-2 sm:px-3 py-2 text-xs sm:text-sm bg-gray-500 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed min-w-[60px] sm:min-w-auto"
            >
              Вперед →
            </button>
          </div>
        </div>
      )}

      {/* Модальное окно редактирования */}
      <EditTransactionModal
        transaction={editingTransaction}
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false)
          setEditingTransaction(null)
        }}
        onSave={updateTransaction}
      />
    </div>
  )
}
