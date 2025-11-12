import React, { useState } from 'react'
import { toast } from 'sonner'
import { config } from '../config'
import { ChevronDownIcon } from 'lucide-react'
import { evaluate } from 'mathjs'

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
    to_asset: 'USDT',
    amount_from: '',
    rate_used: '',
    fee_percent: '1',
    note: '',
  })
  const currencies = ['USD', 'USDT', 'EUR', 'CZK']

  // Ref для скролла к форме
  const formInputsRef = React.useRef<HTMLDivElement>(null)

  // Состояние для модального окна пополнения кассы
  const [insufficientFundsModal, setInsufficientFundsModal] = useState({
    isOpen: false,
    asset: '',
    currentBalance: 0,
    requiredAmount: 0,
    shortfall: 0,
  })
  const [replenishmentAmount, setReplenishmentAmount] = useState('')
  const [replenishmentNote, setReplenishmentNote] = useState('')
  const [replenishing, setReplenishing] = useState(false)
  const [calculatorInput, setCalculatorInput] = useState('')
  const [calculatorResult, setCalculatorResult] = useState<string | null>(null)

  // Предустановки для быстрой навигации
  const presets = [
    { from: 'USD', to: 'USDT' },
    { from: 'EUR', to: 'USDT' },
    { from: 'CZK', to: 'USDT' },
    { from: 'USDT', to: 'USD' },
    { from: 'USDT', to: 'EUR' },
    { from: 'USDT', to: 'CZK' },
    { from: 'EUR', to: 'USD' },
    { from: 'USD', to: 'EUR' },
    { from: 'CZK', to: 'USD' },
    { from: 'USD', to: 'CZK' },
    { from: 'CZK', to: 'EUR' },
    { from: 'EUR', to: 'CZK' },
  ]

  const loadPreset = (preset: (typeof presets)[0]) => {
    // Определяем тип транзакции на основе пары валют
    const fiatCurrencies = ['USD', 'EUR', 'CZK']

    const isFromFiat = fiatCurrencies.includes(preset.from)
    const isToFiat = fiatCurrencies.includes(preset.to)

    let transactionType: string
    if (isFromFiat && isToFiat) {
      transactionType = 'fiat_to_fiat'
    } else if (isFromFiat && !isToFiat) {
      transactionType = 'fiat_to_crypto'
    } else {
      transactionType = 'crypto_to_fiat'
    }

    setFormData({
      ...formData,
      type: transactionType,
      from_asset: preset.from,
      to_asset: preset.to,
      fee_percent: '1',
    })

    // Скролл к форме ввода
    setTimeout(() => {
      formInputsRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      })
    }, 100)
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
        const result = await res.json()
        const effRate = result.rate_for_gleb_pnl
          ? ` (Эфф. курс: ${result.rate_for_gleb_pnl.toFixed(4)})`
          : ''
        toast.success(`Транзакция успешно создана${effRate}`)
        setFormData({
          ...formData,
          amount_from: '',
          rate_used: '',
        })
      } else {
        const error = await res.json()

        // Проверяем, это ошибка недостаточности средств
        if (error.detail && error.detail.includes('Not enough')) {
          // Парсим название актива из ошибки
          const assetMatch = error.detail.match(/Not enough (\w+)/)
          const asset = assetMatch ? assetMatch[1] : formData.to_asset

          // Получаем текущий баланс кассы
          try {
            const cashRes = await fetch(`${API_BASE}/cash/status`)
            if (cashRes.ok) {
              const cashData = await cashRes.json()
              const currentBalance = cashData.cash[asset] || 0

              // Вычисляем недостаток
              const requiredAmount =
                formData.type === 'fiat_to_crypto'
                  ? Math.ceil(
                      (parseFloat(formData.amount_from) *
                        parseFloat(formData.rate_used)) /
                        (1 + parseFloat(formData.fee_percent) / 100)
                    )
                  : Math.ceil(
                      parseFloat(formData.amount_from) *
                        parseFloat(formData.rate_used) *
                        (1 + parseFloat(formData.fee_percent) / 100)
                    )
              const shortfall = requiredAmount - currentBalance

              setInsufficientFundsModal({
                isOpen: true,
                asset,
                currentBalance,
                requiredAmount,
                shortfall: Math.max(0, shortfall),
              })
            }
          } catch (e) {
            toast.error('Не удалось получить информацию о кассе')
          }
        } else {
          toast.error(error.detail || 'Не удалось создать транзакцию')
        }
      }
    } catch (error) {
      toast.error('Ошибка при создании транзакции')
    } finally {
      setLoading(false)
    }
  }

  const handleReplenishCash = async () => {
    const amount = parseFloat(replenishmentAmount)
    if (!amount || amount <= 0) {
      toast.error('Укажите сумму пополнения')
      return
    }

    setReplenishing(true)
    try {
      const res = await fetch(`${API_BASE}/cash/deposit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          asset: insufficientFundsModal.asset,
          amount: amount,
          note: replenishmentNote,
          created_at: new Date().toISOString(),
        }),
      })

      if (res.ok) {
        toast.success(
          `Касса пополнена на ${amount} ${insufficientFundsModal.asset}`
        )
        setInsufficientFundsModal({ ...insufficientFundsModal, isOpen: false })
        setReplenishmentAmount('')
        setReplenishmentNote('')
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось пополнить кассу')
      }
    } catch (error) {
      toast.error('Ошибка при пополнении кассы')
    } finally {
      setReplenishing(false)
    }
  }
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

  return (
    <div className="space-y-6 w-full max-w-full px-4 sm:px-6">
      {/* HEADER: Заголовок */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <h2 className="text-xl sm:text-2xl font-bold">Транзакции</h2>
      </div>

      {/* ФОРМА: Создание транзакции */}
      <div className="bg-gray-50 p-4 sm:p-6 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">Создать Транзакцию</h3>

        {/* БЫСТРАЯ НАВИГАЦИЯ: Кнопки для предустановок */}
        <div className="mb-6 pb-6 border-b">
          <p className="text-sm font-medium text-gray-700 mb-3">
            Быстрая навигация:
          </p>

          {/* Фиат → Крипто */}
          <div className="mb-4">
            <p className="text-xs font-semibold text-blue-600 mb-2">
              💵 Фиат → Крипто
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {presets.slice(0, 3).map((preset, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => loadPreset(preset)}
                  className="px-3 py-2 bg-white border-2 border-blue-300 rounded-lg text-sm font-medium text-gray-800 hover:bg-blue-50 hover:border-blue-400 transition-colors text-center"
                >
                  {preset.from}
                  <br />
                  <span className="text-xs text-gray-500">→</span>
                  <br />
                  {preset.to}
                </button>
              ))}
            </div>
          </div>

          {/* Крипто → Фиат */}
          <div className="mb-4">
            <p className="text-xs font-semibold text-orange-600 mb-2">
              🔄 Крипто → Фиат
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {presets.slice(3, 6).map((preset, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => loadPreset(preset)}
                  className="px-3 py-2 bg-white border-2 border-orange-300 rounded-lg text-sm font-medium text-gray-800 hover:bg-orange-50 hover:border-orange-400 transition-colors text-center"
                >
                  {preset.from}
                  <br />
                  <span className="text-xs text-gray-500">→</span>
                  <br />
                  {preset.to}
                </button>
              ))}
            </div>
          </div>

          {/* Фиат → Фиат */}
          <div>
            <p className="text-xs font-semibold text-purple-600 mb-2">
              💱 Фиат → Фиат
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {presets.slice(6).map((preset, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => loadPreset(preset)}
                  className="px-3 py-2 bg-white border-2 border-purple-300 rounded-lg text-sm font-medium text-gray-800 hover:bg-purple-50 hover:border-purple-400 transition-colors text-center"
                >
                  {preset.from}
                  <br />
                  <span className="text-xs text-gray-500">→</span>
                  <br />
                  {preset.to}
                </button>
              ))}
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div ref={formInputsRef}>
            <label className="block text-sm font-medium mb-2">
              Тип Транзакции
            </label>
            <select
              value={formData.type}
              onChange={(e) => {
                const newType = e.target.value
                let fromAsset, toAsset

                if (newType === 'crypto_to_fiat') {
                  fromAsset = 'USDT'
                  toAsset = 'USD'
                } else if (newType === 'fiat_to_fiat') {
                  fromAsset = 'CZK'
                  toAsset = 'EUR'
                } else {
                  // fiat_to_crypto
                  fromAsset = 'USD'
                  toAsset = 'USDT'
                }

                setFormData({
                  ...formData,
                  type: newType,
                  from_asset: fromAsset,
                  to_asset: toAsset,
                })

                // Скролл к форме ввода
                setTimeout(() => {
                  formInputsRef.current?.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start',
                  })
                }, 100)
              }}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              <option value="fiat_to_crypto">Фиат в Крипто</option>
              <option value="crypto_to_fiat">Крипто в Фиат</option>
              <option value="fiat_to_fiat">Фиат в Фиат</option>
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 items-end">
            <div className="sm:col-span-2">
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

            {/* Кнопка свапа активов - в центре */}
            <div className="flex justify-center">
              <button
                type="button"
                onClick={() => {
                  // Определяем новый тип транзакции
                  const fiatCurrencies = ['USD', 'EUR', 'CZK']
                  const fromIsFiat = fiatCurrencies.includes(formData.to_asset)
                  const toIsFiat = fiatCurrencies.includes(formData.from_asset)
                  const newType =
                    fromIsFiat && !toIsFiat
                      ? 'fiat_to_crypto'
                      : 'crypto_to_fiat'

                  setFormData({
                    ...formData,
                    type: newType,
                    from_asset: formData.to_asset,
                    to_asset: formData.from_asset,
                  })
                }}
                className="px-4 py-2 bg-gradient-to-r from-blue-500 to-blue-900 text-white rounded-lg hover:from-blue-600 hover:to-blue-800 font-bold transition-all text-lg flex items-center justify-center w-12 h-10"
                title="Поменять активы местами"
              >
                ⇅
              </button>
            </div>

            <div className="sm:col-span-2">
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
            <div className="space-y-2">
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
              <div className="flex gap-2 flex-wrap">
                {[0, 0.5, 1, 1.5, 2, 2.5].map((percent) => (
                  <button
                    key={percent}
                    type="button"
                    onClick={() =>
                      setFormData({
                        ...formData,
                        fee_percent: percent.toString(),
                      })
                    }
                    className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                      formData.fee_percent === percent.toString()
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                    }`}
                  >
                    {percent}%
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="border-t p-3 sm:p-4 space-y-3 bg-gray-50">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-2">
                Быстрый Калькулятор
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

      {/* МОДАЛЬНОЕ ОКНО: Пополнение кассы */}
      {insufficientFundsModal.isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white p-6 rounded-lg max-w-md w-full space-y-4">
            <h3 className="text-lg font-semibold text-red-600">
              ⚠️ Недостаточно средств
            </h3>

            <div className="bg-red-50 border border-red-200 p-4 rounded space-y-3">
              <div className="flex justify-between items-center"></div>
              <div className="flex justify-between items-center">
                <span className="text-gray-700">В кассе сейчас:</span>
                <span className="font-bold">
                  {insufficientFundsModal.currentBalance.toFixed(2)}{' '}
                  {insufficientFundsModal.asset}
                </span>
              </div>
              <div className="border-t pt-3 flex justify-between items-center">
                <span className="text-red-600 font-semibold">Недостаток:</span>
                <span className="font-bold text-red-600 text-lg">
                  {insufficientFundsModal.shortfall.toFixed(2)}{' '}
                  {insufficientFundsModal.asset}
                </span>
              </div>
            </div>

            <p className="text-sm text-gray-600">
              Пополните кассу {insufficientFundsModal.asset}, чтобы продолжить
              транзакцию
            </p>

            <div>
              <label className="block text-sm font-medium mb-2">
                Сумма пополнения ({insufficientFundsModal.asset})
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  step="0.01"
                  value={replenishmentAmount}
                  onChange={(e) => setReplenishmentAmount(e.target.value)}
                  className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Необходимо минимум:{' '}
                {insufficientFundsModal.shortfall.toFixed(2)}{' '}
                {insufficientFundsModal.asset}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Пометка (необязательно)
              </label>
              <textarea
                value={replenishmentNote}
                onChange={(e) => setReplenishmentNote(e.target.value)}
                placeholder="Например: Получено от клиента, Пополнение картой и т.д."
                rows={3}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setInsufficientFundsModal({
                    ...insufficientFundsModal,
                    isOpen: false,
                  })
                  setReplenishmentAmount('')
                  setReplenishmentNote('')
                }}
                className="flex-1 px-4 py-2 bg-gray-300 text-gray-800 rounded-lg hover:bg-gray-400 font-medium"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleReplenishCash}
                disabled={replenishing}
                className="flex-1 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 font-medium"
              >
                {replenishing ? 'Пополнение...' : 'Пополнить кассу'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
