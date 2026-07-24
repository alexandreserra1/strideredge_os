"""Evolução pessoal: isola atleta/modelo/vista antes de comparar métricas."""

import json
import uuid
from datetime import datetime, timedelta

from analytics.form_progress import FormProgressService
from core.database import get_connection


def _insert(user_id, cadence, *, backend="blazepose33", version="full-1", view="lateral",
            reliable=True, created_at=None):
    aid = str(uuid.uuid4())
    metrics = {"reliable": reliable, "view": view, "joint_angle_space": "image_2d",
               "cadence_spm": cadence, "ground_contact_ms": 240.0}
    get_connection().execute(
        "INSERT INTO form_analyses (analysis_id, user_id, status, view, backend_effective, "
        "model_version, metrics, created_at) VALUES (?, ?, 'done', ?, ?, ?, ?, ?)",
        [aid, user_id, view, backend, version, json.dumps(metrics), created_at])


def test_progress_compara_so_o_mesmo_atleta_e_assinatura():
    user, other = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        start = datetime(2026, 1, 1, 12, 0, 0)
        # O contrato mais recente é Blaze/2D. Timestamps explícitos mantêm a
        # prova determinística, independentemente da precisão do banco.
        _insert(user, 120, backend="yolo17", created_at=start)  # exclui
        for minute, cadence in enumerate((160, 164, 168), start=1):
            _insert(user, cadence, created_at=start + timedelta(minutes=minute))
        _insert(other, 100)                          # outro atleta: nunca entra
        out = FormProgressService().get(user)
        cadence = next(m for m in out["metrics"] if m["metric"] == "cadence_spm")
        assert out["status"] == "ok"
        assert out["comparable_analyses"] == 3 and out["excluded_incompatible"] == 1
        assert cadence["baseline"] == 160.0 and cadence["current"] == 168.0 and cadence["delta"] == 8.0
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE user_id IN (?, ?)", [user, other])


def test_progress_recusa_amostra_insuficiente_ou_nao_confiavel():
    user = str(uuid.uuid4())
    try:
        _insert(user, 160)
        _insert(user, 170, reliable=False)
        out = FormProgressService().get(user)
        assert out["status"] == "insufficient_history"
        assert out["comparable_analyses"] == 1 and out["metrics"] == []
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE user_id = ?", [user])
