<template>
  <div>
    <div class="page-header">
      <h2>蒸馏任务</h2>
      <el-button type="primary" @click="showCreate = true">新建蒸馏任务</el-button>
    </div>

    <el-table :data="tasks" stripe v-loading="loading">
      <el-table-column prop="name" label="任务名称" />
      <el-table-column prop="strategy" label="策略" width="140">
        <template #default="{ row }">{{ strategyLabel(row.strategy) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="progress" label="进度" width="180">
        <template #default="{ row }">
          <el-progress :percentage="Math.round(row.progress * 100)" :status="progressStatus(row.status)" />
        </template>
      </el-table-column>
      <el-table-column prop="num_epochs" label="Epochs" width="80" />
      <el-table-column prop="learning_rate" label="学习率" width="100" />
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" link @click="$router.push(`/tasks/${row.id}`)">详情</el-button>
          <el-button v-if="row.status === 'running' || row.status === 'pending'" size="small" type="warning" link @click="handleCancel(row.id)">取消</el-button>
          <el-button size="small" type="danger" link @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <CreateTaskDialog v-model:visible="showCreate" @created="loadTasks" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { tasksApi } from '../api'
import CreateTaskDialog from '../components/CreateTaskDialog.vue'
import dayjs from 'dayjs'

const tasks = ref([])
const loading = ref(false)
const showCreate = ref(false)

const statusType = (s) => ({ success: 'success', running: 'warning', failed: 'danger', pending: 'info', cancelled: 'info' }[s] || 'info')
const statusLabel = (s) => ({ success: '成功', running: '运行中', failed: '失败', pending: '等待', cancelled: '已取消' }[s] || s)
const progressStatus = (s) => s === 'failed' ? 'exception' : s === 'success' ? 'success' : ''
const strategyLabel = (s) => ({ logits_kd: 'Logits KD', response_kd: 'Response KD', feature_kd: 'Feature KD', multi_teacher: '多教师', progressive: '渐进式' }[s] || s)
const formatDate = (d) => d ? dayjs(d).format('MM-DD HH:mm') : ''

const loadTasks = async () => {
  loading.value = true
  try { tasks.value = await tasksApi.list() }
  finally { loading.value = false }
}

const handleCancel = async (id) => {
  await ElMessageBox.confirm('确认取消此任务？', '警告', { type: 'warning' })
  await tasksApi.cancel(id)
  ElMessage.success('已取消')
  loadTasks()
}

const handleDelete = async (id) => {
  await ElMessageBox.confirm('确认删除？', '警告', { type: 'warning' })
  await tasksApi.delete(id)
  ElMessage.success('已删除')
  loadTasks()
}

onMounted(loadTasks)
</script>
