"""Roda um piloto Riglet auditável sem extrair o dataset inteiro.

Exemplo (a partir da raiz do repositório):
  .venv/bin/python tools/pose_calibration/run_riglet_pilot.py \
    /Users/user/strideredge_datasets/Data_Run_Walk.zip /tmp/riglet-pilot \
    --binary stride_vision/target/release/stride-vision \
    --yolo-model stride_vision/models/yolo11n-pose.onnx \
    --mediapipe-lib /tmp/strideredge-mediapipe/lib/python3.9/site-packages/mediapipe/tasks/c/libmediapipe.dylib \
    --blazepose-model /tmp/strideredge-mediapipe/pose_landmarker_full.task

O piloto compara YOLO em 2D com BlazePose em 2D nos MESMOS frames de eventos anotados. World-3D é
um modo diagnóstico explícito, nunca uma troca automática de métrica. A perna
de cada corredor é escolhida somente pela confiança combinada dos dois backends, nunca pelo erro
contra o mocap. Vídeos, dumps e CSVs ficam no diretório de saída e não devem entrar no Git.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

# Permite `python tools/pose_calibration/run_riglet_pilot.py ...` a partir de qualquer diretório,
# sem transformar `tools/` em pacote de produção.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.pose_calibration.calibrate import report
from tools.pose_calibration.riglet_adapter import (
    check_sync,
    condition_events_truth,
    run_pose,
    visible_leg_pair,
)


ROOT = "Data_Run_Walk"
CONDITION = "Overground_Run/Run_Comfortable"
VIDEO_NAME = "Video/Run_Comfortable.avi"
CSV_GLOB = "Post_Process/Run_Comfortable*.csv"


def _members_for_subject(archive: zipfile.ZipFile, subject: str, session: str) -> Tuple[str, List[str]]:
    """Retorna os membros mínimos para um corredor ou falha alto se o ZIP for incompleto."""
    base = f"{ROOT}/{subject}/{session}/{CONDITION}/"
    names = archive.namelist()
    video = base + VIDEO_NAME
    csvs = sorted(name for name in names if name.startswith(base + "Post_Process/")
                  and name.endswith(".csv") and Path(name).match("*Run_Comfortable*.csv"))
    if video not in names or not csvs:
        raise ValueError(f"{subject}: AVI/CSVs da condição {session}/{CONDITION} ausentes")
    return video, csvs


def available_subjects(archive_path: Path, session: str) -> List[str]:
    """IDs que têm AVI+CSV para a condição do piloto, em ordem estável."""
    with zipfile.ZipFile(archive_path) as archive:
        prefix = f"{ROOT}/"
        candidates = sorted({name[len(prefix):].split("/", 1)[0] for name in archive.namelist()
                             if name.startswith(prefix) and "/" in name[len(prefix):]})
        return [subject for subject in candidates if _has_members(archive, subject, session)]


def _has_members(archive: zipfile.ZipFile, subject: str, session: str) -> bool:
    try:
        _members_for_subject(archive, subject, session)
        return True
    except ValueError:
        return False


def extract_subject(archive_path: Path, subject: str, session: str, destination: Path) -> Tuple[Path, List[Path]]:
    """Extrai apenas um AVI e seus CSVs Post_Process, preservando os caminhos relativos."""
    with zipfile.ZipFile(archive_path) as archive:
        video_member, csv_members = _members_for_subject(archive, subject, session)
        for member in [video_member, *csv_members]:
            _extract_member_safely(archive, member, destination)
    base = destination / ROOT / subject / session / CONDITION
    return base / VIDEO_NAME, [base / member for member in [
        Path(name).relative_to(f"{ROOT}/{subject}/{session}/{CONDITION}") for name in csv_members
    ]]


def _extract_member_safely(archive: zipfile.ZipFile, member: str, destination: Path) -> Path:
    """Extrai um membro previamente selecionado sem permitir Zip Slip.

    O piloto aceita um ZIP externo de dataset. Mesmo membros filtrados pelo prefixo esperado são
    validados de novo antes da escrita para que ``..`` ou caminhos absolutos nunca escapem de
    ``destination``.
    """
    relative = Path(member)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"membro ZIP inseguro: {member!r}")
    target_root = destination.resolve()
    target = (target_root / relative).resolve()
    try:
        target.relative_to(target_root)
    except ValueError as exc:
        raise ValueError(f"membro ZIP fora do destino: {member!r}") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member) as source, target.open("wb") as output:
        shutil.copyfileobj(source, output)
    return target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def run_pilot(archive_path: Path, out_dir: Path, binary: Path, env: Dict[str, str], *,
              candidates: List[str], n_subjects: int, session: str, resume: bool = False,
              candidate_mode: str = "2d") -> dict:
    """Executa o piloto e persiste todos os insumos necessários para auditoria/reprodução."""
    if out_dir.exists() and any(out_dir.iterdir()) and not resume:
        raise ValueError(f"diretório de saída não está vazio: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted = out_dir / "input"
    dumps_dir = out_dir / "dumps"
    dumps_dir.mkdir(exist_ok=resume)
    events, truth, legs, sync = {}, {}, {}, {}
    accepted, excluded = [], {}

    for subject in candidates:
        if len(accepted) >= n_subjects:
            break
        yolo_path = dumps_dir / f"{subject}.yolo17.frames.json"
        blaze_path = dumps_dir / f"{subject}.blazepose33.frames.json"
        base = extracted / ROOT / subject / session / CONDITION
        csvs = sorted((base / "Post_Process").glob("Run_Comfortable*.csv"))
        avi = base / VIDEO_NAME
        if not avi.is_file() or not csvs:
            avi, csvs = extract_subject(archive_path, subject, session, extracted)
        if not yolo_path.is_file():
            run_pose(str(binary), str(avi), "yolo17", str(yolo_path), env)
        if not blaze_path.is_file():
            run_pose(str(binary), str(avi), "blazepose33", str(blaze_path), env)
        yolo, blaze = _load(yolo_path), _load(blaze_path)
        leg = visible_leg_pair(yolo, blaze)
        frames, subject_truth = condition_events_truth([str(path) for path in csvs], leg)
        subject_sync = check_sync(str(yolo_path), frames, leg)
        if not subject_sync["ok"]:
            excluded[subject] = {**subject_sync, "reason": "sincronia insuficiente"}
            continue
        events[subject], truth[subject], legs[subject], sync[subject] = (
            frames, subject_truth, leg, subject_sync)
        accepted.append(subject)

    if len(accepted) < n_subjects:
        raise RuntimeError(f"só {len(accepted)} corredores passaram o gate de sincronia; "
                           f"meta era {n_subjects}. Excluídos: {excluded}")

    (out_dir / "events.json").write_text(json.dumps(events, indent=2, sort_keys=True))
    (out_dir / "truth.json").write_text(json.dumps(truth, indent=2, sort_keys=True))
    (out_dir / "legs.json").write_text(json.dumps(legs, indent=2, sort_keys=True))
    (out_dir / "sync.json").write_text(json.dumps(sync, indent=2, sort_keys=True))
    (out_dir / "excluded.json").write_text(json.dumps(excluded, indent=2, sort_keys=True))
    dumps = {}
    for subject in accepted:
        dumps[subject] = {
            "yolo17": _load(dumps_dir / f"{subject}.yolo17.frames.json"),
            "blazepose33": _load(dumps_dir / f"{subject}.blazepose33.frames.json"),
        }
    result = report(dumps, "yolo17", "blazepose33", events=events, truth=truth, legs=legs,
                    baseline_mode="2d", candidate_mode=candidate_mode)
    result["pilot"] = {
        "archive": str(archive_path), "archive_sha256": sha256(archive_path),
        "subjects": accepted, "excluded": excluded, "session": session, "condition": CONDITION,
        "selection": "12 IDs ordenados com AVI+CSV; perna por confiança combinada dos backends",
        "assets": {key: env[key] for key in ("STRIDE_MODEL", "STRIDE_MEDIAPIPE_LIB",
                                                "STRIDE_BLAZEPOSE_MODEL")},
    }
    (out_dir / "report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False,
                                                       sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Piloto Riglet pareado e auditável")
    parser.add_argument("archive", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--yolo-model", type=Path, required=True)
    parser.add_argument("--mediapipe-lib", type=Path, required=True)
    parser.add_argument("--blazepose-model", type=Path, required=True)
    parser.add_argument("--session", default="Session1")
    parser.add_argument("--n-subjects", type=int, default=12)
    parser.add_argument("--resume", action="store_true",
                        help="reaproveita dumps já existentes no diretório de saída")
    parser.add_argument("--candidate-mode", choices=["2d", "world_3d"], default="2d",
                        help="geometria avaliada do BlazePose; produção usa image_2d")
    args = parser.parse_args()
    if not args.archive.is_file() or not args.binary.is_file():
        raise SystemExit("archive ou binário não encontrado")
    if not args.yolo_model.is_file() or not args.mediapipe_lib.is_file() or not args.blazepose_model.is_file():
        raise SystemExit("modelo YOLO, runtime ou modelo BlazePose não encontrado")
    candidates = available_subjects(args.archive, args.session)
    if len(candidates) < args.n_subjects:
        raise SystemExit(f"só há {len(candidates)} corredores completos para {args.session}")
    env = {**os.environ, "STRIDE_MODEL": str(args.yolo_model),
           "STRIDE_MEDIAPIPE_LIB": str(args.mediapipe_lib),
           "STRIDE_BLAZEPOSE_MODEL": str(args.blazepose_model)}
    result = run_pilot(args.archive, args.out_dir, args.binary, env, candidates=candidates,
                       n_subjects=args.n_subjects, session=args.session, resume=args.resume,
                       candidate_mode=args.candidate_mode)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
