<template>
  <section id="query-block" class="block">
    <!-- 模式切换 -->
    <div class="mode-tabs">
      <button :class="{ active: mode === 'single' }" @click="mode = 'single'">
        单企业查询
      </button>
      <button :class="{ active: mode === 'pdf' }" @click="mode = 'pdf'">
        PDF 上传
      </button>
    </div>

    <!-- 单企业查询模式 -->
    <template v-if="mode === 'single'">
      <div class="search-row">
        <input
          v-model="query"
          @keyup.enter="doSearch()"
          type="text"
          placeholder="输入股票代码或企业名称，如 贵州茅台 / 600519"
        />
        <button @click="doSearch()" :disabled="searching">
          {{ searching ? '查询中...' : '查询' }}
        </button>
      </div>
      <div class="search-hint">
        已在库企业将直接返回结果；试试输入 <code>示例新能源科技</code> 体验现场实时分析流程
      </div>

      <ToastNotification
        :message="toast.message"
        :type="toast.type"
        :visible="toast.visible"
        @done="toast = { message: '', visible: false }"
      />

      <LiveSteps
        :active="liveActive"
        :current-step="liveStep"
      />

      <div v-if="isCached && currentResult && !liveActive" class="cached-notice">
        <span>当前显示为数据库缓存结果</span>
        <button class="refresh-btn" @click="refreshAnalysis" :disabled="searching">
          {{ searching ? '拉取中...' : '拉取最新一期' }}
        </button>
      </div>

      <ResultCard
        :result="currentResult"
        :is-watched="isWatched"
        @toggle-watch="toggleWatch"
      />
    </template>

    <!-- PDF 上传模式 -->
    <template v-if="mode === 'pdf'">
      <PdfUpload />
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useWatchlistStore } from '../stores/watchlist'
import { dashboardApi, companiesApi } from '../api'
import LiveSteps from './LiveSteps.vue'
import ResultCard from './ResultCard.vue'
import ToastNotification from './ToastNotification.vue'
import PdfUpload from './PdfUpload.vue'

const watchlistStore = useWatchlistStore()
const mode = ref('single')
const query = ref('')
const searching = ref(false)
const liveActive = ref(false)
const liveStep = ref(-1)
const currentResult = ref(null)
const isCached = ref(false)
const currentStockCode = ref('')
const toast = ref({ message: '', type: 'info', visible: false })
const isWatched = computed(() =>
  currentResult.value
    ? watchlistStore.isWatched(currentResult.value.company_id)
    : false
)

function showToast(message, type = 'info') {
  toast.value = { message, type, visible: true }
}

async function doSearch(forceRefresh = false) {
  const q = query.value.trim()
  if (!q) {
    showToast('请输入股票代码或企业名称', 'error')
    return
  }

  searching.value = true
  liveActive.value = true
  liveStep.value = -1
  currentResult.value = null
  isCached.value = false

  try {
    const results = await companiesApi.search(q)
    if (!results.length) {
      showToast('查询错误：未找到该企业，请确认是否为A股上市公司', 'error')
      searching.value = false
      liveActive.value = false
      return
    }
    const found = results[0]
    currentStockCode.value = found.stock_code
    await streamAnalysis(found.stock_code, forceRefresh)
  } catch (err) {
    console.error(err)
    showToast('查询失败，请重试', 'error')
    searching.value = false
    liveActive.value = false
  }
}

