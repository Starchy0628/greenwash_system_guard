<template>
  <div class="trend-wrap" v-if="data.length">
    <h4>历史趋势（近5年）</h4>
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ data: { type: Array, default: () => [] } })
const chartRef = ref(null)
let chart = null

function renderChart() {
  if (!chartRef.value || !props.data.length) return
  if (!chart) chart = echarts.init(chartRef.value)

  const years = props.data.map(d => d.year)
  const values = props.data.map(d => d.gw_index ?? d.gw)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1B2E27',
      borderColor: '#2F6F62',
      textStyle: { color: '#EEEEE4', fontSize: 12 },
    },
    grid: { top: 10, right: 20, bottom: 24, left: 50 },
    xAxis: {
      type: 'category',
      data: years,
      axisLine: { lineStyle: { color: 'rgba(238,238,228,0.2)' } },
      axisLabel: { color: '#6E9186', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'GW指数',
      nameTextStyle: { color: '#6E9186', fontSize: 10 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(238,238,228,0.08)' } },
      axisLabel: { color: '#6E9186', fontSize: 10 },
    },
    series: [{
      data: values,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#A83B2E', width: 2 },
      itemStyle: { color: '#A83B2E' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(168,59,46,0.15)' },
          { offset: 1, color: 'rgba(168,59,46,0)' },
        ]),
      },
    }],
  }, true)
}

onMounted(() => renderChart())
watch(() => props.data, renderChart, { deep: true })
onUnmounted(() => { if (chart) { chart.dispose(); chart = null } })
</script>

<style scoped>
.trend-wrap { margin-top: 22px; }
.trend-wrap h4 {
  font-size: 12.5px;
  letter-spacing: 1px;
  color: var(--ink-soft);
  text-transform: uppercase;
  margin-bottom: 8px;
  font-weight: 700;
}
.chart-container { width: 100%; height: 200px; }
</style>