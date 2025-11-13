/**
 * Адаптер API для постепенной миграции с v1 на v2
 * Обеспечивает обратную совместимость и плавный переход
 */

import { config } from '../config'

const API_BASE = config.apiBaseUrl

/**
 * Конфигурация адаптера API
 */
interface ApiAdapterConfig {
  useV2ForReads: boolean // Использовать v2 для операций чтения
  useV2ForWrites: boolean // Использовать v2 для операций записи
  fallbackToV1: boolean // Откат на v1 при ошибке v2
}

/**
 * Адаптер для работы с API v1/v2
 */
class ApiAdapter {
  public config: ApiAdapterConfig

  constructor(config: Partial<ApiAdapterConfig> = {}) {
    this.config = {
      useV2ForReads: false, // По умолчанию используем v1 для чтения
      useV2ForWrites: false, // По умолчанию используем v1 для записи
      fallbackToV1: true, // Включен откат на v1
      ...config,
    }
  }

  /**
   * Обновить конфигурацию адаптера
   */
  updateConfig(newConfig: Partial<ApiAdapterConfig>) {
    this.config = { ...this.config, ...newConfig }
  }

  /**
   * Получить статус кассы
   */
  async getCashDeskStatus(cashDeskId: string, authenticatedFetch: Function) {
    if (this.config.useV2ForReads) {
      try {
        const v2Response = await authenticatedFetch(
          `${API_BASE}/v2/cash-desks/${cashDeskId}/status`
        )
        if (v2Response.ok) {
          const data = await v2Response.json()

          // Адаптируем формат v2 к v1 для совместимости
          const v1CompatibleData = {
            cash: data.assets.reduce((acc: any, asset: any) => {
              acc[asset.asset] = asset.balance
              return acc
            }, {}),
            cash_desk_id: data.cash_desk_id,
            cash_desk_name: data.cash_desk_name,
          }

          return { ok: true, json: () => Promise.resolve(v1CompatibleData) }
        }
      } catch (error) {
        console.warn('V2 API failed, falling back to V1:', error)
      }
    }

    // Fallback или основной путь для v1
    return authenticatedFetch(
      `${API_BASE}/cash/status?cash_desk_id=${cashDeskId}`
    )
  }

  /**
   * Получить агрегированный статус для tenant
   */
  async getAggregateStatus(authenticatedFetch: Function) {
    if (this.config.useV2ForReads) {
      try {
        const v2Response = await authenticatedFetch(
          `${API_BASE}/v2/tenant/status/aggregate`
        )
        if (v2Response.ok) {
          const data = await v2Response.json()

          // Адаптируем формат v2 к v1
          const v1CompatibleData = {
            cash: data.aggregated_assets.reduce((acc: any, asset: any) => {
              acc[asset.asset] = asset.total_balance
              return acc
            }, {}),
            cash_desks: data.cash_desks,
          }

          return { ok: true, json: () => Promise.resolve(v1CompatibleData) }
        }
      } catch (error) {
        console.warn('V2 API failed, falling back to V1:', error)
      }
    }

    return authenticatedFetch(`${API_BASE}/cash/status`)
  }

  /**
   * Получить транзакции кассы
   */
  async getTransactions(cashDeskId: string, authenticatedFetch: Function) {
    if (this.config.useV2ForReads) {
      try {
        const v2Response = await authenticatedFetch(
          `${API_BASE}/v2/cash-desks/${cashDeskId}/transactions`
        )
        if (v2Response.ok) {
          const data = await v2Response.json()

          // V2 возвращает объект с дополнительной информацией, берем только транзакции
          return { ok: true, json: () => Promise.resolve(data.transactions) }
        }
      } catch (error) {
        console.warn('V2 API failed, falling back to V1:', error)
      }
    }

    return authenticatedFetch(
      `${API_BASE}/transactions?cash_desk_id=${cashDeskId}`
    )
  }

  /**
   * Получить фиатные лоты по валюте
   */
  async getFiatLotsByCurrency(
    currency: string,
    cashDeskId: string,
    authenticatedFetch: Function
  ) {
    if (this.config.useV2ForReads) {
      try {
        const v2Response = await authenticatedFetch(
          `${API_BASE}/v2/cash-desks/${cashDeskId}/fiat-lots/${currency}`
        )
        if (v2Response.ok) {
          return v2Response
        }
      } catch (error) {
        console.warn('V2 API failed, falling back to V1:', error)
      }
    }

    return authenticatedFetch(
      `${API_BASE}/transactions/fiat-lots/${currency}?cash_desk_id=${cashDeskId}`
    )
  }

