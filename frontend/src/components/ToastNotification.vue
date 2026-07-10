<template>
  <div class="toast" :class="{ show: visible, error: type === 'error' }">{{ message }}</div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  message: { type: String, default: '' },
  type: { type: String, default: 'info' },
  duration: { type: Number, default: 2500 },
})
const emit = defineEmits(['done'])
const visible = ref(false)

watch(() => props.message, (val) => {
  if (val) {
    visible.value = true
    setTimeout(() => {
      visible.value = false
      emit('done')
    }, props.duration)
  }
})
</script>

<style scoped>
.toast {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--jade);
  color: #fff;
  padding: 10px 24px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  z-index: 100;
  opacity: 0;
  transition: opacity .3s ease;
  pointer-events: none;
}
.toast.show { opacity: 1; }
.toast.error { background: var(--cinnabar); }
</style>