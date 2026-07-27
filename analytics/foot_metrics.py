"""Guardrails de observabilidade para keypoints Halpe26 do pé.

Este módulo não calcula pronação, dorsiflexão, diagnóstico ou risco. Ele só responde se a série
de pontos do pé é suficientemente presente e temporalmente estável para uma futura validação de
métrica. Os limiares abaixo são de qualidade do rastreamento (não clínicos) e devem ser
recalibrados com vídeos pareados e revisão humana antes de qualquer uso de produto.

Entrada por frame::

    {
        "tornozelo_e": (x, y, confidence),
        "hallux_e": (x, y, confidence),
        "dedinho_e": (x, y, confidence),
        "calcanhar_e": (x, y, confidence),
        # ... os quatro pontos do lado direito
    }
"""

import math
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


MIN_CONFIDENCE = 0.35
MIN_TEMPORAL_COVERAGE = 0.80
MIN_JITTER_TRANSITIONS = 8
MAX_JITTER_RATIO = 0.45

_SIDE_POINTS = {
    "left": ("tornozelo_e", "hallux_e", "dedinho_e", "calcanhar_e"),
    "right": ("tornozelo_d", "hallux_d", "dedinho_d", "calcanhar_d"),
}
_FOOT_POINTS = {
    "left": ("hallux_e", "dedinho_e", "calcanhar_e"),
    "right": ("hallux_d", "dedinho_d", "calcanhar_d"),
}

Point = Tuple[float, float, float]


def assess_foot_keypoint_quality(frames: Sequence[Mapping[str, object]],
                                 min_confidence: float = MIN_CONFIDENCE,
                                 min_temporal_coverage: float = MIN_TEMPORAL_COVERAGE,
                                 max_jitter_ratio: float = MAX_JITTER_RATIO) -> dict:
    """Avalia a observabilidade experimental dos pés em uma série Halpe26.

    ``reliable=True`` significa somente que os pontos passaram nos gates técnicos abaixo; não
    valida nenhuma interpretação biomecânica. Frames com estrutura inválida recusam a série em
    vez de serem silenciosamente ignorados.
    """
    _validate_thresholds(min_confidence, min_temporal_coverage, max_jitter_ratio)
    total = len(frames)
    if not total:
        return _report(total, min_confidence, min_temporal_coverage, max_jitter_ratio,
                       "no_frames", {"left": [], "right": []}, {"left": 0, "right": 0})

    samples = {"left": [], "right": []}
    visible = {"left": 0, "right": 0}
    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, Mapping):
            return _report(total, min_confidence, min_temporal_coverage, max_jitter_ratio,
                           "invalid_keypoint_series", samples, visible)
        for side in ("left", "right"):
            points = _parse_side(frame, side)
            if points is None:
                return _report(total, min_confidence, min_temporal_coverage, max_jitter_ratio,
                               "invalid_keypoint_series", samples, visible)
            foot_visible = all(points[name][2] >= min_confidence for name in _FOOT_POINTS[side])
            if foot_visible:
                visible[side] += 1
            # Para estabilidade é necessário também o tornozelo; isso não reduz a cobertura do pé.
            if foot_visible and points[_SIDE_POINTS[side][0]][2] >= min_confidence:
                samples[side].append((frame_index, points))

    coverage = {side: visible[side] / total for side in ("left", "right")}
    if any(coverage[side] < min_temporal_coverage for side in coverage):
        reason = "insufficient_foot_coverage"
    else:
        jitter = {side: _jitter_ratio(samples[side]) for side in samples}
        if any(value is None for value in jitter.values()):
            reason = "insufficient_stability_samples"
        elif any(value > max_jitter_ratio for value in jitter.values()):
            reason = "excessive_keypoint_jitter"
        else:
            reason = "ok"
        return _report(total, min_confidence, min_temporal_coverage, max_jitter_ratio,
                       reason, samples, visible, jitter)
    return _report(total, min_confidence, min_temporal_coverage, max_jitter_ratio,
                   reason, samples, visible)


