<template>
  <div class="app">
    <AppHeader />
    <QuerySection ref="queryRef" />
    <Top10Grid
      :companies="top10"
      @select="handleSelect"
    />
    <WatchList
      :items="watchlistStore.items"
      @select="handleSelect"
      @remove="handleRemoveWatch"
    />
    <GradingRule />
    <MethodSteps />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { dashboardApi } from './api'
import { useWatchlistStore } from './stores/watchlist'
import {
  AppHeader,
  QuerySection,
  Top10Grid,
  WatchList,
  GradingRule,
  MethodSteps,
} from './components'

const watchlistStore = useWatchlistStore()
const queryRef = ref(null)
const top10 = ref([])

async function fetchTop10() {
  try {
    top10.value = await dashboardApi.getTop10()
  } catch (err) {
    console.error('Failed to load top10:', err)
  }
}

function handleSelect(company) {
  // 滚动到查询区顶部
  const queryBlock = document.getElementById('query-block')
  if (queryBlock) {
    queryBlock.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  // 自动填入股票代码并触发查询
  if (queryRef.value && company.stock_code) {
    queryRef.value.searchByKeyword(company.stock_code)
  }
}

async function handleRemoveWatch(stockCode) {
  await watchlistStore.fetch()
}

onMounted(() => {
  fetchTop10()
  watchlistStore.fetch()
})
</script>

<style scoped>
.app {
  max-width: 1040px;
  margin: 0 auto;
  padding: 0 24px 80px;
}
</style>