<template>
  <div>
    <div class="page-header">
      <h2>模型部署</h2>
      <el-button type="primary" @click="showCreate = true">部署模型</el-button>
    </div>

    <el-table :data="deployments" stripe v-loading="loading">
      <el-table-column prop="model_name" label="模型名称" />
      <el-table-column prop="framework" label="框架" width="100" />
      <el-table-column prop="endpoint_url" label="推理端点" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'running' ? 'success' : row.status === 'stopped' ? 'info' : 'warning'">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="replicas" label="副本数" width="80" />
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button v-if="row.status === 'running'" size="small" type="warning" link @click="handleStop(row.id)">停止</el-button>
          <el-button size="small" type="danger" link @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="部署模型" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="模型名称">
          <el-input v-model="form.model_name" placeholder="如: distilled-glm-v1" />
        </el-form-item>
        <el-form-item label="模型路径">
          <el-input v-model="form.model_path" placeholder="MinIO 路径 或 HuggingFace ID" />
        </el-form-item>
        <el-form-item label="框架">
          <el-select v-model="form.framework">
            <el-option label="vLLM (推荐)" value="vllm" />
            <el-option label="Transformers" value="transformers" />
          </el-select>
        </el-form-item>
        <el-form-item label="副本数">
          <el-input-number v-model="form.replicas" :min="1" :max="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">部署</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deploymentsApi } from '../api'
import dayjs from 'dayjs'

const deployments = ref([])
const loading = ref(false)
const showCreate = ref(false)
const form = ref({ model_name: '', model_path: '', framework: 'vllm', replicas: 1 })

const formatDate = (d) => d ? dayjs(d).format('MM-DD HH:mm') : ''

const loadDeployments = async () => {
  loading.value = true
  try { deployments.value = await deploymentsApi.list() }
  finally { loading.value = false }
}

const handleCreate = async () => {
  await deploymentsApi.create(form.value)
  ElMessage.success('部署已提交')
  showCreate.value = false
  form.value = { model_name: '', model_path: '', framework: 'vllm', replicas: 1 }
  loadDeployments()
}

const handleStop = async (id) => {
  await deploymentsApi.stop(id)
  ElMessage.success('已停止')
  loadDeployments()
}

const handleDelete = async (id) => {
  await ElMessageBox.confirm('确认删除？', '警告', { type: 'warning' })
  await deploymentsApi.delete(id)
  ElMessage.success('已删除')
  loadDeployments()
}

onMounted(loadDeployments)
</script>
