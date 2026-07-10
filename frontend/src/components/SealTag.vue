<template>
  <div class="seal" v-if="show">预警</div>
</template>

<script setup>
defineProps({ show: { type: Boolean, default: false } })
</script>

<style scoped>
.seal {
  width: 40px;
  height: 40px;
  border: 2px solid var(--cinnabar);
  border-radius: 6px;
  color: var(--cinnabar);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Noto Serif SC';
  font-weight: 900;
  font-size: 12px;
  letter-spacing: 1px;
  transform: rotate(-8deg);
  writing-mode: vertical-rl;
  background: rgba(168, 59, 46, 0.05);
  line-height: 1;
  flex-shrink: 0;
}
</style>