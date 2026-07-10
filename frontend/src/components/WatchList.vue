<template>
  <section class="block">
    <div class="block-head"><h2>我的关注列表</h2></div>

    <div v-if="!items.length" class="watch-empty">
      暂无关注 · 查询企业后可添加关注
    </div>

    <div v-else class="watch-list">
      <div
        v-for="item in items"
        :key="item.stock_code"
        class="watch-row"
        @click="$emit('select', item)"
      >
        <div class="left">
          <span class="star">★</span>
          <span class="cname">{{ item.company_name }}</span>
        </div>
        <div class="right">
          <span class="gw" :class="{ warn: item.latest_risk_level === '预警' }">
            {{ item.latest_gw_index?.toFixed(4) ?? '--' }}
          </span>
          <button class="remove-btn" @click.stop="$emit('remove', item.stock_code)" title="取消关注">×</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({ items: { type: Array, default: () => [] } })
defineEmits(['select', 'remove'])
</script>

<style scoped>
.block { margin-bottom: 44px; }
.block-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 14px;
}
.block-head h2 {
  font-family: 'Noto Serif SC';
  font-weight: 700;
  font-size: 18px;
  margin: 0;
}

.watch-empty {
  border: 1px dashed var(--line-soft);
  border-radius: var(--radius);
  padding: 22px;
  text-align: center;
  color: var(--paper-soft);
  font-size: 13px;
}

.watch-list { display: flex; flex-direction: column; gap: 8px; }
.watch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--ink-2);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius);
  padding: 12px 16px;
  cursor: pointer;
}
.watch-row:hover { border-color: var(--jade-dim); }

.left { display: flex; align-items: center; gap: 12px; }
.star { color: var(--gold); }
.cname { font-weight: 600; font-size: 14px; }

.right { display: flex; align-items: center; gap: 12px; }
.gw {
  font-variant-numeric: tabular-nums;
  font-size: 14px;
  color: var(--paper-soft);
}
.gw.warn { color: var(--cinnabar); }

.remove-btn {
  background: none;
  border: 1px solid var(--line-soft);
  color: var(--paper-soft);
  width: 24px;
  height: 24px;
  border-radius: 12px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.remove-btn:hover {
  border-color: var(--cinnabar);
  color: var(--cinnabar);
}
</style>