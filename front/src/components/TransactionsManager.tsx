import React, { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { RefreshCwIcon, TrashIcon } from 'lucide-react'
import { config } from '../config'

const API_BASE = config.apiBaseUrl
export function TransactionsManager() {
  const [transactions, setTransactions] = useState<any>([])
  const [loading, setLoading] = useState(false)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editingTransaction, setEditingTransaction] = useState<any>(null)

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
      console.error('Failed to fetch transactions')
    }
  }
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

  const handleEditTransaction = (tx: any) => {
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

  // Функции сортировки и фильтрации
  const sortTransactions = (transactions: any[]) => {
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

  const filterTransactions = (transactions: any[]) => {
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
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Транзакции</h2>
        <div className="flex gap-2">
          <button
            onClick={fetchTransactions}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            <RefreshCwIcon size={16} />
            Обновить
          </button>
          <button
            onClick={handleResetTransactions}
            className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            <TrashIcon size={16} />
            Удалить Все
          </button>
        </div>
      </div>
      <div className="bg-gray-50 p-6 rounded-lg">
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
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="fiat_to_crypto">Фиат в Крипто</option>
              <option value="crypto_to_fiat">Крипто в Фиат</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
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
              <label className="block text-sm font-medium mb-2">В Актив</label>
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
              <label className="block text-sm font-medium mb-2">От</label>
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
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? 'Создание...' : 'Создать Транзакцию'}
          </button>
        </form>
      </div>
      <div>
        <h3 className="text-lg font-semibold mb-3">История Транзакций</h3>

        {/* Панель фильтров и сортировки */}
        <div className="bg-gray-50 p-4 rounded-lg mb-4 space-y-4">
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

          {/* Кнопки очистки фильтров */}
          <div className="flex gap-2">
            <button
              onClick={() => {
                setDateFilter({ from: '', to: '' })
                setCurrencyFilter('')
                setCurrentPage(1)
              }}
              className="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600"
            >
              Очистить фильтры
            </button>
            <div className="text-sm text-gray-600 flex items-center">
              Показано: {getPaginatedTransactions().length} из{' '}
              {getFilteredAndSortedTransactions().length} транзакций
            </div>
          </div>
        </div>

        <div className="border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
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
                    От{' '}
                    {sortBy === 'amount_from' &&
                      (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                  <th
                    className="px-4 py-3 text-right text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort('amount_to_final')}
                  >
                    К{' '}
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
                  getPaginatedTransactions().map((tx: any) => (
                    <tr key={tx._id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm">
                        {new Date(tx.created_at).toLocaleString('ru-RU')}
                        {tx.is_modified && (
                          <div className="text-xs text-orange-600">
                            Изменено:{' '}
                            {new Date(tx.modified_at).toLocaleString('ru-RU')}
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
                        {tx.is_modified && (
                          <div className="inline-block ml-1">
                            <span className="px-1 py-0.5 text-xs rounded bg-orange-100 text-orange-600">
                              ред.
                            </span>
                          </div>
                        )}
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
                            className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
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
                            onClick={() => handleDeleteTransaction(tx._id)}
                            className="px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600"
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

        {/* Пагинация */}
        {getTotalPages() > 1 && (
          <div className="flex justify-between items-center mt-4 px-4">
            <div className="text-sm text-gray-600">
              Страница {currentPage} из {getTotalPages()}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1}
                className="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                ← Назад
              </button>

              {/* Номера страниц */}
              {Array.from({ length: Math.min(5, getTotalPages()) }, (_, i) => {
                const pageNum = Math.max(
                  1,
                  Math.min(getTotalPages(), currentPage - 2 + i)
                )
                return (
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
                )
              })}

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

      {/* Модальное окно редактирования */}
      {isEditModalOpen && editingTransaction && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
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

// Компонент формы редактирования
function EditTransactionForm({
  transaction,
  onSave,
  onCancel,
}: {
  transaction: any
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
          onChange={(e) => setFormData({ ...formData, type: e.target.value })}
          className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="fiat_to_crypto">Фиат в Крипто</option>
          <option value="crypto_to_fiat">Крипто в Фиат</option>
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-2">Из Актива</label>
          <select
            value={formData.from_asset}
            onChange={(e) =>
              setFormData({ ...formData, from_asset: e.target.value })
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
          <label className="block text-sm font-medium mb-2">В Актив</label>
          <select
            value={formData.to_asset}
            onChange={(e) =>
              setFormData({ ...formData, to_asset: e.target.value })
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
          <label className="block text-sm font-medium mb-2">От</label>
          <input
            type="number"
            step="0.01"
            value={formData.amount_from}
            onChange={(e) =>
              setFormData({ ...formData, amount_from: e.target.value })
            }
            className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">Курс</label>
          <input
            type="number"
            step="0.00000001"
            value={formData.rate_used}
            onChange={(e) =>
              setFormData({ ...formData, rate_used: e.target.value })
            }
            className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
          className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
          className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Пометка</label>
        <textarea
          value={formData.note}
          onChange={(e) => setFormData({ ...formData, note: e.target.value })}
          rows={3}
          className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Пометка к транзакции"
        />
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
        >
          Сохранить
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600"
        >
          Отмена
        </button>
      </div>
    </form>
  )
}
