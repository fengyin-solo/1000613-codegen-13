<template>
  <div class="trend-chart">
    <div class="legend">
      <span><i class="legend-passed"></i>合格</span>
      <span><i class="legend-failed"></i>不合格</span>
      <span><i class="legend-rate"></i>合格率</span>
    </div>
    <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" class="trend-svg" role="img" aria-label="校准趋势图">
      <line
        v-for="tick in gridTicks"
        :key="tick"
        class="grid"
        :x1="PAD.left"
        :x2="WIDTH - PAD.right"
        :y1="rateY(tick)"
        :y2="rateY(tick)"
      />
      <text
        v-for="tick in gridTicks"
        :key="`tick-${tick}`"
        class="axis-label"
        :x="WIDTH - PAD.right + 6"
        :y="rateY(tick) + 4"
      >{{ tick }}%</text>
      <text
        v-for="tick in countTicks"
        :key="`count-${tick}`"
        class="axis-label"
        :x="PAD.left - 6"
        :y="countY(tick) + 4"
        text-anchor="end"
      >{{ tick }}</text>

      <g v-for="(point, i) in points" :key="point.label">
        <rect
          class="bar-passed"
          :x="barX(i)"
          :y="countY(point.passed)"
          :width="barWidth"
          :height="barHeight(point.passed)"
        />
        <rect
          class="bar-failed"
          :x="barX(i)"
          :y="countY(point.passed + point.failed)"
          :width="barWidth"
          :height="barHeight(point.failed)"
        />
        <text
          v-if="showLabel(i)"
          class="axis-label"
          :x="barX(i) + barWidth / 2"
          :y="HEIGHT - 8"
          text-anchor="middle"
        >{{ point.label }}</text>
      </g>

      <path v-for="segment in rateSegments" :key="segment" class="rate-line" :d="segment" fill="none" />
      <circle v-for="dot in rateDots" :key="dot.key" class="rate-dot" :cx="dot.x" :cy="dot.y" r="3">
        <title>{{ dot.key }}：合格率 {{ dot.rate }}%</title>
      </circle>

      <line class="axis" :x1="PAD.left" :x2="WIDTH - PAD.right" :y1="HEIGHT - PAD.bottom" :y2="HEIGHT - PAD.bottom" />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export type TrendPoint = {
  label: string
  total: number
  passed: number
  failed: number
  rate: number | null
}

const props = defineProps<{ points: TrendPoint[] }>()

const WIDTH = 760
const HEIGHT = 240
const PAD = { top: 16, right: 48, bottom: 28, left: 40 }
const INNER_W = WIDTH - PAD.left - PAD.right
const INNER_H = HEIGHT - PAD.top - PAD.bottom

const gridTicks = [0, 25, 50, 75, 100]

const maxCount = computed(() => Math.max(1, ...props.points.map((point) => point.total)))
const countTicks = computed(() => {
  const top = maxCount.value
  return top <= 1 ? [0, top] : [0, Math.round(top / 2), top]
})

const step = computed(() => (props.points.length ? INNER_W / props.points.length : INNER_W))
const barWidth = computed(() => Math.max(8, step.value * 0.55))

function barX(index: number) {
  return PAD.left + index * step.value + (step.value - barWidth.value) / 2
}

function countY(count: number) {
  return PAD.top + INNER_H - (count / maxCount.value) * INNER_H
}

function barHeight(count: number) {
  return (count / maxCount.value) * INNER_H
}

function rateY(rate: number) {
  return PAD.top + INNER_H - (rate / 100) * INNER_H
}

function centerX(index: number) {
  return PAD.left + index * step.value + step.value / 2
}

function showLabel(index: number) {
  const total = props.points.length
  if (total <= 10) return true
  return index % Math.ceil(total / 10) === 0
}

const rateDots = computed(() =>
  props.points
    .map((point, index) => ({ point, index }))
    .filter(({ point }) => point.rate !== null)
    .map(({ point, index }) => ({
      key: point.label,
      x: centerX(index),
      y: rateY(point.rate as number),
      rate: point.rate as number,
    })),
)

const rateSegments = computed(() => {
  const segments: string[] = []
  let current: string[] = []
  props.points.forEach((point, index) => {
    if (point.rate === null) {
      if (current.length) {
        segments.push(`M ${current.join(' L ')}`)
        current = []
      }
      return
    }
    current.push(`${centerX(index)},${rateY(point.rate)}`)
  })
  if (current.length) {
    segments.push(`M ${current.join(' L ')}`)
  }
  return segments
})
</script>
