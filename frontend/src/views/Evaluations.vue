<template>
  <div>
    <div class="page-header">
      <h2>评估对比</h2>
    </div>

    <!-- 雷达图表 -->
    <el-card header="模型指标雷达图" class="mb-20" v-if="evaluations.length">
      <v-chart :option="radarChartOption" style="height: 420px" autoresize />
    </el-card>

    <!-- 对比图表 -->
    <el-card header="原始指标对比" class="mb-20" v-if="evaluations.length">
      <v-chart :option="compareChart" style="height: 400px" autoresize />
    </el-card>

    <!-- 评估列表 -->
    <el-table :data="evaluations" stripe v-loading="loading">
      <el-table-column prop="model_path" label="模型路径" show-overflow-tooltip />
      <el-table-column prop="perplexity" label="PPL" width="100">
        <template #default="{ row }">{{ row.perplexity?.toFixed(2) || '-' }}</template>
      </el-table-column>
      <el-table-column prop="bleu" label="BLEU" width="100">
        <template #default="{ row }">{{ row.bleu?.toFixed(4) || '-' }}</template>
      </el-table-column>
      <el-table-column prop="rouge_l" label="ROUGE-L" width="100">
        <template #default="{ row }">{{ row.rouge_l?.toFixed(4) || '-' }}</template>
      </el-table-column>
      <el-table-column prop="inference_latency_ms" label="延迟(ms/tok)" width="130">
        <template #default="{ row }">{{ row.inference_latency_ms?.toFixed(1) || '-' }}</template>
      </el-table-column>
      <el-table-column prop="model_size_mb" label="大小(MB)" width="100">
        <template #default="{ row }">{{ row.model_size_mb?.toFixed(1) || '-' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="评估时间" width="160">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, RadarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, RadarComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { evaluationsApi } from '../api'
import dayjs from 'dayjs'

use([CanvasRenderer, BarChart, RadarChart, GridComponent, TooltipComponent, LegendComponent, RadarComponent])

const evaluations = ref([])
const loading = ref(false)

const radarMetrics = [
  { key: 'perplexity', name: 'PPL', lowerBetter: true },
  { key: 'bleu', name: 'BLEU' },
  { key: 'rouge_l', name: 'ROUGE-L' },
  { key: 'inference_latency_ms', name: '延迟', lowerBetter: true },
  { key: 'model_size_mb', name: '大小', lowerBetter: true },
]

const modelLabel = (evaluation, index) => {
  const path = evaluation.model_path || `Model ${index + 1}`
  return path.split('/').filter(Boolean).pop() || `Model ${index + 1}`
}

const metricValues = (key) => evaluations.value.map(item => Number(item[key]) || 0).filter(value => value > 0)

const normalizeMetric = (evaluation, metric) => {
  const value = Number(evaluation[metric.key]) || 0
  const values = metricValues(metric.key)
  if (!value || !values.length) return 0
  if (metric.lowerBetter) {
    const best = Math.min(...values)
    return Math.round((best / value) * 100)
  }
  const max = Math.max(...values)
  return max ? Math.round((value / max) * 100) : 0
}

const radarChartOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const evaluation = evaluations.value[params.dataIndex]
      if (!evaluation) return params.name
      return [
        `<b>${params.name}</b>`,
        `PPL: ${evaluation.perplexity?.toFixed(2) || '-'}`,
        `BLEU: ${evaluation.bleu?.toFixed(4) || '-'}`,
        `ROUGE-L: ${evaluation.rouge_l?.toFixed(4) || '-'}`,
        `延迟: ${evaluation.inference_latency_ms?.toFixed(1) || '-'} ms/tok`,
        `大小: ${evaluation.model_size_mb?.toFixed(1) || '-'} MB`,
      ].join('<br/>')
    },
  },
  legend: { top: 0, data: evaluations.value.map(modelLabel) },
  radar: {
    radius: '62%',
    center: ['50%', '56%'],
    indicator: radarMetrics.map(metric => ({ name: metric.name, max: 100 })),
  },
  series: [
    {
      name: '模型指标',
      type: 'radar',
      data: evaluations.value.map((evaluation, index) => ({
        name: modelLabel(evaluation, index),
        value: radarMetrics.map(metric => normalizeMetric(evaluation, metric)),
      })),
    },
  ],
}))

const compareChart = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['Perplexity', 'BLEU', 'ROUGE-L', '延迟(ms)', '大小(MB)'] },
  xAxis: { type: 'category', data: evaluations.value.map((e, i) => `Model ${i+1}`) },
  yAxis: { type: 'value' },
  series: [
    { name: 'Perplexity', type: 'bar', data: evaluations.value.map(e => e.perplexity || 0) },
    { name: 'BLEU', type: 'bar', data: evaluations.value.map(e => e.bleu || 0) },
    { name: 'ROUGE-L', type: 'bar', data: evaluations.value.map(e => e.rouge_l || 0) },
    { name: '延迟(ms)', type: 'bar', data: evaluations.value.map(e => e.inference_latency_ms || 0) },
    { name: '大小(MB)', type: 'bar', data: evaluations.value.map(e => e.model_size_mb || 0) },
  ],
}))

const formatDate = (d) => d ? dayjs(d).format('MM-DD HH:mm') : ''

onMounted(async () => {
  loading.value = true
  try { evaluations.value = await evaluationsApi.list() }
  finally { loading.value = false }
})
</script>

<style scoped>
.mb-20 { margin-bottom: 20px; }
</style>