async function streamAnalysis(stockCode, forceRefresh = false) {
  let eventSource = null

  try {
    const url = new URL(`/api/analysis/stream`, window.location.origin)
    url.searchParams.set('stock_code', stockCode)
    url.searchParams.set('force_refresh', forceRefresh ? 'true' : 'false')
    eventSource = new EventSource(url.href)

    eventSource.addEventListener('status', (e) => {
      const data = JSON.parse(e.data)
      liveStep.value = stepIndex[data.phase] ?? -1
    })

    eventSource.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data)
      liveStep.value = 2
    })

    eventSource.addEventListener('result', (e) => {
      const data = JSON.parse(e.data)
      currentResult.value = data.result
      isCached.value = data.cached === true
      if (data.cached) showToast('已从数据库加载结果', 'info')
      liveActive.value = false
      searching.value = false
      eventSource.close()
    })

    eventSource.addEventListener('analysis_error', (e) => {
      try {
        const data = JSON.parse(e.data)
        showToast(data.message, 'error')
        if (!data.retryable) {
          liveActive.value = false
          searching.value = false
          eventSource.close()
        }
      } catch (err) {
        showToast('网络连接错误', 'error')
        searching.value = false
        liveActive.value = false
        eventSource.close()
      }
    })

    eventSource.onerror = () => {
      showToast('网络连接错误', 'error')
      searching.value = false
      liveActive.value = false
      eventSource.close()
    }
  } catch (err) {
    console.error(err)
    showToast('打开分析连接失败', 'error')
    searching.value = false
    liveActive.value = false
    if (eventSource) eventSource.close()
  }
}

const stepIndex = { checking: 0, fetching: 1, segmenting: 2, classifying: 3, voting: 4, scoring: 4 }

function toggleWatch() {
  if (!currentResult.value) return
  const id = currentResult.value.company_id
  const stockCode = currentResult.value.stock_code
  if (watchlistStore.isWatched(id)) {
    watchlistStore.remove(stockCode)
    showToast('已取消关注')
  } else {
    watchlistStore.add(stockCode)
    showToast('已加入关注列表')
  }
}

function refreshAnalysis() {
  if (!currentStockCode.value) return
  isCached.value = false
  doSearch(true)
}

onMounted(() => {
  watchlistStore.fetch()
})

// 暴露给父组件：点击 Top10 卡片 / 关注列表后自动填入并搜索
defineExpose({
  searchByKeyword(keyword) {
    query.value = keyword
    doSearch()
  }
})
</script>

<style scoped>
#query-block { margin-bottom: 40px; }

.mode-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 18px;
  border: 1px solid var(--line-soft);
  border-radius: var(--radius);
  overflow: hidden;
  width: fit-content;
}
.mode-tabs button {
  background: var(--ink-2);
  color: var(--paper-soft);
  border: none;
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: 'Noto Sans SC';
  transition: background .2s;
}
.mode-tabs button.active {
  background: var(--jade);
  color: #fff;
}
.mode-tabs button:not(.active):hover {
  background: rgba(47, 111, 98, 0.3);
}
.search-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.search-row input {
  flex: 1;
  background: var(--paper);
  color: var(--ink);
  border: none;
  border-radius: var(--radius);
  padding: 15px 16px;
  font-size: 15px;
  font-family: 'Noto Sans SC';
}
.search-row button {
  background: var(--gold);
  color: var(--ink);
  border: none;
  border-radius: var(--radius);
  padding: 0 22px;
  font-weight: 700;
  cursor: pointer;
  font-size: 13px;
}
.search-row button:disabled { opacity: .6; cursor: not-allowed; }
.search-hint {
  font-size: 11.5px;
  color: var(--paper-soft);
  margin-bottom: 18px;
}
.search-hint code {
  background: var(--ink-2);
  padding: 1px 6px;
  border-radius: 3px;
  color: var(--gold);
}

.cached-notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--ink-2);
  border: 1px solid var(--jade-dim);
  border-radius: var(--radius);
  padding: 12px 16px;
  margin-bottom: 18px;
  font-size: 13px;
  color: var(--paper-soft);
}
.refresh-btn {
  background: var(--jade);
  color: #fff;
  border: none;
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: 'Noto Sans SC';
  white-space: nowrap;
}
.refresh-btn:hover { background: var(--jade-dim); }
.refresh-btn:disabled { opacity: .6; cursor: not-allowed; }
</style>