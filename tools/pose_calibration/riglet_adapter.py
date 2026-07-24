"""tools/pose_calibration/riglet_adapter.py — ingere o dataset Riglet (CC0) → arnês de calibração.

Transforma um trial/condição de corrida do Riglet nos JSONs que `calibrate.py` consome:
  - roda os DOIS backends de pose no AVI → dumps por-frame (`<subject>.<backend>.frames.json`);
  - extrai do CSV Post_Process a VERDADE (flexão sagital de joelho/quadril) e os EVENTOS anotados
    (Foot_Strike/Foot_Off) → `events.json` + `truth.json`, com o ângulo no MESMO frame/evento.

Fatos confirmados nos arquivos reais (ver RIGLET_ADAPTER_DESIGN.md):
  - vídeo mpeg4 644×366 @50 fps (overground); mocap 100 Hz; eventos em TEMPO ABSOLUTO → frame do
    vídeo = round(t × 50);
  - CSV: meta (linhas k,v) → blank → eventos → blank → rótulos(`Time,LABEL,,,...`)/unidades/`X,Y,Z`
    → 192 linhas de pontos (Time col 0). Ângulo: coluna X de `RKneeAngles`/`RHipAngles`/`L...`,
    em FLEXÃO (0°=reto) → nosso INTERNO = 180 − flexão (validado: strike ~172°, apoio médio ~140°).

Puro-CSV, sem dependência nova. Não coloca vídeo/dado do dataset no Git. `--check-sync` valida a
sincronia vídeo↔mocap comparando os apoios da POSE com os Foot_Strike anotados antes de confiar.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

VIDEO_FPS = 50.0                       # ffprobe: mpeg4 644x366 @50 (overground Riglet)
SIDE_LABEL = {"r": "Right", "l": "Left"}


# ----------------------------- parsing do CSV Post_Process -----------------------------

def parse_post_process_csv(path: str) -> dict:
    """Lê um CSV Post_Process → {meta, events{label:[tempos]}, times[], flex{(side,joint):[graus]}}.
    `flex` é a FLEXÃO (coluna X) por frame de mocap; o interno é 180−flex (feito na leitura da verdade)."""
    lines = Path(path).read_text().splitlines()
    meta, events, i = {}, {}, 0
    while i < len(lines) and lines[i] and not lines[i].startswith(("Right_", "Left_", "Time,")):
        k, v = lines[i].split(",", 1)
        meta[k] = v
        i += 1
    while i < len(lines) and not lines[i].startswith("Time,"):
        if lines[i].startswith(("Right_", "Left_")):
            parts = [p for p in lines[i].split(",") if p != ""]
            events[parts[0]] = [float(x) for x in parts[1:]]
        i += 1
    labels = lines[i].split(",")                       # linha de rótulos
    col = {name: labels.index(name) for name in
           ("Time", "RKneeAngles", "RHipAngles", "LKneeAngles", "LHipAngles") if name in labels}
    rows = []
    for l in lines[i + 3:]:                             # +1 unidades, +2 X/Y/Z, +3 dados
        if l.strip() == "":
            break
        rows.append(l.split(","))
    times = [float(r[col["Time"]]) for r in rows]
    flex = {}
    for side in ("R", "L"):
        for joint in ("Knee", "Hip"):
            c = col.get(f"{side}{joint}Angles")
            if c is not None:
                flex[(side.lower(), joint.lower())] = [
                    float(r[c]) if r[c] not in ("", None) else None for r in rows]
    return {"meta": meta, "events": events, "times": times, "flex": flex}


def _nearest(times: list, t: float) -> int:
    return min(range(len(times)), key=lambda k: abs(times[k] - t))


def truth_interior(parsed: dict, side: str, joint: str, t: float) -> Optional[float]:
    """Ângulo INTERNO (180−flexão) da `side`/`joint` no instante `t` (frame de mocap mais próximo)."""
    series = parsed["flex"].get((side, joint))
    if not series:
        return None
    v = series[_nearest(parsed["times"], t)]
    return round(180.0 - v, 1) if v is not None else None


def strike_times(parsed: dict, side: str) -> list:
    """Tempos de contato inicial (Foot_Strike) da perna `side` (l|r)."""
    return list(parsed["events"].get(f"{SIDE_LABEL[side]}_Foot_Strike", []))


def midstance_times(parsed: dict, side: str) -> list:
    """Apoio médio ≈ meio entre cada Foot_Strike e o Foot_Off seguinte da mesma perna."""
    strikes = strike_times(parsed, side)
    offs = sorted(parsed["events"].get(f"{SIDE_LABEL[side]}_Foot_Off", []))
    out = []
    for s in strikes:
        nxt = next((o for o in offs if o > s), None)
        if nxt is not None:
            out.append((s + nxt) / 2.0)
    return out


# ----------------------------- eventos + verdade → JSONs do arnês -----------------------------

def condition_events_truth(csv_paths: list, side: str, event: str = "strike",
                           fps: float = VIDEO_FPS) -> tuple:
    """Agrega os N trials de UMA condição (compartilham 1 AVI) → (frames_de_evento_no_vídeo,
    {joint: {frame: interno}}). `event` = strike | midstance. Mede a perna `side`."""
    frames, truth = [], {"knee": {}, "hip": {}}
    for path in csv_paths:
        p = parse_post_process_csv(path)
        times = strike_times(p, side) if event == "strike" else midstance_times(p, side)
        for t in times:
            f = round(t * fps)
            frames.append(f)
            for joint in ("knee", "hip"):
                v = truth_interior(p, side, joint, t)
                if v is not None:
                    truth[joint][f] = v
    return sorted(set(frames)), truth


def visible_leg(dump: dict) -> str:
    """Perna VISÍVEL (a da frente na lateral) = maior confiança somada de joelho+tornozelo. A de
    trás é ocluída e não-confiável — comparar ela contra o mocac é ruído (é o que inflava o MAE)."""
    tot = {"l": 0.0, "r": 0.0}
    for rec in dump.get("frames", []):
        kp = rec.get("kp") if rec.get("present") else None
        if not kp:
            continue
        for leg in ("l", "r"):
            tot[leg] += sum(kp[n][2] for n in (f"knee_{leg}", f"ankle_{leg}") if n in kp)
    return "r" if tot["r"] >= tot["l"] else "l"


def run_pose(binary: str, avi: str, backend: str, out_json: str, env: dict) -> None:
    """Roda o motor Rust no AVI com STRIDE_DUMP_SERIES → dump por-frame do backend. Falha alto."""
    overlay = str(Path(out_json).with_suffix(".overlay.mp4"))
    r = subprocess.run(
        [binary, avi, overlay, "--view", "lateral", "--backend", backend, "--no-overlay"],
        env={**env, "STRIDE_DUMP_SERIES": out_json}, capture_output=True, text=True, timeout=1200)
    if r.returncode != 0:
        raise RuntimeError(f"motor falhou ({backend}): {r.stderr.strip()[-300:]}")


def build_condition(subject: str, csv_paths: list, avi: str, out_dir: str, side: str,
                    binary: str, env: dict, backends=("yolo17", "blazepose33"),
                    event: str = "strike") -> dict:
    """Monta uma condição: roda os backends no AVI (1×) + emite events/truth. Devolve um resumo.
    Escreve `<subject>.<backend>.frames.json` no out_dir; acumula events/truth (o chamador junta)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for backend in backends:
        run_pose(binary, avi, backend, str(out / f"{subject}.{backend}.frames.json"), env)
    frames, truth = condition_events_truth(csv_paths, side, event)
    return {"subject": subject, "n_events": len(frames), "frames": frames, "truth": truth}


