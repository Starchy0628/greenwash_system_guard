<template>
  <div class="result-card" :class="{ show: !!result }">
    <div class="result-top">
      <div>
        <div class="result-name">
          {{ result?.company_name }}
          <span class="result-code">{{ result?.stock_code }}</span>
        </div>
        <div class="result-industry">所属行业：{{ result?.industry }}</div>
      </div>
      <SealTag :show="isWarn" />
    </div>

    <div class="gw-big" :class="{ warn: isWarn }">
      {{ gwDisplay }}
      <span class="u">GW 指数</span>
    </div>

    <SentenceList
      :sentences="confirmedSentences"
      title="已确权语句"
    />

    <SentenceList
      :sentences="disputeSentences"
      title="待人工复核语句（三模型完全分歧）"
    />

    <TrendChart :data="trendData" />

    <div class="action-row">
      <button class="watch-btn" :class="{ watched: isWatched }" @click="$emit('toggleWatch')">
        {{ isWatched ? '✓ 已加入关注' : '+ 加入关注列表' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SealTag from './SealTag.vue'
import SentenceList from './SentenceList.vue'
import TrendChart from './TrendChart.vue'

const props = defineProps({
  result: { type: Object, default: null },
  isWatched: { type: Boolean, default: false },
})
defineEmits(['toggleWatch'])

const isWarn = computed(() => props.result?.risk_level === '预警')
const gwDisplay = computed(() => props.result?.gw_index?.toFixed(4) ?? '--')

const confirmedSentences = computed(() =>
  (props.result?.sentences || []).filter(s => !s.needs_review && s.final_category === 'substantive')
)
const disputeSentences = computed(() =>
  (props.result?.sentences || []).filter(s => s.needs_review)
)
const trendData = computed(() => props.result?.trend || [])
</script>

<style scoped>
.result-card {
  background: var(--paper);
  color: var(--ink);
  border-radius: var(--radius);
  padding: 24px;
  display: none;
}
.result-card.show { display: block; animation: fade .4s ease; }
@keyframes fade { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

.result-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
}
.result-name {
  font-family: 'Noto Serif SC';
  font-weight: 700;
  font-size: 20px;
}
.result-code {
  font-size: 13px;
  color: var(--ink-soft);
  font-weight: 400;
}
.result-industry {
  font-size: 12px;
  color: var(--ink-soft);
  margin-top: 2px;
}

.gw-big {
  font-family: 'Noto Serif SC';
  font-weight: 900;
  font-size: 38px;
  font-variant-numeric: tabular-nums;
  margin-top: 14px;
}
.gw-big.warn { color: var(--cinnabar); }

.gw-big .u {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-soft);
  margin-left: 8px;
}

.action-row { margin-top: 20px; }
.watch-btn {
  background: var(--jade);
  color: #fff;
  border: none;
  padding: 10px 18px;
  border-radius: 4px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  font-family: 'Noto Sans SC';
}
.watch-btn.watched { background: var(--jade-dim); }
.watch-btn:hover { opacity: .9; }
</style>