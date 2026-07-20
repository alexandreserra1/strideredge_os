"""E2E REAL do motor de visão: roda o binário Rust num vídeo demo de verdade e valida a saída.

NÃO-hermético (precisa do binário compilado + ffmpeg + vídeo demo) — nomeado 'e2e' pra sair do
`pytest -k "not e2e"`. Rode com: pytest tests/test_vision_e2e.py -k e2e. Pula gracioso se faltar
binário/vídeo. Valida as correções desta rodada: gct plausível + observabilidade do quality gate."""

import json
import subprocess

import pytest

from core.database import PROJECT_ROOT
from analytics.form_coach import FormCoach

_BIN = PROJECT_ROOT / "stride_vision" / "target" / "release" / "stride-vision"
_MODEL = PROJECT_ROOT / "stride_vision" / "models" / "yolo11n-pose.onnx"
_VIDEO = PROJECT_ROOT / "stride_vision" / "demo" / "esteira_720.mp4"
_ENV = {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", "STRIDE_MODEL": str(_MODEL)}

pytestmark = pytest.mark.skipif(
    not (_BIN.exists() and _MODEL.exists() and _VIDEO.exists()),
    reason="motor não compilado ou vídeo demo ausente (rode cargo build --release)")


def _run_engine(tmp_path) -> dict:
    out = tmp_path / "overlay.mp4"
    r = subprocess.run([str(_BIN), str(_VIDEO), str(out), "--view", "lateral"],
                       env=_ENV, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"motor falhou: {r.stderr[-300:]}"
    return json.loads((tmp_path / "overlay.metrics.json").read_text())


def test_e2e_motor_produz_metricas_com_observabilidade(tmp_path):
    m = _run_engine(tmp_path)
    # o motor rodou e classificou a captura
    assert m["frames"] > 0 and isinstance(m["reliable"], bool)
    # observabilidade nova: os insumos da decisão estão expostos
    assert "reason" in m and m["reason"] in (
        "ok", "low_detection", "not_lateral", "both_legs_missing", "torso_not_visible", "too_short")
    assert "diag_vert_osc_pct" in m and "diag_leg_len_px" in m


def test_e2e_ground_contact_nunca_impossivel(tmp_path):
    """A correção do GCT: nunca mais o valor-lixo ~2000ms — ou plausível (60–500ms) ou None."""
    m = _run_engine(tmp_path)
    gct = m.get("ground_contact_ms")
    assert gct is None or (60.0 <= gct <= 500.0), f"gct impossível vazou: {gct}"


def test_e2e_pipeline_video_ate_coach_bloqueia_captura_ruim(tmp_path):
    """Fio completo: vídeo real → métricas → coach. Captura ruim NÃO vira conselho de lesão."""
    m = _run_engine(tmp_path)

    class _NoLLM:
        def chat(self, s, u): return "- exercício (Fonte: PMC123)"
    plan = FormCoach(llm=_NoLLM()).plan(m)
    if m["reliable"]:
        assert "verdict" in plan
    else:
        assert plan.get("unreliable") is True and not plan.get("actions")  # recusou, sem conselho
