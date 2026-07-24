#!/usr/bin/env python3
"""Valida uma amostra NORMALIZADA de keypoints Halpe26 antes de ela tocar o motor Rust.

Entrada JSON esperada:
{"instances": [{"keypoints": [[x, y], ... 26 vezes], "scores": [0.0, ... 26 vezes]}]}

O conversor MMPose/MMDeploy deve transformar sua saída nesse formato simples. Esta ferramenta
não afirma precisão clínica: ela trava apenas o contrato estrutural, a presença dos seis pontos de
pé e a necessidade de revisão humana do overlay.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List


KEYPOINT_NAMES = (
    "nariz", "olho_e", "olho_d", "orelha_e", "orelha_d", "ombro_e", "ombro_d",
    "cotovelo_e", "cotovelo_d", "punho_e", "punho_d", "quadril_e", "quadril_d",
    "joelho_e", "joelho_d", "tornozelo_e", "tornozelo_d", "cabeca", "pescoco",
    "quadril_c", "hallux_e", "hallux_d", "dedinho_e", "dedinho_d", "calcanhar_e",
    "calcanhar_d",
)
FOOT_INDICES = (20, 21, 22, 23, 24, 25)


def validate_instances(document: Dict[str, Any], min_confidence: float = 0.35) -> Dict[str, Any]:
    """Retorna um relatório serializável; erros estruturais não dependem de MMPose instalado."""
    instances = document.get("instances")
    if not isinstance(instances, list):
        return {"valid": False, "errors": ["instances deve ser uma lista"], "instances": 0}

    errors: List[str] = []
    feet_visible = 0
    for number, instance in enumerate(instances):
        points = instance.get("keypoints") if isinstance(instance, dict) else None
        scores = instance.get("scores") if isinstance(instance, dict) else None
        if not isinstance(points, list) or len(points) != len(KEYPOINT_NAMES):
            errors.append(f"instância {number}: esperado {len(KEYPOINT_NAMES)} keypoints")
            continue
        if not isinstance(scores, list) or len(scores) != len(KEYPOINT_NAMES):
            errors.append(f"instância {number}: esperado {len(KEYPOINT_NAMES)} scores")
            continue
        malformed = False
        for index, point in enumerate(points):
            if (not isinstance(point, list) or len(point) != 2
                    or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in point)):
                errors.append(f"instância {number}: keypoint {index} inválido")
                malformed = True
                break
        if malformed:
            continue
        if any(not isinstance(score, (int, float)) or not 0.0 <= score <= 1.0 for score in scores):
            errors.append(f"instância {number}: scores devem estar entre 0 e 1")
            continue
        if all(scores[index] >= min_confidence for index in FOOT_INDICES):
            feet_visible += 1

    return {
        "valid": not errors,
        "errors": errors,
        "instances": len(instances),
        "instances_with_all_foot_points": feet_visible,
        "minimum_keypoint_confidence": min_confidence,
        "keypoint_order": list(KEYPOINT_NAMES),
        "human_review_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path, help="JSON normalizado pelo conversor MMPose")
    parser.add_argument("--min-confidence", type=float, default=0.35)
    parser.add_argument("--strict-feet", action="store_true", help="falha se nenhum atleta tem os seis pontos visíveis")
    args = parser.parse_args()
    report = validate_instances(json.loads(args.predictions.read_text()), args.min_confidence)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] and (not args.strict_feet or report["instances_with_all_foot_points"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
