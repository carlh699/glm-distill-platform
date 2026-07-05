import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

// ─── Models ───
export const modelsApi = {
  list: (params) => api.get('/models', { params }),
  get: (id) => api.get(`/models/${id}`),
  create: (data) => api.post('/models', data),
  delete: (id) => api.delete(`/models/${id}`),
  presets: () => api.get('/models/presets/list'),
}

// ─── Datasets ───
export const datasetsApi = {
  list: (params) => api.get('/datasets', { params }),
  get: (id) => api.get(`/datasets/${id}`),
  create: (formData) => api.post('/datasets', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  delete: (id) => api.delete(`/datasets/${id}`),
  preview: (id, n) => api.get(`/datasets/${id}/preview`, { params: { n } }),
}

// ─── Tasks ───
export const tasksApi = {
  list: (params) => api.get('/tasks', { params }),
  get: (id) => api.get(`/tasks/${id}`),
  create: (data) => api.post('/tasks', data),
  cancel: (id) => api.post(`/tasks/${id}/cancel`),
  delete: (id) => api.delete(`/tasks/${id}`),
}

// ─── Evaluations ───
export const evaluationsApi = {
  list: (params) => api.get('/evaluations', { params }),
  get: (id) => api.get(`/evaluations/${id}`),
  trigger: (taskId) => api.post(`/evaluations/task/${taskId}`),
}

// ─── Deployments ───
export const deploymentsApi = {
  list: (params) => api.get('/deployments', { params }),
  get: (id) => api.get(`/deployments/${id}`),
  create: (data) => api.post('/deployments', data),
  stop: (id) => api.post(`/deployments/${id}/stop`),
  delete: (id) => api.delete(`/deployments/${id}`),
}

export default api
