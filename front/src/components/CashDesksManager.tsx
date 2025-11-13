import React, { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { config } from '../config'
import { useAuth } from '../services/authService'

const API_BASE = config.apiBaseUrl

interface CashDesk {
  _id: string
  tenant_id: string
  name: string
  created_at: string
  is_active: boolean
}

interface CreateCashDeskData {
  name: string
}

export function CashDesksManager() {
  const [loading, setLoading] = useState(false)
  const [cashDesks, setCashDesks] = useState<CashDesk[]>([])
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newDeskName, setNewDeskName] = useState('')
  const [editingDesk, setEditingDesk] = useState<CashDesk | null>(null)
  const { authenticatedFetch } = useAuth()

  // Загрузка списка касс
  const loadCashDesks = async () => {
    setLoading(true)
    try {
      const res = await authenticatedFetch(`${API_BASE}/cash-desks/`)
      if (res.ok) {
        const data = await res.json()
        setCashDesks(data)
      } else {
        toast.error('Не удалось загрузить список касс')
      }
    } catch (error) {
      toast.error('Ошибка при загрузке касс')
    } finally {
      setLoading(false)
    }
  }

  // Создание новой кассы
  const createCashDesk = async () => {
    if (!newDeskName.trim()) {
      toast.error('Введите название кассы')
      return
    }

    setLoading(true)
    try {
      const res = await authenticatedFetch(`${API_BASE}/cash-desks/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: newDeskName.trim(),
        }),
      })

      if (res.ok) {
        toast.success('Касса успешно создана')
        setNewDeskName('')
        setShowCreateForm(false)
        loadCashDesks()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось создать кассу')
      }
    } catch (error) {
      toast.error('Ошибка при создании кассы')
    } finally {
      setLoading(false)
    }
  }

  // Обновление кассы
  const updateCashDesk = async (deskId: string, updates: Partial<CashDesk>) => {
    setLoading(true)
    try {
      const res = await authenticatedFetch(`${API_BASE}/cash-desks/${deskId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      })

      if (res.ok) {
        toast.success('Касса обновлена')
        setEditingDesk(null)
        loadCashDesks()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось обновить кассу')
      }
    } catch (error) {
      toast.error('Ошибка при обновлении кассы')
    } finally {
      setLoading(false)
    }
  }

  // Деактивация кассы
  const deactivateCashDesk = async (desk: CashDesk) => {
    if (
      !confirm(`Вы уверены что хотите деактивировать кассу "${desk.name}"?`)
    ) {
      return
    }

    setLoading(true)
    try {
      const res = await authenticatedFetch(
        `${API_BASE}/cash-desks/${desk._id}`,
        {
          method: 'DELETE',
        }
      )

      if (res.ok) {
        toast.success('Касса деактивирована')
        loadCashDesks()
      } else {
        const error = await res.json()
        toast.error(error.detail || 'Не удалось деактивировать кассу')
      }
    } catch (error) {
      toast.error('Ошибка при деактивации кассы')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCashDesks()
  }, [])

  return (
    <div className="space-y-6">
      {/* Заголовок и кнопка создания */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Управление Кассами</h2>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 font-medium"
          disabled={loading}
        >
          + Создать Кассу
        </button>
      </div>

      {/* Форма создания кассы */}
      {showCreateForm && (
        <div className="bg-gray-50 p-4 rounded-lg border">
          <h3 className="text-lg font-semibold mb-4">Создать новую кассу</h3>
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="block text-sm font-medium mb-2">
                Название кассы
              </label>
              <input
                type="text"
                value={newDeskName}
                onChange={(e) => setNewDeskName(e.target.value)}
                placeholder="Например: Прага, Украина, Главный офис"
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                onKeyDown={(e) => e.key === 'Enter' && createCashDesk()}
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={createCashDesk}
                disabled={loading}
                className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 font-medium disabled:opacity-50"
              >
                Создать
              </button>
              <button
                onClick={() => {
                  setShowCreateForm(false)
                  setNewDeskName('')
                }}
                className="px-4 py-2 bg-gray-300 text-gray-800 rounded-lg hover:bg-gray-400 font-medium"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Список касс */}
      <div className="bg-white rounded-lg border">
        <div className="p-4 border-b">
          <h3 className="text-lg font-semibold">Активные кассы</h3>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-500">Загрузка...</div>
        ) : cashDesks.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>У вас пока нет касс</p>
            <button
              onClick={() => setShowCreateForm(true)}
              className="mt-2 text-blue-500 hover:text-blue-600 font-medium"
            >
              Создать первую кассу
            </button>
          </div>
        ) : (
          <div className="divide-y">
            {cashDesks.map((desk) => (
              <div
                key={desk._id}
                className="p-4 flex items-center justify-between"
              >
                <div>
                  {editingDesk && editingDesk._id === desk._id ? (
                    <div className="flex gap-3 items-center">
                      <input
                        type="text"
                        value={editingDesk.name}
                        onChange={(e) =>
                          setEditingDesk({
                            ...editingDesk,
                            name: e.target.value,
                          })
                        }
                        className="px-3 py-1 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            updateCashDesk(desk._id, { name: editingDesk.name })
                          } else if (e.key === 'Escape') {
                            setEditingDesk(null)
                          }
                        }}
                      />
                      <button
                        onClick={() =>
                          updateCashDesk(desk._id, { name: editingDesk.name })
                        }
                        className="text-green-600 hover:text-green-800 font-medium"
                      >
                        ✓
                      </button>
                      <button
                        onClick={() => setEditingDesk(null)}
                        className="text-gray-600 hover:text-gray-800 font-medium"
                      >
                        ✕
                      </button>
                    </div>
                  ) : (
                    <div>
                      <h4 className="font-semibold text-lg">{desk.name}</h4>
                      <p className="text-sm text-gray-500">
                        ID: {desk._id} • Создано:{' '}
                        {new Date(desk.created_at).toLocaleDateString('ru-RU')}
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  {editingDesk && editingDesk._id === desk._id ? null : (
                    <>
                      <button
                        onClick={() => setEditingDesk(desk)}
                        className="px-3 py-1 text-blue-600 hover:bg-blue-50 rounded font-medium"
                      >
                        Редактировать
                      </button>
                      <button
                        onClick={() => deactivateCashDesk(desk)}
                        className="px-3 py-1 text-red-600 hover:bg-red-50 rounded font-medium"
                        disabled={loading}
                      >
                        Деактивировать
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Информация о фазе 2 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-800 mb-2">
          💡 Фаза 2: Система касс
        </h4>
        <p className="text-blue-700 text-sm">
          Теперь каждая касса работает независимо. Все транзакции, балансы и
          отчеты привязаны к конкретной кассе. Вы можете создать отдельные кассы
          для разных филиалов (например, "Прага", "Украина") и управлять ими
          раздельно.
        </p>
      </div>
    </div>
  )
}

export default CashDesksManager
