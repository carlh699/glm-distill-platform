<template>
  <div v-loading="loading">
    <div class="page-header">
      <div>
        <el-button @click="$router.push('/tasks')" link><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <span style="margin-left:12px;font-size:20px;font-weight:600">{{ task.name }}</span>
      </div>
      <div>
        <el-tag :type="statusType(task.status)" size="large">{{ statusLabel(task.status) }}</el-tag>
      </div>
    </div>

    <!-- 进度条 -->
    <el-card class="mb-20">
      <el-progress :percentage="Math.round(task.progress * 100)" :status="progressStatus(task.status)" :stroke-width="20" :text-inside="true" />
      <div style="margin-top:8px;color:#909399">
        Step {{ task.current_step }} / {{ task.total_steps }}
      </div>
    </el-card>

    <el-row :gutter="16">
      <!-- 任务配置 -->
      <el-col :span="12">
        <el-card header="任务配置">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="策略">{{ strategyLabel(task.strategy) }}</el-descriptions-item>
            <el-descriptions-item label="温度 (T)">{{ task.distill_temperature }}</el-descriptions-item>
            <el-descriptions-item label="α (KD权重)">{{ task.distill_alpha }}</el-descriptions-item>
            <el-descriptions-item label="学习率">{{ task.learning_rate }}</el-descriptions-item>
            <el-descriptions-item label="Batch Size">{{ task.batch_size }}</el-descriptions-item>
            <el-descriptions-item label="Epochs">{{ task.num_epochs }}</el-descriptions-item>
            <el-descriptions-item label="Max Seq Len">{{ task.max_seq_length }}</el-descriptions-item>
            <el-descriptions-item label="LoRA">{{ task.use_lora ? '是' : '否' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 训练指标 -->
      <el-col :span="12">
        <el-card header="训练指标">
          <el-descriptions :column="1" border v-if="task.metrics">
            <el-descriptions-item label="训练损失">{{ task.metrics?.train_loss?.toFixed(4) || '-' }}</el-descriptions-item>
            <el-descriptions-item label="训练时长">{{ formatDuration(task.metrics?.train_runtime_sec) }}</el-descriptions-item>
            <el-descriptions-item label="吞吐量">{{ task.metrics?.train_samples_per_sec?.toFixed(2) || '-' }} samples/s</el-descriptions-item>
            <el-descriptions-item label="模型大小">{{ task.metrics?.model_size_mb?.toFixed(1) || '-' }} MB</el-descriptions-item>
            <el-descriptions-item label="MLflow Run">{{ task.mlflow_run_id || '-' }}</el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="暂无指标" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 损失曲线 -->
    <el-card header="训练损失曲线" class="mt-20" v-if="lossData.length">
      <v-chart :option="lossChartOption" style="height: 300px" autoresize />
    </el-card>

    <!-- 错误信息 -->
    <el-card v-if="task.error_message" class="mt-20">
      <el-alert :title="task.error_message" type="error" :closable="false" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { tasksApi } from '../api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent])

const route = useRoute()
const loading = ref(true)
const task = ref({})
const lossData = ref([])
let pollTimer = null

const statusType = (s) => ({ success: 'success', running: 'warning', failed: 'danger', pending: 'info' }[s] || 'info')
const statusLabel = (s) => ({ success: '成功', running: '运行中', failed: '失败', pending: '等待', cancelled: '已取消' }[s] || s)
const progressStatus = (s) => s === 'failed' ? 'exception' : s === 'success' ? 'success' : ''
const strategyLabel = (s) => ({ logits_kd: 'Logits KD', response_kd: 'Response KD', feature_kd: 'Feature KD', multi_teacher: '多教师', progressive: '渐进式' }[s] || s)
const formatDuration = (sec) => sec ? `${Math.floor(sec/60)}m ${Math.floor(sec%60)}s` : '-'

const lossChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: lossData.value.map(d => d.step) },
  yAxis: { type: 'value', name: 'Loss' },
  series: [{ name: 'Train Loss', type: 'line', data: lossData.value.map(d => d.loss), smooth: true, itemStyle: { color: '#409EFF' } }],
}))

const loadTask = async () => {
  task.value = await tasksApi.get(route.params.id)
  loading.value = false
  if (task.value.status === 'running' || task.value.status === 'pending') {
    pollTimer = setTimeout(loadTask, 3000)
  }
}

onMounted(loadTask)
onUnmounted(() => { if (pollTimer) clearTimeout(pollTimer) })
</script>

<style scoped>
.mb-20 { margin-bottom: 20px; }
.mt-20 { margin-top: 20px; }
</style>
