<template>
  <section class="page" data-module="calibration">
    <header class="page-head">
      <div>
        <h2>校准记录管理</h2>
        <p class="page-desc">维护校准记录，围绕校准编号、关联设备、校准方式、标准物质做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/calibration/dashboard">校准到期看板</RouterLink>
        <button class="btn primary" type="button" @click="openCreate">登记校准记录</button>
        <button class="btn" type="button" @click="exportRows">导出校准记录清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>校准状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无校准记录数据，可先登记校准记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条校准记录记录</span>
      <span v-if="statusFilter === '待校准'" class="filter-hint">
        待校准口径与校准到期看板一致：已停用设备不计入
      </span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/calibration'
const columns = ["校准编号", "关联设备", "校准方式", "标准物质", "校准结果", "校准日期", "下次校准日", "校准状态"]
const actions = ["开始校准", "判定合格", "判定不合格"]
const statuses = ["待校准", "校准中", "已合格", "不合格"]
const stats = [{"label": "待校准记录", "value": 0}, {"label": "校准合格率", "value": 0}, {"label": "不合格设备", "value": 0}]

const route = useRoute()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '校准记录登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('校准记录动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '校准记录操作失败'
  }
}

function buildQuery() {
  const params = new URLSearchParams()
  const keyword = (filters.value['校准编号'] ?? '').trim()
  const device = (filters.value['关联设备'] ?? '').trim()
  const method = (filters.value['校准方式'] ?? '').trim()
  if (keyword) params.set('keyword', keyword)
  if (device) params.set('device', device)
  if (method) params.set('method', method)
  if (statusFilter.value) params.set('status', statusFilter.value)
  return params.toString()
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) {
      throw new Error('校准记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '校准记录列表读取失败'
  }
}

onMounted(() => {
  const initial = route.query.status
  if (typeof initial === 'string' && statuses.includes(initial)) {
    statusFilter.value = initial
  }
  void reload()
})
</script>
