"""Análise de forma — endpoints + ciclo processing->done com motor FAKE (sem Rust/ffmpeg)."""

import json
import time

from fastapi.testclient import TestClient

from api.form import FormService
from api.main import app
from api.deps import get_form_service
from core.database import get_connection
from core.jobs import JobQueue

client = TestClient(app)

FAKE_METRICS = {"frames": 100, "fps": 30.0, "detection_rate_pct": 98.0,
                "cadence_spm": 172.0, "asymmetry_pct": 4.2, "vertical_oscillation_pct": 7.1,
                "reliable": True, "quality_note": None}


class InlineQueue(JobQueue):
    """Fila síncrona pra teste: roda o job na hora (sem thread) — determinístico."""

    def start(self):
        pass

    def enqueue(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


FAKE_FRONTAL_OK = {"frames": 100, "fps": 30.0, "detection_rate_pct": 96.0,
                   "pelvic_drop_deg": 12.3, "knee_valgus_deg": 9.4,
                   "reliable": True, "quality_note": None, "view": "frontal"}

FAKE_FRONTAL_BAD = {"frames": 100, "fps": 30.0, "detection_rate_pct": 40.0,
                    "pelvic_drop_deg": None, "knee_valgus_deg": None,
                    "reliable": False, "reason": "not_frontal",
                    "quality_note": "filme de frente", "view": "frontal"}


class FakeFormService(FormService):
    """Substitui o subprocess do motor por métricas fixas (hermético). Reusa a fusão real
    (fuse_metrics) — só o motor Rust é fingido, o resto do fluxo é o de produção."""

    frontal_metrics = FAKE_FRONTAL_OK

    def __init__(self):
        super().__init__(queue=InlineQueue())

    def _run_engine(self, original, overlay, view):
        return dict(self.frontal_metrics) if view == "frontal" else dict(FAKE_METRICS)


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


def test_upload_lateral_mais_frontal_funde_metricas(tmp_path):
    """lateral+frontal: métricas sagitais do lateral + queda pélvica/valgo do frontal confiável."""
    app.dependency_overrides[get_form_service] = FakeFormService
    try:
        r = client.post("/api/v1/form", files={
            "video": ("lat.mp4", b"fake-lateral", "video/mp4"),
            "video_frontal": ("front.mp4", b"fake-frontal", "video/mp4")})
        assert r.status_code == 201
        done = _wait_done(r.json()["analysis_id"])
        m = done["metrics"]
        assert done["view"] == "combined"
        assert m["cadence_spm"] == 172.0                       # base sagital preservada
        assert m["pelvic_drop_deg"] == 12.3 and m["knee_valgus_deg"] == 9.4   # do frontal
        assert m["metric_sources"]["frontal_plane"] == "frontal"
    finally:
        app.dependency_overrides.clear()
        get_connection().execute("DELETE FROM form_analyses")


def test_upload_frontal_nao_confiavel_fatores_none(tmp_path):
    """Frontal ruim: pelvic_drop/knee_valgus ficam None (não chuta) + nota; lateral segue valendo."""
    class _BadFrontal(FakeFormService):
        frontal_metrics = FAKE_FRONTAL_BAD

    app.dependency_overrides[get_form_service] = _BadFrontal
    try:
        r = client.post("/api/v1/form", files={
            "video": ("lat.mp4", b"fake-lateral", "video/mp4"),
            "video_frontal": ("front.mp4", b"bad-frontal", "video/mp4")})
        done = _wait_done(r.json()["analysis_id"])
        m = done["metrics"]
        assert m["cadence_spm"] == 172.0                       # lateral intacto
        assert m["pelvic_drop_deg"] is None and m["knee_valgus_deg"] is None
        assert m["metric_sources"]["frontal_plane"] == "dropped_unreliable"
        assert "refilme" in m["frontal_note"].lower()
    finally:
        app.dependency_overrides.clear()
        get_connection().execute("DELETE FROM form_analyses")


def test_get_inexistente_404():
    assert client.get("/api/v1/form/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/api/v1/form/nao-uuid").status_code == 404


def test_create_enfileira_em_vez_de_processar_inline():
    """create() deve ENFILEIRAR (não bloquear): com uma fila que NÃO roda o job, a análise
    fica em 'processing' e a resposta volta na hora."""
    import uuid as _uuid

    class _NoRunQueue(JobQueue):
        def __init__(self):
            self.calls = []
        def start(self):
            pass
        def enqueue(self, fn, *args, **kwargs):
            self.calls.append((fn.__name__, args))   # registra, mas NÃO roda

    q = _NoRunQueue()
    svc = FormService(queue=q)
    try:
        out = svc.create(b"bytes", "run.mp4")
        assert out["status"] == "processing"
        assert q.calls and q.calls[0][0] == "_process"        # enfileirou o processamento
        row = svc.get(out["analysis_id"])
        assert row["status"] == "processing"                  # não rodou inline (fila não executou)
    finally:
        get_connection().execute("DELETE FROM form_analyses")


def test_recover_orphaned_marca_failed():
    """Recuperação de crash: 'processing' órfão vira 'failed' com aviso."""
    import uuid as _uuid
    from api.form import recover_orphaned_analyses

    aid = str(_uuid.uuid4())
    con = get_connection()
    con.execute("INSERT INTO form_analyses (analysis_id, status, modality) VALUES (?, 'processing', 'run')", [aid])
    try:
        n = recover_orphaned_analyses()
        assert n >= 1
        row = con.execute("SELECT status, error FROM form_analyses WHERE analysis_id=?", [aid]).fetchone()
        assert row[0] == "failed" and "reenvie" in row[1].lower()
    finally:
        con.execute("DELETE FROM form_analyses WHERE analysis_id=?", [aid])
