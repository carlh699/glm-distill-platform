<template>
  <div>
    <div class="page-header">
      <h2>算力节点</h2>
      <div>
        <el-button type="primary" :loading="connecting" @click="handleAutoConnect">
          <el-icon style="margin-right:4px"><Cpu /></el-icon>一键连接本机算力
        </el-button>
        <el-button @click="showAddRemote = true">添加远程节点</el-button>
      </div>
    </div>

    <!-- 算力概览 -->
    <el-row :gutter="16" class="mb-20" v-if="nodes.length">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value" style="color:#67C23A">{{ onlineCount }}</div>
          <div class="stat-label">在线节点</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ totalGpus }}</div>
          <div class="stat-label">总 GPU 数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ totalVram }} GB</div>
          <div class="stat-label">总显存</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value" style="color:#E6A23C">{{ busyCount }}</div>
          <div class="stat-label">繁忙节点</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 节点列表 -->
    <el-table :data="nodes" stripe v-loading="loading">
      <el-table-column prop="name" label="节点名称" width="150" />
      <el-table-column prop="node_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.node_type === 'local' ? 'success' : 'warning'" size="small">
            {{ row.node_type === 'local' ? '本机' : '远程SSH' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small" effect="dark">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="gpu_model" label="GPU 型号" show-overflow-tooltip />
      <el-table-column prop="gpu_count" label="GPU数" width="70" />
      <el-table-column label="显存" width="120">
        <template #default="{ row }">
          {{ row.gpu_vram_used_gb.toFixed(1) }} / {{ row.gpu_total_vram_gb.toFixed(1) }} GB
        </template>
      </el-table-column>
      <el-table-column label="GPU利用率" width="160">
        <template #default="{ row }">
          <el-progress
            :percentage="Math.round(row.gpu_utilization)"
            :color="gpuColor(row.gpu_utilization)"
            :stroke-width="14"
            :text-inside="true"
          />
        </template>
      </el-table-column>
      <el-table-column label="温度" width="80">
        <template #default="{ row }">
          <span :style="{ color: row.gpu_temp > 80 ? '#F56C6C' : row.gpu_temp > 60 ? '#E6A23C' : '#67C23A' }">
            {{ row.gpu_temp.toFixed(0) }}°C
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="cpu_count" label="CPU" width="60" />
      <el-table-column label="RAM" width="100">
        <template #default="{ row }">
          {{ row.ram_used_gb.toFixed(1) }} / {{ row.ram_total_gb.toFixed(1) }} GB
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'offline' || row.status === 'error'"
            size="small" type="primary" link
            @click="handleConnect(row.id)"
          >连接</el-button>
          <el-button
            v-if="row.status === 'online' || row.status === 'busy'"
            size="small" type="warning" link
            @click="handleDisconnect(row.id)"
          >断开</el-button>
          <el-button
            v-if="row.status === 'online' || row.status === 'busy'"
            size="small" link
            @click="startMonitor(row)"
          >监控</el-button>
          <el-button size="small" type="danger" link @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 添加远程节点 -->
    <el-dialog v-model="showAddRemote" title="添加远程算力节点" width="600px">
      <el-form :model="remoteForm" label-width="120px">
        <el-form-item label="节点名称">
          <el-input v-model="remoteForm.name" placeholder="如: GPU服务器-01" />
        </el-form-item>
        <el-form-item label="主机地址">
          <el-input v-model="remoteForm.host" placeholder="192.168.1.100" />
        </el-form-item>
        <el-form-item label="SSH 端口">
          <el-input-number v-model="remoteForm.ssh_port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="SSH 用户">
          <el-input v-model="remoteForm.ssh_user" placeholder="root" />
        </el-form-item>
        <el-form-item label="SSH 密钥路径">
          <el-input v-model="remoteForm.ssh_key_path" placeholder="~/.ssh/id_rsa" />
        </el-form-item>
        <el-form-item label="Python 路径">
          <el-input v-model="remoteForm.python_path" placeholder="python3" />
        </el-form-item>
        <el-form-item label="工作目录">
          <el-input v-model="remoteForm.working_dir" placeholder="/data" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddRemote = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="handleAddRemote">创建并连接</el-button>
      </template>
    </el-dialog>

    <!-- 实时监控对话框 -->
    <el-dialog v-model="showMonitor" :title="`实时监控 - ${monitorNode?.name || ''}`" width="700px" @close="stopMonitor">
      <div v-if="monitorStats" style="padding: 10px">
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="monitor-card">
              <div class="monitor-title">GPU 利用率</div>
              <el-progress type="dashboard" :percentage="Math.round(monitorStats.gpu_utilization)" :color="gpuColor(monitorStats.gpu_utilization)" :width="120" />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="monitor-card">
              <div class="monitor-title">显存使用</div>
              <el-progress type="dashboard" :percentage="vramPercent" :color="gpuColor(vramPercent)" :width="120" />
              <div style="font-size:13px;color:#909399;margin-top:8px">
                {{ monitorStats.gpu_vram_used_gb }} / {{ monitorStats.gpu_vram_total_gb }} GB
              </div>
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="16" style="margin-top:20px">
          <el-col :span="8">
            <el-statistic title="GPU 温度" :value="monitorStats.gpu_temp" suffix="°C" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="CPU 利用率" :value="monitorStats.cpu_utilization" suffix="%" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="RAM 使用" :value="monitorStats.ram_used_gb" suffix="GB" />
          </el-col>
        </el-row>
      </div>
      <el-empty v-else description="等待数据..." />
      <template #footer>
        <span style="color:#909399;font-size:12px">每 5 秒自动刷新</span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computeApi } from '../api'

const nodes = ref([])
const loading = ref(false)
const connecting = ref(false)
const showAddRemote = ref(false)
const adding = ref(false)
const showMonitor = ref(false)
const monitorNode = ref(null)
const monitorStats = ref(null)
let monitorTimer = null

const remoteForm = ref({
  name: '', host: '', ssh_port: 22, ssh_user: 'root',
  ssh_key_path: '', python_path: 'python3', working_dir: '/data',
})

const onlineCount = computed(() => nodes.value.filter(n => n.status === 'online').length)
const busyCount = computed(() => nodes.value.filter(n => n.status === 'busy').length)
const totalGpus = computed(() => nodes.value.filter(n => n.status !== 'offline').reduce((s, n) => s + n.gpu_count, 0))
const totalVram = computed(() => nodes.value.filter(n => n.status !== 'offline').reduce((s, n) => s + n.gpu_total_vram_gb, 0).toFixed(0))
const vramPercent = computed(() => {
  if (!monitorStats.value || !monitorStats.value.gpu_vram_total_gb) return 0
  return Math.round(monitorStats.value.gpu_vram_used_gb / monitorStats.value.gpu_vram_total_gb * 100)
})

const statusType = (s) => ({ online: 'success', busy: 'warning', offline: 'info', error: 'danger' }[s] || 'info')
const statusLabel = (s) => ({ online: '在线', busy: '运行中', offline: '离线', error: '错误' }[s] || s)
const gpuColor = (v) => v > 90 ? '#F56C6C' : v > 70 ? '#E6A23C' : '#67C23A'

const loadNodes = async () => {
  loading.value = true
  try { nodes.value = await computeApi.list() }
  finally { loading.value = false }
}

const handleAutoConnect = async () => {
  connecting.value = true
  try {
    const result = await computeApi.autoConnectLocal()
    ElMessage.success(result.message || '本机算力已连接')
    loadNodes()
  } catch (e) {
    // error handled by interceptor
  } finally { connecting.value = false }
}

const handleConnect = async (id) => {
  try {
    await computeApi.connect(id)
    ElMessage.success('节点已连接')
    loadNodes()
  } catch (e) {}
}

const handleDisconnect = async (id) => {
  await computeApi.disconnect(id)
  ElMessage.success('已断开')
  loadNodes()
}

const handleDelete = async (id) => {
  await ElMessageBox.confirm('确认删除该算力节点？', '警告', { type: 'warning' })
  await computeApi.delete(id)
  ElMessage.success('已删除')
  loadNodes()
}

const handleAddRemote = async () => {
  if (!remoteForm.value.name || !remoteForm.value.host) {
    ElMessage.warning('请填写节点名称和主机地址')
    return
  }
  adding.value = true
  try {
    const node = await computeApi.create({ ...remoteForm.value, node_type: 'remote_ssh' })
    // 创建后自动连接
    await computeApi.connect(node.id, {
      ssh_user: remoteForm.value.ssh_user,
      ssh_key_path: remoteForm.value.ssh_key_path,
      ssh_port: remoteForm.value.ssh_port,
      python_path: remoteForm.value.python_path,
      working_dir: remoteForm.value.working_dir,
    })
    ElMessage.success('远程节点已创建并连接')
    showAddRemote.value = false
    remoteForm.value = { name: '', host: '', ssh_port: 22, ssh_user: 'root', ssh_key_path: '', python_path: 'python3', working_dir: '/data' }
    loadNodes()
  } catch (e) {
  } finally { adding.value = false }
}

const startMonitor = (node) => {
  monitorNode.value = node
  showMonitor.value = true
  const poll = async () => {
    try {
      monitorStats.value = await computeApi.heartbeat(node.id)
      // 同时更新列表中的数据
      const idx = nodes.value.findIndex(n => n.id === node.id)
      if (idx >= 0) {
        nodes.value[idx].gpu_utilization = monitorStats.value.gpu_utilization
        nodes.value[idx].gpu_vram_used_gb = monitorStats.value.gpu_vram_used_gb
        nodes.value[idx].gpu_temp = monitorStats.value.gpu_temp
        nodes.value[idx].cpu_utilization = monitorStats.value.cpu_utilization
        nodes.value[idx].ram_used_gb = monitorStats.value.ram_used_gb
      }
    } catch (e) {
      stopMonitor()
    }
  }
  poll()
  monitorTimer = setInterval(poll, 5000)
}

const stopMonitor = () => {
  if (monitorTimer) { clearInterval(monitorTimer); monitorTimer = null }
  monitorStats.value = null
}

onMounted(loadNodes)
onUnmounted(stopMonitor)
</script>

<style scoped>
.mb-20 { margin-bottom: 20px; }
.monitor-card { text-align: center; padding: 10px; }
.monitor-title { font-size: 14px; color: #909399; margin-bottom: 12px; }
</style>
