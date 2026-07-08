"""Análise de forma — endpoints + ciclo processing->done com motor FAKE (sem Rust/ffmpeg)."""

import json
import time

from fastapi.testclient import TestClient

from api.form import FormService
from api.main import app
from api.deps import get_form_service
from core.database import get_connection

client = TestClient(app)

FAKE_METRICS = {"frames": 100, "fps": 30.0, "detection_rate_pct": 98.0,
                "cadence_spm": 172.0, "asymmetry_pct": 4.2, "vertical_oscillation_pct": 7.1}


class FakeFormService(FormService):
    """Substitui o subprocess do motor por métricas fixas (hermético)."""

    def _process(self, analysis_id, original):
        get_connection().execute(
            "UPDATE form_analyses SET status='done', video_path=?, metrics=? WHERE analysis_id=?",
            [str(original.parent / "overlay.mp4"), json.dumps(FAKE_METRICS), analysis_id])


def _wait_done(aid, tries=50):
    for _ in range(tries):
        r = client.get(f"/api/v1/form/{aid}").json()
        if r["status"] != "processing":
            return r
        time.sleep(0.05)
    raise AssertionError("não processou a tempo")


def test_upload_processa_e_devolve_metricas(tmp_path):
    app.dependency_overrides[get_form_service] = FakeFormService
    try:
        r = client.post("/api/v1/form", files={"video": ("run.mp4", b"fake-bytes", "video/mp4")})
        assert r.status_code == 201
        aid = r.json()["analysis_id"]
        done = _wait_done(aid)
        assert done["status"] == "done"
        assert done["metrics"]["cadence_spm"] == 172.0
        # lista encontra a análise
        assert any(a["analysis_id"] == aid for a in client.get("/api/v1/form").json())
    finally:
        app.dependency_overrides.clear()
        get_connection().execute("DELETE FROM form_analyses")


def test_get_inexistente_404():
    assert client.get("/api/v1/form/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/api/v1/form/nao-uuid").status_code == 404
