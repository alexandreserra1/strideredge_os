"""tools/pose_calibration/calibrate.py — comparador de ângulos PAREADO e backend-independente.

O erro do comparador antigo: media o ângulo nos picos de apoio que CADA backend escolhia — frames
diferentes. Calibração válida exige medir os dois motores no MESMO frame/evento, com a MESMA
fórmula, contra o GROUND-TRUTH (mocap/força) — não contra o YOLO.

Este módulo consome o dump por-frame do motor (`STRIDE_DUMP_SERIES`): um registro por frame
decodificado com índice, timestamp, `present` e os landmarks por NOME semântico. A partir dos
landmarks ele recomputa qualquer ângulo (fórmula única), então:
  - PAREADO backend↔backend: no mesmo frame, Bland-Altman (MAE, viés, limites de concordância);
  - vs GROUND-TRUTH: MAE/viés de cada backend contra o ângulo verdadeiro nos frames de evento;
  - EVENTOS: precision/recall dos apoios de cada backend contra os eventos anotados.

Gates de honestidade (app de lesão): sem eventos anotados → só agreement diagnóstico (NÃO acurácia);
sem ground-truth → concordância, não acerto; poucos corredores → piloto de engenharia, não validação.
Ver docs/adr/0002 e AI-STRATEGY. O adaptador do dataset Riglet (CC0) alimenta eventos+truth aqui.
"""

import json
import math
import statistics as st
from pathlib import Path
from typing import Optional

MIN_SUBJECTS = 8               # abaixo disto é piloto de engenharia, não validação
CONTACT_JOINTS = ("knee", "hip")


def joint_angle(a, b, c) -> Optional[float]:
    """Ângulo interno (graus) no vértice b, de a-b-c. Espelha `biomechanics::joint_angle` (Rust)."""
    v1x, v1y = a[0] - b[0], a[1] - b[1]
    v2x, v2y = c[0] - b[0], c[1] - b[1]
    m1 = math.hypot(v1x, v1y)
    m2 = math.hypot(v2x, v2y)
    if m1 == 0 or m2 == 0:
        return None
    cos = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / (m1 * m2)))
    return math.degrees(math.acos(cos))


def _joint_pts(joint: str, leg: str) -> tuple:
    return ((f"hip_{leg}", f"knee_{leg}", f"ankle_{leg}") if joint == "knee"
            else (f"shoulder_{leg}", f"hip_{leg}", f"knee_{leg}"))


def angle_at(rec: dict, joint: str, leg: str) -> Optional[float]:
    """Ângulo do `joint` (knee|hip) da perna `leg` (l|r) NUM frame — dos landmarks 2D, sem depender
    do backend. None se o frame não tem pose ou falta algum ponto."""
    kp = rec.get("kp") if rec and rec.get("present") else None
    if not kp:
        return None
    pts = _joint_pts(joint, leg)
    if any(p not in kp for p in pts):
        return None
    return joint_angle(kp[pts[0]], kp[pts[1]], kp[pts[2]])


def joint_angle_3d(a, b, c) -> Optional[float]:
    """Ângulo interno 3D no vértice b (x,y,z). O mocap mede em 3D; o BlazePose entrega world
    landmarks 3D → este ângulo é imune à projeção 2D que erra fora do plano."""
    v1 = [a[i] - b[i] for i in range(3)]
    v2 = [c[i] - b[i] for i in range(3)]
    m1 = math.sqrt(sum(x * x for x in v1))
    m2 = math.sqrt(sum(x * x for x in v2))
    if m1 == 0 or m2 == 0:
        return None
    cos = max(-1.0, min(1.0, sum(v1[i] * v2[i] for i in range(3)) / (m1 * m2)))
    return math.degrees(math.acos(cos))


def angle_at_3d(rec: dict, joint: str, leg: str) -> Optional[float]:
    """Ângulo 3D do `joint` a partir dos world landmarks (`kpw`). None se o backend não trouxe 3D
    (só o BlazePose traz) ou faltar ponto."""
    kpw = rec.get("kpw") if rec and rec.get("present") else None
    if not kpw:
        return None
    pts = _joint_pts(joint, leg)
    if any(p not in kpw for p in pts):
        return None
    return joint_angle_3d(kpw[pts[0]], kpw[pts[1]], kpw[pts[2]])


def by_index(dump: dict) -> dict:
    """`{frame_index: registro}` — pra parear os dois backends pelo MESMO frame decodificado."""
    return {r["i"]: r for r in dump.get("frames", [])}


