import { useState } from 'react'
import { Toaster } from 'sonner'
import { Dashboard } from './components/Dashboard'
import { CashManager } from './components/CashManager'
import { TransactionsManager } from './components/TransactionsManager'
import { TransactionsHistory } from './components/TransactionsHistory'
export function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  return (
    <div className="w-full min-h-screen bg-gray-50">
      <Toaster position="top-right" />
      <div className="max-w-7xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">Панель Обменника</h1>
        <div className="flex gap-2 mb-6 border-b">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`px-4 py-2 font-medium ${
              activeTab === 'dashboard'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Обзор
          </button>
          <button
            onClick={() => setActiveTab('cash')}
            className={`px-4 py-2 font-medium ${
              activeTab === 'cash'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Управление Кассой
          </button>
          <button
            onClick={() => setActiveTab('transactions')}
            className={`px-4 py-2 font-medium ${
              activeTab === 'transactions'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Транзакции
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2 font-medium ${
              activeTab === 'history'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            История
          </button>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          {activeTab === 'dashboard' && <Dashboard />}
          {activeTab === 'cash' && <CashManager />}
          {activeTab === 'transactions' && (
            <TransactionsManager
              onNavigateToHistory={() => setActiveTab('history')}
            />
          )}
          {activeTab === 'history' && <TransactionsHistory />}
        </div>
      </div>
    </div>
  )
}
