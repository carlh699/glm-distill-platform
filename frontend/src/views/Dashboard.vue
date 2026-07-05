<template>
  <div>
    <div class="page-header">
      <h2>仪表盘</h2>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="mb-20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.models }}</div>
          <div class="stat-label">模型总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.datasets }}</div>
          <div class="stat-label">数据集</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.tasks }}</div>
          <div class="stat-label">蒸馏任务</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value" style="color: #67C23A">{{ stats.success }}</div>
          <div class="stat-label">成功任务</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表 -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card header="任务状态分布">
          <v-chart :option="taskStatusChart" style="height: 320px" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="蒸馏策略使用">
          <v-chart :option="strategyChart" style="height: 320px" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近任务 -->
    <el-card header="最近任务" class="mt-20">
      <el-table :data="recentTasks" stripe>
        <el-table-column prop="name" label="任务名称" />
        <el-table-column prop="strategy" label="策略" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.progress * 100)" :status="row.status === 'failed' ? 'exception' : row.status === 'success' ? 'success' : ''" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { tasksApi, modelsApi, datasetsApi } from '../api'
import dayjs from 'dayjs'

use([CanvasRenderer, PieChart, BarChart, TitleComponent, TooltipComponent, LegendComponent])

const stats = ref({ models: 0, datasets: 0, tasks: 0, success: 0 })
const recentTasks = ref([])

const taskStatusChart = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: [
      { value: recentTasks.value.filter(t => t.status === 'success').length, name: '成功' },
      { value: recentTasks.value.filter(t => t.status === 'running').length, name: '运行中' },
      { value: recentTasks.value.filter(t => t.status === 'pending').length, name: '等待中' },
      { value: recentTasks.value.filter(t => t.status === 'failed').length, name: '失败' },
    ],
  }],
}))

const strategyChart = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: ['Logits KD', 'Response KD', 'Feature KD', '多教师', '渐进式'] },
  yAxis: { type: 'value' },
  series: [{
    type: 'bar',
    data: [
      recentTasks.value.filter(t => t.strategy === 'logits_kd').length,
      recentTasks.value.filter(t => t.strategy === 'response_kd').length,
      recentTasks.value.filter(t => t.strategy === 'feature_kd').length,
      recentTasks.value.filter(t => t.strategy === 'multi_teacher').length,
      recentTasks.value.filter(t => t.strategy === 'progressive').length,
    ],
    itemStyle: { color: '#409EFF' },
  }],
}))

const statusType = (s) => ({ success: 'success', running: 'warning', failed: 'danger', pending: 'info', cancelled: 'info' }[s] || 'info')
const statusLabel = (s) => ({ success: '成功', running: '运行中', failed: '失败', pending: '等待', cancelled: '已取消' }[s] || s)
const formatDate = (d) => d ? dayjs(d).format('YYYY-MM-DD HH:mm') : ''

onMounted(async () => {
  try {
    const [models, datasets, tasks] = await Promise.all([
      modelsApi.list(), datasetsApi.list(), tasksApi.list()
    ])
    stats.value = {
      models: models.length,
      datasets: datasets.length,
      tasks: tasks.length,
      success: tasks.filter(t => t.status === 'success').length,
    }
    recentTasks.value = tasks.slice(0, 10)
  } catch (e) { console.error(e) }
})
</script>

<style scoped>
.mb-20 { margin-bottom: 20px; }
.mt-20 { margin-top: 20px; }
</style>
