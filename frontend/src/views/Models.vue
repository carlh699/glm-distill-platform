<template>
  <div>
    <div class="page-header">
      <h2>模型管理</h2>
      <div>
        <el-button @click="loadPresets">预置模型</el-button>
        <el-button type="primary" @click="showDialog = true">添加模型</el-button>
      </div>
    </div>

    <el-table :data="models" stripe v-loading="loading">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="model_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.model_type === 'teacher' ? 'warning' : 'success'">
            {{ row.model_type === 'teacher' ? 'Teacher' : row.model_type === 'student' ? 'Student' : '蒸馏模型' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="base_model" label="基座模型" />
      <el-table-column prop="parameters" label="参数量(亿)" width="120" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column prop="is_available" label="可用" width="80">
        <template #default="{ row }">
          <el-icon color="#67C23A" v-if="row.is_available"><CircleCheck /></el-icon>
          <el-icon color="#F56C6C" v-else><CircleClose /></el-icon>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" type="danger" link @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 添加模型对话框 -->
    <el-dialog v-model="showDialog" title="添加模型" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="如: GLM-4-9B-Chat" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.model_type">
            <el-option label="Teacher (教师模型)" value="teacher" />
            <el-option label="Student (学生模型)" value="student" />
            <el-option label="Distilled (蒸馏模型)" value="distilled" />
          </el-select>
        </el-form-item>
        <el-form-item label="基座模型">
          <el-input v-model="form.base_model" placeholder="如: THUDM/glm-4-9b-chat" />
        </el-form-item>
        <el-form-item label="HF ID">
          <el-input v-model="form.huggingface_id" placeholder="HuggingFace Model ID" />
        </el-form-item>
        <el-form-item label="本地路径">
          <el-input v-model="form.local_path" placeholder="/data/models/..." />
        </el-form-item>
        <el-form-item label="参数量(亿)">
          <el-input-number v-model="form.parameters" :min="0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确认</el-button>
      </template>
    </el-dialog>

    <!-- 预置模型对话框 -->
    <el-dialog v-model="showPresets" title="预置 GLM 模型" width="700px">
      <el-table :data="presets" stripe>
        <el-table-column prop="name" label="模型名称" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="parameters" label="参数量(亿)" width="100" />
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="importPreset(row)">导入</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modelsApi } from '../api'

const models = ref([])
const loading = ref(false)
const showDialog = ref(false)
const showPresets = ref(false)
const presets = ref([])
const form = ref({
  name: '', model_type: 'student', base_model: '', huggingface_id: '',
  local_path: '', parameters: 0, description: ''
})

const loadModels = async () => {
  loading.value = true
  try { models.value = await modelsApi.list() }
  finally { loading.value = false }
}

const loadPresets = async () => {
  presets.value = await modelsApi.presets()
  showPresets.value = true
}

const importPreset = async (preset) => {
  await modelsApi.create({
    name: preset.name,
    model_type: preset.type,
    base_model: preset.base_model,
    huggingface_id: preset.source === 'huggingface' ? preset.base_model : null,
    parameters: preset.parameters,
    description: preset.description,
  })
  ElMessage.success('导入成功')
  loadModels()
}

const handleCreate = async () => {
  await modelsApi.create(form.value)
  ElMessage.success('创建成功')
  showDialog.value = false
  form.value = { name: '', model_type: 'student', base_model: '', huggingface_id: '', local_path: '', parameters: 0, description: '' }
  loadModels()
}

const handleDelete = async (id) => {
  await ElMessageBox.confirm('确认删除该模型？', '警告', { type: 'warning' })
  await modelsApi.delete(id)
  ElMessage.success('已删除')
  loadModels()
}

onMounted(loadModels)
</script>
