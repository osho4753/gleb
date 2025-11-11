import { useState } from 'react'
import { Toaster } from 'sonner'
import { Dashboard } from './components/Dashboard'
import { CashManager } from './components/CashManager'
import { TransactionsManager } from './components/TransactionsManager'
import { TransactionsHistory } from './components/TransactionsHistory'
import { FiatLotsManager } from './components/FiatLotsManager'
import { PnLMatches } from './components/PnLMatches'
export function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  return (
    <div className="w-full min-h-screen bg-gray-50">
      <Toaster position="top-right" />
      <div className="max-w-7xl mx-auto p-3 sm:p-6">
        <h1 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6">
          Панель Обменника
        </h1>
        <div className="mb-6 border-b">
          <div className="flex gap-1 sm:gap-2 overflow-x-auto scrollbar-hide">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`px-3 sm:px-4 py-2 font-medium whitespace-nowrap text-sm sm:text-base ${
                activeTab === 'dashboard'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Обзор
            </button>
            <button
              onClick={() => setActiveTab('cash')}
              className={`px-3 sm:px-4 py-2 font-medium whitespace-nowrap text-sm sm:text-base ${
                activeTab === 'cash'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Управление Кассой
            </button>
            <button
              onClick={() => setActiveTab('transactions')}
              className={`px-3 sm:px-4 py-2 font-medium whitespace-nowrap text-sm sm:text-base ${
                activeTab === 'transactions'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Транзакции
            </button>

            <button
              onClick={() => setActiveTab('history')}
              className={`px-3 sm:px-4 py-2 font-medium whitespace-nowrap text-sm sm:text-base ${
                activeTab === 'history'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              История
            </button>

            <button
              onClick={() => setActiveTab('lots')}
              className={`px-3 sm:px-4 py-2 font-medium whitespace-nowrap text-sm sm:text-base ${
                activeTab === 'lots'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Фиат Лоты
            </button>

            <button
              onClick={() => setActiveTab('pnl')}
              className={`px-3 sm:px-4 py-2 font-medium whitespace-nowrap text-sm sm:text-base ${
                activeTab === 'pnl'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              PnL Матчи
            </button>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-3 sm:p-6">
          {activeTab === 'dashboard' && <Dashboard />}
          {activeTab === 'cash' && <CashManager />}
          {activeTab === 'transactions' && (
            <TransactionsManager
              onNavigateToHistory={() => setActiveTab('history')}
            />
          )}

          {activeTab === 'history' && <TransactionsHistory />}
          {activeTab === 'lots' && <FiatLotsManager />}
          {activeTab === 'pnl' && <PnLMatches />}
        </div>
      </div>
    </div>
  )
}
