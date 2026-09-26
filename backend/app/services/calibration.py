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

# 看板口径：待校准看板数量与列表按「待校准」筛选后的条数保持一致；
# 设备台账里已停用的设备不再进入待校准。
DISABLED_INSTRUMENT_STATUS = "已停用"
RESULT_STATUSES = {"已合格", "不合格"}
# 趋势图支持的时间段：近 7 天按天、近 30 天按周、近 90 天按月分桶。
RANGE_OPTIONS = {"7d": 7, "30d": 30, "90d": 90}
DUE_DAY_OPTIONS = {7, 15, 30}


def _parse_date(value: Any) -> date | None:
    """把记录里的日期字段解析成 date；解析不了返回 None，不让脏数据弄挂看板。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


class CalibrationService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("校准编号", ""))]
        if status:
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

    def board(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        due_days: int = 30,
        range_key: str = "30d",
        today: date | None = None,
    ) -> dict[str, Any]:
        """校准到期看板：待校准数量与列表筛选口径一致，停用设备不进待校准。"""
        today = today or date.today()
        if due_days not in DUE_DAY_OPTIONS:
            due_days = 30
        if range_key not in RANGE_OPTIONS:
            range_key = "30d"
        rows = store.rows(MODULE)
        # 与列表接口完全相同的筛选逻辑，保证看板待校准数能对上列表条数。
        _, list_total = self.list_entries(keyword=keyword, status=status, page=1, size=len(rows) or 1)
        disabled = self._disabled_instruments()
        pending_rows = [
            row
            for row in self._filter_rows(rows, keyword=keyword, status=STATUS_ORDER[0])
            if str(row.get("关联设备", "")).strip() not in disabled
        ]
        device_groups = self._device_groups(rows, disabled=disabled, due_days=due_days, today=today)
        judged = [row for row in rows if row.get("status") in RESULT_STATUSES]
        record_count = len(rows)
        backlog = sum(len(group[key]) for group in device_groups for key in ("待校准", "临近到期", "已过期"))
        return {
            "pending_total": len(pending_rows),
            "list_total": list_total,
            "record_count": record_count,
            "due_days": due_days,
            "range": range_key,
            "device_groups": device_groups,
            "method_pass_rates": self._pass_rates(judged, "校准方式"),
            "material_pass_rates": self._pass_rates(judged, "标准物质"),
            "trend": self._trend(rows, range_key=range_key, today=today),
            "empty_reason": self._empty_reason(record_count=record_count, backlog=backlog),
        }

    def _filter_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        keyword: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("校准编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def _disabled_instruments(self) -> set[str]:
        """设备台账里已停用设备的编号与名称；这些设备不再进入待校准。"""
        disabled: set[str] = set()
        for row in store.rows(INSTRUMENT_MODULE):
            if row.get("status") != DISABLED_INSTRUMENT_STATUS:
                continue
            for field in ("设备编号", "设备名称"):
                name = str(row.get(field) or "").strip()
                if name:
                    disabled.add(name)
        return disabled

    def _device_groups(
        self,
        rows: list[dict[str, Any]],
        *,
        disabled: set[str],
        due_days: int,
        today: date,
    ) -> list[dict[str, Any]]:
        """按设备与校准周期分组，列出待校准、临近到期、已过期的校准编号。"""
        periods = self._instrument_periods()
        groups: dict[str, dict[str, Any]] = {}
        due_limit = today + timedelta(days=due_days)
        for row in rows:
            device = str(row.get("关联设备") or "").strip() or "未关联设备"
            code = str(row.get("校准编号") or "").strip()
            if not code:
                continue
            group = groups.setdefault(device, {
                "设备": device,
                "校准周期": periods.get(device, "—"),
                "待校准": [],
                "临近到期": [],
                "已过期": [],
            })
            next_date = _parse_date(row.get("下次校准日"))
            if row.get("status") == STATUS_ORDER[0]:
                # 已停用设备不进入待校准，其余按状态归入待校准。
                if device not in disabled:
                    group["待校准"].append(code)
            elif next_date is not None and next_date < today:
                group["已过期"].append(code)
            elif next_date is not None and next_date <= due_limit:
                group["临近到期"].append(code)
        ordered = [group for group in groups.values() if group["待校准"] or group["临近到期"] or group["已过期"]]
        return sorted(ordered, key=lambda group: group["设备"])

    def _instrument_periods(self) -> dict[str, str]:
        """从设备台账取校准周期，看板按设备展示时直接引用，不改台账数据。"""
        periods: dict[str, str] = {}
        for row in store.rows(INSTRUMENT_MODULE):
            period = str(row.get("校准周期") or "").strip()
            if not period:
                continue
            for field in ("设备编号", "设备名称"):
                name = str(row.get(field) or "").strip()
                if name:
                    periods.setdefault(name, period)
        return periods

    def _pass_rates(self, judged: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
        """按校准方式或标准物质统计合格率；没有判定结果的维度如实标为空。"""
        buckets: dict[str, dict[str, int]] = {}
        for row in judged:
            name = str(row.get(field) or "").strip() or "未填写"
            bucket = buckets.setdefault(name, {"total": 0, "passed": 0})
            bucket["total"] += 1
            if row.get("status") == "已合格":
                bucket["passed"] += 1
        rates = []
        for name, bucket in sorted(buckets.items()):
            total = bucket["total"]
            rates.append({
                "name": name,
                "total": total,
                "passed": bucket["passed"],
                "rate": round(bucket["passed"] * 100 / total, 1) if total else None,
            })
        return rates

    def _trend(self, rows: list[dict[str, Any]], *, range_key: str, today: date) -> list[dict[str, Any]]:
        """按时间段统计合格/不合格趋势：7 天按天、30 天按周、90 天按月。"""
        days = RANGE_OPTIONS[range_key]
        start = today - timedelta(days=days - 1)
        judged = [
            (parsed, row)
            for row in rows
            if row.get("status") in RESULT_STATUSES and (parsed := _parse_date(row.get("校准日期"))) is not None
        ]
        buckets: list[dict[str, Any]] = []
        if range_key == "7d":
            spans = [(start + timedelta(days=offset), start + timedelta(days=offset)) for offset in range(days)]
            labels = [span[0].strftime("%m-%d") for span in spans]
        elif range_key == "30d":
            spans = []
            cursor = start
            while cursor <= today:
                spans.append((cursor, min(cursor + timedelta(days=6), today)))
                cursor += timedelta(days=7)
            labels = [f"{span[0].strftime('%m-%d')}~{span[1].strftime('%m-%d')}" for span in spans]
        else:
            spans = []
            cursor = start.replace(day=1)
            while cursor <= today:
                month_end = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                spans.append((max(cursor, start), min(month_end, today)))
                cursor = month_end + timedelta(days=1)
            labels = [span[0].strftime("%Y-%m") for span in spans]
        for (span_start, span_end), label in zip(spans, labels):
            in_span = [row for parsed, row in judged if span_start <= parsed <= span_end]
            buckets.append({
                "label": label,
                "passed": sum(1 for row in in_span if row.get("status") == "已合格"),
                "failed": sum(1 for row in in_span if row.get("status") == "不合格"),
            })
        return buckets

    def _empty_reason(self, *, record_count: int, backlog: int) -> str | None:
        """空态说明：没有校准记录、或全部合格没有待办时，看板给出原因而不是空白。"""
        if record_count == 0:
            return "no_records"
        if backlog == 0:
            return "all_clear"
        return None
