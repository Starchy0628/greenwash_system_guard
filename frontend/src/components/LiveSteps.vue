<template>
  <div class="live-panel" :class="{ show: active }">
    <div v-for="(step, i) in steps" :key="i" class="live-step" :class="stepClass(i)">
      <div class="dot"></div>
      <span>{{ step }}</span>
    </div>
    <div v-if="progress" class="live-progress">
      {{ progress }}
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  active: { type: Boolean, default: false },
  currentStep: { type: Number, default: -1 },
  progress: { type: String, default: '' },
  steps: {
    type: Array,
    default: () => [
      '抓取企业最新披露文本（ESG报告 / 年报MD&A，就高原则）',
      '语句切分与环保相关性过滤',
      '三模型独立分类投票中',
      '语境情感打分 + 行业基准修正，合成GW指数',
    ],
  },
})

function stepClass(i) {
  if (i < props.currentStep) return 'done'
  if (i === props.currentStep) return 'active'
  return ''
}
</script>

<style scoped>
.live-panel {
  background: var(--ink-2);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 20px;
  display: none;
}
.live-panel.show { display: block; }

.live-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--paper-soft);
  opacity: .35;
}
.live-step.active { opacity: 1; color: var(--paper); }
.live-step.done { opacity: .7; color: var(--jade-dim); }

.live-step .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--paper-soft);
  flex-shrink: 0;
}
.live-step.active .dot { background: var(--gold); animation: pulse 1s infinite; }
.live-step.done .dot { background: var(--jade-dim); }

@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .3; } }

.live-progress {
  margin-top: 8px;
  font-size: 12px;
  color: var(--paper-soft);
  padding-left: 18px;
}
</style>