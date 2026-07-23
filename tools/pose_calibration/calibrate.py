"""tools/pose_calibration/calibrate.py — arnês de re-derivação de ângulos entre backends de pose.

Consome as séries por-frame que o motor despeja quando `STRIDE_DUMP_SERIES` aponta um arquivo
(um por clipe × backend) e responde à pergunta da calibração: o ângulo NO APOIO de um backend
candidato (ex.: blazepose33) é uma versão CALIBRÁVEL do baseline (yolo17), ou eles medem coisas
diferentes demais pra trocar sem re-derivar limiares?

HONESTIDADE POR CONSTRUÇÃO (é app de lesão):
  - offset backend↔backend NÃO é acurácia — só concordância. Sem ground-truth, o relatório diz isso.
  - com POUCOS clipes, nada de fator de correção — o gate `insufficient_clips` barra.
  - se o offset TROCA DE SINAL entre clipes (ex.: o quadril nos nossos 2 vídeos), é `unstable` →
    NÃO é um deslocamento fixo; re-derivar limiares, não "somar X graus".
  - só propõe uma correção quando: N>=MIN_CLIPS, offset estável (sinal consistente + spread baixo),
    E existe âncora de ground-truth dizendo qual backend erra menos.

Não baixa nem embute vídeo; roda sobre os dumps que já temos. Ver docs/adr/0002 e AI-STRATEGY.
"""

import json
import statistics as st
from pathlib import Path
from typing import Optional

# Abaixo disto, qualquer "offset" é anedota — 2 clipes não caracterizam um viés de gait.
MIN_CLIPS = 8
# Um offset só é "estável" se o sinal é o mesmo em todos os clipes e o desvio entre clipes é baixo.
STABLE_MAX_STD_DEG = 4.0
# Articulações que a métrica de risco usa no apoio (lateral).
CONTACT_JOINTS = ("knee", "hip")


def _contacts(ankle_y: list) -> list:
    """Índices de APOIO: máximos locais de ankle_y (pé mais fundo na tela), espaçados >=4 frames.
    Espelha exatamente a detecção de `biomechanics::contact_angle` no Rust."""
    out, last = [], 0
    for i in range(1, len(ankle_y) - 1):
        if ankle_y[i] >= ankle_y[i - 1] and ankle_y[i] > ankle_y[i + 1] and (not out or i - last >= 4):
            out.append(i)
            last = i
    return out


def _visible_leg(series: dict) -> str:
    """Perna que alimenta as métricas de apoio = a de maior confiança somada (a de trás é ocluída)."""
    return "r" if series.get("conf_r", 0.0) >= series.get("conf_l", 0.0) else "l"


def contact_angles(series: dict, joint: str) -> list:
    """Ângulos do `joint` (knee|hip) nos frames de apoio da perna visível — a mesma amostra que vira
    `knee_contact_deg`/`hip_contact_deg`. Devolve a lista bruta (pra medir média E dispersão)."""
    leg = _visible_leg(series)
    angles, ankle = series[f"{joint}_{leg}"], series[f"ankle_{leg}"]
    n = min(len(angles), len(ankle))
    return [angles[i] for i in _contacts(ankle[:n]) if angles[i] > 1.0]


def per_clip_contact(dumps: dict) -> dict:
    """`dumps[clip][backend] = series` -> `{clip: {backend: {joint: media_no_apoio}}}` (+ n)."""
    out = {}
    for clip, backends in dumps.items():
        out[clip] = {}
        for backend, series in backends.items():
            row = {}
            for joint in CONTACT_JOINTS:
                vals = contact_angles(series, joint)
                row[joint] = {"mean": round(st.mean(vals), 1), "n": len(vals),
                              "sd": round(st.pstdev(vals), 1)} if vals else None
            out[clip][backend] = row
    return out


