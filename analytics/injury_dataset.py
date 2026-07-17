"""analytics/injury_dataset.py — a PONTE lesão ↔ histórico de análises (o dado do ML de risco).

A lesão é longitudinal: correlaciona com o PADRÃO biomecânico do atleta ANTES dela, não com um
vídeo só. Pra cada lesão reportada `(user, diagnóstico, onset_date)`, junta as análises daquele
atleta na janela ANTES da data → vira um exemplo rotulado `(X = fatores biomecânicos, y = lesão)`.

Dois usos:
  - `build_dataset()`: monta a tabela rotulada — o insumo do modelo TREINADO (XGBoost) quando
    houver casos suficientes.
  - `validate_literature_model()`: o que dá pra fazer JÁ com poucos casos — checa se as análises
    anteriores flaguearam os fatores que a taxonomia liga àquela lesão (face-validity do modelo de
    risco da literatura contra outcome REAL). É a validação honesta antes de treinar.
"""

import json
from datetime import timedelta

from core.database import get_connection
from analytics.biomechanics import ideal_targets, diagnose
from analytics.injury_taxonomy import factors_for, is_mapped

_FACTOR_KEYS = tuple(ideal_targets().keys())


def _analyses_before(con, user_id: str, onset, window_weeks: int) -> list:
    """Métricas (JSON) das análises 'done' daquele atleta na janela [onset-N semanas, onset]."""
    start = onset - timedelta(weeks=window_weeks)
    rows = con.execute(
        "SELECT metrics FROM form_analyses WHERE user_id = ? AND status = 'done' "
        "AND metrics IS NOT NULL AND CAST(created_at AS DATE) BETWEEN ? AND ?",
        [user_id, start, onset]).fetchall()
    return [json.loads(r[0]) for r in rows]


def _mean_features(metrics_list: list) -> dict:
    """Agrega os fatores biomecânicos pela MÉDIA na janela (feature vector estável por atleta)."""
    feats = {}
    for k in _FACTOR_KEYS:
        vals = [m[k] for m in metrics_list if m.get(k) is not None]
        if vals:
            feats[k] = round(sum(vals) / len(vals), 2)
    return feats


def build_dataset(window_weeks: int = 8) -> list:
    """Exemplos rotulados `(features, label)` — o insumo do modelo treinado. Só lesões com análise
    do atleta na janela anterior."""
    con = get_connection()
    injuries = con.execute(
        "SELECT user_id, diagnosis, region, onset_date FROM injury_reports "
        "WHERE onset_date IS NOT NULL AND user_id IS NOT NULL").fetchall()
    out = []
    for user_id, dx, region, onset in injuries:
        feats = _mean_features(_analyses_before(con, user_id, onset, window_weeks))
        if feats:
            out.append({"user_id": str(user_id), "label_dx": dx, "label_region": region,
                        "features": feats, "n_analyses": len(_analyses_before(con, user_id, onset, window_weeks))})
    return out


def validate_literature_model(window_weeks: int = 8) -> dict:
    """Face-validity do modelo de risco da literatura contra outcome real: pra cada lesão MAPEADA,
    as análises anteriores flaguearam os fatores que a taxonomia liga a ela?"""
    con = get_connection()
    targets = ideal_targets()
    injuries = con.execute(
        "SELECT user_id, diagnosis, onset_date FROM injury_reports "
        "WHERE onset_date IS NOT NULL AND user_id IS NOT NULL").fetchall()
    cases = []
    for user_id, dx, onset in injuries:
        if not (dx and is_mapped(dx)):
            continue
        expected = set(factors_for(dx))
        flagged = set()
        for m in _analyses_before(con, user_id, onset, window_weeks):
            for d in diagnose(m, targets):
                flagged.add(d["metric"])
        hit = expected & flagged
        cases.append({
            "diagnosis": dx, "expected_factors": sorted(expected),
            "flagged_before": sorted(hit), "n_analyses": len(_analyses_before(con, user_id, onset, window_weeks)),
            "hit_rate": round(len(hit) / len(expected), 2) if expected else None,
        })
    rated = [c["hit_rate"] for c in cases if c["hit_rate"] is not None]
    return {"cases": cases, "n": len(cases),
            "avg_hit_rate": round(sum(rated) / len(rated), 2) if rated else None}
