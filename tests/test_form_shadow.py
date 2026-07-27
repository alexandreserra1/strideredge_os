"""Shadow BlazePose→YOLO: telemetria interna sem alterar a análise do atleta."""

import json
import uuid
from pathlib import Path

import pytest

from api.form import FormService, PoseBackendSnapshot
from core import config
from core.database import get_connection
from core.jobs import JobQueue


class InlineQueue(JobQueue):
    def start(self):
        pass

    def enqueue(self, fn, *args, **kwargs):
        fn(*args, **kwargs)
        return True


class MultiResolver:
    def __init__(self, root):
        self.root = root

    def resolve(self, backend):
        if backend == "yolo17":
            return PoseBackendSnapshot(
                requested="yolo17", effective="yolo17", model_version="yolo11n-pose",
                model_assets={"yolo11n-pose.onnx": "a" * 64},
                subprocess_env={"STRIDE_MODEL": str(self.root / "yolo.onnx")},
            )
        return PoseBackendSnapshot(
            requested="blazepose33", effective="blazepose33", model_version="pose-landmarker-full",
            model_assets={"runtime": "b" * 64, "pose_landmarker": "c" * 64},
            subprocess_env={
                "STRIDE_MEDIAPIPE_LIB": str(self.root / "libmediapipe.dylib"),
                "STRIDE_BLAZEPOSE_MODEL": str(self.root / "pose_landmarker_full.task"),
            },
        )


class FakeEngineFormService(FormService):
    def __init__(self, *args, fail_shadow=False, main_reliable=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_shadow = fail_shadow
        self.main_reliable = main_reliable
        self.calls = []

    def _run_engine(self, original, overlay, view, snapshot, draw_overlay=True):
        if draw_overlay:   # passada de overlay (cosmética) — não é execução de análise/shadow
            return {"reliable": True, "frames": 100, "fps": 30.0, "reason": "ok"}
        self.calls.append(snapshot.effective)
        if snapshot.effective == "yolo17" and self.fail_shadow:
            raise RuntimeError("asset candidate unavailable")
        return {
            "reliable": self.main_reliable if snapshot.effective == "blazepose33" else True,
            "detection_rate_pct": 98.0 if snapshot.effective == "blazepose33" else 96.5,
            "frames": 100,
            "fps": 30.0,
            "reason": "ok",
            "joint_angle_space": "image_2d",
            "cadence_spm": 172.0 if snapshot.effective == "blazepose33" else 151.0,
            "ground_contact_ms": 230.0 if snapshot.effective == "blazepose33" else 240.0,
        }


def _analysis(tmp_path):
    aid = str(uuid.uuid4())
    original = tmp_path / "original.mp4"
    original.write_bytes(b"video")
    get_connection().execute(
        "INSERT INTO form_analyses (analysis_id, status, view) VALUES (?, 'processing', 'lateral')",
        [aid])
    return aid, original


def _saved(aid):
    row = get_connection().execute(
        "SELECT status, metrics, shadow_report FROM form_analyses WHERE analysis_id=?", [aid]).fetchone()
    return row[0], json.loads(row[1]), json.loads(row[2]) if row[2] else None


def _service(tmp_path, **kwargs):
    resolver = MultiResolver(tmp_path)
    main = resolver.resolve("blazepose33")
    return FakeEngineFormService(
        queue=InlineQueue(), backend="blazepose33", shadow_backend="yolo17",
        backend_resolver=resolver, **kwargs), main


def test_shadow_persiste_comparacao_sem_trocar_metricas_principais(tmp_path):
    svc, main = _service(tmp_path)
    aid, original = _analysis(tmp_path)
    try:
        svc._process(aid, original, snapshot=main)
        status, metrics, report = _saved(aid)
        assert status == "done"
        assert metrics["cadence_spm"] == 172.0  # YOLO não substitui dado do atleta.
        assert svc.calls == ["blazepose33", "yolo17"]
        assert report["status"] == "completed"
        assert report["backend"]["effective"] == "yolo17"
        assert report["comparison"]["detection_rate_delta_pct"] == -1.5
        assert report["comparison"]["metric_deltas"]["cadence_spm"] == -21.0
        assert report["comparison"]["joint_angle_space_match"] is True
        assert str(tmp_path) not in json.dumps(report)  # paths não são persistidos.
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE analysis_id=?", [aid])


def test_shadow_pula_captura_principal_nao_confiavel(tmp_path):
    svc, main = _service(tmp_path, main_reliable=False)
    aid, original = _analysis(tmp_path)
    try:
        svc._process(aid, original, snapshot=main)
        status, _, report = _saved(aid)
        assert status == "done"
        assert svc.calls == ["blazepose33"]
        assert report == {"status": "skipped", "reason": "primary_unreliable"}
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE analysis_id=?", [aid])


def test_falha_do_shadow_nao_falha_analise_principal(tmp_path):
    svc, main = _service(tmp_path, fail_shadow=True)
    aid, original = _analysis(tmp_path)
    try:
        svc._process(aid, original, snapshot=main)
        status, metrics, report = _saved(aid)
        assert status == "done"
        assert metrics["cadence_spm"] == 172.0
        assert report["status"] == "failed"
        assert report["reason"] == "shadow_execution_failed"
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE analysis_id=?", [aid])


def test_sem_shadow_nao_cria_relatorio_nem_execucao_extra(tmp_path):
    resolver = MultiResolver(tmp_path)
    main = resolver.resolve("blazepose33")
    svc = FakeEngineFormService(queue=InlineQueue(), backend="blazepose33", shadow_backend=None,
                                backend_resolver=resolver)
    aid, original = _analysis(tmp_path)
    try:
        svc._process(aid, original, snapshot=main)
        status, _, report = _saved(aid)
        assert status == "done"
        assert svc.calls == ["blazepose33"]
        assert report is None
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE analysis_id=?", [aid])


def test_config_shadow_ausente_nao_muda_baseline_e_invalida_nao_derruba_boot(monkeypatch):
    assert config.pose_shadow_backend({}) is None
    with pytest.raises(config.ConfigurationError):
        config.pose_shadow_backend({"STRIDE_POSE_SHADOW_BACKEND": "path-do-cliente"})
    monkeypatch.setenv("STRIDE_POSE_SHADOW_BACKEND", "path-do-cliente")
    assert config.summary()["pose_shadow_backend"] == "invalid"
