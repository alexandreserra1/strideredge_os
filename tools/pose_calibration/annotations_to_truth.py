"""tools/pose_calibration/annotations_to_truth.py — anotações de dado PRÓPRIO → JSONs do arnês.

Fecha a trilha de "coletar validação própria" (OWN_DATA_PROTOCOL.md): a gente filma corredores com
celular (nosso caso de uso) e obtém a VERDADE do ângulo por qualquer âncora — IMU no segmento,
mocap alugado ou anotação manual. Este conversor é AGNÓSTICO à fonte: recebe um CSV simples de
`(clip, frame, joint, angle_deg[, side])` e cospe `events.json` + `truth.json` no formato exato que
`calibrate.py --events --truth` consome. Sem licença de terceiros — o dado é nosso.

Convenção: `angle_deg` é o ângulo INTERNO (180°=reto), a MESMA de `calibrate.angle_at`/`angle_at_3d`
e da verdade do Riglet (interno = 180 − flexão). Anote nessa convenção (ou converta antes).

CSV esperado (cabeçalho obrigatório):
    clip,frame,joint,angle_deg
    corredor01,142,knee,141.0
    corredor01,318,knee,138.5
    corredor02, 96,hip,150.0
`side` é opcional (default: a perna visível é decidida pelo arnês); `frame` é o índice no vídeo que
o motor dumpou (mesma base do `STRIDE_DUMP_SERIES`).
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

VALID_JOINTS = {"knee", "hip"}


def load_annotations(csv_path: str) -> list:
    """Lê o CSV de anotações → lista de dicts validados. Falha ALTO em linha malformada (é verdade
    pra um app de lesão — não se chuta nem se ignora silenciosamente)."""
    rows = []
    with open(csv_path, newline="") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            joint = (row.get("joint") or "").strip().lower()
            if joint not in VALID_JOINTS:
                raise ValueError(f"linha {n}: joint inválido {joint!r} (use knee|hip)")
            try:
                rows.append({"clip": row["clip"].strip(), "frame": int(row["frame"]),
                             "joint": joint, "angle_deg": float(row["angle_deg"])})
            except (KeyError, ValueError) as exc:
                raise ValueError(f"linha {n}: campo faltando/ inválido — {exc}") from exc
    if not rows:
        raise ValueError("CSV sem anotações")
    return rows


def to_events_and_truth(rows: list) -> tuple:
    """Anotações → (`events`, `truth`) no formato do arnês. `events[clip]=[frames]` (os frames de
    evento anotados, únicos e ordenados); `truth[clip][joint]={frame: interno}`."""
    events = defaultdict(set)
    truth: dict = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        events[r["clip"]].add(r["frame"])
        truth[r["clip"]][r["joint"]][r["frame"]] = round(r["angle_deg"], 1)
    events = {clip: sorted(frames) for clip, frames in events.items()}
    truth = {clip: {j: dict(fr) for j, fr in joints.items()} for clip, joints in truth.items()}
    return events, truth


def convert(csv_path: str, out_dir: str) -> dict:
    """CSV → escreve `events.json` + `truth.json` em `out_dir`. Devolve um resumo (clips, n anotações)."""
    rows = load_annotations(csv_path)
    events, truth = to_events_and_truth(rows)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "events.json").write_text(json.dumps(events, indent=2, ensure_ascii=False))
    (out / "truth.json").write_text(json.dumps(truth, indent=2, ensure_ascii=False))
    return {"clips": len(events), "annotations": len(rows),
            "events_json": str(out / "events.json"), "truth_json": str(out / "truth.json")}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Anotações de dado próprio (CSV) → events/truth do arnês")
    ap.add_argument("csv", help="CSV: clip,frame,joint,angle_deg")
    ap.add_argument("out_dir", help="onde escrever events.json + truth.json")
    print(json.dumps(convert(ap.parse_args().csv, ap.parse_args().out_dir), indent=2, ensure_ascii=False))
