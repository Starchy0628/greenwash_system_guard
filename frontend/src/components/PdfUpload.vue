<template>
  <div class="pdf-upload">
    <!-- 上传区域 -->
    <div
      class="upload-area"
      :class="{ dragging: isDragging, hasFile: !!file }"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".pdf"
        @change="handleFile"
        hidden
      />

      <div v-if="!file" class="upload-placeholder">
        <div class="upload-icon">📄</div>
        <div class="upload-title">上传企业年报 PDF</div>
        <div class="upload-desc">
          拖拽文件到此处，或
          <button class="browse-btn" @click="$refs.fileInput.click()">点击选择文件</button>
        </div>
        <div class="upload-hint">
          支持 .pdf 格式 · 最大 50MB · 文本型PDF效果最佳
        </div>
      </div>

      <div v-else class="upload-loaded">
        <div class="file-info">
          <span class="file-icon">📄</span>
          <span class="file-name">{{ file.name }}</span>
          <span class="file-size">{{ formatSize(file.size) }}</span>
        </div>
        <button class="clear-btn" @click="clearFile" :disabled="analyzing">清除</button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="upload-error">
      <span class="err-icon">⚠️</span>
      {{ errorMsg }}
      <button class="err-dismiss" @click="errorMsg = ''">×</button>
    </div>

    <!-- 分析按钮 -->
    <div class="analyze-row" v-if="file">
      <button
        class="analyze-btn"
        :disabled="analyzing"
        @click="startAnalysis"
      >
        {{ analyzing ? '分析中...' : '开始分析' }}
      </button>
    </div>

    <!-- 进度指示 -->
    <LiveSteps
      :active="analyzing"
      :current-step="liveStep"
      :steps="pdfSteps"
    />

    <!-- 分析结果 -->
    <ResultCard
      :result="result"
      :is-watched="false"
      @toggle-watch="() => {}"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import LiveSteps from './LiveSteps.vue'
import ResultCard from './ResultCard.vue'

const fileInput = ref(null)
const file = ref(null)
const isDragging = ref(false)
const analyzing = ref(false)
const liveStep = ref(-1)
const result = ref(null)
const errorMsg = ref('')

const pdfSteps = [
  '接收文件并校验格式',
  '解析 PDF，提取文本内容',
  '语句切分与环保相关性过滤',
  '三模型独立分类投票中',
  '语境情感打分 + 行业基准修正，合成GW指数',
]

const stepIndex = { uploading: 0, parsing: 0, parsed: 1, segmenting: 2, classifying: 3, voting: 4, scoring: 4 }

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function handleFile(e) {
  const f = e.target.files?.[0]
  validateAndSet(f)
}

function handleDrop(e) {
  isDragging.value = false
  const f = e.dataTransfer?.files?.[0]
  validateAndSet(f)
}

function validateAndSet(f) {
  errorMsg.value = ''
  if (!f) return
  if (!f.name.toLowerCase().endsWith('.pdf')) {
    errorMsg.value = '仅支持 PDF 格式文件'
    return
  }
  if (f.size > 50 * 1024 * 1024) {
    errorMsg.value = '文件超过 50MB 限制，请压缩后重试'
    return
  }
  file.value = f
}

function clearFile() {
  file.value = null
  result.value = null
  errorMsg.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

async function startAnalysis() {
  if (!file.value) return
  analyzing.value = true
  liveStep.value = -1
  result.value = null
  errorMsg.value = ''

  const formData = new FormData()
  formData.append('file', file.value)

  let eventSource = null
  try {
    const response = await fetch('/api/pdf/analyze', {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      throw new Error(`服务器错误: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let eventType = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            handleSSE(eventType, data)
          } catch (e) {
            // 忽略解析错误
          }
          eventType = ''
        }
      }
    }
  } catch (err) {
    console.error('PDF analysis error:', err)
    errorMsg.value = err.message || '分析失败，请重试'
    analyzing.value = false
  }
}

function handleSSE(type, data) {
  switch (type) {
    case 'status':
      liveStep.value = stepIndex[data.phase] ?? -1
      break
    case 'progress':
      liveStep.value = 3
      break
    case 'result':
      result.value = data.result
      analyzing.value = false
      break
    case 'analysis_error':
      errorMsg.value = data.message
      if (!data.retryable) {
        analyzing.value = false
      }
      break
  }
}
</script>

<style scoped>
.pdf-upload { margin-bottom: 20px; }

.upload-area {
  border: 2px dashed var(--line-soft);
  border-radius: var(--radius);
  padding: 36px 24px;
  text-align: center;
  transition: all .2s;
  cursor: pointer;
}
.upload-area.dragging {
  border-color: var(--jade);
  background: rgba(47, 111, 98, 0.08);
}
.upload-area.hasFile {
  border-style: solid;
  border-color: var(--jade-dim);
  padding: 16px 20px;
}

.upload-placeholder { }
.upload-icon { font-size: 36px; margin-bottom: 10px; }
.upload-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--paper);
  margin-bottom: 6px;
}
.upload-desc {
  font-size: 13px;
  color: var(--paper-soft);
  margin-bottom: 8px;
}
.browse-btn {
  background: none;
  border: none;
  color: var(--jade);
  cursor: pointer;
  font-weight: 600;
  text-decoration: underline;
  font-family: 'Noto Sans SC';
  font-size: 13px;
}
.upload-hint {
  font-size: 11px;
  color: var(--ink-soft);
}

.upload-loaded { }
.file-info {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--paper);
}
.file-icon { font-size: 20px; }
.file-name { font-weight: 600; flex: 1; text-align: left; }
.file-size { font-size: 12px; color: var(--paper-soft); }
.clear-btn {
  background: none;
  border: 1px solid var(--line-soft);
  color: var(--paper-soft);
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  margin-top: 10px;
  font-family: 'Noto Sans SC';
}
.clear-btn:hover { border-color: var(--cinnabar); color: var(--cinnabar); }
.clear-btn:disabled { opacity: .5; cursor: not-allowed; }

.upload-error {
  margin-top: 12px;
  background: rgba(168, 59, 46, 0.1);
  border: 1px solid var(--cinnabar);
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 13px;
  color: var(--cinnabar);
  display: flex;
  align-items: center;
  gap: 8px;
}
.err-icon { font-size: 16px; }
.err-dismiss {
  background: none;
  border: none;
  color: var(--cinnabar);
  cursor: pointer;
  margin-left: auto;
  font-size: 16px;
}

.analyze-row { margin-top: 14px; }
.analyze-btn {
  width: 100%;
  background: var(--gold);
  color: var(--ink);
  border: none;
  border-radius: var(--radius);
  padding: 12px;
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
  font-family: 'Noto Sans SC';
}
.analyze-btn:disabled { opacity: .5; cursor: not-allowed; }
</style>