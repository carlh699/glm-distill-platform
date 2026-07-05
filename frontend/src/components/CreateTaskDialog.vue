<template>
  <el-dialog :model-value="visible" @update:model-value="$emit('update:visible', $event)" title="新建蒸馏任务" width="700px">
    <el-form :model="form" label-width="140px">
      <el-divider content-position="left">基本信息</el-divider>
      <el-form-item label="任务名称">
        <el-input v-model="form.name" placeholder="如: GLM-4 → ChatGLM3 蒸馏" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" />
      </el-form-item>

      <el-divider content-position="left">模型与数据</el-divider>
      <el-form-item label="Teacher 模型">
        <el-select v-model="form.teacher_model_id" placeholder="选择教师模型" filterable>
          <el-option v-for="m in teacherModels" :key="m.id" :label="`${m.name} (${m.base_model})`" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="Student 模型">
        <el-select v-model="form.student_model_id" placeholder="选择学生模型" filterable>
          <el-option v-for="m in studentModels" :key="m.id" :label="`${m.name} (${m.base_model})`" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="训练数据集">
        <el-select v-model="form.dataset_id" placeholder="选择数据集" filterable>
          <el-option v-for="d in datasets" :key="d.id" :label="`${d.name} (${d.num_samples} samples)`" :value="d.id" />
        </el-select>
      </el-form-item>

      <el-divider content-position="left">蒸馏策略</el-divider>
      <el-form-item label="策略">
        <el-radio-group v-model="form.strategy">
          <el-radio-button value="logits_kd">Logits KD</el-radio-button>
          <el-radio-button value="response_kd">Response KD</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="温度 (T)">
        <el-slider v-model="form.distill_temperature" :min="0.5" :max="10" :step="0.5" show-input />
      </el-form-item>
      <el-form-item label="α (KD 权重)">
        <el-slider v-model="form.distill_alpha" :min="0" :max="1" :step="0.1" show-input />
      </el-form-item>

      <el-divider content-position="left">训练参数</el-divider>
      <el-row>
        <el-col :span="12">
          <el-form-item label="学习率">
            <el-input-number v-model="form.learning_rate" :min="1e-7" :max="1e-3" :step="1e-5" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="Batch Size">
            <el-input-number v-model="form.batch_size" :min="1" :max="64" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row>
        <el-col :span="12">
          <el-form-item label="Epochs">
            <el-input-number v-model="form.num_epochs" :min="1" :max="20" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="Max Seq Len">
            <el-input-number v-model="form.max_seq_length" :min="256" :max="8192" :step="256" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="使用 LoRA">
        <el-switch v-model="form.use_lora" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="creating" @click="handleCreate">创建并启动</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { modelsApi, datasetsApi, tasksApi } from '../api'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['update:visible', 'created'])

const creating = ref(false)
const teacherModels = ref([])
const studentModels = ref([])
const datasets = ref([])
const form = ref({
  name: '', description: '',
  teacher_model_id: '', student_model_id: '', dataset_id: '',
  strategy: 'logits_kd',
  distill_temperature: 2.0, distill_alpha: 0.5,
  learning_rate: 5e-5, batch_size: 4, num_epochs: 3,
  max_seq_length: 2048, use_lora: false,
})

watch(() => props.visible, async (val) => {
  if (val) {
    const [models, ds] = await Promise.all([modelsApi.list(), datasetsApi.list()])
    teacherModels.value = models.filter(m => m.model_type === 'teacher')
    studentModels.value = models.filter(m => m.model_type === 'student')
    datasets.value = ds
  }
})

const handleCreate = async () => {
  if (!form.value.name || !form.value.teacher_model_id || !form.value.student_model_id || !form.value.dataset_id) {
    ElMessage.warning('请填写完整信息')
    return
  }
  creating.value = true
  try {
    await tasksApi.create(form.value)
    ElMessage.success('任务已创建并提交')
    emit('update:visible', false)
    emit('created')
    form.value = { name: '', description: '', teacher_model_id: '', student_model_id: '', dataset_id: '', strategy: 'logits_kd', distill_temperature: 2.0, distill_alpha: 0.5, learning_rate: 5e-5, batch_size: 4, num_epochs: 3, max_seq_length: 2048, use_lora: false }
  } finally { creating.value = false }
}
</script>