def offset_report(dumps: dict, baseline: str, candidate: str,
                  ground_truth: Optional[dict] = None) -> dict:
    """Relatório de calibração candidate↔baseline por articulação, com gates de honestidade.

    `ground_truth[clip][joint]` (opcional) = ângulo VERDADEIRO no apoio (graus, mesma convenção:
    180°=reto), de mocap/anotação. Quando presente, computa o erro absoluto de cada backend."""
    contact = per_clip_contact(dumps)
    clips = [c for c in contact if baseline in contact[c] and candidate in contact[c]]
    joints = {}
    for joint in CONTACT_JOINTS:
        deltas, base_err, cand_err = [], [], []
        for clip in clips:
            b = contact[clip][baseline].get(joint)
            c = contact[clip][candidate].get(joint)
            if not b or not c:
                continue
            deltas.append(c["mean"] - b["mean"])
            gt = (ground_truth or {}).get(clip, {}).get(joint)
            if gt is not None:
                base_err.append(abs(b["mean"] - gt))
                cand_err.append(abs(c["mean"] - gt))
        joints[joint] = _judge_joint(joint, deltas, base_err, cand_err, len(clips))
    return {
        "baseline": baseline, "candidate": candidate,
        "n_clips": len(clips),
        "has_ground_truth": bool(ground_truth),
        "joints": joints,
        "verdict": _overall(joints, len(clips), bool(ground_truth)),
    }


def _judge_joint(joint: str, deltas: list, base_err: list, cand_err: list, n_clips: int) -> dict:
    if not deltas:
        return {"status": "no_data"}
    mean = round(st.mean(deltas), 1)
    sd = round(st.pstdev(deltas), 1) if len(deltas) > 1 else 0.0
    same_sign = all(d >= 0 for d in deltas) or all(d <= 0 for d in deltas)
    out = {"delta_mean_deg": mean, "delta_sd_deg": sd, "same_sign": same_sign,
           "stable": same_sign and sd <= STABLE_MAX_STD_DEG}
    if base_err and cand_err:
        out["baseline_abs_err_deg"] = round(st.mean(base_err), 1)
        out["candidate_abs_err_deg"] = round(st.mean(cand_err), 1)
        out["candidate_closer_to_truth"] = st.mean(cand_err) < st.mean(base_err)
    # A correção só é PROPOSTA quando há dado suficiente + estável + âncora de verdade.
    if n_clips >= MIN_CLIPS and out["stable"] and base_err and cand_err:
        out["proposed_offset_deg"] = -mean   # somar isto ao candidato o alinha ao baseline
        out["recommendation"] = "apply_offset"
    elif not out["stable"]:
        out["recommendation"] = "not_calibratable_rederive_thresholds"
    elif n_clips < MIN_CLIPS:
        out["recommendation"] = "insufficient_clips"
    else:
        out["recommendation"] = "need_ground_truth"
    return out


def _overall(joints: dict, n_clips: int, has_gt: bool) -> str:
    if n_clips < MIN_CLIPS:
        return f"insufficient_clips ({n_clips}<{MIN_CLIPS}) — offsets são anedóticos, não calibre ainda"
    if any(j.get("recommendation") == "not_calibratable_rederive_thresholds" for j in joints.values()):
        return "nao_calibravel_por_offset — ao menos uma articulação diverge instável; re-derivar limiares"
    if not has_gt:
        return "sem_ground_truth — offsets estáveis, mas só concordância; falta âncora de verdade"
    return "calibravel — offsets estáveis + âncora de verdade; ver proposed_offset_deg por articulação"


def load_dumps(directory: str) -> dict:
    """Lê `<clip>.<backend>.series.json` de um diretório -> `dumps[clip][backend] = series`."""
    dumps: dict = {}
    for path in sorted(Path(directory).glob("*.series.json")):
        stem = path.name[: -len(".series.json")]
        clip, _, backend = stem.rpartition(".")
        dumps.setdefault(clip, {})[backend] = json.loads(path.read_text())
    return dumps


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Re-derivação/calibração de ângulos entre backends de pose")
    ap.add_argument("dumps_dir", help="diretório com <clip>.<backend>.series.json (STRIDE_DUMP_SERIES)")
    ap.add_argument("--baseline", default="yolo17")
    ap.add_argument("--candidate", default="blazepose33")
    ap.add_argument("--ground-truth", help="JSON {clip: {knee: deg, hip: deg}} de mocap/anotação")
    args = ap.parse_args()
    gt = json.loads(Path(args.ground_truth).read_text()) if args.ground_truth else None
    report = offset_report(load_dumps(args.dumps_dir), args.baseline, args.candidate, gt)
    print(json.dumps(report, indent=2, ensure_ascii=False))
