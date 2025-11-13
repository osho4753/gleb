import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react'
import { toast } from 'sonner'
import { config } from '../config'
import { useAuth } from './authService'

const API_BASE = config.apiBaseUrl

interface CashDesk {
  _id: string
  tenant_id: string
  name: string
  created_at: string
  is_active: boolean
}

interface CashDeskContextType {
  cashDesks: CashDesk[]
  selectedCashDesk: CashDesk | null
  selectedCashDeskId: string | null
  loadCashDesks: () => Promise<void>
  selectCashDesk: (deskId: string) => void
  selectNewlyCreatedCashDesk: (deskId: string) => void
  loading: boolean
  isAggregateView: boolean
  setAggregateView: (aggregate: boolean) => void
}

const CashDeskContext = createContext<CashDeskContextType | undefined>(
  undefined
)

interface CashDeskProviderProps {
  children: ReactNode
}

export function CashDeskProvider({ children }: CashDeskProviderProps) {
  const [cashDesks, setCashDesks] = useState<CashDesk[]>([])
  const [selectedCashDeskId, setSelectedCashDeskId] = useState<string | null>(
    localStorage.getItem('selectedCashDeskId')
  )
  const [loading, setLoading] = useState(false)
  const [isAggregateView, setIsAggregateView] = useState(false)
  const { authenticatedFetch, isAuthenticated } = useAuth()

  // Загрузка списка касс
  const loadCashDesks = async () => {
    if (!isAuthenticated) return

    setLoading(true)
    try {
      const res = await authenticatedFetch(`${API_BASE}/cash-desks/`)
      if (res.ok) {
        const data = await res.json()
        setCashDesks(data)

        // Если выбранной кассы нет в списке, выбираем первую доступную
        if (
          data.length > 0 &&
          (!selectedCashDeskId ||
            !data.find((d: CashDesk) => d._id === selectedCashDeskId))
        ) {
          selectCashDesk(data[0]._id)
        }
      } else {
        toast.error('Не удалось загрузить список касс')
      }
    } catch (error) {
      console.error('Error loading cash desks:', error)
      toast.error('Ошибка при загрузке касс')
    } finally {
      setLoading(false)
    }
  }

  // Выбор кассы
  const selectCashDesk = (deskId: string) => {
    setSelectedCashDeskId(deskId)
    setIsAggregateView(false)
    localStorage.setItem('selectedCashDeskId', deskId)
  }

  // Включение агрегированного вида
  const setAggregateView = (aggregate: boolean) => {
    setIsAggregateView(aggregate)
    if (aggregate) {
      setSelectedCashDeskId(null)
      localStorage.removeItem('selectedCashDeskId')
    } else if (cashDesks.length > 0) {
      // Возвращаемся к первой кассе если выходим из агрегированного вида
      selectCashDesk(cashDesks[0]._id)
    }
  }

  // Выбор новой созданной кассы
  const selectNewlyCreatedCashDesk = async (deskId: string) => {
    // Перезагружаем список касс чтобы включить новую
    await loadCashDesks()
    // Выбираем новую кассу
    selectCashDesk(deskId)
    toast.success('Новая касса выбрана и готова к использованию')
  }

  // Получение текущей выбранной кассы
  const selectedCashDesk = selectedCashDeskId
    ? cashDesks.find((desk) => desk._id === selectedCashDeskId) || null
    : null

  // Загрузка касс при аутентификации
  useEffect(() => {
    if (isAuthenticated) {
      loadCashDesks()
    }
  }, [isAuthenticated])

  const value: CashDeskContextType = {
    cashDesks,
    selectedCashDesk,
    selectedCashDeskId,
    loadCashDesks,
    selectCashDesk,
    selectNewlyCreatedCashDesk,
    loading,
    isAggregateView,
    setAggregateView,
  }

  return (
    <CashDeskContext.Provider value={value}>
      {children}
    </CashDeskContext.Provider>
  )
}

export function useCashDesk() {
  const context = useContext(CashDeskContext)
  if (context === undefined) {
    throw new Error('useCashDesk must be used within a CashDeskProvider')
  }
  return context
}

export type { CashDesk }
