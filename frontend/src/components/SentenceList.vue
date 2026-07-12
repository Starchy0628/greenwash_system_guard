<template>
  <div class="sent-group">
    <h4>{{ title }}</h4>
    <div v-if="!sentences.length" class="empty">暂无</div>
    <template v-else>
      <div
        v-for="(s, i) in visibleSentences"
        :key="i"
        class="sent-item"
        :class="{ dispute: s.needs_review, open: s._open }"
        @click="toggleExpand(s)"
      >
        <span class="tag">{{ s.needs_review ? '待复核' : labelMap[s.final_category] || s.final_category }}</span>
        {{ s.sentence_text }}
        <div class="sent-detail" v-if="s._open">
          <div>DeepSeek-R1: {{ s.deepseek_result }}</div>
          <div>Qwen-3: {{ s.qwen_result }}</div>
          <div>GLM-OCR: {{ s.glm_result }}</div>
          <div v-if="s.sentiment_score !== null && s.sentiment_score !== undefined">情感评分: {{ s.sentiment_score?.toFixed(2) }}</div>
        </div>
      </div>
      <div v-if="sentences.length > 5" class="toggle-btn" @click="expanded = !expanded">
        {{ expanded ? '收起' : `展开全部（${sentences.length} 条）` }}
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  sentences: { type: Array, default: () => [] },
  title: { type: String, default: '语句清单' },
})

const labelMap = { substantive: '实质性', descriptive: '描述性', non_env: '非环保', non_environmental: '非环保' }
const expanded = ref(false)

const visibleSentences = computed(() => {
  if (expanded.value) return props.sentences
  return props.sentences.slice(0, 5)
})

function toggleExpand(s) {
  s._open = !s._open
}
</script>

<style scoped>
.sent-group { margin-top: 22px; }
.sent-group h4 {
  font-size: 12.5px;
  letter-spacing: 1px;
  color: var(--ink-soft);
  text-transform: uppercase;
  margin-bottom: 8px;
  font-weight: 700;
}
.empty { font-size: 13px; color: var(--ink-soft); padding: 8px 0; }

.sent-item {
  border-top: 1px solid var(--line);
  padding: 10px 0;
  font-size: 13.5px;
  line-height: 1.6;
  cursor: pointer;
}
.sent-item .tag {
  display: inline-block;
  font-size: 10.5px;
  padding: 1px 7px;
  border-radius: 8px;
  margin-right: 8px;
  background: var(--jade);
  color: #fff;
  font-weight: 600;
  vertical-align: middle;
}
.sent-item.dispute .tag { background: var(--cinnabar); }

.sent-detail {
  display: none;
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(0,0,0,.04);
  border-radius: 4px;
  font-size: 12px;
  color: var(--ink-soft);
}
.sent-item.open .sent-detail { display: block; }

.toggle-btn {
  margin-top: 10px;
  font-size: 12.5px;
  color: var(--jade);
  cursor: pointer;
  font-weight: 600;
}
.toggle-btn:hover { color: var(--jade-dim); }
</style>