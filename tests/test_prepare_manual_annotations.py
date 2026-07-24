"""Seleção de frames para anotação manual: só prepara a revisão humana, não mede acurácia."""

import importlib.util
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    "prepare", Path(__file__).resolve().parent.parent / "tools" / "pose_calibration" /
    "prepare_manual_annotations.py")
prepare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prepare)


def _record(frame, y_left, y_right, left_conf=0.9, right_conf=0.6):
    def point(y, confidence): return [10.0, float(y), confidence]
    return {"i": frame, "present": True, "kp": {
        "hip_l": point(20, left_conf), "knee_l": point(50, left_conf), "ankle_l": point(y_left, left_conf),
        "heel_l": point(y_left, left_conf), "big_toe_l": point(y_left - 2, left_conf),
        "hip_r": point(20, right_conf), "knee_r": point(50, right_conf), "ankle_r": point(y_right, right_conf),
        "heel_r": point(y_right, right_conf), "big_toe_r": point(y_right - 2, right_conf),
    }}


def test_escolhe_perna_visivel_e_picos_separados():
    values = [10, 30, 50, 30, 10, 10, 25, 48, 25, 10, 10, 27, 49, 27, 10]
    dump = {"fps": 20, "frames": [_record(i, value, 15) for i, value in enumerate(values)]}
    assert prepare.choose_leg(dump) == "l"
    assert prepare.select_contact_frames(dump, "l", count=3) == [2, 7, 12]
