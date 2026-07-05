import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const readView = (name) => readFileSync(new URL(`../src/views/${name}.vue`, import.meta.url), 'utf8')

test('TaskDetail streams loss data and exposes task actions', () => {
  const source = readView('TaskDetail')

  assert.match(source, /new WebSocket/)
  assert.match(source, /\/api\/v1\/tasks\/\$\{route\.params\.id\}\/ws/)
  assert.match(source, /lossData\.value/)
  assert.match(source, /evaluationsApi\.trigger/)
  assert.match(source, /deploymentsApi\.create/)
  assert.match(source, /教师.*学生/s)
  assert.match(source, /评估模型/)
  assert.match(source, /部署模型/)
})

test('Evaluations renders a radar comparison for model metrics', () => {
  const source = readView('Evaluations')

  assert.match(source, /RadarChart/)
  assert.match(source, /RadarComponent/)
  assert.match(source, /radarChartOption/)
  assert.match(source, /perplexity/)
  assert.match(source, /bleu/)
  assert.match(source, /rouge_l/)
  assert.match(source, /inference_latency_ms/)
  assert.match(source, /model_size_mb/)
})

test('ComputeNodes heartbeats online nodes and warns on high GPU temperature', () => {
  const source = readView('ComputeNodes')

  assert.match(source, /heartbeatTimer/)
  assert.match(source, /refreshOnlineNodeHeartbeats/)
  assert.match(source, /computeApi\.heartbeat/)
  assert.match(source, /setInterval\(refreshOnlineNodeHeartbeats,\s*5000\)/)
  assert.match(source, /gpuTempType/)
  assert.match(source, />\s*80/)
  assert.match(source, /高温/)
})
