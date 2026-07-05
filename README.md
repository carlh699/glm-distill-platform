# GLM-Distill-Platform

基于智谱 GLM 系列的大模型蒸馏 MLOps 平台，提供从数据管理、蒸馏训练、评估对比到模型部署的全流程能力。

## 架构

```
┌─────────────────────────────────────────────────────┐
│                    Web Frontend                     │
│            Vue3 + Element Plus + ECharts            │
├──────────────┬──────────────┬───────────────────────┤
│  任务管理     │  模型对比     │  蒸馏配置/可视化       │
├──────────────┴──────────────┴───────────────────────┤
│                   FastAPI Backend                    │
│           REST API + WebSocket 实时推送                │
├──────────────┬──────────────┬───────────────────────┤
│  数据管理     │  评估引擎     │  部署管理 (vLLM)        │
├──────────────┴──────────────┴───────────────────────┤
│                 Training Engine                       │
│  PyTorch + HF Transformers + DeepSpeed + Celery       │
├─────────────────────────────────────────────────────┤
│              Storage & Tracking                      │
│  PostgreSQL │ Redis │ MinIO │ MLflow                 │
└─────────────────────────────────────────────────────┘
```

## 核心功能

1. **蒸馏策略**
   - 黑盒蒸馏（Logits-based KD）
   - 黑盒蒸馏（Response-based KD）
   - 多教师蒸馏
   - 渐进式蒸馏

2. **数据管理**
   - 训练数据集上传与管理
   - Teacher 模型推理生成（soft labels / response）
   - 数据质量过滤与增强

3. **训练管理**
   - 分布式训练（DeepSpeed ZeRO）
   - 混合精度训练
   - 训练过程实时监控
   - 断点续训

4. **评估对比**
   - 自动评测（Perplexity, BLEU, ROUGE）
   - Teacher vs Student 对比
   - 性能基准测试

5. **模型部署**
   - vLLM 推理服务
   - A/B Testing

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url>
cd glm-distill-platform

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 GLM API Key、模型路径等

# 3. 一键启动所有服务
docker compose up -d

# 4. 访问
# Web UI:  http://localhost:3000
# API Docs: http://localhost:8000/docs
# MLflow:  http://localhost:5000
# MinIO:   http://localhost:9001
```

## 支持的 GLM 模型

| 角色 | 模型 | 参数量 |
|------|------|--------|
| Teacher | GLM-4-Plus / GLM-4-9B | 9B+ |
| Teacher | GLM-5 (API) | 300B+ |
| Student | GLM-4-9B-Chat | 9B |
| Student | ChatGLM3-6B | 6B |
| Student | ChatGLM3-6B-INT4 | 6B (量化) |

## License

MIT
