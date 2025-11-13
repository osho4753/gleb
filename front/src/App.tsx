import { useState, useEffect } from 'react'
import { Toaster } from 'sonner'
import { Dashboard } from './components/Dashboard'
import { CashManager } from './components/CashManager'
import { TransactionsManager } from './components/TransactionsManager'
import { TransactionsHistory } from './components/TransactionsHistory'
import { FiatLotsViewer } from './components/FiatLotsViewer'
import { PnLMatches } from './components/PnLMatches'
import { LoginScreen } from './components/LoginScreen'
import { GoogleSheetsModal } from './components/GoogleSheetsModal'
import { GoogleSheetsIcon } from './components/GoogleSheetsIcon'
import { CashDesksManager } from './components/CashDesksManager'
import { CashDeskSelector } from './components/CashDeskSelector'
import { useAuth, TenantInfo } from './services/authService'
import { useCashDesk } from './services/cashDeskService'

export function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [isGoogleSheetsModalOpen, setIsGoogleSheetsModalOpen] = useState(false)
  const [tenantInfo, setTenantInfo] = useState<TenantInfo | null>(null)
  const { isAuthenticated, login, logout, getTenantInfo } = useAuth()

  useEffect(() => {
    if (isAuthenticated) {
      getTenantInfo()
        .then((info) => {
          setTenantInfo(info)
        })
        .catch((error) => {
          console.error('Ошибка загрузки информации о tenant:', error)
        })
    } else {
      setTenantInfo(null)
    }
  }, [isAuthenticated])

  // Если не аутентифицирован, показываем экран входа
  if (!isAuthenticated) {
    return <LoginScreen onLoginSuccess={login} />
  }

  return (
    <div className="w-full min-h-screen bg-gray-50">
      <Toaster position="top-right" />
      <div className="max-w-7xl mx-auto p-3 sm:p-6">
        <div className="flex justify-between items-center mb-4 sm:mb-6">
          <div>
            <div className="flex items-center gap-4 mb-2">
              <h1 className="text-2xl sm:text-3xl font-bold">
                Панель Обменника
              </h1>
              <CashDeskSelector />
            </div>
            {tenantInfo && (
              <p className="text-sm text-gray-600 mt-1">
                <span className="font-medium text-blue-600">
                  {tenantInfo.name}
                </span>
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* Google Sheets Icon */}
            <GoogleSheetsIcon
              onOpenModal={() => setIsGoogleSheetsModalOpen(true)}
            />

            {/* Logout Button */}
            <button
              onClick={logout}
              className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors flex items-center gap-2"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              Выйти
            </button>
          </div>
        </div>
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
              onClick={() => setActiveTab('cash-desks')}
              className={`px-3 sm:px-4 py-2 font-medium whitespace-nowrap text-sm sm:text-base ${
                activeTab === 'cash-desks'
                  ? 'border-b-2 border-blue-500 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Кассы
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
          {activeTab === 'cash-desks' && <CashDesksManager />}
          {activeTab === 'cash' && <CashManager />}
          {activeTab === 'transactions' && (
            <TransactionsManager
              onNavigateToHistory={() => setActiveTab('history')}
            />
          )}

          {activeTab === 'history' && <TransactionsHistory />}
          {activeTab === 'lots' && <FiatLotsViewer />}
          {activeTab === 'pnl' && <PnLMatches />}
        </div>
      </div>

      {/* Google Sheets Modal */}
      <GoogleSheetsModal
        isOpen={isGoogleSheetsModalOpen}
        onClose={() => setIsGoogleSheetsModalOpen(false)}
      />
    </div>
  )
}
