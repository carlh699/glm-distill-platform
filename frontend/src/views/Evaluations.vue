<template>
  <div>
    <div class="page-header">
      <h2>评估对比</h2>
    </div>

    <!-- 对比图表 -->
    <el-card class="mb-20" v-if="evaluations.length">
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
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { evaluationsApi } from '../api'
import dayjs from 'dayjs'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const evaluations = ref([])
const loading = ref(false)

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
