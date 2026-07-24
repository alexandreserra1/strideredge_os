#!/usr/bin/env python3
"""Mede Halpe26 em uma sequência de vídeo e gera a entrada do ``benchmark.py``.

É um runner de avaliação, não o processador de produção: amostra frames a uma frequência fixa,
reutiliza as sessões ONNX e registra quantos frames mantêm os seis pontos semânticos do pé.
"""

import argparse
import json
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Tuple


def sample_stride(source_fps: float, sample_fps: float) -> int:
    """Número de frames pulados entre as amostras, sempre ao menos um."""
    if source_fps <= 0 or sample_fps <= 0:
        raise ValueError("source_fps e sample_fps devem ser positivos")
    return max(1, round(source_fps / sample_fps))


def oriented_dimensions(width: int, height: int, rotation: int) -> Tuple[int, int]:
    """Espelha a geometria que o ffmpeg auto-rotacionado entrega no pipe rawvideo."""
    return (height, width) if rotation % 180 else (width, height)


def probe(video: Path) -> Tuple[int, int, float]:
    """Lê a mesma geometria/FPS que o benchmark Rust usa para decodificar o vídeo."""
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height,r_frame_rate:stream_side_data=rotation", "-of", "csv=p=0", str(video),
    ]
    row = subprocess.check_output(command, text=True).strip().split(",")
    if len(row) < 3:
        raise ValueError("ffprobe não retornou dimensões e FPS do vídeo")
    numerator, denominator = (float(part) for part in row[2].split("/"))
    rotation = int(row[3]) if len(row) > 3 and row[3].lstrip("-").isdigit() else 0
    width, height = oriented_dimensions(int(row[0]), int(row[1]), rotation)
    return width, height, numerator / denominator


def summarize_samples(reports: Iterable[Dict[str, Any]], min_visible_rate: float) -> Dict[str, Any]:
    reports = list(reports)
    if not reports:
        raise ValueError("o vídeo não produziu frames amostrados")
    valid = sum(bool(report["valid"]) for report in reports)
    feet = sum(bool(report["instances_with_all_foot_points"]) for report in reports)
    visible_rate = feet / len(reports)
    return {
        "sampled_frames": len(reports),
        "structurally_valid_frames": valid,
        "foot_points_visible_frames": feet,
        "foot_points_visible_rate": round(visible_rate, 4),
        "reliable": valid == len(reports) and visible_rate >= min_visible_rate,
        "foot_points_visible": feet > 0,
    }


def run_video(
    video: Path, device: str = "mps", sample_fps: float = 5.0, min_visible_rate: float = 0.8,
) -> Dict[str, Any]:
    """Retorna um documento de benchmark para um vídeo sem persistir frames do atleta."""
    import numpy as np
    from run_reference import build_pipeline, normalize_keypoints
    from validate import validate_instances

    width, height, source_fps = probe(video)
    stride = sample_stride(source_fps, sample_fps)
    bytes_per_frame = width * height * 3
    decoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE,
    )
    if decoder.stdout is None:
        raise RuntimeError("não foi possível abrir stdout do ffmpeg")

    init_start = perf_counter()
    pipeline = build_pipeline(device)
    init_seconds = perf_counter() - init_start
    reports: List[Dict[str, Any]] = []
    infer_start = perf_counter()
    frame_number = 0
    try:
        while True:
            raw = decoder.stdout.read(bytes_per_frame)
            if not raw:
                break
            if len(raw) != bytes_per_frame:
                raise ValueError("ffmpeg entregou um frame de tamanho incompleto")
            if frame_number % stride == 0:
                frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3)).copy()
                keypoints, scores = pipeline(frame)
                reports.append(validate_instances(normalize_keypoints(keypoints, scores)))
            frame_number += 1
    finally:
        decoder.stdout.close()
        if decoder.wait() != 0:
            raise RuntimeError("ffmpeg falhou ao decodificar o vídeo")
    wall_seconds = perf_counter() - infer_start
    summary = summarize_samples(reports, min_visible_rate)
    run = {
        "video": video.name,
        "frames": summary.pop("sampled_frames"),
        "wall_seconds": wall_seconds,
        "measurement_stage": "decode+pose_inference",
        "source_fps": source_fps,
        "sample_stride": stride,
        "source_frames": frame_number,
        "init_seconds": init_seconds,
        **summary,
    }
    return {"runs": [run], "human_overlay_review_required": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--sample-fps", type=float, default=5.0)
    parser.add_argument("--min-visible-rate", type=float, default=0.8)
    args = parser.parse_args()
    report = run_video(args.video, args.device, args.sample_fps, args.min_visible_rate)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
