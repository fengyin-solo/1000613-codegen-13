import { defineStore } from 'pinia'

// 校准到期看板的查看条件：放在 pinia 里，从设备台账等页面返回后
// 到期区间、趋势时间段与筛选条件都保持原样，不用重新选择。
export const useCalibrationBoardStore = defineStore('calibrationBoard', {
  state: () => ({
    dueDays: 30,
    range: '30d',
    status: '',
  }),
  actions: {
    setDueDays(days: number) {
      this.dueDays = days
    },
    setRange(range: string) {
      this.range = range
    },
    setStatus(status: string) {
      this.status = status
    },
  },
})
