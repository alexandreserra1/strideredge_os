"""Resumo interno de shadow: agrega divergência sem vazar atleta ou vídeo."""

import json
import uuid

from analytics.pose_shadow_summary import PoseShadowSummaryService
from core.database import get_connection


def _report(*, status="completed", cadence=None, detection=None, reliable_match=True):
    report = {"status": status}
    if status == "completed":
        report.update({
            "backend": {"effective": "yolo17", "model_version": "yolo11n-pose"},
            "comparison": {
                "reliable_match": reliable_match,
                "joint_angle_space_match": True,
                "metric_deltas": {} if cadence is None else {"cadence_spm": cadence},
            },
        })
        if detection is not None:
            report["comparison"]["detection_rate_delta_pct"] = detection
    return report


def _insert(report, *, primary="blazepose33", version="full-1"):
    analysis_id = str(uuid.uuid4())
    get_connection().execute(
        "INSERT INTO form_analyses (analysis_id, status, backend_effective, model_version, shadow_report) "
        "VALUES (?, 'done', ?, ?, ?)",
        [analysis_id, primary, version, json.dumps(report)])
    return analysis_id


def test_resumo_agrega_deltas_sem_retornar_identidade_da_analise():
    ids = []
    try:
        ids.extend((_insert(_report(cadence=-10.0, detection=-2.0)),
                    _insert(_report(cadence=-20.0, detection=-4.0, reliable_match=False)),
                    _insert(_report(status="skipped"))))
        out = PoseShadowSummaryService().summary()
        assert out["reports"] == {"total": 3, "completed": 2, "skipped": 1, "failed": 0, "invalid": 0}
        comparison = out["comparisons"][0]
        assert comparison["primary"]["backend"] == "blazepose33"
        assert comparison["shadow"]["backend"] == "yolo17"
        assert comparison["reliable_mismatches"] == 1
        assert comparison["metric_deltas"]["cadence_spm"]["median_delta"] == -15.0
        assert comparison["detection_rate_delta_pct"]["p95_abs_delta"] == 4.0
        assert not any(str(analysis_id) in json.dumps(out) for analysis_id in ids)
    finally:
        get_connection().execute(
            "DELETE FROM form_analyses WHERE analysis_id IN (?, ?, ?)", ids)


def test_resumo_ignora_relatorio_malformado():
    analysis_id = str(uuid.uuid4())
    try:
        get_connection().execute(
            "INSERT INTO form_analyses (analysis_id, status, shadow_report) VALUES (?, 'done', ?)",
            [analysis_id, "not-json"])
        out = PoseShadowSummaryService().summary()
        assert out["reports"]["invalid"] >= 1
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE analysis_id = ?", [analysis_id])
