<template>
  <el-container class="app-container">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon size="28" color="#409EFF"><Cpu /></el-icon>
        <span class="logo-text">GLM 蒸馏平台</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        background-color="#1d1e2c"
        text-color="#a0a3b1"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/models">
          <el-icon><Box /></el-icon>
          <span>模型管理</span>
        </el-menu-item>
        <el-menu-item index="/datasets">
          <el-icon><Folder /></el-icon>
          <span>数据集</span>
        </el-menu-item>
        <el-menu-item index="/tasks">
          <el-icon><Lightning /></el-icon>
          <span>蒸馏任务</span>
        </el-menu-item>
        <el-menu-item index="/evaluations">
          <el-icon><DataAnalysis /></el-icon>
          <span>评估对比</span>
        </el-menu-item>
        <el-menu-item index="/deployments">
          <el-icon><Upload /></el-icon>
          <span>模型部署</span>
        </el-menu-item>
        <el-menu-item index="/compute">
          <el-icon><Monitor /></el-icon>
          <span>算力节点</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div class="breadcrumb">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="topbar-right">
          <el-tag type="success" effect="dark" size="small">● 服务正常</el-tag>
          <el-avatar size="small" :icon="UserFilled" />
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { UserFilled } from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => route.path)
const currentPageTitle = computed(() => {
  const map = {
    '/dashboard': '仪表盘',
    '/models': '模型管理',
    '/datasets': '数据集',
    '/tasks': '蒸馏任务',
    '/evaluations': '评估对比',
    '/deployments': '模型部署',
    '/compute': '算力节点',
  }
  return map[route.path] || ''
})
</script>

<style scoped>
.app-container { height: 100vh; }
.sidebar {
  background: #1d1e2c;
  display: flex;
  flex-direction: column;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px;
  color: #fff;
}
.logo-text {
  font-size: 18px;
  font-weight: 600;
}
.sidebar-menu { border-right: none; flex: 1; }
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  height: 60px;
}
.topbar-right { display: flex; align-items: center; gap: 12px; }
.main-content { background: #f0f2f5; padding: 20px; }
</style>
