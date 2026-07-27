"""tools/pose_calibration/bootstrap_ci.py — IC bootstrap do MAE por backend (rigor no piloto).

O piloto Riglet (n=12) mostrou o MAE do 2D oscilando entre subconjuntos. Em vez de fingir que 12
basta, este tool quantifica: intervalo de confiança 95% do MAE de cada backend (bootstrap sobre os
corredores) e a diferença PAREADA por corredor (mesmo corredor nos dois backends) — com a pergunta
honesta: o IC da diferença cruza zero? Se cruza, n=12 não sustenta a alegação de superioridade.

Entrada: o `report.json`/`final_summary.json` do piloto (chave `rows`, cada uma com
`{backend: {"mae": float}}`). Sem dependências além da stdlib — determinístico com `seed`.
"""

import json
import random
import statistics as st
from pathlib import Path
from typing import Optional


def maes(rows: list, key: str) -> list:
    """MAE por corredor de um backend, pulando corredores sem esse backend."""
    return [r[key]["mae"] for r in rows if isinstance(r.get(key), dict) and "mae" in r[key]]


def bootstrap_ci(xs: list, n: int = 10000, seed: int = 42, alpha: float = 0.05) -> dict:
    """IC bootstrap da MÉDIA de `xs` (reamostragem com reposição)."""
    if not xs:
        raise ValueError("amostra vazia — nada para reamostrar")
    rng = random.Random(seed)
    means = sorted(st.mean(rng.choices(xs, k=len(xs))) for _ in range(n))
    lo = means[int((alpha / 2) * n)]
    hi = means[int((1 - alpha / 2) * n)]
    return {"mean": round(st.mean(xs), 2), "ci_low": round(lo, 2), "ci_high": round(hi, 2),
            "n": len(xs), "stdev": round(st.pstdev(xs), 2)}


def paired_diff_ci(a: list, b: list, n: int = 10000, seed: int = 42, alpha: float = 0.05) -> dict:
    """IC bootstrap da diferença PAREADA (a-b) por corredor. `significant` = o IC não cruza zero."""
    if len(a) != len(b) or not a:
        raise ValueError("amostras pareadas precisam do mesmo tamanho, não-vazio")
    diffs = [x - y for x, y in zip(a, b)]
    rng = random.Random(seed)
    boots = sorted(
        st.mean([diffs[i] for i in (rng.randrange(len(diffs)) for _ in diffs)]) for _ in range(n))
    lo, hi = boots[int((alpha / 2) * n)], boots[int((1 - alpha / 2) * n)]
    return {"mean_diff": round(st.mean(diffs), 2), "ci_low": round(lo, 2), "ci_high": round(hi, 2),
            "p_gt_0": round(sum(1 for m in boots if m > 0) / n, 3),
            "significant": bool(lo > 0 or hi < 0)}


def analyze(report_path: str, backends: Optional[list] = None) -> dict:
    rows = json.loads(Path(report_path).read_text())["rows"]
    backends = backends or ["yolo_2d", "blaze_2d", "blaze_3d"]
    series = {b: maes(rows, b) for b in backends}
    out = {"n_rows": len(rows), "per_backend": {b: bootstrap_ci(s) for b, s in series.items()},
           "paired": {}}
    for i in range(len(backends)):
        for j in range(i + 1, len(backends)):
            a, b = backends[i], backends[j]
            if len(series[a]) == len(series[b]) and series[a]:
                out["paired"][f"{a}_minus_{b}"] = paired_diff_ci(series[a], series[b])
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="IC bootstrap do MAE por backend (piloto de pose)")
    ap.add_argument("report", help="report.json/final_summary.json do piloto (com 'rows')")
    print(json.dumps(analyze(ap.parse_args().report), indent=2, ensure_ascii=False))