def _parse_side(frame: Mapping[str, object], side: str) -> Optional[Dict[str, Point]]:
    points = {}
    for name in _SIDE_POINTS[side]:
        value = frame.get(name)
        if not isinstance(value, (tuple, list)) or len(value) != 3:
            return None
        x, y, confidence = value
        if (not all(isinstance(item, (int, float)) and math.isfinite(item)
                    for item in (x, y, confidence))
                or not 0.0 <= confidence <= 1.0):
            return None
        points[name] = (float(x), float(y), float(confidence))
    return points


def _jitter_ratio(samples: List[Tuple[int, Dict[str, Point]]]) -> Optional[float]:
    """p95 do salto interframe relativo ao tamanho do pé no mesmo frame.

    A posição global do corredor não entra: comparamos cada ponto ao tornozelo e normalizamos
    pela distância calcanhar→hallux. Isso detecta saltos de keypoint sem confundir translação da
    câmera/corredor com jitter. Só transições em frames consecutivos contam; uma lacuna não vira
    um falso salto grande.
    """
    transitions = []
    for (previous_index, previous), (current_index, current) in zip(samples, samples[1:]):
        if current_index != previous_index + 1:
            continue
        previous_ankle = previous[next(name for name in previous if name.startswith("tornozelo"))]
        current_ankle = current[next(name for name in current if name.startswith("tornozelo"))]
        foot_names = [name for name in current if not name.startswith("tornozelo")]
        scale = _distance(current[foot_names[-1]], current[foot_names[0]])
        if scale <= 1e-6:
            continue
        jumps = []
        for name in foot_names:
            before = _relative(previous[name], previous_ankle)
            after = _relative(current[name], current_ankle)
            jumps.append(_distance(before, after) / scale)
        transitions.append(max(jumps))
    if len(transitions) < MIN_JITTER_TRANSITIONS:
        return None
    return _percentile(transitions, 0.95)


def _relative(point: Point, anchor: Point) -> Point:
    return point[0] - anchor[0], point[1] - anchor[1], 0.0


def _distance(first: Point, second: Point) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def _percentile(values: List[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * quantile)]


def _report(total: int, min_confidence: float, min_coverage: float, max_jitter: float,
            reason: str, samples: Dict[str, List[Tuple[int, Dict[str, Point]]]],
            visible: Dict[str, int], jitter: Optional[Dict[str, Optional[float]]] = None) -> dict:
    coverage = {side: round(visible[side] / total, 4) if total else 0.0
                for side in ("left", "right")}
    jitter = jitter or {"left": None, "right": None}
    return {
        "experimental": True,
        "reliable": reason == "ok",
        "reason": reason,
        "quality": {
            "frames": total,
            "minimum_keypoint_confidence": min_confidence,
            "minimum_temporal_coverage": min_coverage,
            "maximum_jitter_ratio": max_jitter,
            "left_coverage": coverage["left"],
            "right_coverage": coverage["right"],
            "left_visible_frames": visible["left"],
            "right_visible_frames": visible["right"],
            "left_stability_frames": len(samples["left"]),
            "right_stability_frames": len(samples["right"]),
            "left_jitter_ratio": _rounded(jitter["left"]),
            "right_jitter_ratio": _rounded(jitter["right"]),
            "minimum_jitter_transitions": MIN_JITTER_TRANSITIONS,
        },
    }


def _rounded(value: Optional[float]) -> Optional[float]:
    return round(value, 4) if value is not None else None


def _validate_thresholds(min_confidence: float, min_coverage: float, max_jitter: float) -> None:
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence deve estar entre 0 e 1")
    if not 0.0 < min_coverage <= 1.0:
        raise ValueError("min_temporal_coverage deve estar em (0, 1]")
    if max_jitter <= 0.0:
        raise ValueError("max_jitter_ratio deve ser positivo")
