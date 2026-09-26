<template>
  <section class="page" data-module="calibration-dashboard">
    <header class="page-head">
      <div>
        <h2>校准到期看板</h2>
        <p class="page-desc">
          按设备与校准周期汇总待校准、临近到期与已过期的校准编号，跟踪校准方式与标准物质的合格率；已停用设备不再进入待校准。
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/calibration">查看校准记录列表</RouterLink>
        <button class="btn" type="button" @click="reload">刷新看板</button>
      </div>
    </header>

    <div v-if="dashboard && dashboard.records_total === 0" class="empty-panel">
      暂无校准记录：请先在「校准记录」页登记校准记录，看板会自动汇总到期区间、合格率与趋势。
    </div>

    <template v-else-if="dashboard">
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">待校准（与记录列表筛选口径一致）</span>
          <strong class="stat-value">{{ dashboard.pending_total }}</strong>
          <RouterLink class="stat-link" :to="{ path: '/calibration', query: { status: '待校准' } }">
            核对列表条数
          </RouterLink>
        </article>
        <article class="stat-card">
          <span class="stat-label">临近到期（未来 {{ dashboard.window_days }} 天）</span>
          <strong class="stat-value warn">{{ dashboard.bucket_counts['临近到期'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">已过期</span>
          <strong class="stat-value bad">{{ dashboard.bucket_counts['已过期'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">涉及设备（当前筛选）</span>
          <strong class="stat-value">{{ dashboard.devices.length }}</strong>
        </article>
      </div>

      <form class="filter-bar" @submit.prevent="reload">
        <label class="filter-item">
          <span>到期区间</span>
          <select v-model.number="store.windowDays" @change="reload">
            <option v-for="option in windowOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="filter-item">
          <span>校准方式</span>
          <select v-model="store.method">
            <option value="">全部方式</option>
            <option v-for="name in methodOptions" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>设备检索</span>
          <input v-model.trim="store.deviceKeyword" placeholder="按设备编号或名称检索" />
        </label>
        <button class="btn" type="submit">应用条件</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
        <span class="filter-hint">筛选条件在跳转设备台账后返回时自动保留</span>
      </form>

      <section class="panel">
        <header class="panel-head">
          <h3 class="panel-title">设备到期分桶（按设备与校准周期）</h3>
          <span class="panel-note">已停用设备不参与统计</span>
        </header>
        <table v-if="dashboard.devices.length" class="data-table">
          <thead>
            <tr>
              <th>设备编号</th>
              <th>设备名称</th>
              <th>校准周期</th>
              <th>校准到期日</th>
              <th>待校准</th>
              <th>临近到期</th>
              <th>已过期</th>
              <th>设备台账</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="device in dashboard.devices" :key="device.设备编号">
              <td>{{ device.设备编号 }}</td>
              <td>{{ device.设备名称 }}</td>
              <td>{{ device.校准周期 }}</td>
              <td>{{ device.校准到期日 }}</td>
              <td v-for="bucket in bucketMeta" :key="bucket.key">
                <span
                  v-for="entry in device.buckets[bucket.key]"
                  :key="entry.id"
                  class="chip"
                  :class="bucket.className"
                  :title="`校准方式：${entry.校准方式 ?? '—'}；标准物质：${entry.标准物质 ?? '—'}`"
                >
                  {{ entry.校准编号 }}<em v-if="entry.下次校准日"> · {{ entry.下次校准日 }}</em>
                </span>
                <span v-if="!device.buckets[bucket.key].length">—</span>
              </td>
              <td>
                <RouterLink class="link" to="/instrument">查看设备</RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="hasActiveFilters" class="empty-state">
          没有符合筛选条件的设备校准记录，可调整或重置筛选条件。
        </p>
        <p v-else class="empty-state">
          当前到期区间内没有待校准、临近到期或已过期的校准记录，设备校准均在有效期内。
        </p>
      </section>

      <div class="panel-grid">
        <section class="panel">
          <header class="panel-head">
            <h3 class="panel-title">校准方式合格率</h3>
          </header>
          <table v-if="dashboard.pass_rates.by_method.length" class="data-table">
            <thead>
              <tr><th>校准方式</th><th>已完成</th><th>合格</th><th>不合格</th><th>合格率</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in dashboard.pass_rates.by_method" :key="item.name">
                <td>{{ item.name }}</td>
                <td>{{ item.total }}</td>
                <td>{{ item.passed }}</td>
                <td>{{ item.failed }}</td>
                <td>
                  <template v-if="item.rate !== null">
                    <div class="rate-bar"><span :style="{ width: `${item.rate}%` }"></span></div>
                    {{ item.rate }}%
                  </template>
                  <span v-else>—（暂无结果）</span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="empty-state">暂无校准方式数据。</p>
        </section>

        <section class="panel">
          <header class="panel-head">
            <h3 class="panel-title">标准物质合格率</h3>
          </header>
          <table v-if="dashboard.pass_rates.by_material.length" class="data-table">
            <thead>
              <tr><th>标准物质</th><th>已完成</th><th>合格</th><th>不合格</th><th>合格率</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in dashboard.pass_rates.by_material" :key="item.name">
                <td>{{ item.name }}</td>
                <td>{{ item.total }}</td>
                <td>{{ item.passed }}</td>
                <td>{{ item.failed }}</td>
                <td>
                  <template v-if="item.rate !== null">
                    <div class="rate-bar"><span :style="{ width: `${item.rate}%` }"></span></div>
                    {{ item.rate }}%
                  </template>
                  <span v-else>—（暂无结果）</span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="empty-state">暂无标准物质数据。</p>
        </section>
      </div>
      <p v-if="!hasCompletedResults" class="empty-state">
        暂无已出结果的校准记录，合格率将在判定合格或不合格后生成。
      </p>

      <section class="panel">
        <header class="panel-head">
          <h3 class="panel-title">校准趋势</h3>
          <div class="segment">
            <button
              v-for="option in rangeOptions"
              :key="option.value"
              type="button"
              :class="{ active: store.rangeDays === option.value }"
              @click="switchRange(option.value)"
            >
              {{ option.label }}
            </button>
          </div>
        </header>
        <TrendChart v-if="dashboard.trend.points.length" :points="dashboard.trend.points" />
        <p v-else class="empty-state">所选时间段内没有校准记录，可切换时间段或先登记校准。</p>
      </section>
    </template>

    <footer class="page-foot">
      <span v-if="dashboard">数据日期：{{ dashboard.today }} · 共 {{ dashboard.records_total }} 条校准记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useCalibrationDashboardStore } from '@/stores/calibrationDashboard'
import TrendChart, { type TrendPoint } from './TrendChart.vue'

type CalibrationSummary = {
  id: number
  校准编号: string
  校准方式: string | null
  标准物质: string | null
  校准结果: string | null
  校准日期: string | null
  下次校准日: string | null
  校准状态: string
}

type BucketKey = '待校准' | '临近到期' | '已过期'

type DeviceBuckets = {
  设备编号: string
  设备名称: string
  校准周期: string
  校准到期日: string
  buckets: Record<BucketKey, CalibrationSummary[]>
}

type PassRate = { name: string; total: number; passed: number; failed: number; rate: number | null }

type DashboardPayload = {
  today: string
  window_days: number
  range_days: number
  records_total: number
  pending_total: number
  bucket_counts: Record<BucketKey, number>
  devices: DeviceBuckets[]
  pass_rates: { by_method: PassRate[]; by_material: PassRate[] }
  trend: { granularity: string; start: string; points: TrendPoint[] }
}

const ENDPOINT = '/api/calibration/dashboard'
const bucketMeta: { key: BucketKey; className: string }[] = [
  { key: '待校准', className: 'pending' },
  { key: '临近到期', className: 'due' },
  { key: '已过期', className: 'overdue' },
]
const windowOptions = [
  { value: 7, label: '未来 7 天' },
  { value: 30, label: '未来 30 天' },
  { value: 90, label: '未来 90 天' },
]
const rangeOptions = [
  { value: 30, label: '近 30 天' },
  { value: 90, label: '近 90 天' },
  { value: 180, label: '近 180 天' },
]

const store = useCalibrationDashboardStore()
const dashboard = ref<DashboardPayload | null>(null)
const errorMessage = ref('')

const methodOptions = computed(() => {
  const names = dashboard.value?.pass_rates.by_method.map((item) => item.name) ?? []
  if (store.method && !names.includes(store.method)) {
    names.push(store.method)
  }
  return names
})

const hasActiveFilters = computed(() => Boolean(store.method || store.deviceKeyword))

const hasCompletedResults = computed(() => {
  const rates = dashboard.value?.pass_rates
  if (!rates) return false
  return [...rates.by_method, ...rates.by_material].some((item) => item.total > 0)
})

function switchRange(value: number) {
  store.rangeDays = value
  void reload()
}

function resetFilters() {
  store.reset()
  void reload()
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams({
    window: String(store.windowDays),
    range: String(store.rangeDays),
  })
  if (store.method) params.set('method', store.method)
  if (store.deviceKeyword) params.set('device', store.deviceKeyword)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('校准到期看板读取失败')
    }
    dashboard.value = (await response.json()) as DashboardPayload
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '校准到期看板读取失败'
  }
}

onMounted(reload)
</script>
