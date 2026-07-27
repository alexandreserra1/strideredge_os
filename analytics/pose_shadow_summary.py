"""Resumo privado da telemetria BlazePose→YOLO durante a migração.

Não lê vídeo, usuário, analysis_id ou paths. O objetivo é decidir com números agregados quando o
shadow pode ser desligado, sem transformar divergência entre modelos em veredito clínico.
"""

import json
import math
from collections import defaultdict
from statistics import median
from typing import Optional

from core.database import get_connection


class PoseShadowSummaryService:
    """Agrupa relatórios shadow persistidos para operação interna, sem expor dados de atletas."""

    def __init__(self, connection=None):
        self.connection = connection

    def summary(self) -> dict:
        connection = self.connection or get_connection()
        rows = connection.execute(
            "SELECT backend_effective, model_version, shadow_report "
            "FROM form_analyses WHERE shadow_report IS NOT NULL").fetchall()
        counters = {"total": 0, "completed": 0, "skipped": 0, "failed": 0, "invalid": 0}
        groups = {}
        for primary_backend, primary_version, raw_report in rows:
            report = self._parse(raw_report)
            if report is None:
                counters["invalid"] += 1
                continue
            counters["total"] += 1
            status = report.get("status")
            if status not in ("completed", "skipped", "failed"):
                counters["invalid"] += 1
                continue
            counters[status] += 1
            if status != "completed":
                continue
            shadow = report.get("backend")
            if not isinstance(shadow, dict) or not isinstance(shadow.get("effective"), str):
                counters["invalid"] += 1
                continue
            key = (primary_backend or "unknown", primary_version or "unknown",
                   shadow["effective"], shadow.get("model_version") or "unknown")
            groups.setdefault(key, self._empty_group())
            self._add(groups[key], report.get("comparison"))
        return {
            "reports": counters,
            "comparisons": [self._render(key, group) for key, group in sorted(groups.items())],
            "caveat": (
                "Deltas são shadow menos BlazePose na mesma captura; eles medem divergência entre "
                "implementações, não erro clínico nem melhora do atleta."),
        }

    @staticmethod
    def _parse(raw_report: object) -> Optional[dict]:
        try:
            report = json.loads(raw_report)
        except (TypeError, json.JSONDecodeError):
            return None
        return report if isinstance(report, dict) else None

    @staticmethod
    def _empty_group() -> dict:
        return {"completed": 0, "reliable_mismatches": 0, "angle_space_mismatches": 0,
                "detection_deltas": [], "metric_deltas": defaultdict(list)}

    @staticmethod
    def _add(group: dict, comparison: object) -> None:
        if not isinstance(comparison, dict):
            return
        group["completed"] += 1
        if comparison.get("reliable_match") is False:
            group["reliable_mismatches"] += 1
        if comparison.get("joint_angle_space_match") is False:
            group["angle_space_mismatches"] += 1
        value = comparison.get("detection_rate_delta_pct")
        if PoseShadowSummaryService._finite(value):
            group["detection_deltas"].append(float(value))
        deltas = comparison.get("metric_deltas")
        if isinstance(deltas, dict):
            for metric, delta in deltas.items():
                if isinstance(metric, str) and PoseShadowSummaryService._finite(delta):
                    group["metric_deltas"][metric].append(float(delta))

    @staticmethod
    def _finite(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    @staticmethod
    def _stats(values: list) -> Optional[dict]:
        if not values:
            return None
        ordered_abs = sorted(abs(value) for value in values)
        p95_index = max(0, math.ceil(len(ordered_abs) * 0.95) - 1)
        return {
            "samples": len(values),
            "median_delta": round(median(values), 3),
            "median_abs_delta": round(median(ordered_abs), 3),
            "p95_abs_delta": round(ordered_abs[p95_index], 3),
        }

    def _render(self, key: tuple, group: dict) -> dict:
        primary_backend, primary_version, shadow_backend, shadow_version = key
        return {
            "primary": {"backend": primary_backend, "model_version": primary_version},
            "shadow": {"backend": shadow_backend, "model_version": shadow_version},
            "completed": group["completed"],
            "reliable_mismatches": group["reliable_mismatches"],
            "joint_angle_space_mismatches": group["angle_space_mismatches"],
            "detection_rate_delta_pct": self._stats(group["detection_deltas"]),
            "metric_deltas": {
                metric: self._stats(values)
                for metric, values in sorted(group["metric_deltas"].items())
            },
        }
