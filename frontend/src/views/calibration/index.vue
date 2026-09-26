<template>
  <section class="page" data-module="calibration">
    <header class="page-head">
      <div>
        <h2>校准记录管理</h2>
        <p class="page-desc">维护校准记录，围绕校准编号、关联设备、校准方式、标准物质做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记校准记录</button>
        <button class="btn" type="button" @click="exportRows">导出校准记录清单</button>
      </div>
    </header>

    <section class="board" data-module="calibration-board">
      <div class="board-head">
        <div>
          <h3>校准到期看板</h3>
          <p class="board-desc">按设备与校准周期汇总待校准、临近到期与已过期，待校准口径与下方列表筛选一致。</p>
        </div>
        <div class="board-controls">
          <label class="board-control">
            <span>到期区间</span>
            <select v-model.number="boardStore.dueDays" @change="loadBoard">
              <option v-for="days in dueDayOptions" :key="days" :value="days">未来 {{ days }} 天</option>
            </select>
          </label>
          <div class="range-tabs" role="tablist">
            <button
              v-for="option in rangeOptions"
              :key="option.value"
              type="button"
              class="range-tab"
              :class="{ active: boardStore.range === option.value }"
              @click="switchRange(option.value)"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
      </div>

      <p v-if="boardError" class="error-text">{{ boardError }}</p>

      <div v-if="board && board.empty_reason === 'no_records'" class="board-empty">
        暂无校准记录，看板没有可汇总的数据；登记校准记录后，这里会按设备列出待校准与到期情况。
      </div>

      <template v-else-if="board">
        <div class="stat-row">
          <article class="stat-card">
            <span class="stat-label">待校准（口径同列表筛选）</span>
            <strong class="stat-value">{{ board.pending_total }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">临近到期（{{ board.due_days }} 天内）</span>
            <strong class="stat-value">{{ dueSoonTotal }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">已过期</span>
            <strong class="stat-value">{{ overdueTotal }}</strong>
          </article>
        </div>

        <div v-if="board.empty_reason === 'all_clear'" class="board-empty">
          全部校准均已合格，当前没有待校准、临近到期或已过期的校准任务。
        </div>

        <table v-else class="data-table board-table">
          <thead>
            <tr>
              <th>设备</th>
              <th>校准周期</th>
              <th>待校准</th>
              <th>临近到期</th>
              <th>已过期</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="group in board.device_groups" :key="group.设备">
              <td>{{ group.设备 }}</td>
              <td>{{ group.校准周期 }}</td>
              <td>{{ group.待校准.join('、') || '—' }}</td>
              <td>{{ group.临近到期.join('、') || '—' }}</td>
              <td>{{ group.已过期.join('、') || '—' }}</td>
            </tr>
          </tbody>
        </table>

        <div class="board-panels">
          <section class="board-panel">
            <h4>校准方式合格率</h4>
            <table class="data-table">
              <thead>
                <tr><th>校准方式</th><th>判定数</th><th>合格数</th><th>合格率</th></tr>
              </thead>
              <tbody>
                <tr v-for="item in board.method_pass_rates" :key="item.name">
                  <td>{{ item.name }}</td>
                  <td>{{ item.total }}</td>
                  <td>{{ item.passed }}</td>
                  <td>{{ formatRate(item.rate) }}</td>
                </tr>
                <tr v-if="!board.method_pass_rates.length">
                  <td colspan="4" class="empty-state">暂无已判定的校准结果</td>
                </tr>
              </tbody>
            </table>
          </section>
          <section class="board-panel">
            <h4>标准物质合格率</h4>
            <table class="data-table">
              <thead>
                <tr><th>标准物质</th><th>判定数</th><th>合格数</th><th>合格率</th></tr>
              </thead>
              <tbody>
                <tr v-for="item in board.material_pass_rates" :key="item.name">
                  <td>{{ item.name }}</td>
                  <td>{{ item.total }}</td>
                  <td>{{ item.passed }}</td>
                  <td>{{ formatRate(item.rate) }}</td>
                </tr>
                <tr v-if="!board.material_pass_rates.length">
                  <td colspan="4" class="empty-state">暂无已判定的校准结果</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>

        <section class="board-panel">
          <h4>合格趋势（{{ currentRangeLabel }}）</h4>
          <div v-if="hasTrendValues" class="trend-chart">
            <div v-for="bucket in board.trend" :key="bucket.label" class="trend-item">
              <div class="trend-bars">
                <span
                  class="trend-bar passed"
                  :style="{ height: barHeight(bucket.passed) }"
                  :title="`合格 ${bucket.passed}`"
                ></span>
                <span
                  class="trend-bar failed"
                  :style="{ height: barHeight(bucket.failed) }"
                  :title="`不合格 ${bucket.failed}`"
                ></span>
              </div>
              <span class="trend-label">{{ bucket.label }}</span>
            </div>
          </div>
          <p v-else class="board-empty">该时间段内没有已判定的校准记录，趋势图暂无数据。</p>
          <p class="trend-legend">
            <span class="legend-dot passed"></span>合格
            <span class="legend-dot failed"></span>不合格
          </p>
        </section>
      </template>
    </section>

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
        <select v-model="boardStore.status">
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
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useCalibrationBoardStore } from '@/stores/calibrationBoard'

type Row = Record<string, string | number | null>
type BoardGroup = { 设备: string; 校准周期: string; 待校准: string[]; 临近到期: string[]; 已过期: string[] }
type PassRate = { name: string; total: number; passed: number; rate: number | null }
type TrendBucket = { label: string; passed: number; failed: number }
type Board = {
  pending_total: number
  list_total: number
  record_count: number
  due_days: number
  range: string
  device_groups: BoardGroup[]
  method_pass_rates: PassRate[]
  material_pass_rates: PassRate[]
  trend: TrendBucket[]
  empty_reason: string | null
}

const ENDPOINT = '/api/calibration'
const columns = ["校准编号", "关联设备", "校准方式", "标准物质", "校准结果", "校准日期", "下次校准日", "校准状态"]
const actions = ["开始校准", "判定合格", "判定不合格"]
const statuses = ["待校准", "校准中", "已合格", "不合格"]
const stats = [{"label": "待校准记录", "value": 0}, {"label": "校准合格率", "value": 0}, {"label": "不合格设备", "value": 0}]
const dueDayOptions = [7, 15, 30]
const rangeOptions = [
  { label: '近 7 天', value: '7d' },
  { label: '近 30 天', value: '30d' },
  { label: '近 90 天', value: '90d' },
]

const boardStore = useCalibrationBoardStore()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const board = ref<Board | null>(null)
const boardError = ref('')

const dueSoonTotal = computed(() =>
  (board.value?.device_groups ?? []).reduce((sum, group) => sum + group.临近到期.length, 0),
)
const overdueTotal = computed(() =>
  (board.value?.device_groups ?? []).reduce((sum, group) => sum + group.已过期.length, 0),
)
const trendMax = computed(() =>
  Math.max(1, ...(board.value?.trend ?? []).map((bucket) => Math.max(bucket.passed, bucket.failed))),
)
const hasTrendValues = computed(() =>
  (board.value?.trend ?? []).some((bucket) => bucket.passed > 0 || bucket.failed > 0),
)
const currentRangeLabel = computed(() =>
  rangeOptions.find((option) => option.value === boardStore.range)?.label ?? '',
)

function barHeight(value: number) {
  return `${Math.round((value / trendMax.value) * 100)}%`
}

function formatRate(rate: number | null) {
  return rate === null ? '暂无判定' : `${rate}%`
}

function switchRange(range: string) {
  boardStore.setRange(range)
  void loadBoard()
}

function resetFilters() {
  filters.value = {}
  boardStore.setStatus('')
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

async function loadBoard() {
  boardError.value = ''
  const params = new URLSearchParams({
    due_days: String(boardStore.dueDays),
    range: boardStore.range,
  })
  if (boardStore.status) {
    params.set('status', boardStore.status)
  }
  try {
    const response = await request(`${ENDPOINT}/board?${params.toString()}`)
    if (!response.ok) {
      throw new Error('校准到期看板读取失败')
    }
    board.value = (await response.json()) as Board
  } catch (error) {
    boardError.value = error instanceof Error ? error.message : '校准到期看板读取失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>)
  if (boardStore.status) {
    query.set('status', boardStore.status)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('校准记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '校准记录列表读取失败'
  }
  await loadBoard()
}

onMounted(reload)
</script>
