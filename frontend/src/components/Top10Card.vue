<template>
  <div class="risk-card" @click="$emit('click')">
    <SealTag :show="isWarn" />
    <div class="rank">NO.{{ rank }}</div>
    <div class="cname">{{ company.company_name }}</div>
    <div class="gw" :class="{ warn: isWarn }">{{ gwDisplay }}</div>
    <div class="gw-label">GW INDEX</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SealTag from './SealTag.vue'

const props = defineProps({
  company: { type: Object, required: true },
  rank: { type: Number, required: true },
})
defineEmits(['click'])

const isWarn = computed(() => props.company.risk_level === '预警')
const gwDisplay = computed(() => props.company.gw_index?.toFixed(4) ?? '--')
</script>

<style scoped>
.risk-card {
  position: relative;
  background: var(--paper);
  color: var(--ink);
  border-radius: var(--radius);
  padding: 16px 14px 14px;
  cursor: pointer;
  transition: transform .2s ease, box-shadow .2s ease;
}
.risk-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(0,0,0,.25);
}
.rank {
  font-size: 11px;
  color: var(--ink-soft);
  font-weight: 600;
  margin-bottom: 8px;
  font-variant-numeric: tabular-nums;
}
.cname {
  font-family: 'Noto Serif SC';
  font-weight: 700;
  font-size: 15px;
  line-height: 1.3;
  margin-bottom: 10px;
  min-height: 39px;
}
.gw {
  font-family: 'Noto Serif SC';
  font-weight: 900;
  font-size: 22px;
  font-variant-numeric: tabular-nums;
}
.gw.warn { color: var(--cinnabar); }
.gw-label {
  font-size: 10px;
  color: var(--ink-soft);
  letter-spacing: 1px;
  margin-top: 2px;
}
</style>