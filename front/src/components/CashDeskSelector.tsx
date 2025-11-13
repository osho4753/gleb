import React, { useState } from 'react'
import { useCashDesk } from '../services/cashDeskService'

export function CashDeskSelector() {
  const {
    cashDesks,
    selectedCashDesk,
    selectCashDesk,
    isAggregateView,
    setAggregateView,
    loading,
  } = useCashDesk()

  const [dropdownOpen, setDropdownOpen] = useState(false)

  if (loading) {
    return <div className="text-sm text-gray-500">Загрузка касс...</div>
  }

  if (cashDesks.length === 0) {
    return (
      <div className="text-sm text-red-600 font-medium">
        ⚠️ Нет доступных касс
      </div>
    )
  }

  const handleSelect = (deskId: string | 'aggregate') => {
    if (deskId === 'aggregate') {
      setAggregateView(true)
    } else {
      selectCashDesk(deskId)
    }
    setDropdownOpen(false)
  }

  const currentDisplayName = isAggregateView
    ? 'Общий отчет (все кассы)'
    : selectedCashDesk
    ? selectedCashDesk.name
    : 'Выберите кассу'

  return (
    <div className="relative">
      <button
        onClick={() => setDropdownOpen(!dropdownOpen)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg border font-medium text-sm transition-colors ${
          selectedCashDesk || isAggregateView
            ? 'bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100'
            : 'bg-red-50 border-red-200 text-red-700 hover:bg-red-100'
        }`}
      >
        <span className="text-lg">{isAggregateView ? '📊' : '🏪'}</span>
        <span className="max-w-[200px] truncate">{currentDisplayName}</span>
        <svg
          className={`w-4 h-4 transition-transform ${
            dropdownOpen ? 'rotate-180' : ''
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
      </button>

      {dropdownOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
          <div className="p-2 space-y-1">
            {/* Агрегированный вид */}
            <button
              onClick={() => handleSelect('aggregate')}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 ${
                isAggregateView
                  ? 'bg-blue-100 text-blue-700 font-medium'
                  : 'hover:bg-gray-100 text-gray-700'
              }`}
            >
              <span className="text-lg">📊</span>
              <div>
                <div className="font-medium">Общий отчет</div>
                <div className="text-xs text-gray-500">Все кассы вместе</div>
              </div>
            </button>

            {/* Разделитель */}
            <hr className="border-gray-200" />

            {/* Отдельные кассы */}
            <div className="text-xs text-gray-500 px-3 py-1 font-medium">
              КАССЫ:
            </div>

            {cashDesks.map((desk) => (
              <button
                key={desk._id}
                onClick={() => handleSelect(desk._id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center gap-2 ${
                  selectedCashDesk &&
                  selectedCashDesk._id === desk._id &&
                  !isAggregateView
                    ? 'bg-blue-100 text-blue-700 font-medium'
                    : 'hover:bg-gray-100 text-gray-700'
                }`}
              >
                <span className="text-lg">🏪</span>
                <div>
                  <div className="font-medium">{desk.name}</div>
                  <div className="text-xs text-gray-500">
                    ID: {desk._id.slice(-6)}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Overlay для закрытия дропдауна */}
      {dropdownOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setDropdownOpen(false)}
        />
      )}
    </div>
  )
}

export default CashDeskSelector
