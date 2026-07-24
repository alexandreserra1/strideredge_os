#!/usr/bin/env python3
"""Roda RTMDet + RTMPose Halpe26 via ONNX Runtime e produz o JSON do spike.

Usa ``rtmlib`` (Apache-2.0), que chama os ONNX oficiais do OpenMMLab sem trazer MMPose, MMCV ou
MMDetection para o runtime. É a referência local do experimento; produção continuará sendo uma
implementação Rust do mesmo pipeline ONNX, após os gates de qualidade e performance.
"""

import argparse
import json
import os
from time import perf_counter
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# URLs publicadas pelo OpenMMLab; os .zip contêm os ONNX e metadados usados pelo rtmlib.
DETECTOR_URL = (
    "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/"
    "yolox_m_8xb8-300e_humanart-c2c7a14a.zip"
)
POSE_URL = (
    "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/"
    "rtmpose-m_simcc-body7_pt-body7-halpe26_700e-256x192-4d3e73dd_20230605.zip"
)


def normalize_keypoints(keypoints: Any, scores: Any) -> Dict[str, Any]:
    """Converte a saída do runtime na entrada estável de ``validate.py``.

    O score do SimCC é uma ativação, não uma probabilidade calibrada; em alguns frames ele passa
    levemente de 1. O contrato público é uma confiança limitada a [0, 1], por isso só saturamos
    os extremos aqui — as coordenadas e a ordenação do modelo ficam intactas.
    """
    def bounded_confidence(value: Any) -> float:
        value = float(value)
        return max(0.0, min(1.0, value))

    return {
        "instances": [
            {
                "keypoints": points.tolist(),
                "scores": [bounded_confidence(score) for score in confidence.tolist()],
            }
            for points, confidence in zip(keypoints, scores)
        ]
    }


def build_pipeline(device: str):
    """Carrega o detector e o pose model uma única vez para uma sequência de frames."""
    # rtmlib baixa seus ONNX em XDG_CACHE_HOME. No spike não escrevemos em ~/.cache nem no repo.
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/strideredge-halpe26-cache")
    from rtmlib import Custom

    return Custom(
        det_class="YOLOX", det=DETECTOR_URL, det_input_size=(640, 640),
        pose_class="RTMPose", pose=POSE_URL, pose_input_size=(192, 256),
        backend="onnxruntime", device=device,
    )


def run(
    image: Path, output: Path, device: str = "mps", iterations: int = 1,
    overlay: Optional[Path] = None,
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """Executa a mesma imagem repetidas vezes, reutilizando as sessões ONNX.

    ``init_seconds`` é separado da latência por frame: a primeira mede a carga/compilação do
    CoreML; ``inference_ms_per_frame`` é a medida que interessa para processar um vídeo.
    """
    if iterations < 1:
        raise ValueError("iterations deve ser maior ou igual a 1")
    import cv2

    frame = cv2.imread(str(image))
    if frame is None:
        raise ValueError(f"não foi possível ler a imagem: {image}")
    init_start = perf_counter()
    pipeline = build_pipeline(device)
    init_seconds = perf_counter() - init_start
    infer_start = perf_counter()
    for _ in range(iterations):
        keypoints, scores = pipeline(frame)
    inference_seconds = perf_counter() - infer_start
    report = normalize_keypoints(keypoints, scores)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if overlay is not None:
        from rtmlib import draw_skeleton
        rendered = draw_skeleton(frame.copy(), keypoints, scores, kpt_thr=0.35)
        if not cv2.imwrite(str(overlay), rendered):
            raise ValueError(f"não foi possível escrever o overlay: {overlay}")
    return report, {
        "init_seconds": init_seconds,
        "inference_ms_per_frame": (inference_seconds / iterations) * 1000,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--iterations", type=int, default=1,
                        help="repetições sobre a mesma imagem para medir inferência aquecida")
    parser.add_argument("--overlay", type=Path,
                        help="PNG/JPEG opcional para revisão humana do esqueleto Halpe26")
    args = parser.parse_args()
    report, timings = run(args.image, args.output, args.device, args.iterations, args.overlay)
    print(json.dumps({"instances": len(report["instances"]), "output": str(args.output),
                      "iterations": args.iterations, **timings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
