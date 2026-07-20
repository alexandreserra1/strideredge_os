"""Retry com re-enfileiramento — falha transitória recupera; determinística esgota e falha.
Hermético: subprocess (ffmpeg + motor) mockado, fila síncrona."""

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

from api.form import FormService, _MAX_ATTEMPTS
from core.jobs import JobQueue
from core.database import get_connection

_METRICS = {"frames": 100, "fps": 30.0, "detection_rate_pct": 98.0, "cadence_spm": 172.0,
            "reliable": True, "reason": "ok"}


class InlineQueue(JobQueue):
    """Roda o job na hora (re-enfileiramento vira recursão síncrona — determinístico)."""
    def start(self): pass
    def enqueue(self, fn, *args, **kwargs): fn(*args, **kwargs)


def _fake_run(fail_times: int):
    """subprocess.run falso: ffmpeg normaliza; o motor falha `fail_times` vezes e depois vence."""
    calls = {"engine": 0}
    def run(cmd, **kw):
        if "ffmpeg" in str(cmd[0]):
            Path(cmd[-1]).write_bytes(b"x")                       # normalized.mp4
            return SimpleNamespace(returncode=0, stderr="", stdout="")
        calls["engine"] += 1
        overlay = Path(cmd[2])
        if calls["engine"] <= fail_times:
            return SimpleNamespace(returncode=1, stderr="boom transitório", stdout="")
        (overlay.parent / "overlay.metrics.json").write_text(json.dumps(_METRICS))
        return SimpleNamespace(returncode=0, stderr="", stdout="")
    return run, calls


def _new_analysis(tmp_path) -> tuple:
    aid = str(uuid.uuid4())
    get_connection().execute(
        "INSERT INTO form_analyses (analysis_id, status, view) VALUES (?, 'processing', 'lateral')",
        [aid])
    original = tmp_path / "original.mp4"
    original.write_bytes(b"fake-video")
    return aid, original


def _status(aid: str) -> str:
    return get_connection().execute(
        "SELECT status FROM form_analyses WHERE analysis_id=?", [aid]).fetchone()[0]


def test_retry_recupera_de_falha_transitoria(tmp_path, monkeypatch):
    run, calls = _fake_run(fail_times=1)                          # falha 1x, vence na 2ª
    monkeypatch.setattr("api.form.subprocess.run", run)
    svc = FormService(queue=InlineQueue())
    aid, original = _new_analysis(tmp_path)
    svc._process(aid, original, "lateral")
    assert _status(aid) == "done"                                 # recuperou
    assert calls["engine"] == 2                                   # 1 falha + 1 sucesso


def test_falha_persistente_esgota_tentativas_e_falha(tmp_path, monkeypatch):
    run, calls = _fake_run(fail_times=99)                         # sempre falha
    monkeypatch.setattr("api.form.subprocess.run", run)
    svc = FormService(queue=InlineQueue())
    aid, original = _new_analysis(tmp_path)
    svc._process(aid, original, "lateral")
    assert _status(aid) == "failed"                               # esgotou → falhou honesto
    assert calls["engine"] == _MAX_ATTEMPTS                       # tentou o teto exato


def test_sucesso_de_primeira_nao_retenta(tmp_path, monkeypatch):
    run, calls = _fake_run(fail_times=0)
    monkeypatch.setattr("api.form.subprocess.run", run)
    svc = FormService(queue=InlineQueue())
    aid, original = _new_analysis(tmp_path)
    svc._process(aid, original, "lateral")
    assert _status(aid) == "done" and calls["engine"] == 1        # sem retry desnecessário
