import { defineStore } from 'pinia'

/** 校准到期看板的筛选状态：放在 Pinia 里，跳到设备台账再回来时条件不丢。 */
export const useCalibrationDashboardStore = defineStore('calibrationDashboard', {
  state: () => ({
    /** 临近到期区间（天）：7、30、90 */
    windowDays: 30,
    /** 趋势图时间段（天）：30、90、180 */
    rangeDays: 90,
    /** 校准方式筛选，空串表示全部 */
    method: '',
    /** 设备编号或名称关键字 */
    deviceKeyword: '',
  }),
  actions: {
    reset() {
      this.windowDays = 30
      this.rangeDays = 90
      this.method = ''
      this.deviceKeyword = ''
    },
  },
})
