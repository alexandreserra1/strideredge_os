"""tools/pose_calibration/trc_to_truth.py — verdade 3D TRIANGULADA (nossa) → JSONs do arnês.

Fecha a trilha AUTOSSUFICIENTE (SELF_SUFFICIENT_GROUNDTRUTH.md): filmamos corredores com 2–4
câmeras baratas e geramos a VERDADE 3D com o Pose2Sim (BSD-3, forkável, comercial OK) — não
dependemos de mocap de terceiros. O Pose2Sim cospe um `.trc` (posições 3D dos joints, em metros);
este adaptador computa o ângulo INTERNO 3D de joelho/quadril nele e escreve `truth.json` (+ `events`)
no formato de `calibrate.py`. Como a triangulação vem dos MESMOS vídeos que a pose single-cam, o
índice de frame do `.trc` alinha DIRETO com o dump do motor — sem sincronia externa.

`.trc` = formato-padrão: linha `Frame#\tTime\tMARKER...\t\t\t...` nomeia cada marcador (spanning 3
colunas X/Y/Z); dados a partir daí. `marker_map` liga os nossos nomes semânticos aos nomes de joint
que o Pose2Sim usou (dependem do modelo de pose — Halpe/Body25/COCO), ex.: {"knee_l":"LKnee",...}.
"""

import json
import math
from pathlib import Path
from typing import Optional

# nomes de joint que a biomecânica usa; o marker_map default cobre a convenção comum (L/R + Joint).
JOINT_MARKERS = {
    "knee": {"l": ("LHip", "LKnee", "LAnkle"), "r": ("RHip", "RKnee", "RAnkle")},
    "hip": {"l": ("LShoulder", "LHip", "LKnee"), "r": ("RShoulder", "RHip", "RKnee")},
}


def parse_trc(path: str) -> dict:
    """Lê um `.trc` → {rate, marker_col{nome: índice_da_coluna_X}, rows:[[floats]]}. Falha alto se o
    cabeçalho de marcadores não aparecer (não se adivinha coluna num app de lesão)."""
    lines = Path(path).read_text().splitlines()
    hdr = next((k for k, l in enumerate(lines) if l.split("\t")[0] == "Frame#"), None)
    if hdr is None:
        raise ValueError("TRC sem linha de cabeçalho 'Frame#' — arquivo inválido")
    labels = lines[hdr].split("\t")
    # cada marcador ocupa a coluna do nome + as 2 seguintes (X/Y/Z). Frame#=0, Time=1, markers >=2.
    marker_col = {name.strip(): i for i, name in enumerate(labels) if name.strip() and i >= 2}
    rate = 0.0
    if hdr >= 2:
        vals = lines[hdr - 1].split("\t")
        try:
            rate = float(vals[0])
        except (ValueError, IndexError):
            rate = 0.0
    rows = []
    for l in lines[hdr + 2:]:                       # +1 = sub-header X/Y/Z, +2 = dados
        parts = l.split("\t")
        if len(parts) < 3 or not parts[0].strip():
            continue
        rows.append([float(p) if p.strip() not in ("", "NaN") else float("nan") for p in parts])
    return {"rate": rate, "marker_col": marker_col, "rows": rows}


def _angle_3d(a, b, c) -> Optional[float]:
    v1 = [a[i] - b[i] for i in range(3)]
    v2 = [c[i] - b[i] for i in range(3)]
    m1 = math.sqrt(sum(x * x for x in v1))
    m2 = math.sqrt(sum(x * x for x in v2))
    if m1 == 0 or m2 == 0 or any(math.isnan(x) for x in v1 + v2):
        return None
    cos = max(-1.0, min(1.0, sum(v1[i] * v2[i] for i in range(3)) / (m1 * m2)))
    return round(math.degrees(math.acos(cos)), 1)


def _xyz(trc: dict, row: list, marker: str) -> Optional[tuple]:
    col = trc["marker_col"].get(marker)
    if col is None or col + 2 >= len(row):
        return None
    xyz = (row[col], row[col + 1], row[col + 2])
    return None if any(math.isnan(v) for v in xyz) else xyz


def truth_from_trc(trc: dict, joint: str, side: str, marker_map: Optional[dict] = None,
                   frames: Optional[list] = None) -> dict:
    """{frame: ângulo_interno_3d} do `joint`/`side` no `.trc`. `frames`=None usa todos. `marker_map`
    sobrescreve os nomes default (ex.: se o Pose2Sim nomeou 'CHip'/'RKnee'/...)."""
    names = (marker_map or {}).get(f"{joint}_{side}") or JOINT_MARKERS[joint][side]
    out = {}
    for i, row in enumerate(trc["rows"]):
        if frames is not None and i not in frames:
            continue
        pts = [_xyz(trc, row, n) for n in names]
        if all(p is not None for p in pts):
            a = _angle_3d(*pts)
            if a is not None:
                out[i] = a
    return out


def convert(trc_path: str, clip: str, out_dir: str, marker_map: Optional[dict] = None,
            frames: Optional[list] = None) -> dict:
    """`.trc` → escreve/atualiza `truth.json` (knee+hip) e `events.json` em `out_dir` p/ o `clip`.
    Sem `frames`, os eventos = todos os frames com ângulo válido (o chamador pode restringir a apoios)."""
    trc = parse_trc(trc_path)
    truth = {"knee": {}, "hip": {}}
    for joint in ("knee", "hip"):
        for side in ("l", "r"):
            truth[joint].update({f: a for f, a in
                                 truth_from_trc(trc, joint, side, marker_map, frames).items()})
    ev = sorted(set(truth["knee"]) | set(truth["hip"]))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ep, tp = out / "events.json", out / "truth.json"
    events = json.loads(ep.read_text()) if ep.exists() else {}
    truths = json.loads(tp.read_text()) if tp.exists() else {}
    events[clip] = ev
    truths[clip] = truth
    ep.write_text(json.dumps(events, indent=2))
    tp.write_text(json.dumps(truths, indent=2, ensure_ascii=False))
    return {"clip": clip, "n_frames": len(ev), "rate": trc["rate"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Verdade 3D triangulada (.trc do Pose2Sim) → arnês")
    ap.add_argument("trc"); ap.add_argument("clip"); ap.add_argument("out_dir")
    ap.add_argument("--marker-map", help="JSON {joint_side: [ombro/hip,knee,ankle]}")
    a = ap.parse_args()
    mm = json.loads(Path(a.marker_map).read_text()) if a.marker_map else None
    print(json.dumps(convert(a.trc, a.clip, a.out_dir, mm), indent=2, ensure_ascii=False))
