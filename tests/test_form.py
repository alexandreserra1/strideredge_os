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
        # Este fake exercita o contrato legado do motor. Declarar o backend
        # evita que o teste dependa do default de produção (BlazePose).
        super().__init__(queue=InlineQueue(), backend="yolo17")

    def _run_engine(self, original, overlay, view, snapshot, draw_overlay=True):
        return dict(self.frontal_metrics) if view == "frontal" else dict(FAKE_METRICS)


def _headers(access_token):
    return {"X-Analysis-Token": access_token} if access_token else {}


def _wait_done(aid, access_token, tries=50):
    for _ in range(tries):
        r = client.get(f"/api/v1/form/{aid}", headers=_headers(access_token)).json()
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
        access_token = r.json()["access_token"]
        done = _wait_done(aid, access_token)
        assert done["status"] == "done"
        assert done["metrics"]["cadence_spm"] == 172.0
        assert done["backend"]["effective"] == "yolo17"
        # convidado acessa apenas pela capability; não existe lista pública.
        assert client.get("/api/v1/form").status_code == 401
    finally:
        app.dependency_overrides.clear()
        get_connection().execute("DELETE FROM form_analyses")


def test_processamento_persiste_duracoes_sem_expor_no_endpoint():
    """A telemetria operacional fica no banco, separada das métricas e da resposta do atleta."""
    app.dependency_overrides[get_form_service] = FakeFormService
    try:
        r = client.post("/api/v1/form", files={"video": ("run.mp4", b"fake-bytes", "video/mp4")})
        aid, token = r.json()["analysis_id"], r.json()["access_token"]
        done = _wait_done(aid, token)
        assert "processing_report" not in done
        raw = get_connection().execute(
            "SELECT processing_report FROM form_analyses WHERE analysis_id=?", [aid]
        ).fetchone()[0]
        report = json.loads(raw)
        assert report["schema_version"] == 1
        assert report["stages"]["metrics"]["status"] == "completed"
        assert report["stages"]["metrics"]["duration_ms"] >= 0
        assert report["stages"]["overlay"]["status"] == "completed"
        assert "path" not in json.dumps(report).lower()
    finally:
        app.dependency_overrides.clear()
        get_connection().execute("DELETE FROM form_analyses")


def test_upload_ignora_backend_enviado_pelo_cliente():
    """Não existe campo de seleção no endpoint: multipart extra não pode alterar o job."""
    app.dependency_overrides[get_form_service] = FakeFormService
    try:
        r = client.post("/api/v1/form", data={"backend": "blazepose33"},
                        files={"video": ("run.mp4", b"fake-bytes", "video/mp4")})
        done = _wait_done(r.json()["analysis_id"], r.json()["access_token"])
        assert done["backend"]["requested"] == "yolo17"
        assert done["backend"]["effective"] == "yolo17"
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
        done = _wait_done(r.json()["analysis_id"], r.json()["access_token"])
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
        done = _wait_done(r.json()["analysis_id"], r.json()["access_token"])
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


def test_analise_nao_vaza_entre_atletas():
    app.dependency_overrides[get_form_service] = FakeFormService
    try:
        a = client.post("/api/v1/auth/register", json={"name": "A", "email": "a@id.test", "password": "corrida123"}).json()
        b = client.post("/api/v1/auth/register", json={"name": "B", "email": "b@id.test", "password": "corrida123"}).json()
        owner = {"Authorization": f"Bearer {a['token']}"}
        other = {"Authorization": f"Bearer {b['token']}"}
        out = client.post("/api/v1/form", headers=owner,
                          files={"video": ("run.mp4", b"fake-bytes", "video/mp4")}).json()
        aid = out["analysis_id"]
        assert client.get(f"/api/v1/form/{aid}", headers=other).status_code == 404
        assert client.get("/api/v1/form", headers=other).json() == []
        assert client.get(f"/api/v1/form/{aid}", headers=owner).status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_connection().execute("DELETE FROM form_analyses")
        get_connection().execute("DELETE FROM auth_users WHERE email IN (?, ?)", ["a@id.test", "b@id.test"])


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
    svc = FormService(queue=q, backend="yolo17")
    try:
        out = svc.create(b"bytes", "run.mp4")
        assert out["status"] == "processing"
        assert q.calls and q.calls[0][0] == "_process"        # enfileirou o processamento
        row = svc.get(out["analysis_id"])
        assert row["status"] == "processing"                  # não rodou inline (fila não executou)
    finally:
        get_connection().execute("DELETE FROM form_analyses")


def test_capability_de_convidado_expira_e_e_purgada():
    import uuid as _uuid
    from datetime import datetime, timedelta
    from api.form import VIDEOS_DIR, purge_expired_guest_analyses

    class _NoRunQueue(JobQueue):
        def start(self):
            pass
        def enqueue(self, fn, *args, **kwargs):
            return True

    svc = FormService(queue=_NoRunQueue(), backend="yolo17")
    out = svc.create(b"bytes", "run.mp4")
    aid, token = out["analysis_id"], out["access_token"]
    try:
        get_connection().execute(
            "UPDATE form_analyses SET access_token_expires_at = ? WHERE analysis_id = ?",
            [datetime.utcnow() - timedelta(seconds=1), aid])
        assert svc.get_authorized(aid, None, token) is None
        assert purge_expired_guest_analyses() == 1
        assert svc.get(aid) is None
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE analysis_id = ?", [aid])
        FormService._discard_dir(VIDEOS_DIR / aid)


def test_upload_rejeita_content_length_acima_do_limite():
    app.dependency_overrides[get_form_service] = FakeFormService
    try:
        r = client.post("/api/v1/form", headers={"Content-Length": str(303 * 1024 * 1024)},
                        files={"video": ("run.mp4", b"fake-bytes", "video/mp4")})
        assert r.status_code == 413
    finally:
        app.dependency_overrides.clear()


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
