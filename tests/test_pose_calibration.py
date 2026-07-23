"""Arnês de calibração de ângulos (tools/pose_calibration) — honesto por construção.

Herméticos: séries sintéticas com apoio e ângulo conhecidos. Provam que o arnês (a) extrai o ângulo
no APOIO como o Rust, (b) SÓ propõe correção com clipes suficientes + offset estável + ground-truth,
(c) marca 'não calibrável' quando o offset troca de sinal entre clipes."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "calibrate", Path(__file__).resolve().parent.parent / "tools" / "pose_calibration" / "calibrate.py")
cal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cal)


def _clip(knee_contact: float, hip_contact: float, cycles: int = 12) -> dict:
    """Série sintética: apoios (máx de ankle) a cada 5 frames; no apoio o joelho/quadril ficam nos
    valores dados, fora do apoio em outro valor. Perna esquerda visível (conf alta)."""
    ankle, knee, hip = [], [], []
    for _ in range(cycles):
        for k in range(5):
            contact = k == 2                       # índice 2 do ciclo = pé mais fundo (apoio)
            ankle.append(100.0 if contact else 10.0)
            knee.append(knee_contact if contact else 90.0)
            hip.append(hip_contact if contact else 100.0)
    n = len(ankle)
    return {"knee_l": knee, "knee_r": knee, "hip_l": hip, "hip_r": hip,
            "trunk": [5.0] * n, "ankle_l": ankle, "ankle_r": ankle,
            "conf_l": 0.9, "conf_r": 0.1, "layout": "test"}


def test_extrai_angulo_no_apoio_como_o_rust():
    vals = cal.contact_angles(_clip(150.0, 165.0), "knee")
    assert len(vals) >= 8 and all(v == 150.0 for v in vals)   # só os frames de apoio


def test_poucos_clipes_nao_propoe_correcao():
    dumps = {f"c{i}": {"yolo17": _clip(150.0, 165.0), "blazepose33": _clip(160.0, 168.0)}
             for i in range(2)}
    rep = cal.offset_report(dumps, "yolo17", "blazepose33")
    assert rep["joints"]["knee"]["delta_mean_deg"] == 10.0
    assert rep["joints"]["knee"]["same_sign"] is True
    assert rep["joints"]["knee"]["recommendation"] == "insufficient_clips"
    assert "insufficient_clips" in rep["verdict"]


def test_offset_instavel_marca_nao_calibravel():
    # joelho consistente (+10), quadril TROCA de sinal entre clipes -> não calibrável por offset
    dumps = {}
    for i in range(10):
        hip_cand = 175.0 if i % 2 == 0 else 155.0   # candidato ora acima, ora abaixo do baseline 165
        dumps[f"c{i}"] = {"yolo17": _clip(150.0, 165.0),
                          "blazepose33": _clip(160.0, hip_cand)}
    rep = cal.offset_report(dumps, "yolo17", "blazepose33")
    assert rep["joints"]["hip"]["same_sign"] is False
    assert rep["joints"]["hip"]["recommendation"] == "not_calibratable_rederive_thresholds"
    assert "nao_calibravel" in rep["verdict"]


def test_estavel_com_ground_truth_propoe_offset_e_escolhe_o_mais_certo():
    # 8 clipes, offset estável +10 no joelho; ground-truth = 152 (baseline erra 2, candidato erra 8)
    dumps = {f"c{i}": {"yolo17": _clip(150.0, 165.0), "blazepose33": _clip(160.0, 166.0)}
             for i in range(8)}
    gt = {f"c{i}": {"knee": 152.0, "hip": 165.5} for i in range(8)}
    rep = cal.offset_report(dumps, "yolo17", "blazepose33", gt)
    knee = rep["joints"]["knee"]
    assert knee["stable"] is True and knee["recommendation"] == "apply_offset"
    assert knee["proposed_offset_deg"] == -10.0                       # somar -10 ao candidato o alinha
    assert knee["candidate_closer_to_truth"] is False                 # baseline (err 2) < candidato (err 8)
    assert rep["verdict"].startswith("calibravel")
