"""Prepara uma âncora manual mínima para comparar pose em vídeos próprios.

Extrai poucos frames de apoio, nunca o vídeo inteiro, e organiza os dumps BlazePose/YOLO no formato
de ``calibrate.py``. A anotação resultante é sanity check de engenharia, não ground truth clínico.
"""

import argparse
import csv
import json
import shutil
import subprocess
from pathlib import Path
from statistics import mean


_KP_CONF = 0.5


def _point(record: dict, name: str):
    point = (record.get("kp") or {}).get(name)
    if not isinstance(point, list) or len(point) < 3:
        return None
    return point if all(isinstance(value, (int, float)) for value in point[:3]) else None


def choose_leg(dump: dict) -> str:
    """Escolhe a perna mais visível sem olhar a verdade manual."""
    scores = {"l": [], "r": []}
    for record in dump.get("frames", []):
        if not record.get("present"):
            continue
        for leg in scores:
            points = [_point(record, f"{joint}_{leg}") for joint in ("hip", "knee", "ankle")]
            if all(points):
                scores[leg].append(min(point[2] for point in points))
    return max(scores, key=lambda leg: mean(scores[leg]) if scores[leg] else -1.0)


def _ground_y(record: dict, leg: str):
    heel, toe = _point(record, f"heel_{leg}"), _point(record, f"big_toe_{leg}")
    if heel and toe and heel[2] >= _KP_CONF and toe[2] >= _KP_CONF:
        return max(heel[1], toe[1])
    ankle = _point(record, f"ankle_{leg}")
    return ankle[1] if ankle and ankle[2] >= _KP_CONF else None


def select_contact_frames(dump: dict, leg: str, count: int) -> list:
    """Escolhe máximos locais do ponto mais baixo do pé, distribuídos pelo clipe.

    É somente um seletor de frames para a pessoa anotar; não declara evento clínico nem usa o YOLO
    como referência. A regra de separação evita vários frames do mesmo apoio.
    """
    fps = float(dump.get("fps") or 30.0)
    values = [(int(record["i"]), _ground_y(record, leg)) for record in dump.get("frames", [])]
    values = [(frame, value) for frame, value in values if value is not None]
    min_separation = max(1, round(fps * 0.25))
    peaks = []
    for index in range(1, len(values) - 1):
        frame, value = values[index]
        if value >= values[index - 1][1] and value > values[index + 1][1]:
            if not peaks or frame - peaks[-1][0] >= min_separation:
                peaks.append((frame, value))
            elif value > peaks[-1][1]:
                peaks[-1] = (frame, value)
    if not peaks:
        raise ValueError("não encontrei apoios confiáveis para selecionar frames")
    if len(peaks) <= count:
        return [frame for frame, _ in peaks]
    positions = [round(index * (len(peaks) - 1) / (count - 1)) for index in range(count)]
    return [peaks[index][0] for index in positions]


def _extract_frame(video: Path, frame: int, fps: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # Seek APÓS o input é mais lento que seek por keyframe, mas é preciso: a anotação precisa cair
    # no mesmo frame temporal do dump. São só seis imagens por clipe, fora do caminho do produto.
    timestamp_s = frame / fps
    result = subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(video), "-ss", f"{timestamp_s:.9f}",
        "-frames:v", "1", str(output),
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg não extraiu frame {frame}: {result.stderr.strip()[-300:]}")
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg não gerou frame {frame}")


def prepare(inputs: list, out_dir: str, count: int = 6) -> dict:
    """Gera template único de anotação e dumps prontos para ``calibrate.py``."""
    root = Path(out_dir)
    dumps_dir, frames_dir = root / "dumps", root / "frames"
    rows, legs, selected = [], {}, {}
    for clip, video_raw, blaze_raw, yolo_raw in inputs:
        video, blaze_path, yolo_path = Path(video_raw), Path(blaze_raw), Path(yolo_raw)
        if not video.is_file() or not blaze_path.is_file() or not yolo_path.is_file():
            raise FileNotFoundError(f"{clip}: vídeo ou dump ausente")
        blaze = json.loads(blaze_path.read_text())
        leg = choose_leg(blaze)
        frames = select_contact_frames(blaze, leg, count)
        fps = float(blaze.get("fps") or 30.0)
        legs[clip], selected[clip] = leg, frames
        for frame in frames:
            _extract_frame(video, frame, fps, frames_dir / clip / f"frame_{frame:06d}.png")
            rows.append({"clip": clip, "frame": frame, "joint": "knee", "angle_deg": "", "side": leg})
        dumps_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(blaze_path, dumps_dir / f"{clip}.blazepose33.frames.json")
        shutil.copyfile(yolo_path, dumps_dir / f"{clip}.yolo17.frames.json")
    csv_path = root / "annotations.template.csv"
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("clip", "frame", "joint", "angle_deg", "side"))
        writer.writeheader()
        writer.writerows(rows)
    (root / "legs.json").write_text(json.dumps(legs, indent=2))
    (root / "README.txt").write_text(
        "Preencha angle_deg no CSV com o ângulo INTERNO do joelho (180 = reto), olhando os PNGs.\n"
        "Depois: annotations_to_truth.py annotations.csv truth/ e calibrate.py dumps/ --events ...\n"
        "Isto é uma âncora manual fraca de engenharia, não validação clínica.\n")
    return {"clips": len(inputs), "frames": selected, "legs": legs,
            "csv": str(csv_path), "dumps_dir": str(dumps_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepara frames/CSV para anotação manual de joelho")
    parser.add_argument("--input", nargs=4, action="append", metavar=("CLIP", "VIDEO", "BLAZE", "YOLO"),
                        required=True, help="repita: id do clipe, vídeo, dump Blaze, dump YOLO")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--count", type=int, default=6)
    args = parser.parse_args()
    if args.count < 2:
        parser.error("--count deve ser pelo menos 2")
    print(json.dumps(prepare(args.input, args.out_dir, args.count), ensure_ascii=False, indent=2))
