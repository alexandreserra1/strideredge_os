"""Seleção server-side de backend de pose e proveniência por análise."""

import pytest

from api.form import (BackendConfigurationError, FormService, PoseBackendSnapshot,
                      VIDEOS_DIR)
from core.database import get_connection
from core.jobs import JobQueue


class NoRunQueue(JobQueue):
    """Captura o job sem executar Rust/ffmpeg."""

    def __init__(self):
        self.calls = []

    def start(self):
        pass

    def enqueue(self, fn, *args, **kwargs):
        self.calls.append((fn, args, kwargs))
        return True


class FixedResolver:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.requested = []

    def resolve(self, backend):
        self.requested.append(backend)
        return self.snapshot


def _halpe_snapshot(tmp_path) -> PoseBackendSnapshot:
    detector = tmp_path / "detector.onnx"
    pose = tmp_path / "pose.onnx"
    detector.write_bytes(b"detector")
    pose.write_bytes(b"pose")
    return PoseBackendSnapshot(
        requested="halpe26", effective="halpe26", model_version="rtmpose-m-halpe26",
        model_assets={"detector": "a" * 64, "pose": "b" * 64},
        subprocess_env={
            "STRIDE_HALPE_DETECTOR": str(detector),
            "STRIDE_HALPE_POSE": str(pose),
        },
    )


def _blazepose_snapshot(tmp_path) -> PoseBackendSnapshot:
    runtime = tmp_path / "libmediapipe.dylib"
    model = tmp_path / "pose_landmarker_full.task"
    runtime.write_bytes(b"runtime")
    model.write_bytes(b"task")
    return PoseBackendSnapshot(
        requested="blazepose33", effective="blazepose33", model_version="pose-landmarker-full",
        model_assets={"runtime": "a" * 64, "pose_landmarker": "b" * 64},
        subprocess_env={
            "STRIDE_MEDIAPIPE_LIB": str(runtime),
            "STRIDE_BLAZEPOSE_MODEL": str(model),
        },
    )


def test_server_snapshot_e_proveniencia_halpe_seguem_para_o_job(tmp_path):
    queue = NoRunQueue()
    resolver = FixedResolver(_halpe_snapshot(tmp_path))
    svc = FormService(queue=queue, backend="halpe26", backend_resolver=resolver)
    out = svc.create(b"video", "run.mp4")
    aid = out["analysis_id"]
    try:
        saved = svc.get(aid)
        assert resolver.requested == ["halpe26"]
        assert saved["backend"] == {
            "requested": "halpe26", "effective": "halpe26",
            "model_version": "rtmpose-m-halpe26",
            "assets": {"detector": "a" * 64, "pose": "b" * 64},
        }
        # O job recebe o snapshot já decidido pelo servidor; o request nunca participa.
        assert queue.calls[0][1][4].effective == "halpe26"
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE analysis_id = ?", [aid])
        FormService._discard_dir(VIDEOS_DIR / aid)


def test_backend_fora_da_allowlist_nao_chega_ao_registro():
    with pytest.raises(BackendConfigurationError):
        FormService(queue=NoRunQueue(), backend="../../modelo-do-cliente")


def test_resolver_nao_pode_injetar_env_do_subprocesso(tmp_path):
    snapshot = _halpe_snapshot(tmp_path)
    unsafe = PoseBackendSnapshot(
        requested=snapshot.requested, effective=snapshot.effective,
        model_version=snapshot.model_version, model_assets=snapshot.model_assets,
        subprocess_env={**snapshot.subprocess_env, "LD_PRELOAD": "/tmp/evil.dylib"},
    )
    svc = FormService(queue=NoRunQueue(), backend="halpe26", backend_resolver=FixedResolver(unsafe))
    with pytest.raises(BackendConfigurationError):
        svc.create(b"video", "run.mp4")


def test_snapshot_blazepose_aprovado_chega_ao_job(tmp_path):
    queue = NoRunQueue()
    svc = FormService(queue=queue, backend="blazepose33",
                      backend_resolver=FixedResolver(_blazepose_snapshot(tmp_path)))
    out = svc.create(b"video", "run.mp4")
    try:
        assert queue.calls[0][1][4].effective == "blazepose33"
        assert svc.get(out["analysis_id"])["backend"]["assets"] == {
            "runtime": "a" * 64, "pose_landmarker": "b" * 64,
        }
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE analysis_id = ?", [out["analysis_id"]])
        FormService._discard_dir(VIDEOS_DIR / out["analysis_id"])
