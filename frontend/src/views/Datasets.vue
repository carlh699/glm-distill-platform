<template>
  <div>
    <div class="page-header">
      <h2>数据集管理</h2>
      <el-button type="primary" @click="showUpload = true">上传数据集</el-button>
    </div>

    <el-table :data="datasets" stripe v-loading="loading">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="format" label="格式" width="80" />
      <el-table-column prop="num_samples" label="样本数" width="100" />
      <el-table-column prop="file_size" label="大小" width="100">
        <template #default="{ row }">{{ (row.file_size / 1024).toFixed(1) }} KB</template>
      </el-table-column>
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" link @click="handlePreview(row.id)">预览</el-button>
          <el-button size="small" type="danger" link @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUpload" title="上传数据集" width="600px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="uploadForm.name" placeholder="如: GLM-蒸馏训练集" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="uploadForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".jsonl,.csv,.json"
            :on-change="(file) => uploadForm.file = file.raw"
          >
            <el-button>选择文件</el-button>
            <template #tip>
              <div style="color:#909399; font-size:12px;">支持 JSONL / CSV 格式</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUpload = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">上传</el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreview" title="数据预览" width="800px">
      <el-table :data="previewData" border max-height="500">
        <el-table-column type="index" width="50" />
        <el-table-column v-for="key in previewKeys" :key="key" :prop="key" :label="key" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { datasetsApi } from '../api'
import dayjs from 'dayjs'

const datasets = ref([])
const loading = ref(false)
const showUpload = ref(false)
const showPreview = ref(false)
const uploading = ref(false)
const previewData = ref([])
const uploadForm = ref({ name: '', description: '', file: null })

const previewKeys = computed(() => {
  if (!previewData.value.length) return []
  return Object.keys(previewData.value[0])
})

const formatDate = (d) => d ? dayjs(d).format('YYYY-MM-DD HH:mm') : ''

const loadDatasets = async () => {
  loading.value = true
  try { datasets.value = await datasetsApi.list() }
  finally { loading.value = false }
}

const handleUpload = async () => {
  if (!uploadForm.value.name || !uploadForm.value.file) {
    ElMessage.warning('请填写名称并选择文件')
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadForm.value.file)
    await datasetsApi.create(formData, {
      params: {
        name: uploadForm.value.name,
        description: uploadForm.value.description,
      },
    })
    ElMessage.success('上传成功')
    showUpload.value = false
    uploadForm.value = { name: '', description: '', file: null }
    loadDatasets()
  } finally {
    uploading.value = false
  }
}

const handlePreview = async (id) => {
  const result = await datasetsApi.preview(id, 20)
  previewData.value = result.samples
  showPreview.value = true
}

const handleDelete = async (id) => {
  await ElMessageBox.confirm('确认删除？', '警告', { type: 'warning' })
  await datasetsApi.delete(id)
  ElMessage.success('已删除')
  loadDatasets()
}

onMounted(loadDatasets)
</script>