  /**
   * Получить PnL матчи
   */
  async getPnLMatches(cashDeskId: string, authenticatedFetch: Function) {
    if (this.config.useV2ForReads) {
      try {
        const v2Response = await authenticatedFetch(
          `${API_BASE}/v2/cash-desks/${cashDeskId}/pnl-matches`
        )
        if (v2Response.ok) {
          const data = await v2Response.json()

          // Адаптируем к формату v1
          return {
            ok: true,
            json: () => Promise.resolve({ matches: data.matches }),
          }
        }
      } catch (error) {
        console.warn('V2 API failed, falling back to V1:', error)
      }
    }

    return authenticatedFetch(
      `${API_BASE}/transactions/pnl-matches?cash_desk_id=${cashDeskId}`
    )
  }

  /**
   * Создать транзакцию
   */
  async createTransaction(
    transactionData: any,
    cashDeskId: string,
    authenticatedFetch: Function
  ) {
    if (this.config.useV2ForWrites) {
      try {
        const v2Response = await authenticatedFetch(
          `${API_BASE}/v2/cash-desks/${cashDeskId}/transactions`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(transactionData),
          }
        )

        if (v2Response.ok) {
          return v2Response
        }
      } catch (error) {
        console.warn('V2 API failed, falling back to V1:', error)
      }
    }

    // Fallback на v1
    return authenticatedFetch(
      `${API_BASE}/transactions?cash_desk_id=${cashDeskId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(transactionData),
      }
    )
  }

  /**
   * Пополнить кассу
   */
  async depositToCashDesk(
    depositData: any,
    cashDeskId: string,
    authenticatedFetch: Function
  ) {
    if (this.config.useV2ForWrites) {
      try {
        const v2Response = await authenticatedFetch(
          `${API_BASE}/v2/cash-desks/${cashDeskId}/deposit`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(depositData),
          }
        )

        if (v2Response.ok) {
          return v2Response
        }
      } catch (error) {
        console.warn('V2 API failed, falling back to V1:', error)
      }
    }

    return authenticatedFetch(
      `${API_BASE}/cash/deposit?cash_desk_id=${cashDeskId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(depositData),
      }
    )
  }

  /**
   * Вывести из кассы
   */
  async withdrawFromCashDesk(
    withdrawalData: any,
    cashDeskId: string,
    authenticatedFetch: Function
  ) {
    if (this.config.useV2ForWrites) {
      try {
        const v2Response = await authenticatedFetch(
          `${API_BASE}/v2/cash-desks/${cashDeskId}/withdrawal`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(withdrawalData),
          }
        )

        if (v2Response.ok) {
          return v2Response
        }
      } catch (error) {
        console.warn('V2 API failed, falling back to V1:', error)
      }
    }

    return authenticatedFetch(
      `${API_BASE}/cash/withdrawal?cash_desk_id=${cashDeskId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(withdrawalData),
      }
    )
  }
}

// Создаем глобальный экземпляр адаптера
export const apiAdapter = new ApiAdapter()

// Функции для постепенной миграции
export const migrationHelpers = {
  /**
   * Включить V2 для операций чтения
   */
  enableV2ForReads() {
    apiAdapter.updateConfig({ useV2ForReads: true })
    console.log('✅ V2 API enabled for read operations')
  },

  /**
   * Включить V2 для операций записи
   */
  enableV2ForWrites() {
    apiAdapter.updateConfig({ useV2ForWrites: true })
    console.log('✅ V2 API enabled for write operations')
  },

  /**
   * Полная миграция на V2
   */
  enableFullV2() {
    apiAdapter.updateConfig({
      useV2ForReads: true,
      useV2ForWrites: true,
      fallbackToV1: false,
    })
    console.log('✅ Full V2 API migration completed')
  },

  /**
   * Откат на V1
   */
  rollbackToV1() {
    apiAdapter.updateConfig({
      useV2ForReads: false,
      useV2ForWrites: false,
      fallbackToV1: true,
    })
    console.log('⬅️ Rolled back to V1 API')
  },
}