def check_sync(pose_dump_path: str, strike_frames: list, side: str, tol_frames: int = 6) -> dict:
    """Valida a sincronia vídeo↔mocap SEM confiar: os APOIOS que a pose detecta (mínimo vertical do
    tornozelo = pé no chão) devem cair perto dos Foot_Strike anotados (com um pequeno lag strike→apoio).
    Devolve o lag mediano e a fração de eventos casados dentro de `tol_frames`."""
    dump = json.loads(Path(pose_dump_path).read_text())
    ankle = f"ankle_{side}"
    ys = {r["i"]: r["kp"][ankle][1] for r in dump["frames"]
          if r.get("present") and ankle in (r.get("kp") or {})}
    idx = sorted(ys)
    contacts = [idx[k] for k in range(1, len(idx) - 1)
                if ys[idx[k]] >= ys[idx[k - 1]] and ys[idx[k]] > ys[idx[k + 1]]]
    lags = []
    for s in strike_frames:
        near = min(contacts, key=lambda c: abs(c - s)) if contacts else None
        if near is not None and abs(near - s) <= max(tol_frames, 8):
            lags.append(near - s)
    matched = len(lags) / len(strike_frames) if strike_frames else 0.0
    lags.sort()
    return {"n_strikes": len(strike_frames), "matched_frac": round(matched, 2),
            "median_lag_frames": lags[len(lags) // 2] if lags else None,
            "ok": matched >= 0.6}