def _angle_reader(mode: str):
    """Escolhe explicitamente a geometria usada pelo relatório.

    ``world_3d`` é uma estimativa 3D do modelo, não uma verdade clínica. Ele evita a
    projeção no plano da câmera; só o mocap/força no ``truth`` pode validar acurácia.
    Não há modo ``auto`` de propósito: misturar 2D e 3D sem registrá-lo tornou um
    resultado anterior impossível de reproduzir.
    """
    readers = {"2d": angle_at, "world_3d": angle_at_3d}
    try:
        return readers[mode]
    except KeyError as exc:
        raise ValueError("angle_mode deve ser '2d' ou 'world_3d'") from exc


def paired_agreement(dump_a: dict, dump_b: dict, joint: str, leg: str,
                     frames: Optional[list] = None, *, mode_a: str = "2d",
                     mode_b: str = "2d") -> dict:
    """Bland-Altman de b−a no MESMO frame. `frames`=None usa todos onde ambos têm pose (diagnóstico
    de agreement, NÃO ancorado em evento). `frames`=eventos anotados dá a comparação válida."""
    reader_a, reader_b = _angle_reader(mode_a), _angle_reader(mode_b)
    ia, ib = by_index(dump_a), by_index(dump_b)
    idxs = frames if frames is not None else sorted(set(ia) & set(ib))
    diffs = []
    for i in idxs:
        a = reader_a(ia.get(i, {}), joint, leg)
        b = reader_b(ib.get(i, {}), joint, leg)
        if a is not None and b is not None:
            diffs.append(b - a)
    if not diffs:
        return {"n": 0, "modes": {"a": mode_a, "b": mode_b}}
    bias = st.mean(diffs)
    sd = st.pstdev(diffs) if len(diffs) > 1 else 0.0
    return {"n": len(diffs), "mae_deg": round(st.mean(map(abs, diffs)), 1),
            "bias_deg": round(bias, 1), "sd_deg": round(sd, 1),
            "loa_deg": [round(bias - 1.96 * sd, 1), round(bias + 1.96 * sd, 1)],
            "event_anchored": frames is not None,
            "modes": {"a": mode_a, "b": mode_b}}


def error_vs_truth(dump: dict, truth: dict, joint: str, leg: str, *, mode: str = "2d") -> dict:
    """MAE/viés de um backend contra o ângulo VERDADEIRO.

    ``truth`` é ``{frame_index: angulo_graus}``; ``mode`` fica no resultado para que um
    MAE 2D nunca seja apresentado como resultado dos world landmarks 3D.
    """
    reader = _angle_reader(mode)
    idx = by_index(dump)
    errs = []
    for i, gt in truth.items():
        a = reader(idx.get(int(i), {}), joint, leg)
        if a is not None:
            errs.append(a - gt)
    if not errs:
        return {"n": 0, "mode": mode}
    return {"n": len(errs), "mae_deg": round(st.mean(map(abs, errs)), 1),
            "bias_deg": round(st.mean(errs), 1), "mode": mode}


def report(dumps: dict, baseline: str, candidate: str, leg: str = "l",
           events: Optional[dict] = None, truth: Optional[dict] = None,
           *, baseline_mode: str = "2d", candidate_mode: str = "2d",
           legs: Optional[dict] = None) -> dict:
    """Relatório por articulação. `dumps[subject][backend]=dump`. `events[subject]=[frames]` (comuns
    aos dois backends). `truth[subject][joint]={frame: angulo}` do mocap.

    ``legs`` permite uma perna visível por corredor, escolhida por uma regra independente da verdade;
    se ausente, preserva o ``leg`` global para os testes e usos antigos.
    """
    subjects = [s for s in dumps if baseline in dumps[s] and candidate in dumps[s]]
    # Um relatório ancorado em eventos não pode contar um dump sem evento só porque há frames
    # disponíveis. Isso inflaria n_subjects_agree com acordo de fases arbitrárias.
    if events is not None:
        subjects = [s for s in subjects if s in events]
    joints = {}
    for joint in CONTACT_JOINTS:
        agrees, base_err, cand_err = [], [], []
        for s in subjects:
            subject_leg = (legs or {}).get(s, leg)
            if subject_leg not in ("l", "r"):
                raise ValueError("legs deve mapear cada corredor para 'l' ou 'r'")
            ev = (events or {}).get(s)
            ag = paired_agreement(dumps[s][baseline], dumps[s][candidate], joint, subject_leg, ev,
                                  mode_a=baseline_mode, mode_b=candidate_mode)
            if ag["n"]:
                agrees.append(ag)
            gt = (truth or {}).get(s, {}).get(joint)
            if gt:
                be = error_vs_truth(dumps[s][baseline], gt, joint, subject_leg, mode=baseline_mode)
                ce = error_vs_truth(dumps[s][candidate], gt, joint, subject_leg, mode=candidate_mode)
                if be["n"] and ce["n"]:
                    base_err.append(be["mae_deg"])
                    cand_err.append(ce["mae_deg"])
        joints[joint] = _summarize(agrees, base_err, cand_err)
    return {"baseline": baseline, "candidate": candidate, "leg": leg,
            "angle_modes": {baseline: baseline_mode, candidate: candidate_mode},
            "legs": {s: (legs or {}).get(s, leg) for s in subjects},
            "n_subjects": len(subjects), "event_anchored": bool(events),
            "has_ground_truth": bool(truth), "joints": joints,
            "study_scope": "piloto_de_engenharia_nao_validacao_clinica",
            "verdict": _verdict(len(subjects), bool(events), bool(truth), joints)}


