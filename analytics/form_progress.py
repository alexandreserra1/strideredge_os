"""Evolução pessoal de forma — comparação temporal, não ranking clínico/populacional.

Lê análises já persistidas e só compara capturas compatíveis do MESMO atleta. Não mistura
backends, versões ou geometrias de ângulo: uma troca de motor deve iniciar uma nova linha de base,
não fabricar uma melhora/piora numérica.
"""

import json
import math
from statistics import median
from typing import Optional

from core.database import get_connection


_METRICS = {
    "cadence_spm": {"label": "Cadência", "unit": "spm"},
    "vertical_oscillation_pct": {"label": "Oscilação vertical", "unit": "%"},
    "knee_contact_deg": {"label": "Joelho no apoio", "unit": "°"},
    "hip_contact_deg": {"label": "Quadril no apoio", "unit": "°"},
    "trunk_lean_deg": {"label": "Inclinação do tronco", "unit": "°"},
    "ground_contact_ms": {"label": "Contato com o solo", "unit": "ms"},
    "flight_ms": {"label": "Tempo de voo", "unit": "ms"},
    "pelvic_drop_deg": {"label": "Queda pélvica", "unit": "°"},
    "knee_valgus_deg": {"label": "Valgo de joelho", "unit": "°"},
}
_MIN_ANALYSES = 3


class FormProgressService:
    """Consulta e resume a evolução comparável de um único atleta autenticado."""

    def get(self, user_id: str) -> dict:
        records = self._reliable_records(user_id)
        if not records:
            return self._insufficient(0, 0)
        latest = records[-1]
        group = [r for r in records if r["signature"] == latest["signature"]]
        if len(group) < _MIN_ANALYSES:
            return self._insufficient(len(group), len(records), latest["signature"])
        return {
            "status": "ok",
            "comparable_analyses": len(group),
            "excluded_incompatible": len(records) - len(group),
            "signature": latest["signature"],
            "metrics": self._summaries(group),
            "caveat": (
                "Comparação com suas próprias capturas confiáveis e compatíveis; mudança numérica "
                "não é diagnóstico nem prova de causa."),
        }

    @staticmethod
    def _insufficient(comparable: int, total: int, signature: Optional[dict] = None) -> dict:
        return {
            "status": "insufficient_history",
            "comparable_analyses": comparable,
            "excluded_incompatible": max(0, total - comparable),
            "signature": signature,
            "metrics": [],
            "caveat": (
                f"São necessárias {_MIN_ANALYSES} análises confiáveis e comparáveis para mostrar "
                "evolução pessoal."),
        }

    @staticmethod
    def _signature(row: tuple, metrics: dict) -> dict:
        return {
            "view": metrics.get("view") or row[2] or "lateral",
            "backend": row[3] or "unknown",
            "model_version": row[4] or "unknown",
            "joint_angle_space": metrics.get("joint_angle_space") or "unknown",
        }

    def _reliable_records(self, user_id: str) -> list:
        rows = get_connection().execute(
            "SELECT analysis_id, created_at, view, backend_effective, model_version, metrics "
            "FROM form_analyses WHERE user_id=? AND status='done' AND metrics IS NOT NULL "
            "ORDER BY created_at ASC, analysis_id ASC", [user_id]).fetchall()
        records = []
        for row in rows:
            try:
                metrics = json.loads(row[5])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(metrics, dict) or metrics.get("reliable") is not True:
                continue
            records.append({
                "analysis_id": str(row[0]), "created_at": str(row[1]), "metrics": metrics,
                "signature": self._signature(row, metrics),
            })
        return records

    @staticmethod
    def _summaries(records: list) -> list:
        # Com três análises, compara a primeira à última; com mais, medianas dos terços inicial e
        # recente amortecem um vídeo atípico sem transformar uma tendência em treino de modelo.
        window = max(1, len(records) // 3)
        baseline, recent = records[:window], records[-window:]
        out = []
        for key, meta in _METRICS.items():
            before = [r["metrics"].get(key) for r in baseline]
            now = [r["metrics"].get(key) for r in recent]
            before = [float(v) for v in before if isinstance(v, (int, float)) and math.isfinite(v)]
            now = [float(v) for v in now if isinstance(v, (int, float)) and math.isfinite(v)]
            if not before or not now:
                continue
            initial, current = median(before), median(now)
            out.append({
                "metric": key, **meta, "baseline": round(initial, 1), "current": round(current, 1),
                "delta": round(current - initial, 1), "baseline_samples": len(before),
                "current_samples": len(now),
            })
        return out
