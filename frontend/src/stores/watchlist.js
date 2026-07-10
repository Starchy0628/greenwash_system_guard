import { defineStore } from 'pinia'
import { watchlistApi } from '../api'

export const useWatchlistStore = defineStore('watchlist', {
  state: () => ({
    items: [],
    loading: false,
  }),
  actions: {
    async fetch() {
      this.loading = true
      try {
        this.items = await watchlistApi.get()
      } finally {
        this.loading = false
      }
    },
    async add(stockCode) {
      await watchlistApi.add(stockCode)
      await this.fetch()
    },
    async remove(stockCode) {
      await watchlistApi.remove(stockCode)
      await this.fetch()
    },
    isWatched(companyId) {
      return this.items.some(i => i.company_id === companyId)
    }
  }
})