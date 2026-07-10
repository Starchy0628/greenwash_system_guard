<template>
  <section class="block">
    <div class="block-head">
      <h2><span class="idx">TOP 10</span>当前风险最高企业</h2>
      <span class="note">按GW指数降序排列</span>
    </div>
    <div class="risk-grid">
      <Top10Card
        v-for="(c, i) in companies"
        :key="c.stock_code"
        :company="c"
        :rank="i + 1"
        @click="$emit('select', c)"
      />
    </div>
  </section>
</template>

<script setup>
import Top10Card from './Top10Card.vue'

defineProps({ companies: { type: Array, default: () => [] } })
defineEmits(['select'])
</script>

<style scoped>
.block { margin-bottom: 44px; }
.block-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 14px;
  gap: 12px;
  flex-wrap: wrap;
}
.block-head h2 {
  font-family: 'Noto Serif SC';
  font-weight: 700;
  font-size: 18px;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.block-head h2 .idx { color: var(--gold); font-size: 13px; font-weight: 500; letter-spacing: 1px; }
.block-head .note { font-size: 12px; color: var(--paper-soft); }

.risk-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}
</style>