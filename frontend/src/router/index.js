import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/models', name: 'Models', component: () => import('../views/Models.vue') },
  { path: '/datasets', name: 'Datasets', component: () => import('../views/Datasets.vue') },
  { path: '/tasks', name: 'Tasks', component: () => import('../views/Tasks.vue') },
  { path: '/tasks/:id', name: 'TaskDetail', component: () => import('../views/TaskDetail.vue') },
  { path: '/evaluations', name: 'Evaluations', component: () => import('../views/Evaluations.vue') },
  { path: '/deployments', name: 'Deployments', component: () => import('../views/Deployments.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
