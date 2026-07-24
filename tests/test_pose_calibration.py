"""Comparador pareado de ângulos (tools/pose_calibration) — backend-independente e honesto.

Herméticos: dumps por-frame sintéticos com ângulo conhecido. Provam (a) ângulo recomputado dos
landmarks (fórmula única), (b) Bland-Altman pareado no MESMO frame, (c) erro vs ground-truth escolhe
o backend certo, (d) os gates de honestidade (sem evento = diagnóstico; sem verdade = só concordância)."""

import importlib.util
import math
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "calibrate", Path(__file__).resolve().parent.parent / "tools" / "pose_calibration" / "calibrate.py")
cal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cal)


def _frame(i: int, knee_deg: float) -> dict:
    """Registro por-frame com joelho ESQUERDO no ângulo interno dado (hip-knee-ankle)."""
    t = math.radians(knee_deg)
    return {"i": i, "t_ms": i * 33, "present": True, "conf": 0.9,
            "kp": {"hip_l": [0.0, -1.0, 0.9], "knee_l": [0.0, 0.0, 0.9],
                   "ankle_l": [math.sin(t), -math.cos(t), 0.9]}}


def _dump(knee_deg: float, n: int = 20) -> dict:
    return {"layout": "test", "fps": 30.0, "frames_total": n,
            "frames": [_frame(i, knee_deg) for i in range(n)]}


def test_angulo_recomputado_dos_landmarks():
    assert abs(cal.joint_angle([0, -1], [0, 0], [0, 1]) - 180.0) < 0.01     # perna reta
    assert abs(cal.joint_angle([0, -1], [0, 0], [1, 0]) - 90.0) < 0.01      # ângulo reto
    assert abs(cal.angle_at(_frame(0, 150.0), "knee", "l") - 150.0) < 0.01
    assert cal.angle_at({"present": False}, "knee", "l") is None            # sem pose -> None


def test_angulo_3d_dos_world_landmarks():
    # perna reta em 3D (hip acima, ankle abaixo, colinear no eixo y) -> 180°
    assert abs(cal.joint_angle_3d([0, -1, 0], [0, 0, 0], [0, 1, 0]) - 180.0) < 0.01
    # 90° com componente em z (fora do plano da imagem) — o 2D erraria, o 3D pega
    assert abs(cal.joint_angle_3d([0, -1, 0], [0, 0, 0], [0, 0, 1]) - 90.0) < 0.01
    rec = {"present": True, "kpw": {"hip_l": [0, -1, 0], "knee_l": [0, 0, 0], "ankle_l": [0, 0, 1]}}
    assert abs(cal.angle_at_3d(rec, "knee", "l") - 90.0) < 0.01
    assert cal.angle_at_3d({"present": True, "kp": {}}, "knee", "l") is None   # sem kpw -> None


def test_pareado_no_mesmo_frame_bland_altman():
    # baseline 150°, candidato 160° nos MESMOS frames -> viés +10, MAE 10, LoA apertado
    ag = cal.paired_agreement(_dump(150.0), _dump(160.0), "knee", "l")
    assert ag["n"] == 20 and ag["bias_deg"] == 10.0 and ag["mae_deg"] == 10.0
    assert ag["sd_deg"] == 0.0 and ag["event_anchored"] is False


def test_erro_vs_ground_truth():
    err = cal.error_vs_truth(_dump(160.0), {5: 152.0, 6: 152.0}, "knee", "l")
    assert err["n"] == 2 and err["mae_deg"] == 8.0 and err["bias_deg"] == 8.0


def test_sem_evento_e_so_diagnostico():
    dumps = {"s0": {"yolo17": _dump(150.0), "blazepose33": _dump(160.0)}}
    rep = cal.report(dumps, "yolo17", "blazepose33")
    assert rep["event_anchored"] is False
    assert rep["verdict"].startswith("agreement_diagnostico")
    assert rep["joints"]["knee"]["bias_deg"] == 10.0


def test_valido_com_evento_ground_truth_escolhe_o_mais_certo():
    # 8 corredores, evento anotado (frame 5), verdade 152 -> baseline erra 2, candidato erra 8
    dumps, events, truth = {}, {}, {}
    for k in range(8):
        s = f"s{k}"
        dumps[s] = {"yolo17": _dump(150.0), "blazepose33": _dump(160.0)}
        events[s] = [5]
        truth[s] = {"knee": {5: 152.0}}
    rep = cal.report(dumps, "yolo17", "blazepose33", events=events, truth=truth)
    knee = rep["joints"]["knee"]
    assert rep["event_anchored"] and rep["has_ground_truth"] and rep["n_subjects"] == 8
    assert knee["baseline_mae_vs_truth"] == 2.0 and knee["candidate_mae_vs_truth"] == 8.0
    assert knee["candidate_closer_to_truth"] is False
    assert rep["verdict"].startswith("valido")
