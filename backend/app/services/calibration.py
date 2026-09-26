"""校准记录业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.store import store

MODULE = "calibration"
INSTRUMENT_MODULE = "instrument"
REQUIRED_FIELDS = ["校准编号", "关联设备", "校准方式"]
STATUS_ORDER = ["待校准", "校准中", "已合格", "不合格"]
ACTION_RULES = {"开始校准": "校准中", "判定合格": "已合格", "判定不合格": "不合格"}
NEGATIVE_ACTIONS = []

PENDING_STATUS = "待校准"
DEACTIVATED_STATUS = "已停用"
BUCKET_NAMES = ["待校准", "临近到期", "已过期"]
WINDOW_OPTIONS = {7, 30, 90}
RANGE_OPTIONS = {30: "day", 90: "week", 180: "month"}


def _parse_date(value: Any) -> date | None:
    """把 2026-09-26 这类字符串解析成日期；解析不了返回 None，由调用方决定兜底。"""
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


class CalibrationService:
    # ---------- 列表 ----------
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        device: str | None = None,
        method: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("校准编号", ""))]
        if device:
            rows = [row for row in rows if device in str(row.get("关联设备", ""))]
        if method:
            rows = [row for row in rows if method in str(row.get("校准方式", ""))]
        if status:
            if status == PENDING_STATUS:
                # 待校准口径与到期看板一致：已停用设备不再进入待校准
                rows = [row for row in rows if self._is_pending(row)]
            else:
                rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"校准记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于校准记录可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"校准记录已{action}"

    # ---------- 到期看板 ----------
    def dashboard(
        self,
        *,
        window_days: int = 30,
        range_days: int = 90,
        device: str | None = None,
        method: str | None = None,
    ) -> dict[str, Any]:
        """汇总到期区间分桶、合格率与趋势；待校准数量与列表「待校准」筛选同口径。"""
        today = date.today()
        rows = store.rows(MODULE)
        deadline = today + timedelta(days=window_days)

        devices: dict[str, dict[str, Any]] = {}
        bucket_counts = {name: 0 for name in BUCKET_NAMES}
        for row in rows:
            if self._device_deactivated(row):
                continue
            bucket = self._bucket_of(row, today, deadline)
            if bucket is None:
                continue
            bucket_counts[bucket] += 1
            entry = self._device_slot(devices, row)
            entry["buckets"][bucket].append(self._summary(row))

        device_rows = list(devices.values())
        if device:
            device_rows = [
                item for item in device_rows
                if device in str(item["设备编号"]) or device in str(item["设备名称"])
            ]
        if method:
            filtered = []
            for item in device_rows:
                buckets = {
                    name: [e for e in item["buckets"][name] if method in str(e["校准方式"])]
                    for name in BUCKET_NAMES
                }
                if any(buckets.values()):
                    filtered.append({**item, "buckets": buckets})
            device_rows = filtered

        return {
            "today": today.isoformat(),
            "window_days": window_days,
            "range_days": range_days,
            "records_total": len(rows),
            "pending_total": len(self.pending_entries()),
            "bucket_counts": bucket_counts,
            "devices": device_rows,
            "pass_rates": {
                "by_method": self._pass_rates(rows, "校准方式"),
                "by_material": self._pass_rates(rows, "标准物质"),
            },
            "trend": self._trend(rows, today, range_days),
        }

    def pending_entries(self) -> list[dict[str, Any]]:
        """待校准记录全集：列表筛选与看板计数共用这一份口径，保证两边条数相同。"""
        return [row for row in store.rows(MODULE) if self._is_pending(row)]

    def _is_pending(self, row: dict[str, Any]) -> bool:
        return row.get("status") == PENDING_STATUS and not self._device_deactivated(row)

    def _linked_instrument(self, row: dict[str, Any]) -> dict[str, Any] | None:
        """按设备编号或设备名称把校准记录挂到设备台账上；匹配不到就返回 None。"""
        text = str(row.get("关联设备") or "")
        if not text:
            return None
        for instrument in store.rows(INSTRUMENT_MODULE):
            code = str(instrument.get("设备编号") or "")
            name = str(instrument.get("设备名称") or "")
            if code and code in text:
                return instrument
            if name and name in text:
                return instrument
        return None

    def _device_deactivated(self, row: dict[str, Any]) -> bool:
        instrument = self._linked_instrument(row)
        if instrument is None:
            return False
        return (
            instrument.get("status") == DEACTIVATED_STATUS
            or instrument.get("设备状态") == DEACTIVATED_STATUS
        )

    def _bucket_of(self, row: dict[str, Any], today: date, deadline: date) -> str | None:
        """按状态与下次校准日把记录归入待校准、临近到期、已过期；其余不进看板。"""
        if row.get("status") == PENDING_STATUS:
            return "待校准"
        due = _parse_date(row.get("下次校准日"))
        if due is None:
            instrument = self._linked_instrument(row)
            due = _parse_date(instrument.get("校准到期日")) if instrument else None
        if due is None:
            return None
        if due < today:
            return "已过期"
        if due <= deadline:
            return "临近到期"
        return None

    def _device_slot(self, devices: dict[str, dict[str, Any]], row: dict[str, Any]) -> dict[str, Any]:
        instrument = self._linked_instrument(row)
        key = str(instrument.get("设备编号")) if instrument else str(row.get("关联设备") or "未关联设备")
        if key not in devices:
            devices[key] = {
                "设备编号": instrument.get("设备编号") if instrument else "—",
                "设备名称": instrument.get("设备名称") if instrument else str(row.get("关联设备") or "未关联设备"),
                "校准周期": instrument.get("校准周期") if instrument else "—",
                "校准到期日": instrument.get("校准到期日") if instrument else "—",
                "buckets": {name: [] for name in BUCKET_NAMES},
            }
        return devices[key]

    @staticmethod
    def _summary(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "校准编号": row.get("校准编号"),
            "校准方式": row.get("校准方式"),
            "标准物质": row.get("标准物质"),
            "校准结果": row.get("校准结果"),
            "校准日期": row.get("校准日期"),
            "下次校准日": row.get("下次校准日"),
            "校准状态": row.get("status"),
        }

    @staticmethod
    def _result_of(row: dict[str, Any]) -> bool | None:
        """判定单条记录合格与否；还没有结果的返回 None，不计入合格率。"""
        status = row.get("status")
        if status == "已合格":
            return True
        if status == "不合格":
            return False
        text = str(row.get("校准结果") or "")
        if "不合格" in text:
            return False
        if "合格" in text:
            return True
        return None

    def _pass_rates(self, rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            name = str(row.get(field) or "").strip() or "未填写"
            group = groups.setdefault(name, {"name": name, "total": 0, "passed": 0, "failed": 0})
            result = self._result_of(row)
            if result is None:
                continue
            group["total"] += 1
            group["passed" if result else "failed"] += 1
        items = []
        for group in groups.values():
            total = group["total"]
            items.append({**group, "rate": round(group["passed"] / total * 100, 1) if total else None})
        return sorted(items, key=lambda item: item["name"])

    def _trend(self, rows: list[dict[str, Any]], today: date, range_days: int) -> dict[str, Any]:
        granularity = RANGE_OPTIONS.get(range_days, "week")
        start = today - timedelta(days=range_days - 1)
        buckets: dict[str, dict[str, Any]] = {}
        for row in rows:
            day = _parse_date(row.get("校准日期"))
            if day is None or day < start or day > today:
                continue
            label = self._trend_label(day, granularity)
            point = buckets.setdefault(label, {"label": label, "total": 0, "passed": 0, "failed": 0})
            point["total"] += 1
            result = self._result_of(row)
            if result is True:
                point["passed"] += 1
            elif result is False:
                point["failed"] += 1
        points = []
        for label in sorted(buckets):
            point = buckets[label]
            done = point["passed"] + point["failed"]
            point["rate"] = round(point["passed"] / done * 100, 1) if done else None
            points.append(point)
        return {"granularity": granularity, "start": start.isoformat(), "points": points}

    @staticmethod
    def _trend_label(day: date, granularity: str) -> str:
        if granularity == "day":
            return day.isoformat()
        if granularity == "week":
            monday = day - timedelta(days=day.weekday())
            return f"{monday.isoformat()} 周"
        return day.strftime("%Y-%m")
