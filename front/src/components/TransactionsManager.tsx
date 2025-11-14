import React, { useState } from 'react'
import { toast } from 'sonner'
import { config } from '../config'
import { useAuth } from '../services/authService'
import { useCashDesk } from '../services/cashDeskService'

import { evaluate } from 'mathjs'

const API_BASE = config.apiBaseUrl

interface TransactionsManagerProps {
  onNavigateToHistory?: () => void
}

export function TransactionsManager({
  onNavigateToHistory,
}: TransactionsManagerProps) {
  const [loading, setLoading] = useState(false)
  const { authenticatedFetch } = useAuth()
  const { selectedCashDeskId, selectedCashDesk, cashDesks } = useCashDesk()
  const [formData, setFormData] = useState({
    type: 'fiat_to_crypto',
    from_asset: 'USD',
    to_asset: 'USDT',
    amount_from: '',
    rate_used: '',
    fee_percent: '1',
    note: '',
    to_cash_desk_id: '',
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

  // Состояние для предварительного просмотра транзакции
  const [preview, setPreview] = useState<any>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewExpanded, setPreviewExpanded] = useState(false)

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
    if (
      !formData.amount_from ||
      (!formData.rate_used && formData.type !== 'cash_to_cash')
    ) {
      toast.error('Заполните все обязательные поля')
      return
    }
    if (!selectedCashDeskId) {
      toast.error('Выберите кассу для работы')
      return
    }
    if (formData.type === 'cash_to_cash') {
      if (!formData.to_cash_desk_id) {
        toast.error('Выберите кассу-получателя')
        return
      }
      setLoading(true)
      try {
        // 1. Списание с текущей кассы
        const res1 = await authenticatedFetch(
          `${API_BASE}/cash/withdrawal?cash_desk_id=${selectedCashDeskId}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset: formData.from_asset,
              amount: parseFloat(formData.amount_from),
              note: `Перевод в кассу: ${
                cashDesks.find((d) => d._id === formData.to_cash_desk_id)
                  ?.name || formData.to_cash_desk_id
              }`,
            }),
          }
        )
        // 2. Депозит в кассу-получатель
        const res2 = await authenticatedFetch(
          `${API_BASE}/cash/deposit?cash_desk_id=${formData.to_cash_desk_id}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset: formData.from_asset,
              amount: parseFloat(formData.amount_from),
              note: `Получено из кассы: ${
                cashDesks.find((d) => d._id === selectedCashDeskId)?.name ||
                selectedCashDeskId
              }`,
            }),
          }
        )
        if (res1.ok && res2.ok) {
          toast.success('✅ Перевод между кассами выполнен!')
          setFormData({
            ...formData,
            amount_from: '',
            to_cash_desk_id: '',
          })
        } else {
          toast.error('Ошибка при переводе между кассами')
        }
      } catch (error) {
        toast.error('Ошибка при переводе между кассами')
      } finally {
        setLoading(false)
      }
      return
    }
    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/transactions?cash_desk_id=${selectedCashDeskId}`,
        {
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
        }
      )
      if (res.ok) {
        const result = await res.json()
        const effRate = result.rate_for_gleb_pnl
          ? ` (Эфф. курс: ${result.rate_for_gleb_pnl.toFixed(4)})`
          : ''
        toast.success(`✅ Транзакция успешно создана${effRate}.`)
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
            const cashRes = await authenticatedFetch(
              `${API_BASE}/cash/status?cash_desk_id=${selectedCashDeskId}`
            )
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

  // Функция для расчета предварительного просмотра транзакции
  const calculatePreview = React.useCallback(async () => {
    if (!formData.amount_from || !formData.rate_used || !selectedCashDeskId) {
      setPreview(null)
      return
    }

    setPreviewLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/transactions/calculate-preview?cash_desk_id=${selectedCashDeskId}`,
        {
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
        }
      )

      if (res.ok) {
        const result = await res.json()
        setPreview(result)
      } else {
        setPreview(null)
      }
    } catch (error) {
      console.error('Error calculating preview:', error)
      setPreview(null)
    } finally {
      setPreviewLoading(false)
    }
  }, [formData, authenticatedFetch, selectedCashDeskId])

  // Автоматический расчет предварительного просмотра при изменении данных
  React.useEffect(() => {
    const timer = setTimeout(() => {
      calculatePreview()
    }, 500) // Debounce 500ms

    return () => clearTimeout(timer)
  }, [calculatePreview])

  const handleReplenishCash = async () => {
    const amount = parseFloat(replenishmentAmount)
    if (!amount || amount <= 0) {
      toast.error('Укажите сумму пополнения')
      return
    }

    setReplenishing(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/cash/deposit?cash_desk_id=${selectedCashDeskId}`,
        {
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
        }
      )

      if (res.ok) {
        toast.success(
          `✅ Касса пополнена на ${amount} ${insufficientFundsModal.asset}. Данные синхронизированы с Google Таблицей.`
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
        <div>
          <h2 className="text-xl sm:text-2xl font-bold">Транзакции</h2>
          {selectedCashDesk && (
            <p className="text-sm text-gray-600">
              Касса:{' '}
              <span className="font-medium text-blue-600">
                {selectedCashDesk.name}
              </span>
            </p>
          )}
          {!selectedCashDeskId && (
            <p className="text-sm text-red-600 font-medium">
              ⚠️ Выберите кассу для работы
            </p>
          )}
        </div>
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
            {/* Тип транзакции */}
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
                } else if (newType === 'cash_to_cash') {
                  fromAsset = 'USD'
                  toAsset = 'USD'
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
                  note: '', // note будет автозаполняться
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
              <option value="cash_to_cash">С кассы в кассу</option>
            </select>
          </div>

          {/* Если выбран перевод между кассами — показываем только нужные инпуты */}
          {formData.type === 'cash_to_cash' && (
            <>
              <div className="mt-2">
                <label className="block text-sm font-medium mb-2">
                  В какую кассу перевести
                </label>
                <select
                  value={formData.to_cash_desk_id}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      to_cash_desk_id: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  <option value="">Выберите кассу...</option>
                  {cashDesks
                    .filter((d) => d._id !== selectedCashDeskId)
                    .map((desk) => (
                      <option key={desk._id} value={desk._id}>
                        {desk.name}
                      </option>
                    ))}
                </select>
              </div>
              <div className="mt-2">
                <label className="block text-sm font-medium mb-2">Валюта</label>
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
              <div className="mt-2">
                <label className="block text-sm font-medium mb-2">Сумма</label>
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
            </>
          )}

          {/* Если не cash_to_cash, то показываем полную форму */}
          {formData.type !== 'cash_to_cash' && (
            <>
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
                      const fromIsFiat = fiatCurrencies.includes(
                        formData.to_asset
                      )
                      const toIsFiat = fiatCurrencies.includes(
                        formData.from_asset
                      )
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
                  <label className="block text-sm font-medium mb-2">
                    В Актив
                  </label>
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
                        <span className="text-gray-600 text-xs sm:text-sm">
                          =
                        </span>
                        <span className="text-blue-600 text-sm sm:text-lg flex-1 sm:flex-none text-right sm:min-w-[80px] sm:text-right">
                          {calculatorResult}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">
                  Пометка
                </label>
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

              {/* ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР */}
              {(preview || previewLoading) && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg overflow-hidden">
                  <div
                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-blue-100 transition-colors"
                    onClick={() => setPreviewExpanded(!previewExpanded)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-blue-600 font-semibold">
                        📊 Предварительный просмотр
                      </span>
                      {previewLoading && (
                        <span className="text-xs text-gray-500">
                          Рассчитывается...
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {preview && !previewLoading && (
                        <span className="text-xs text-blue-600 font-medium">
                          {previewExpanded ? 'Свернуть' : 'Развернуть'}
                        </span>
                      )}
                      <svg
                        className={`w-5 h-5 text-blue-600 transition-transform duration-200 ${
                          previewExpanded ? 'rotate-180' : ''
                        }`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 9l-7 7-7-7"
                        />
                      </svg>
                    </div>
                  </div>

                  {previewExpanded && preview && !previewLoading && (
                    <div className="px-4 pb-4 space-y-3">
                      <div className="space-y-3">
                        {/* Детали транзакции */}
                        <div className="bg-white rounded p-3 space-y-2">
                          <h4 className="font-medium text-sm text-gray-700">
                            💰 Детали транзакции
                          </h4>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            {preview.transaction_preview?.type ===
                            'fiat_to_fiat' ? (
                              <>
                                <div>
                                  Получаем:{' '}
                                  <span className="font-semibold text-green-600">
                                    +
                                    {
                                      preview.transaction_preview
                                        ?.amount_to_final
                                    }{' '}
                                    {preview.transaction_preview?.to_asset}
                                  </span>
                                </div>
                                <div>
                                  Отдаем:{' '}
                                  <span className="font-semibold text-red-600">
                                    -{preview.transaction_preview?.amount_from}{' '}
                                    {preview.transaction_preview?.from_asset}
                                  </span>
                                </div>
                              </>
                            ) : (
                              <>
                                <div>
                                  Получаем:{' '}
                                  <span className="font-semibold text-green-600">
                                    +{preview.transaction_preview?.amount_from}{' '}
                                    {preview.transaction_preview?.from_asset}
                                  </span>
                                </div>
                                <div>
                                  Отдаем:{' '}
                                  <span className="font-semibold text-red-600">
                                    -
                                    {
                                      preview.transaction_preview
                                        ?.amount_to_final
                                    }{' '}
                                    {preview.transaction_preview?.to_asset}
                                  </span>
                                </div>
                              </>
                            )}
                            <div>
                              Курс:{' '}
                              <span className="font-semibold">
                                {preview.transaction_preview?.rate_used}
                              </span>
                            </div>
                            <div>
                              Комиссия:{' '}
                              <span className="font-semibold text-orange-600">
                                {preview.transaction_preview?.fee_amount} (
                                {preview.transaction_preview?.fee_percent}%)
                              </span>
                            </div>
                          </div>

                          {preview.transaction_preview?.type ===
                            'crypto_to_fiat' &&
                            !preview.profit_analysis && (
                              <div className="mt-3 pt-2 border-t bg-gray-50 rounded p-2">
                                <div className="flex justify-between items-center">
                                  <span className="text-sm font-medium text-gray-700">
                                    Выручка от продажи:
                                  </span>
                                  <span className="font-bold text-lg text-blue-600">
                                    {
                                      preview.transaction_preview
                                        ?.amount_to_final
                                    }{' '}
                                    {preview.transaction_preview?.to_asset}
                                  </span>
                                </div>
                                <div className="text-xs text-gray-500 mt-1">
                                  Эффективный курс:{' '}
                                  {(
                                    preview.transaction_preview
                                      ?.amount_to_final /
                                    preview.transaction_preview?.amount_from
                                  ).toFixed(4)}{' '}
                                  {preview.transaction_preview?.to_asset}/
                                  {preview.transaction_preview?.from_asset}
                                </div>
                              </div>
                            )}
                        </div>

                        {/* Влияние на кассу */}
                        {preview.cash_impact && (
                          <div className="bg-white rounded p-3 space-y-2">
                            <h4 className="font-medium text-sm text-gray-700">
                              💼 Изменения в кассе
                            </h4>
                            <div className="space-y-1 text-xs">
                              {Object.entries(preview.cash_impact.changes).map(
                                ([asset, change]: [string, any]) => (
                                  <div
                                    key={asset}
                                    className="flex justify-between"
                                  >
                                    <span>{asset}:</span>
                                    <span
                                      className={`font-semibold ${
                                        change > 0
                                          ? 'text-green-600'
                                          : 'text-red-600'
                                      }`}
                                    >
                                      {change > 0 ? '+' : ''}
                                      {change} →{' '}
                                      {preview.cash_impact.new_balances[asset]}
                                    </span>
                                  </div>
                                )
                              )}
                            </div>
                          </div>
                        )}

                        {/* Анализ прибыли */}
                        {preview.profit_analysis ? (
                          <div className="bg-gradient-to-r from-green-50 to-blue-50 border-2 border-green-200 rounded-lg p-4 space-y-3">
                            <h4 className="font-semibold text-base text-gray-800 flex items-center gap-2">
                              💰 Прибыль от сделки
                              <span
                                className={`px-2 py-1 rounded-full text-xs font-bold ${
                                  preview.profit_analysis.realized_profit >= 0
                                    ? 'bg-green-100 text-green-800'
                                    : 'bg-red-100 text-red-800'
                                }`}
                              >
                                {preview.profit_analysis.realized_profit >= 0
                                  ? 'Прибыльная'
                                  : 'Убыточная'}
                              </span>
                            </h4>

                            {/* Основная информация о прибыли */}
                            <div className="bg-white rounded-lg p-3 border">
                              {/* Итоговая прибыль */}
                              <div className="mt-3 pt-3 border-t">
                                <div className="flex justify-between items-center">
                                  <span className="text-lg font-semibold text-gray-800">
                                    Чистая прибыль:
                                  </span>
                                  <div className="text-right">
                                    <div
                                      className={`text-xl font-bold ${
                                        preview.profit_analysis
                                          .realized_profit >= 0
                                          ? 'text-green-600'
                                          : 'text-red-600'
                                      }`}
                                    >
                                      {preview.profit_analysis
                                        .realized_profit >= 0
                                        ? '+'
                                        : ''}
                                      {preview.profit_analysis.realized_profit}{' '}
                                      {preview.profit_analysis.profit_currency}
                                    </div>
                                    {preview.profit_analysis
                                      .realized_profit_usdt && (
                                      <div className="text-sm text-gray-600">
                                        ≈{' '}
                                        {preview.profit_analysis
                                          .realized_profit_usdt >= 0
                                          ? '+'
                                          : ''}
                                        {preview.profit_analysis.realized_profit_usdt.toFixed(
                                          2
                                        )}{' '}
                                        USDT
                                      </div>
                                    )}
                                    {preview.profit_analysis.total_fiat_used >
                                      0 && (
                                      <div
                                        className={`text-sm font-semibold ${
                                          preview.profit_analysis
                                            .realized_profit >= 0
                                            ? 'text-green-500'
                                            : 'text-red-500'
                                        }`}
                                      ></div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div
                            className={`rounded-lg p-3 border ${
                              preview.transaction_preview?.type ===
                              'crypto_to_fiat'
                                ? 'bg-yellow-50 border-yellow-200'
                                : 'bg-blue-50 border-blue-200'
                            }`}
                          >
                            {preview.transaction_preview?.type ===
                            'crypto_to_fiat' ? (
                              <div>
                                <h4 className="font-medium text-sm text-yellow-700 mb-2 flex items-center gap-2">
                                  ⚠️ Нет данных для расчета прибыли
                                </h4>
                                <div className="space-y-2 text-xs">
                                  <p className="text-yellow-700">
                                    Для расчета прибыли от продажи{' '}
                                    <strong>
                                      {preview.transaction_preview?.from_asset}
                                    </strong>{' '}
                                    нужны фиат-лоты с историей покупки этой
                                    криптовалюты.
                                  </p>
                                  <div className="bg-yellow-100 rounded p-2">
                                    <p className="text-yellow-800 font-medium mb-1">
                                      💡 Что это значит:
                                    </p>
                                    <ul className="text-yellow-700 space-y-1">
                                      <li>
                                        • В системе нет записей о покупке{' '}
                                        {
                                          preview.transaction_preview
                                            ?.from_asset
                                        }
                                      </li>
                                      <li>
                                        • Прибыль нельзя рассчитать без
                                        себестоимости
                                      </li>
                                      <li>
                                        • Выручка:{' '}
                                        <strong>
                                          {
                                            preview.transaction_preview
                                              ?.amount_to_final
                                          }{' '}
                                          {
                                            preview.transaction_preview
                                              ?.to_asset
                                          }
                                        </strong>
                                      </li>
                                    </ul>
                                  </div>
                                  <p className="text-yellow-600 text-xs">
                                    <strong>Совет:</strong> Создайте фиат-лоты
                                    для{' '}
                                    {preview.transaction_preview?.from_asset} в
                                    разделе "Фиат Лоты" или используйте
                                    транзакции пополнения.
                                  </p>
                                </div>
                              </div>
                            ) : (
                              <div>
                                <h4 className="font-medium text-sm text-blue-700 mb-2">
                                  ℹ️ Пополнение криптовалютой
                                </h4>
                                <p className="text-xs text-blue-600">
                                  Это пополнение кассы криптовалютой. Прибыль
                                  будет рассчитана при продаже{' '}
                                  <strong>
                                    {preview.transaction_preview?.to_asset}
                                  </strong>
                                  .
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

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
