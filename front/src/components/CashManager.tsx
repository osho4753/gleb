import { useEffect, useState, useCallback, useMemo } from 'react'
import { toast } from 'sonner'
import { config } from '../config'
import { useAuth } from '../services/authService'
import { useCashDesk } from '../services/cashDeskService'

const API_BASE = config.apiBaseUrl

// --- Types for improved clarity ---
type CashStatus = {
  cash: {
    [key: string]: number
  }
}

type SelectedAsset = {
  asset: string
  amount: number
} | null

// --- Custom Modal Component (Inline for Single-File Mandate) ---
const Modal = ({
  isOpen,
  title,
  children,
  onClose,
}: {
  isOpen: boolean
  title: string
  children: React.ReactNode
  onClose: () => void
}) => {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm transform transition-all">
        <div className="p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4">{title}</h3>
          {children}
        </div>
        {/* Optional close button outside the form */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 p-1"
          aria-label="Закрыть"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>
    </div>
  )
}

// --- Main Component ---
export function CashManager() {
  const [currency, setCurrency] = useState('USD')
  const [amount, setAmount] = useState('')
  const [depositNote, setDepositNote] = useState('')
  const [operationType, setOperationType] = useState<'deposit' | 'withdrawal'>(
    'deposit'
  )
  const { authenticatedFetch } = useAuth()
  const { selectedCashDeskId, selectedCashDesk } = useCashDesk()
  const [cashStatus, setCashStatus] = useState<CashStatus>({ cash: {} })
  const [loading, setLoading] = useState(false)

  // State for modal management
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [selectedAsset, setSelectedAsset] = useState<SelectedAsset>(null)
  const [editAmount, setEditAmount] = useState('')

  const currencies = ['USD', 'USDT', 'EUR', 'CZK']

  const fetchCashStatus = useCallback(async () => {
    try {
      const res = await authenticatedFetch(`${API_BASE}/cash/status`)
      if (res.ok) {
        const data = await res.json()
        setCashStatus(data)
      }
    } catch (error) {
      console.error('Failed to fetch cash status:', error)
      toast.error('Не удалось загрузить статус кассы')
    }
  }, [])

  useEffect(() => {
    fetchCashStatus()
  }, [fetchCashStatus])

  // Function to handle balance update API call
  const updateBalance = useCallback(
    async (asset: string, amount: number) => {
      setLoading(true)
      try {
        const res = await authenticatedFetch(
          `${API_BASE}/cash/${asset}?amount=${amount}&cash_desk_id=${selectedCashDeskId}`,
          {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
          }
        )

        if (res.ok) {
          toast.success(`Баланс ${asset} обновлен`)
          fetchCashStatus()
        } else {
          const error = await res.json()
          toast.error(error.detail || 'Не удалось обновить баланс')
        }
      } catch (error) {
        toast.error('Ошибка при обновлении баланса')
      } finally {
        setLoading(false)
      }
    },
    [fetchCashStatus, selectedCashDeskId]
  )

  // Handler for "Set Cash Balance" form submission (POST /cash/set)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!amount || isNaN(parseFloat(amount))) {
      toast.error('Введите корректную сумму')
      return
    }
    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/cash/set?cash_desk_id=${selectedCashDeskId}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            asset: currency,
            amount: parseFloat(amount),
          }),
        }
      )
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

  // Handler for deposit (пополнение)
  const handleDeposit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!amount || isNaN(parseFloat(amount)) || parseFloat(amount) <= 0) {
      toast.error('Введите корректную сумму пополнения')
      return
    }
    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/cash/deposit?cash_desk_id=${selectedCashDeskId}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            asset: currency,
            amount: parseFloat(amount),
            note: depositNote,
          }),
        }
      )
      if (res.ok) {
        const result = await res.json()
        toast.success(`Касса пополнена: ${result.amount} ${result.asset}`)
        setAmount('')
        setDepositNote('')
        fetchCashStatus()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось пополнить кассу')
      }
    } catch (error) {
      toast.error('Ошибка при пополнении кассы')
    } finally {
      setLoading(false)
    }
  }

  // Handler for withdrawal (вычет)
  const handleWithdrawal = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!amount || isNaN(parseFloat(amount)) || parseFloat(amount) <= 0) {
      toast.error('Введите корректную сумму вычета')
      return
    }
    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/cash/withdrawal?cash_desk_id=${selectedCashDeskId}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            asset: currency,
            amount: parseFloat(amount),
            note: depositNote,
          }),
        }
      )
      if (res.ok) {
        const result = await res.json()
        toast.success(`Из кассы выведено: ${result.amount} ${result.asset}`)
        setAmount('')
        setDepositNote('')
        fetchCashStatus()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось вывести средства из кассы')
      }
    } catch (error) {
      toast.error('Ошибка при выводе средств из кассы')
    } finally {
      setLoading(false)
    }
  }

  // --- Modal Control Functions ---

  const handleOpenEditModal = (asset: string, currentAmount: number) => {
    setSelectedAsset({ asset, amount: currentAmount })
    setEditAmount(currentAmount.toFixed(2).toString())
    setIsEditModalOpen(true)
  }

  const handleOpenDeleteModal = (asset: string, currentAmount: number) => {
    setSelectedAsset({ asset, amount: currentAmount })
    setIsDeleteModalOpen(true)
  }

  const handleCloseModals = () => {
    setIsEditModalOpen(false)
    setIsDeleteModalOpen(false)
    setSelectedAsset(null)
    setEditAmount('')
  }

  // --- Modal Action Functions ---

  const handleConfirmEdit = () => {
    if (!selectedAsset) return

    const newAmount = parseFloat(editAmount)
    if (isNaN(newAmount)) {
      toast.error('Введите корректную сумму')
      return
    }

    updateBalance(selectedAsset.asset, newAmount)
    handleCloseModals()
  }

  const handleConfirmDelete = async () => {
    if (!selectedAsset) return

    const assetToDelete = selectedAsset.asset
    handleCloseModals() // Close modal immediately

    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/cash/${assetToDelete}?cash_desk_id=${selectedCashDeskId}`,
        {
          method: 'DELETE',
        }
      )

      if (res.ok) {
        toast.success(`${assetToDelete} удален из кассы`)
        fetchCashStatus()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось удалить валюту')
      }
    } catch (error) {
      toast.error('Ошибка при удалении валюты')
    } finally {
      setLoading(false)
    }
  }

  const cashEntries = useMemo(() => {
    return cashStatus?.cash ? Object.entries(cashStatus.cash) : []
  }, [cashStatus])

  // Проверяем, что касса выбрана
  if (!selectedCashDeskId) {
    return (
      <div className="min-h-screen bg-gray-100 p-4 sm:p-6 lg:p-8 font-sans">
        <div className="max-w-4xl mx-auto space-y-6 sm:space-y-8">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
            <h2 className="text-xl font-semibold text-yellow-800 mb-2">
              ⚠️ Касса не выбрана
            </h2>
            <p className="text-yellow-700">
              Для управления кассой необходимо сначала выбрать кассу в селекторе
              вверху страницы.
            </p>
            <p className="text-yellow-600 text-sm mt-2">
              Если у вас нет касс, создайте их на вкладке "Кассы".
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100 p-4 sm:p-6 lg:p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-6 sm:space-y-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 border-b pb-2">
            Управление Кассой
          </h1>
          {selectedCashDesk && (
            <div className="text-sm text-gray-600 bg-blue-50 px-3 py-1 rounded-lg">
              📦 {selectedCashDesk.name}
            </div>
          )}
        </div>

        {/* Section: Set Cash Balance / Deposit */}
        <div className="bg-white p-4 sm:p-6 rounded-xl shadow-lg border border-gray-200">
          <h2 className="text-lg sm:text-xl font-bold mb-4 sm:mb-5 text-gray-800">
            Управление Балансом
          </h2>

          {/* Operation Type Selector */}
          <div className="mb-4">
            <div className="flex gap-1 p-1 bg-gray-100 rounded-lg">
              <button
                type="button"
                onClick={() => setOperationType('deposit')}
                className={`flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors ${
                  operationType === 'deposit'
                    ? 'bg-white text-green-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Пополнить Кассу
              </button>
              <button
                type="button"
                onClick={() => setOperationType('withdrawal')}
                className={`flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors ${
                  operationType === 'withdrawal'
                    ? 'bg-white text-red-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Вывести из Кассы
              </button>
            </div>
          </div>

          <form
            onSubmit={
              operationType === 'deposit' ? handleDeposit : handleWithdrawal
            }
            className="space-y-4"
          >
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1 text-gray-700">
                  Валюта
                </label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 transition duration-150 ease-in-out"
                >
                  {currencies.map((curr) => (
                    <option key={curr} value={curr}>
                      {curr}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-gray-700">
                  {operationType === 'deposit'
                    ? 'Сумма пополнения'
                    : 'Сумма вывода'}
                </label>
                <input
                  type="number"
                  step="0.01"
                  min={operationType !== 'deposit' ? '0.01' : undefined}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder={
                    operationType === 'deposit'
                      ? 'Введите сумму пополнения'
                      : 'Введите сумму вывода'
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 transition duration-150 ease-in-out"
                />
              </div>
            </div>

            {(operationType === 'deposit' ||
              operationType === 'withdrawal') && (
              <div>
                <label className="block text-sm font-medium mb-1 text-gray-700">
                  {operationType === 'deposit'
                    ? 'Пометка к пополнению'
                    : 'Пометка к выводу'}
                </label>
                <textarea
                  value={depositNote}
                  onChange={(e) => setDepositNote(e.target.value)}
                  placeholder="Введите пометку (необязательно)"
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 transition duration-150 ease-in-out"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className={`w-full px-4 py-2 text-white font-semibold rounded-lg shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition duration-150 ease-in-out ${
                operationType === 'deposit'
                  ? 'bg-green-600 hover:bg-green-700'
                  : 'bg-red-600 hover:bg-red-700'
              }`}
            >
              {loading
                ? operationType === 'deposit'
                  ? 'Пополнение...'
                  : 'Вывод...'
                : operationType === 'deposit'
                ? 'Пополнить Кассу'
                : 'Вывести из Кассы'}
            </button>
          </form>
        </div>

        {/* Section: Current Balances */}
        <div className="bg-white p-4 sm:p-6 rounded-xl shadow-lg border border-gray-200">
          <h2 className="text-lg sm:text-xl font-bold mb-4 text-gray-800">
            Текущие Балансы
          </h2>

          {/* Mobile Card View - Hidden on desktop */}
          <div className="md:hidden space-y-3">
            {cashEntries.length > 0 ? (
              cashEntries.map(([curr, amt]) => (
                <div
                  key={curr}
                  className="border border-gray-200 p-4 rounded-lg shadow-sm bg-white space-y-3"
                >
                  <div className="flex justify-between items-center">
                    <div className="font-medium text-lg">{curr}</div>
                    <div className="text-lg font-semibold">
                      {Number(amt).toFixed(2)}
                    </div>
                  </div>
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => handleOpenDeleteModal(curr, Number(amt))}
                      className="p-2 rounded-full text-white bg-red-500 hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition duration-150"
                      aria-label={`Удалить ${curr}`}
                      disabled={loading}
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
              ))
            ) : (
              <div className="text-center py-6 text-gray-500 italic">
                Балансы не установлены
              </div>
            )}
          </div>

          {/* Desktop Table View - Hidden on mobile */}
          <div className="rounded-lg border overflow-x-auto hidden md:block">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    Валюта
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    Сумма
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    Действия
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {cashEntries.length > 0 ? (
                  cashEntries.map(([curr, amt]) => (
                    <tr
                      key={curr}
                      className="hover:bg-gray-50 transition duration-150"
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {curr}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 text-right">
                        {Number(amt).toFixed(2)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                        <div className="flex gap-2 justify-center">
                          <button
                            onClick={() =>
                              handleOpenDeleteModal(curr, Number(amt))
                            }
                            className="p-1.5 rounded-full text-white bg-red-500 hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition duration-150"
                            aria-label={`Удалить ${curr}`}
                            disabled={loading}
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
                      className="px-6 py-8 text-center text-gray-500 italic"
                    >
                      Балансы не установлены
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* --- Delete Confirmation Modal --- */}
        <Modal
          isOpen={isDeleteModalOpen}
          title={`Удалить ${selectedAsset?.asset || 'валюту'}?`}
          onClose={handleCloseModals}
        >
          <p className="text-gray-700 mb-6">
            Вы уверены, что хотите **удалить** баланс **{selectedAsset?.asset}**
            из кассы? Это действие необратимо.
          </p>
          <div className="flex justify-end gap-3">
            <button
              onClick={handleCloseModals}
              className="px-4 py-2 text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition"
            >
              Отмена
            </button>
            <button
              onClick={handleConfirmDelete}
              disabled={loading}
              className="px-4 py-2 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 disabled:opacity-50 transition"
            >
              Удалить
            </button>
          </div>
        </Modal>
      </div>
    </div>
  )
}