def _summarize(agrees: list, base_err: list, cand_err: list) -> dict:
    if not agrees:
        return {"status": "no_data"}
    out = {"n_subjects_agree": len(agrees),
           "mae_deg": round(st.mean(a["mae_deg"] for a in agrees), 1),
           "bias_deg": round(st.mean(a["bias_deg"] for a in agrees), 1),
           "bias_sd_across_subjects": round(st.pstdev([a["bias_deg"] for a in agrees]), 1)
           if len(agrees) > 1 else 0.0}
    if base_err and cand_err:
        out["baseline_mae_vs_truth"] = round(st.mean(base_err), 1)
        out["candidate_mae_vs_truth"] = round(st.mean(cand_err), 1)
        out["candidate_closer_to_truth"] = st.mean(cand_err) < st.mean(base_err)
    return out


def _verdict(n: int, anchored: bool, truth: bool, joints: dict) -> str:
    if not anchored:
        return "agreement_diagnostico — medido em TODOS os frames (mistura fases), não em eventos; " \
               "não é calibração válida. Falta anotar contato/apoio/toe-off comuns."
    if not truth:
        return "sem_ground_truth — pareado em eventos, mas só concordância entre backends; falta a verdade (mocap)."
    if n < MIN_SUBJECTS:
        return f"piloto_engenharia ({n}<{MIN_SUBJECTS} corredores) — mede erro real, mas não valida clinicamente."
    return "avaliacao_pareada_de_engenharia — eventos + ground-truth; não é validação clínica"


def load_dumps(directory: str) -> dict:
    """Lê `<subject>.<backend>.frames.json` -> `dumps[subject][backend]=dump`."""
    dumps: dict = {}
    for path in sorted(Path(directory).glob("*.frames.json")):
        stem = path.name[: -len(".frames.json")]
        subject, _, backend = stem.rpartition(".")
        dumps.setdefault(subject, {})[backend] = json.loads(path.read_text())
    return dumps


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Comparador de ângulos pareado e backend-independente")
    ap.add_argument("dumps_dir", help="diretório com <subject>.<backend>.frames.json (STRIDE_DUMP_SERIES)")
    ap.add_argument("--baseline", default="yolo17")
    ap.add_argument("--candidate", default="blazepose33")
    ap.add_argument("--leg", default="l", choices=["l", "r"])
    ap.add_argument("--baseline-mode", default="2d", choices=["2d", "world_3d"])
    ap.add_argument("--candidate-mode", default="2d", choices=["2d", "world_3d"])
    ap.add_argument("--events", help="JSON {subject: [frames_de_evento]}")
    ap.add_argument("--truth", help="JSON {subject: {joint: {frame: angulo}}}")
    ap.add_argument("--legs", help="JSON opcional {subject: 'l'|'r'} (perna visível por corredor)")
    args = ap.parse_args()
    ev = json.loads(Path(args.events).read_text()) if args.events else None
    gt = json.loads(Path(args.truth).read_text()) if args.truth else None
    legs = json.loads(Path(args.legs).read_text()) if args.legs else None
    print(json.dumps(report(load_dumps(args.dumps_dir), args.baseline, args.candidate,
                            args.leg, ev, gt, baseline_mode=args.baseline_mode,
                            candidate_mode=args.candidate_mode, legs=legs), indent=2,
                     ensure_ascii=False))
