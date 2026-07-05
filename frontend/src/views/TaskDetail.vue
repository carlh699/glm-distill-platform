<template>
  <div v-loading="loading">
    <div class="page-header">
      <div>
        <el-button @click="$router.push('/tasks')" link><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <span style="margin-left:12px;font-size:20px;font-weight:600">{{ task.name }}</span>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="evaluating" @click="handleEvaluate">评估模型</el-button>
        <el-button v-if="canDeploy" type="success" :loading="deploying" @click="handleDeploy">部署模型</el-button>
        <el-tag :type="statusType(task.status)" size="large">{{ statusLabel(task.status) }}</el-tag>
      </div>
    </div>

    <!-- 进度条 -->
    <el-card class="mb-20">
      <el-progress :percentage="Math.round((task.progress || 0) * 100)" :status="progressStatus(task.status)" :stroke-width="20" :text-inside="true" />
      <div style="margin-top:8px;color:#909399">
        Step {{ task.current_step || 0 }} / {{ task.total_steps || 0 }}
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
            <el-descriptions-item label="训练损失">{{ formatNumber(task.metrics?.train_loss, 4) }}</el-descriptions-item>
            <el-descriptions-item label="训练时长">{{ formatDuration(task.metrics?.train_runtime_sec) }}</el-descriptions-item>
            <el-descriptions-item label="吞吐量">{{ formatNumber(task.metrics?.train_samples_per_sec, 2) }} samples/s</el-descriptions-item>
            <el-descriptions-item label="模型大小">{{ formatNumber(task.metrics?.model_size_mb, 1) }} MB</el-descriptions-item>
            <el-descriptions-item label="输出模型">{{ task.output_model_path || '-' }}</el-descriptions-item>
            <el-descriptions-item label="MLflow Run">{{ task.mlflow_run_id || '-' }}</el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="暂无指标" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 教师 vs 学生模型 -->
    <el-card header="教师 / 学生模型对比" class="mt-20">
      <el-table :data="teacherStudentRows" border v-loading="modelLoading">
        <el-table-column prop="metric" label="指标" width="120" />
        <el-table-column prop="teacher" label="教师模型" show-overflow-tooltip />
        <el-table-column prop="student" label="学生模型" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 损失曲线 -->
    <el-card header="训练损失曲线" class="mt-20">
      <v-chart v-if="lossData.length" :option="lossChartOption" style="height: 300px" autoresize />
      <el-empty v-else description="等待 WebSocket 推送损失数据" />
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
import { ElMessage } from 'element-plus'
import { tasksApi, evaluationsApi, deploymentsApi, modelsApi } from '../api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent])

const route = useRoute()
const loading = ref(true)
const modelLoading = ref(false)
const evaluating = ref(false)
const deploying = ref(false)
const task = ref({})
const teacherModel = ref(null)
const studentModel = ref(null)
const lossData = ref([])
let pollTimer = null
let taskSocket = null
let loadedModelPair = ''

const statusType = (s) => ({ success: 'success', running: 'warning', failed: 'danger', pending: 'info', cancelled: 'info' }[s] || 'info')
const statusLabel = (s) => ({ success: '成功', running: '运行中', failed: '失败', pending: '等待', cancelled: '已取消' }[s] || s)
const progressStatus = (s) => s === 'failed' ? 'exception' : s === 'success' ? 'success' : ''
const strategyLabel = (s) => ({ logits_kd: 'Logits KD', response_kd: 'Response KD', feature_kd: 'Feature KD', multi_teacher: '多教师', progressive: '渐进式' }[s] || s)
const formatDuration = (sec) => sec ? `${Math.floor(sec / 60)}m ${Math.floor(sec % 60)}s` : '-'
const formatNumber = (value, digits = 2) => Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '-'

const canDeploy = computed(() => task.value.status === 'success' && !!task.value.output_model_path)

const formatParameters = (value) => {
  const number = Number(value)
  if (!Number.isFinite(number) || number <= 0) return '-'
  if (number >= 1e9) return `${(number / 1e9).toFixed(1)}B`
  if (number >= 1e6) return `${(number / 1e6).toFixed(1)}M`
  return number.toLocaleString()
}

const modelSource = (model) => model?.huggingface_id || model?.local_path || model?.minio_path || '-'

const teacherStudentRows = computed(() => [
  { metric: '模型名称', teacher: teacherModel.value?.name || '-', student: studentModel.value?.name || '-' },
  { metric: '基础模型', teacher: teacherModel.value?.base_model || '-', student: studentModel.value?.base_model || '-' },
  { metric: '参数规模', teacher: formatParameters(teacherModel.value?.parameters), student: formatParameters(studentModel.value?.parameters) },
  { metric: '模型来源', teacher: modelSource(teacherModel.value), student: modelSource(studentModel.value) },
])

const lossChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 48, right: 24, top: 28, bottom: 40 },
  xAxis: { type: 'category', name: 'Step', data: lossData.value.map(d => d.step) },
  yAxis: { type: 'value', name: 'Loss', scale: true },
  series: [
    {
      name: 'Train Loss',
      type: 'line',
      data: lossData.value.map(d => d.loss),
      smooth: true,
      showSymbol: false,
      itemStyle: { color: '#409EFF' },
      areaStyle: { color: 'rgba(64,158,255,0.12)' },
    },
  ],
}))

const normalizeLossPoint = (entry, fallbackStep) => {
  if (typeof entry === 'number') return { step: fallbackStep, loss: entry }
  if (!entry || typeof entry !== 'object') return null
  const loss = entry.loss ?? entry.train_loss ?? entry.value
  if (loss === undefined || loss === null) return null
  return {
    step: entry.step ?? entry.global_step ?? entry.current_step ?? fallbackStep,
    loss: Number(loss),
  }
}

const extractLossPoints = (payload) => {
  const metrics = payload?.metrics || {}
  const history = payload?.loss_history || metrics.loss_history || metrics.train_loss_history
  if (Array.isArray(history) && history.length) {
    return history.map((item, index) => normalizeLossPoint(item, index + 1)).filter(Boolean)
  }

  const loss = payload?.loss ?? payload?.train_loss ?? metrics.loss ?? metrics.train_loss
  if (loss === undefined || loss === null) return []
  return [{
    step: payload?.current_step ?? metrics.step ?? lossData.value.length + 1,
    loss: Number(loss),
  }]
}

const updateLossData = (points) => {
  points
    .filter(point => Number.isFinite(point.loss))
    .forEach((point) => {
      const existingIndex = lossData.value.findIndex(item => String(item.step) === String(point.step))
      if (existingIndex >= 0) {
        lossData.value[existingIndex] = point
      } else {
        lossData.value.push(point)
      }
    })
  if (lossData.value.length > 300) lossData.value = lossData.value.slice(-300)
}

const mergeTaskPayload = (payload) => {
  task.value = {
    ...task.value,
    ...payload,
    metrics: payload.metrics || task.value.metrics || {},
  }
  updateLossData(extractLossPoints(payload))
}

const loadModelComparison = async () => {
  if (!task.value.teacher_model_id || !task.value.student_model_id) return
  const pairKey = `${task.value.teacher_model_id}:${task.value.student_model_id}`
  if (pairKey === loadedModelPair) return
  loadedModelPair = pairKey
  modelLoading.value = true
  try {
    const [teacher, student] = await Promise.all([
      modelsApi.get(task.value.teacher_model_id),
      modelsApi.get(task.value.student_model_id),
    ])
    teacherModel.value = teacher
    studentModel.value = student
  } finally {
    modelLoading.value = false
  }
}

const schedulePoll = () => {
  if (pollTimer) clearTimeout(pollTimer)
  if (task.value.status === 'running' || task.value.status === 'pending') {
    pollTimer = setTimeout(loadTask, 3000)
  }
}

const loadTask = async () => {
  try {
    const data = await tasksApi.get(route.params.id)
    mergeTaskPayload(data)
    await loadModelComparison()
  } finally {
    loading.value = false
    schedulePoll()
  }
}

const closeTaskSocket = () => {
  if (taskSocket) {
    taskSocket.close()
    taskSocket = null
  }
}

const openTaskSocket = () => {
  closeTaskSocket()
  taskSocket = new WebSocket(`ws://localhost:8000/api/v1/tasks/${route.params.id}/ws`)
  taskSocket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data)
      if (payload.error) {
        ElMessage.error(payload.error)
        return
      }
      mergeTaskPayload(payload)
      schedulePoll()
    } catch (error) {
      ElMessage.warning('实时训练数据解析失败')
    }
  }
  taskSocket.onerror = () => {
    closeTaskSocket()
  }
  taskSocket.onclose = () => {
    taskSocket = null
  }
}

const handleEvaluate = async () => {
  evaluating.value = true
  try {
    await evaluationsApi.trigger(route.params.id)
    ElMessage.success('评估任务已提交')
  } finally {
    evaluating.value = false
  }
}

const handleDeploy = async () => {
  if (!canDeploy.value) {
    ElMessage.warning('任务完成且存在输出模型后才能部署')
    return
  }
  deploying.value = true
  try {
    await deploymentsApi.create({
      model_name: task.value.name || 'distilled-model',
      model_path: task.value.output_model_path,
      framework: 'vllm',
      replicas: 1,
    })
    ElMessage.success('部署已提交')
  } finally {
    deploying.value = false
  }
}

onMounted(async () => {
  await loadTask()
  openTaskSocket()
})

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
  closeTaskSocket()
})
</script>

<style scoped>
.mb-20 { margin-bottom: 20px; }
.mt-20 { margin-top: 20px; }
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
