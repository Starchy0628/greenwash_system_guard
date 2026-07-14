<template>
  <div class="result-card" :class="{ show: !!result }">
    <div class="result-top">
      <div>
        <div class="result-name">
          {{ result?.company_name }}
          <span class="result-code">{{ result?.stock_code }}</span>
        </div>
        <div class="result-industry">
          所属行业：{{ result?.industry }}
          <span v-if="isSampleInsufficient" class="ref-tag" title="行业样本量不足30家，结果仅供参考">参考</span>
        </div>
      </div>
      <SealTag :show="isWarn" />
    </div>

    <div class="gw-big" :class="{ warn: isWarn }">
      {{ gwDisplay }}
      <span class="u">GW 指数</span>
    </div>

    <div class="metric-row">
      <div class="metric-item">
        <div class="mv">{{ result?.substantive_count ?? 0 }}</div>
        <div class="ml">已确权语句数</div>
      </div>
      <div class="metric-item">
        <div class="mv">{{ result?.env_sentences ?? 0 }}</div>
        <div class="ml">环境语句数</div>
      </div>
      <div class="metric-item">
        <div class="mv">{{ result?.dispute_count ?? 0 }}</div>
        <div class="ml">分歧语句数</div>
      </div>
      <div class="metric-item">
        <div class="mv">{{ result?.industry_sample_count ?? 0 }}</div>
        <div class="ml">行业样本量
          <span v-if="isSampleInsufficient" class="ref-dot" title="样本量不足30家"></span>
        </div>
      </div>
    </div>

    <SentenceList
      :sentences="envSentences"
      title="环境语句"
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
const isSampleInsufficient = computed(() => {
  const count = props.result?.industry_sample_count
  return count !== undefined && count !== null && count < 30
})

const envSentences = computed(() =>
  (props.result?.sentences || []).filter(s => s.final_category !== 'non_env')
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

.ref-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 600;
  color: var(--gold);
  background: rgba(200, 170, 100, 0.15);
  border: 1px solid rgba(200, 170, 100, 0.4);
  border-radius: 3px;
  vertical-align: middle;
  cursor: help;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin: 18px 0 20px;
  padding: 14px;
  background: var(--ink-soft-2);
  border-radius: var(--radius);
}
.metric-item { text-align: center; }
.metric-item .mv {
  font-family: 'Noto Serif SC';
  font-weight: 800;
  font-size: 20px;
  color: var(--jade);
  font-variant-numeric: tabular-nums;
}
.metric-item .ml {
  font-size: 11px;
  color: var(--ink-soft);
  margin-top: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
}
.ref-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gold);
  cursor: help;
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