/**
 * Улучшенный компонент для безопасного удаления касс с проверками
 */

import { useState } from 'react'
import { toast } from 'sonner'
import { AlertCircle, Info, Trash2, RotateCcw } from 'lucide-react'

interface CashDesk {
  _id: string
  name: string
  is_active: boolean
  deleted_at?: string
  usage_summary?: {
    has_data: boolean
  }
}

interface UsageInfo {
  has_balances: boolean
  has_transactions: boolean
  has_fiat_lots: boolean
  has_pnl_matches: boolean
  details: {
    balances?: Array<{ asset: string; balance: number }>
    transactions_count?: number
    active_lots?: Array<{ currency: string; remaining: number }>
    pnl_matches_count?: number
  }
}

interface CashDeskUsageInfo {
  cash_desk: {
    id: string
    name: string
    is_active: boolean
  }
  usage_info: UsageInfo
  can_be_safely_deleted: boolean
}

interface SafeCashDeskDeletionProps {
  cashDesk: CashDesk
  onDeleted: () => void
  onRestored: () => void
  authenticatedFetch: Function
  apiBase: string
}

export function SafeCashDeskDeletion({
  cashDesk,
  onDeleted,
  onRestored,
  authenticatedFetch,
  apiBase,
}: SafeCashDeskDeletionProps) {
  const [loading, setLoading] = useState(false)
  const [usageInfo, setUsageInfo] = useState<CashDeskUsageInfo | null>(null)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [forceDelete, setForceDelete] = useState(false)

  // Получить информацию об использовании кассы
  const fetchUsageInfo = async () => {
    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${apiBase}/cash-desks/${cashDesk._id}/usage-info`
      )
      if (res.ok) {
        const data = await res.json()
        setUsageInfo(data)
      } else {
        toast.error('Не удалось получить информацию о кассе')
      }
    } catch (error) {
      toast.error('Ошибка при получении информации о кассе')
    } finally {
      setLoading(false)
    }
  }

  // Удалить кассу
  const deactivateCashDesk = async () => {
    setLoading(true)
    try {
      const url = `${apiBase}/cash-desks/${cashDesk._id}${
        forceDelete ? '?force=true' : ''
      }`
      const res = await authenticatedFetch(url, { method: 'DELETE' })

      if (res.ok) {
        const result = await res.json()

        if (result.error === 'cash_desk_has_active_data') {
          // Касса имеет активные данные
          toast.warning('Касса содержит активные данные')
          setUsageInfo({
            cash_desk: {
              id: cashDesk._id,
              name: cashDesk.name,
              is_active: true,
            },
            usage_info: result.usage_info,
            can_be_safely_deleted: false,
          })
          setShowConfirmDialog(true)
        } else {
          // Успешное удаление
          toast.success(result.message)

          // Показываем детали удаленных данных
          if (result.deleted_data) {
            const deletedData = result.deleted_data
            const deletedItems = []
            if (deletedData.balances_deleted > 0)
              deletedItems.push(`${deletedData.balances_deleted} балансов`)
            if (deletedData.transactions_deleted > 0)
              deletedItems.push(
                `${deletedData.transactions_deleted} транзакций`
              )
            if (deletedData.fiat_lots_deleted > 0)
              deletedItems.push(
                `${deletedData.fiat_lots_deleted} фиатных лотов`
              )
            if (deletedData.pnl_matches_deleted > 0)
              deletedItems.push(`${deletedData.pnl_matches_deleted} PnL матчей`)

            if (deletedItems.length > 0) {
              toast.info(`Также удалено: ${deletedItems.join(', ')}`)
            }
          }

          if (result.warning) {
            toast.warning(result.warning)
          }

          setShowConfirmDialog(false)
          onDeleted()
        }
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось удалить кассу')
      }
    } catch (error) {
      toast.error('Ошибка при удалении кассы')
    } finally {
      setLoading(false)
    }
  }

  // Восстановить кассу
  const restoreCashDesk = async () => {
    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${apiBase}/cash-desks/${cashDesk._id}/restore`,
        {
          method: 'POST',
        }
      )

      if (res.ok) {
        const result = await res.json()
        toast.success(result.message)
        toast.warning(
          'Внимание: удаленные данные (балансы, транзакции и т.д.) не восстанавливаются автоматически'
        )
        onRestored()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось восстановить кассу')
      }
    } catch (error) {
      toast.error('Ошибка при восстановлении кассы')
    } finally {
      setLoading(false)
    }
  }

  // Начать процесс удаления
  const startDeletion = async () => {
    await fetchUsageInfo()
    setShowConfirmDialog(true)
  }

  if (showConfirmDialog && usageInfo) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-96 overflow-y-auto">
          <div className="flex items-center gap-3 mb-4">
            <AlertCircle className="text-orange-500" size={24} />
            <h3 className="text-lg font-semibold">
              Удаление кассы "{usageInfo.cash_desk.name}"
            </h3>
          </div>

          {/* Предупреждение о каскадном удалении */}
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle size={16} className="text-red-600" />
              <span className="font-medium text-red-800">
                ⚠️ Внимание! Каскадное удаление
              </span>
            </div>
            <p className="text-red-700 text-sm">
              При удалении кассы будут <strong>безвозвратно удалены</strong> все
              связанные данные: балансы, транзакции, фиатные лоты и PnL матчи.
              Восстановление кассы не восстановит эти данные.
            </p>
          </div>

          {/* Статус безопасности */}
          <div
            className={`p-3 rounded-lg mb-4 ${
              usageInfo.can_be_safely_deleted
                ? 'bg-green-50 border border-green-200'
                : 'bg-orange-50 border border-orange-200'
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <Info
                size={16}
                className={
                  usageInfo.can_be_safely_deleted
                    ? 'text-green-600'
                    : 'text-orange-600'
                }
              />
              <span
                className={`font-medium ${
                  usageInfo.can_be_safely_deleted
                    ? 'text-green-800'
                    : 'text-orange-800'
                }`}
              >
                {usageInfo.can_be_safely_deleted
                  ? 'Касса может быть безопасно удалена'
                  : 'Внимание! Касса содержит активные данные'}
              </span>
            </div>
          </div>

          {/* Детали использования */}
          <div className="space-y-3 mb-6">
            {usageInfo.usage_info.has_balances && (
              <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
                <div className="font-medium text-yellow-800 mb-2">
                  💰 Ненулевые балансы:
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {usageInfo.usage_info.details.balances?.map(
                    (balance, idx) => (
                      <div key={idx} className="text-sm">
                        {balance.asset}: {balance.balance}
                      </div>
                    )
                  )}
                </div>
              </div>
            )}

            {usageInfo.usage_info.has_fiat_lots && (
              <div className="bg-purple-50 border border-purple-200 rounded p-3">
                <div className="font-medium text-purple-800 mb-2">
                  📊 Активные фиатные лоты:
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {usageInfo.usage_info.details.active_lots?.map((lot, idx) => (
                    <div key={idx} className="text-sm">
                      {lot.currency}: {lot.remaining.toFixed(2)}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {usageInfo.usage_info.has_transactions && (
              <div className="bg-blue-50 border border-blue-200 rounded p-3">
                <div className="font-medium text-blue-800">
                  📝 Транзакций:{' '}
                  {usageInfo.usage_info.details.transactions_count}
                </div>
              </div>
            )}

            {usageInfo.usage_info.has_pnl_matches && (
              <div className="bg-green-50 border border-green-200 rounded p-3">
                <div className="font-medium text-green-800">
                  🎯 PnL матчей:{' '}
                  {usageInfo.usage_info.details.pnl_matches_count}
                </div>
              </div>
            )}
          </div>

          {/* Опция принудительного удаления */}
          {!usageInfo.can_be_safely_deleted && (
            <div className="mb-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={forceDelete}
                  onChange={(e) => setForceDelete(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm">
                  Я понимаю риски и хочу <strong>безвозвратно удалить</strong>{' '}
                  кассу со всеми данными
                </span>
              </label>
            </div>
          )}

          {/* Кнопки действий */}
          <div className="flex gap-3 justify-end">
            <button
              onClick={() => {
                setShowConfirmDialog(false)
                setForceDelete(false)
              }}
              className="px-4 py-2 bg-gray-300 text-gray-800 rounded hover:bg-gray-400"
            >
              Отмена
            </button>
            <button
              onClick={deactivateCashDesk}
              disabled={
                loading || (!usageInfo.can_be_safely_deleted && !forceDelete)
              }
              className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50 flex items-center gap-2"
            >
              <Trash2 size={16} />
              {loading ? 'Удаление...' : 'Удалить'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Обычные кнопки
  if (cashDesk.is_active) {
    return (
      <button
        onClick={startDeletion}
        disabled={loading}
        className="px-3 py-1 text-red-600 hover:bg-red-50 rounded font-medium disabled:opacity-50 flex items-center gap-1"
      >
        <Trash2 size={14} />
        Удалить
      </button>
    )
  } else {
    return (
      <div className="flex gap-2">
        <span className="px-2 py-1 bg-gray-200 text-gray-600 rounded text-xs">
          Удалена{' '}
          {cashDesk.deleted_at &&
            new Date(cashDesk.deleted_at).toLocaleDateString('ru-RU')}
        </span>
        <button
          onClick={restoreCashDesk}
          disabled={loading}
          className="px-3 py-1 text-blue-600 hover:bg-blue-50 rounded font-medium disabled:opacity-50 flex items-center gap-1"
        >
          <RotateCcw size={14} />
          Восстановить
        </button>
      </div>
    )
  }
}

export default SafeCashDeskDeletion
