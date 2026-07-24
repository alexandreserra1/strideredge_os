#!/usr/bin/env python3
"""Compara relatórios de shadow evaluation YOLO17 × Halpe26 de forma reprodutível.

Cada documento deve conter ``runs``. Uma run identifica um vídeo pelo seu nome e informa
``frames``, ``wall_seconds``, ``sample_stride`` e ``measurement_stage``. O comparador só aceita
um par por vídeo: repetir o mesmo vídeo no mesmo documento torna a amostra ambígua e exige gerar
relatórios separados. Ele mede execução e observabilidade; não avalia precisão anatômica nem
declara vencedor clínico.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _required_int(run: Dict[str, Any], name: str, *, positive: bool = False) -> int:
    value = run.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or (positive and value <= 0):
        qualifier = " inteiro > 0" if positive else " inteiro"
        raise ValueError(f"{name} precisa ser{qualifier}")
    return value


def _required_text(run: Dict[str, Any], name: str) -> str:
    value = run.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} precisa ser texto não vazio")
    return value


def _optional_percent(run: Dict[str, Any], name: str) -> Optional[float]:
    value = run.get(name)
    if value is None:
        return None
    if not _is_number(value) or not 0.0 <= float(value) <= 100.0:
        raise ValueError(f"{name} precisa estar entre 0 e 100")
    return float(value)


def _foot_coverage(run: Dict[str, Any], frames: int) -> Tuple[Optional[float], str]:
    """Retorna cobertura quantitativa quando o formato do runner a fornece.

    Relatórios antigos carregam somente ``foot_points_visible``. Eles ainda informam presença,
    mas não permitem calcular taxa comparável; preservar essa distinção evita inventar precisão.
    """
    visible_frames = run.get("foot_points_visible_frames")
    if visible_frames is not None:
        if not isinstance(visible_frames, int) or isinstance(visible_frames, bool) or not 0 <= visible_frames <= frames:
            raise ValueError("foot_points_visible_frames precisa estar entre 0 e frames")
        return visible_frames / frames, "frames"
    visible_rate = run.get("foot_points_visible_rate")
    if visible_rate is not None:
        if not _is_number(visible_rate) or not 0.0 <= float(visible_rate) <= 1.0:
            raise ValueError("foot_points_visible_rate precisa estar entre 0 e 1")
        return float(visible_rate), "rate"
    visible = run.get("foot_points_visible")
    if visible is None:
        return None, "missing"
    if not isinstance(visible, bool):
        raise ValueError("foot_points_visible precisa ser booleano")
    return (1.0 if visible else 0.0), "boolean"


def _normalize_run(run: Any) -> Dict[str, Any]:
    if not isinstance(run, dict):
        raise ValueError("cada run precisa ser um objeto JSON")
    frames = _required_int(run, "frames", positive=True)
    elapsed = run.get("wall_seconds")
    if not _is_number(elapsed) or float(elapsed) <= 0:
        raise ValueError("wall_seconds precisa ser número > 0")
    video = _required_text(run, "video")
    sampling = _required_int(run, "sample_stride", positive=True)
    stage = _required_text(run, "measurement_stage")
    reliable = run.get("reliable")
    if not isinstance(reliable, bool):
        raise ValueError("reliable precisa ser booleano")
    coverage, coverage_source = _foot_coverage(run, frames)
    return {
        "video": video,
        "frames": frames,
        "wall_seconds": float(elapsed),
        "fps": frames / float(elapsed),
        "sample_stride": sampling,
        "measurement_stage": stage,
        "reliable": reliable,
        "detection_rate_pct": _optional_percent(run, "detection_rate_pct"),
        "foot_coverage": coverage,
        "foot_coverage_source": coverage_source,
    }


def _runs_by_video(document: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    runs = document.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("runs deve conter ao menos uma medição")
    indexed: Dict[str, Dict[str, Any]] = {}
    for raw_run in runs:
        run = _normalize_run(raw_run)
        video = run["video"]
        if video in indexed:
            raise ValueError(f"vídeo duplicado no mesmo relatório: {video}")
        indexed[video] = run
    return indexed


def summarize(document: Dict[str, Any]) -> Dict[str, Any]:
    """Resumo compatível, agora sem sobrescrever runs que partilham um vídeo."""
    runs = list(_runs_by_video(document).values())
    total_frames = sum(run["frames"] for run in runs)
    total_seconds = sum(run["wall_seconds"] for run in runs)
    rates = [run["detection_rate_pct"] for run in runs if run["detection_rate_pct"] is not None]
    foot_coverages = [run["foot_coverage"] for run in runs if run["foot_coverage"] is not None]
    return {
        "videos": sorted(run["video"] for run in runs),
        "runs": len(runs),
        "mean_fps": round(sum(run["fps"] for run in runs) / len(runs), 2),
        "aggregate_fps": round(total_frames / total_seconds, 2),
        "reliable_runs": sum(run["reliable"] for run in runs),
        "foot_points_visible_runs": sum(bool(run["foot_coverage"] and run["foot_coverage"] > 0) for run in runs),
        "detection_rate_pct": round(sum(rates) / len(rates), 3) if rates else None,
        "foot_coverage": round(sum(foot_coverages) / len(foot_coverages), 4) if foot_coverages else None,
        "sample_stride_by_video": {run["video"]: run["sample_stride"] for run in runs},
        "measurement_stage_by_video": {run["video"]: run["measurement_stage"] for run in runs},
        "frames_by_video": {run["video"]: run["frames"] for run in runs},
    }


def _pair_runs(baseline: Dict[str, Any], candidate: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    base_runs, candidate_runs = _runs_by_video(baseline), _runs_by_video(candidate)
    reasons: List[str] = []
    base_videos, candidate_videos = set(base_runs), set(candidate_runs)
    if base_videos != candidate_videos:
        missing_candidate = sorted(base_videos - candidate_videos)
        missing_baseline = sorted(candidate_videos - base_videos)
        if missing_candidate:
            reasons.append("candidate_missing_videos:" + ",".join(missing_candidate))
        if missing_baseline:
            reasons.append("baseline_missing_videos:" + ",".join(missing_baseline))

    pairs: List[Dict[str, Any]] = []
    for video in sorted(base_videos & candidate_videos):
        base, trial = base_runs[video], candidate_runs[video]
        same_sampling = base["sample_stride"] == trial["sample_stride"]
        same_stage = base["measurement_stage"] == trial["measurement_stage"]
        same_frames = base["frames"] == trial["frames"]
        detection_comparable = base["detection_rate_pct"] is not None and trial["detection_rate_pct"] is not None
        detection_delta = (trial["detection_rate_pct"] - base["detection_rate_pct"] if detection_comparable else None)
        pairs.append({
            "video": video,
            "baseline_fps": round(base["fps"], 3),
            "candidate_fps": round(trial["fps"], 3),
            "fps_ratio": round(trial["fps"] / base["fps"], 3),
            "same_sampling": same_sampling,
            "same_measurement_stage": same_stage,
            "same_frames": same_frames,
            "reliability_ok": trial["reliable"] >= base["reliable"],
            "baseline_detection_rate_pct": base["detection_rate_pct"],
            "candidate_detection_rate_pct": trial["detection_rate_pct"],
            "detection_comparable": detection_comparable,
            "detection_rate_delta_pct": round(detection_delta, 3) if detection_delta is not None else None,
            "candidate_foot_coverage": round(trial["foot_coverage"], 4) if trial["foot_coverage"] is not None else None,
            "candidate_foot_coverage_source": trial["foot_coverage_source"],
            "candidate_has_foot_points": bool(trial["foot_coverage"] and trial["foot_coverage"] > 0),
        })
    return pairs, reasons


def compare(
    baseline: Dict[str, Any], candidate: Dict[str, Any], min_fps_ratio: float = 0.75,
    min_foot_coverage: float = 0.0,
) -> Dict[str, Any]:
    """Gera uma decisão operacional de comparabilidade para o próximo shadow run.

    ``eligible_for_shadow_evaluation`` significa apenas que os relatórios foram pareados e que o
    candidato não regrediu nos gates técnicos definidos. Não substitui revisão de overlay nem
    validação anatômica/clínica.
    """
    if not _is_number(min_fps_ratio) or float(min_fps_ratio) <= 0:
        raise ValueError("min_fps_ratio precisa ser número > 0")
    if not _is_number(min_foot_coverage) or not 0.0 <= float(min_foot_coverage) <= 1.0:
        raise ValueError("min_foot_coverage precisa estar entre 0 e 1")

    base, trial = summarize(baseline), summarize(candidate)
    pairs, reasons = _pair_runs(baseline, candidate)
    warnings: List[str] = []
    same_videos = not any(reason.startswith(("candidate_missing_videos:", "baseline_missing_videos:")) for reason in reasons)
    same_sampling = bool(pairs) and all(pair["same_sampling"] for pair in pairs)
    same_stage = bool(pairs) and all(pair["same_measurement_stage"] for pair in pairs)
    same_frames = bool(pairs) and all(pair["same_frames"] for pair in pairs)
    reliability_ok = bool(pairs) and all(pair["reliability_ok"] for pair in pairs)
    fps_ratio = trial["aggregate_fps"] / base["aggregate_fps"]
    foot_ok = bool(pairs) and all(
        pair["candidate_has_foot_points"] and pair["candidate_foot_coverage"] >= float(min_foot_coverage)
        for pair in pairs
    )
    detection_comparable = bool(pairs) and all(pair["detection_comparable"] for pair in pairs)
    detection_ok = (not detection_comparable) or all(pair["detection_rate_delta_pct"] >= 0 for pair in pairs)

    if not same_sampling:
        reasons.append("sample_stride_diverges")
    if not same_stage:
        reasons.append("measurement_stage_diverges")
    if not same_frames:
        reasons.append("frame_count_diverges")
    if fps_ratio < float(min_fps_ratio):
        reasons.append("candidate_fps_below_minimum")
    if not reliability_ok:
        reasons.append("candidate_reliability_regression")
    if not foot_ok:
        reasons.append("candidate_foot_coverage_insufficient")
    if not detection_comparable:
        warnings.append("detection_not_comparable")
    elif not detection_ok:
        reasons.append("candidate_detection_regression")

    # Compatibilidade de nome para o gate do spike já existente. O nome não implica promoção.
    eligible = same_videos and same_sampling and same_stage and same_frames and fps_ratio >= float(min_fps_ratio) and reliability_ok and foot_ok and detection_ok
    return {
        "baseline": base,
        "candidate": trial,
        "pairs": pairs,
        "fps_ratio": round(fps_ratio, 3),
        "same_videos": same_videos,
        "same_sampling": same_sampling,
        "same_measurement_stage": same_stage,
        "same_frames": same_frames,
        "reliability_ok": reliability_ok,
        "foot_points_ok": foot_ok,
        "detection_comparable": detection_comparable,
        "detection_ok": detection_ok,
        "min_fps_ratio": float(min_fps_ratio),
        "min_foot_coverage": float(min_foot_coverage),
        "eligible_for_shadow_evaluation": eligible,
        "eligible_for_rust_adapter": eligible,
        "ineligibility_reasons": reasons,
        "comparison_warnings": warnings,
        "clinical_winner": None,
        "clinical_conclusion": "not_assessed",
        "human_overlay_review_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="relatório JSON do YOLO17")
    parser.add_argument("candidate", type=Path, help="relatório JSON do Halpe26")
    parser.add_argument("--min-fps-ratio", type=float, default=0.75)
    parser.add_argument("--min-foot-coverage", type=float, default=0.0)
    args = parser.parse_args()
    report = compare(
        json.loads(args.baseline.read_text()), json.loads(args.candidate.read_text()),
        args.min_fps_ratio, args.min_foot_coverage,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["eligible_for_shadow_evaluation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
