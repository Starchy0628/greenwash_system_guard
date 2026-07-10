import api from './request'

export const dashboardApi = {
  getTop10() { return api.get('/dashboard/top10').then(r => r.data) },
  getMetrics() { return api.get('/dashboard/metrics').then(r => r.data) },
}

export const companiesApi = {
  search(q) { return api.get('/companies/search', { params: { q } }).then(r => r.data) },
  getById(id) { return api.get(`/companies/${id}`).then(r => r.data) },
  getTrend(id) { return api.get(`/companies/${id}/trend`).then(r => r.data) },
}

export const watchlistApi = {
  get() { return api.get('/watchlist').then(r => r.data) },
  add(stockCode) { return api.post(`/watchlist/${stockCode}`).then(r => r.data) },
  remove(stockCode) { return api.delete(`/watchlist/${stockCode}`).then(r => r.data) },
}

